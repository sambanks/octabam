#!/usr/bin/env python3
"""SRC3 KEY under the ColdFire port. [MIDI] in the audio editor is the SRC3 record key (MKI):
  midi      [MIDI] in the editor starts a SRC3 take on the track's recorder, again stops it, the editor stays;
            SRC3 off in RECORDING SETUP records nothing; the setting off gives stock's [MIDI]
            (with LAZY CHOP in the image: in LIVE CHOP, TRIG 1 joins that take and YES stops it)

    python3 tools/verify/verify_src3_key.py [REMIX] [scenario ...]
    make check REMIX=<a remix with SRC3 KEY>   # runs this as the module gate

The harness, the project and the cards are verify_lazy_chop.py's (one boot and card a scenario). SKIPs without the
port, the .venv, or SRC3 KEY in the image.
"""
import os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
os.environ.setdefault("LAZY_CHOP_OUT", "out/src3_key_verify")
import verify_lazy_chop  # noqa: E402

if __name__ == "__main__":
    sys.exit(verify_lazy_chop.main(sys.argv[1:], gate="src3_key"))
