#!/usr/bin/env python3
"""Build the ColdFire unit `drummer_unit.s` from drummer.c + adapter.c + hooks.s, or --check that the
checked-in copy is current, or --dry to compile only. The engine stays in C; the builder links GNU-as.

Needs m68k-elf-gcc. Reads no firmware.
"""
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools/build"))
import c_unit  # noqa: E402  (tools/build/c_unit.py: compile, checks, --check / --dry)

SOURCES = ('drummer.c', 'autokit.c', 'adapter.c', 'kit.c', 'store.c')
ASM = ('hooks.s',)
# Stock targets the unit may reach besides its own labels: the stubs' returns (0x400a2d88 the
# sequencer tick, 0x4000d3b4 the packer) and the stock FLEX start 0x4000f450.
STOCK_CALLS = {'0x400a2d88', '0x4000d3b4', '0x4000f450', '0x4009dcaa',
               # kit.c: the Part's edited mark
               '0x40027e00',
               # kit.c: the window, its drawing, the layers, the track's trig (CHORDS' and SCALES' calls)
               '0x40005030', '0x40012254', '0x40012bd8', '0x40011910', '0x4003146c', '0x40031494',
               '0x400356a8', '0x40055db4', '0x40057c84', '0x4005829c',
               # store.c: STORE's file calls and stock's file copy
               'store_path', 'store_fopen', 'store_fread', 'store_fwrite', 'store_fclose', 'store_crc32',
               'store_refuse', '0x40016388',
               # the kit file: the engine task's receive, its continuations, the queue post
               '0x40000d00', '0x4008484e', '0x4008485e', '0x40000c3c',
               # AUTO: stock's pool walk, the YES/NO box, the toast
               '0x4009499c', '0x4006d57c', '0x4005a2b8',
               # PAGES' locks (hooks.s, HAVE_PAGELOCKS)
               'pg_lk_step', 'pg_lk_value', 'pg_lk_shown', 'pg_lk_where'}


UNIT = c_unit.Unit(HERE, 'drummer_unit.s', SOURCES, asm=ASM, stock_calls=STOCK_CALLS,
                   remix_inc='.set HAVE_PAGELOCKS, 1\n.set DR_CLIENT, 8\n')   # manifest.py's drummer_inc

if __name__ == '__main__':
    # styles.inc, which drummer.c includes, is styles.py's output: refresh or check it first
    subprocess.run([sys.executable, str(HERE / 'styles.py')] + (['--check'] if '--check' in sys.argv else []), check=True)
    c_unit.main(UNIT)
