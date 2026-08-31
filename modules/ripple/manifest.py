"""Ripple -- a Mutable-Instruments-Ripples-flavoured resonant filter.

A per-track INSERT (no bus role, both payloads, any track): a Chamberlin
state-variable filter with a drive stage in front, LP/BP/HP select, and the
resonance allowed to sing. The drive clip and the in-loop limiter on the HP
node are the character, the way Ripples' OTA clip is -- this is a filter to
push, not a surgical EQ.

Cutoff spans ~24 Hz..7.2 kHz on a squared taper (the SVF's stable region at
44.1 kHz -- f = 2sin(pi*fc/fs) capped below 1.0). RES=127 reaches Q ~ 30:
a screaming peak, deliberately short of self-oscillation.

DRV=0 is unity into the filter and MIX=0 is an exact passthrough, the same
null gates as WarpFold.
"""

from remix.schema import (BusRole, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="ripple",
    key="RIPPLE",
    kind=Kind.DSP_EFFECT,
    doc="Ripples-style insert: driven SVF filter, LP/BP/HP, singing resonance.",
    menu=MenuEntry(
        fx2_id=0x0b,
        donor_desc=0x400d58b8,        # DARK REV, the standing donor
        abbr=b"RPPL",
        fullname=b"Ripple",
        build_tag=True,
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        Param(b"FREQ", 90, active=True, formatter=_PLAIN,
              doc="cutoff, ~24 Hz..7.2 kHz on a squared taper"),
        Param(b"RES", 40, active=True, formatter=_PLAIN,
              doc="resonance, up to a screaming Q~30 -- just short of self-oscillation"),
        Param(b"DRV", 0, active=True, formatter=_PLAIN,
              doc="drive into the filter -- the clip is the character; 0 = unity"),
        Param(b"MIX", 127, active=True, formatter=_PLAIN,
              doc="dry/wet; 0 = exact passthrough"),
        Param(), Param(),
        # ---- page 2 -------------------------------------------------------
        Param(),
        Param(b"MODE", 0, 3, active=True, formatter=_STEP,
              labels=("LP", "BP", "HP"),
              doc="filter response: low-pass, band-pass or high-pass"),
        Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/ripple/ripple_svf.asm",
        priority=6,                   # after warpfold
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char="F", is_server=False),
)
