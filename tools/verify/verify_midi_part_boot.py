#!/usr/bin/env python3
"""Prove the boot gate still rejects code drift outside named Part-state data."""
import contextlib
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath  # noqa: E402,F401


def main():
    if len(sys.argv) > 1:
        os.environ['REMIX'] = sys.argv[1]
    original = subprocess.run
    dump = ROOT/'out/_dump_octabam.bin'
    saved = None

    def run(args, *pos, **kwargs):
        nonlocal saved
        result = original(args, *pos, **kwargs)
        if str(args[0]) == str(ROOT/'out/emu/ot_emu'):
            saved = dump.read_bytes()
            # The runtime begins with executable code, not either Part array.
            data = bytearray(saved)
            for i in range(65):
                data[i] ^= 0xff
            dump.write_bytes(data)
        return result

    output = io.StringIO()
    status = None
    try:
        subprocess.run = run
        with contextlib.redirect_stdout(output):
            try:
                runpy.run_path(str(ROOT/'tools/verify/verify_dram_boot.py'), run_name='__main__')
            except SystemExit as e:
                status = e.code
    finally:
        subprocess.run = original
        if saved is not None:
            dump.write_bytes(saved)
    text = output.getvalue()
    assert saved is not None and status == 1, (status, text)
    assert '[PASS] verify_dram_boot:' in text and 'boots to the handoff' in text, text
    assert '[FAIL] verify_dram_boot: octabam reserve' in text, text
    print('[ok] real boot reaches handoff; injected code drift outside Part-state data is rejected')


if __name__ == '__main__':
    main()
