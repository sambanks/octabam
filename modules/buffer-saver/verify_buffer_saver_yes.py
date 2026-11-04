#!/usr/bin/env python3
"""BUFFER SAVER, the `yes` scenario of tools/verify/verify_buffer_saver.py."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools/verify"))
from verify_buffer_saver import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["yes"]))
