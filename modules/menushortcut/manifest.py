"""MENU SHORTCUT -- MAIN MENU > CONTROL > REVERB / DELAY.

The bus servers live on a track, so reaching their controls means finding
which track hosts them and pressing [FX2] there. This adds two rows to the
CONTROL submenu that do it for you: each selects the track HOSTING that
server and opens its EFFECT 2 SETUP window.

NOTHING ABOUT THE DATA MODEL MOVES. The parameters still live on the host
track's FX2 page, in the Part, scene-lockable, reachable by CC exactly as
before -- this is navigation only, which is what makes it cheap. A control
surface of its own would need a parameter store of its own, and that is the
swamp `docs/MAINMENU.md` section 6 declines.

HOW (docs/MAINMENU.md sections 2-5, 7, all traced there):

  * the CONTROL list descriptor at 0x400cbd54 holds its count at +0x00 and
    its row array pointer at +0x18. The array cannot grow in place, so the
    build copies the six rows into this cave, appends two, repoints the
    pointer and bumps the count to 8. Two writes, both asserted against the
    stock bytes first.
  * a row is 24 bytes: label, window descriptor, action, 0, child, page id.
    An ACTION row -- window 0, child 0, action set, id 0 -- is the shape
    SYSTEM's USB DISK MODE and OS UPGRADE already use, so it is proven at
    submenu level rather than inferred.
  * the action is menu_shortcut.s: guard MIDI mode, set the page-kind
    globals, close the menu, select the host track, open EFFECT 2 SETUP.

⚠️ CONTROL, NOT THE ROOT MENU. A fifth root row is two writes as well
(MAINMENU.md section 5) and one press shallower -- but PROJECT's and
SYSTEM's descriptor addresses are hard-compared at 0x40064fa0..c2 for an
alternate-list swap whose semantics are unknown, and a root leaf with no
window descriptor is a shape stock never uses. CONTROL is the shape stock
already runs. The row can move up once the emulator has walked this one.

⚠️ UNFLASHED, and priced honestly in MAINMENU.md section 7 at ~65% for a
first flash. The two inferences that carry the risk: that closing the menu
from inside an action is safe (stock's own [NO] does it) and that the
per-track FX2 id array is where tempo_cave.s reads it. The second degrades
to "opens the current track's page" rather than crashing.
"""

import pathlib

from remix.schema import CavePatch, Kind, Module

# The CONTROL submenu, from docs/MAINMENU.md section 2.
CONTROL_DESC = 0x400cbd54          # count at +0x00, rows pointer at +0x18
CONTROL_ROWS = 0x400cc5a8
ROW_LEN, ROW_N = 24, 6
# menu_shortcut.s, assembled with m68k-elf-as -mcpu=5407. Position independent:
# every address it names is an OS absolute, so it may be planted anywhere.
# menu_shortcut.s, assembled with m68k-elf-as -mcpu=5407. Position
# independent: every address it names is an OS absolute, so the cave may be
# planted wherever the placer has room. Spelled out in full rather than
# chunked -- these bytes ARE the contract, and a transcription slip in a cave
# is a crash on the unit.
HANDLER = bytes.fromhex(
    "70 07 60 02 70 06 4a b9 80 00 00 12 66 4c 72 04"
    "23 c1 46 0d 16 84 13 c1 46 c7 d8 d8 41 f9 80 00"
    "0e cc 72 00 14 18 02 82 00 00 00 ff b4 80 67 0c"
    "52 81 0c 81 00 00 00 08 6d ea 72 ff 2f 01 4e b9"
    "40 06 4b c0 22 1f 4a 81 6d 0a 2f 01 4e b9 40 08"
    "3b f8 58 8f 4e b9 40 05 99 6c 4e 75".replace(" ", ""))
REV_ENTRY, DLY_ENTRY = 0, 4        # hrev, hdly within HANDLER
LABELS = (b"REVERB\0", b"DELAY\0")

_STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
_BASE = 0x40000400


def _stock_rows() -> bytes:
    """The six CONTROL rows, read from the pristine image at build time so a
    firmware whose menu differs stops the build instead of being written
    over."""
    d = _STOCK.read_bytes()
    a = CONTROL_ROWS - _BASE
    return d[a:a + ROW_LEN * ROW_N]


def emit(addr: int):
    """The cave, and the two writes that hang it off CONTROL.

    Layout: handler, labels, then the eight rows -- the rows last because
    they are the only part whose CONTENT depends on `addr`.
    """
    blob = HANDLER
    lab_at = {}
    for text in LABELS:
        lab_at[text] = addr + len(blob)
        blob += text
    blob += b"\0" * (-len(blob) % 4)                  # rows want alignment
    rows_at = addr + len(blob)
    rows = bytearray(_stock_rows())
    for text, entry in zip(LABELS, (REV_ENTRY, DLY_ENTRY)):
        rows += (lab_at[text].to_bytes(4, "big")      # +0x00 label
                 + b"\0" * 4                          # +0x04 no window
                 + (addr + entry).to_bytes(4, "big")  # +0x08 action
                 + b"\0" * 4                          # +0x0c
                 + b"\0" * 4                          # +0x10 no child
                 + b"\0" * 4)                         # +0x14 id 0 -> action
    blob += bytes(rows)
    pokes = (
        (CONTROL_DESC, ROW_N.to_bytes(4, "big"),
         (ROW_N + len(LABELS)).to_bytes(4, "big")),
        (CONTROL_DESC + 0x18, CONTROL_ROWS.to_bytes(4, "big"),
         rows_at.to_bytes(4, "big")),
    )
    return blob, pokes


MODULE = Module(
    name="menushortcut",
    key="MENU SHORTCUT",
    kind=Kind.CF_PATCH,
    doc="MAIN MENU > CONTROL > REVERB / DELAY: jump to the host track's FX2 page.",
    cf_patches=(CavePatch(
        label="menu shortcut cave",
        # ⚠️ PINNED OUTSIDE THE CLONE WINDOW, at the unclaimed 2,064-byte zero
        # run docs/MAINMENU.md section 5 names. The floating region is where
        # descriptor clones and label formatters live, and the BamSep26 rig
        # leaves 84 bytes there -- this cave is 300. Nothing else claims this
        # run; the build refuses if it is not still zero.
        cave_addr=0x400d24d0,
        pinned=b"",                       # the content depends on the address
        source="modules/menushortcut/menu_shortcut.s",
        emit=emit,
        report_note=" (CONTROL gains REVERB and DELAY rows)",
    ),),
)
