"""SLOW LFO -- MULT 1/2X, 1/4X and 1/8X on the audio and MIDI tracks' LFOs.

Stock routines changed: the LFO engine's rate step and MULT load, in the
audio engine (0x4000cfa8) and its MIDI copy (0x40003c0e); the MULT count of
both LFO pages (7 -> 10); the shared MULT formatter. MULT 0..6 run stock's
code unchanged. 7, 8 and 9 shift the engine's per-pass step right by 1, 2
or 3 and skip stock's left shift, so they run at 1/2, 1/4 and 1/8 of 1X,
still from the project tempo. unit.s has the ground; README.md what was
measured and what ran on a unit.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof

RATE = bytes.fromhex("4c036800" "203c000021d1")   # mulsl %d3,%d6; movel #8657,%d0
MULT = bytes.fromhex("79b22824" "bc83")           # mvzb 0x24(%a2,%d2:l),%d4; cmpl %d3,%d6
COUNT = (7).to_bytes(4, "big")                     # the LFO page's MULT value count

MODULE = Module(
    name="slow-lfo",
    key="SLOW LFO",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES, author="nathangroth", author_url="https://github.com/nathangroth",
    proof=Proof.HARDWARE, proof_note="the author's MKI (author's report, rates by ear): the same unit.s loaded "
        "over USB by Modwerk's loader, 4 Nov 2026, audio and MIDI tracks; this octabam form not flashed; "
        "`verify_slow_lfo` under the port",
    doc="LFO MULT gains 1/2X, 1/4X and 1/8X on audio and MIDI tracks: LFOs up to eight times slower.",
    linked=(Linked("slow_lfo", "modules/slow-lfo/unit.s", dram=True),),
    detours=(
        Detour(0x4000CFB0, RATE, "slow_lfo", "sl_rate_audio",
               "audio LFO engine rate step: MULT 7-9 shift SPD x tempo right by 1-3", kind="jmp", pad_to=10),
        Detour(0x4000CFD6, MULT, "slow_lfo", "sl_mult_audio",
               "audio LFO engine MULT load: 7-9 shift the wrap count by 0", kind="jmp"),
        Detour(0x40003C16, RATE, "slow_lfo", "sl_rate_midi",
               "MIDI LFO engine rate step: as the audio engine's", kind="jmp", pad_to=10),
        Detour(0x40003C3C, MULT, "slow_lfo", "sl_mult_midi",
               "MIDI LFO engine MULT load: as the audio engine's", kind="jmp"),
        # movel %sp@(8),%d1; movel %d1,%d0
        Detour(0x4003BDA4, bytes.fromhex("222f0008" "2001"), "slow_lfo", "sl_format",
               "MULT formatter (both LFO pages): 7-9 print 1/2X, 1/4X, 1/8X", kind="jmp"),
    ),
    pokes=(
        Poke(0x400D38B0, expect=COUNT, write=(10).to_bytes(4, "big"), note="audio LFO page MULT count 7 -> 10"),
        Poke(0x400D421C, expect=COUNT, write=(10).to_bytes(4, "big"), note="MIDI LFO page MULT count 7 -> 10"),
    ),
    gates=(Gate("tools/verify/verify_slow_lfo.py", venv=True, stage="image"),),
)
