#!/usr/bin/env python3
"""REC THRESHOLD, the `arming` scenarios of tools/verify/verify_rec_threshold.py: tones, late, cancel, untrig."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools/verify"))
from verify_rec_threshold import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(['tones', 'late', 'cancel', 'untrig']))
