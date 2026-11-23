"""VCA160 -- a VCA compressor modelled on the dbx 160 compressor/limiter (1976), with a light side-chain bus.

Called dB666 in the author's own images (aCiDtRacK) before it was contributed here.

A per-track insert with an id of its own (0x1b preferred; it takes no stock
effect's id, and its code runs in a given-up effect's words), modelled from the 160's schematic and its manual
(modules/vca160/README.md):

  * the detector is dbx's TRUE RMS (the RMS 208 module, M2: Blackmer's
    log-domain RMS, US 3,681,618): the mean square of the signal through one
    time constant. The manual's release rate, 125 dB/s, fixes it at
    tau = 10 log10(e)/125 = 34.7 ms, and the same tau gives the manual's
    attack times (15 / 5 / 3 ms for 10 / 20 / 30 dB) -- the 160's "attack and
    release track the program" is this detector, not a control;
  * THRESHOLD (R70) takes the threshold off the detector's dB output, a
    hard knee (the 160 has no OverEasy; the 160A's OverEasy is page 2);
  * COMPRESSION (R40 with R41/R43) sends a FRACTION k of the dB above
    threshold to the VCA (the dbx 200, M1): ratio = 1/(1 - k). k runs 0..0.992
    (1:1 .. 120:1, the 160's range) over RATI 0..100 and on to k = 2
    (-1:1, the 160A's "negative compression") over 101..127;
  * OUTPUT GAIN (R80), +-20 dB;
  * KEY: OFF (the track itself) or T1..T8: that track's block mean square,
    which KEYBUS (modules/keybus) publishes for every track every block.
Stereo-linked: one detector on (L^2 + R^2)/2, one gain for both channels.
"""
import importlib.util as _ilu
import math as _m
import pathlib as _pl

from remix.schema import (Store, BusRole, Category, DspSection, Formatter,
                          Gate, Harness, Kind, MenuEntry, Module, Param, Evidence, Level, YBase)

FS = 44100.0


def _q(v):
    i = round(v * (1 << 23))
    i = max(-(1 << 23), min((1 << 23) - 1, i))
    return i & 0xFFFFFF


# ---- the 160 ---------------------------------------------------------------
RELEASE_DB_S = 125.0                         # the manual
TAU = 10 * _m.log10(_m.e) / RELEASE_DB_S     # 34.7 ms: the RMS detector
ALPHA = 1.0 - _m.exp(-1.0 / (FS * TAU))
THR_LO, THR_HI = -50.0, 0.0                  # dBFS RMS; the 160's 10 mV..3 V span (49.5 dB)
OUT_DB = 20.0                                # R80: +-20 dB
K_160 = 0.992                                # 120:1 at RATI 100
RATI_160 = 100                               # RATI above this: the 160A's beyond-infinity
KNEE_DB = 10.0                               # ASSUMED OverEasy width (the 160A's page-2 KNEE)
DB_PER_BIT = 10 * _m.log10(2.0)              # 3.0103 dB per bit of MEAN SQUARE

# ---- the key: KEYBUS's mean-square words (X, shared window; modules/keybus) -----
_kb = _ilu.spec_from_file_location("_keybus_manifest", _pl.Path(__file__).resolve().parents[1] / "keybus/manifest.py")
_kbm = _ilu.module_from_spec(_kb)
_kb.loader.exec_module(_kbm)
KEY_MS = _kbm.MS_WORDS                       # track t's block mean square at KEY_MS + t

# P table: LOG[i] = log2(0.5 + i/64)/32 (33), EXP[i] = 2^(i/32)/2 (33; the
# last is 1.0, held at full scale).
LOG = tuple(_q(_m.log2(0.5 + i / 64) / 32) for i in range(33))
EXP = tuple(_q(2.0 ** (i / 32) / 2) for i in range(33))
EXP_AT = len(LOG)
PTABLE = LOG + EXP

W32 = KNEE_DB / DB_PER_BIT / 32               # the knee width, MS bits / 32
CONST = {
    "ALPHA": ALPHA,
    # THRS: T/32 in MS bits = THLO + x * THSPAN
    "THLO": THR_LO / DB_PER_BIT / 32,
    "THSPAN": (THR_HI - THR_LO) / DB_PER_BIT / 32,
    # RATI: k/2 = w * K1 (w <= 100/128); beyond: 1/2 + (w - 100/128) * K2H * 4
    "K1": K_160 * 128 / RATI_160 / 2,
    "WRAT": RATI_160 / 128,
    "K2Q": 128 / (127 - RATI_160) / 2 / 4,
    # OUT: amp bits/32 = (w - 1/2) * OUTK, w = knob/128 (64 -> 0 dB, 127 -> +19.8 dB)
    "OUTK": 128 * OUT_DB / 63.5 / (20 * _m.log10(2.0)) / 32,
    "W2": W32 / 2,
    "W32": W32,
    "IW8": 1.0 / (2 * W32) / 8,               # d^2/(2W) in /32 units: x 1/(2W), stored /8
    "TMIN": -0.5,                             # -16 bits of amplitude (-96 dB)
    "TMAX": 0.125,                            # +4 bits (+24 dB)
    "STRETCH": 1.0 / 127.0,
}
CONSTQ = {k: _q(v) for k, v in CONST.items()}
CONSTQ.update(EXP_AT=EXP_AT, KEYMS=KEY_MS)

_P = Formatter.PLAIN
_B = Formatter.BIPOLAR

MODULE = Module(
    name="vca160",
    key="VCA160",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="MaMarko", author_url="https://github.com/braikomarko-hub",
    # BRAIN's store id stays the one it had as dB666 (octabam.<module directory> then): the defaults and
    # templates the author saved on his card keep applying after the rename (README "FX id")
    store=Store("octabam.db666"),
    evidence=(Evidence(Level.UNIT, unit="MKI", who="MaMarko", date="2026-10-28",
        note="as dB666, the owner's MKI, acidtrack images on EQUALIZER's id from 11 Oct 2026, with the bus at the then "
             "+$3FF8 words in ACIDV79 (27 Oct) and ACIDV81 (28 Oct): side-chain ducking by ear, hours of live use. "
             "That form had no AGU nops, no BEAT handshake and no one-cycle sum"),
              Evidence(Level.EMULATOR, ref="verify_vca160",
        note="bit-exact against its fixed-point model (verify_vca160, dsp_host), KEY read from KEYBUS's mean-square words"),
              Evidence(Level.UNIT, unit="MKI", who="MaMarko", date="2026-11-22",
        note="as dB666 on its own id 0x1b (the DSP words of this PR's first commit, unchanged in the fork since 29 Oct "
             "2026), in the owner's acidtrack images, among them ACIDF07B (from 18 Nov 2026) and ACIDF08 (from 19 Nov): "
             "usually on T5 and T6 with KEY on T1 (the kicks), so the key crosses from core 1 to core 0; also on the "
             "master and on single tracks; no defect noticed (the owner's report, 22 Nov 2026, who confirmed the images "
             "and the 29 Oct date). By ear, "
             "not a measurement. The DSP audit's T34, T31 and T11 commits after it are not flashed"),),
    doc="Modelled on the dbx 160 compressor: true-RMS detector, threshold, ratio to infinity and beyond, side-chain KEY from any track.",
    menu=MenuEntry(
        fx2_id=0x1b,                  # preferred, not a stock id: the remix may move it (registry.assign_ids)
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots
        abbr=b"V160",
        fullname=b"VCA160",
        build_tag=False,
    ),
    params=(
        Param(b"THRS", 96, 128, active=True, formatter=_P,
              doc="THRESHOLD: -50 dBFS (0) .. 0 dBFS (127) RMS, the 160's 49.5 dB span"),
        Param(b"RATI", 50, 128, active=True, formatter=_P,
              doc="COMPRESSION: 0 = 1:1, 50 = 2:1, 75 = 4:1, 100 = 120:1 (inf), 127 = -1:1"),
        Param(b"OUT", 64, 128, active=True, formatter=_B,
              doc="OUTPUT GAIN: -20 .. +20 dB, 0 = unity"),
        Param(b"KEY", 0, count=9, active=True, formatter=Formatter.WIDE_STEPPED,
              labels=("OFF", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"),
              doc="the detector's source: OFF = this track, T1..T8 = that track (KEYBUS's mean square)"),
        Param(b"MIX", 127, 128, active=True, formatter=_P,
              doc="dry/wet: 127 = the 160 alone, 0 = exact passthrough (parallel compression between)"),
        Param(b"", 0),
        Param(b"KNEE", 0, count=2, active=True, formatter=Formatter.STEPPED,
              labels=("HARD", "OVER"),
              doc="HARD = the 160's knee; OVER = the 160A's OverEasy (10 dB wide, assumed)"),
        Param(b"", 0), Param(b"", 0), Param(b"", 0), Param(b"", 0), Param(b"", 0),
    ),
    dsp=DspSection(
        asm="modules/vca160/vca160.asm",
        ptable=PTABLE,
        priority=26,                  # 25 is KEYBUS's, which VCA160 requires
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    requires=("KEYBUS",),
    harness=Harness(layout_char=None, is_server=False),
    gates=(Gate("tools/verify/verify_vca160.py", remix_arg=False),),
    dear={"THRS": 0, "RATI": 127, "OUT": 127, "KEY": 5, "MIX": 127, "KNEE": 1},
)
