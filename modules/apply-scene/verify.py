#!/usr/bin/env python3
"""APPLY SCENE engine gate. Reads no firmware and runs no emulator.

1. Compiles the engine for the host and runs its tests (test_apply.c): the
   blend at every crossfader position for every pair of values, against the
   frame builder's arithmetic (MIDI.md appendix C), to half a step; the
   values a gesture writes (A, B, the blend, an absent scene, skipped flats);
   the scene a blend saves (XVOL, SCENES P2's bytes); page 2 (SCENES P2's cells): read, blended as its
   frame pass morphs them at every fader position, cleared, set.
2. With m68k-elf-gcc on the PATH, checks apply_unit.s is generate.py's output
   of apply.c, adapter.c and hooks.s, and that the state read before the unit
   writes it is in .data: the unit's .bss is not zeroed at boot.

What it cannot show: the unit in the firmware (tools/verify/verify_apply_scene.py
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
DATA_SYMS = ('aps_owned',)


def host():
    with tempfile.TemporaryDirectory() as td:
        exe = pathlib.Path(td) / 'engine'
        subprocess.run([CC, *FLAGS, '-o', str(exe), 'apply.c', 'test_apply.c'], cwd=HERE, check=True)
        r = subprocess.run([str(exe)], capture_output=True, text=True)
        print(r.stdout.rstrip())
        if r.returncode:
            sys.exit('[FAIL] APPLY SCENE engine')


def data_syms():
    """The symbols read before the unit first writes them: in .data, never .bss."""
    unit = (HERE / 'apply_unit.s').read_text().splitlines()
    section, where = '.text', {}
    for line in unit:
        w = line.split()
        if w[:1] in (['.section'], ['.data'], ['.bss'], ['.text']):
            section = w[1].split(',')[0] if w[0] == '.section' else w[0]
        elif len(w) == 1 and w[0].endswith(':') and w[0][:-1] in DATA_SYMS:
            where[w[0][:-1]] = section
    bad = {k: where.get(k) for k in DATA_SYMS if where.get(k) != '.data'}
    if bad:
        sys.exit(f'[FAIL] APPLY SCENE state not in .data (the unit boots with .bss nonzero): {bad}')
    print('  .data: ' + ', '.join(DATA_SYMS))


def generated():
    if not shutil.which('m68k-elf-gcc'):
        print('[SKIP] m68k-elf-gcc not on PATH: apply_unit.s not checked')
        return
    r = subprocess.run([sys.executable, str(HERE / 'generate.py'), '--check'], capture_output=True, text=True)
    print('  ' + (r.stdout + r.stderr).strip())
    if r.returncode:
        sys.exit('[FAIL] apply_unit.s is not generate.py\'s output')


if __name__ == '__main__':
    print('APPLY SCENE engine')
    host()
    generated()
    data_syms()
    print('[PASS] APPLY SCENE engine')
