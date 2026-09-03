"""Nimbus -- a Mutable-Instruments-Clouds-flavoured granular texture insert.

A per-track INSERT with a real buffer: the track's audio records continuously
into a 32,768-word mono line (743 ms) and four unity-rate grains read it back
-- two per channel at half-period offsets, so each channel's triangle windows
sum to constant power. POS reaches back into the buffer, SIZE picks the grain
length (23/46/93/186 ms), DENS scatters each grain's start by up to ~92 ms of
per-grain randomness (latched at the grain's own wrap, the trap GRAIN taught
us about), and FRZE stops the write head so the last 743 ms becomes a frozen
cloud to graze.

⚠️ ONE NIMBUS PER CORE. The buffer is the fixed core-private FX2-instance
region Y:0x4000-0xBFFF -- the same ground BusVerb's tank uses in `bus`.
Safe in an insert remix because every module there is zero-Y-footprint
(exactly the argument BUS.md made for the hardcoded-base server), but two
Nimbus instances on one core would share one buffer, and a legacy project
putting a buffer-writing stock FX2 on the same core carries the same caveat
PLAN.md records for the servers.

MIX=0 is an exact passthrough (during warm-up the effect outputs pure dry).
"""

from remix.schema import (BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="nimbus",
    key="NIMBUS",
    kind=Kind.DSP_EFFECT,
    doc="Clouds-style insert: 743 ms granular texture, 4 grains, freeze.",
    menu=MenuEntry(
        fx2_id=0x1a,
        # ⚠️ was 0x0c/0x0d until 2 Sep 2026: STOCK ids (EQUALIZER /
        # DJ EQ). The dispatch tables are shared with FX1, so the old
        # id hijacked that effect on both menus. schema.STOCK_FX2_IDS
        # now rejects it at construction.
        donor_desc=0x400d58b8,        # DARK REV, the standing donor
        abbr=b"NMBS",
        fullname=b"Nimbus",
        build_tag=True,
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        Param(b"POS", 30, active=True, formatter=_PLAIN,
              doc="how far back into the 743 ms buffer the grains read"),
        Param(b"SIZE", 70, active=True, formatter=_PLAIN,
              doc="grain length, 23/46/93/186 ms"),
        Param(b"DENS", 40, active=True, formatter=_PLAIN,
              doc="per-grain start scatter, up to ~92 ms -- 0 is coherent, high is cloud"),
        Param(b"MIX", 100, active=True, formatter=_PLAIN,
              doc="dry/wet; 0 = exact passthrough"),
        Param(), Param(),
        # ---- page 2 -------------------------------------------------------
        Param(),
        Param(b"FRZE", 0, 2, active=True, formatter=_STEP,
              labels=("RUN", "HOLD"),
              doc="stop the write head -- the last 743 ms becomes a frozen cloud"),
        Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/nimbus/nimbus_grain.asm",
        priority=8,                   # after rungs
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,            # the buffer is core-private Y, no $30000
        r7_latch_slot=None,
        gate_label=None,
    ),
    # The 743 ms line is hardcoded into Y:0x4000-0xBFFF -- the same per-CORE
    # region BusVerb's tank uses, which is why the two cannot share a core
    # and why this module has its own remix.
    claims=Claims(owns_fx2_buffers=True),
    harness=Harness(layout_char="N", is_server=False),
)
