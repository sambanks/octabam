"""FET76 -- a per-track insert modelled on the UREI 1176LN FET limiting amplifier (1967).

Modelled from the 1176LN manual (block diagram, Figs. 3 and 5, specifications) and Universal Audio's
descriptions (modules/fet76/README.md):

  * the gain cell is the FET Q1, a voltage-variable resistor in the lower leg of a divider with R5 (27k):
    G = 1 / (1 + u), u the detector's voltage at the gate (triode region, Rds ~ 1/Vov);
  * FEEDBACK: the side chain reads the pre-amp's output, after the gain cell. The loop is closed inside
    the sample, linearised at the last gain (one division, no square root), stable at the 20 us attack;
  * the ratio buttons set the side chain's level S and the diode bias T: the loop's ratio is
    (1 + T + 2u)/(1 + u), so T is chosen for 4 / 8 / 12 / 20:1 averaged over the first 10 dB of gain
    reduction (a softer knee at 4:1, a harder one at 20:1); "ALL" = the four side-chain levels together
    (a lower threshold), the bias of a 16:1, the attack three times slower, more FET distortion;
  * CR2/CR3 rectify both halves (L and R linked, the larger of the two);
  * the attack (R55 25k into C27 0.022 uF, 20 .. 800 us) and the release (R56 5M + R57 270k from C22
    0.22 uF, 50 ms .. 1.1 s): two capacitors, so the release follows the program -- a short peak only fills
    C27 and lets go in ~10 ms, held compression fills C22 and lets go at the knob's time;
  * the FET's square-law residue (the "LN" network cancels most of it): an even harmonic that grows with
    gain reduction; REV BLUE = the earlier units without LN;
  * the class-A output stage: 0.5 % THD at full scale (+22 dBm), then 0 dBFS;
  * ATK 0 = the attack pot's OFF click: no gain reduction, the amplifier still there.
INPT has no threshold of its own (the 1176's is fixed): it drives the signal into it.
"""
import math as _m

from remix.schema import (BusRole, Category, DspSection, Evidence, Formatter, Gate, Harness, Kind, Level,
                          MenuEntry, Module, Param, YBase)

FS = 44100.0


def _q(v):
    i = round(v * (1 << 23))
    i = max(-(1 << 23), min((1 << 23) - 1, i))
    return i & 0xFFFFFF


# ---- the 1176LN (manual) -------------------------------------------------------------------------------------
CA, CB = 0.022e-6, 0.22e-6                   # C27, C22
RX = 220e3                                   # ASSUMED: the coupling of the two capacitors
ATK_FAST, ATK_SLOW = 20e-6, 800e-6           # attack 20 .. 800 us
REL_FAST, REL_SLOW = 0.050, 1.1              # release 50 ms .. 1.1 s
E_MAX = 6.0                                  # ASSUMED: the side chain's swing (gain reduction up to ~17 dB)
ABI_ATK_STEPS = 37                           # attack x3 in ALL: 126 ln 3 / ln 40 knob steps on the log taper
EPS = (0.06, 0.35, 0.48, 0.5)                # ASSUMED FET residue: LN, BLUE, LN+ALL, BLUE+ALL (capped)
D_SCALE = 0.5
KNOB_DB = 30.0 / 63.5                        # INPT / OUTP: dB per knob step, 64 = 0 dB


def _t_for(ratio):                           # T so the first 10 dB of GR average `ratio`:1
    return 2.162 / (10 ** (10.0 / (ratio - 1) / 20) - 1)


BUTTONS = ((_t_for(4), -20.0), (_t_for(8), -17.0), (_t_for(12), -15.0), (_t_for(20), -13.0))   # T, thr dBFS peak
_S = [T / 10 ** (thr / 20) for T, thr in BUTTONS]
ROWS = [(T, S) for (T, _), S in zip(BUTTONS, _S)] + [(_t_for(16), sum(_S))]                 # + ALL
RATIO_LABELS = ("4:1", "8:1", "12:1", "20:1", "ALL")


def attack_tau(atk):
    return ATK_SLOW * (ATK_FAST / ATK_SLOW) ** ((max(atk, 1) - 1) / 126.0)


def release_tau(rel):
    return REL_SLOW * (REL_FAST / REL_SLOW) ** (rel / 127.0)


def ka_of(atk):
    return 1 - _m.exp(-1 / (FS * attack_tau(atk)))


def kr_of(rel):
    rr = release_tau(rel) / (CA + CB)
    return 1 - _m.exp(-1 / (FS * rr * CB))


# ---- the P table -------------------------------------------------------------------------------------------
EXP = tuple(_q(2.0 ** (i / 32) / 2) for i in range(33))                 # 2^(i/32)/2, the last held at 1.0
KA = tuple(_q(ka_of(max(4 * i, 1))) for i in range(33))                 # every 4th ATK, interpolated
KR = tuple(_q(kr_of(min(4 * i, 127) if i < 32 else 128)) for i in range(33))
BTN = []
for T, S in ROWS:
    abi = 1 if (T, S) == ROWS[-1] else 0
    BTN += [_q((T / S) / 32),                # YT: the threshold amplitude, /32 (the gain cell's headroom)
            _q(1 / (4 * S)),                 # IS4: the charge test's 1/(4S)
            _q(S / 512),                     # SW: w/16384 = ka A32 G0^2 S/512
            _q(T / 64),                      # T64
            (ABI_ATK_STEPS << 16) if abi else 0,
            abi, 0, 0]
EPSQ = tuple(_q(e) for e in EPS)
EXP_AT, KA_AT, KR_AT, BTN_AT = 0, 33, 66, 99
EPS_AT = BTN_AT + len(BTN)
PTABLE = EXP + KA + KR + tuple(BTN) + EPSQ

CONST = {
    "GK": 128 * KNOB_DB / (20 * _m.log10(2.0)) / 32,      # gain bits / 32 per (w - 1/2)
    "GINOFF": -5.0 / 32,                                  # INPT: the signal /32 into the gain cell
    "GOUTOFF": 5.0 / 32,                                  # OUTP: x32 back out
    "KXA": 1 - _m.exp(-1 / (FS * RX * CA)),
    "KXB": 1 - _m.exp(-1 / (FS * RX * CB)),
    "KDC": 1 - _m.exp(-2 * _m.pi * 8.0 / FS),             # the residue's coupling: 8 Hz
    "EMAX8": E_MAX / 8,
    "C002": 0.02,
}
CONSTQ = {k: _q(v) for k, v in CONST.items()}
CONSTQ.update(EXP_AT=EXP_AT, KA_AT=KA_AT, KR_AT=KR_AT, BTN_AT=BTN_AT, EPS_AT=EPS_AT)

_P = Formatter.PLAIN
_B = Formatter.BIPOLAR

MODULE = Module(
    name="fet76",
    key="FET76",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="MaMarko", author_url="https://github.com/braikomarko-hub",
    evidence=(Evidence(Level.EMULATOR, ref="verify_fet76",
        note="code by Claude (Anthropic); bit-exact against its fixed-point model (verify_fet76, dsp_host); "
             "no unit record written yet"),),
    doc="Modelled on the UREI 1176LN FET limiter: feedback FET gain cell, 4/8/12/20:1 and ALL BUTTONS, "
        "20-800 us attack, program-dependent release, LN or BLUE.",
    menu=MenuEntry(
        fx2_id=0x1d,                  # preferred; the remix assigns the id (registry.assign_ids)
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots
        abbr=b"F76",
        fullname=b"FET76",
        build_tag=False,
    ),
    params=(
        Param(b"INPT", 64, 128, active=True, formatter=_B,
              doc="INPUT: -30 .. +30 dB into the fixed threshold (64 = 0 dB); more input, more limiting"),
        Param(b"OUTP", 64, 128, active=True, formatter=_B,
              doc="OUTPUT: -30 .. +30 dB (64 = 0 dB)"),
        Param(b"ATK", 100, 128, active=True, formatter=_P,
              doc="ATTACK: 1 = 800 us .. 127 = 20 us (the 1176's dial 1 .. 7); 0 = OFF, no limiting"),
        Param(b"REL", 64, 128, active=True, formatter=_P,
              doc="RELEASE: 0 = 1.1 s .. 127 = 50 ms, after held limiting; short peaks let go faster"),
        Param(b"RATI", 3, count=5, active=True, formatter=Formatter.STEPPED,
              labels=RATIO_LABELS,
              doc="the ratio buttons: 4:1, 8:1, 12:1, 20:1, ALL (all four in)"),
        Param(b"MIX", 127, 128, active=True, formatter=_P,
              doc="dry/wet: 127 = the 1176 alone, 0 = exact passthrough"),
        Param(b"REV", 0, count=2, active=True, formatter=Formatter.STEPPED,
              labels=("LN", "BLUE"),
              doc="LN = the low-noise units with the FET linearised; BLUE = the first ones, more 2nd harmonic"),
        Param(b"", 0), Param(b"", 0), Param(b"", 0), Param(b"", 0), Param(b"", 0),
    ),
    dsp=DspSection(
        asm="modules/fet76/fet76.asm",
        ptable=PTABLE,
        priority=28,
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char=None, is_server=False),
    gates=(Gate("tools/verify/verify_fet76.py", remix_arg=False),),
    dear={"INPT": 127, "OUTP": 127, "ATK": 127, "REL": 127, "RATI": 4, "MIX": 64, "REV": 1},
)
