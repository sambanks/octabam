#!/usr/bin/env python3
"""Knob-liveness sweep: every BusVerb page-1 and page-2 parameter, A/B'd over
MIDI on the unit with tools/hw_bus_test.py (T5 soloed, Rytm transport, EVO
capture, synchronous paired detection vs the TIME control). One line per
parameter in out/hw/bustest/sweep.log, then a live/dead summary.

    python3 tools/hw_knob_sweep.py            # BusVerb host on ch5
    python3 tools/hw_knob_sweep.py --ch 1     # BusDelay host on ch1 (page-2 counts differ)

Selects are toggled 0 <-> count-1, knobs 0 <-> 127. TIME (CC 40) is the
control in every run so its own effect is logged each time. Leaves the host
on a neutral setting at the end (see RESTORE).
"""
import argparse
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ot_midi

LOG = pathlib.Path("out/hw/bustest/sweep.log")

# (cc, name, a, b)  -- BusVerb slot order: page 1 then page 2
VERB = [
    (41, "MOD",  0, 127), (42, "SIZE", 0, 127), (43, "TONE", 0, 127), (44, "-DEL", 0, 127), (45, "IN", 0, 127),
    (62, "MODE", 0, 2),   (63, "SHMR", 0, 127), (64, "DIFF", 0, 127), (65, "SHFT", 0, 3),
    (66, "GATE", 0, 127), (67, "RATE", 0, 3),
]
# CC 62-67 = page-2 slots 6-11 = MODE MDEP MRAT SIZE -DEL FRZE (the manifest's
# order; this table was one slot off until 5 Sep 2026).
DELAY = [
    (41, "FDBK", 0, 127), (42, "TONE", 0, 127), (43, "PING", 0, 127), (44, "-VRB", 0, 127), (45, "PTCH", 0, 127),
    (62, "MODE", 0, 2),   (63, "MDEP", 0, 127), (64, "MRAT", 0, 127), (65, "SIZE", 0, 3),
    (66, "-DEL", 0, 127), (67, "FRZE", 0, 1),
]
RESTORE = {40: 90, 41: 20, 42: 64, 43: 0, 44: 127, 45: 100,
           62: 1, 63: 0, 64: 64, 65: 0, 66: 0, 67: 1}

LINE = re.compile(r"TEST page-2\s+CC(\d+) (\d+)<->(\d+):\s+gapfloor d=([+-][\d.]+)dB \(t=([+-][\d.]+)\)\s+\| rms d=([+-][\d.]+) \(t=([+-][\d.]+)\)\s+tilt d=([+-][\d.]+) \(t=([+-][\d.]+)\)")
CTRL = re.compile(r"CONTROL page-1\s+CC40 .*?gapfloor d=([+-][\d.]+)dB \(t=([+-][\d.]+)\)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ch", type=int, default=5)
    ap.add_argument("--period", type=float, default=1.3)
    ap.add_argument("--cycles", type=int, default=12)
    args = ap.parse_args()
    params = DELAY if args.ch == 1 else VERB
    LOG.parent.mkdir(parents=True, exist_ok=True)
    out = ot_midi.Out("A")
    rows = []
    with LOG.open("a") as log:
        log.write(f"\n=== sweep ch{args.ch} {time.strftime('%Y-%m-%d %H:%M')} period {args.period} cycles {args.cycles} ===\n")
        for cc, name, a, b in params:
            cmd = [sys.executable, "tools/hw_bus_test.py", "--ch", str(args.ch), "--period", str(args.period),
                   "--cycles", str(args.cycles), "--test", str(cc), "--a", str(a), "--b", str(b)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            m = LINE.search(r.stdout); c = CTRL.search(r.stdout)
            if m:
                gf, tg, rm, tr, tl, tt = (float(x) for x in m.groups()[3:])
                cg, ct = (float(x) for x in c.groups()) if c else (0.0, 0.0)
                tmax = max(abs(tg), abs(tr), abs(tt))
                verdict = "LIVE" if tmax >= 3 else ("weak" if tmax >= 1.5 else "dead?")
                line = (f"CC{cc:2d} {name:5s} {a:3d}<->{b:3d}: gapfloor {gf:+.2f}dB(t{tg:+.1f}) rms {rm:+.2f}(t{tr:+.1f}) "
                        f"tilt {tl:+.2f}(t{tt:+.1f}) | ctrl TIME {cg:+.2f}dB(t{ct:+.1f}) -> {verdict}")
            else:
                line = f"CC{cc:2d} {name:5s}: harness gave no result\n{r.stdout[-400:]}"
            print(line, flush=True); log.write(line + "\n"); rows.append(line)
        for cc, v in RESTORE.items():
            out.send([0xB0 | (args.ch - 1), cc, v]); time.sleep(0.05)
        out.send([0xB0 | (args.ch - 1), 50, 0])          # un-solo
        log.write("restored neutral settings, un-soloed\n")
    print("\nsummary:"); [print(" ", r_.split(" -> ")[-1].rjust(6), r_.split(":")[0]) for r_ in rows if " -> " in r_]


if __name__ == "__main__":
    main()
