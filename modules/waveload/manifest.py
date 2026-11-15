"""WAVE LOAD -- a probe: K instances of the fixed-point port of CHOMPI
WAVE's voice engine (4 voices each) rendered inside the frame interrupt,
output discarded, so CF METER's interrupt-duration slots read what a
4-voice wave track would cost on the unit and where the ColdFire runs out.

`load.s` is generated from `load.c` + `engine.c` (generate.py); `wrap.s`
is the entry CF METER's m_isr calls with K = its BURN knob, saving the
EMAC state the engine uses. No detour of its own: CF METER's interrupt hook
calls it (CF METER's remix.inc sets WAVE_LOAD).
"""

from remix.schema import Category, Kind, Linked, Module, Evidence, Level

MODULE = Module(
    name="waveload",
    key="WAVE LOAD",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-03",
        note="image 92, Sam's MKII, 3 Oct 2026: one 4-voice engine 69.2 us of the 362.8 us frame, clean beside "
             "four sample tracks"),),
    doc="Probe: K 4-voice wave engines per frame interrupt (CF METER's BURN), for CF METER's duration readout.",
    requires=("CF METER",),
    linked=(Linked("waveload", "modules/waveload/load.s", dram=True),
            Linked("waveload_wrap", "modules/waveload/wrap.s", dram=True)),
)
