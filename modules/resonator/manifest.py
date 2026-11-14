"""RESONATOR -- 4 Chamberlin BPs with per-band gains.

Page 1: GN1..GN4, DECY, MIX. Page 2 (FX SETUP): PIT1..PIT4, SCAL, LIM.
GN = relative band level (64 = unity at SCAL 8). SCAL is the makeup
multiplier: 8 = tame (build-after-TN), 127 ≈ build-TN smash (~×16 at GN64).
g = (GN/128)*(SCAL/128)*32. DECY raises Q; weak drive at 127. LIM is
post-MIX transparent GR (0 = off).
"""
import math as _m

from remix.peak_limiter import source as peak_limiter_source
from remix.schema import (BusRole, Category, Claims, DspSection, Formatter, Gate,
                          Harness, Kind, MenuEntry, Module, Param, Proof,
                          YBase)

_FS = 44100.0
_NYQ = _FS * 0.5
_FMIN, _FMAX = 40.0, 4000.0
_DAMP_MIN, _DAMP_MAX = 0.02, 1.6
_PLAIN = Formatter.PLAIN



def _q(v: float) -> int:
    return max(-(1 << 23), min((1 << 23) - 1, int(round(v * (1 << 23))))) & 0xFFFFFF


def _fc(i: int) -> float:
    return _FMIN * (_FMAX / _FMIN) ** (i / 32)


F_TAB = tuple(_q(2.0 * _m.sin(_m.pi * min(_fc(i), _NYQ * 0.45) / _FS))
              for i in range(33))
DAMP_TAB = tuple(_q(_DAMP_MIN * (_DAMP_MAX / _DAMP_MIN) ** (i / 32))
                 for i in range(33))

MODULE = Module(
    name="resonator",
    key="RESONATOR",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK,
    author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    proof=Proof.CHECK,
    proof_note="Current-block stereo limiter gated in verify_resonator; "
               "unity below ceiling; LIM 127 about -2.5 dBFS. "
               "New limiter awaits hardware confirmation; prior LIM tests used the old curve.",
    doc="FX1 Torso S-4 RING-style filter bank: 4 pitched BPs, SCAL makeup, DECY, LIM.",
    menu=MenuEntry(
        # Custom id 0x1e (BBD 0x1b). Selftest fixtures use DELAY 0x08.
        fx2_id=0x1e,
        donor_desc=0x400d58b8,
        abbr=b"RESO",
        fullname=b"Resonator",
        build_tag=False,
    ),
    params=(
        Param(b"GN1", 64, 128, active=True, formatter=_PLAIN,
              doc="band 1 level; 64 is unity at SCAL 8"),
        Param(b"GN2", 64, 128, active=True, formatter=_PLAIN,
              doc="band 2 level; 64 is unity at SCAL 8"),
        Param(b"GN3", 64, 128, active=True, formatter=_PLAIN,
              doc="band 3 level; 64 is unity at SCAL 8"),
        Param(b"GN4", 64, 128, active=True, formatter=_PLAIN,
              doc="band 4 level; 64 is unity at SCAL 8"),
        Param(b"DECY", 127, 128, active=True, formatter=_PLAIN,
              doc="high rings longer and drives less; low is wider and tracks the input"),
        Param(b"MIX", 127, 128, active=True, formatter=_PLAIN,
              doc="0 is dry, 127 is wet only; exact passthrough when LIM is 0"),
        Param(b"PIT1", 32, 128, active=True, formatter=_PLAIN,
              doc="band 1 centre pitch"),
        Param(b"PIT2", 48, 128, active=True, formatter=_PLAIN,
              doc="band 2 centre pitch"),
        Param(b"PIT3", 64, 128, active=True, formatter=_PLAIN,
              doc="band 3 centre pitch"),
        Param(b"PIT4", 80, 128, active=True, formatter=_PLAIN,
              doc="band 4 centre pitch"),
        Param(b"SCAL", 8, 128, active=True, formatter=_PLAIN,
              doc="gain scale: 8 is tame, 127 is a smash"),
        Param(b"LIM", 0, 128, active=True, formatter=_PLAIN,
              doc="peak limiter after MIX; 0 off, 1..127 ≈ 0..-2.5 dB ceiling"),
    ),
    dsp=DspSection(
        asm="modules/resonator/resonator.asm",
        subst={pl: peak_limiter_source("rspk", 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e, 0x2f, knob=0xe) for pl in ("A", "B")},
        ptable=F_TAB + DAMP_TAB,
        priority=31,
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    claims=Claims(fx1_only=True),
    harness=Harness(layout_char="W", is_server=False),
    gates=(Gate("tools/verify/verify_resonator.py", remix_arg=False),),
    dear={"GN1": 64, "GN2": 64, "GN3": 64, "GN4": 64,
          "PIT1": 64, "PIT2": 80, "PIT3": 96, "PIT4": 112,
          "SCAL": 8, "DECY": 127, "MIX": 127},
)
