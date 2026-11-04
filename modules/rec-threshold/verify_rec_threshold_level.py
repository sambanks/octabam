#!/usr/bin/env python3
"""REC THRESHOLD, the `level` scenarios of tools/verify/verify_rec_threshold.py: high, quiet, low, full."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools/verify"))
from verify_rec_threshold import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(['high', 'quiet', 'low', 'full']))
