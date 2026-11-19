#!/usr/bin/env python3
"""ZOOM KEEP under the ColdFire port. the audio editor keeps its zoom when a slice is auditioned:
  aedview   encoder F zooms in; in SLICES trig mode TRIG 2 selects slice 2 with the zoom kept and its start in
            view; TRIG 1 selects slice 1, the zoom still kept

    python3 tools/verify/verify_zoom_keep.py [REMIX] [scenario ...]
    make check REMIX=<a remix with ZOOM KEEP>   # runs this as the module gate

The harness, the project and the cards are verify_lazy_chop.py's (one boot and card a scenario). SKIPs without the
port, the .venv, or ZOOM KEEP in the image.
"""
import os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
os.environ.setdefault("LAZY_CHOP_OUT", "out/zoom_keep_verify")
import verify_lazy_chop  # noqa: E402

if __name__ == "__main__":
    sys.exit(verify_lazy_chop.main(sys.argv[1:], gate="zoom_keep"))
