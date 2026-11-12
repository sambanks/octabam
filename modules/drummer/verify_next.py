#!/usr/bin/env python3
"""DRUMMER's NEXT page under the port (MKII): an order turned on the panel, played by the engine.

    .venv/bin/python3 modules/drummer/verify_next.py --sample DIR/NAME.wav [--image out/mainos_bus.bin]
        [--project <empty project>] [--case NAME]

verify_port.py's project (the user's sample on FLEX slot 1, T1 a DRUMMER track, BREAKBEAT, 240 BPM, a bar
a second) with a CRASH slice in the kit (slice 16) and NEXT's B-F written into every Part (THRU's SETUP
column of T1, marked 'N'). The live script answers the date prompt, selects T1, opens NEXT (SRC twice:
KIT BALANCE, then NEXT), presses PLAY, and turns A WHEN mid-bar (it arms half a second after the knob rests). Every T1 voice start is watched, with
the engine's dr_stopped, dr_nx_when, dr_vstep, dr_cur_style and dr_last_hit:

  stop      B STOP, C DRY, A BAR at 1.4 s: on the next bar's 1 dr_stopped = 1 and WHEN back to none; no
            start from that step on; A BAR again at 3.2 s: playing again from the bar after, starts again
  fill      B STOP, C FILL+CR, D TRIP: the bar before the 1 ends in fill hits (DRF_FILL) heard, the 1 plays
            (the landing: CRASH), then no start
  resume    the drummer stopped first (STOP, DRY, A BAR at 1.4 s), then C FILL, D RUDI, A BAR at 3.4 s: while
            stopped only the order's fill is heard (every start in that bar a fill hit), then the groove
  grid      B STOP, C DRY, the track's own trigs on steps 1 5 9 13: once stopped they still play, nothing else
  silent    the same with B SILENT: once stopped no start at all (the grid's trigs made trigless)
  style     E HHOP (style 7), B none: the engine's style is BREAKBEAT until the order's 1, HHOP from it
  brk       F BAR (B none): BRK cuts (DRF_BREAK) in the bar from the order's 1, none in the bar before or
            after; the drummer never stops
  travel    B STOP, A turned three detents: short of BEAT (four detents a value), nothing armed
  settle    B STOP, A turned to BEAT then BAR 0.2 s later: WHEN arms only once the knob rests (half a
            second), so the order is BAR's (stopped on a bar's 1), not BEAT's (image 83 sent BEAT at once)
"""
import argparse
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe_slices as ps  # noqa: E402
import verify_port as vp  # noqa: E402

ROOT = ps.ROOT
OUT = ROOT / "out/drummer/next"
YES, T1, SRC, PLAY = 0x31, 0x10, 0x22, 0x28
NX_AT, NMARK = 0x1E6, 0x41                # RAM Part offsets (the file's: + 9)
DRF_FILL, DRF_BREAK = 4, 8
HHOP = 7                                   # E's value: style 6 + 1
# B RUN, C HOW, D FILL, E STYL, F BRK (adapter.c's NX_*); forced steps; arms (s); a second order's C D
CASES = {
    "stop":   ((1, 0, 0, 0, 0), (), (1.2, 3.2), None),
    "fill":   ((1, 3, 1, 0, 0), (), (1.2,), None),
    "resume": ((1, 0, 0, 0, 0), (), (1.2, 3.2), (2, 3)),
    "grid":   ((1, 0, 0, 0, 0), (0, 4, 8, 12), (1.2,), None),
    "silent": ((2, 0, 0, 0, 0), (0, 4, 8, 12), (1.2,), None),
    "style":  ((0, 0, 0, HHOP, 0), (), (1.2,), None),
    "brk":    ((0, 0, 0, 0, 3), (), (1.2,), None),
    "settle": ((1, 0, 0, 0, 0), (), (1.0,), None),
    "travel": ((1, 0, 0, 0, 0), (), (1.2,), None),
}
FAILS = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def tap(ms, code):
    return [f"{int(ms)} key {code:#x} down", f"{int(ms) + 60} key {code:#x} up"]


def build(a, case, wav, slices, count, frames, out):
    nx, forced, _, _ = CASES[case]
    proj = out / "project"
    ps.build_project(pathlib.Path(a.project), proj, frames, slices, count, vp.TEMPO, track=0)
    live, conf, _ = vp.CASES["groove"]

    def mut(data):
        row1, row2 = vp.knob_rows(live, conf)
        for p in range(ps.otp.NPARTS_ALL):
            part = ps.otp.PART_BASE + p * ps.otp.PART_STRIDE
            base = part + ps.VALUES_OFF + 6 * ps.FLEX
            data[base:base + 6] = bytes(row1)
            su = part + ps.SETUP_OFF + 6 * ps.FLEX
            data[su:su + 6] = bytes(row2)
            data[part + 9 + 60:part + 9 + 63] = b"DR\x01"
            data[part + 9 + NX_AT:part + 9 + NX_AT + 5] = bytes(nx)
            data[part + 9 + NMARK] = ord("N")
        off = ps.otp.trac_off(0, 0)
        data[off:off + 64] = bytes(64)
        data[off + 0x59:off + 0x59 + 64 * 32] = bytes([0xff]) * (64 * 32)
        for s in forced:
            data[off + 7 - s // 8] |= 1 << (s % 8)
    ps.otp._bank_write(proj, 1, mut, guard=False)
    zones = list(vp.DEF_ZONE)
    vp.DEF_ZONE[15] = "CRASH"                 # a crash for the landing
    try:
        vp.write_kit(proj, 0)
    finally:
        vp.DEF_ZONE[:] = zones
    card = out / "card.img"
    r = subprocess.run([str(ps.PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "RIG",
                        "--tree", str(out / "tree"), "--out", str(card), "--audio", f"{wav}:{ps.SAMPLE_REL}"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"stage_card failed: {(r.stdout + r.stderr)[-600:]}")
    return card


def run(a, case, card, out):
    _, _, arms, second = CASES[case]
    t0 = 3000                                  # PLAY: the bars start here
    ev = tap(300, YES) + tap(1500, T1) + tap(2100, SRC) + tap(2600, SRC) + tap(t0, PLAY)
    for i, s in enumerate(arms):
        ms = t0 + s * 1000
        if i and second:                       # the second order's C and D first
            ev += [f"{int(ms) - 300} enc 2 {second[0]}", f"{int(ms) - 200} enc 3 {second[1]}"]
        if case == "travel":                   # three detents: short of a value, nothing armed
            ev.append(f"{int(ms)} enc 0 3")
        elif case == "settle":                   # A through BEAT to BAR, 0.2 s apart: armed at rest, on BAR
            ev += [f"{int(ms)} enc 0 4", f"{int(ms) + 200} enc 0 4"]
        else:
            ev.append(f"{int(ms)} enc 0 8")      # A WHEN +2 values (4 detents each): BAR (armed half a second after, at rest)
    ev.append(f"{t0 + 6500} quit")
    script = out / "next.script"
    script.write_text("\n".join(sorted(ev, key=lambda l: int(l.split()[0]))) + "\n")
    sym = {n: vp.symbol(n) for n in ("dr_stopped", "dr_nx_when", "dr_vstep", "dr_cur_style", "dr_last_hit")}
    watch = [f"{0x800049f8:#x},1", f"{sym['dr_stopped']:#x},1", f"{sym['dr_nx_when']:#x},1",
             f"{sym['dr_vstep']:#x},1", f"{sym['dr_cur_style']:#x},1", f"{sym['dr_last_hit'] + 4:#x},4"]
    cmd = [str(ps.EMU), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "RIG", "--mkii",
           "--load-ms", "90000", "--main-level", "64", "--live-script", str(script),
           "--lcd", str(out / "next.lcd"), "--watch-mem", ";".join(watch)]
    log = out / "port.txt"
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    subprocess.run([str(ps.PY), str(ROOT / "tools/emu/lcd_view.py"), str(out / "next.lcd"), "--png",
                    str(out / "next.png")], cwd=ROOT, capture_output=True)
    text = log.read_text()
    if "ended on quit" not in text:
        sys.exit(f"verify_next: the port run failed -- {log}")
    ev = []                                    # (time, what, value, pc)
    names = {0x800049f8: "start", sym["dr_stopped"]: "stopped", sym["dr_nx_when"]: "when",
             sym["dr_vstep"]: "vstep", sym["dr_cur_style"]: "style", sym["dr_last_hit"] + 4: "hit"}
    for m in re.finditer(r"\[\s*([\d.]+)\] \[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|0) \(\d\) at pc (0x[0-9a-f]+)", text):
        t, addr, val, pc = float(m.group(1)), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16)
        what = names.get(addr)
        if what == "start" and pc != 0x4000f67c:
            continue
        if what == "hit":                      # rtrg rtim zone flags
            ev.append((t, "zone", val >> 8 & 0xff))
            ev.append((t, "flags", val & 0xff))
        elif what:
            ev.append((t, what, val))
    return ev, str(log)


def steps_of(ev):
    """The engine's decisions in order: (time, vstep, zone, flags, stopped) -- dr_last_hit is stored right
    after dr_vstep (one decision each; a word unchanged is not logged: the decision before's)."""
    out, cur, stopped, zone, flags = [], None, 0, None, None
    for t, w, v in ev:
        if w == "stopped":
            stopped = v
        if w == "vstep":
            cur = [t, v, zone, flags, stopped]
            out.append(cur)
        elif w == "zone":
            zone = v
            if cur is not None:
                cur[2] = v
        elif w == "flags":
            flags = v
            if cur is not None:
                cur[3] = v
    return out


def judge(case, ev, info):
    starts = [t for t, w, v in ev if w == "start"]
    fires, armed = [], 0                     # an order played: WHEN from armed back to none (a turn's disarm
    for t, w, v in ev:                       # writes 0 over 0)
        if w == "when":
            if armed and v == 0:
                fires.append(t)
            armed = v
    stops = [(t, v) for t, w, v in ev if w == "stopped"]
    dec = steps_of(ev)
    # a decision is a step ahead of its sound: a start belongs to the step decided last before it
    def decision_at(t):
        prior = [d for d in dec if d[0] <= t]
        return prior[-1] if prior else None
    def starts_between(a, b):
        return [t for t in starts if a < t <= b]
    if case == "travel":
        check("travel: three detents on WHEN arm nothing (four a value): the drummer never stops",
              not any(v for t, v in stops) and not fires and len(starts) > 20, f"{len(starts)} starts")
        return
    if not stops and case not in ("style", "brk"):
        check(f"{case}: dr_stopped never moved", False, info)
        return
    if case in ("stop", "fill", "resume", "grid", "silent", "settle"):
        t_s = stops[0][0]
        d_next = [d for d in dec if d[0] > t_s]
        first_vstep = d_next[0][1] if d_next else None
        check(f"{case}: stopped on a bar's 1 (decided with step 1 of the bar), WHEN back to none",
              first_vstep == 0 and any(abs(f - t_s) < 2000 for f in fires), f"vstep after {first_vstep}, fires {len(fires)}")
        end = stops[1][0] if len(stops) > 1 else float("inf")
        if case == "settle":
            check("settle: WHEN through BEAT to BAR sends BAR (stopped on a bar's 1, never on the beat after the turn)",
                  first_vstep == 0, f"vstep {first_vstep}")
        after = starts_between(t_s + 3000, end)          # the order's 1 sounds right after its decision
        if case == "stop":
            check("stop: no start while stopped", not after, f"{len(after)} starts")
            check("stop: A BAR again resumes on a bar's 1, starts again",
                  len(stops) > 1 and stops[1][1] == 0 and len(starts_between(end + 3000, end + 30000)) > 2,
                  f"stops {[(round(t), v) for t, v in stops]}")
        if case == "fill":
            before = [d for d in dec if d[0] < t_s][-5:]
            fills = [d for d in before if d[3] is not None and d[3] & DRF_FILL]
            land = [d for d in dec if d[0] >= t_s - 1][:1]
            check("fill: the bar before the 1 ends in the order's fill (DRF_FILL)", len(fills) >= 2,
                  f"last steps' flags {[d[3] for d in before]}")
            one = starts_between(t_s - 100, t_s + 3000)
            check("fill: the 1 plays (the landing), then nothing", len(one) >= 1 and not after,
                  f"{len(one)} on the 1, {len(after)} after")
        if case == "resume":
            t_r = stops[1][0] if len(stops) > 1 else None
            check("resume: resumed on the second order", t_r is not None and stops[1][1] == 0)
            if t_r:
                bar = starts_between(t_r - 30000, t_r - 100)
                fl = [decision_at(t) for t in bar]
                ok = bool(bar) and all(d and d[3] is not None and d[3] & DRF_FILL for d in fl)
                check("resume: while stopped only the order's fill is heard, before the 1", ok,
                      f"{len(bar)} starts, flags {[d[3] if d else None for d in fl]}")
                check("resume: the groove after the 1", len(starts_between(t_r, t_r + 40000)) > 3)
        if case in ("grid", "silent"):
            st = [decision_at(t) for t in after]
            if case == "grid":
                # a start sounds about as the next step is decided: judged by time, every start a whole
                # number of beats (four steps) from the one before -- the trigs on 1 5 9 13 alone
                gaps = [(b - a) / vp.STEP for a, b in zip(after, after[1:])]
                ok = len(after) >= 8 and all(abs(g - 4 * round(g / 4)) < 0.2 and round(g) >= 4 for g in gaps)
                check("grid: stopped, the track's trigs (steps 1 5 9 13) still play, nothing else", ok,
                      f"{len(after)} starts, gaps in steps {sorted({round(g, 2) for g in gaps})}")
            else:
                check("silent: stopped SILENT, no start at all (trigs made trigless)", not after,
                      f"{len(after)} starts")
    if case == "style":
        t_f = fires[0] if fires else None
        sty = [(t, v) for t, w, v in ev if w == "style"]
        before = {v for t, v in sty if t_f and t < t_f - 100}
        aft = {v for t, v in sty if t_f and t > t_f + 100}
        check("style: BREAKBEAT before the order's 1, HHOP from it", t_f is not None and before == {0} and aft == {HHOP - 1},
              f"before {before} after {aft}")
    if case == "brk":
        t_f = fires[0] if fires else None
        brk = [d for d in dec if d[3] is not None and d[3] & DRF_BREAK]
        bar_len = vp.STEP * 16
        inb = [d for d in brk if t_f and t_f - 100 <= d[0] < t_f + bar_len]
        out = [d for d in brk if not (t_f and t_f - 100 <= d[0] < t_f + bar_len)]
        check("brk: BRK cuts in the bar from the order's 1, none elsewhere", t_f is not None and inb and not out,
              f"{len(inb)} in, {len(out)} out")
        check("brk: the drummer never stops", not any(v for t, v in stops))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--project", default=str(ROOT / "out/drummer/slices/fresh/image/NOPROJ"))
    ap.add_argument("--case", action="append", choices=sorted(CASES))
    a = ap.parse_args()
    wav = pathlib.Path(a.sample).expanduser().resolve()
    slices, count = ps.read_ot(wav.with_suffix(".ot"))
    import wave
    with wave.open(str(wav)) as w:
        frames = w.getnframes()
    print("DRUMMER NEXT (port, MKII)")
    import concurrent.futures as cf

    def one(case):
        out = OUT / case
        out.mkdir(parents=True, exist_ok=True)
        card = build(a, case, wav, slices, count, frames, out)
        return case, run(a, case, card, out)
    with cf.ThreadPoolExecutor(len(a.case or CASES)) as ex:
        for case, (ev, info) in ex.map(one, a.case or list(CASES)):
            judge(case, ev, info)
    print(f"{'PASS' if not FAILS else 'FAIL'}: DRUMMER NEXT")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
