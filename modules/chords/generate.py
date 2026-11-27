#!/usr/bin/env python3
"""Build the ColdFire unit `chords_unit.s` from chords.c + adapter.c + hooks.s,
or --check that the checked-in copy is current, or --dry to compile only.
The engine stays in C; the builder links GNU-as.

Needs m68k-elf-gcc. Reads no firmware.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools/build"))
import c_unit  # noqa: E402  (tools/build/c_unit.py: compile, checks, --check / --dry)

SOURCES = ('chords.c', 'adapter.c')
# Stock targets the unit may reach besides its own labels: SCALES' service
# (sc_track, sc_mask, sc_keyboard), STORE's (files, the Part reads); adapter.c's window,
# layer, drawing and MIDI calls (its enum). GCC prints those in decimal: the
# scan reads both.
STOCK_CALLS = {'sc_track', 'sc_mask', 'sc_keyboard',
               '0x40012254', '0x40012bd8', '0x40012f30', '0x4003146c', '0x40031494', '0x40035624',
               '0x40055db4', '0x4005829c', '0x40016388', '0x40010bc8',
               'store_path', 'store_fopen', 'store_fread', 'store_fwrite', 'store_fclose', 'store_crc32',
               'store_refuse', 'store_part_ui_context', 'store_part_midi_read',
               '0x4009e9a8', '0x40000c3c', '0x4007e998', '0x400135b0', '0x400131a0',
               '0x40035a00', '0x4003604c', '0x400502d4', '0x4005029c', '0x400444f8', '0x400441fc',
               '0x40013904', '0x4003601a', '0x40035f98', '0x400453e2', '0x40044b7c', '0x400455f2', '0x4004550a', '0x4004400c', '0x400444f8',
               '0x40057c84', '0x400356a8', '0x400128a8', '0x40011910',
               '0x40027e00', '0x4009da20', '0x4005a2b8', '0x4004d948'}


UNIT = c_unit.Unit(HERE, 'chords_unit.s', SOURCES, asm=('hooks.s',), stock_calls=STOCK_CALLS,
                   # the build's remix.inc sets HAVE_SCALES; both forms must assemble
                   remix_inc='.set HAVE_SCALES, 1\n.set CH_CLIENT, 8\n')

if __name__ == '__main__':
    c_unit.main(UNIT)
