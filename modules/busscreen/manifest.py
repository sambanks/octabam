"""BUS SCREEN -- a MAIN MENU editor for the bus effects (STEP 1: the table).

The goal is a twelve-row screen that edits every control of BusVerb and
BusDelay off the track (docs/MAINMENU.md sections 9c-ii, 9e). This module is
the FOUNDATION that every later piece needs: it grows the menu-state table
from 16 entries to 17, so a bespoke screen can live in the 17th state.

WHY A NEW MENU STATE. docs/MAINMENU.md section 9a: the state table at
0x400cbdac is `{on_enter, on_exit, draw, key_handler, encoder_handler}` x 16,
0x14 bytes each, named by exactly THREE `lea` immediates and no pointer cell.
So it relocates like the FX1 chooser list (tools/build_fx1.py): copy the 16
entries to a cave, append a 17th, repoint the three `lea` operands.

STEP 1, THIS COMMIT: the 17th entry is a CLONE of state 2's handlers -- a
real, known-good state -- so the only thing under test is that the table can
be grown and the three references repointed WITHOUT breaking boot or menu
navigation. Proven with tools/verify_busscreen.py (in make check): the image
boots to the RTOS handoff and walks the MAIN MENU out of RAM, exactly as it
does without this module. The bespoke draw and encoder handlers that make it
an editor are later steps and land on top of this.

⚠️ The EDIT side of a bus screen cannot be proven locally at all -- the
page-2 editor's delta path reads live page-dispatcher state the emulator
does not supply (docs/MAINMENU.md 9c-ii tail). The DRAW side (a later step)
can. This step touches neither; it only moves the table.
"""

import pathlib

from remix.schema import CavePatch, Kind, Module

STATE_TABLE = 0x400cbdac          # {enter,exit,draw,key,enc} x 16, 0x14 each
ENTRY_LEN, ENTRY_N = 0x14, 16
# The three `lea 0x400cbdac,%aN` sites (docs/MAINMENU.md 9a). Each names the
# table in a 4-byte operand at the INSTRUCTION address + 2 (the 2-byte lea
# opcode 4Xf9 precedes it), confirmed against the booted image 4 Sep 2026.
LEA_SITES = (0x40064bd2, 0x40064e34, 0x400650e6)
LEA_OPCODES = (b"\x41\xf9", b"\x43\xf9", b"\x45\xf9", b"\x47\xf9",
               b"\x49\xf9", b"\x4b\xf9")
# STEP 1: the appended 17th state is a byte-copy of state 2 (a known-good
# state with a real draw and key handler). Its index within the table.
DONOR_STATE = 2

_STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
_BASE = 0x40000400


def _stock_table() -> bytes:
    d = _STOCK.read_bytes()
    a = STATE_TABLE - _BASE
    return d[a:a + ENTRY_LEN * ENTRY_N]


def emit(addr: int):
    """The relocated table (16 stock entries + a 17th), and the three operand
    rewrites that move every reference to it. Content is address-independent
    (the entries hold OS absolutes, the leas get the cave address), so the
    cave may float; the pokes carry the new base."""
    table = _stock_table()
    donor = table[DONOR_STATE * ENTRY_LEN:(DONOR_STATE + 1) * ENTRY_LEN]
    blob = table + donor                                   # 17 x 0x14
    pokes = tuple(
        (site + 2, STATE_TABLE.to_bytes(4, "big"), addr.to_bytes(4, "big"))
        for site in LEA_SITES
    )
    return blob, pokes


def _assert_leas():
    """Read at import time is not possible (no image yet); the build asserts
    each site holds a lea opcode + the stock operand before repointing. This
    mirrors tools/build_fx1.py's LIST_REFS check."""


MODULE = Module(
    name="busscreen",
    key="BUS SCREEN",
    kind=Kind.CF_PATCH,
    doc="Grow the menu-state table to 17 so a bus editor screen can live in it.",
    cf_patches=(CavePatch(
        label="menu-state table (relocated, +1 entry)",
        cave_addr=None,                   # float: content is position-independent
        pinned=b"",                       # depends on the cave address
        source=None,                      # pure data + pokes, no .s
        emit=emit,
        report_note=" (menu-state table 16 -> 17 entries)",
    ),),
)
