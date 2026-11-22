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
  * KEY: OFF (the track itself) or T1..T8, read from the SIDE-CHAIN BUS: a
    hook in the stock dispatcher (where SIDECHAIN_COMPRESSOR hooks) keeps a
    record of four words per track in the shared window (BEAT COUNT LAST
    LEVEL); a keyed VCA160 writes its heartbeat to BEAT and reads LEVEL, the
    block's mean square, which the tap computes only while a VCA160 keys
    that track.
Stereo-linked: one detector on (L^2 + R^2)/2, one gain for both channels.
"""
import math as _m

from remix.schema import (BusRole, Category, Claims, DspHook, DspRange, DspSection, Formatter,
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

# ---- the side-chain bus ------------------------------------------------------
# The top of T8's and T4's FX2 slots (+$3FF0): above every stock effect's
# extent (DARK REV +$3DA2) and inside Y:0x37f00..0x3ffff, which payload B's
# boot zero loop clears. (Until 26 Oct 2026 one word per track sat at
# $33ff8 / $3bff8; the demand loader's window code now starts below $33ff8
# and stops payload A's boot zero loop at 0x33dc3. 26-29 Oct: one word per
# track at +$3FF8.) One record of four words per track, BEAT COUNT LAST LEVEL, from +$3FF0 of
# each core's half: payload A tracks 4..7 at $37ff0.., payload B tracks 0..3
# at $3fff0... A VCA160 whose KEY names the track writes its heartbeat to BEAT
# each block; the tap (the only writer of COUNT, LAST and LEVEL) sums the
# block only while BEAT changed within the last WANT_BLOCKS blocks. Track t
# (0-based)'s LEVEL: $3fff0 + 4t + 3 (t < 4) or $37fe0 + 4t + 3 (t >= 4).
REC_A, REC_B = 0x37FF0, 0x3FFF0
LEVEL_AT = 3
WANT_BLOCKS = 8

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
CONSTQ.update(EXP_AT=EXP_AT, WANT=WANT_BLOCKS)

_P = Formatter.PLAIN
_B = Formatter.BIPOLAR

MODULE = Module(
    name="vca160",
    key="VCA160",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="MaMarko", author_url="https://github.com/braikomarko-hub",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="MaMarko", date="2026-10-28",
        note="as dB666, the owner's MKI, acidtrack images on EQUALIZER's id from 11 Oct 2026, with the bus at today's "
             "+$3FF8 words in ACIDV79 (27 Oct) and ACIDV81 (28 Oct): side-chain ducking by ear, hours of live use. "
             "That form had no AGU nops, no BEAT handshake and no one-cycle sum"),
              Evidence(Level.EMULATOR, ref="verify_vca160",
        note="bit-exact against its fixed-point model (verify_vca160, dsp_host), the tap and its handshake included"),
              Evidence(Level.UNIT, unit="MKI", who="MaMarko", date="2026-11-22",
        note="as dB666 on its own id 0x1b (DSP source byte-identical to this PR's, unchanged in the fork since 29 Oct "
             "2026), in the owner's acidtrack images, among them ACIDF07B (from 18 Nov 2026) and ACIDF08 (from 19 Nov): "
             "usually on T5 and T6 with KEY on T1 (the kicks), so the key crosses from core 1 to core 0; also on the "
             "master and on single tracks; no clicks, noise or hangs heard (the owner's report, 22 Nov 2026). By ear, "
             "not a measurement"),),
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
              doc="the detector's source: OFF = this track, T1..T8 = that track (the bus)"),
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
        priority=25,                  # 19 is STUTTR's and VOCODER's
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
        hooks=(
            # SIDECHAIN_COMPRESSOR's `sctap` site: the dispatcher's FX1 entry,
            # every track, every block, the track's audio at X:0..$1f. The
            # displaced `move x:>$208,r6` is replayed inside dbt_tap, after its address arithmetic.
            DspHook({"A": 0x004a7, "B": 0x0029c}, (0x66f000, 0x000208), "dbt_tap",
                    "dispatcher: every keyed track's block mean square, into its record"),
        ),
        subst={
            "A": {"@ROFF@": "$37fe0"},     # REC_A - 4 x 4: T5..T8 are tracks 4..7
            "B": {"@ROFF@": "$3fff0"},     # REC_B - 0: T1..T4 are tracks 0..3
        },
    ),
    claims=Claims(dsp_ranges=(
        DspRange("y", 0x7FF0, 0x10, "the side-chain bus: a record of four words per track "
                                    "(BEAT COUNT LAST LEVEL), four per core's half", half_relative=True),
    )),
    conflicts=(("SIDECHAIN_COMPRESSOR",
                "the same dispatcher hook site (sctap): both tap every track's block at the FX1 entry"),
               ("KEYBUS",
                "the same dispatcher hook site: KEYBUS publishes a peak, VCA160's tap a mean square"),),
    harness=Harness(layout_char=None, is_server=False),
    gates=(Gate("tools/verify/verify_vca160.py", remix_arg=False),),
    dear={"THRS": 0, "RATI": 127, "OUT": 127, "KEY": 5, "MIX": 127, "KNEE": 1},
)
