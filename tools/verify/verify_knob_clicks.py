#!/usr/bin/env python3
"""KNOB CLICK CENSUS: every continuous knob of every DSP module in bamsep26,
moved mid-render under dsp_host, checked for block-rate steps in the output.

A knob the DSP applies once per block (16 frames on the unit) and not per
sample makes a step at every block boundary while it moves: zipper crackle
at 2,756 Hz and its harmonics. This renders a steady 438.75 Hz tone at
0.3 FS through each module (the rig's layout for the bus engines and
SEND, both payloads for the stations) in 16-frame blocks, and per knob
and mode:

  move    knob at LO 20, a jump to HI 110 at block J1, back to LO at J2,
          then a turn LO -> HI one step every two blocks from S0
  static  the same render with the knob held at LO, and again at HI

The measure, per window (jump up, jump down, turn): the third difference
d3 of each observed channel, its energy in each of the 16 sample phases
of the block; the loudest phase over the median phase, less three robust
deviations of the phases, as the RMS height of one step per block in
dBFS (a step of height s puts 6 s^2 into d3). A step lands on the same
phases every block; a tone, its harmonics, a swept resonance and an
effect's own period-3 rotation spread over all of them. d3 terms touching
a sample on the store's limit are left out (clipping is the effect's
level, not a step).

A knob is FLAGGED when a window's move level is above STEP_LIMIT and
MARGIN over the louder static render. STEP_LIMIT (-70 dBFS) sits under
the delay's per-block FDBK glide, which measured -60 to -72 here before
it got a per-sample ramp. Selects (count < 128: MODE, SIZE, SHFT, SAT)
and the knobs in STEPPED change something discrete on a value change and
are listed apart; KNOWN lists a residual with its reason and fails only
if it gets louder than its ceiling.

The instrument is checked before any module is judged: a 0.3 FS tone
under a gain glided an eighth of the way per block must flag, and the
same glide ramped per sample must not.

The garbage start: every module and mode is also rendered with its instance
block pre-filled (0x7fffff, 0x5a5a5a) and the tone from block 0; the first
256 blocks' peak may not exceed the same render's from a zero block by more
than 1 dB (the settled peak, blocks 1000 on, is reported beside).
verify_dirtystate's silence cannot see a garbage gain or coefficient state.

What this cannot see: the chip's cycle overrun (a block that misses its
deadline crackles on the unit and renders clean here), anything the
ColdFire does between a panel turn and r6 (knobs are poked into r6 once
per block, as -sched does), a trig-split block (the dispatcher's two calls
per block; dsp_host makes one), and a step under the tone's own d3 floor.

    make verify-knobs                 # the census + the garbage start (~1.5 min)
    python3 tools/verify/verify_knob_clicks.py --only SPECTRUM --report out/k.md
"""
import argparse
import concurrent.futures as cf
import math
import pathlib
import shutil
import statistics
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe  # noqa: E402
import verify_onebus as vo  # noqa: E402
from remix import registry  # noqa: E402

SCRATCH = ROOT / "out/dsp/_knobs"
FRAMES = 16                 # the unit's block (docs/remixer/HARNESS.md "Blocks")
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
# continuous knobs whose values select discrete things: listed with the
# selects, not flagged
KNOWN = {
    # integer taps (forced odd) move with SIZE's per-block glide; a
    # per-sample fractional ramp in the tank loop prices ~100 cycles/sample
    # on the reverb, more than the worst core's headroom
    ("REVERB SERVER", "SIZE"): ("the tank taps are integers that step per block", -25.0),
}
STEPPED = {
    ("MODULATION", "LOFI"): "hold length and bit mask are integers",
    ("MODULATION", "STGS"): "PHSR's stage count, 2/4/6/8 by quarters of DLY",
}
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


def render(mems, case, at, sched, tag, tone="tone.raw", pad=PAD, epmems=None):
    """vo.run's command, with -sched; returns the observed tracks' L and R.
    `epmems`: the dumps the entry points are read from (a filled dump's
    appended runs confuse send_probe's reader)"""
    insts, moving, obs = case.layout(at)
    epmems = epmems or mems
    ep = {c: {} for c in mems}
    for i in insts:
        ep[i.core][i.key] = send_probe.entry_points(epmems[i.core], registry.by_key(i.key).menu.fx2_id)
    for c, m in epmems.items():
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
           "-in", str(SCRATCH / tone), "-out", str(out)]
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
        raw = p.read_bytes()
        a = [v / 8388607.0 for v in struct.unpack(f"<{len(raw) // 4}i", raw)]
        res += [a[0::2][pad:], a[1::2][pad:]]
    return res


def tone_file(path, blocks, amp=0.3, pad=PAD):
    """the steady tone, from sample `pad` on"""
    w = 2 * math.pi * vo.TONE_HZ / vo.SR
    v = [int(amp * 8388607 * math.sin(w * (i - pad))) if i >= pad else 0
         for i in range(blocks * FRAMES)]
    path.write_bytes(struct.pack(f"<{len(v)}i", *v))


def phase_energy(x, b0, b1):
    """the energy of d3 over blocks [b0, b1), per sample phase of the block.
    A sample on the store's limit is the effect clipping, not a step: the d3
    terms that touch one are left out (a resonance swept through the tone
    overshoots; that is the effect's level, a separate question)."""
    e = [0.0] * FRAMES
    s0 = b0 * FRAMES
    for n in range(s0, b1 * FRAMES):
        a, b, c, d = x[n - 2], x[n - 1], x[n], x[n + 1]
        if max(abs(a), abs(b), abs(c), abs(d)) >= 0.9999:
            continue
        v = d - 3 * c + 3 * b - a
        e[n % FRAMES] += v * v
    return e


def step_db(x, b0, b1):
    """the block-locked step in blocks [b0, b1), dBFS: the energy of d3 in
    the loudest of the 15 phases over the median phase, less three robust
    deviations of the phases (a swept resonance spreads noise over all 15;
    a step lands on the same two every block), as the RMS height of one
    step per block (a step of height s puts 6 s^2 into d3)"""
    e = phase_energy(x, b0, b1)
    med = statistics.median(e)
    spread = 1.4826 * statistics.median(abs(v - med) for v in e)
    excess = max(e) - med - 3 * spread
    return max(-140.0, 10 * math.log10(max(excess, 1e-30) / (6 * (b1 - b0))))


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
    w = 2 * math.pi * vo.TONE_HZ / vo.SR
    x = [0.3 * math.sin(w * t) for t in range(n)]
    def gain(pos):
        return 1.0 if pos < J1 else 0.5 + 0.5 * 0.875 ** (pos - J1)
    step = [v * gain(t // FRAMES) for t, v in enumerate(x)]
    ramp = [v * gain(t / FRAMES) for t, v in enumerate(x)]
    half = [0.5 * v for v in x]
    rs = measure([step] * 2, [x, x], [half, half])
    rr = measure([ramp] * 2, [x, x], [half, half])
    ok = flagged(rs) and not flagged(rr)
    print(f"  [{'PASS' if ok else 'FAIL'}] instrument: a gain glided per block {rs['up'][0]:.1f} dBFS "
          f"(flags), the same glide ramped per sample {rr['up'][0]:.1f} dBFS (clean)")
    return ok


def run_case(mems, case):
    lo = render(mems, case, LO, None, case.tag + "_lo")
    hi = render(mems, case, HI, None, case.tag + "_hi")
    mv = render(mems, case, LO, sched_for(case, case.layout(LO)[1]), case.tag + "_mv")
    return case, measure(mv, lo, hi)


# ---- the garbage start ---------------------------------------------------
# verify_dirtystate renders from a garbage instance block on SILENCE, which
# cannot see a garbage gain or coefficient: a run value or glide state that
# init does not seed gives garbage gains for the blocks it takes to glide
# in, and silence in is silence out either way. Here each module and mode is
# rendered from a garbage block on the tone from block 0, and the first 256
# blocks' peak must not exceed the same render's from a ZERO block (the
# port's and dsp_host's start) by more than GARBAGE_DB: an onset transient
# the effect makes on its own (a resonance ringing up, a compressor's
# attack) is in both. The settled peak (blocks 1000 on) is reported beside.
GARBAGE_FILLS = (0x7fffff, 0x5a5a5a)
GARBAGE_BLOCKS = 256
GARBAGE_DB = 1.0
SETTLED_FROM = 1000


def mem_with_fill(base, fill, out, r7s):
    """the .mem with the instance blocks at `r7s` (X, 0x100 words each)
    filled (verify_dirtystate's run format)"""
    blob = base.read_bytes()
    body, term = blob[:-9], blob[-9:]
    assert term[0] == 0xff, "not a .mem dump"
    runs = b"".join(struct.pack("<BII", 1, r7, 0x100) + struct.pack("<I", fill) * 0x100 for r7 in r7s)
    out.write_bytes(body + runs + term)
    return out


def garbage_case(mems, key, mode, fill):
    m = registry.by_key(key)
    knobs = mode_knobs(key, mode)
    name, label, slot, count = next(k for k in knobs if k[2] != m.mode_slot)
    case = Case(key, mode, name, label, slot, count)
    at = base_knobs(key, mode).get(name, (m.params[slot].default or 0))
    insts, _, obs = case.layout(at)
    fills = {0: [], 1: []}
    for o in obs:
        i = insts[o]
        fills[i.core].append(0x6100 + 0x100 * (1 + 3 * i.pos + (i.fx - 1)))
    gm = {c: mem_with_fill(mems[c], fill, SCRATCH / f"garb_{case.tag}_{fill:06x}_{'AB'[c]}.mem", fills[c]) for c in mems}
    x = render(gm, case, at, None, f"garb_{case.tag}_{fill:06x}", tone="tone0.raw", pad=0, epmems=mems)
    peaks = [max(max(abs(v) for v in ch[b * FRAMES:(b + 1) * FRAMES]) for ch in x) for b in range(END)]
    return case, max(peaks[:GARBAGE_BLOCKS]), max(peaks[SETTLED_FROM:])


def ratio_db(a, b):
    return 20 * math.log10(a / b) if a > 0 and b > 0 else (0.0 if a == 0 else 99.0)


def garbage_census(mems, only):
    tone_file(SCRATCH / "tone0.raw", END + 2, pad=0)
    todo = [(key, mode, fill) for key in BUS + STATIONS if not only or key in only
            for mode in modes(key) for fill in (0,) + GARBAGE_FILLS]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda t: garbage_case(mems, *t), todo))
    zero = {(key, mode): first for (key, mode, fill), (c, first, settled) in zip(todo, results) if fill == 0}
    rows, flags = [], []
    for (key, mode, fill), (c, first, settled) in zip(todo, results):
        if fill == 0:
            continue
        over = ratio_db(first, zero[(key, mode)])
        bad = over > GARBAGE_DB
        rows.append(f"| {key} | {'' if mode is None else mode} | {fill:06x} | "
                    f"{20 * math.log10(max(first, 1e-9)):.1f} | {20 * math.log10(max(zero[(key, mode)], 1e-9)):.1f} | "
                    f"{20 * math.log10(max(settled, 1e-9)):.1f} | {over:+.1f}{' FLAG' if bad else ''} |")
        if bad:
            flags.append(f"{key} mode {mode} fill {fill:06x}: first {GARBAGE_BLOCKS} blocks {over:+.1f} dB over the zero start")
    head = ("| module | mode | fill | first 256 blocks peak dBFS | from a zero block | settled | over zero |\n"
            "|---|---|---|---|---|---|---|")
    return "\n".join([head, *rows]), flags


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
    ap.add_argument("--no-garbage", action="store_true", help="skip the garbage-start renders")
    a = ap.parse_args()
    mems = ({0: SCRATCH / "spec_A.mem", 1: SCRATCH / "spec_B.mem"} if a.no_build else build())
    tone_file(SCRATCH / "tone.raw", END + 2 + send_probe.WARMUP_BLOCKS)
    ok = self_test()
    todo = cases(set(a.only) if a.only else None)
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda c: run_case(mems, c), todo))
    rows, sel, flags = [], [], []
    for c, r in results:
        mode = "" if c.mode is None else str(c.mode)
        cells = " | ".join(f"{r[w][0]:.0f} / {r[w][1]:.0f}" for w, _, _ in WINDOWS)
        line = f"| {c.key} | {mode} | {c.label} | {cells} |"
        if (c.count is not None and c.count < 128) or (c.key, c.label) in STEPPED:
            sel.append(line)
        elif (c.key, c.label) in KNOWN:
            why, ceil = KNOWN[(c.key, c.label)]
            worse = any(m > ceil for m, _ in r.values())
            rows.append(line + (" LOUDER THAN KNOWN |" if worse else " known |"))
            if worse:
                flags.append(f"{c.key} mode {mode} {c.label} (known: {why}; ceiling {ceil} dBFS)")
        else:
            rows.append(line + (" FLAG |" if flagged(r) else " |"))
            if flagged(r):
                flags.append(f"{c.key} mode {mode} {c.label}")
    head = ("| module | mode | knob | jump up, move / static dBFS | jump down | turn | |\n"
            "|---|---|---|---|---|---|---|")
    text = "\n".join([head, *rows, "", "selects (not flagged):", "",
                      "| module | mode | knob | jump up | jump down | turn |", "|---|---|---|---|---|---|", *sel])
    print(text)
    print(f"\n{len(rows)} continuous knob cases, {len(flags)} flagged:")
    for f in flags:
        print("  FLAG", f)
    gtext, gflags = ("", []) if a.no_garbage else garbage_census(mems, set(a.only) if a.only else None)
    if gtext:
        print("\ngarbage start (the instance block pre-filled, the tone from block 0):\n")
        print(gtext)
        print(f"\n{len(gflags)} garbage-start cases flagged:")
        for f in gflags:
            print("  FLAG", f)
    if a.report:
        pathlib.Path(a.report).write_text(text + "\n\n" + gtext + "\n")
    if not ok or flags or gflags:
        sys.exit(1)


if __name__ == "__main__":
    main()
