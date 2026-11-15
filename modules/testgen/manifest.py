"""TESTGEN -- a measurement source: exact, reproducible test signals on a track.

An FX2 insert that replaces its track's audio with a known signal, so the
track's output (analog, or a channel of the USB audio out) carries it: for
measuring the Octatrack's path, the USB audio stream, or any module's
response. modules/testgen/README.md says what each signal is proved to be.

SINE at ISO third-octave frequencies and A 440, with a fine tune, an exponential SWEEP (20 Hz to 20 kHz
over LEN, then 1 s of silence, repeating), PINK and WHITE noise, and an
IMPULSE train, a NEEDLE pulse train at FREQ and a DC offset; LEVL in 0.5 dB steps,
CHAN routing. An FX1 effect (buffer-free); on FX2 it passes its input untouched.
"""
import math as _m

from remix.schema import (BusRole, Category, Claims, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, Module, Param, Evidence, Level, YBase)

_FS = 44100.0


def _q23(v):
    """Q23, two's complement in 24 bits, held at the largest positive value."""
    return min(round(v * (1 << 23)), 0x7FFFFF) & 0xFFFFFF


FREQS = (20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 440, 500, 630, 800,
         1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000)
# the ISO third-octave centres, and A 440 between 400 and 500

# P table, 192 words, read through the ptable literal:
#   +0    LEVEL[128]  LEVL k -> 10^(-(127 - k) * 0.5 / 20), Q23 (0 dBFS held at 0x7fffff);
#                     LEVL 0 is silence, and the default: choosing TESTGEN makes no sound
#                     until LEVL is turned up (a full-level tone on insert, Ignorato's MKII)
#   +128  FINC[32]    FREQ k -> the phase increment f / FS * 2^24 for FREQS[k]
#                     (a cycle is 2^24; 1 kHz is 380436, 1000.0007 Hz)
#   +160  SWD[16]     LEN step t = LEN >> 3 -> the sweep's growth per sample, (r - 1) * 2^35,
#                     r^N = 20 kHz / 20.0007 Hz, N = (t + 1) 44100 (computed, not tabled)
# The sine's polynomial, the noise generator and the pink filter are
# immediates in testgen.asm; testgen_ref.py holds the same laws.
LEVEL = (0,) + tuple(_q23(10 ** (-(127 - k) * 0.5 / 20)) for k in range(1, 128))
FINC = tuple(round(f / _FS * (1 << 24)) for f in FREQS)
_SWEEP_INC0 = 7609                              # 20.0007 Hz; testgen_ref.SWEEP_INC0
SWN = tuple((t + 1) * int(_FS) for t in range(16))
SWD = tuple(round(((20000.0 / (_SWEEP_INC0 * _FS / (1 << 24))) ** (1.0 / n) - 1.0) * (1 << 35)) for n in SWN)

_P = Formatter.PLAIN
_S = Formatter.STEPPED
_W = Formatter.WIDE_STEPPED
_BLANK = Param(b"", 0)

MODE_LABELS = ("SINE", "SWEP", "PINK", "WHIT", "IMPL", "NEDL", "DC")
CHAN_LABELS = ("L+R", "L", "R", "L-R", "MONO")
FREQ_LABELS = ("20", "25", "31.5", "40", "50", "63", "80", "100", "125", "160", "200", "250", "315",
               "400", "A440", "500", "630", "800", "1k", "1k25", "1k6", "2k", "2k5", "3k15", "4k", "5k",
               "6k3", "8k", "10k", "12k5", "16k", "20k")

MODULE = Module(
    name="testgen",
    key="TESTGEN",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="Ignorato", author_url="https://github.com/Ignorato",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="Ignorato", image="OCTABAM4", date="2026-10-04",
        note="images OCTABAM4-6 and 10 (remix testgen), 3-4 Oct 2026; 0.1 measured at the main outs; FX1-only in "
             "the emulator so far"),),
    doc="Measurement source: a sine, sweep, pink or white noise, impulses, a needle pulse train or DC replace the track's audio.",
    menu=MenuEntry(
        fx2_id=0x17,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"TGEN",
        fullname=b"TESTGEN",
        build_tag=False,
    ),
    params=(
        Param(b"LEVL", 0, 128, active=True, formatter=_P,
              doc="output level: 0 = silent (the default), 1 = -63 dBFS .. 127 = 0 dBFS, 0.5 dB a step"),
        Param(b"FREQ", 18, 32, active=True, formatter=_W, labels=FREQ_LABELS,
              doc="SINE and NEEDLE frequency in Hz: ISO third-octave centres 20 Hz-20 kHz, and A440"),
        Param(b"LEN", 32, 128, active=True, formatter=_P,
              doc="SWEEP length 1..16 s (LEN/8 + 1) and IMPULSE period, a quarter of that"),
        Param(b"FINE", 64, 128, active=True, formatter=Formatter.BIPOLAR,
              doc="SINE, NEEDLE fine tune: -64..+63 is -200..+197 cents, 3.125 a step; 0 = FREQ exactly"),
        _BLANK, _BLANK,
        Param(b"MODE", 0, 7, active=True, formatter=_W, labels=MODE_LABELS,
              doc="SINE, SWEEP (20 Hz-20 kHz), PINK, WHITE, IMPULSE, NEEDLE (pulses at FREQ), DC (at LEVL)"),
        _BLANK,
        Param(b"CHAN", 0, 5, active=True, formatter=_S, labels=CHAN_LABELS,
              doc="L+R (noise independent per side), L, R, L and inverted R, MONO (same both sides)"),
        _BLANK, _BLANK, _BLANK,
    ),
    mode_slot=6,
    dsp=DspSection(
        asm="modules/testgen/testgen.asm",
        ptable=LEVEL + FINC + SWD,
        priority=18,
        bus_role=BusRole.NONE,        # an insert
        ybase=YBase.NEVER,            # no buffers, nothing in the shared window
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char="G", is_server=False),
    # FX1 ONLY: a source belongs at the head of a track's chain. An FX2 instance (a 0.1
    # project) runs as a dry pass, so the chooser takes no FX2 row and the pricer charges
    # FX1 slots only. Two in series crackled on Ignorato's MKII (FX1 PINK into FX2 TESTGEN,
    # OCTABAM10, 4 Oct 2026; cause not found).
    claims=Claims(fx1_only=True),
    gates=(Gate("tools/verify/verify_testgen.py", remix_arg=False),),
    dear={"LEVL": 127, "FREQ": 31, "FINE": 127, "LEN": 127, "MODE": 0, "CHAN": 3},
)
