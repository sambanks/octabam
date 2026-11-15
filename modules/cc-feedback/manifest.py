"""CC FEEDBACK -- the OT transmits a CC for every live knob byte that changes,
whatever changed it, so a controller's encoders follow the unit.

Stock transmits a page-1 knob's CC on a panel turn only (0x400552f0). A
pattern or part change, a project load, MODE DEFAULTS, an incoming CC and
every page-2 knob leave a controller showing stale values. This unit runs
once per UI tick (a jmp detour on the keyrepeat task's loop, 0x4005595c,
120 Hz) and compares one track's live knob lane (0x80000810 + track*72)
with the stock emitter's own last-sent cache (0x46c7bf2c + channel*128 +
cc), queueing every byte that differs through the emitter 0x40033e3c: page
1 as CC 16-45, FX1 page 2 as CC 108-111, 14, 15 and FX2 page 2 as CC
102-107 (CC MAP's numbering; 68-73 and 62-67 until 1 Nov 2026, issue #981). Gated where stock gates: AUDIO CC OUT bit 1 (EXT), the track's
trig channel, no MIDI track on that channel. See cc_feedback.s."""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Evidence, Level

MODULE = Module(
    name="cc-feedback",
    key="CC FEEDBACK",
    kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026; page 2 on CC 62-73 then); "
             "`verify_ccfeedback` (Unicorn) and `verify_set` (the port's MIDI OUT bytes)"),),
    doc="Every knob value change is transmitted as its CC (page 1: 16-45; page 2: CC MAP's 102-111, 14, 15), "
        "so a controller's encoders follow the unit.",
    linked=(Linked("cc_feedback", "modules/cc-feedback/cc_feedback.s", dram=True),),
    detours=(
        Detour(0x4005595c, bytes.fromhex("487946c7e0e2"), "cc_feedback", "cf_tick",
               "the keyrepeat task's loop: one track's lane compared and queued per UI tick"),
    ),
    gates=(Gate("tools/verify/verify_ccfeedback.py", remix_arg=False, venv=True),),
)
