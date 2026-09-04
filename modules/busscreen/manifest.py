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
DRAW_MEMBER = 2                        # {enter,exit,DRAW,key,enc}
KEY_MEMBER = 3
KEY_OFF = 0x11a                        # key: entry point offset within HANDLER

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

# screen_draw.s, assembled with m68k-elf-as -mcpu=5407. Four self-references
# the build patches to cave addresses (placeholders 0x40bad000/4/8/c):
#   VERBTAB, DLYTAB -- the two twelve-entry name pointer tables
#   FMT             -- the sprintf format string
#   SCRATCH         -- an 8-byte number buffer (appears twice in the code)
# verify_busscreen re-assembles the source and compares, so a drifted source
# cannot pass unnoticed.
HANDLER = bytes.fromhex(
    "4fefffd448d77cfc286f00304a8c670001002e3946c82456670000f67000103980000003223c000018b24c010000de807c001c39800000002047d1fc0008ed88d1c6700010104bf940bad0007206b28066064bf940bad0042006721e4c0100002647d7fc0008f084d7c076002803e78c5084203940bad010b0836622487940bad0144878ffff2f04487800012f0c4879400ba8764eb940012bd84fef001824353c002f024878ffff2f044878000a2f0c4879400ba8764eb940012bd84fef00187000103338002f00487940bad008487940bad00c4eb940013a084fef000c2803e78c5084487940bad00c4878ffff2f04487800362f0c4879400ba8764eb940012bd84fef00185283700cb0836e00ff5e4cd77cfc4fef002c4e75202f0004223940bad0107433b48066084a8167185381600e7434b480660e740bb4816708528123c140bad0104e75")
# placeholder marker -> which emitted-blob field it is patched to.
MARKS = {
    "40bad000": "verbtab",
    "40bad004": "dlytab",
    "40bad008": "fmt",
    "40bad00c": "scratch",
    "40bad010": "cursor",
    "40bad014": "gt",
}

# The twelve parameter names of each engine, slot order (page 1 then page 2),
# matching modules/busverb and modules/busdelay.
VERB_NAMES = (b"TIME", b"MOD", b"SIZE", b"HP", b"LP", b"IN",
              b"MODE", b"SHMR", b"DIFF", b"SHFT", b"GATE", b"RATE")
DLY_NAMES = (b"TIME", b"FDBK", b"TONE", b"PING", b"-VRB", b"PTCH",
             b"MDEP", b"MODE", b"MRAT", b"SIZE", b"DRV", b"FRZE")

_STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
_BASE = 0x40000400


def _stock_table() -> bytes:
    d = _STOCK.read_bytes()
    a = STATE_TABLE - _BASE
    return d[a:a + ENTRY_LEN * ENTRY_N]


def emit(addr):
    """Relocated 17-entry table (17th DRAW -> our handler), the handler, both
    name tables and their strings, the sprintf format and a scratch buffer,
    then the six table-reference rewrites. Layout depends on `addr`, so this
    is emit() not pinned bytes."""
    table = bytearray(_stock_table())
    handler_off = ENTRY_LEN * (ENTRY_N + 1)
    body_off = handler_off + len(HANDLER)

    data = bytearray()
    def place(names):
        ptrs = []
        for nm in names:
            ptrs.append(addr + body_off + len(data))
            data.extend(nm + b"\0")
        return ptrs
    verb_ptrs = place(VERB_NAMES)
    dly_ptrs = place(DLY_NAMES)
    fmt_here = body_off + len(data)
    data.extend(b"%d\0")
    while (body_off + len(data)) % 4:
        data.append(0)
    verbtab_here = body_off + len(data)
    data.extend(b"".join(x.to_bytes(4, "big") for x in verb_ptrs))
    dlytab_here = body_off + len(data)
    data.extend(b"".join(x.to_bytes(4, "big") for x in dly_ptrs))
    scratch_here = body_off + len(data)
    data.extend(b"\0" * 8)
    cursor_here = body_off + len(data)
    data.extend(b"\0" * 4)                            # the cursor row, init 0
    gt_here = body_off + len(data)
    data.extend(b">\0")

    targets = {
        "verbtab": addr + verbtab_here,
        "dlytab": addr + dlytab_here,
        "fmt": addr + fmt_here,
        "scratch": addr + scratch_here,
        "cursor": addr + cursor_here,
        "gt": addr + gt_here,
    }
    handler = bytearray(HANDLER)
    for mark, field in MARKS.items():
        mb = bytes.fromhex(mark)
        want = targets[field].to_bytes(4, "big")
        i = handler.find(mb)
        assert i >= 0, "placeholder %s missing" % mark
        while i >= 0:
            handler[i:i + 4] = want
            i = handler.find(mb, i + 4)

    entry = bytearray(b"\0" * ENTRY_LEN)
    entry[DRAW_MEMBER * 4:DRAW_MEMBER * 4 + 4] = (addr + handler_off).to_bytes(4, "big")
    entry[KEY_MEMBER * 4:KEY_MEMBER * 4 + 4] = (addr + handler_off + KEY_OFF).to_bytes(4, "big")

    blob = bytes(table) + bytes(entry) + bytes(handler) + bytes(data)
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
