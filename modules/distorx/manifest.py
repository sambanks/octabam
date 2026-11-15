"""DISTORX -- two pedals in one insert: the BOSS SD-1 Super OverDrive (1981)
and the Pro Co RAT (1978), with the Turbo RAT's LEDs as a third MODE.

MODE 0, OFF (v8, the default), runs nothing: the frames pass untouched, so
DISTORX can go on a track live and a pedal be faded in.

MODE 1, SD-1, is the BOSS circuit from the 1981 service notes' part values, at
the sample rate since v8 (2x until then).

MODE 2, RAT, and MODE 3, TURBO, are the RAT circuit as ElectroSmash's
analysis gives it (parts list and schematic), modelled from its part values:

  in   = (L + R)/2 * IN                      0 dBFS = 1 V at the jack
  vp   = HP 7.2 Hz                           C1, R2 (R3/C2's 159 kHz pole left out)
  --- at the sample rate (twice it until 15 Oct 2026) ---
  vo   = the LM308 stage: v- through Zf = DISTORTION || C4 and the two
         ground legs R4+C5, R5+C6 (nodal, exact), the op-amp an integrator
         of 0.8 MHz gain-bandwidth (fit to the analysis's own response curve)
         slewing at 0.3 V/us, its output at +-3.5 V
  v    = the clipper node: C7 + R6 from vo, D1/D2 to ground, the FILTER
         network (FILTER + R7, C8, C9/R8) as its load; the diode law solved
         exactly (Wright omega, tabulated)
  g    = the JFET's gate: C9 into R8
  out  = HP 1.6 Hz (C10 into VOLUME) * LEVEL, MIX against the dry

RAT and TURBO differ only in the diodes: 1N914 (the SD-1's 1N4148 model) or
red LEDs (the LTspice LedRed model).

Page 1: LEVL TONE DRIV IN MIX, and MODE on the
sixth knob. TONE is FILTER on the RAT, turned round so that right is bright
in every mode.
"""
import math as _m

from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, Module, Param, Evidence, Level, YBase)

FS = 44100.0


def _q(v):
    """Q23, two's complement in 24 bits, saturated."""
    i = round(v * (1 << 23))
    i = max(-(1 << 23), min((1 << 23) - 1, i))
    return i & 0xFFFFFF


# =============================================================================
# MODE 1: the SD-1 -- the service notes' part values (v8: run at 1x)
# =============================================================================
# ---- parts (the service notes) --------------------------------------------
R1, C1, R2 = 10e3, 47e-9, 470e3
C2, R4 = 18e-9, 100e3
R5, VR1 = 33e3, 1e6                # DRIVE: VR1 "1MB" (linear) + R5
R6, C3 = 4.7e3, 47e-9
R7, C4 = 10e3, 18e-9
VR3, C5, R8 = 20e3, 27e-9, 470.0   # TONE: VR3 "20kW"
R9, C6 = 10e3, 10e-9
C7, R10, VR2 = 1e-6, 4.7e3, 10e3   # LEVEL: VR2 "10kB" (linear)
# ---- assumed (README "Assumptions") ----------------------------------------
IS, NID, VT = 2.52e-9, 1.752, 0.025852    # 1S2473 ~ 1N4148
N1 = NID * VT                             # D4: the negative side
N2 = 2 * N1                               # D5 + D6: the positive side
RAIL = 3.3                                # uPC4558 swing on 9 V, volts
MAKEUP = 2.0 ** 0.5                       # +3 dB after the LEVEL divider

K2 = 2.0 * FS                             # bilinear


def _bil1(b, a, k2=K2):
    """(b0 + b1 s)/(a0 + a1 s) -> (B0, B1, A1) normalised."""
    B0, B1 = b[0] + b[1] * k2, b[0] - b[1] * k2
    A0, A1 = a[0] + a[1] * k2, a[0] - a[1] * k2
    return B0 / A0, B1 / A0, A1 / A0


def _hp(tau, k2=K2):
    """HP s tau/(1 + s tau): y = c (x - x1) + p y1."""
    b0, b1, a1 = _bil1((0.0, tau), (1.0, tau), k2)
    return b0, -a1


def _lp(tau):
    """LP 1/(1 + s tau): y = l (x + x1) + p y1."""
    b0, b1, a1 = _bil1((1.0, 0.0), (1.0, tau))
    return b0, -a1


HP1 = _hp(R2 * C1)                  # 7.2 Hz, Q5's input coupling
HP2 = _hp(R4 * C2)                  # 88 Hz, into IC1a
HP3 = _hp(R6 * C3)                  # 720 Hz, the gain leg
LP6 = _lp(R9 * C6)                  # 1.59 kHz, IC1b's feedback pole
HP4 = _hp((R10 + VR2) * C7)         # 10.8 Hz, into LEVEL


def _tone_unnorm(t):
    R = VR3
    Ra, Rb = t * R, (1.0 - t) * R
    tau4, tau6 = R7 * C4, R9 * C6
    p0, p1 = R, C5 * (Ra * Rb + R * R8)
    num = (p0, p1 + p0 * tau6 + C5 * R9 * Ra, p1 * tau6)
    den = (p0, p1 + p0 * tau4 + R7 * C5 * Rb, p1 * tau4)

    def z(c):
        return (c[0] + c[1] * K2 + c[2] * K2 * K2,
                2 * c[0] - 2 * c[2] * K2 * K2,
                c[0] - c[1] * K2 + c[2] * K2 * K2)
    return z(num), z(den)


def _tone_poly():
    vals = [_tone_unnorm(t) for t in (0.0, 0.5, 1.0)]
    S = vals[1][1][0]
    out = []
    for which in (0, 1):
        for k in range(3):
            y0, yh, y1 = (v[which][k] / S for v in vals)
            p0 = y0
            p2 = 2 * y1 - 4 * yh + 2 * y0
            p1 = y1 - y0 - p2
            out.append((p0, p1, p2))
    return tuple(out)


TONE_POLY = _tone_poly()


def tone_taper(x):
    """VR3 is a 'W' taper (ASSUMED: an S curve flatter in the middle,
    slope 0.6 there, exact at both ends)."""
    d = x - 0.5
    return 0.5 + d * (0.6 + 1.6 * d * d)


HB = (0.30581255, -0.08048805)              # offsets +-1, +-3
_HBQ = [round(HB[0] * (1 << 23)), round(HB[1] * (1 << 23))]
_HBQ.append((1 << 21) - _HBQ[0] - _HBQ[1])  # offset +-5: the three sum to 1/4
HBQ = tuple(_HBQ)                            # Q23 ints, decimation taps


def _wf(U):
    w = U if U < 1.0 else _m.log(U)
    for _ in range(60):
        f = w + _m.exp(w) - U
        w -= f / (1.0 + _m.exp(w))
    return w


WF = tuple(_q(_wf(2.0 ** o * (1 + s / 16) - 8.0) / 16.0)
           for o in range(15) for s in range(16)) + (_q(_wf(2.0 ** 15 - 8.0) / 16.0),)
LN = tuple(_q(_m.log(0.5 + i / 128) / 16.0) for i in range(65))
EXP = tuple(_q(2.0 ** (-2 + i / 8) / 4.0) for i in range(33))

CONST = {
    "HP1C": HP1[0], "HP1P": HP1[1], "HP2C": HP2[0], "HP2P": HP2[1],
    "HP3C": HP3[0], "HP3P": HP3[1], "LP6L": LP6[0], "LP6P": LP6[1],
    "HP4C": HP4[0], "HP4P": HP4[1], "HP4H": HP4[0] / 2, "HP4Q": 1.0 - HP4[1],
    "RAIL": RAIL / 4.0,
    "R5S": R5 / 2.0 ** 20, "V1S": VR1 / 2.0 ** 20,
    "KG2": 128.0 / (R6 * N2),
    "KK": 2.0 ** 20 * IS / N2,
    "K0": (_m.log(IS / N2) + 20 * _m.log(2.0)) / 16.0,
    "LN2": _m.log(2.0), "LN2_16": _m.log(2.0) / 16.0,
    "A2": 4.0 * N2, "A1": 4.0 * N1,
    "STRETCH": 1.0 / 127.0,
    "LVL8": 4.0 * VR2 / (R10 + VR2) * MAKEUP / 8.0,
    "TAPA": 0.3, "TAPB": 0.8,
}
for _n, (_p0, _p1, _p2) in zip(("B0", "B1", "B2", "A0", "A1", "A2"), TONE_POLY):
    CONST[f"T{_n}P0"], CONST[f"T{_n}P1"], CONST[f"T{_n}P2"] = _p0 / 8, _p1 / 8, _p2 / 8
CONST["HBI1"], CONST["HBI3"], CONST["HBI5"] = (2 * v / (1 << 23) for v in HBQ)
CONST["HBD1"], CONST["HBD3"], CONST["HBD5"] = (v / (1 << 23) for v in HBQ)


# =============================================================================
# MODES 1 and 2: the Pro Co RAT (ElectroSmash's parts list)
# =============================================================================
class RAT:
    """The RAT's parts; the module's own names, so they cannot collide with
    the SD-1's R1..R10 above."""
    R1, C1, R2 = 1e6, 22e-9, 1e6          # input pull-down, coupling, bias
    R3, C2 = 1e3, 1e-9                    # 159 kHz: left out (README)
    R4, C5 = 47.0, 2.2e-6                 # the gain legs to ground
    R5, C6 = 560.0, 4.7e-6
    C4 = 100e-12                          # across DISTORTION
    RDIST = 100e3                         # DISTORTION, 100k-A
    C7, R6 = 4.7e-6, 1e3                  # into the diodes
    RTONE, R7, C8 = 100e3, 1.5e3, 3.3e-9  # FILTER, 100k-A
    C9, R8 = 22e-9, 1e6                   # into the JFET's gate
    C10, RVOL = 1e-6, 100e3               # out, VOLUME 100k-A
    # ---- assumed / fitted (README "Assumptions") ---------------------------
    FT = 0.8e6        # LM308 gain-bandwidth with C3 = 30 pF: the fit to the
                      # analysis's response curve (64 dB peak near 700 Hz)
    SR = 0.3e6        # slew rate, V/s (the analysis, from the datasheet)
    VSAT = 3.5        # output swing around the 4.5 V bias (datasheet: 1 V
                      # short of each rail, typical)
    THETA_C = 0.3     # the op-amp integrator: trapezoidal, damped only
                      # where its own pole is stiff (README)


RFS = FS                                  # the RAT core runs at 1x (it ran at 2x until
                                          # 15 Oct 2026: README "On the unit", the cost)
RT = 1.0 / RFS
RK = 2.0 * RFS

# diodes: (Is, n) -- 1N914 as the SD-1's 1N4148/1S2473; red LED: LTspice LedRed
DIODE = {1: (2.52e-9, 1.752), 2: (93.2e-12, 3.73)}

# ---- the op-amp stage, companion form at 1x ---------------------------------
RC4 = RT / (2 * RAT.C4)                   # 56.7 k
RC5 = RT / (2 * RAT.C5)
RC6 = RT / (2 * RAT.C6)
G4 = 1 / (RAT.R4 + RC5)
G5 = 1 / (RAT.R5 + RC6)
GG = G4 + G5
LAM = G4 / GG                             # Hn = LAM vh5 + (1 - LAM) vh6
K5 = 2 * RC5 * G4                         # vh5 += K5 (v- - vh5)
K6 = 2 * RC6 * G5
W = 2 * _m.pi * RAT.FT * RT               # the integrator per sample
SRT = RAT.SR * RT                         # the slew per sample, volts
# ---- the clipper node ---------------------------------------------------------
RC7 = RT / (2 * RAT.C7)
R6P = RAT.R6 + RC7
K7 = 2 * RC7 / R6P
RC8 = RT / (2 * RAT.C8)
RC9 = RT / (2 * RAT.C9)
R89 = RAT.R8 + RC9
G8X = 1 / RC8 + 1 / R89
K9 = 2 * RC9 / R89
GR8 = RAT.R8 / R89                        # the gate: g = GR8 (vX - vh9)


def taperA(x):
    """A 100k-A pot: 10 % of its track at the middle (an exponential law
    through 0, 0.1 and 1)."""
    return (81.0 ** x - 1.0) / 80.0


TAPER = tuple(_q(min(taperA(i / 32), 1.0)) for i in range(33))


def rat_omega(U):
    """omega(U): w + ln w = U."""
    if U > 1.0:
        w = U - _m.log(U)
    else:
        w = _m.exp(U)
    for _ in range(60):
        f = w + _m.log(w) - U
        w2 = w - f * w / (w + 1.0)
        if w2 <= 0:
            w2 = w / 2
        if abs(w2 - w) < 1e-16 * max(1.0, w):
            return w2
        w = w2
    return w


# OM[o*16 + s] = omega(U)/128 at U + 12 = 2^o (1 + s/16), o = 0..6, s = 0..15
OM = tuple(_q(rat_omega(2.0 ** o * (1 + s / 16) - 12.0) / 128.0)
           for o in range(7) for s in range(16)) + (_q(rat_omega(128.0 - 12.0) / 128.0),)


def mode_consts(mode):
    """The six per-mode words: KX = 1/(32 N), 8N, (ln k0 + 12)/256, k0/256,
    NK0 = Is R6'/8, the make-up. k0 = Is R6'/N (k = k0 rho)."""
    Is, n = DIODE[mode]
    N = n * VT
    k0 = Is * R6P / N
    return (1 / (32 * N), 8 * N, (_m.log(k0) + 12) / 256, k0 / 256, Is * R6P / 8,
            MAKEUP_RAT[mode])


# The make-up after LEVEL: the modes meet the SD-1's loudness at the default
# knobs (an acid line, LEVEL/DRIVE/TONE 64; README "Level").
MAKEUP_RAT = {1: 0.51, 2: 0.20}

MK = tuple(_q(v) for v in mode_consts(1) + mode_consts(2))

RHP1 = _hp(RAT.R2 * RAT.C1)               # 7.2 Hz, at 1x (48-bit state)
RHPO = _hp(RAT.C10 * RAT.RVOL)            # 1.6 Hz, at 1x

RCONST = {
    "RHPC": RHP1[0], "RHPQ": 1.0 - RHP1[1],
    "RHOH": RHPO[0] / 2, "RHOQ": 1.0 - RHPO[1],
    "RLAM": LAM, "RLAM1": 1.0 - LAM, "RK5": K5, "RK6": K6,
    # W ~ 114 and SRT ~ 6.8 V a sample at 1x: W/128 (an extra shift where it
    # is used), the slew compared at volts/8 (the step halved, then doubled)
    "RW128": W / 128, "RSRT8": SRT / 8, "RNSRT8": -SRT / 8,
    "RVSAT": RAT.VSAT / 4, "RNVSAT": -RAT.VSAT / 4,
    "RK7X2": 2 * K7, "RK9": K9, "RGR8": GR8,
    # per block: DRIVE (C4 left out: Zf = Rd, P = 1 + Rd Gg)
    "RPG": RAT.RDIST * GG / 4096,         # P/4096 = 1/4096 + RPG taper
    "RPW": 4096 / W / 128,                # P/W = 128 RPW (P/4096)
    "RTH0": 1 / (1 + RAT.THETA_C),        # theta = max(1/2, RTH0 - P/W)
    "RW4K": W / 4096,                     # (P + theta W)/4096
    # per block: FILTER
    "RTG0": 1 / 64 + RAT.R7 * G8X / 64, "RTGT": RAT.RTONE * G8X / 64,
    "RTC7": RAT.R7 / RC8 / 64, "RTCT": RAT.RTONE / RC8 / 64,
    "RT97": RAT.R7 / R89, "RT9T": RAT.RTONE / R89,
    "RRG": R6P * G8X / 2, "RSC8": R6P / RC8, "RSC9": R6P / R89,
}

# The SD-1's TONE polynomials as a table the decode loops over: B0 B1 B2 A1 A2 A0, each (P2, P1, P0), /8.
TP = tuple(_q(CONST[f"T{_n}P{_k}"]) for _n in ("B0", "B1", "B2", "A1", "A2", "A0")
           for _k in (2, 1, 0))

# ---- the P table -------------------------------------------------------------
WF_AT, LN_AT, EXP_AT = 0, len(WF), len(WF) + len(LN)
TAP_AT = EXP_AT + len(EXP)
TP_AT = TAP_AT + len(TAPER)
OM_AT = TP_AT + len(TP)
MK_AT = OM_AT + len(OM)
PTABLE = WF + LN + EXP + TAPER + TP + OM + MK

CONSTQ = {k: _q(v) for k, v in {**CONST, **RCONST}.items()}
CONSTQ.update(WF_AT=WF_AT, LN_AT=LN_AT, EXP_AT=EXP_AT, TAP_AT=TAP_AT, TP_AT=TP_AT, OM_AT=OM_AT,
              MK_AT=MK_AT, MK_AT6=MK_AT + 6, OMB=OM_AT + 7 * 16,
              OMB16=OM_AT + 7 * 16 - 16)   # OMB16: the RAT loop's lookup runs 16 high (the 2m form)

_P = Formatter.PLAIN
_B = Formatter.BIPOLAR
_BLANK = Param(b"", 0)

MODULE = Module(
    name="distorx",
    key="DISTORX",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="MaMarko", author_url="https://github.com/braikomarko-hub",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="MaMarko", date="2026-10-22",
        note="image DTXPR3 (BUILD 96, remix distorx, on 0x05), 22 Oct 2026: DISTORX on T1 for more than four "
             "minutes with four DISTORX at once on both cores (T1 and T2 kicks with DISTORX, T3 hats and T4 claps "
             "dry, T5 COMB FILTER + DISTORX, T6 COMB FILTER + DARK REV, T7 COMB FILTER + DISTORX, T8 MASTER), MODE"
             " changed while playing, OFF on re-selection, no clicks, by ear. Before, on 0x0a, image DTXPR1 (21 "
             "Oct): every knob in every MODE, FX1 and FX2, an LFO, a scene, save and reload. v10's loops and the "
             "move to id 0x1b (28 Oct) are not flashed"),),
    doc="SD-1 + RAT + Turbo RAT in one insert: MODE picks the pedal (OFF first), a 3 ms fade between them.",
    menu=MenuEntry(
        fx2_id=0x1b,                  # a free id (README "FX id"); stock SPATIALIZER keeps 0x05
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots
        abbr=b"DTX",
        fullname=b"DISTORX",
        build_tag=False,
    ),
    params=(
        Param(b"LEVL", 64, 128, active=True, formatter=_P,
              doc="output level; 64 matches the input's loudness at DRIV 64, in every MODE"),
        Param(b"TONE", 64, 128, active=True, formatter=_P,
              doc="SD-1 TONE or RAT FILTER: 0 dark to 127 bright, in every MODE"),
        Param(b"DRIV", 64, 128, active=True, formatter=_P,
              doc="SD-1 drive (18 to 47 dB) or RAT distortion (0 to 67 dB)"),
        Param(b"IN", 64, 128, active=True, formatter=_B,
              doc="how hard the track hits the pedal: -12 to +12 dB"),
        Param(b"MIX", 127, 128, active=True, formatter=_P,
              doc="dry/wet; 127 is the pedal alone, 0 is exact passthrough"),
        Param(b"MODE", 0, 4, active=True, formatter=Formatter.STEPPED,
              labels=("OFF", "SD-1", "RAT", "TURB"),
              doc="the pedal: OFF (nothing runs), SD-1 (BOSS), RAT (Pro Co), TURB (Turbo RAT)"),
        # ---- page 2: empty (v9: PAD removed, README "v9") --
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/distorx/distorx.asm",
        ptable=PTABLE,
        priority=18,
        bus_role=BusRole.NONE,        # an insert; never on the bus
        ybase=YBase.NEVER,            # no buffers, nothing in the shared window
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char=None, is_server=False),
    gates=(Gate("tools/verify/verify_distorx.py", remix_arg=False),),
    conflicts=(("SHATTER", "both are per-track dirt inserts (drive, clip): one in a remix"),),
    # MIX 126, not 127: v10's settled loop (MIX 127) is cheaper than the calm blend below it
    dear={"LEVL": 127, "TONE": 127, "DRIV": 127, "IN": 127, "MIX": 126, "MODE": 2},
)
