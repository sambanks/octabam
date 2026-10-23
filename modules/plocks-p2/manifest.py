"""PLOCKS P2 -- per-step parameter locks for page 2 of FX1 and FX2.

Stock's step record carries 32 lock bytes, page 1 of the five pages, and
every byte of the pattern is used (docs/firmware/STEP_LOCKS.md). This
module keeps page 2 in its own table in the platform runtime (12 bytes a
step, every bank, pattern, track and step: 1,572,864 B of .bss) and runs
it beside stock's lock pipeline: a knob turned on the FX1 or FX2 SETUP
page with trigs held locks page 2 of those steps (stock sends that turn
to the page-1 lock editor, which locks the page-1 slot behind the
window), and each trig carries its step's page-2 locks through the
sequencer's staging and pending records to the frame ISR, which writes
them into the live lane and puts the Part's value back at the next trig.

Requires SCENES P2: its page-2 dial hooks show a held step's lock.
"""

from remix.schema import Category, Claims, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex

MODULE = Module(
    name="plocks-p2",
    key="PLOCKS P2",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); Core P4 on radiohagen's MKII (17 Oct); EDIT EVENTS held-edit/copy paths on radiohagen's MKII, Core PLK858 (22 Oct); scoped operator report; shared EVENTS migration is software-only, not hardware-tested",
    doc="Parameter locks on FX1/FX2 page 2 (hold trigs, turn a knob on the SETUP page).",
    linked=(Linked("p2locks", "modules/plocks-p2/p2locks.s", dram=True),),
    detours=(
        Detour(0x40060B38, H("4eb94004d948"), "p2locks", "plk_page_draw",
               "trig release: refresh the native page and active FX SETUP popup", kind="jsr"),
        Detour(0x40058958, H("4eb94004d948"), "p2locks", "plk_page_draw",
               "trig hold: refresh FX SETUP with the native held-step page redraw", kind="jsr"),
        Detour(0x40037878, H("2f032f132f09"), "p2locks", "plk_widget2",
               "FX2 SETUP widget: native held-lock highlight and persistent value", kind="jmp"),
        Detour(0x40037C14, H("2f032f132f09"), "p2locks", "plk_widget1",
               "FX1 SETUP widget: native held-lock highlight and persistent value", kind="jmp"),
        Detour(0x4009D704, H("2807eb8c206f004e"), "p2locks", "plk_fill_slide",
               "the trig record builder, slide path: the step's page-2 locks beside it",
               kind="jmp", pad_to=8),
        Detour(0x4009D8C6, H("2207eb89206f004e"), "p2locks", "plk_fill_plain",
               "the trig record builder, plain path: the same", kind="jmp", pad_to=8),
        Detour(0x4009B858, H("2040d1fc46c76ac0"), "p2locks", "plk_s2p_a",
               "staging record to pending slot 0", kind="jmp", pad_to=8),
        Detour(0x4009C038, H("2040d1fc46c76ac0"), "p2locks", "plk_s2p_b",
               "staging record to pending slot 0, second site", kind="jmp", pad_to=8),
        Detour(0x4009B220, H("2f0243f980006500"), "p2locks", "plk_reset",
               "pending slots reset", kind="jmp", pad_to=8),
        Detour(0x4000BAFE, H("4cd030de48d230de"), "p2locks", "plk_p2r",
               "frame ISR: pending slot to the trig record", kind="jmp", pad_to=8),
        Detour(0x4000B770, H("4cd130de48d030de"), "p2locks", "plk_note",
               "frame ISR: a MIDI note's trig record (no page-2 locks)", kind="jmp", pad_to=8),
        Detour(0x4000C59E, H("200c44c06b70"), "p2locks", "plk_apply",
               "frame ISR, restore/apply join: page 2 restored and applied in the lane",
               kind="jmp", pad_to=6),
        Detour(0x4006036E, H("e98e260dd686"), "p2locks", "plk_place",
               "placing a trig clears the step's locks: page 2 too", kind="jmp", pad_to=6),
        Detour(0x40040E14, H("4fefffd448d77cfc"), "p2locks", "plk_clrlocks",
               "clear the held steps' locks: page 2 too", kind="jmp", pad_to=8),
        Detour(0x40039DF4, H("4fefffc448d77cfc"), "p2locks", "plk_clrtrack",
               "clear a track (and, per track, a pattern): page 2 too", kind="jmp", pad_to=8),
        Detour(0x4002BF38, H("4fefffc048d77cfc"), "p2locks", "plk_tcopy",
               "trig copy into the clipboard or the undo buffer: page 2 beside it",
               kind="jmp", pad_to=8),
        Detour(0x4002CB52, H("d1fc1001614f"), "p2locks", "plk_tpaste",
               "trig paste: page 2 from the buffer's mirror", kind="jmp", pad_to=6),
    ),
    requires=("SCENES P2", "STORE", "EVENTS"),
    # NV copy of the current bank's page 2 in CS1 (battery SRAM), nv_save in
    # p2locks.s: 0x100f8600..0x100fbdf0, unused by stock beyond its whole-CS1 init.
    claims=Claims(sram=((0x100f8600, 0x100fbdf0 - 0x100f8600, "P2NV bank copy in CS1"),)),
    gates=(Gate('tools/verify/verify_plocks_p2.py'),),
)
