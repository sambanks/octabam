"""OS SWITCH -- boot an OS image from the card without writing the flash.

A fifth MAIN MENU category, OS, lists the card root's `.OBI` files (raw OS images:
`make obi`), stages the chosen one at the top of the platform's arena
reserve with a mailbox, and resets the unit the way OS UPGRADE does after
it flashes. On the way back up, a chainloader in the OS entry (a ROM cave,
reached before the DSP upload or any other set-up) finds the mailbox,
checks the stage, copies it over the image the bootstrap just depacked and
calls it as the bootstrap called us. NOR is never written; a power-cycle
boots the flashed image again, and a staged image need not carry this
module (stock 1.40C itself is a valid target).

Two units: `chain.s` (the chainloader, a ROM cave: the DRAM runtime is not
depacked yet when it runs) and `switch.s` (the row, the picker, the load and
the reset, DRAM). `osw.inc` is the layout both share.
docs/proposals/FIRMWARE_SWITCHER.md is the design and what is measured;
README.md beside this file is the procedure.
"""

import pathlib

from remix.schema import (Category, Detour, DspHook, DspSection, Gate, Kind, Linked, Module,
                          Poke, Proof, SymbolRef)

H = bytes.fromhex
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
ROOT_ROWS, ROOT_COUNT = 0x400CC698, 4              # docs/firmware/MAINMENU.md section 2

# The OS category's icon, as stock draws its four (19 x 9, a long per
# column, row r at bit 23 + r: the top row is the low bit, measured from
# PROJECT's folded corner): two arrows, one each way.
ICON = (
    "...................",
    "...................",
    "...........##......",
    "....##########.....",
    "...........##......",
    ".....##............",
    "....##########.....",
    ".....##............",
    "...................",
)


def _icon_longs(rows):
    return [sum(1 << (23 + r) for r, row in enumerate(rows) if row[c] == "#")
            for c in range(19)]


def _include(_modules):
    """osw.inc, the root's four stock rows taken from the user's own image
    at build time (never a stock byte in the repo), and the icon."""
    off = ROOT_ROWS - 0x40000400
    ink = ", ".join(f"0x{v:08x}" for v in _icon_longs(ICON))
    # the image's own name, what MAIN MENU > OS shows it as: make's VERSION
    # (exported by the Makefile, the name make image gives the .bin and the
    # .OBI), else OCTABAM<BUILD>; A-Z 0-9 _ - and 12 characters, as make_obi
    # OSW_TRACE=1: this module's own BOOT TRACE notes (1 and 12 from the
    # chainloader, 13 before a switch's reset, 26/27 from the boot picker)
    # without the BOOT TRACE module, whose ROM-cave detours a full rig has
    # no room for (bottleservice-ret: CC MAP's page-2 cave, 30 Sep 2026)
    import os
    import re
    name = os.environ.get("VERSION") or f"OCTABAM{os.environ.get('BUILD', '')}"
    name = re.sub(r"[^A-Z0-9_-]", "", name.upper())[:12] or "OCTABAM"
    return ((HERE / "osw.inc").read_text()
            + f"        .set    TRACE, {1 if 'BOOT TRACE' in _modules or os.environ.get('OSW_TRACE') == '1' else 0}\n"
            + "        .macro  ROOT_ROWS\n"
            + f"        .incbin \"{STOCK}\", 0x{off:x}, {ROOT_COUNT * 0x18}\n"
            + "        .endm\n"
            + "        .macro  ICON_INK\n"
            + f"        .long   {ink}\n"
            + "        .endm\n"
            + "        .macro  OSW_SELF\n"
            + f"        .asciz  \"{name}\"\n"
            + "        .endm\n"
            + "        .macro  ICON_MASK\n"
            + "        .rept   19\n        .long   0xff800000\n        .endr\n"
            + "        .endm\n")


MODULE = Module(
    name="os-switch",
    key="OS SWITCH",
    kind=Kind.HYBRID,
    category=Category.REFERENCE, author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.HARDWARE,
    proof_note="an MKII, 29 Sep 2026 (OCTABAM14 with BOOT TRACE): switched to its own "
               "image and to stock 1.40C, audio and play working; and with the park "
               "moved into the dead vector run (BSRETVEC) booted, played and switched "
               "away again -- 40 region words down to 18; `verify_osswitch`",
    doc="MAIN MENU > OS lists the card root's raw OS images (.OBI) and boots the one "
        "picked without writing the flash; a power-cycle returns to the flashed image. "
        "At power-on a picker offers them before the project loads (3 s, then NO).",
    linked=(
        Linked("osw_chain", "modules/os-switch/chain.s", loader=True, include=_include),
        Linked("osw_switch", "modules/os-switch/switch.s", dram=True, include=_include),
    ),
    # Each DSP core, told by host command $12 before the reset, parks in a
    # boot-ROM loader of its own (dsp_park.asm): the soft reset restarts the
    # ColdFire but not the DSP, whose ROM only listens after a chip reset.
    dsp=DspSection(
        asm="modules/os-switch/dsp_park.asm",
        priority=20,
        payloads=frozenset({"A", "B"}),
        hooks=(DspHook(0x1E, (0x0C001E, 0x000000), "osw_dsp",
                       "host command $0F (the DMA3 vector, dead in both payloads): "
                       "park in a loader"),),
        # WHOLLY in stock's dead interrupt vectors, so the park costs the
        # effect region NOTHING and a remix that harvests nothing can still
        # carry it. 31 words at P:$20..$3E (the DMA3..ESAI run, entered by
        # the hook above) and 8 at P:$06..$0D (debug, trap, NMI and the two
        # reserved slots) with a one-word bridge between them. $02 (stack
        # error) and $04 (illegal instruction) are deliberately left as
        # stock's freeze-traps: those two fire when something is already
        # wrong, and a frozen core is more diagnosable than one running park
        # words. verify_dspvectors audits every slot on every build.
        pins=(0x20, 0x06),
        pin_split_label="osw_tail",
    ),
    detours=(
        Detour(0x40000412, H("2e7c48000000"), "osw_chain", "osw_chain",
               "the OS entry, after it parks the bootstrap's argument: a staged image first"),
        Detour(0x40064C32, H("2f39400cbf6c"), "osw_switch", "osw_menu",
               "MAIN MENU opening: the OS list rescanned from the card"),
        Detour(0x4002574C, H("4879100f8378"), "osw_switch", "osw_bootpick",
               "the named project's (re)load post: the boot's first offers the card's "
               "images before the project loads"),
        Detour(0x4002573E, H("4eb9400228dc"), "osw_switch", "osw_bootfiles",
               "the last-set mount's LOADING FILES post: held with the load while the "
               "boot picker is up, posted after it in stock's order", kind="jsr"),
    ),
    symbol_refs=(
        SymbolRef(0x400CBDA4, ROOT_ROWS, "osw_switch", "osw_root",
                  "the root's rows: stock's four, then OS"),
    ),
    pokes=(
        Poke(0x400CBD8C, H("00000004"), H("00000005"), "root row count 4 -> 5"),
    ),
    gates=(Gate("tools/verify/verify_osswitch.py", venv=True),
           # The park's 40 words could come out of the DSP's unused
           # interrupt vectors instead of the effect region. That is only
           # safe while nothing arms an interrupt in those runs, and once
           # code lives there the freeze that would announce one is gone --
           # so the audit runs on every build, not in a session nobody
           # repeats.
           Gate("tools/verify/verify_dspvectors.py"),),
)
