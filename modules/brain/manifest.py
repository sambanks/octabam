"""BRAIN -- the brain's run-time layers on the unit (docs/proposals/BRAIN.md).

This increment: card-layer FX page defaults, read-only. At each LOAD PROJECT
and at the power-up's bank load the brain reads /BRAIN/card.work (card.strd
by the pair rule) and writes each valid default record over its effect's
descriptor defaults; the choosers and the new-part initialiser read them
from there. Written by tools/hw/ot_brain.py on a computer; the unit's own
SAVE AS DEFAULT, the SETTINGS list, the project pair and the CS1 block are
the next increments. README.md.
"""
import os
import pathlib
import struct
import sys

from remix import schema
from remix.schema import (Binary, Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, Setting,
                          Store, SymbolRef)

H = bytes.fromhex
SOURCE = "modules/brain/brain.s"


def fx_inc(modules):
    """The `remix.inc` brain.s includes: brain_fx[], one 36-byte entry per
    selected effect with knobs (brain.fx_targets): layout hash, store id
    pointer, twelve keys, fx id, id length."""
    sys.path.insert(0, str(pathlib.Path(schema.__file__).resolve().parents[1]))
    from remix import brain
    mods = modules if isinstance(modules, dict) else {}
    targets = [m for m in mods.values() if m.menu is not None and len(m.params) == 12]
    out = ["| remix.inc -- brain_fx: the effects in this image (modules/brain/manifest.py)",
           "        .section .rodata", "        .balign 4", "        .globl  brain_fx, brain_fx_n",
           f"brain_fx_n: .long {len(targets)}", "brain_fx:"]
    for i, m in enumerate(targets):
        keys = ", ".join(str(k) for k in brain.fx_keys(m))
        out += [f"        .long   0x{brain.fx_layout(m):08x}, brain_id_{i}",
                f"        .word   {keys}",
                f"        .byte   0x{m.menu.fx2_id:02x}, {len(brain.fx_store_id(m))}",
                "        .word   0"]
    for i, m in enumerate(targets):
        out.append(f'brain_id_{i}: .ascii "{brain.fx_store_id(m)}"')
    return "\n".join(out) + "\n" + menu_inc() + "\n" + settings_inc(mods) + "\n        .text\n"


PANE_W = 15                              # characters BRAIN's list pane shows (brain.c PANE_W)


def settings_inc(mods):
    """brain_set[] and brain_values[]: one entry per setting the unit holds
    at run time (remix.brain.live_table), in the SETTINGS list's order.
    An entry is 40 bytes (brain.c struct set_ent): store id, id length,
    type (1 Binary, 2 Option, 3 Number), apply (0 live, 1 callback, 2 next
    boot), label count, key, min, max, the default after layers 1 and 2,
    the labels, the name, the module's key (the list's heading). Each value
    is a long with its own global (remix.brain.value_symbol), which a
    module's read macro loads."""
    from remix import brain, registry
    from remix.schema import Apply, Binary, Number, Option
    remix = registry.remix(os.environ.get("REMIX")) if os.environ.get("REMIX") else None
    rows = brain.live_table(remix, mods) if remix is not None else []
    applies = {Apply.LIVE: 0, Apply.CALLBACK: 1, Apply.NEXT_BOOT: 2}
    out = ["        .data", "        .balign 4", "        .globl  brain_set, brain_set_n, brain_values",
           f"brain_set_n: .long {len(rows)}", "brain_set:"]
    strs, groups = [], {}
    for i, (r, s, m) in enumerate(rows):
        k = s.kind
        widest = max(len(x) for x in (("ON", "OFF") if isinstance(k, Binary) else
                                      k.labels if isinstance(k, Option) else (str(k.min), str(k.max))))
        if len(s.name) + 1 + widest > PANE_W:
            raise ValueError(f"{m.key}: setting {s.name!r} and its widest value {widest} characters "
                             f"do not fit BRAIN's {PANE_W}-character list pane")
        if m.key not in groups:
            groups[m.key] = len(groups)
            g = m.key[:PANE_W - 2]
            # octal: gas's \x takes every hex digit after it (\x17B is one byte)
            strs.append(f'brain_sgrp_{groups[m.key]}: .asciz "\\027{g}' + "\\027" * (PANE_W - 1 - len(g)) + '"')
        typ, lo, hi, nl = ((1, 0, 1, 0) if isinstance(k, Binary) else
                           (2, 0, len(k.labels) - 1, len(k.labels)) if isinstance(k, Option) else
                           (3, k.min, k.max, 0))
        out += [f"        .long   brain_sid_{i}",
                f"        .byte   {len(r.store_id)}, {typ}, {applies[s.apply]}, {nl}",
                f"        .word   {r.key}, {k.step if isinstance(k, Number) else 1}",
                f"        .long   {lo}, {hi}, {int(r.value)}",
                f"        .long   {f'brain_slab_{i}' if nl else 0}, brain_snam_{i}, brain_sgrp_{groups[m.key]}"]
        strs += [f'brain_sid_{i}: .ascii "{r.store_id}"', f'brain_snam_{i}: .asciz "{s.name}"']
        if nl:
            strs.append(f"brain_slab_{i}: .long " + ", ".join(f"brain_slab_{i}_{j}" for j in range(nl)))
            strs += [f'brain_slab_{i}_{j}: .asciz "{lab}"' for j, lab in enumerate(k.labels)]
    out += ["        .balign 4", "brain_values:"]
    for r, s, m in rows:
        sym = brain.value_symbol(r.store_id, r.key)
        out += [f"        .globl  {sym}", f"{sym}: .long {int(r.value)}"]
    out += ["        .balign 4"] + strs + ["        .balign 4"]
    return "\n".join(out)


ROOT_ROWS, ROOT_DESC, ROOT_COUNT_AT = 0x400cc698, 0x400cbd8c, 0x400cbd8c
ICON_MASK = 0x400cbfc4                   # the stock categories' shared second plane
# BRAIN's icon: 19 columns x 8 rows; the plane is one long per column,
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
    """The BRAIN root category (docs/firmware/MAINMENU.md sections 1-5): the
    root row array with the four stock rows copied from the stock image at
    build time and BRAIN appended, its icon, its list descriptor and rows.
"""
    img = (pathlib.Path(schema.__file__).resolve().parents[2] / "out/raw/section_3_MAIN_OS.bin").read_bytes()
    rows = img[ROOT_ROWS - 0x40000400:ROOT_ROWS - 0x40000400 + 4 * 24]
    words = struct.unpack(">24I", rows)
    cols = [sum(1 << r for r in range(8) if ICON[r][c] == "#") << 24 for c in range(19)]
    out = ["        .data", "        .balign 4", "        .globl  brain_root_rows",
           "brain_root_rows:"]
    for i in range(4):
        out.append("        .long   " + ", ".join(f"0x{w:08x}" for w in words[i * 6:i * 6 + 6]))
    out += ["        .long   brain_lbl_root, brain_icon, 0, 0, brain_list, 0",
            "brain_icon: .long 0x13, 0x09, 0x01, brain_icon_plane, " + f"0x{ICON_MASK:08x}",
            "brain_icon_plane: .long " + ", ".join(f"0x{c:08x}" for c in cols),
            "        .balign 4",
            "        .globl  brain_list",
            # shipped at the top level; brain.c's show() repoints it
            "brain_list: .long 4, 0, 0, 0, 7, 4, brain_top_rows",
            "        .globl  brain_top_rows, brain_def_rows, brain_tool_rows, brain_rmx_rows, brain_rmx_n, brain_set_rows",
            "brain_top_rows:",
            "        .long   brain_lbl_settings, 0, brain_open_settings, 0, 0, 0",
            "        .long   brain_lbl_defaults, 0, brain_open_defaults, 0, 0, 0",
            "        .long   brain_lbl_remixes, 0, brain_open_remixes, 0, 0, 0",
            "        .long   brain_lbl_tools, 0, brain_open_tools, 0, 0, 0",
            "brain_def_rows:",
            "        .long   brain_lbl_bdefaults, 0, brain_menu_back, 0, 0, 0",
            "        .long   brain_lbl_save, 0, brain_menu_save, 0, 0, 0",
            "        .long   brain_lbl_clear, 0, brain_menu_clear, 0, 0, 0",
            "brain_tool_rows:",
            "        .long   brain_lbl_btools, 0, brain_menu_back, 0, 0, 0",
            "        .long   brain_lbl_log, 0, brain_menu_log, 0, 0, 0",
            # REMIXES: the back row, then REMIX SWITCH's rows (modules/
            # remix-switch/switch.s): up to NMAX (32) images and four text rows
            "brain_rmx_rows:",
            "        .long   brain_lbl_bremixes, 0, brain_menu_back, 0, 0, 0",
            "        .space  36 * 0x18",
            "brain_rmx_n: .long 1",
            # SETTINGS: the back row, then brain.c's rows (a heading per
            # module and each setting: up to 48 settings and their headings)
            "brain_set_rows:",
            "        .long   brain_lbl_bsettings, 0, brain_menu_back, 0, 0, 0",
            "        .space  97 * 0x18",
            'brain_lbl_root: .asciz "BRAIN"',
            # \x14 / \x13: the stock font's right and left arrows (drawn
            # under the port, 8 Oct 2026); \027 its separator dot
            'brain_lbl_settings: .asciz "SETTINGS    \\x14"',
            'brain_lbl_bsettings: .asciz "\\x13 SETTINGS"',
            'brain_lbl_defaults: .asciz "DEFAULTS    \\x14"',
            'brain_lbl_remixes: .asciz "REMIXES     \\x14"',
            'brain_lbl_tools: .asciz "TOOLS       \\x14"',
            'brain_lbl_bdefaults: .asciz "\\x13 DEFAULTS"',
            'brain_lbl_bremixes: .asciz "\\x13 REMIXES"',
            'brain_lbl_btools: .asciz "\\x13 TOOLS"',
            'brain_lbl_save: .asciz "SAVE AS DEFAULT"',
            'brain_lbl_clear: .asciz "CLEAR DEFAULT"',
            'brain_lbl_log: .asciz "WRITE DEBUG LOG"']
    return "\n".join(out)


# BRAIN_DIAG=noload (a diagnostic build): the two load-path hooks are left
# out, so nothing of BRAIN runs at boot or at a project load; the menu, the
# engine job switch and the store copy stay.
_NOLOAD = os.environ.get("BRAIN_DIAG") == "noload"

MODULE = Module(
    name="brain", key=schema.BRAIN_KEY, kind=Kind.CF_PATCH,
    category=Category.SETTINGS, author="Sam Banks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="`verify_brain` under the port (6 Oct 2026); not on hardware",
    doc="The settings store on the unit: card-wide knob defaults read from BRAIN/card.work at each project load (docs/proposals/BRAIN.md).",
    # MODEDEF_TABLE: MODE DEFAULTS' view table, 0 without that module.
    # BRAIN's own settings (SETTINGS > BRAIN), read by brain.c
    store=Store("octabam.brain"),
    settings=(Setting(1, "MIDI LOG", Binary(), default=1,
                      doc="the debug log records MIDI messages (TOOLS > WRITE DEBUG LOG); off, the MIDI thread's handler call returns at once after the handler"),
              Setting(2, "DEFAULTS", Binary(), default=1,
                      doc="the card's knob defaults (BRAIN/card.work) apply at each project load; off, every effect takes the image's defaults")),
    linked=(Linked("brain", SOURCE, cpu="5475", dram=True, include=fx_inc,
                   defsyms=(("MODEDEF_TABLE", 0),)),),
    detours=tuple(d for d in (
        Detour(0x40085342, H("721b2d41fdc6"), "brain", "brain_on_load",
               "LOAD PROJECT, before the empty-project init: the card's defaults onto the descriptors", kind="jsr"),
        Detour(0x40084d4a, H("73b980000002"), "brain", "brain_on_bankload",
               "the bank load the power-up runs: the card's defaults onto the descriptors", kind="jsr"),
        Detour(0x40005572, H("20720c004e90"), "brain", "brain_on_midi",
               "the MIDI thread's handler call: the debug log records each message and what it left", kind="jsr"),
        Detour(0x4008485e, H("7192722db280"), "brain", "brain_on_job",
               "the engine task's job switch: type 0x41 runs SAVE AS DEFAULT"),
        *(Detour(site, H("4eb94008ee74"), "brain", "brain_on_store",
                 "SAVE PROJECT's project store: card.work copied to card.strd", kind="jsr")
          for site in (0x40085642, 0x400856dc, 0x40085780)),
    ) if not (_NOLOAD and d.site in (0x40085342, 0x40084d4a))),
    # the BRAIN root category: the root list's rows pointer to brain_root_rows
    # and its count 4 -> 5 (two modules growing the root are refused by the ledger)
    symbol_refs=(SymbolRef(ROOT_DESC + 0x18, ROOT_ROWS, "brain", "brain_root_rows",
                           "MAIN MENU root rows: the four stock categories + BRAIN"),),
    pokes=(Poke(ROOT_COUNT_AT, H("00000004"), H("00000005"), "MAIN MENU root count: + BRAIN"),),
    gates=(Gate("tools/verify/verify_brain.py", remix_arg=False, venv=True, stage="image"),),
)
