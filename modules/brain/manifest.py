"""BRAIN -- the brain's run-time layers on the unit (docs/proposals/BRAIN.md).

This increment: card-layer FX page defaults, read-only. At each LOAD PROJECT
and at the power-up's bank load the brain reads /BRAIN/card.work (card.strd
by the pair rule) and writes each valid default record over its effect's
descriptor defaults; the choosers and the new-part initialiser read them
from there. Written by tools/hw/ot_brain.py on a computer; the unit's own
SAVE FX DEFAULT, the SETTINGS list, the project pair and the CS1 block are
the next increments. README.md.
"""
import os
import pathlib
import struct
import sys

from remix import schema
import idspace
from remix.schema import (Binary, Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, Scope, Setting,
                          Store, SymbolRef)

H = bytes.fromhex
SOURCE = "modules/brain/brain.s"


def fx_inc(modules, remix):
    """The `remix.inc` brain.s includes: brain_fx[], one 40-byte entry per
    selected effect with knobs (brain.fx_targets): layout hash, store id
    pointer, twelve keys, fx id, id length, name (the module's key)."""
    sys.path.insert(0, str(pathlib.Path(schema.__file__).resolve().parents[1]))
    from remix import brain
    mods = modules if isinstance(modules, dict) else {}
    targets = [m for m in mods.values() if m.menu is not None and len(m.params) == 12]
    out = ["| remix.inc -- brain_fx: the effects in this image (modules/brain/manifest.py)",
           f"        .set    brain_fx2_ids, {idspace.fx2_ids(remix):#x}",
           "        .section .rodata", "        .balign 4", "        .globl  brain_fx, brain_fx_n",
           f"brain_fx_n: .long {len(targets)}", "brain_fx:"]
    for i, m in enumerate(targets):
        keys = ", ".join(str(k) for k in brain.fx_keys(m))
        out += [f"        .long   0x{brain.fx_layout(m):08x}, brain_id_{i}",
                f"        .word   {keys}",
                f"        .byte   0x{m.menu.fx2_id:02x}, {len(brain.fx_store_id(m))}",
                f"        .word   0",
                f"        .long   brain_nm_{i}"]
    for i, m in enumerate(targets):
        out.append(f'brain_id_{i}: .ascii "{brain.fx_store_id(m)}"')
        out.append(f'brain_nm_{i}: .asciz "{m.key[:PANE_W - 2]}"')
    return ("\n".join(out) + "\n" + image_inc(mods) + "\n" + menu_inc() + "\n" + settings_inc(mods, remix)
            + "\n" + page_keys_inc() + "\n" + func_keys_inc()
            + "\n        .text\n")


PAGE_LAYER_KEYS, PAGE_KEYS, PAGE_RECORDS, KEY_RECORD = 0x400bab72, 0x400baad2, 5, 0x1a


def page_keys_inc():
    """The page-held key layer's table (docs/firmware/PANEL.md: a page key's
    record names layer 0x400bab6e, whose keys are 0x400baad2 on both models:
    REC, STOP, PLAY, YES, NO), copied from the user's stock image at build
    time, with BRAIN's record for FUNC (0x2d) after them: hold a page key and
    press FUNC for the page shortcut (brain.c brain_page_func). Records are
    0x1a bytes {code, 0, then six longs: press, release, repeat, sub-map,
    +0x12, +0x16}; the table ends at a code 0xff. A record written two bytes
    short put the 0xff off the stride, and stock's reader ran on into the
    .data after the table (brain_ts) and filled the key cache from it: FUNC
    then called a TCB address (13 Oct 2026, under the port)."""
    stock = pathlib.Path(schema.__file__).resolve().parents[2] / "out/raw/section_3_MAIN_OS.bin"
    return "\n".join([
        "        .data", "        .balign 2", "        .globl  brain_page_keys", "brain_page_keys:",
        f'        .incbin "{stock}", 0x{PAGE_KEYS - 0x40000400:x}, {PAGE_RECORDS * KEY_RECORD}',
        "        .byte   0x2d, 0",
        "        .long   brain_page_func, 0, 0, 0, 0, 0",
        "        .byte   0xff, 0", "        .long   0, 0, 0, 0, 0, 0"])


FUNC_LAYER_KEYS, FUNC_KEYS = 0x400bfa36, 0x400bf628   # the MKII FUNC layer (0x400bfa32) and its keys


def func_keys_inc():
    """The MKII FUNC layer's keys, copied from the user's stock image at
    build time (docs/firmware/PANEL.md; the records up to the 0xff end,
    counted here), with BRAIN's record for the LEVEL encoder's push (0x3e)
    after them: FUNC + LEVEL push opens TOOLS > LOAD (brain.c
    brain_load_chord). Stock's FUNC layer has no record for 0x3e, and the
    push handler 0x4004ecfc ignores FUNC (docs/proposals/BRAIN.md section
    9). The MKI's encoders do not push and its FUNC layer is left alone."""
    stock = pathlib.Path(schema.__file__).resolve().parents[2] / "out/raw/section_3_MAIN_OS.bin"
    img = stock.read_bytes()
    n = 0
    while img[FUNC_KEYS - 0x40000400 + n * KEY_RECORD] != 0xff:
        n += 1
    return "\n".join([
        "        .data", "        .balign 2", "        .globl  brain_func_keys", "brain_func_keys:",
        f'        .incbin "{stock}", 0x{FUNC_KEYS - 0x40000400:x}, {n * KEY_RECORD}',
        "        .byte   0x3e, 0",
        "        .long   brain_load_chord, 0, 0, 0, 0, 0",
        "        .byte   0xff, 0", "        .long   0, 0, 0, 0, 0, 0"])


def image_inc(mods):
    """ABOUT's table: the image's own name (remix.brain.image_name)
    and one row per module, its key and its author (the first of
    "a/b"), alphabetical; brain_img_name, brain_img_n, brain_img[] of
    {key, author} string pointers."""
    from remix import brain
    rows = sorted((m.key, (m.author or "").split("/")[0].strip()) for m in (mods if isinstance(mods, dict) else {}).values())
    out = ["        .section .rodata", "        .balign 4",
           "        .globl  brain_img_name, brain_img_n, brain_img, brain_img_remix, brain_img_os",
           f'brain_img_name: .asciz "{brain.image_name()}"',
           f'brain_img_remix: .asciz "{brain.remix_label()}"',
           'brain_img_os: .asciz "1.40C"',
           "        .balign 4", f"brain_img_n: .long {len(rows)}", "brain_img:"]
    for i in range(len(rows)):
        out.append(f"        .long   brain_img_k{i}, brain_img_a{i}")
    for i, (k, au) in enumerate(rows):
        out.append(f'brain_img_k{i}: .asciz "{k[:22]}"')
        out.append(f'brain_img_a{i}: .asciz "{au[:14]}"')
    out.append("        .balign 4")
    return "\n".join(out)


PANE_W = 15                              # characters BRAIN's list pane shows (brain.c PANE_W)


def settings_inc(mods, remix=None):
    """brain_set[] and brain_values[]: one entry per setting the unit holds
    at run time (remix.brain.live_table), in the SETTINGS list's order.
    An entry is 44 bytes (brain.c struct set_ent): store id, id length,
    type (1 Binary, 2 Option, 3 Number), apply (0 live, 1 callback, 2 next
    boot), label count, key, min, max, the default after layers 1 and 2,
    the setting's value address in CS1 when it is early (0 otherwise,
    remix.brain.early_layout), the labels, the name, the module's key (the
    list's heading), the scope (0 CARD: card.work; 1 PROJECT: the project's
    brain.work). Each value is a long with its own global
    (remix.brain.value_symbol), which a module's read macro loads."""
    from remix import brain
    from remix.schema import Apply, Binary, Number, Option
    rows = brain.live_table(remix, mods) if remix is not None else []
    applies = {Apply.LIVE: 0, Apply.CALLBACK: 1, Apply.NEXT_BOOT: 2}
    cs1 = brain.early_layout(remix, mods)[1] if remix is not None else {}
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
                f"        .long   {cs1.get((r.store_id, r.key), 0)}",
                f"        .long   {f'brain_slab_{i}' if nl else 0}, brain_snam_{i}, brain_sgrp_{groups[m.key]}, "
                f"{1 if s.scope is Scope.PROJECT else 0}"]
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
STATE_TABLE = 0x400cbdac               # 16 entries x {enter, exit, draw, key, encoder}
SCREENS = 7                            # BRAIN's states 16..22 (brain.c SC_N)
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
            "brain_list: .long 7, 0, 0, 0, 7, 7, brain_top_rows",
            "        .globl  brain_top_rows, brain_def_rows, brain_tool_rows, brain_rmx_rows, brain_rmx_n, brain_set_rows",
           "        .globl  brain_tpl_rows",
            # the root rows, the most used first, no arrows; each opens one of
            # BRAIN's screens (menu states, brain.c)
            "brain_top_rows:",
            "        .long   brain_lbl_templates, 0, brain_open_templates, 0, 0, 0",
            "        .long   brain_lbl_remixes, 0, brain_open_remixes, 0, 0, 0",
            "        .long   brain_lbl_settings, 0, brain_open_settings, 0, 0, 0",
            "        .long   brain_lbl_perf, 0, brain_open_perf, 0, 0, 0",
            "        .long   brain_lbl_log, 0, brain_open_log, 0, 0, 0",
            "        .long   brain_lbl_about, 0, brain_open_about, 0, 0, 0",
            # REMIXES: REMIX SWITCH's rows (modules/remix-switch/switch.s):
            # up to NMAX (32) images and four text rows
            "        .globl  brain_rmx_rows, brain_rmx_n",
            "brain_rmx_rows:",
            "        .space  36 * 0x18",
            "brain_rmx_n: .long 0",
            # the menu-state table (stock: 16 entries of {enter, exit, draw,
            # key, encoder}, 0x400cbdac) copied with BRAIN's screens appended
            # as states 16..; the six references to it repointed (SymbolRefs)
            "        .globl  brain_stab, brain_stab_draw, brain_stab_key, brain_stab_enc",
            ]
    stab = struct.unpack(">80I", img[STATE_TABLE - 0x40000400:STATE_TABLE - 0x40000400 + 16 * 20])
    out.append("brain_stab:")
    for i in range(16):
        out.append("        .long   " + ", ".join(f"0x{w:08x}" for w in stab[i * 5:i * 5 + 5]))
    for _ in range(SCREENS):
        out.append("        .long   brain_scr_enter, brain_scr_exit, brain_scr_draw, brain_scr_key, brain_scr_enc")
    out += ["        .set    brain_stab_draw, brain_stab + 8", "        .set    brain_stab_key, brain_stab + 12",
            "        .set    brain_stab_enc, brain_stab + 16",
            "        .globl  brain_icon",
            'brain_lbl_root: .asciz "BRAIN"',
            'brain_lbl_about: .asciz "ABOUT"',
            'brain_lbl_log: .asciz "LOG"',
            'brain_lbl_perf: .asciz "PERFORMANCE"',
            'brain_lbl_remixes: .asciz "REMIXES"',
            'brain_lbl_settings: .asciz "SETTINGS"',
            'brain_lbl_templates: .asciz "TEMPLATES"']
    return "\n".join(out)


# BRAIN_DIAG=noload (a diagnostic build): the two load-path hooks are left
# out, so nothing of BRAIN runs at boot or at a project load; the menu, the
# engine job switch and the store copy stay.
_NOLOAD = os.environ.get("BRAIN_DIAG") == "noload"

MODULE = Module(
    name="brain", key=schema.BRAIN_KEY, kind=Kind.CF_PATCH,
    category=Category.SETTINGS, author="Sam Banks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); " "`verify_brain` under the port (6 Oct 2026)",
    doc="The settings store on the unit: card-wide knob defaults read from BRAIN/card.work at each project load (docs/proposals/BRAIN.md).",
    # MODEDEF_TABLE: MODE DEFAULTS' view table, 0 without that module.
    # BRAIN's own settings (SETTINGS > BRAIN), read by brain.c
    store=Store("octabam.brain"),
    settings=(Setting(1, "MIDI LOG", Binary(), default=0,
                      doc="the debug log records MIDI messages (TOOLS > WRITE DEBUG LOG); off, the MIDI thread's handler call returns at once after the handler"),
              Setting(3, "EVENT LOG", Binary(), default=1,
                      doc="LOG > EVENTS records the audio drops, frame overruns, full processors and slow card commands; off, none are noted"),
              Setting(2, "APPLY DFLTS", Binary(), default=1,
                      doc="the card's knob defaults (BRAIN/card.work) apply at each project load; off, every effect takes the image's defaults")),
    linked=(Linked("brain", SOURCE, cpu="5475", dram=True, include=fx_inc,
                   defsyms=(("MODEDEF_TABLE", 0), ("LM_STATS", 0), ("LM_DSP", 0), ("LM_OT", 0), ("ARENA_BASE", 0x40A955E0),
                           ("CS1_EARLY_BASE", 0x100F859C),  # build override: remix.brain.early_layout
                           # other modules' counters, 0 without them (hooks.s brain_usb*)
                           ("usbaudio_underruns", 0), ("usbaudio_overruns", 0), ("in_counters", 0),
                           ("usbmidi_tx_drops", 0))),),
    detours=tuple(d for d in (
        Detour(0x40085342, H("721b2d41fdc6"), "brain", "brain_on_load",
               "LOAD PROJECT, before the empty-project init: the card's defaults onto the descriptors", kind="jsr"),
        Detour(0x40084d4a, H("73b980000002"), "brain", "brain_on_bankload",
               "the bank load the power-up runs: the card's defaults onto the descriptors", kind="jsr"),
        Detour(0x40005572, H("20720c004e90"), "brain", "brain_on_midi",
               "the MIDI thread's handler call: the debug log records each message and what it left", kind="jsr"),
        Detour(0x4008485e, H("7192722db280"), "brain", "brain_on_job",
               "the engine task's job switch: type 0x41 runs SAVE FX DEFAULT"),
        Detour(0x40085176, H("4eb940096f24"), "brain", "brain_on_newproj",
               "CREATE EMPTY PROJECT, after the empty project's RAM (0x400909d8): the card's project settings",
               kind="jsr"),
        Detour(0x4004e474, H("2f2effc86006"), "brain", "brain_klabel_hook",
               "the CTRL pages' label push: a MIDI track's knob names (NAME KNOB)"),
        Detour(0x40000554, H("23c880006900"), "brain", "brain_sched",
               "the scheduler's entry (trap #0 and PIT0), after its `movew #0x2700,%sr`: the time since the last entry is charged to the task that was running (CPU)"),
        Detour(0x40005a38, H("2f4a005c4cd77cfc"), "brain", "brain_partinit",
               "the end of the Part initialiser (Part Clear, a new project, KITS' default Part): the card's PART default"),
        Detour(0x4001513c, H("7004c0b9" "46c86576"), "brain", "brain_ata_in",
               "the ATA dispatcher, a command just dequeued: its opcode, sector count and start stamp", kind="jsr", pad_to=8),
        Detour(0x40015284, H("72ffb2806606"), "brain", "brain_ata_out",
               "the ATA dispatcher's common exit: the command counted and timed (IO)"),
        *(Detour(site, H("4eb94008ee74"), "brain", "brain_on_store",
                 "SAVE PROJECT's project store: card.work copied to card.strd", kind="jsr")
          for site in (0x40085642, 0x400856dc, 0x40085780)),
    ) if not (_NOLOAD and d.site in (0x40085342, 0x40084d4a))),
    # the BRAIN root category: the root list's rows pointer to brain_root_rows
    # and its count 4 -> 5 (two modules growing the root are refused by the ledger)
    symbol_refs=(
                 # the menu-state table moved to DRAM with BRAIN's screens appended
                 # (the six references, as modules/busscreen did: three `lea`
                 # of the table and `addal` of the draw, key and encoder members)
                 SymbolRef(0x40064bd4, STATE_TABLE, "brain", "brain_stab", "menu state table: enter member (opener)"),
                 SymbolRef(0x40064e36, STATE_TABLE, "brain", "brain_stab", "menu state table: enter member (id path)"),
                 SymbolRef(0x400650e8, STATE_TABLE, "brain", "brain_stab", "menu state table: exit member (NO)"),
                 SymbolRef(0x40064e04, STATE_TABLE + 8, "brain", "brain_stab_draw", "menu state table: draw member"),
                 SymbolRef(0x4006511c, STATE_TABLE + 12, "brain", "brain_stab_key", "menu state table: key member"),
                 SymbolRef(0x40065086, STATE_TABLE + 16, "brain", "brain_stab_enc", "menu state table: encoder member"),
                 SymbolRef(FUNC_LAYER_KEYS, FUNC_KEYS, "brain", "brain_func_keys",
                           "the MKII FUNC layer's keys: stock's records + LEVEL push, the LOAD view"),
                 SymbolRef(PAGE_LAYER_KEYS, PAGE_KEYS, "brain", "brain_page_keys",
                           "the page-held key layer's keys: stock's five records + FUNC, the page shortcut"),
                 SymbolRef(ROOT_DESC + 0x18, ROOT_ROWS, "brain", "brain_root_rows",
                           "MAIN MENU root rows: the four stock categories + BRAIN"),),
    pokes=(Poke(ROOT_COUNT_AT, H("00000004"), H("00000005"), "MAIN MENU root count: + BRAIN"),),
    # This gate builds its own octabam-bus image. Run it before the selected
    # image is restored, never between gates that inspect that image.
    gates=(Gate("tools/verify/verify_brain.py", remix_arg=False, venv=True),),
)
