"""doom -- an OS image that boots into Doom.

OS SWITCH, DOOM (modules/doom) and PIRATE FLAG; no stock effect, so the
DSP region holds DOOM's sound hook. Built as an .OBI (`make obi REMIX=doom
OBI=DOOM`) and booted from the flashed image's MAIN MENU > OS or its boot
picker: it goes straight into Doom instead of loading the project, and
Doom's QUIT (or FUNC + STOP) resets back to the flashed image. Not meant to
be flashed: it would boot into Doom at every power-on (a power-on with no
DOOM1.WAD on the card boots the OS as usual). PIRATE FLAG replaces the OS's
boot animation, so the way into Doom shows a Jolly Roger.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="doom",
    family="reference", proof=Proof.HARDWARE,
    proof_note="an MKII, 1 Oct 2026 (ffa6ff78): Doom with music, through OS SWITCH",
    doc="Doom on the panel, with sound: an .OBI that the OS SWITCH boots into Doom; QUIT goes home.",
    # no stock effect: their DSP words are the region DOOM's sound hook is
    # placed in, and nothing in a Doom image plays a track
    modules=("DOOM", "PIRATE FLAG"),
    fallback="NONE",
)
