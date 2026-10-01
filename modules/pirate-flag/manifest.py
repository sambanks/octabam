"""PIRATE FLAG -- the OS's own boot animation becomes a waving Jolly Roger.

The MAIN OS plays a 2.8 s animation of its own at every boot (0x400559c6..
0x40055b7a, the LED/key-scan task: a sprite field on DTIM3's clock, then the
UI). One jsr detour at its per-frame flush (0x40055aa2) draws the flag over
each frame, the cloth waving with the frame number, and flushes as stock
did. The art is made from shapes in art.py at build time.

What it cannot change: the bootstrap in NOR draws before any OS runs, so the
first logo and the version line stay the flashed image's (docs/proposals/
FIRMWARE_SWITCHER.md step 4). What follows them is the running image's own
animation, so an OS SWITCH to an image carrying this module shows the flag
on the way in -- DOOM.OBI does -- and a flashed image carrying it shows it
at every power-on.
"""

import pathlib
import sys

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

HERE = pathlib.Path(__file__).resolve().parent
H = bytes.fromhex


def _include(_modules):
    sys.path.insert(0, str(HERE))
    import art
    import math
    cols = art.columns()
    lines = [f"        .set    CLOTH, {art.CLOTH}", "        .macro  FLAG_COLUMNS"]
    for i in range(0, len(cols), 4):
        lines.append("        .long   " + ", ".join(f"0x{a:08x}, 0x{b:08x}" for a, b in cols[i:i + 4]))
    lines += ["        .endm", "        .macro  SIN64"]
    sin = [round(32 * math.sin(2 * math.pi * i / 64)) for i in range(64)]
    for i in range(0, 64, 16):
        lines.append("        .byte   " + ", ".join(str(v & 0xFF) for v in sin[i:i + 16]))
    lines.append("        .endm")
    return "\n".join(lines) + "\n"


MODULE = Module(
    name="pirate-flag",
    key="PIRATE FLAG",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE,
    author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.CHECK,
    proof_note="drawn under the port with --boot-logo (tools/verify/verify_pirateflag.py); never on a unit",
    doc="The OS's boot animation becomes a waving Jolly Roger (the bootstrap's logo before it "
        "is NOR's and stays).",
    linked=(
        Linked("pirate_flag", "modules/pirate-flag/flag.s", dram=True, include=_include),
    ),
    detours=(
        Detour(0x40055AA2, H("4eb940013abc"), "pirate_flag", "pirate_frame",
               "the boot animation's per-frame flush: the flag first", kind="jsr"),
    ),
    gates=(Gate("tools/verify/verify_pirateflag.py", venv=True),),
)
