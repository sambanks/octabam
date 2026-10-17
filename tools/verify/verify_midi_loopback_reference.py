#!/usr/bin/env python3
"""Rebuild the pinned author's cross-unit reference; no firmware is distributed."""
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath  # noqa: E402,F401

if __name__ == '__main__':
    subprocess.run([sys.executable, str(ROOT/'modules/midi-loopback/upstream/tools/verify_reference.py')], check=True)
