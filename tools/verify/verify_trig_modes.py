#!/usr/bin/env python3
"""Execute shared trig-mode dispatch with independent clients, without firmware."""
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN
from unicorn.m68k_const import *

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402,F401

BASE, STACK, DONE = 0x41000000, 0x47008000, 0x4700fff0
MODE, MIDI, GRID = 0x460d16f0, 0x80000012, 0x460d1736


class Probe:
    def __init__(self, selected):
        ns = runpy.run_path(str(ROOT / 'modules/trig-modes/manifest.py'))
        env = ns['registrations'].__globals__
        Mode = ns['Mode']
        env['CLIENTS'] = (
            Mode('A', 2, 'PROBE A', 30, 'a_key', 'a_leds', 'a_release', overlay='a_overlay'),
            Mode('B', 9, 'PROBE B', 20, 'b_key', 'b_leds', 'b_release', guide='b_guide', octave=True),
        )
        with tempfile.TemporaryDirectory(prefix='trig-modes-') as directory:
            p = Path(directory)
            (p / 'remix.inc').write_text(ns['mode_inc'](selected))
            stub = ['.text']
            for i, name in enumerate(('a_key', 'a_leds', 'b_key', 'b_leds', 'b_guide'), 1):
                stub += [f'.global {name}', f'{name}: moveq #{i},%d0', 'rts']
            stub += ['.global a_overlay', 'a_overlay: move.l 0x47000000,%d0', 'rts']
            for i, name in enumerate(('a_release', 'b_release')):
                stub += [f'.global {name}', f'{name}: move.l 4(%sp),%d0',
                         f'move.l %d0,{0x47000010+4*i:#x}',
                         'moveq #-1,%d0', 'moveq #-1,%d1', 'move.l %d0,%a0', 'move.l %d0,%a1', 'rts']
            (p / 'stubs.s').write_text('\n'.join(stub) + '\n')
            for name, source in (('modes', ROOT / 'modules/trig-modes/modes.s'), ('stubs', p / 'stubs.s')):
                subprocess.run(['m68k-elf-as', '-mcpu=54455', '-I', directory,
                                '-o', str(p / f'{name}.o'), str(source)], check=True)
            subprocess.run(['m68k-elf-ld', f'-Ttext={BASE:#x}', '-e', 'tm_key', '-o', str(p / 'modes.elf'),
                            str(p / 'modes.o'), str(p / 'stubs.o')], check=True)
            subprocess.run(['m68k-elf-objcopy', '-O', 'binary', str(p / 'modes.elf'), str(p / 'modes.bin')], check=True)
            raw = subprocess.check_output(['m68k-elf-nm', str(p / 'modes.elf')], text=True)
            self.symbols = {n: int(a, 16) for a, n in re.findall(r'^([0-9a-f]+) [A-Za-z] (\w+)$', raw, re.M)}
            image = (p / 'modes.bin').read_bytes()
        u = self.u = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        for start, size in ((BASE, 0x10000), (0x40000000, 0x100000), (0x460d0000, 0x10000),
                            (0x47000000, 0x10000), (0x80000000, 0x1000)):
            u.mem_map(start, size)
        u.mem_write(BASE, image)
        self.put(MIDI, 1)

    def put(self, address, value):
        self.u.mem_write(address, (value & 0xffffffff).to_bytes(4, 'big'))

    def get(self, address):
        return int.from_bytes(self.u.mem_read(address, 4), 'big')

    def call(self, name, mode=0, stop=DONE, args=()):
        self.put(MODE, mode)
        self.u.reg_write(UC_M68K_REG_SR, 0x2700)
        self.u.reg_write(UC_M68K_REG_A7, STACK)
        self.put(STACK, DONE)
        for i, a in enumerate(args):
            self.put(STACK + 4 + 4*i, a)
        self.u.emu_start(self.symbols[name], stop, count=2000)
        assert self.u.reg_read(UC_M68K_REG_PC) == stop, (name, hex(self.u.reg_read(UC_M68K_REG_PC)))
        return self.u.reg_read(UC_M68K_REG_D0)


def main():
    for selected, rows in (({'A'}, (0, 1, 2, 4)), ({'B'}, (0, 1, 9, 4)),
                           ({'A', 'B'}, (0, 1, 9, 2, 4))):
        m = Probe(selected)
        for mode in range(32):
            m.u.reg_write(UC_M68K_REG_D0, mode)
            assert m.call('tm_row') == (rows.index(mode) if mode in rows else 0)
        for owner, mode, key, led in (('A', 2, 1, 2), ('B', 9, 3, 4)):
            if owner in selected:
                assert m.call('tm_key', mode, stop=0x400502d4) == key
                assert m.call('tm_leds', mode) == led
        m.put(MIDI, 0)
        m.call('tm_key', 9, stop=0x400501de)
        assert m.u.reg_read(UC_M68K_REG_A7) == STACK - 4
        m.put(MIDI, 1)
        m.put(GRID, 1)
        m.call('tm_leds', 9, stop=0x40043fe4)
        assert m.u.reg_read(UC_M68K_REG_A7) == STACK - 68
        m.put(GRID, 0)
        if 'A' in selected:
            m.put(0x47000000, 77)
            assert m.call('tm_leds', 9) == 77, 'page overlay must precede the selected mode'
            m.put(0x47000000, 0)
        # Cleanup reaches both owners even when another mode is now selected.
        regs = (UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_A0, UC_M68K_REG_A1)
        before = {r: 0x12340000 + i for i, r in enumerate(regs)}
        for r, value in before.items(): m.u.reg_write(r, value)
        m.call('tm_release', 1, stop=0x40043730, args=(7,))
        assert {r: m.u.reg_read(r) for r in regs} == before
        assert m.u.reg_read(UC_M68K_REG_A7) == STACK - 16
        assert m.get(0x47000010) == (7 if 'A' in selected else 0)
        assert m.get(0x47000014) == (7 if 'B' in selected else 0)
    print('[ok] independent clients: sparse mode IDs, navigation, dispatch, audio/grid fallback, overlays and cleanup')


if __name__ == '__main__':
    main()
