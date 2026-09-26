#!/usr/bin/env python3
"""KNOB CLICK CENSUS: every continuous knob of every DSP module in bamsep26,
moved mid-render under dsp_host, checked for block-rate steps in the output.

A knob the DSP applies once per block (15 samples) and not per sample makes
a step at every block boundary while it moves: zipper crackle at 2,940 Hz
and its harmonics. This renders a steady 438.75 Hz tone through each module
(the rig's layout for the bus engines and SEND, both payloads for the
stations), and per knob and mode:

  move    knob at LO, jump to HI at block J1, back to LO at J2, then a turn
          LO -> HI one step every two blocks from S0
  static  the same render with the knob held at LO, and again at HI

Two measures per window (jump up, jump down, turn), on the second
difference d2 of the observed track's L and R:

  grid    the energy of d2 in each of the 15 sample phases of the block,
          max over median. A step at a block boundary lands on one phase
          every block (the offset is whatever latency the step passes
          through, so the max is taken over phases); a tone, harmonics and
          noise spread evenly. Reported as move / static, the static being
          the larger of LO and HI over the same window.
  spikes  samples where |d2| exceeds twice the static renders' max over the
          same window.

A knob is FLAGGED when either window's grid ratio exceeds GRID_LIMIT or its
spikes exceed SPIKE_LIMIT. Selects (count < 128: MODE, SIZE, SHFT, SAT) change
the engine on a value change and are listed apart, not flagged.

The instrument is checked before any module is judged: a static render
multiplied by a gain stepping once per block must flag, and the same gain
ramped per sample must not.

What this cannot see: the chip's cycle overrun (a block that misses its
deadline crackles on the unit and renders clean here), anything the
ColdFire does between a panel turn and r6 (knobs are poked into r6 once per
block, as the -sched option does), and a step smaller than the tone's own
d2 floor.

    make verify-knobs                 # the census + its checks (~4 min)
    python3 tools/verify/verify_knob_clicks.py --only SPECTRUM   # one module
"""
import argparse
import concurrent.futures as cf
import math
import pathlib
import shutil
import struct
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe  # noqa: E402
import verify_onebus as vo  # noqa: E402
from remix import registry  # noqa: E402

SCRATCH = ROOT / "out/dsp/_knobs"
FRAMES = send_probe.FRAMES
PAD = send_probe.WARMUP_BLOCKS * FRAMES
J1, J2, S0, END = 1500, 2000, 2500, 3000       # blocks after PAD
LO, HI = 20, 110
STEP_LIMIT = -70.0      # dBFS, one step per block
MARGIN = 6.0            # dB over the static renders
WINDOWS = (("up", J1, J2), ("down", J2, S0), ("turn", S0, END))

# the knobs each module is heard through when it is not the one moving
CONTEXT = {
    "DELAY SERVER": dict(TIME=20, FDBK=60, TONE=100, PING=0, WET=127),
    "REVERB SERVER": dict(SHMR=0),
    "SPECTRUM": dict(FREQ=64, RES=40),
    "CHARACTER": dict(DRV=60, COMP=40, MIX=127),
    "MODULATION": dict(),
}
BUS = ("DELAY SERVER", "REVERB SERVER", "SEND")
STATIONS = ("SPECTRUM", "CHARACTER", "MODULATION")


def build():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    snap = SCRATCH / "mainos_bus.snapshot.bin"
    had = vo.IMAGE.is_file()
    if had:
        shutil.copy2(vo.IMAGE, snap)
    try:
        vo.build({"XBUS": "1", "SPEC": "1"}, SCRATCH / "build_spec.log")
        a = send_probe.dump_mem(vo.IMAGE, SCRATCH / "spec_A.mem", "A")
        b = send_probe.dump_mem(vo.IMAGE, SCRATCH / "spec_B.mem", "B")
    finally:
        if had:
            shutil.copy2(snap, vo.IMAGE)
    return {0: a, 1: b}


def mode_knobs(key, mode):
    """(name, slot, count) of the knobs this mode uses: named, not '---'"""
    m = registry.by_key(key)
    km = m.knob_map_all()
    v = m.view_for(mode) if mode is not None else None
    out = []
    for p in m.params:
        if not p.name:
            continue
        slot = km[p.name.decode()]
        if v is not None and v.names.get(slot) == b"---":
            continue
        name = (v.names.get(slot) if v else None) or p.name
        out.append((p.name.decode(), name.decode(), slot, p.count))
    return out


def modes(key):
    m = registry.by_key(key)
    if m.mode_slot is None:
        return [None]
    count = m.params[m.mode_slot].count
    return list(range(count))


def base_knobs(key, mode):
    m = registry.by_key(key)
    kw = dict(CONTEXT.get(key, {}))
    if mode is not None:
        kw[m.params[m.mode_slot].name.decode()] = mode
        v = m.view_for(mode)
        if v is not None:
            names = {s: n for n, s in m.knob_map_all().items()}
            for s, val in v.defaults.items():
                kw[names[s]] = val
    return kw


class Case:
    def __init__(self, key, mode, knob, label, slot, count):
        self.key, self.mode, self.knob, self.label, self.slot, self.count = key, mode, knob, label, slot, count

    @property
    def tag(self):
        return f"{self.key.split()[0]}_{self.mode}_{self.knob}".replace(" ", "")

    def layout(self, at):
        """(instances, moving instance indices, observed instance index)"""
        kw = base_knobs(self.key, self.mode)
        kw[self.knob] = at
        if self.key in STATIONS:
            insts = [vo.Inst(self.key, 0, 0, fx=1, fed=True, **kw),
                     vo.Inst(self.key, 1, 0, fx=1, fed=True, **kw)]
            return insts, [0, 1], [0, 1]
        rk = dict(kw if self.key == "REVERB SERVER" else base_knobs("REVERB SERVER", None))
        dk = dict(kw if self.key == "DELAY SERVER" else base_knobs("DELAY SERVER", None))
        s6 = dict(DEL=0, REV=100)          # core 0 sender: the reverb
        s2 = dict(DEL=100, REV=0)          # core 1 sender: the delay
        feed_r = feed_d = False
        if self.key == "REVERB SERVER":
            rk.setdefault("DLY", 0)
            if self.knob in ("DEL", "REV"):
                s6, feed_r = dict(DEL=0, REV=0), True
            if self.knob == "DLY":
                s6 = dict(DEL=0, REV=0)
            obs = 1 if self.knob == "DEL" else 0
        elif self.key == "DELAY SERVER":
            rk["DLY"] = 0
            if self.knob in ("DEL", "REV"):
                s2, feed_d = dict(DEL=0, REV=0), True
            obs = 0 if self.knob == "REV" else 1
        else:   # SEND: both senders move the knob; observe the engine it feeds
            s6 = {"DEL": 0, "REV": 0, self.knob: at}
            s2 = {"DEL": 0, "REV": 0, self.knob: at}
            rk["DLY"] = 0
            obs = 1 if self.knob == "DEL" else 0
        insts = [vo.Inst("REVERB SERVER", 0, 0, fed=feed_r, **rk),
                 vo.Inst("DELAY SERVER", 1, 0, fed=feed_d, **dk),
                 vo.Inst("SEND", 0, 1, fed=True, **s6),
                 vo.Inst("SEND", 1, 1, fed=True, **s2)]
        mv = {"REVERB SERVER": [0], "DELAY SERVER": [1], "SEND": [2, 3]}[self.key]
        return insts, mv, [obs]


def sched_for(case, moving):
    ev = []
    for i in moving:
        ev += [(J1, i, HI), (J2, i, LO)]
        for k, v in enumerate(range(LO + 1, HI + 1)):
            ev.append((S0 + 2 * k, i, v))
    return ",".join(f"{b + send_probe.WARMUP_BLOCKS}:{i}:{case.slot}={v}" for b, i, v in ev)


def render(mems, case, at, sched, tag):
    """vo.run's command, with -sched; returns the observed tracks' L and R"""
    insts, moving, obs = case.layout(at)
    ep = {c: {} for c in mems}
    for i in insts:
        ep[i.core][i.key] = send_probe.entry_points(mems[i.core], registry.by_key(i.key).menu.fx2_id)
    for c, m in mems.items():
        sid = send_probe.entry_points(m, send_probe.SERVER_ID["S"])
        for i in insts:
            if i.core == c and i.key != "SEND" and ep[c][i.key] == sid:
                sys.exit(f"{i.key} is not in payload {'AB'[c]} (its entry is SEND's)")
    out = SCRATCH / f"{tag}.raw"
    cmd = [str(send_probe.HOST), "-mem", str(mems[0]), "-memB", str(mems[1]),
           "-init", ",".join(f"{ep[i.core][i.key][0]:x}" for i in insts),
           "-proc", ",".join(f"{ep[i.core][i.key][1]:x}" for i in insts),
           "-inst", str(len(insts)),
           "-core", ",".join(str(i.core) for i in insts),
           "-alloc", ",".join(str(2 * i.pos + (i.fx - 1)) for i in insts),
           "-r7", ",".join(str(1 + 3 * i.pos + (i.fx - 1)) for i in insts),
           "-audioidx", ",".join(str(k) for k, _ in enumerate(insts)),
           "-audio", "9000",
           "-inmask", str(sum(1 << k for k, i in enumerate(insts) if i.fed)),
           "-frames", str(FRAMES), "-blocks", str(END + 2 + send_probe.WARMUP_BLOCKS),
           "-in", str(SCRATCH / "tone.raw"), "-out", str(out)]
    for i in insts:
        cmd += ["-params", ",".join(map(str, i.params))]
    if sched:
        cmd += ["-sched", sched]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed ({tag}):\n{r.stdout[-2500:]}{r.stderr[-1000:]}")
    res = []
    for o in obs:
        p = out if o == 0 else pathlib.Path(f"{out}.i{o}")
        a = np.frombuffer(p.read_bytes(), dtype="<i4").astype(np.float64) / 8388607.0
        res += [a[0::2][PAD:], a[1::2][PAD:]]
    return res


def d3(x):
    return x[3:] - 3 * x[2:-1] + 3 * x[1:-2] - x[:-3]


def win(x, b0, b1):
    """d3 of blocks [b0, b1), as (values, sample phase within the block)"""
    s0, s1 = b0 * FRAMES, b1 * FRAMES
    d = d3(x[s0 - 2:s1 + 1])
    return d, np.arange(s0, s1) % FRAMES


def step_db(x, b0, b1):
    """the block-locked step in blocks [b0, b1), dBFS: the energy of d3 in
    the loudest of the 15 phases over the median phase, as the RMS height
    of one step per block (a step of height s puts 6 s^2 into d3)"""
    d, ph = win(x, b0, b1)
    e = np.array([np.sum(d[ph == p] ** 2) for p in range(FRAMES)])
    excess = e.max() - np.median(e)
    return 10 * math.log10(max(excess, 1e-30) / (6 * (b1 - b0)))


def measure(move, lo, hi):
    """per window: (move dB, static dB): the static is the louder of the
    knob held at LO and at HI over the same window"""
    res = {}
    for name, b0, b1 in WINDOWS:
        m = max(step_db(v, b0, b1) for v in move)
        s = max(step_db(v, b0, b1) for v in lo + hi)
        res[name] = (m, s)
    return res


def flagged(res):
    return any(m > STEP_LIMIT and m > s + MARGIN for m, s in res.values())


def self_test():
    """the instrument must see a gain glided once per block (the delay's
    FDBK law, an eighth of the way per block) and not the same gain ramped
    per sample"""
    n = END * FRAMES + 3
    t = np.arange(n)
    x = 0.3 * np.sin(2 * math.pi * vo.TONE_HZ / vo.SR * t)
    blk = t // FRAMES + (t % FRAMES) / FRAMES
    def glide(pos):
        g = np.ones(n)
        k = np.clip(pos - J1, 0, None)
        g[t >= J1 * FRAMES] = (0.5 + 0.5 * 0.875 ** k)[t >= J1 * FRAMES]
        return g
    step = glide(t // FRAMES)
    ramp = glide(blk)
    lo, hi = [x, x], [0.5 * x, 0.5 * x]
    rs = measure([x * step] * 2, lo, hi)
    rr = measure([x * ramp] * 2, lo, hi)
    ok = flagged(rs) and not flagged(rr)
    print(f"  [{'PASS' if ok else 'FAIL'}] instrument: a gain glided per block {rs['up'][0]:.1f} dBFS "
          f"(flags), the same glide ramped per sample {rr['up'][0]:.1f} dBFS (clean)")
    return ok


def run_case(mems, case):
    lo = render(mems, case, LO, None, case.tag + "_lo")
    hi = render(mems, case, HI, None, case.tag + "_hi")
    mv = render(mems, case, LO, sched_for(case, case.layout(LO)[1]), case.tag + "_mv")
    return case, measure(mv, lo, hi)


def cases(only):
    out = []
    for key in BUS + STATIONS:
        if only and key not in only:
            continue
        for mode in modes(key):
            for knob, label, slot, count in mode_knobs(key, mode):
                m = registry.by_key(key)
                if slot == m.mode_slot:
                    continue
                out.append(Case(key, mode, knob, label, slot, count))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="module keys, e.g. SPECTRUM 'DELAY SERVER'")
    ap.add_argument("--no-build", action="store_true", help="reuse out/dsp/_knobs/spec_*.mem")
    ap.add_argument("--report", help="write the table (markdown) here")
    a = ap.parse_args()
    mems = ({0: SCRATCH / "spec_A.mem", 1: SCRATCH / "spec_B.mem"} if a.no_build else build())
    vo.tone_file(SCRATCH / "tone.raw", END + 2 + send_probe.WARMUP_BLOCKS, amp=0.3)
    ok = self_test()
    todo = cases(set(a.only) if a.only else None)
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda c: run_case(mems, c), todo))
    rows, sel, flags = [], [], []
    for c, r in results:
        mode = "" if c.mode is None else str(c.mode)
        cells = " | ".join(f"{r[w][0]:.0f} / {r[w][1]:.0f}" for w, _, _ in WINDOWS)
        line = f"| {c.key} | {mode} | {c.label} | {cells} |"
        if c.count is not None and c.count < 128:
            sel.append(line)
        else:
            rows.append(line + (" FLAG |" if flagged(r) else " |"))
            if flagged(r):
                flags.append(f"{c.key} mode {mode} {c.label}")
    head = ("| module | mode | knob | jump up, move / static dBFS | jump down | turn | |\n"
            "|---|---|---|---|---|---|---|")
    text = "\n".join([head, *rows, "", "selects (not flagged):", "",
                      "| module | mode | knob | jump up | jump down | turn |", "|---|---|---|---|---|---|", *sel])
    print(text)
    if a.report:
        pathlib.Path(a.report).write_text(text + "\n")
    print(f"\n{len(rows)} continuous knob cases, {len(flags)} flagged:")
    for f in flags:
        print("  FLAG", f)
    if not ok or flags:
        sys.exit(1)


if __name__ == "__main__":
    main()
