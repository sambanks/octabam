#!/usr/bin/env python3
"""Build PAGES' locks unit `locks_unit.s` from locks.c + locks.s, or --check that the checked-in
copy is current. The engine stays in C; the builder links GNU-as (remix.inc gives the clients).

Needs m68k-elf-gcc. Reads no firmware.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools/build"))
import c_unit  # noqa: E402  (tools/build/c_unit.py: compile, checks, --check / --dry)

# remix.inc's macros, empty, for the assembly check (manifest.py locks_inc writes the real ones)
STUB_INC = '.set PG_CLIENT, 10\n.macro pg_lk_ctx_calls\n.endm\n.macro pg_lk_shown_calls\n.endm\n.macro pg_lk_by_page name\n.endm\n.macro pg_lk_holds\n.space 8\n.endm\n'


UNIT = c_unit.Unit(HERE, 'locks_unit.s', ('locks.c',), asm=('locks.s',), remix_inc=STUB_INC)

if __name__ == '__main__':
    c_unit.main(UNIT)
