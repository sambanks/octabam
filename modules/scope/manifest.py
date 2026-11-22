"""SCOPE -- standalone full-screen OSC / XY / ALL of track audio.

DOWN + TEMPO opens a 128x64 class-1 window. UP + TEMPO is not handled
here. OSC = mono polyline; XY = L×R Lissajous. A=GAIN B=TIME; CUE release
toggles the G/P HUD.
"""

from remix.schema import Category, Detour, Evidence, Kind, Level, Linked, Module

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
    evidence=(Evidence(Level.BUILD, ref="REMIX=test/scope-alone"),
              Evidence(Level.BUILD, ref="REMIX=test/scope"),
              Evidence(Level.UNIT_MEASURED, image="OCTA S2", date="2026-11-15",
                  note="Flashed image. SCOPE open during 30 loader transitions: zero bad records. The paired "
                       "closed/open comparison had a 340 ms median audio gap in both states and median DSP "
                       "window maxima of 49%/48%.")),
    doc="Full-screen scope of the track's audio (DOWN + TEMPO): waveform, XY or both, with gain and time on A and B.",
    linked=(Linked("scope", "modules/scope/scope.s", cpu="5475", dram=True),),
    detours=(
        Detour(TEMPO_OPEN, H("4ab9460d16a0"), "scope", "sc_tempo",
               "TEMPO: DOWN -> SCOPE, else stock"),
        Detour(FRAME_TAIL, H("23c180004800"), "scope", "sc_frame",
               "frame_isr: fill SCOPE ring while that window is open"),
        Detour(UI_LOOP, H("4879460d1664"), "scope", "sc_tick",
               "UI loop: SCOPE ~60 Hz draw"),
    ),
)
