#!/usr/bin/env python3
"""Repeat what the v0.6 suite did before each stall: switch the image, reload the project, then play (ot_stallhunt.py).

    .venv/bin/python3 tools/hw/ot_stallcycle.py [--cycles 60] [--image "OCTABAM FL1.RMX"] [--trials 2]

A cycle: `ot_card.py boot IMAGE` (a switch to the running image's own file), `ot_card.py load PROJECT`, then
`ot_stallhunt.py --noload --trials N` in its own process (CoreAudio and CoreMIDI keep a stale device list across a
re-enumeration). Stops at the first cycle in which a command fails or the stall hunt loses the unit; the hunt writes
its frame-log dump to out/hw/stall/. Every command's output is printed.
"""
import argparse
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def run(*args):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    return r.returncode, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", type=int, default=60)
    ap.add_argument("--image", default="OCTABAM FL1.RMX")
    ap.add_argument("--project", default="out/v06c/V06_OCT_01")
    ap.add_argument("--trials", type=int, default=2)
    a = ap.parse_args()
    for c in range(1, a.cycles + 1):
        print(f"=== cycle {c}", flush=True)
        for step, cmd in (("boot", [HERE / "ot_card.py", "boot", a.image]),
                          ("load", [HERE / "ot_card.py", "load", a.project]),
                          ("hunt", [HERE / "ot_stallhunt.py", "--noload", "--trials", a.trials])):
            rc, out = run(*cmd)
            tail = "\n".join(out.splitlines()[-3:])
            print(f"  {step}: rc={rc}\n    " + tail.replace("\n", "\n    "), flush=True)
            if rc or "UNIT LOST" in out:
                print(f"STOP at cycle {c}, step {step}: {'unit lost' if 'UNIT LOST' in out else 'command failed'}", flush=True)
                return 1
    print("cycles done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
