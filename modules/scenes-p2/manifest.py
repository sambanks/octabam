"""SCENES P2 -- scene locks and the crossfader reach page 2 of FX1 and FX2.

Stock morphs 30 bytes a track a scene: page 1 of the five pages. Page 2 has
no scene byte, and the exclusion is structural (block size, the 32-pair
working copy, the frame builder's loop extents; docs/firmware/MIDI.md
Appendix C). This module keeps its own page-2 locks in a 144-byte pool
inside each Part window (+0x90522, the run midisc's MIDI-track locks use)
and adds one pass to the frame builder, after the stock morph and before
the transfer, that lerps every locked page-2 slot into the voice record
with the stock weight table; a select snaps at the fader's midpoint. A
page-2 knob turned while a scene is held edits that scene's lock instead
of the Part (both page-2 editors detoured at entry). The pool travels with
the Part: Part Save / Reload and Project Save copy the window whole, and
Octakit's Kits keep the Part layout.

Sites: the frame builder's join after the morph (0x4000cf40), the FX2
page-2 editor (0x4003a9dc) and FX1's (0x4003abe4), all at instruction
boundaries with the displaced instructions replayed.
"""

from remix.schema import Claims, Detour, Kind, Linked, Module

H = bytes.fromhex


def next_inc(modules):
    """Where a turn with no scene held continues: the stock prologue replay
    inside the unit, or, when Octakit is in the image, nothing here -- the
    SCENES P2 KITS bridge overrides her writes at the two editor entries and
    the build defines P2_NEXT2 / P2_NEXT1 as her wrappers."""
    if "OCTAKIT" in modules:
        return "| P2_NEXT2 / P2_NEXT1: Octakit's editor wrappers (SCENES P2 KITS)\n"
    return ("        .set    P2_NEXT2, fx2_stock\n"
            "        .set    P2_NEXT1, fx1_stock\n")

MODULE = Module(
    name="scenes-p2",
    key="SCENES P2",
    kind=Kind.CF_PATCH,
    doc="Scene locks and the crossfader on FX1/FX2 page 2 "
        "(hold a scene, turn a page-2 knob).",
    linked=(Linked("p2scenes", "modules/scenes-p2/p2scenes.s", dram=True, include=next_inc),),
    detours=(
        Detour(0x4000CF40, H("246f0080d5fc80000660"), "p2scenes", "frame_hook",
               "frame builder, after the stock scene morph: lerp the page-2 locks "
               "into the voice records", kind="jmp", pad_to=10),
        Detour(0x4003A9DC, H("4fefffe448d71c3c246f0020"), "p2scenes", "fx2_edit_hook",
               "FX2 page-2 editor entry: a held scene takes the turn as a lock",
               kind="jmp", pad_to=12),
        Detour(0x4003ABE4, H("4fefffe448d71c3c246f0020"), "p2scenes", "fx1_edit_hook",
               "FX1 page-2 editor entry: the same for FX1", kind="jmp", pad_to=12),
        Detour(0x400274CC, H("4fefffe848d700fc242f001c"), "p2scenes", "scene_copy_hook",
               "scene copy: snapshot the scene's page-2 locks beside the stock clipboard",
               kind="jmp", pad_to=12),
        Detour(0x40025B40, H("4fefffd048d77cfc2a6f0034"), "p2scenes", "scene_write_hook",
               "scene write (paste, clear, undo): the target scene's page-2 locks follow",
               kind="jmp", pad_to=12),
        Detour(0x400275A0, H("4fefffe848d700fc242f0020"), "p2scenes", "scene_undo_hook",
               "undo snapshot before a paste or clear: the scene's page-2 locks beside it",
               kind="jmp", pad_to=12),
        Detour(0x40038C30, H("4fefffd848d73cfc282f002c"), "p2scenes", "scene_clear_hook",
               "scene clear: the scene's page-2 locks go with its bytes", kind="jmp", pad_to=12),
        Detour(0x40037840, H("d1fc0008f0841c10"), "p2scenes", "dial2_hook",
               "FX2 page-2 dial: with a scene held, draw that scene's lock", kind="jmp", pad_to=8),
        Detour(0x40037BDC, H("d1fc0008f07e1c10"), "p2scenes", "dial1_hook",
               "FX1 page-2 dial: the same", kind="jmp", pad_to=8),
    ),
    claims=Claims(part_window=((0x90522, 144, "page-2 scene lock pool"),)),
)
