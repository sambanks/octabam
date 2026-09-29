"""OS SWITCH -- boot an OS image from the card without writing the flash.

A seventh CONTROL row lists the card root's `.OBI` files (raw OS images:
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
CONTROL_ROWS, CONTROL_COUNT = 0x400CC5A8, 6        # docs/firmware/MAINMENU.md section 2


def _include(_modules):
    """osw.inc, and CONTROL's six stock rows taken from the user's own image
    at build time (never a stock byte in the repo)."""
    off = CONTROL_ROWS - 0x40000400
    return ((HERE / "osw.inc").read_text()
            + f"        .set    TRACE, {1 if 'BOOT TRACE' in _modules else 0}\n"
            + "        .macro  CONTROL_ROWS\n"
            + f"        .incbin \"{STOCK}\", 0x{off:x}, {CONTROL_COUNT * 0x18}\n"
            + "        .endm\n")


MODULE = Module(
    name="os-switch",
    key="OS SWITCH",
    kind=Kind.HYBRID,
    category=Category.REFERENCE, author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.HARDWARE,
    proof_note="an MKII, 29 Sep 2026 (OCTABAM14 with BOOT TRACE): switched to its own "
               "image and to stock 1.40C, audio and play working; `verify_osswitch`",
    doc="CONTROL > OS SWITCH boots a raw OS image (.OBI) from the card root "
        "without writing the flash; a power-cycle returns to the flashed image.",
    linked=(
        Linked("osw_chain", "modules/os-switch/chain.s", cpu="5475", include=_include),
        Linked("osw_switch", "modules/os-switch/switch.s", dram=True, include=_include),
    ),
    # Each DSP core, told by host command $12 before the reset, parks in a
    # boot-ROM loader of its own (dsp_park.asm): the soft reset restarts the
    # ColdFire but not the DSP, whose ROM only listens after a chip reset.
    dsp=DspSection(
        asm="modules/os-switch/dsp_park.asm",
        priority=20,
        payloads=frozenset({"A", "B"}),
        hooks=(DspHook(0x24, (0x0C0024, 0x000000), "osw_dsp",
                       "host command $12 (stock's unused reserved24 vector): park in a loader"),),
    ),
    detours=(
        Detour(0x40000412, H("2e7c48000000"), "osw_chain", "osw_chain",
               "the OS entry, after it parks the bootstrap's argument: a staged image first"),
    ),
    symbol_refs=(
        SymbolRef(0x400CBD6C, CONTROL_ROWS, "osw_switch", "osw_rows",
                  "CONTROL's rows: stock's six, then OS SWITCH"),
    ),
    pokes=(
        Poke(0x400CBD54, H("00000006"), H("00000007"), "CONTROL row count 6 -> 7"),
    ),
    gates=(Gate("tools/verify/verify_osswitch.py", venv=True),),
)
