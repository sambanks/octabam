#!/usr/bin/env python3
"""FREE LOOP gate. Reads no firmware and runs no emulator.

1. Compiles the engine for the host and runs its tests (test_freeloop.c):
   RLEN PLEN's loop length, the tempo of a take (exact cases, 30 / 300 BPM
   limits, AUTO's range, 3/4, 7/8, 16 bars) and a sweep of takes from
   0.5 s to 60 s in four signatures (the slowest tempo24 whose loop
   fits, never longer than the take, a cut under 1/tempo24), the pedal's
   transitions (free take, launch, arm, overdub, cut, busy, slave), the
   long press (stop, clear, stop and clear, nothing on a take), the
   per-pattern entry modes, the window's rows, the toasts.
2. With m68k-elf-gcc on the PATH, compiles the engine for the ColdFire
   (-mcpu=5475, freestanding) and refuses any undefined symbol: no libgcc
   helper, no memset the optimiser invented; then checks free_loop.s is
   generate.py's output of freeloop.c, adapter.c and hooks.s (no call
   outside the unit but the stock routines it lists).

What it cannot show: the unit in the firmware (tools/verify/verify_free_loop.py
under the port).
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
CC = shutil.which('cc') or shutil.which('clang') or shutil.which('gcc')
FLAGS = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-O2']
CF_FLAGS = ['-mcpu=5475', '-msoft-float', '-O2', '-ffreestanding', '-fno-builtin', '-fno-common',
            '-fno-tree-loop-distribute-patterns', '-fno-jump-tables', '-fno-asynchronous-unwind-tables',
            '-fno-ident', '-fomit-frame-pointer', '-std=c11', '-Wall', '-Wextra', '-Werror']


def host():
    with tempfile.TemporaryDirectory() as td:
        exe = pathlib.Path(td) / 'engine'
        subprocess.run([CC, *FLAGS, '-o', str(exe), 'freeloop.c', 'test_freeloop.c'], cwd=HERE, check=True)
        r = subprocess.run([str(exe)], capture_output=True, text=True)
        print(r.stdout.rstrip())
        if r.returncode:
            sys.exit('[FAIL] FREE LOOP engine')


def coldfire():
    gcc = shutil.which('m68k-elf-gcc')
    if not gcc:
        print('[SKIP] m68k-elf-gcc not on PATH: ColdFire compile not checked')
        return False
    with tempfile.TemporaryDirectory() as td:
        obj = pathlib.Path(td) / 'freeloop.o'
        subprocess.run([gcc, *CF_FLAGS, '-c', '-o', str(obj), 'freeloop.c'], cwd=HERE, check=True)
        nm = shutil.which('m68k-elf-nm')
        undef = subprocess.run([nm, '-u', str(obj)], capture_output=True, text=True, check=True).stdout.split()
        undef = [u for u in undef if u != 'U']
        if undef:
            sys.exit(f'[FAIL] the ColdFire engine needs {undef}')
        size = subprocess.run([shutil.which('m68k-elf-size'), str(obj)], capture_output=True, text=True).stdout
        print('  ColdFire: ' + ' '.join(size.splitlines()[-1].split()[:3]) + ' (text data bss), no outside call')
    if subprocess.run([sys.executable, 'generate.py', '--check'], cwd=HERE).returncode:
        sys.exit('[FAIL] free_loop.s (see the message above)')
    return True


if __name__ == '__main__':
    if not CC:
        sys.exit('[FAIL] no host C compiler')
    host()
    cf = coldfire()
    print('[PASS] FREE LOOP engine' + (' (host and ColdFire compile)' if cf else ' (host only)')
          + ' -- the port: tools/verify/verify_free_loop.py')
