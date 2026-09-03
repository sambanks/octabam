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
    name="nimbuslite",
    key="NIMBUS LITE",
    kind=Kind.DSP_EFFECT,
    doc="Nimbus on one allocator buffer: 371 ms, 4 grains, freeze.",
    menu=MenuEntry(
        fx2_id=0x1d,
        # ⚠️ was 0x0c/0x0d until 2 Sep 2026: STOCK ids (EQUALIZER /
        # DJ EQ). The dispatch tables are shared with FX1, so the old
        # id hijacked that effect on both menus. schema.STOCK_FX2_IDS
        # now rejects it at construction.
        donor_desc=0x400d58b8,        # DARK REV, the standing donor
        abbr=b"NMBL",
        fullname=b"NimbusLite",
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
        asm="modules/nimbuslite/nimbus_lite.asm",
        priority=9,                   # after rungs
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,            # the buffer is core-private Y, no $30000
        r7_latch_slot=None,
        gate_label=None,
    ),
    # ⚠️ NO owns_fx2_buffers, and that is the whole point of this variant.
    # Nimbus pins Y:0x4000-0xBFFF -- both core-private FX2 slots, every
    # buffer the allocator has to hand out -- so the ledger refuses it beside
    # the seven stock effects that need one. This ASKS the allocator for one
    # 16,384-word slot at init (docs/DSP.md section 10) exactly as those
    # stock effects do, so they coexist and two instances get two slots.
    #
    # It still cannot sit beside a module with FIXED buffers there (BusVerb,
    # Nimbus): two of the allocator's four FX2 bases are 0x30000/0x34000, in
    # payload A's half of the shared window, which is where BusVerb's
    # relocated tank and the bus scratch live. stock_instance_buffer is the
    # claim that says "I take an allocator slot", and the ledger already
    # refuses that pairing.
    claims=Claims(stock_instance_buffer=True),
    harness=Harness(layout_char="Q", is_server=False),
)
