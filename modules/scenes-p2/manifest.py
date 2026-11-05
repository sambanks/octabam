"""SCENES P2 -- scene locks and the crossfader reach page 2 of FX1 and FX2.

Stock morphs 30 bytes a track a scene: page 1 of the five pages. Page 2 has
no scene byte, and the exclusion is structural (block size, the 32-pair
working copy, the frame builder's loop extents; docs/firmware/MIDI.md
Appendix C). This module keeps its page-2 locks in bytes 30 and 31 of
each track's block in the stock scene block, which the frame builder skips
(eight two-byte cells a scene), and adds one pass to the frame builder, after the stock morph and before
the transfer, that lerps every locked page-2 slot into the voice record
with the stock weight table; a select snaps at the fader's midpoint. A
page-2 knob turned while a scene is held edits that scene's lock instead
of the Part (both page-2 editors detoured at entry). The cells travel with
the scene: Part Save / Reload, Project Save and a KITS Kit copy the Part
whole, and stock scene copy, paste, undo and clear copy each track's 32
bytes.

Sites: the frame builder's join after the morph (0x4000cf40), the FX2
page-2 editor (0x4003a9dc) and FX1's (0x4003abe4), all at instruction
boundaries with the displaced instructions replayed.
"""

from remix.schema import Gate, Category, Proof, Claims, Detour, Kind, Linked, Module
import idspace

H = bytes.fromhex


def next_inc(modules, remix):
    """Where a turn with no scene held continues: the stock prologue replay
    inside the unit. PLOCKS = 1 when PLOCKS P2 is in the remix: the dial
    shows a held step's page-2 lock."""
    plocks = f"        .set    PLOCKS, {1 if 'PLOCKS P2' in modules else 0}\n"
    desc2 = f"        .set    DESC2, {idspace.fx2_ids(remix):#x}\n"
    return (plocks + desc2 + "        .set    P2_NEXT2, fx2_stock\n"
            "        .set    P2_NEXT1, fx1_stock\n")

MODULE = Module(
    name="scenes-p2",
    key="SCENES P2",
    kind=Kind.CF_PATCH,
    category=Category.PARTS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); " "26 Sep 2026",
    doc="Scene locks and the crossfader on FX1/FX2 page 2 "
        "(hold a scene, turn a page-2 knob).",
    linked=(Linked("p2scenes", "modules/scenes-p2/p2scenes.s", dram=True, include=next_inc),),
    detours=(
        Detour(0x4000CF40, H("246f0080d5fc80000660"), "p2scenes", "frame_hook",
               "frame builder, after the stock scene morph: lerp the page-2 locks "
               "into the voice records", kind="jmp", pad_to=10),
        Detour(0x4003A9DC, H("4fefffe448d71c3c"), "p2scenes", "fx2_edit_hook",
               "FX2 page-2 editor entry: a held scene takes the turn as a lock",
               kind="jmp", pad_to=8),
        Detour(0x4003ABE4, H("4fefffe448d71c3c"), "p2scenes", "fx1_edit_hook",
               "FX1 page-2 editor entry: the same for FX1", kind="jmp", pad_to=8),
        Detour(0x40025B40, H("4fefffd048d77cfc2a6f0034"), "p2scenes", "scene_write_hook",
               "scene write (paste, undo): the frame cache is dropped after it",
               kind="jmp", pad_to=12),
        Detour(0x40038C30, H("4fefffd848d73cfc282f002c"), "p2scenes", "scene_clear_hook",
               "scene clear: the frame cache is dropped after it", kind="jmp", pad_to=12),
        Detour(0x40053498, H("4fefffdc48d71cfc"), "p2scenes", "scene_knob_hook",
               "stock's scene-lock knob handler, which a held scene installs over "
               "every encoder: with an FX SETUP window open, a page-2 turn goes to the "
               "edit hooks", kind="jmp", pad_to=8),
        Detour(0x40037840, H("d1fc0008f0841c10"), "p2scenes", "dial2_hook",
               "FX2 page-2 dial: with a scene held, draw that scene's lock", kind="jmp", pad_to=8),
        Detour(0x40037BDC, H("d1fc0008f07e1c10"), "p2scenes", "dial1_hook",
               "FX1 page-2 dial: the same", kind="jmp", pad_to=8),
    ),
    # bytes 30, 31 of every (scene, track) block: Part +0x8f3e2 + 0x100*scene
    # + 0x20*track + 30
    claims=Claims(part_window=tuple((0x8f400 + 0x20 * i, 2, f"page-2 scene cell {i}")
                                    for i in range(128))),
    gates=(Gate('tools/verify/verify_scenes_p2.py'),),
)
