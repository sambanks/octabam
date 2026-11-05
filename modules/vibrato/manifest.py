"""VIBRATO -- a pitch vibrato: sine, triangle, square or random pitch, FX1.

A per-track insert (FX1 only): one modulated delay per channel, wet only,
MIX blends. DEP is a pitch depth in cents, held as SPD moves (the delay
swing scales as 1/rate, capped by the 1,024-word lines). Each shape is a
pitch trajectory and the delay its integral: SINE is a sine, TRI a triangle
in pitch, SQR a two-note trill (a triangle in delay), RND a new random pitch
each half cycle (the square's step rate), steered so the delay stays in its
swing. SLEW rounds the trajectory (a one-pole on the delay offset, up to a
quarter cycle); WID offsets R's phase by up to half a cycle, and on RND
decorrelates R's random stream instead.

FX1 only, as MODULATION and RESONATOR are: two 1,024-word lines out of the
FX1 slot's 3,072, the base read from the allocator at init; on an FX2 slot
it is a dry pass and writes nothing (`Claims(fx1_only=True)`, proven by
verify_vibrato). vibrato_ref.py is the float reference and the source of the
P table (103 words). Prototyped in Faust (README, "Design").
"""

import importlib.util
import pathlib

from remix.schema import (BusRole, Category, Claims, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, Module, Param, Proof, YBase)

_spec = importlib.util.spec_from_file_location("vibrato_ref",
                                               pathlib.Path(__file__).with_name("vibrato_ref.py"))
_ref = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ref)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED
_BLANK = Param(b"", 0)

MODULE = Module(
    name="vibrato",
    key="VIBRATO",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="Bryan T", author_url="https://github.com/bryantysinger",
    proof=Proof.HARDWARE,
    proof_note="Bryan T's MKII, _bt_oct with VIBRATO and LOAD METER, 4 Nov 2026: four FX1 instances on tracks 1-4, 4.5 % a slot (LOAD METER over USB)",
    doc="FX1: pitch vibrato -- sine, triangle, square trill or random; depth in cents.",
    menu=MenuEntry(
        # 0x0b: a free-pool id; WAVE (an experiment) prefers it too, and the
        # registry settles a remix carrying both (registry.assign_ids).
        fx2_id=0x0b,
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects 7/9/11
        abbr=b"VIBR",
        fullname=b"VIBRATO",
        build_tag=False,
    ),
    params=(
        # ---- page 1: the LFO on top, WID and MIX beneath --------------------
        Param(b"SPD", 80, active=True, formatter=_PLAIN,
              doc="rate, 0.25 to 15.5 Hz, exponential (80 is 3.4 Hz; 21 steps an octave)"),
        Param(b"DEP", 48, active=True, formatter=_PLAIN,
              doc="peak pitch deviation, 100 (k/127)^2 cents: 14 at 48, 25 at 64, 100 at 127"),
        Param(b"SLEW", 0, active=True, formatter=_PLAIN,
              doc="rounds the shape: 0 is none, 127 a quarter-cycle time constant"),
        Param(b"WID", 0, active=True, formatter=_PLAIN,
              doc="R's LFO lead, up to half a cycle; on RND, decorrelates R's random pitch"),
        _BLANK,
        Param(b"MIX", 127, active=True, formatter=_PLAIN,
              doc="dry/wet; 127 is the vibrato alone, 0 is exact passthrough"),
        # ---- page 2: SHP on slot 6, as MODE is on every effect -------------
        Param(b"SHP", 0, 4, active=True, formatter=_STEP,
              labels=("SINE", "TRI", "SQR", "RND"),
              doc="pitch shape: SINE, TRI, SQR (a two-note trill) or RND (stepped random)"),
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/vibrato/vibrato.asm",
        ptable=_ref.TABLE,            # INC, PERW, DEV8 (33 words each), FACW (4)
        # the LFSR's per-payload seed word (eor r7 << 8 at init): tracks on
        # the two cores never share a random sequence
        subst={p: {"@SEED@": f"${_ref.SEEDS[p]:06x}"} for p in ("A", "B")},
        priority=32,
        bus_role=BusRole.NONE,        # an insert; it writes nothing to the bus
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    # Two 1,024-word lines out of the 3,072 an FX1 slot gives; `fx1_only` is
    # the promise that an FX2 instance writes nothing (verify_vibrato).
    claims=Claims(stock_instance_buffer=True, buffer_words=2048, fx1_only=True),
    harness=Harness(layout_char="9", is_server=False, bus_client=False),
    gates=(Gate("tools/verify/verify_vibrato.py", remix_arg=False),),
    dear={"SPD": 127, "DEP": 127, "SLEW": 127, "WID": 127, "MIX": 127, "SHP": 3},
)
