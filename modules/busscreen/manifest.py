"""BUS SCREEN -- a MAIN MENU editor for the bus effects.

Goal: a twelve-row screen that edits every control of BusVerb and BusDelay
off the track (docs/MAINMENU.md 9c-ii, 9e). Built in steps, each verifiable
in the emulator with no flash (the EDIT side alone is a flash question, 9c-ii):

  STEP 1 -- grow the menu-state table at 0x400cbdac from 16 entries to 17,
    relocated to a cave with the three `lea` references repointed (9a).
  STEP 2 (this commit) -- the 17th state's DRAW handler renders twelve
    labelled rows through the firmware's own text primitive. Labels are
    BusVerb's twelve parameter names; live VALUES and engine-switch are
    step 3, and the encoder handler (the edit) is step 4.

The 17th entry: draw = our handler in the cave; on_enter/on_exit/key/encoder
are 0 (NULL members are skipped -- 9a), so the state draws and does nothing
else yet. tools/verify_busscreen.py enters state 16 in the emulator and
confirms the twelve names are drawn, and re-assembles screen_draw.s to prove
the shipped bytes still match the source.
"""

import pathlib

from remix.schema import CavePatch, Kind, Module

STATE_TABLE = 0x400cbdac
ENTRY_LEN, ENTRY_N = 0x14, 16
DRAW_MEMBER = 2                        # {enter,exit,DRAW,key,enc}: draw is index 2

# EVERY reference to the state table, as (operand_addr, stock_operand,
# member_offset). docs/MAINMENU.md 9a listed only the three `lea` sites for the
# ENTER member (member 0); the dispatchers for DRAW, KEY and ENCODER each name
# the table too, as `addal #(base+member_off),%a0` immediates -- found 4 Sep
# 2026 when a grown table drew nothing because MENU_DRAW still read the stock
# one. All six must move together, each rewritten to new_base + its member
# offset. (The EXIT member, +4, has no such reference: it is reached another
# way and needs no repoint.)
TABLE_REFS = (
    (0x40064bd4, STATE_TABLE + 0x0, 0x0),    # enter, lea (43f9)
    (0x40064e36, STATE_TABLE + 0x0, 0x0),    # enter, lea (41f9)
    (0x400650e8, STATE_TABLE + 0x0, 0x0),    # enter, lea (43f9)
    (0x40064e04, STATE_TABLE + 0x8, 0x8),    # draw,  addal (d1fc)
    (0x4006511c, STATE_TABLE + 0xc, 0xc),    # key,   addal (d1fc)
    (0x40065086, STATE_TABLE + 0x10, 0x10),  # enc,   addal (d1fc)
)

# screen_draw.s, assembled with m68k-elf-as -mcpu=5407. The one self-reference
# is `lea LABELTAB,%a5` at byte 18: a placeholder 0x40bad000 the build patches
# to the cave's own pointer-table address. verify_busscreen re-assembles the
# source and compares, so a drifted source cannot pass unnoticed.
HANDLER = bytes.fromhex(
    "4fefffd848d77c7c286f002c4a8c6738"
    "4bf940bad00076002435" "3c002803e78c5084"
    "2f024878ffff2f0448780008" "2f0c4879400ba8764eb940012bd8"
    "4fef00185283700cb0836ed04cd77c7c4fef00284e75")
LABELTAB_OFF = 18                      # the placeholder operand, patched in emit
LABELTAB_MARK = bytes.fromhex("40bad000")

# BusVerb's twelve parameter names, slot order (page 1 then page 2). Step 3
# replaces these with per-engine names AND live values; for now they are the
# static proof that twelve rows draw.
LABELS = (b"TIME", b"MOD", b"SIZE", b"HP", b"LP", b"IN",
          b"MODE", b"SHMR", b"DIFF", b"SHFT", b"GATE", b"RATE")

_STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
_BASE = 0x40000400


def _stock_table() -> bytes:
    d = _STOCK.read_bytes()
    a = STATE_TABLE - _BASE
    return d[a:a + ENTRY_LEN * ENTRY_N]


def emit(addr: int):
    """The relocated 17-entry table (17th = a state-2 clone with its DRAW
    field repointed at our handler and its other members zeroed), the draw
    handler, the twelve label strings, and the pointer table the handler
    walks. Then the three `lea` operand rewrites that move every reference to
    the table. Layout is a function of `addr` (the handler names its own
    pointer table), which is why this is emit() rather than pinned bytes."""
    table = bytearray(_stock_table())

    draw_off = ENTRY_LEN * (ENTRY_N + 1)                 # handler follows 17 entries
    strings_off = draw_off + len(HANDLER)

    # place the strings, remember each absolute address
    blob = bytearray()
    str_at = []
    cur = strings_off
    strings = bytearray()
    for s in LABELS:
        str_at.append(addr + cur)
        strings += s + b"\0"
        cur += len(s) + 1
    while cur % 4:                                       # align the pointer table
        strings += b"\0"
        cur += 1
    ptrtab_off = cur
    ptrtab = b"".join(a.to_bytes(4, "big") for a in str_at)

    # the 17th entry: clone of state 2, draw member -> our handler, rest zeroed
    entry = bytearray(b"\0" * ENTRY_LEN)
    entry[DRAW_MEMBER * 4:DRAW_MEMBER * 4 + 4] = (addr + draw_off).to_bytes(4, "big")

    # the handler, with its LABELTAB placeholder patched to the pointer table
    handler = bytearray(HANDLER)
    assert handler[LABELTAB_OFF:LABELTAB_OFF + 4] == LABELTAB_MARK, \
        "screen_draw.s LABELTAB placeholder moved -- re-pin HANDLER/LABELTAB_OFF"
    handler[LABELTAB_OFF:LABELTAB_OFF + 4] = (addr + ptrtab_off).to_bytes(4, "big")

    blob = bytes(table) + bytes(entry) + bytes(handler) + bytes(strings) + ptrtab

    pokes = tuple(
        (op, stock.to_bytes(4, "big"), (addr + moff).to_bytes(4, "big"))
        for op, stock, moff in TABLE_REFS
    )
    return blob, pokes


MODULE = Module(
    name="busscreen",
    key="BUS SCREEN",
    kind=Kind.CF_PATCH,
    doc="A MAIN MENU screen that draws the bus effects' twelve rows.",
    cf_patches=(CavePatch(
        label="bus screen: menu-state table + draw handler",
        cave_addr=None,                   # float: content carries its own base
        pinned=b"",
        source="modules/busscreen/screen_draw.s",
        emit=emit,
        report_note=" (17th menu state + 12-row draw handler)",
    ),),
)
