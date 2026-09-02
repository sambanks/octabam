"""HELLO WORLD -- a linear volume knob, and the reference minimal insert.

The smallest complete module: one page-1 knob (GAIN), out = in * GAIN/128,
processed in place per the insert contract. It exists to be read -- the
worked example of manifest + engine + render gates that _template describes
-- and to stay permanently buildable as a canary for the pipeline.

GAIN >= 127 takes an early-out before any arithmetic, so 127 is a BIT-EXACT
passthrough (frames are in place; unity gain is "touch nothing"). GAIN=0 is
exact silence (a zero coefficient through mpy). Both are render gates.
The cost of the exact top: 126 -> 127 steps 0.984 -> 1.0 (~0.14 dB).

Planned, not present: a taper select on page-2 slot 7 (LIN/LOG/...), and
FX1 availability once build_fx1.py's chooser-relocation is folded into the
module contract. Neither is started.
"""

from remix.schema import (BusRole, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param, YBase)

MODULE = Module(
    name="hello",
    key="HELLO WORLD",
    kind=Kind.DSP_EFFECT,
    doc="Reference minimal insert: one GAIN knob, out = in * GAIN/128.",

    menu=MenuEntry(
        # Free on BOTH sides: not one of stock's fifteen (so no stock effect
        # is displaced on FX1 either -- schema.STOCK_FX2_IDS), and no module
        # claims it. The registry is the arbiter and refuses a duplicate at
        # import, remix membership notwithstanding; 0x17 -- which this module
        # arrived on -- is Rungs's since 2 Sep 2026.
        fx2_id=0x1b,
        donor_desc=0x400d58b8,        # DARK REV -- the proven insert donor
        abbr=b"HELO",                 # <=4 chars: the field is 5 bytes and must
                                      # stay NUL-terminated. "HELLO" filled all 5
                                      # with no terminator, so a C-string read ran
                                      # into fullname -- crashing on LFO modulation
                                      # (line-F, faulting addr = the abbr bytes).
        fullname=b"HELLO WORLD",      # 11 of 13 bytes
        build_tag=False,
    ),

    params=(
        # ---- page 1 -------------------------------------------------------
        Param(b"GAIN", 127, 128, active=True, formatter=Formatter.PLAIN,
              doc="linear level, out = in x GAIN/128; 127 exact pass, 0 silence"),
        Param(), Param(), Param(), Param(), Param(),
        # ---- page 2: none in v1 (taper select will land on slot 7) --------
        Param(), Param(), Param(), Param(), Param(), Param(),
    ),

    dsp=DspSection(
        asm="modules/hello/gain.asm",
        priority=11,                  # after bodeshift (10); byte-load-bearing
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,            # no absolute Y anywhere in the source
        r7_latch_slot=None,
        gate_label=None,
    ),

    harness=Harness(layout_char="H", is_server=False),
)
