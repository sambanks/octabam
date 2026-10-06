"""CORE -- the OBAM store's run-time layers on the unit (docs/proposals/STORE.md).

This increment: card-layer FX page defaults, read-only. At each LOAD PROJECT
and at the power-up's bank load the core reads /OCTABAM/card.work (card.strd
by the pair rule) and writes each valid default record over its effect's
descriptor defaults; the choosers and the new-part initialiser read them
from there. Written by tools/hw/ot_store.py on a computer; the unit's own
SAVE AS DEFAULT, the SETTINGS list, the project pair and the CS1 block are
the next increments. README.md.
"""
import os
import pathlib
import struct
import sys

from remix import schema
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, SymbolRef

H = bytes.fromhex
SOURCE = "modules/core/core.s"


def fx_inc(modules):
    """The `remix.inc` core.s includes: core_fx[], one 36-byte entry per
    selected effect with knobs (store.fx_targets): layout hash, store id
    pointer, twelve keys, fx id, id length."""
    sys.path.insert(0, str(pathlib.Path(schema.__file__).resolve().parents[1]))
    from remix import store
    mods = modules if isinstance(modules, dict) else {}
    targets = [m for m in mods.values() if m.menu is not None and len(m.params) == 12]
    out = ["| remix.inc -- core_fx: the effects in this image (modules/core/manifest.py)",
           "        .section .rodata", "        .balign 4", "        .globl  core_fx, core_fx_n",
           f"core_fx_n: .long {len(targets)}", "core_fx:"]
    for i, m in enumerate(targets):
        keys = ", ".join(str(k) for k in store.fx_keys(m))
        out += [f"        .long   0x{store.fx_layout(m):08x}, core_id_{i}",
                f"        .word   {keys}",
                f"        .byte   0x{m.menu.fx2_id:02x}, {len(store.fx_store_id(m))}",
                "        .word   0"]
    for i, m in enumerate(targets):
        out.append(f'core_id_{i}: .ascii "{store.fx_store_id(m)}"')
    return "\n".join(out) + "\n" + menu_inc() + "\n        .text\n"


ROOT_ROWS, ROOT_DESC, ROOT_COUNT_AT = 0x400cc698, 0x400cbd8c, 0x400cbd8c
ICON_MASK = 0x400cbfc4                   # the stock categories' shared second plane
# OCTABAM's icon: 19 columns x 8 rows; the plane is one long per column,
# the column's pixels in its high byte, bit 0 the top row (stock's icons)
ICON = ("......#######......",
        ".....#.......#.....",
        ".....#..###..#.....",
        ".....#..#.#..#.....",
        ".....#..###..#.....",
        ".....#.......#.....",
        "......#######......",
        "...................")


def menu_inc():
    """The OCTABAM root category (docs/firmware/MAINMENU.md sections 1-5): the
    root row array with the four stock rows copied from the stock image at
    build time and OCTABAM appended, its icon, its list descriptor and rows.
    The heading row names the remix and the build tag."""
    img = (pathlib.Path(schema.__file__).resolve().parents[2] / "out/raw/section_3_MAIN_OS.bin").read_bytes()
    rows = img[ROOT_ROWS - 0x40000400:ROOT_ROWS - 0x40000400 + 4 * 24]
    words = struct.unpack(">24I", rows)
    head = f"{os.environ.get('REMIX', '?').upper()} {os.environ.get('BUILD', '79')}"[:20]
    cols = [sum(1 << r for r in range(8) if ICON[r][c] == "#") << 24 for c in range(19)]
    out = ["        .data", "        .balign 4", "        .globl  core_root_rows",
           "core_root_rows:"]
    for i in range(4):
        out.append("        .long   " + ", ".join(f"0x{w:08x}" for w in words[i * 6:i * 6 + 6]))
    out += ["        .long   core_lbl_root, core_icon, 0, 0, core_list, 0",
            "core_icon: .long 0x13, 0x09, 0x01, core_icon_plane, " + f"0x{ICON_MASK:08x}",
            "core_icon_plane: .long " + ", ".join(f"0x{c:08x}" for c in cols),
            "        .balign 4",
            "core_list: .long 3, 0, 0, 0, 7, 3, core_rows",
            "core_rows:",
            "        .long   core_lbl_head, 0, 0, 0, 0, 0",
            "        .long   core_lbl_save, 0, core_menu_save, 0, 0, 0",
            "        .long   core_lbl_clear, 0, core_menu_clear, 0, 0, 0",
            'core_lbl_root: .asciz "OCTABAM"',
            f'core_lbl_head: .asciz "{head}"',
            'core_lbl_save: .asciz "SAVE AS DEFAULT"',
            'core_lbl_clear: .asciz "CLEAR DEFAULT"']
    return "\n".join(out)


MODULE = Module(
    name="core", key=schema.CORE_KEY, kind=Kind.CF_PATCH,
    category=Category.SETTINGS, author="Sam Banks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="`verify_core` under the port (6 Oct 2026); not on hardware",
    doc="The settings store on the unit: card-wide knob defaults read from OCTABAM/card.work at each project load (docs/proposals/STORE.md).",
    # MODEDEF_TABLE: MODE DEFAULTS' view table, 0 without that module.
    linked=(Linked("core", SOURCE, cpu="5475", dram=True, include=fx_inc,
                   defsyms=(("MODEDEF_TABLE", 0),)),),
    detours=(
        Detour(0x40085342, H("721b2d41fdc6"), "core", "core_on_load",
               "LOAD PROJECT, before the empty-project init: the card's defaults onto the descriptors", kind="jsr"),
        Detour(0x40084d4a, H("73b980000002"), "core", "core_on_bankload",
               "the bank load the power-up runs: the card's defaults onto the descriptors", kind="jsr"),
        Detour(0x4008485e, H("7192722db280"), "core", "core_on_job",
               "the engine task's job switch: type 0x41 runs SAVE AS DEFAULT"),
        *(Detour(site, H("4eb94008ee74"), "core", "core_on_store",
                 "SAVE PROJECT's project store: card.work copied to card.strd", kind="jsr")
          for site in (0x40085642, 0x400856dc, 0x40085780)),
    ),
    # the OCTABAM root category: the root list's rows pointer to core_root_rows
    # and its count 4 -> 5 (two modules growing the root are refused by the ledger)
    symbol_refs=(SymbolRef(ROOT_DESC + 0x18, ROOT_ROWS, "core", "core_root_rows",
                           "MAIN MENU root rows: the four stock categories + OCTABAM"),),
    pokes=(Poke(ROOT_COUNT_AT, H("00000004"), H("00000005"), "MAIN MENU root count: + OCTABAM"),),
    gates=(Gate("tools/verify/verify_core.py", remix_arg=False, venv=True, stage="image"),),
)
