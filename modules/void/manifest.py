"""VOID -- scrape: noise or input × audio-rate LFO, then body + drive.

MODE=SCRAPE (Idea A) with one-sample FDBK through DRV (FEED start). Stages:
noise → HPF/COLR → FDBK+DRV → AM → WID → BAL vs dry. r7 $40..$4f stays
reserved for a longer FEED delay / MODE=VOID later.
"""
import math as _m

from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, Module, Param, Proof, YBase)

_FS = 44100.0
_P = Formatter.PLAIN
_S = Formatter.STEPPED
_BLANK = Param(b"", 0)


def _q(v: float) -> int:
    return round(v * (1 << 23)) & 0xFFFFFF


def _rate_inc(k: int) -> int:
    """Phase step for RATE k: 2 Hz .. 200 Hz exponential.

    The first taper (20 Hz .. 8 kHz) packed the useful scrape into ~0..22;
    this puts that region across most of the travel. WarpFold / LOFI2:
    one cycle is 2.0 in Q23, so step = 2·f/fs.
    """
    f = 2.0 * (100.0) ** (k / 127.0)
    return _q(2.0 * f / _FS)


def _onepole(f: float) -> int:
    return _q(1.0 - _m.exp(-2.0 * _m.pi * f / _FS))


# P table, 387 words, read through the ptable literal:
#   +0    RATE   phase step for RATE = 0..128 (entry 128 = neighbour of 127)
#   +129  HPF    one-pole coef; knob 0 forced to 0 (bypass) in the block decode
#   +258  COLOR  one-pole LP coef; knob 127 forced to ~1 (open) in the block decode
RATE = tuple(_rate_inc(min(k, 127)) for k in range(129))
HPF = tuple(_onepole(20.0 * (400.0) ** (k / 127.0)) for k in range(129))  # 20 Hz .. 8 kHz
COLOR = tuple(_onepole(30.0 * (16000.0 / 30.0) ** (k / 127.0)) for k in range(129))  # 30 Hz .. 16 kHz

MODULE = Module(
    name="void",
    key="VOID",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK,
    author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    proof=Proof.HARDWARE,
    proof_note="MKII LATEST NP / VRCS VJ: SRC LFO|NBR, COLR/HPF main, SHPE/DPTH SETUP, DPTH default 127; verify_void",
    doc="Input↔noise BAL; LFO/nbr AM + DRV/FDBK on noise only; WID stereo grit.",
    menu=MenuEntry(
        # No free custom FX2 id left in-tree (SHATTER=0x0a, …). PLATE is
        # VERBERATION's (GATE VERB's until 6 Nov 2026). Replace COMB FILTER; DSP still sits in harvested PLATE.
        fx2_id=0x13,
        replaces="COMB FILTER",
        donor_desc=0x400d58b8,  # DARK REV page layout (12 knobs)
        abbr=b"VOID",
        fullname=b"VOID",
        build_tag=False,
    ),
    params=(
        # ---- page 1 --------------------------------------------------------
        Param(b"BAL", 0, 128, active=True, formatter=_P,
              doc="dry to noise: 0 is exact dry, 127 pure noise; AM, DRV and FDBK act on the noise only"),
        Param(b"RATE", 72, 128, active=True, formatter=_P,
              doc="LFO rate; no effect when SRC is NBR"),
        Param(b"COLR", 64, 128, active=True, formatter=_P,
              doc="low-pass on the noise, after the HPF; 127 is open; the dry is untouched"),
        Param(b"HPF", 0, 128, active=True, formatter=_P,
              doc="high-pass on the noise, before COLR; 0 bypasses; the dry is untouched"),
        Param(b"DRV", 0, 128, active=True, formatter=_P,
              doc="soft-clip on the noise only (before BAL); 0 bypasses"),
        Param(b"FDBK", 0, 128, active=True, formatter=_P,
              doc="one-sample AC feedback on the noise only; 0 is off"),
        # ---- page 2 --------------------------------------------------------
        # Top: SHPE DPTH WID ; bottom: SRC · · .
        # SHPE=$c knob; DPTH=$c companion; WID=$d knob; SRC=$d companion.
        Param(b"SHPE", 0, 3, active=True, formatter=_S,
              labels=("SIN", "SQR", "SAW"),
              doc="LFO shape; no effect when SRC is NBR"),
        Param(b"DPTH", 127, 128, active=True, formatter=_P,
              doc="AM depth on the noise (LFO or neighbour envelope); full by default"),
        Param(b"WID", 0, 128, active=True, formatter=_P,
              doc="noise stereo width; 0 is mono; the side shares HPF, COLR and DRV"),
        Param(b"SRC", 0, 2, active=True, formatter=_S,
              labels=("LFO", "NBR"),
              doc="AM source: the LFO, or NBR, the previous track's key-bus envelope"),
        _BLANK,
        _BLANK,
    ),
    dsp=DspSection(
        asm="modules/void/void.asm",
        ptable=RATE + HPF + COLOR,
        priority=22,
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
    ),
    harness=Harness(layout_char="M", is_server=False),  # B = MULTIBCOMP; W = RESONATOR; V = DARK
    gates=(Gate("tools/verify/verify_void.py", remix_arg=False),),
    dear={"BAL": 127, "RATE": 127, "SHPE": 2, "DPTH": 127, "DRV": 127,
          "FDBK": 100, "COLR": 0, "HPF": 127, "WID": 64},
)
