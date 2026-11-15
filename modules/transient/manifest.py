"""TRANSIENT -- a differential-envelope transient shaper.

A per-track insert. ATCK boosts or cuts each onset, SUST lengthens or
tightens each tail, both bipolar and level-independent: the detector works
in log2 units, so the same setting does the same thing to a quiet hit and a
loud one. No threshold, no lookahead, no buffers.

The law (modules/transient/DESIGN.md, float reference transient_ref.py):
  d   = max(|L|, |R|) -> linear peak (instant attack, 10 ms release)
  v   = log2(max(peak, 2^-16)) / 32         clb/normf + a 33-point table
  F   = follower(v; 0.5 ms up, 50 ms down)   the envelope
  S   = follower(v; TIME up, 50 ms down), S >= F - 2 bits
  H   = follower(v; 0.5 ms up, 500 ms down)  48-bit state
  g   = clamp(ATCK*max(F-S,0) + SUST*max(H-F,0), +-2 bits) + OUT
  out = x + MIX*(x*2^g - x)                   2^g from a 33-point table
"""
import math as _m

from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, Module, Param, Evidence, Level, YBase)

_FS = 44100.0


def _q(v):
    """Q23, two's complement in 24 bits."""
    return round(v * (1 << 23)) & 0xFFFFFF


def _coef(ms):
    return 1.0 - _m.exp(-1.0 / (_FS * ms * 1e-3))


# P table, 99 words, read through the ptable literal:
#   +0   LOG: log2(m)/32 for m = 0.5 + i/64, i = 0..32 (m in [0.5, 1])
#   +33  EXP: 2^(-4 + i/4) / 16, i = 0..32 (gains 2^-4 .. 2^4, stored /16;
#        the last word is 1.0, held at the largest Q23 value)
#   +66  TIMEC: the slow follower's attack coefficient for TIME = 4i,
#        i = 0..32, TIME -> 5 * 10^(TIME/127) ms
LOG = tuple(_q(_m.log2(0.5 + i / 64) / 32) for i in range(33))
EXP = tuple(min(_q(2.0 ** (-4 + i / 4) / 16), 0x7FFFFF) for i in range(33))
TIMEC = tuple(_q(_coef(5.0 * 10 ** (4 * i / 127))) for i in range(33))

_B = Formatter.BIPOLAR
_P = Formatter.PLAIN
_BLANK = Param(b"", 0)

MODULE = Module(
    name="transient",
    key="TRANSIENT",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="Ignorato", author_url="https://github.com/Ignorato",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="Ignorato", image="OCTABAM2", date="2026-10-03",
        note="images OCTABAM2 and OCTABAM3 (remix transient), 3 Oct 2026"),),
    doc="Transient shaper: ATCK and SUST reshape onsets and tails, level-independent.",
    menu=MenuEntry(
        fx2_id=0x0a,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"TRNS",
        fullname=b"TRANSIENT",      # all caps, as the stock names
        build_tag=False,              # OS VERSION (OCTABAM<N>) traces the image
    ),
    params=(
        Param(b"ATCK", 64, 128, active=True, formatter=_B,
              doc="onset: above centre up to +12 dB punch, below up to -12 dB softer; centre untouched"),
        Param(b"SUST", 64, 128, active=True, formatter=_B,
              doc="tail: above centre longer and roomier, below tighter (up to 12 dB); centre untouched"),
        Param(b"TIME", 40, 128, active=True, formatter=_P,
              doc="how long an onset counts as the transient: 5 ms at 0 to 50 ms at 127"),
        Param(b"OUT", 64, 128, active=True, formatter=_B,
              doc="output trim, -12 to +12 dB; centre is unity"),
        Param(b"MIX", 127, 128, active=True, formatter=_P,
              doc="dry/wet; 0 is exact passthrough"),
        _BLANK,
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/transient/transient.asm",
        ptable=LOG + EXP + TIMEC,
        priority=17,
        bus_role=BusRole.NONE,        # an insert; never on the bus
        ybase=YBase.NEVER,            # no buffers, nothing in the shared window
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char="N", is_server=False),
    gates=(Gate("tools/verify/verify_transient.py", remix_arg=False),),
    dear={"ATCK": 127, "SUST": 127, "TIME": 0, "OUT": 127, "MIX": 127},
)
