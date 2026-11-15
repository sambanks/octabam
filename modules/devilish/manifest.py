"""dEVILish -- Robin Whittle's Devil Fish mods to the TB-303, as an FX for OCTA303 tracks.

Put dEVILish on the FX1 or FX2 of an OCTA-303 track (or a FLEX track playing a TB303* sample): OCTA303's
voice reads this slot's twelve knobs from the live lane and applies them INSIDE the 303 -- in
the oscillator's level into the filter, the filter's frequency, its feedback, the envelopes and
the slide, where the mods live and where an effect after the voice cannot reach. Take dEVILish
off and the track is the 303 of v6.1.1, sample for sample. Its DSP part is a pass-through
(init and proc return at once: an in-place insert that touches no frame).

After Whittle, "User Manual for the Devil Fish mods to the TB-303" (2019); the knob laws are
tools/octa303/o3tables.py (DF_*), the voice is modules/octa303/octa303.s.

Page 1, the knobs (lock-, scene- and LFO-able): OVDR FM TRCK VDEC SLID ADEC.
Page 2: SATK, then the switches SWP SPD MUFF CUTX ENVX (selects, as on the Devil Fish).
Every default is the TB-303 ("Limiting the Devil Fish to TB-303 sounds", p. 8).
"""

from remix.schema import (BusRole, Category, DspSection, Formatter, Harness, Kind, MenuEntry,
                          Module, Param, Evidence, Level, YBase)

# The FX id. OCTA303's unit compares the track's FX1/FX2 id bytes with it (DEVIL_ID in
# modules/octa303/manifest.py, through remix.inc); test_octa303 checks the two agree.
# PHASER's id, replaced: every non-stock id is a module's (0x1e, dEVILish's until 21 Oct 2026, is
# RESONATOR's), and a remix with dEVILish gives up PHASER on both menus (acidtrack lists neither).
FX_ID = 0x10

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="devilish",
    key="DEVILISH",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK,
    author="MaMarko", author_url="https://github.com/braikomarko-hub",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="MaMarko", date="2026-10-22",
        note="image DEVPR2 (BUILD 93, remix devilish, on 0x10), 22 Oct 2026: every knob of both pages, FX1 and "
             "FX2, an LFO on a knob moving the 303, a scene and a lock, a non-303 track passing, two 303 tracks "
             "for five minutes, save and reload. Before, in daily use in the acidtrack images up to ACIDV71 (on "
             "0x1f / 0x1e). The Devil Fish engine is bit-exact in OCTA303's source simulator"),),
    doc="The Devil Fish mods (Robin Whittle) for an OCTA303 track: twelve knobs read by the 303 "
        "voice; the DSP passes the audio through.",
    menu=MenuEntry(
        fx2_id=FX_ID,
        replaces="PHASER",
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots (CHARACTER's donor, on hardware)
        abbr=b"dEVL",
        fullname=b"dEVILish",
        build_tag=False,
    ),
    params=(
        # ---- page 1: the knobs ------------------------------------------------
        Param(b"OVDR", 25, 128, active=True, formatter=_PLAIN,
              doc="overdrive into the filter: 0 none, 25 the 303, 127 is 66.6x (resonance swamped)"),
        Param(b"FM", 0, 128, active=True, formatter=_PLAIN,
              doc="filter FM from the amp output (after the Muffler); 0 off, high heads towards chaos"),
        Param(b"TRCK", 0, 128, active=True, formatter=_PLAIN,
              doc="filter tracking, linear in Hz up to ~2.7 kHz/octave; low notes can shut the filter"),
        Param(b"VDEC", 64, 128, active=True, formatter=_PLAIN,
              doc="volume: 0-64 sets decay, 16 ms to the 303's; 64-127 sets the final level, 127 endless"),
        Param(b"SLID", 0, 128, active=True, formatter=_PLAIN,
              doc="slide time, 60 ms (0, the 303) to 360 ms"),
        Param(b"ADEC", 50, 128, active=True, formatter=_PLAIN,
              doc="filter decay on accented notes, 30 ms to 3 s; 50 is the 303's fixed ~200 ms"),
        # ---- page 2 ------------------------------------------------------------
        Param(b"SATK", 0, 128, active=True, formatter=_PLAIN,
              doc="soft attack on the volume of unaccented notes: 0 none, 1 to 127 is 0.3 to 30 ms"),
        Param(b"SWP", 0, 3, active=True, formatter=_STEP, labels=("ACID", "WHST", "SELF"),
              doc="accent sweep: ACID is the 303; WHST doubles resonance; SELF too, with no sweep"),
        Param(b"SPD", 1, 3, active=True, formatter=_STEP, labels=("FAST", "NORM", "SLOW"),
              doc="accent sweep speed: FAST first accent strongest, NORM the 303, SLOW up to twice"),
        Param(b"MUFF", 0, 3, active=True, formatter=_STEP, labels=("OFF", "SOFT", "HARD"),
              doc="Muffler after the amp: clips the loud peaks, keeps the bass"),
        Param(b"CUTX", 0, 2, active=True, formatter=_STEP, labels=("OFF", "ON"),
              doc="the wide cutoff pot: lower, and up to about 5 kHz"),
        Param(b"ENVX", 0, 2, active=True, formatter=_STEP, labels=("OFF", "ON"),
              doc="envelope modulation tripled, from none"),
    ),
    dsp=DspSection(
        asm="modules/devilish/devilish.asm",
        priority=22,                  # 20 is REMIX SWITCH's (both payloads)
        bus_role=BusRole.NONE,        # an insert; never on the bus
        ybase=YBase.NEVER,            # no buffers
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char=None, is_server=False),
    requires=("OCTA303",),            # without the voice there is nothing to read the knobs
    dear={"OVDR": 127, "FM": 127, "TRCK": 127, "VDEC": 127, "SLID": 127, "ADEC": 127,
          "SATK": 127, "SWP": 1, "SPD": 2, "MUFF": 1, "CUTX": 1, "ENVX": 1},
)
