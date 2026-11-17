#!/usr/bin/env python3
"""LAZY CHOP TEMPO under the ColdFire port: the tempo popup after LAZY CHOP's YES.
  tempo     every case in tools/verify/chop_tempo_cases.json (8thmyth's chops) through the module's own code:
            the line is tools/hw/chop_tempo_int.py's; the instructions one reading costs, against a limit
  tempopop  a real chop: YES shows the slice count, then the tempo popup, up until the next key

    python3 tools/verify/verify_chop_tempo.py [REMIX] [scenario ...]
    make check REMIX=<a remix with LAZY CHOP TEMPO>   # runs this as the module gate

The harness, the project and the cards are verify_lazy_chop.py's (one boot and card a scenario). SKIPs without the
port, the .venv, or LAZY CHOP TEMPO in the image.
"""
import os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
os.environ.setdefault("LAZY_CHOP_OUT", "out/chop_tempo_verify")
import verify_lazy_chop  # noqa: E402

if __name__ == "__main__":
    sys.exit(verify_lazy_chop.main(sys.argv[1:], gate="chop_tempo"))
