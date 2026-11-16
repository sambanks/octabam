#!/usr/bin/env python3
"""LOCK EDIT under the ColdFire port. [TRIG]+[BANK] in grid recording opens the audio editor on the held step's sample and slice:
  lockedit  SLIC off STRT 64: the SLICE page, the slice holding STRT/128 of the trim selected, in view with room;
            the encoders edit it while the trig is held; SLIC on STRT 4/8/9: slice STRT/2 (capped); SLIC on and
            the sample without slices: the view centred on STRT/128; no lock: the Part's STRT
  lock      the step's sample lock (FLEX, STATIC) or the track's sample; the trig released clean; a held trig's
            lock popup swapped for the editor; [BANK] alone and outside grid recording stay stock
            (with LAZY CHOP in the image: it arms on, plays and writes the locked slot)

    python3 tools/verify/verify_lock_edit.py [REMIX] [scenario ...]
    make check REMIX=<a remix with LOCK EDIT>   # runs this as the module gate

The harness, the project and the cards are verify_lazy_chop.py's (one boot and card a scenario). SKIPs without the
port, the .venv, or LOCK EDIT in the image.
"""
import os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
os.environ.setdefault("LAZY_CHOP_OUT", "out/lock_edit_verify")
import verify_lazy_chop  # noqa: E402

if __name__ == "__main__":
    sys.exit(verify_lazy_chop.main(sys.argv[1:], gate="lock_edit"))
