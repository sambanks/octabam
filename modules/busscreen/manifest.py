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
ENC_MEMBER = 4
KEY_OFF = 0x180                        # key
ENTER_REV_OFF = 0x1de                  # REVERB row action
ENTER_DLY_OFF = 0x1e2                  # DELAY row action
ENC_OFF = 0x228                        # encoder

# The CONTROL submenu (docs/MAINMENU.md 2, same as modules/menushortcut): its
# count is at CONTROL_DESC+0 and its row-array pointer at +0x18. We relocate
# the six rows into the cave, append a "BUS FX" row whose action enters the
# screen, repoint the pointer and bump the count to 7. An action row is
# window 0, child 0, id 0 -- the id-0 path calls +0x08 with argument 0.
CONTROL_DESC = 0x400cbd54
CONTROL_ROWS = 0x400cc5a8
ROW_LEN, ROW_N = 24, 6
REV_LABEL = b"REVERB\0"
DLY_LABEL = b"DELAY\0"

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
    "4fefffd448d77cfc286f00304a8c670001662e3946c824566700015c7000103980000003223c000018b24c010000de807c001c39800000002047d1fc0008ed88d1c6700010104bf940bad0004df940bad01c7206b280660c4bf940bad0044df940bad020200672184c0100002647d7fc0008ee9ad7c0d7fc000000122006721e4c0100002447d5fc0008ef5ad5c0d5fc000000122e3940bad01870064c00780076002803e78c50842a03da87203940bad010b0836622487940bad0144878ffff2f04487800012f0c4879400ba8764eb940012bd84fef001824355c002f024878ffff2f044878000a2f0c4879400ba8764eb940012bd84fef001870007206b2856e061032580060041033580022765c002209671622115381b0816f0220014a806c02700024310c04601e2f00487940bad008487940bad00c4eb940013a084fef000c243c40bad00c2803e78c50842f024878ffff2f04487800362f0c4879400ba8764eb940012bd84fef001852837006b0836e00ff2e4cd77cfc4fef002c4e75202f0004223940bad010243940bad0187633b68067147634b680670e7635b680671a7636b680671460324a8167045381601e4a8267265382720560147605b68167045281600a7601b68267105282720023c140bad01023c240bad0184e7570076002700641f980000ecc720014180282000000ffb480670a52817408b4816eec600613c180000000700023c040bad01023c040bad018701023c0400cbf40700d23c0400cbd9c4e754fefffd448d77cfc2a2f0034263940bad01870064c003800203940bad010d6807c001c39800000007000103980000003223c000018b24c0100002e3946c82456de807006b0836e1a700423c0460d5c3020035d802f052f004eb94003a474508f6044200672184c0100002047d1fc0008ee9ad1c0d1fc00000012d1c370001010d0856c027000727fb2806c02200122030681000000182f002f012f064eb940054cd84fef000c4cd77cfc4fef002c4e75")
# placeholder marker -> which emitted-blob field it is patched to.
MARKS = {
    "40bad000": "verbtab",
    "40bad004": "dlytab",
    "40bad008": "fmt",
    "40bad00c": "scratch",
    "40bad010": "cursor",
    "40bad014": "gt",
    "40bad018": "page",
    "40bad01c": "verbsel",
    "40bad020": "dlysel",
}

# The twelve parameter names of each engine, slot order (page 1 then page 2),
# matching modules/busverb and modules/busdelay.
VERB_NAMES = (b"TIME", b"MOD", b"SIZE", b"HP", b"LP", b"IN",
              b"MODE", b"SHMR", b"DIFF", b"SHFT", b"GATE", b"RATE")
DLY_NAMES = (b"TIME", b"FDBK", b"TONE", b"PING", b"-VRB", b"PTCH",
             b"MDEP", b"MODE", b"MRAT", b"SIZE", b"DRV", b"FRZE")

# Per-engine SELECT slots and their labels (count < 128 in the manifests),
# so the screen prints ROOM/PLATE/BIG etc. instead of a raw number. slot ->
# labels, value clamped to the count.
VERB_SELECTS = {6: (b"ROOM", b"PLATE", b"BIG"),
                9: (b"+12", b"+19", b"+7", b"-12"),
                11: (b"0.5x", b"1x", b"2x", b"4x")}
DLY_SELECTS = {6: (b"CLEAN", b"GRAIN", b"REVRS"),
               9: (b"46MS", b"93MS", b"23MS", b"XTRM"),
               11: (b"RUN", b"HOLD")}

_STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
_BASE = 0x40000400


def _stock_table() -> bytes:
    d = _STOCK.read_bytes()
    a = STATE_TABLE - _BASE
    return d[a:a + ENTRY_LEN * ENTRY_N]


def _stock_control_rows() -> bytes:
    d = _STOCK.read_bytes()
    a = CONTROL_ROWS - _BASE
    return d[a:a + ROW_LEN * ROW_N]


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

    # per-engine SELECT records: for each slot a {count, labelptr...} record,
    # then a 12-entry table (0 for a knob). The draw indexes it by slot.
    def place_selects(selmap):
        recs = [0] * 12
        for slot, labels in selmap.items():
            ptrs = []
            for lb in labels:
                ptrs.append(addr + body_off + len(data))
                data.extend(lb + b"\0")
            while (body_off + len(data)) % 4:
                data.append(0)
            rec_here = body_off + len(data)
            data.extend(len(labels).to_bytes(4, "big"))
            for pr in ptrs:
                data.extend(pr.to_bytes(4, "big"))
            recs[slot] = addr + rec_here
        while (body_off + len(data)) % 4:
            data.append(0)
        tab_here = body_off + len(data)
        for e in recs:
            data.extend((e or 0).to_bytes(4, "big"))
        return tab_here
    verbsel_here = place_selects(VERB_SELECTS)
    dlysel_here = place_selects(DLY_SELECTS)
    scratch_here = body_off + len(data)
    data.extend(b"\0" * 8)
    cursor_here = body_off + len(data)
    data.extend(b"\0" * 4)                            # cursor row 0..5, init 0
    page_here = body_off + len(data)
    data.extend(b"\0" * 4)                            # page 0/1, init 0
    gt_here = body_off + len(data)
    data.extend(b">\0")

    targets = {
        "verbtab": addr + verbtab_here,
        "dlytab": addr + dlytab_here,
        "fmt": addr + fmt_here,
        "scratch": addr + scratch_here,
        "cursor": addr + cursor_here,
        "page": addr + page_here,
        "gt": addr + gt_here,
        "verbsel": addr + verbsel_here,
        "dlysel": addr + dlysel_here,
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
    entry[ENC_MEMBER * 4:ENC_MEMBER * 4 + 4] = (addr + handler_off + ENC_OFF).to_bytes(4, "big")

    # ---- two CONTROL rows: REVERB and DELAY ------------------------------
    rev_action = handler_off + ENTER_REV_OFF
    dly_action = handler_off + ENTER_DLY_OFF
    rev_label_here = body_off + len(data)
    data.extend(REV_LABEL)
    dly_label_here = body_off + len(data)
    data.extend(DLY_LABEL)
    while (body_off + len(data)) % 4:
        data.append(0)
    ctrl_rows_here = body_off + len(data)
    rows = bytearray(_stock_control_rows())
    for label_here, action in ((rev_label_here, rev_action),
                               (dly_label_here, dly_action)):
        rows += (addr + label_here).to_bytes(4, "big")   # +0x00 label
        rows += b"\0" * 4                                 # +0x04 no window
        rows += (addr + action).to_bytes(4, "big")        # +0x08 action
        rows += b"\0" * 4                                 # +0x0c
        rows += b"\0" * 4                                 # +0x10 no child
        rows += b"\0" * 4                                 # +0x14 id 0 -> action
    data.extend(rows)

    blob = bytes(table) + bytes(entry) + bytes(handler) + bytes(data)
    pokes = tuple(
        (op, stock.to_bytes(4, "big"), (addr + moff).to_bytes(4, "big"))
        for op, stock, moff in TABLE_REFS
    ) + (
        (CONTROL_DESC, ROW_N.to_bytes(4, "big"), (ROW_N + 2).to_bytes(4, "big")),
        (CONTROL_DESC + 0x18, CONTROL_ROWS.to_bytes(4, "big"),
         (addr + ctrl_rows_here).to_bytes(4, "big")),
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
