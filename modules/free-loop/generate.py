#!/usr/bin/env python3
"""Build the ColdFire unit `free_loop.s` from freeloop.c + adapter.c +
hooks.s, or --check that the checked-in copy is current, or --dry to
compile only. The engine stays in C; the builder links GNU-as.

Needs m68k-elf-gcc (Homebrew's bottle or the SDK toolchain). Reads no
firmware.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools/build"))
import c_unit  # noqa: E402  (tools/build/c_unit.py: compile, checks, --check / --dry)

SOURCES = ('freeloop.c', 'adapter.c')
# Stock targets the unit may reach besides its own labels: the detour
# stubs' returns (0x4000e7a4, 0x4009da16, 0x4009d9ae, 0x40056c2e, 0x40006d20), the CC
# handler's stock calls (0x40001854 the channel map,
# 0x40033970 the auto guard, 0x4009a404 / 0x400a1030 the cue) and STORE's
# file calls; and the stock routines adapter.c calls through FN (its enums:
# the recorder mailbox, MIDI Start / Stop, the drawing calls, the file copy,
# CLEAR SLOT, the layers, the window, the toast, the tempo). GCC prints
# those in decimal: the scan reads both.
STOCK_CALLS = {'0x4000e7a4', '0x4009da16', '0x4009d9ae', '0x40056c2e', '0x40006d20', '0x40001854', '0x40033970',
               '0x4009a404', '0x400a1030', 'store_path', 'store_fopen', 'store_fread', 'store_fwrite',
               'store_fclose', 'store_crc32', 'store_refuse',
               '0x40005178', '0x4000a1e0', '0x4000a274', '0x40011910', '0x40012254', '0x40012bd8',
               '0x40012f30', '0x40016388', '0x4002557c', '0x4003146c', '0x40031494', '0x40035624',
               '0x40055db4', '0x40056f4c', '0x4005829c', '0x4005a2b8', '0x4009c708', '0x400053d8',
               '0x40033e3c', '0x4004c012', '0x4004c024', '0x4004c02a',   # CC_SEND; the edge renderer's draw, blit, skip
               '0x40008f84', '0x4009d3a6', '0x4009d91a',   # RELEASE; the record builder's trig, no-trig exits
               'rtm_gate',   # REC_TRIG_MUTE's, beside it under HOOKS (HK_REC_GATE)
               'rl_uitick'}  # RELOAD_FROM_PROJECT's, beside it under HOOKS (HK_UI_TICK}


UNIT = c_unit.Unit(HERE, 'free_loop.s', SOURCES, asm=('hooks.s',), stock_calls=STOCK_CALLS,
                   defsyms=(('FL_CLIENT', 5),))   # manifest.py's defsym

if __name__ == '__main__':
    c_unit.main(UNIT)
