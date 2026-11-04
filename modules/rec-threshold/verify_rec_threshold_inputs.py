#!/usr/bin/env python3
"""REC THRESHOLD, the `inputs` scenarios of tools/verify/verify_rec_threshold.py: silent, stock, inpage_one, inpage_thr."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools/verify"))
from verify_rec_threshold import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(['silent', 'stock', 'inpage_one', 'inpage_thr']))
