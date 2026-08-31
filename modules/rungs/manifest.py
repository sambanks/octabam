"""Rungs -- a Mutable-Instruments-Rings-flavoured modal resonator.

A per-track INSERT (no bus role, both payloads, any track): the track's own
audio excites a bank of EIGHT two-pole resonators tuned to a partial series,
Rings-as-an-effect -- drums become struck metal, melodies ring through a
bell. MODE picks the partial series (STRING harmonic / BELL / GLASS
stretched-inharmonic), STRUCT stretches it further, DAMP is the ring time
(T60 ~0.1-9 s), FREQ places the fundamental (~55 Hz .. ~1.25 kHz).

Mode frequencies are computed per block from the knobs -- sin/cos by a
half-angle polynomial, tuning error ~0.2% at the extremes 🟡 (measured in the
render pass; a resonator a few cents off is character, not a defect).

MIX=0 is an exact passthrough, the standing null gate.
"""

from remix.schema import (BusRole, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="rungs",
    key="RUNGS",
    kind=Kind.DSP_EFFECT,
    doc="Rings-style insert: 8-mode modal resonator, STRING/BELL/GLASS.",
    menu=MenuEntry(
        fx2_id=0x0c,
        donor_desc=0x400d58b8,        # DARK REV, the standing donor
        abbr=b"RNGS",
        fullname=b"Rungs",
        build_tag=True,
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        Param(b"FREQ", 60, active=True, formatter=_PLAIN,
              doc="the resonator's fundamental, ~55 Hz..1.25 kHz"),
        Param(b"STRC", 0, active=True, formatter=_PLAIN,
              doc="structure -- stretches the partial series toward inharmonic"),
        Param(b"DAMP", 80, active=True, formatter=_PLAIN,
              doc="ring time, T60 ~0.1..9 s -- how long the modes sing"),
        Param(b"MIX", 100, active=True, formatter=_PLAIN,
              doc="dry/wet; 0 = exact passthrough"),
        Param(), Param(),
        # ---- page 2 -------------------------------------------------------
        Param(),
        Param(b"MODE", 0, 3, active=True, formatter=_STEP,
              labels=("STRING", "BELL", "GLASS"),
              doc="partial series: harmonic string, bell, or stretched glass"),
        Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/rungs/rungs_modal.asm",
        priority=7,                   # after ripple
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char="M", is_server=False),
)
