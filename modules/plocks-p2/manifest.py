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
MEMCPY = ("a memcpy site that moves patterns or tracks between the banks, the clipboard "
          "and the undo buffer: page 2 goes along")

MODULE = Module(
    name="plocks-p2",
    key="PLOCKS P2",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="",
    doc="Parameter locks on FX1/FX2 page 2 (hold trigs, turn a knob on the SETUP page).",
    linked=(Linked("p2locks", "modules/plocks-p2/p2locks.s", dram=True),),
    detours=(
        Detour(0x400508E4, H("4fefffb048d77cfc"), "p2locks", "plk_edit",
               "page-1 lock editor entry: on an FX SETUP page the turn locks page 2",
               kind="jmp", pad_to=8),
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
        Detour(0x400267E8, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40026884, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40026ECE, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40026F5E, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40027764, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40027834, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x4002924C, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40029280, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40029316, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40029352, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40029980, H("4eb940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="jsr"),
        Detour(0x40029652, H("49f940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="lea"),
        Detour(0x4002978E, H("49f940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="lea"),
        Detour(0x4002B370, H("45f940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="lea"),
        Detour(0x4002B42E, H("45f940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="lea"),
        Detour(0x4002B4B2, H("49f940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="lea"),
        Detour(0x4002B692, H("49f940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="lea"),
        Detour(0x4002B9DA, H("45f940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="lea"),
        Detour(0x4003DE14, H("47f940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="lea"),
        Detour(0x4003E036, H("47f940020898"), "p2locks", "plk_memcpy",
               MEMCPY, kind="lea"),
    ),
    requires=("SCENES P2", "STORE"),
    # NV copy of the current bank's page 2 in CS1 (battery SRAM), nv_save in
    # p2locks.s: 0x100f8600..0x100fbdf0, unused by stock beyond its whole-CS1 init.
    claims=Claims(sram=((0x100f8600, 0x100fbdf0 - 0x100f8600, "P2NV bank copy in CS1"),)),
    gates=(Gate('tools/verify/verify_plocksp2.py'),),
)
