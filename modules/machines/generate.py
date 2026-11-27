#!/usr/bin/env python3
"""Build the ColdFire unit `machines_unit.s` from machines.c + machines.s, or --check that the
checked-in copy is current. Needs m68k-elf-gcc. Reads no firmware.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools/build"))
import c_unit  # noqa: E402  (tools/build/c_unit.py: compile, checks, --check / --dry)

# A sample remix.inc for the assembly check: two clients.
SAMPLE_INC = """.set MC_END, 7
mc_count: .long 2
mc_sigs: .long 0, 0
mc_defaults: .long 0, 0
mc_flags: .long 0, 0
mc_pages: .long 0, 0
mc_ticks: .long 0, 0
mc_keeps: .long 0, 0
mc_src_names: .long 0, 0, 0, 0, 0, 0, 0
"""


UNIT = c_unit.Unit(HERE, 'machines_unit.s', ('machines.c',), asm=('machines.s',), remix_inc=SAMPLE_INC,
                   asm_first=True)

if __name__ == '__main__':
    c_unit.main(UNIT)
