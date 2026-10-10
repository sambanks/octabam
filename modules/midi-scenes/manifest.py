"""MIDI SCENES -- scene locks for the MIDI tracks, after bkkbrls-del's midisc.

Stock 1.40C keeps scene locks for the audio tracks only. This module adds a
second table (MSC, `scene<<8 | track<<5 | flat`, 4096 bytes, 0xff = no lock)
and routes the scene hold, the encoder press, the lock LEDs, the crossfader
and the scene clear / copy / paste rows to it when a MIDI track is
displayed.

Phase 1 of the rewrite (modules/midi-scenes/README.md): hold-to-lock, the
readout, encoder unlock, lock LEDs and pad indicator, the XF morph, scene
apply, the scene rows. The table, the clipboard and the mix state live in
the unit's DRAM and nothing is written to a Part, a bank file or CS1.

The behaviour is bkkbrls-del's MIDISC2.1 (original author); `scenes.s` is
written fresh and checked against his image under the port
(`tools/verify/verify_scenes.py`). His repository is no longer a submodule here.
"""

from remix.schema import Category, Claims, Detour, Gate, Kind, Linked, Module, Poke, Proof

H = bytes.fromhex

DETOURS = (
    Detour(0x400534CE, H("4ab98000001266000586"), "scenes", "scn_hold_a",
           "scene A held + encoder, MIDI mode: the lock goes to MSC", pad_to=10),
    Detour(0x40052ECE, H("4ab980000012660005b6"), "scenes", "scn_hold_b",
           "scene B held + encoder, MIDI mode: the lock goes to MSC", pad_to=10),
    Detour(0x4004E348, H("71b9100b14cc"), "scenes", "scn_dial",
           "knob readout: the held scene's lock"),
    Detour(0x40053A9E, H("4ab980000012660008aa"), "scenes", "scn_enc_a",
           "scene held + encoder press, MIDI mode: the lock cleared", pad_to=10),
    Detour(0x40054392, H("4ab980000012660008b8"), "scenes", "scn_enc_b",
           "scene held + encoder press, MIDI mode (second function)", pad_to=10),
    Detour(0x400343BC, H("4ab980000012"), note="per-track lock offset: always the audio path", target=0x400343C4),
    Detour(0x4003445E, H("4ab980000012"), note="per-page lock offset: always the audio path", target=0x40034466),
    Detour(0x400343E8, H("06800008f3e2"), "scenes", "scn_taddi",
           "scene-block base per track: MSC in MIDI mode", kind="jsr"),
    Detour(0x4003448E, H("06810008f3e2"), "scenes", "scn_paddi",
           "scene-block base per page: MSC in MIDI mode", kind="jsr"),
    Detour(0x40034764, H("06800008f3e2"), "scenes", "scn_taddi",
           "lock LED paint, first scan: MSC in MIDI mode", kind="jsr"),
    Detour(0x40034950, H("06800008f3e2"), "scenes", "scn_taddi",
           "lock LED paint, second scan: MSC in MIDI mode", kind="jsr"),
    Detour(0x40031F44, H("4fefffe448d704fc"), "scenes", "scn_pad",
           "scene pad lit when MSC holds a lock for the scene", pad_to=8),
    Detour(0x400434CA, H("4ebae414241f"), "scenes", "scn_press",
           "scene key pressed, MIDI mode: the knob overlay redrawn"),
    Detour(0x40052A10, H("4ef94007e8d8"), "scenes", "scn_done",
           "scene recall completion (second path): mix at the XF"),
    Detour(0x40052AE0, H("4ef94007e8d8"), "scenes", "scn_done",
           "scene recall completion (first path): mix at the XF"),
    Detour(0x4003F3A2, H("4ef94003577c"), "scenes", "scn_morph",
           "tail of the audio morph: mix when the XF moved"),
    Detour(0x40061E78, H("71398000004a"), "scenes", "scn_xf1",
           "after the panel XF handler's CC 48 out: mix"),
    Detour(0x40062C32, H("71b980000003"), "scenes", "scn_xf2",
           "after the second XF publish: mix"),
    Detour(0x40062F24, H("4eb940038c30"), "scenes", "scn_clear",
           "CLEAR SCENE row: MSC[scene] wiped", kind="jsr"),
    Detour(0x40062FBE, H("4eb9400274cc"), "scenes", "scn_copy",
           "COPY SCENE row: MSC[scene] to the clipboard", kind="jsr"),
    Detour(0x40062E3C, H("4eb940027578"), "scenes", "scn_paste",
           "PASTE SCENE row: the clipboard to MSC[scene]", kind="jsr"),
)

POKES = (
    Poke(0x40034754, H("665a"), H("4e71"), "lock LEDs scan MSC too, first scan (bne -> nop)"),
    Poke(0x4003493E, H("6648"), H("4e71"), "lock LEDs scan MSC too, second scan (bne -> nop)"),
)

MODULE = Module(
    name="midi-scenes",
    key="MIDI SCENES",
    kind=Kind.CF_PATCH,
    category=Category.PARTS, author="bkkbrls-del/midisc", author_url="https://github.com/bkkbrls-del/midisc",
    proof=Proof.PORT,
    proof_note="`verify_scenes` against MIDISC2.1 under the port, phase 1 scenarios (b1, b7, b3, b29copy, b29clear); the earlier 2.0 build ran on his unit as `ok-ms`, 14 Sep 2026",
    doc="Scene locks for the MIDI tracks (hold-to-lock, readout, unlock, lock LEDs, XF morph, "
        "scene clear / copy / paste), kept per Part in scenes.work and CS1. After bkkbrls-del's midisc.",
    linked=(Linked("scenes", "modules/midi-scenes/scenes.s", dram=True),),
    detours=DETOURS,
    pokes=POKES,
    requires=("STORE",),
    # CS1 (battery SRAM): the current bank's four lock tables, as stock keeps
    # its Part copy there (docs/firmware/MIDI_SCENES.md section 8).
    claims=Claims(sram=((0x100FBDF0, 0x100FFE00 - 0x100FBDF0, "MIDI SCENES: the current bank's lock tables"),)),
    gates=(Gate("tools/verify/verify_scenes.py", once=True),),
)
