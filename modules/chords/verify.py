#!/usr/bin/env python3
"""CHORDS FACTORY engine gate. Reads no firmware and runs no emulator.

1. Compiles the engine for the host and runs its tests (test_chords.c):
   every chord type at every root, inversion and spread built and named
   back; the voice leading's known cases (C -> F, Dm7 -> G7 -> Cmaj7 ...)
   and its properties over every pair of types and roots (every pitch class,
   no crossing, in the window, ranked, the root in the bass on request, as
   smooth as any built voicing); the scale's chords; the keyboard and the
   voice moves; the slots; chords.work's round trip and its checks.
2. With m68k-elf-gcc on the PATH, compiles the engine for the ColdFire
   (-mcpu=5475, freestanding) and refuses any undefined symbol; then checks
   chords_unit.s is generate.py's output of chords.c, adapter.c and hooks.s,
   and that the state read before the unit writes it is in .data: the
   unit's .bss is not zeroed at boot.

What it cannot show: the unit in the firmware (tools/verify/verify_chords.py
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
        subprocess.run([CC, *FLAGS, '-o', str(exe), 'chords.c', 'test_chords.c'], cwd=HERE, check=True)
        r = subprocess.run([str(exe)], capture_output=True, text=True)
        print(r.stdout.rstrip())
        if r.returncode:
            sys.exit('[FAIL] CHORDS FACTORY engine')


DATA_SYMS = ('ch_ready', 'ch_win', 'ch_pushed', 'ch_slot', 'ch_func', 'ch_answers', 'ch_on_n',
             'ch_on_ch', 'ch_on_held', 'ch_on_note', 'ch_on_left', 'ch_nowrite', 'ch_backup',
             'ch_held_n', 'ch_held_t', 'ch_held', 'ch_current',
             'ch_held_at', 'ch_ev', 'ch_ev_next', 'ch_pick', 'ch_up_pushed', 'ch_pk_win',
             'ch_pk_pushed')


def data_syms():
    """The symbols read before the unit first writes them: in .data, never .bss
    (the boot leaves .bss nonzero on the unit; FAILURE_MODES.md, image A7)."""
    unit = (HERE / 'chords_unit.s').read_text().splitlines()
    section, where = '.text', {}
    for line in unit:
        w = line.split()
        if w[:1] in (['.section'], ['.data'], ['.bss'], ['.text']):
            section = w[1].split(',')[0] if w[0] == '.section' else w[0]
        elif len(w) == 1 and w[0].endswith(':') and w[0][:-1] in DATA_SYMS:
            where[w[0][:-1]] = section
    bad = {k: where.get(k) for k in DATA_SYMS if where.get(k) != '.data'}
    if bad:
        sys.exit(f'[FAIL] CHORDS state not in .data (the unit boots with .bss nonzero): {bad}')
    print('  .data: ' + ', '.join(DATA_SYMS))


def coldfire():
    gcc = shutil.which('m68k-elf-gcc')
    if not gcc:
        print('[SKIP] m68k-elf-gcc not on PATH: ColdFire compile not checked')
        return False
    with tempfile.TemporaryDirectory() as td:
        obj = pathlib.Path(td) / 'chords.o'
        subprocess.run([gcc, *CF_FLAGS, '-c', '-o', str(obj), 'chords.c'], cwd=HERE, check=True)
        nm = shutil.which('m68k-elf-nm')
        undef = subprocess.run([nm, '-u', str(obj)], capture_output=True, text=True, check=True).stdout.split()
        undef = [u for u in undef if u != 'U']
        if undef:
            sys.exit(f'[FAIL] the ColdFire engine needs {undef}')
        size = subprocess.run([shutil.which('m68k-elf-size'), str(obj)], capture_output=True, text=True).stdout
        print('  ColdFire: ' + ' '.join(size.splitlines()[-1].split()[:3]) + ' (text data bss), no outside call')
    if subprocess.run([sys.executable, 'generate.py', '--check'], cwd=HERE).returncode:
        sys.exit('[FAIL] chords_unit.s (see the message above)')
    data_syms()
    return True


if __name__ == '__main__':
    if not CC:
        sys.exit('[FAIL] no host C compiler')
    host()
    cf = coldfire()
    print('[PASS] CHORDS FACTORY engine' + (' (host and ColdFire compile)' if cf else ' (host only)')
          + ' -- the port: tools/verify/verify_chords.py')
