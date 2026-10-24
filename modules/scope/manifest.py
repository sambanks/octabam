"""SCOPE -- full-screen OSC / XY / ALL of track audio.

DOWN + TEMPO opens a 128x64 class-1 window. Owns TEMPO / frame_isr /
UI-loop when TUNER is also selected (Override of TUNER's three detours);
UP + TEMPO still opens Tim's tuner. OSC = mono polyline; XY = L×R
Lissajous. A=GAIN B=TIME; CUE release toggles the G/P HUD.
"""

from remix.schema import Category, Detour, Kind, Linked, Module, Override, Proof

H = bytes.fromhex

TEMPO_OPEN = 0x40059EF0
FRAME_TAIL = 0x4000D99A
UI_LOOP = 0x40056C72

MODULE = Module(
    name="scope",
    key="SCOPE",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES,
    author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    proof=Proof.HARDWARE,
    proof_note="MKII: LSCOPE BJ 24 Oct 2026 (OSC/XY/ALL; owner busy 8-track: CF METER SCOPE open ISR mean 291 µs / closed 288 µs, TUE 0 ROE 0; several min ALL soak no glitch); also make check REMIX=test/scope",
    doc="DOWN+TEMPO OSC/XY/ALL; UP/DOWN switch; A GAIN B TIME; bridges TUNER.",
    requires=("TUNER",),
    overrides=(
        Override(TEMPO_OPEN, "TUNER"),
        Override(FRAME_TAIL, "TUNER"),
        Override(UI_LOOP, "TUNER"),
    ),
    linked=(Linked("scope", "modules/scope/scope.s", cpu="5475", dram=True),),
    detours=(
        Detour(TEMPO_OPEN, H("4ab9460d16a0"), "scope", "sc_tempo",
               "TEMPO: DOWN -> SCOPE, UP -> TUNER, else stock"),
        Detour(FRAME_TAIL, H("23c180004800"), "scope", "sc_frame",
               "frame_isr: fill SCOPE or TUNER ring while that window is open"),
        Detour(UI_LOOP, H("4879460d1664"), "scope", "sc_tick",
               "UI loop: SCOPE ~60 Hz draw, or TUNER analyse+draw ~7 Hz"),
    ),
)
