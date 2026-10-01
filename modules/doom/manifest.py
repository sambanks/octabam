"""DOOM -- id Software's Doom on the Octatrack's panel, booted as an OS image.

doomgeneric (ozkl/doomgeneric, GPL-2.0, a submodule at upstream/) compiled
for the MCF54455 with a freestanding C library and the Octatrack platform
(octa/), linked into octabam's DRAM runtime as one prebuilt object
(Makefile -> doom.o; tools/remix/platform_build.py links a `.o` unit as
is). The remix `doom` carries it with stock's effects and OS SWITCH, so
`make obi REMIX=doom OBI=DOOM` gives a DOOM.OBI that MAIN MENU > OS (or the
boot picker) boots, and a power-cycle -- or Doom's own QUIT, or FUNC +
STOP -- returns to the flashed image.

It takes the boot where OS SWITCH's boot picker does (the project load's
two posts), holds the load, reads /DOOM1.WAD whole into its own 2,728
arena pages, opens a 128 x 64 window and pushes an input layer over every
key. A soft timer on the sys tick posts 35 tics a second to the UI task;
each renders Doom's 320 x 200 frame box-filtered and ordered-dithered into
the window's 1-bit plane. No DOOM1.WAD: the boot carries on to OS SWITCH
as if DOOM were not in the image.

The WAD is the user's, like the stock image: never in the repo, copied to
the card root. The shareware DOOM1.WAD (v1.9, sha1 5b2e249b...) is what it
was built against.

README.md beside this file: controls, the memory map, what is measured.
"""

import os
import pathlib

from remix import arena
from remix.schema import (ArenaReserve, Category, Detour, DspHook, DspSection, Gate, Kind,
                          Linked, Module, Override, Proof)

H = bytes.fromhex
HERE = pathlib.Path(__file__).resolve().parent

PAGES = 2728                 # 2,200 for Doom, then Octakit's 528-page window left unused
USED = 2200

# octa/octa.h carries the ends as constants (C cannot ask the build); they
# are the arena's top reservation when DOOM is the only top reservation in
# the remix, which the doom remix is. Re-derived here so a change to the
# arena's geometry refuses the build instead of moving Doom's heap.
_base = arena.END - PAGES * arena.PAGE
_end = _base + USED * arena.PAGE
_h = (HERE / "octa/octa.h").read_text()
if f"DOOM_RAM_BASE  0x{_base:08x}u" not in _h or f"DOOM_RAM_END   0x{_end:08x}u" not in _h:
    raise SystemExit(f"modules/doom: octa/octa.h's DOOM_RAM_BASE/END must be "
                     f"0x{_base:08x}/0x{_end:08x} (tools/remix/arena.py)")

# DOOM_NOHOOKS=1: a bisect build without the sound path (no state-7 detour,
# no DSP hook); with DOOM_CFLAGS=-DOCTA_NOSOUND the C side is silent too
NOHOOKS = os.environ.get("DOOM_NOHOOKS") == "1"
NOSTATE7 = NOHOOKS or os.environ.get("DOOM_NOSTATE7") == "1"     # the frame transfer alone off
NODSPHOOK = NOHOOKS or os.environ.get("DOOM_NODSPHOOK") == "1"   # the DSP hook alone off

MODULE = Module(
    name="doom",
    key="DOOM",
    kind=Kind.HYBRID,
    category=Category.REFERENCE,
    author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.HARDWARE,
    proof_note="an MKII, 1 Oct 2026 (ffa6ff78): booted through OS SWITCH's picker, the picture "
               "upright, Doom's speed, the music from the card, the turning; verify_doom",
    doc="Doom on the panel with its sound and music, as an OS image of its own: boot DOOM.OBI "
        "through OS SWITCH, quit (or FUNC+STOP) back to the flashed OS. Needs DOOM1.WAD on the card.",
    linked=(
        Linked("doom", "modules/doom/doom.o", dram=True),
    ),
    detours=(
        Detour(0x4002574C, H("4879100f8378"), "doom", "doom_projpost",
               "the named project's (re)load post: DOOM takes the boot, else OS SWITCH's picker"),
        Detour(0x4002573E, H("4eb9400228dc"), "doom", "doom_files",
               "the last-set mount's LOADING FILES post: the same, for a unit whose SRAM "
               "knows the card", kind="jsr"),
    ) + (() if NOSTATE7 else (
        # USB AUDIO IN's site (modules/usb-audio-in-ab): a remix carries one
        Detour(0x40004BC0, H("720113c1fc04801d"), "doom", "doom_state7",
               "frame transfer state 7: Doom's 16 stereo samples to core 0 at $6320",
               pad_to=8),)),
    # Doom's sound into MAIN L/R, right after the mixdown (doom_mix.asm)
    dsp=None if NODSPHOOK else DspSection(
        asm="modules/doom/doom_mix.asm",
        priority=20,
        payloads=frozenset({"A"}),          # core 0 runs the mixdown
        hooks=(DspHook(0x2D5, (0x60F000, 0x000206), "doomsnd",
                       "after the mixdown: Doom's pair added into MAIN L/R"),),
    ),
    overrides=(
        Override(0x4002574C, "OS SWITCH"),
        Override(0x4002573E, "OS SWITCH"),
    ),
    requires=("OS SWITCH",),
    arena=ArenaReserve(PAGES, "top"),
    # SKIPs without DOOM1.WAD ($DOOM_WAD or out/doom/DOOM1.WAD): the WAD is
    # the user's, like the stock image
    gates=(Gate("tools/verify/verify_doom.py", venv=True),),
)
