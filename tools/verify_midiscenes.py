#!/usr/bin/env python3
"""The midi-scenes port's exact claim, checked: every cave region in the
submodule's gas/*.s assembles and links to the bytes bkkbrls-del's own
Python encoder produces, at his own addresses.

The proof lives upstream -- `tools/gas_port.py` on the fork's octabam-gas
branch regenerates gas/*.s from his build_* functions and compares -- so
this just runs it in place and reports. SKIPs, rather than fails, when the
submodule or the m68k toolchain is absent: `make verify` runs on machines
that never asked for midi-scenes.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
UP = ROOT / "modules/midi-scenes/upstream"
PORT = UP / "tools/gas_port.py"

if not PORT.exists():
    print("  [SKIP] verify_midiscenes: submodule not checked out "
          "(git submodule update --init modules/midi-scenes/upstream)")
    sys.exit(0)
if any(shutil.which(t) is None for t in ("m68k-elf-as", "m68k-elf-ld", "m68k-elf-objcopy")):
    print("  [SKIP] verify_midiscenes: m68k-elf toolchain not installed (make setup)")
    sys.exit(0)

before = {p: p.read_bytes() for p in (UP / "gas").glob("*.s")}
r = subprocess.run([sys.executable, str(PORT)], cwd=UP, capture_output=True, text=True)
after = {p: p.read_bytes() for p in (UP / "gas").glob("*.s")}
regen = [p.name for p in after if before.get(p) != after[p]]
ok = r.returncode == 0 and not regen
print(f"  [{'PASS' if ok else 'FAIL'}] verify_midiscenes: gas/*.s reproduce the encoder's "
      f"bytes at his addresses"
      + (f"; regenerated files DIFFER from what is committed: {regen}" if regen else ""))
if r.returncode:
    print((r.stdout + r.stderr)[-1200:])
sys.exit(0 if ok else 1)
