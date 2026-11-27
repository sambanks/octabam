"""OCTA303 v6.9 (dEVILish) -- every constant and lookup table of the engine, computed in one place.

gen_tables.py writes these into modules/octa303/octa303.s; ref303.py imports them.
A table is derived here from a stated physical/design quantity, never typed by hand.
"""
import math

FS = 44100
CS = 16                     # control step: envelopes/cutoff/pitch every 16 samples (0.36 ms)
SHIFT_OUT = 6               # S20 -> s16 : >>5 is full scale, >>6 leaves 6 dB headroom

# ---------------------------------------------------------------- pitch
# frame word 0 (PTCH) = raw<<8 + the LFO's fraction.  v6.4, Tim Hastie's tuning system: on a 303
# track the PTCH byte is SEMITONES (raw 64 = 0, one unit a semitone; stock: 5 units a semitone), the
# page clone limits TUNE to TUNE_LO..TUNE_HI = -24..+24 (raw 40..88: four octaves, 0 in the middle;
# v6.5c, the author's choice over v6.4's -12..+24).
# p_abs (Q8 semitones) = P_CENTER + (word0 - 0x4000), clamped to P_LO..P_HI (p_abs = 16384 -> BASE note)
P_CENTER = 64 * 256
TUNE_LO, TUNE_HI = -24, 24
P_LO, P_HI = P_CENTER - 36 * 256, P_CENTER + 36 * 256      # the knob's range plus an octave of LFO
BASE_HZ = 130.81278          # C3: PTCH 0 plays C3 (the author's choice: his sound centred, keys aligned)
F_LOW = BASE_HZ * 2 ** (-64 / 12)
INC_TAB = [round(F_LOW * 2 ** (i / 768) / FS * 2 ** 32) for i in range(768)]   # one octave, 1/64 semitone

def q15(x): return int(round(x * 32768))
def q30(x): return int(round(x * (1 << 30)))
def onepole(tau_s, n=CS): return 1.0 - math.exp(-n / (FS * tau_s))
def onepole_hz(hz, n=1): return 1.0 - math.exp(-2 * math.pi * hz * n / FS)

ONE30 = (1 << 30) - 1

# ---------------------------------------------------------------- v6.5: the 303's own gate
# With the track's AMP HOLD at INF (127, locks applied) OCTA303 gates itself as the 303 does: a note
# sounds for half a step, and stays on into the next step when that step holds a trigless trig or a
# trigless lock (a slide).  Any other HOLD: the AMP decides, v6.4 sample for sample.
GATE_HOLD_INF = 127
GATE_K = q15(onepole(0.003))            # the gate's edges, 3 ms (no click), at the control rate
GATE_IDLE = 2048                        # frames (0.74 s) without a step/tick change = the sequencer stopped
GATE_TPS0 = 6                           # ticks a step before one has been measured (1x)
# v7.4 (Discord, 2 Nov 2026: with GATE 303 the first trig after PLAY is silent).  Measured under the port (1.40C, MKI,
# 120 BPM, 3 Nov 2026): the STOP there wrote the transport word 0x800065b8 = 0 and the step word 0 (STEM_REC.md: 0 =
# stopped and rewound, 2 = stopped by the STOP key with the position kept; the gate takes anything but 1 as stopped,
# v7.5 also the first move a fresh state sees, the first PLAY after boot); PLAY writes the step word
# and tick 0, transport 1, and the first tick (1) one frame later, on every PLAY.  The gate measured that frame as a
# tick and shut the first note ~1.5 ms after it began.  Now a STOP is the transport word, a move while stopped is no
# tick, and after a PLAY the first GATE_FSKIP intervals are skipped (the last tempo's frames a tick stand meanwhile).
GATE_FSKIP = 2

# ---------------------------------------------------------------- TB-303 engine
# v6.4: every 303 constant below checked against the Roland service notes' main-board schematic
SLIDE_TAU = 103.3e3 * 0.22e-6           # the slide RC: 103.3k (DAC + protection, Whittle p. 16) * C35 0.22 uF = 22.7 ms
TB_SLIDE = q15(onepole(SLIDE_TAU))      # 303 slide: ~68 ms to 95 % (v6.3: 21 ms, an inconsistency with DF_SLIDE's own RC)
# >>> CAL v6.7
# v6.9 (19 Oct 2026): the RESONANCE by its decay.  Din Sync measured at every saw reset: at full RES the real
# ring decays ~2.2 dB/ms from 400 Hz to 11 kHz, v6.8's 6-8 dB/ms above 1 kHz (RES 95 agreed).  New law
# k = LK*KMUL*KF - UD*KD (km0-5 on seven RES knots, kr0-4 the shape, ud0-5 dB/ms); the square's soft edges (sqlp,
# a one-pole lowpass: Din Sync's square is 3-9 dB under the saw's harmonics above 1.4 kHz).  Fitted, with the
# accent, the cutoff/env/decay laws and the levels, on Din Sync (bands, peaks, the ring's decay in 12 RES x
# frequency cells, the BRIGHTNESS -- spectral centroid -- of all 400 notes at 2..1000 ms) and tinyloops (the
# ring's frequency, the three drops' decay, the spectrum), under two rules: the ring never grows (no
# self-oscillation, -1.2 dB/ms or faster) and never decays faster as RES goes up.  v6.8 -> v6.9: ring cells
# 1.09 -> 0.16 (log2), brightness 0.30 -> 0.18 octave (square 0.28 -> 0.21), tinyloops drops -3.95/-7.8/-6.6
# -> -3.4/-3.1/-3.1 dB/ms (303: -3.4/-3.0/-3.1), its spectrum 6.1 -> 1.0 dB, bands 4.73 -> 4.68, peaks 2.30
# -> 2.29 dB; tinyloops' knobs come out at CUT 52 RES 112 ENV 111 ACC 125 (the photo: RES 85-90 %).  Level:
# v6.8's -2 dB at mid knobs (the accents are louder against the notes, as on Din Sync; ceiling -0.9 dBFS).
# v7.5 (3 Nov 2026): refitted with the circuit's layout and v7.3's accent stage (modules/octa303/README.md, v7.5);
# tinyloops' knobs come out at CUT 45 RES 106 ENV 116 (the edges of the photo's reading).  Keys no longer read:
# acc_dec (the accent decays as DECAY at 0), gc0-gc3 / gall (TB_GCOMP is one gain with the VCA pair), shi0-shi4
# (ENV MOD by ENV only); prehp 0 = no coupling high-pass (C17/R62's 0.72 Hz: a 3/32768 coefficient).
CAL = {
    'cut0':      176.565218,
    'cut1':      192.705942,
    'cut2':      355.32167,
    'cut3':      892.26029,
    'cut4':      1406.683938,
    'slo0':      0.815188,
    'slo1':      1.060223,
    'slo2':      1.579708,
    'slo3':      3.723475,
    'slo4':      5.228276,
    'shi0':      0.838333,
    'shi1':      0.675048,
    'shi2':      1.5677,
    'shi3':      3.46185,
    'shi4':      4.88259,
    'km0':       0.114461,
    'km1':       0.33979,
    'km2':       0.450509,
    'km3':       0.581631,
    'km4':       0.720628,
    'km5':       0.818979,
    'ud0':       0.553855,
    'ud1':       0.411605,
    'ud2':       0.436251,
    'ud3':       0.499047,
    'ud4':       0.608455,
    'ud5':       0.637572,
    'gc0':       0.853566,
    'gc1':       1.38368,
    'gc2':       1.72866,
    'gc3':       2.2254,
    'dec0':      0.156576,
    'dec1':      0.191704,
    'dec2':      0.617436,
    'dec3':      1.665996,
    'dec4':      2.459161,
    'acc0':      0.012298,
    'acc1':      0.512746,
    'acc2':      1.154899,
    'acc3':      1.858586,
    'kr0':       0.747688,
    'kr1':       0.957628,
    'kr2':       1.099306,
    'kr3':       1.150141,
    'kr4':       1.198502,
    'lg0':       0.568091,
    'lg1':       0.415718,
    'lg2':       0.495073,
    'lg3':       0.638123,
    'lg4':       1.728566,
    'swk0':      0.698501,
    'swk1':      0.349962,
    'swk2':      0.967627,
    'swk3':      1.0,
    'chk0':      1.0,
    'chk1':      1.0,
    'chk2':      1.03938,
    'chk3':      1.06649,
    'chk4':      1.0,
    'off_a':     0.004615,
    'off_b':     0.340864,
    'acc_dec':   0.130431,
    'meg_att':   0.000787,
    'ach0':      0.074035,
    'ach1':      0.015727,
    'dis':       0.155329,
    'swd':       0.177708,
    'swc':       0.531882,
    'sweep_st':  72.98452,
    'accvca_gain': 0.790284,
    'accvca_tau': 0.00136,
    'prehp':     0.0,
    'fbhp':      120.0,
    'dchp':      8.84257,
    'c1r':       2.3481,
    'ksq':       0.530941,
    'sq_c2':     0.539828,
    'veg_tau':   1.55926,
    'satk':      0.000197,
    'smax':      12531.6,
    'osat_db':   -1.164349,
    'sqlp':      6731.564995,
    'gall':      3.7383,
    'vpair':     1,
    'vgain':     2.538188,
    'env_flat':  1,
    'q8vlo':     4.49575,
    'q8sw':      5.635355,
    'q8beta':    265.609259,
    'ota_v':     5.752357,
    'p6v':       2.265,      # v7.8 (V8A): the pin-6 level at the centre of Din Sync's band (blocco 3, T8S strada a)
    'p6r':       1.46,       # v7.8: the positive side's limit / the negative side's (pin 6 toward +12 V; 1.31-1.61)
    'r122w':     0.16,       # v7.7 C2c: the RES wiper feeding R122 (VCA pair) follows an S track (logistic width)
    'r122rl':    50.0}       # ... loaded by ~50 kohm (R67 + Q18 || R99, R122); claude/OCTA303_blocco2_vca.md sec. 22-23
KNOT_RAW = (0, 32, 64, 95, 127)                 # 0/25/50/75/100 percent of the pots
def pchip(xs, ys, x):
    """Monotone piecewise-cubic Hermite (Fritsch-Carlson, scipy's PchipInterpolator rules)."""
    n = len(xs); h = [xs[i + 1] - xs[i] for i in range(n - 1)]; m = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    sg = lambda v: (v > 0) - (v < 0)
    dd = [0.0] * n
    for k in range(1, n - 1):
        if sg(m[k - 1]) * sg(m[k]) <= 0: dd[k] = 0.0
        else:
            w1 = 2 * h[k] + h[k - 1]; w2 = h[k] + 2 * h[k - 1]
            dd[k] = (w1 + w2) / (w1 / m[k - 1] + w2 / m[k])
    def edge(h0, h1, m0, m1):
        e = ((2 * h0 + h1) * m0 - h0 * m1) / (h0 + h1)
        if sg(e) != sg(m0): return 0.0
        if sg(m0) != sg(m1) and abs(e) > abs(3 * m0): return 3 * m0
        return e
    dd[0] = edge(h[0], h[1], m[0], m[1]); dd[-1] = edge(h[-1], h[-2], m[-1], m[-2])
    k = max(0, min(n - 2, max(i for i in range(n - 1) if xs[i] <= x) if x >= xs[0] else 0))
    t = (x - xs[k]) / h[k]; t2 = t * t; t3 = t2 * t
    return ((2 * t3 - 3 * t2 + 1) * ys[k] + (t3 - 2 * t2 + t) * h[k] * dd[k] + (-2 * t3 + 3 * t2) * ys[k + 1] + (t3 - t2) * h[k] * dd[k + 1])
def _curve(vals): return [pchip(KNOT_RAW, vals, r) for r in range(128)]
TB_PREHP = q15(onepole_hz(CAL['prehp']))   # VCO->VCF coupling highpass (v6.5f: 44.5 Hz)
TB_FBHP = q15(onepole_hz(CAL['fbhp']))     # highpass inside the resonance loop (v6.5f: 150 Hz, Open303)
TB_DCHP = q15(onepole_hz(CAL['dchp']))     # output coupling (v6.5f: 24 Hz)
TB_MEG_ATT = q15(onepole(CAL['meg_att']))  # MEG attack (v6.5f: 3 ms)
TB_ACC_VCA = q15(onepole(CAL['accvca_tau']))   # accent VCA path (v6.5f: 47k * 0.033uF = 1.55 ms)
TB_MEG_ACC = q30(math.exp(-CS / (FS * CAL['acc_dec'] / math.log(10))))  # accent MEG decay (v6.5f: 0.2 s, Whittle; v7.4: replaced below)
_DEC = [math.exp(v) for v in _curve([math.log(CAL['dec%d' % i]) for i in range(5)])]   # -20 dB time by DECAY raw
DEC_T_MIN, DEC_T_MAX = _DEC[0], _DEC[127]
TB_MEG = [q30(math.exp(-CS / (FS * t / math.log(10)))) for t in _DEC]
TB_DIS = q15(onepole(CAL['dis']))          # accent-sweep capacitor discharge (v6.5f: 0.2 s)
TB_ACH = [q15(onepole((CAL['ach0'] + CAL['ach1'] * r / 127) * math.exp(v))) for r, v in enumerate(_curve([math.log(CAL['chk%d' % i]) for i in range(5)]))]   # charge: 47k + pot (2nd res gang), shaped
TB_SWDIRECT = [q15(min(0.999, CAL['swd']) * (1 - r / 127)) for r in range(128)]   # direct path, pot ACW (v6.5f: 100/147)
TB_SWCAP = [q15(min(0.999, max(0.0, CAL['swc'] * v))) for v in _curve([0.0] + [CAL['swk%d' % i] for i in range(4)])]   # the 2nd RES gang's law
TB_SWEEP_ST = int(round(CAL['sweep_st'] * 256))                 # full accent sweep, Q8 semitones
TB_ACCVCA_GAIN = q15(min(0.999, CAL['accvca_gain']))   # accent VCA boost (v6.5f: 0.85)

# cutoff domain: s (Q8 semitones) above FC0 = 20 Hz; tables are 1/4 semitone
FC0 = 20.0
def s_of_hz(hz): return 12 * math.log2(hz / FC0) * 256
S_MAX = int(s_of_hz(CAL['smax'])) // 64 * 64       # v6.7: the ladder's top, from the fit (v6.6: 108 * 256, ~10.2 kHz)
TB_CUT = [int(round(s_of_hz(max(math.exp(v), 21.0)))) for v in _curve([math.log(CAL['cut%d' % i]) for i in range(5)])]
TB_OFF = [q15(CAL['off_a'] * r / 127 + CAL['off_b']) for r in range(128)]
TB_SLO = [int(round(max(v, 0.0) * 3072)) for v in _curve([CAL['slo%d' % i] for i in range(5)])]   # env sweep, octaves*12*256
TB_SHI = [int(round(max(v, 0.0) * 3072)) for v in _curve([CAL['shi%d' % i] for i in range(5)])]
# v6.9: the RES pot's law on seven knots (the 303's pot is steep at its top: 95 -> 127 takes the ring from
# ~13 to ~2 dB/ms on Din Sync), as a fraction of the ladder's true oscillation point (KF holds KO / LK)
RES_KNOTS = (0, 32, 64, 80, 95, 110, 127)
def _rcurve(vals): return [pchip(RES_KNOTS, vals, r) for r in range(128)]
TB_KMUL = [q15(min(0.999, max(0.0, v))) for v in _rcurve([0.0] + [CAL['km%d' % i] for i in range(6)])]
# v6.9: the ring's own decay by RES, dB/ms (Q10), whatever the cutoff: the real 303 at full RES rings
# ~2.2 dB/ms from 400 Hz to 11 kHz (Din Sync), which no fraction of the oscillation point can give
TB_UD = [int(round(min(60.0, max(0.0, v)) * 1024)) for v in _rcurve([0.0] + [CAL['ud%d' % i] for i in range(6)])]
TB_GCOMP = [int(round(4096 * 1.3 * CAL['gall'] * math.exp(v))) for v in _curve([0.0] + [math.log(CAL['gc%d' % i]) for i in range(4)])]
ACC_AMT = [int(round(max(0.0, v) * 127 * 8454660)) for v in _curve([0.0] + [CAL['acc%d' % i] for i in range(4)])]   # Q30
TB_C1R = int(round(CAL['c1r'] * 4096))     # ladder: first stage = b * C1R (Q12); the schematic's smaller bottom cap
TB_KSQ = int(round(CAL['ksq'] * 32768))    # square level (v6.6: 27853); v7.6: unused (O3_K's slot kept)
TB_SQLP = q15(onepole_hz(CAL['sqlp']))   # v6.9: the square's soft edges (Din Sync: ~3-9 dB under the saw's harmonics above 1.4 kHz)
TB_SATK = q30(1.0 - math.exp(-CS / (FS * CAL['satk'])))   # the 303's own attack on non-accented notes (DF_SATK[0])
VEG_TAU = CAL['veg_tau']                   # the VCA decay (DF_VEG at VDEC 64; v6.6: 1.23 s, Open303)
# v6.7: the resonance's strength (KF) and the level (LG) by cutoff frequency, Q12 by ladder index
FKN_HZ = (100.0, 300.0, 1000.0, 3000.0, 10000.0)
def _ixcurve(pre):
    xs = [math.log2(f) for f in FKN_HZ]; ys = [math.log(CAL[pre + '%d' % i]) for i in range(5)]
    out = []
    for i in range(S_MAX // 64 + 1):
        x = min(max(math.log2(FC0 * 2.0 ** (i * 64 / 3072.0)), xs[0]), xs[-1])
        out.append(int(round(4096 * math.exp(pchip(xs, ys, x)))))
    return out
LG = _ixcurve('lg')

# ---------------------------------------------------------------- v6.9: the resonance by its decay
# The ladder of ref303.sample, small signal (5 states: y1..y4 and the loop highpass), solved per ladder
# index: KO = the feedback at which its resonant mode neither grows nor decays, KD = the feedback taken
# off that point for each dB/ms of decay.  k = LK * KMUL * KF - UD * KD, KF = KO / LK * the shape kr(f).
def _lin_M(b, c1, k, fbhp):
    import numpy as np
    A = np.zeros((5, 5))
    for col in range(5):
        y1, y2, y3, y4, fb = [1.0 if j == col else 0.0 for j in range(5)]
        fb = fb + fbhp * (y4 - fb); y0 = -k * (y4 - fb)
        y1 = y1 + c1 * (y0 - y1 + y2); y2 = y2 + b * (y1 - 2 * y2 + y3)
        y3 = y3 + b * (y2 - 2 * y3 + y4); y4 = y4 + b * (y3 - 2 * y4)
        A[:, col] = [y1, y2, y3, y4, fb]
    return A
def _lin_decay(b, c1, k, fbhp):                     # dB/ms of the slowest resonant (complex) mode
    import numpy as np
    ev = np.linalg.eigvals(_lin_M(b, c1, k, fbhp)); ev = ev[np.abs(np.angle(ev)) > 2 * math.pi * 15 / FS]
    return 20 * math.log10(max(abs(ev))) * FS / 1000 if len(ev) else -999.0
def _lin_k(b, c1, fbhp, target):
    lo, hi = 0.0, 1.0
    while _lin_decay(b, c1, hi, fbhp) < target: hi *= 1.5
    for _ in range(50):
        m = (lo + hi) / 2
        if _lin_decay(b, c1, m, fbhp) < target: lo = m
        else: hi = m
    return (lo + hi) / 2
def resonance_tables(LB):
    fbhp = TB_FBHP / 32768.0; KO, KD = [], []
    for i in range(S_MAX // 64 + 1):
        b = LB[i] / 32768.0; c1 = b * TB_C1R / 4096.0
        ko = _lin_k(b, c1, fbhp, 0.0); KO.append(ko); KD.append(ko - _lin_k(b, c1, fbhp, -1.0))
    return KO, KD
def _ladder_cache():
    import json, os
    p = os.path.join(os.path.dirname(os.path.abspath(globals().get('__file__', 'o3tables.py'))), 'ladder_cache.json')
    if os.path.exists(p): d = json.load(open(p))
    else: d = {}; d['B'], d['K'] = ladder_tables()
    if d.get('res_key') != [TB_C1R, TB_FBHP, S_MAX]:
        d['KO'], d['KD'] = resonance_tables(d['B']); d['res_key'] = [TB_C1R, TB_FBHP, S_MAX]
    return d

# the square's duty (high part) moves with the pitch (Whittle: 45 % high .. 71 % low): sq_c2 at C2, -3.5 % an octave
# v7.6: SQ_TH (the square's duty by pitch, sq_c2) and TB_KSQ's use are gone: Q8's circuit gives both (o3q8.py)
# v6.8: the 303's output stage saturates softly: on Din Sync every accented note peaks at ~0.35-0.39 of full
# scale whatever the knobs (A5, D1, E1, E5), the normal notes below.  Out = OSAT_OUT * softclip(OSAT_IN * y):
# unity for small signals, a soft ceiling of osat_db dBFS (softclip's top, 988783 in S20, reached at sqrt2).
SOFTCLIP_TOP = 988783
# v7.7: with the pin-6 ceiling (P6_ON) this digital stage is gone from octa303.s; OSAT_* are still emitted as constants
# (unused) and kept for builds without p6v. DRIV is now VR8 into the output mixer: DRV_* below.
DRV_CEIL_DB = -0.80
_OSAT_DB = DRV_CEIL_DB if CAL.get('p6v', 0.0) > 0 else CAL['osat_db']
OSAT_OUT = int(round(10 ** (_OSAT_DB / 20.0) * 32767 * 64 * 512 / (SOFTCLIP_TOP >> 6)))   # fm(.., 6, 9)
OSAT_IN = int(round(2 ** 25 / OSAT_OUT))                                                    # fm(.., 2, 8)
OSAT_LIM = 4 * ((2 ** 31 - 1) // OSAT_IN) - 4                                               # (y >> 2) * IN fits 32 bits
# v6.9 (v7.3: see below for today's form): the VCA's multiply must fit 32 bits; the loudest amp is the full VCA envelope plus the
# accent path at ACC 127.  The ladder's output is held under VCA_LIM before it (reached only by dEVILish's
# self-oscillating modes or OVDR far up; the 303 alone peaks ~0.9 of it): a clip there, never a wrap.
# v7.3: with SETUP's ACCV (v7.0) the accent path's gain goes to (TB_ACCVCA_GAIN * 127) >> 6, twice the 303's:
# v7.0-v7.1 sized AMP_MAX with the 303's gain only, so ACCV > 64 on an open accented note could wrap the VCA
# multiply (found while checking #1011: CUT 80 RES 0 ENV 127 ACC 127 ACCV 127).
# ---------------------------------------------------------------- v7.4: the 303's circuit (claude/TB303_circuito_fonti.md)
# The Roland service notes' main board (= the x0xb0x netlist): the VCA input pair R121 220k / C21 10 nF (72 Hz) and
# R122 100k / C22 10 nF (156 Hz) from the RES wiper; ENV MOD's depth by ENV only; the accent's decay as DECAY at 0.
# v7.5: the accent stage is v7.3's (TB_ACH / TB_DIS / TB_SWDIRECT / TB_SWCAP / ACC_AMT / TB_ACC_VCA, fitted again
# with the rest on Din Sync + tinyloops).  v7.4's network solved from the schematic (D24 / R46 / VR4b / C13 / R72)
# fitted Din Sync but not tinyloops' accents in a row, and with tinyloops in its fit it lost the lines (fit G).
# ---------------------------------------------------------------- v7.6: Q8, the square (claude/OCTA303_v76_Q8_studio.md)
# The square shaper solved as its circuit (o3q8.py) at each semitone; the saw's swing (q8vlo .. q8vlo + q8sw volts)
# and Q8's hFE fitted (Din Sync + tinyloops).  Cached: ~1 s a semitone in Python.
def _q8_tables():
    import json, os, hashlib, tempfile, o3q8
    here = os.path.dirname(os.path.abspath(globals().get('__file__', 'o3tables.py')))
    src = hashlib.sha256(open(os.path.join(here, 'o3q8.py'), 'rb').read()).hexdigest()   # the generator itself
    key = [F_LOW, CAL['q8vlo'], CAL['q8vlo'] + CAL['q8sw'], CAL['q8beta'], o3q8.NPT, Q8_LO, Q8_HI, src]
    p = os.path.join(here, 'q8_cache.json')
    try:
        d = json.load(open(p))
        if d.get('key') == key: return d['SQC'], d['SQK']
    except (OSError, ValueError):
        pass                                                        # missing or half-written: rebuild (~70 s)
    SQC, SQK = o3q8.tables(F_LOW, key[1], key[2], key[3], Q8_LO, Q8_HI)
    fd, tmp = tempfile.mkstemp(dir=here, suffix='.tmp')
    with os.fdopen(fd, 'w') as f: json.dump({'key': key, 'SQC': SQC, 'SQK': SQK}, f)
    os.replace(tmp, p)                                              # atomic: parallel builds never read half a file
    return SQC, SQK
Q8_LO, Q8_HI = P_LO >> 8, P_HI >> 8                                 # every semitone the pitch can reach
SQC, SQK = _q8_tables()                                             # SQC[semitone][128] Q15, SQK[semitone] Q15
SQC_FLAT = [v for row in SQC for v in row]
# v7.6: the VCA's OTA (IC15 BA6110): OTA_V * softclip(o / OTA_V), OTA_V = 10^ota_v in the ladder's units
OTA_V = 10 ** CAL['ota_v']
OTA_IN = int(round(2 ** 32 / OTA_V))                                # u = (o >> 4) * OTA_IN >> 8 = o * 2^20 / OTA_V
OTA_OUT = int(round(OTA_V / 2 ** 20 * 32768))                       # back: (y >> 4) * OTA_OUT >> 11
OTA_LIM = int(1.4142 * OTA_V)                                       # softclip's clamp, so the product fits 32 bits
SQL_DLIM = 1800000                                                  # the square's edge lowpass step: (d >> 4) * TB_SQLP < 2^31
VCA_PAIR = int(CAL.get('vpair', 1))
VP_HP1 = q15(onepole_hz(1 / (2 * math.pi * 222.2e3 * 0.01e-6))) if VCA_PAIR else 0
VP_HP2 = q15(onepole_hz(1 / (2 * math.pi * 102.2e3 * 0.01e-6))) if VCA_PAIR else 0
def _smap(x, w):                    # v7.7 (C2c): normalised logistic S track of width w (taccuino 3.C); w 0 = linear (B)
    if w <= 0: return x
    lo, hi = 1 / (1 + math.exp(0.5 / w)), 1 / (1 + math.exp(-0.5 / w))
    return (1 / (1 + math.exp(-(x - 0.5) / w)) - lo) / (hi - lo)
def _r122(r):                        # the R122 branch's wiper ratio: S track, 50k pot, wiper loaded by r122rl kohm (twin sim.c)
    ra = _smap(r / 127.0, CAL.get('r122w', 0.0)); RL = CAL.get('r122rl', 0.0)
    if RL > 0:
        Rb = ra * 50.0; Rp = Rb * RL / (Rb + RL + 1e-12); ra = Rp / ((1 - ra) * 50.0 + Rp + 1e-12)
    return ra
VP_W2 = [int(round(2.2 * _r122(r) * 4096)) if VCA_PAIR else 0 for r in range(128)]
TB_MEG_ACC = TB_MEG[0]                                              # v7.4: an accent decays as DECAY at 0 (IC12 shorts the pot)
# ---------------------------------------------------------------- v7.8 (V8A): the MEG and the accent from the circuit
# claude/OCTA303_blocco3_accento.md (V8A passes from C2c and C2c': no number fitted).  Three pieces, all at the control
# rate (CS samples):
# (1) MEG: C62 discharging through R138 (+ VR6) into the diodes D28/D29/D26 (o3meg.py): a factor per frame by DECAY and
#     by level, MEG_T (NROW rows x NLEV levels, Q30).  Accents (and DECAY 0) take row 0.  v7.9: accents read ADEC_T
#     (below), whose row for ADEC 50 is MEG_T's row 0; dEVILish's ADEC moves along it with no jump.
# (2) the accent's push to the filter (VR7 -> D24 -> R46 -> VR4B -> C13, VR4B's wiper -> R72 -> N134) and (3) its
#     current into the VCA (VR7 -> R119 -> C36 -> R120 -> D27 -> pin 1 of the BA662A, a junction): the twin's a2_step
#     (backward Euler on C13 and C36, 2 sub-steps a frame) solved in closed form: D24 is one diode in series with
#     R24 = Re(ACC) + RA(RES); C36's step and D27 together are one diode in series with R27 = R120 + 1/G.  A diode in
#     series with R: y = i R from AC_F[V'] (R0, 32.8 mV steps), V' = V + nVT ln(R / R0) (linear in R: R24 spans
#     80-107k).  Voltages in uV, y in uV.  VR7 and VR4B on the S track of VR4A (C2c, width 0.16).
def _meg_tables():
    import json, os, hashlib, tempfile, o3meg
    here = os.path.dirname(os.path.abspath(globals().get('__file__', 'o3tables.py')))
    src = hashlib.sha256(open(os.path.join(here, 'o3meg.py'), 'rb').read()).hexdigest()
    t10 = [-CS * math.log(10) / (FS * math.log(f / 2.0 ** 30)) for f in TB_MEG]   # the model's -20 dB time by DECAY
    key = [hashlib.sha256(repr(TB_MEG).encode()).hexdigest(), CS, FS, src]
    p = os.path.join(here, 'meg_cache.json')
    try:
        d = json.load(open(p))
        if d.get('key') == key: return d['MEG_T'], d['is_scale'], d['vr6_scale']
    except (OSError, ValueError):
        pass                                                        # missing or half-written: rebuild (~2 min)
    Q, s_, kv, _ = o3meg.tables(t10)
    fd, tmp = tempfile.mkstemp(dir=here, suffix='.tmp')
    with os.fdopen(fd, 'w') as f: json.dump({'key': key, 'MEG_T': Q, 'is_scale': s_, 'vr6_scale': kv}, f)
    os.replace(tmp, p); os.chmod(p, 0o644)
    return Q, s_, kv
MEG_T, MEG_IS_SCALE, MEG_VR6_SCALE = _meg_tables()
MEG_NROW, MEG_NLEV, MEG_LPO = len(MEG_T), len(MEG_T[0]), 6
MEG_FLAT = [v for row in MEG_T for v in row]
assert MEG_NROW == 33 and MEG_NLEV == 64
assert all(abs(MEG_T[r + 1][j] - MEG_T[r][j]) * 3 < 2 ** 31 for r in range(32) for j in range(64))   # (diff * w) fits
# v7.9: dEVILish ADEC continuous (o3meg.adec_tables; claude/OCTA303_v79_tarature.md sec. 3).  ADEC_T has MEG_T's format;
# ADEC a reads row position a + 2 (DF_ADEC); 0 (no dEVILish) means ADEC 50, the 303 = MEG_T's row 0, the same bits.
def _adec_tables():
    import json, os, hashlib, tempfile, o3meg
    here = os.path.dirname(os.path.abspath(globals().get('__file__', 'o3tables.py')))
    src = hashlib.sha256(open(os.path.join(here, 'o3meg.py'), 'rb').read()).hexdigest()
    key = [hashlib.sha256(repr(MEG_T).encode()).hexdigest(), MEG_IS_SCALE, src]
    p = os.path.join(here, 'adec_cache.json')
    try:
        d = json.load(open(p))
        if d.get('key') == key: return d['ADEC_T'], d['R']
    except (OSError, ValueError):
        pass                                                        # missing or half-written: rebuild (~3 min)
    Q, rs = o3meg.adec_tables(MEG_IS_SCALE, MEG_T[0])
    fd, tmp = tempfile.mkstemp(dir=here, suffix='.tmp')
    with os.fdopen(fd, 'w') as f: json.dump({'key': key, 'ADEC_T': Q, 'R': rs}, f)
    os.replace(tmp, p); os.chmod(p, 0o644)
    return Q, rs
ADEC_T, ADEC_R = _adec_tables()
ADEC_NROW, ADEC_Q50 = 34, 52
ADEC_FLAT = [v for row in ADEC_T for v in row]
assert len(ADEC_T) == ADEC_NROW and all(len(r) == MEG_NLEV for r in ADEC_T)
assert ADEC_T[ADEC_Q50 >> 2] == MEG_T[0]                            # ADEC 50 = the 303, bit for bit
assert all(abs(ADEC_T[r + 1][j] - ADEC_T[r][j]) * 3 < 2 ** 31 for r in range(ADEC_NROW - 1) for j in range(64))
AC_VT, AC_NVT, AC_IS = 0.02585, 1.752 * 0.02585, 2.52e-9            # 1N4148 SPICE (D24, D27): Is, n
AC_R46, AC_R72, AC_R119, AC_R120, AC_RV, AC_RON = 47e3, 100e3, 47e3, 22e3, 50e3, 200.0
AC_C13, AC_C36, AC_V134, AC_VPK, AC_IQ31 = 1e-6, 0.033e-6, 3.27, 9.99, 48e-6   # C13 rests at N134 3.27 V; MEG peak
AC_W = 0.16                                                         # VR7 and VR4B: VR4A's S track (C2c)
AC_DT = CS / FS / 2                                                 # two sub-steps a frame, as the twin (a2_sub 2)
def _acc_row(acc):
    a = _smap(acc / 127.0, AC_W) if acc else 0.0
    Rt = (1 - a) * AC_RV + AC_RON + 1.0; Rb = a * AC_RV + 1.0; kth = Rb / (Rt + Rb); Rth = Rt * Rb / (Rt + Rb)
    Re = 1 / (1 / Rth + 1 / AC_R119)
    return kth * Re / Rth, Re / AC_R119, Re
def _res_row(res):
    r = _smap(res / 127.0, AC_W)
    Rwc = (1 - r) * AC_RV + 1.0; Rp = Rwc * AC_R72 / (Rwc + AC_R72); k = AC_DT / (AC_C13 * (Rwc + AC_R72))
    return AC_R46 + r * AC_RV + 1.0 + Rp, Rp, AC_R72 / (Rwc + AC_R72), k / (1 + k)
AC_A1 = [int(round(_acc_row(a)[0] * AC_VPK * 1e6)) for a in range(128)]   # uV at the MEG's peak: Ve = A1 megs + A2 v34
AC_A2 = [q30(_acc_row(a)[1]) for a in range(128)]
AC_RE = [int(round(_acc_row(a)[2])) for a in range(128)]            # ohm
AC_RA = [int(round(_res_row(r)[0])) for r in range(128)]            # ohm: R46 + VR4B to the wiper + (the rest || R72)
AC_RP = [int(round(_res_row(r)[1])) for r in range(128)]            # ohm: (VR4B wiper to C13) || R72
AC_B1 = [q30(_res_row(r)[2]) for r in range(128)]                  # Q30: C13 seen at the wiper
AC_K2 = [q30(_res_row(r)[3]) for r in range(128)]                  # Q30: C13's backward-Euler step, k / (1 + k)
AC_G = AC_C36 / AC_DT + 1 / AC_R119                                 # C36's companion conductance with R119
AC_R27 = AC_R120 + 1 / AC_G
AC_AL, AC_BE = q30((AC_C36 / AC_DT) / AC_G), q30((1 / AC_R119) / AC_G)
AC_Q27G = q30((1 / AC_G) / AC_R27)                                  # i27 / G = y27 Q27G
AC_V134 = int(round(AC_V134 * 1e6))
AC_V69 = int(round(AC_VT * math.log(1 + AC_IQ31 / 1e-14) * 1e6))    # pin 1 at Q31's current alone (the rest: AC_L69)
AC_R72N = int(AC_R72)                                               # ohm, an integer for the engine
AC_R0 = 93000                                                       # AC_F's resistor
AC_KLN = int(round(AC_NVT * 1e6 / AC_R0 * 65536))                  # V' = V + ((R24 - R0) KLN >> 16) ~ nVT ln(R24 / R0)
AC_FN, AC_FSH = 400, 15                                             # AC_F: 400 points, 2^15 uV apart (to 13.1 V)
def _iser(v, R):                                                    # y = i R of a 1N4148 in series with R under v volts
    if v <= 0: return 0.0
    i = max(0.5 * v / R, 1e-12)
    for _ in range(60):
        f = i * R + AC_NVT * math.log(1 + i / AC_IS) - v; i2 = i - f / (R + AC_NVT / (AC_IS + i))
        if i2 <= 0: i2 = 0.1 * i
        if abs(i2 - i) < 1e-15: i = i2; break
        i = i2
    return i * R
AC_F = [int(round(_iser((j << AC_FSH) * 1e-6, AC_R0) * 1e6)) for j in range(AC_FN)]
AC_F27 = [int(round(_iser((j << AC_FSH) * 1e-6, AC_R27) * 1e6)) for j in range(AC_FN)]
AC_VMAX = ((AC_FN - 1) << AC_FSH) - 1                               # V' is clamped under the last point
AC_L69 = [int(round(AC_VT * math.log(1 + (j << 16) * 1e-6 / (AC_R27 * AC_IQ31)) * 1e6)) for j in range(129)]   # by y27
AC_KV = q30(16384 / (AC_R27 * AC_IQ31 * 1e6))                      # Q14 VCA level per uV of y27: (I_Q31 + I27) / I_Q31
AC_KSW = q30(2.2e3 / AC_R72 / (AC_VT * math.log(2)) * 3072 / 1e6)   # Q8 semitones per uV at the wiper (R72 into N134)
assert all(0 <= AC_F[j + 1] - AC_F[j] < 1 << 15 for j in range(AC_FN - 1)) and all(0 <= AC_F27[j + 1] - AC_F27[j] < 1 << 15 for j in range(AC_FN - 1))
AC_YMAX = AC_F27[-1]                                                # y27 at most (V27 clamped)
AMP_MAX = (ONE30 >> 16) + ((((AC_YMAX >> 1) * (AC_KV >> 1)) >> 28) * 127 >> 6) + 64   # the VCA's level: ACCV 127
if VCA_PAIR:                                                        # the level by RES comes from the pair: one gain
    TB_GCOMP = [int(round(4096 * CAL.get('vgain', 0.21)))] * 128
if CAL.get('env_flat', 0):                                          # v7.4: ENV MOD's depth does not depend on RES (VR4b
    TB_SHI = list(TB_SLO)                                           # goes only to the accent sweep)
# v7.3 (Zac Kyoti, sambanks/octabam#1011): the plain 303 did reach the old limit (RES near 0 with the filter open
# or accented: +3.4 dB over it, hard-clipped).  The VCA multiply is now (o >> 7) * (amp >> 1) >> 6: one bit off
# the ladder's output and one off the VCA level (Q14, ~-96 dB steps), four times the room; with AMP_MAX now
# counting ACCV, the 303 alone peaks ~-4 dB under it at any ACCV.
# v7.3: MUFF's lowpass input (o - mlo) is held under DF_MUFF_DLIM so ((o - mlo) >> 4) * DF_MUFF_LP fits 32 bits
# at the wider VCA (the review of #1011's fix: not reached in the model, ~54 % at most, but no longer guaranteed).
VCA_LIM = (((2 ** 31 - 1) // ((AMP_MAX >> 1) + 1)) << 7) - 128
# v7.7 (5 Nov 2026, claude/OCTA303_blocco2_vca.md sec. 10-17): the BA662A's output (pin 6) cannot leave the supply. Its
# voltage is the OTA current x 52.5 kohm (R127 + R129 || R128); a normal note fully driven (48 uA) = 2.52 V = 0.9428 OTA_V
# in the ladder's units. Above the limit p6v (volts) a knee then flat: o / (1 + (o/L)^4)^(1/4), as a 257-point table of
# r = |o| / L in 0..4 (64 steps per L) with linear interpolation. With it on, the digital output ceiling (OSAT) is off;
# SETUP's DRIV drives the output mixer after it (DRV_*).
P6_ON = CAL.get('p6v', 0.0) > 0
_P6_L = CAL.get('p6v', 0.0) / (48e-6 * 52.5e3) * (2 ** 0.5 - 2 ** 1.5 / 6) * OTA_V if P6_ON else 1.0
P6_K = int(round(2 ** 30 / _P6_L)) if P6_ON else 0                      # t = ((|o| >> 6) * P6_K) >> 2 = 64 r in Q16
P6_F = [int(round(_P6_L * (j / 64.0) / (1 + (j / 64.0) ** 4) ** 0.25)) for j in range(258)] if P6_ON else [0] * 258
P6_AMAX = 1 << 25                  # (v7.8: 2^25, the lower p6v) |o| is clamped here first: 64 r is then >= 256 (the flat end) and the multiply fits 32 bits
assert not P6_ON or ((P6_AMAX >> 6) * P6_K < 2 ** 31 and ((P6_AMAX >> 6) * P6_K >> 2) >> 16 >= 256)
assert all(P6_F[j + 1] >= P6_F[j] and P6_F[j + 1] - P6_F[j] < 1 << 15 for j in range(257))   # rising; (diff * frac) fits
# v7.8 (V8A): pin 6 is asymmetric (Din Sync caps the negative side): the positive side's limit is p6r x the negative's
_P6_LP = _P6_L * CAL.get('p6r', 1.0)
P6_KP = int(round(2 ** 30 / _P6_LP)) if P6_ON else 0
P6_FP = [int(round(_P6_LP * (j / 64.0) / (1 + (j / 64.0) ** 4) ** 0.25)) for j in range(258)] if P6_ON else [0] * 258
assert not P6_ON or ((P6_AMAX >> 6) * P6_KP >> 2) >> 16 >= 256
assert all(P6_FP[j + 1] >= P6_FP[j] and P6_FP[j + 1] - P6_FP[j] < 1 << 15 for j in range(257))
# ---------------------------------------------------------------- v7.3: the ladder's soft clip at the top
# Zac Kyoti, sambanks/octabam#1011: with CUT, RES and ENV high the resonance sweeps up through ~11 kHz, the
# cubic soft clip's 3rd harmonic (3 fs/4) folds back onto fs/4 exactly and the loop locks to a period-4
# cycle -- a fixed 11.025 kHz whistle for the first 25-45 ms of every note (measured in ref303: -2.7 dB of
# the note at CUT 127 RES 127 ENV 120).  The clip now works at a lower operating point near the top of the
# table: y0 = softclip(u * g) / g, g = 1 up to ladder index CL_I0 (~5 kHz; the clip is v7.1's below it)
# falling linearly to CL_GMIN at CL_I1 (~10 kHz) and above.  Small signals are unchanged (the clip's slope
# is 1 at 0, so the resonance law, KO/KD, is the same); only the loop's saturation eases where it folds.
# ACID mode only: dEVILish's WHST / SELF oscillate on purpose, the clip sets their level, and easing it there
# made them up to +4.6 dB louder at the top without curing their own fs/4 lock (left as it was, see the README).
# v8.3 (#1011): CL_GMIN 0.5 -> 0.3.  At 0.5 a 12-note accented run at CUT 110, RES/ENV/ACC 127, SAW R still
# locked one note in three TUNEs (ref303, 2,304-note grid: 3 locked notes); at 0.3: 0.  Not 0.25: the clip's
# output grows as 1/g and feeds the ladder's first multiply (l1); a random search with dEVILish OVDR/FM/MUFF
# up reached 0.72 of 2^31 there at 0.25, 0.62 at 0.3 (0.37 at 0.5).
CL_I0, CL_I1, CL_GMIN = 383, 431, 0.3
def _clg(i):
    if i <= CL_I0: return 4096
    if i >= CL_I1: return int(round(CL_GMIN * 4096))
    return int(round(4096 * (1.0 + (CL_GMIN - 1.0) * (i - CL_I0) / (CL_I1 - CL_I0))))
CL_G = [_clg(i) for i in range(CL_I0, S_MAX // 64 + 1)]            # Q12, by ladder index - CL_I0
CL_INV = [(4096 * 4096 + g // 2) // g for g in CL_G]               # Q12, 1/g
CL_LIM = [(1482910 * 4096) // g for g in CL_G]                     # softclip's clamp (+-sqrt2) before the * g
# <<< CAL v6.7


# ---------------------------------------------------------------- v7.0: the TB-303 machine's SETUP page
# Six slots: WAVE (SAW SQR SAW+D SQR+D: the carrier names' four voices), GATE (OFF: the AMP decides, as v6.9;
# 303: the 303's own gate, 3.5 of the step's 6 clocks -- Whittle's slide page -- and held through a slide),
# FINE (+-50 cents, 64 = 0), SLID (the slide RC as dEVILish's SLID, 0 = the 303), DRIV (the output stage
# past Din Sync's VR8: 0 = the recording .. +10 dB into the output mixer's saturation, DRV_*), ACCV (the accent's share on the VCA, 64 = the 303).
# SETUP_NEUTRAL: a new machine's SETUP (o3_mdefs); until v7.9 also what a TB303* sample's track played.
SETUP_NAMES = ('WAVE', 'GATE', 'FINE', 'SLID', 'DRIV', 'ACCV')
SETUP_NEUTRAL = (0, 0, 64, 0, 0, 64)
SETUP_COUNT = (8, 2, 128, 128, 128, 128)
# v7.9: WAVE's bit 2 = R, the factory preset (TM3 as Roland trims it, claude/OCTA303_v79_tarature.md sec. 4); labels
# of at most 5 characters (a 6-byte field with its NUL; no '.', the panel's font may lack it)
WAVE_LABELS = ('SAW', 'SQR', 'SAW+D', 'SQR+D', 'RSAW', 'RSQR', 'RSAWD', 'RSQRD')
assert len(WAVE_LABELS) == SETUP_COUNT[0] and all(len(l) <= 5 and l.isascii() and l.isupper() for l in WAVE_LABELS)
# v7.9: R, the factory preset: TM3 into N134 through R73 adds the same octaves at every CUT (claude/OCTA303_v79_
# catena_e_fabbrica.md sec. 2).  Roland's procedure (service notes p. 7: saw, key C, CUT 64, RES 127, ENV/DEC/ACC 0,
# ring 2.0 ms +-0.5) on V8A's model gives 2.97-2.99 ms: log2(2.98 / 2.0) = +0.575 octave = 1766 of the cutoff's
# 3072 a octave (claude/OCTA303_v79_tarature.md sec. 4; the researcher's +0.47..+0.64)
TM3_FAB = int(round(0.575 * 3072))
GATE_LABELS = ('OFF', '303')
FINE_Q8 = 2                                   # Q8 semitones a FINE step: +-64 steps = +-0.5 semitone
# v7.7: DRIV is the 303's own VOLUME (VR8) turned past Din Sync's position, driving the output mixer Q33/Q34 into
# saturation (claude/OCTA303_componenti_303.md sec. 8, the researcher's recipe). After today's ceiling C (pin 6):
# x = 10^(10 DRIV/127/20) y (0 .. +10 dB, linear in dB: the top of VR8's A track), then a soft asymmetric limit per
# side: |x| <= K passes, beyond it K + (L - K) tanh((|x| - K)/(L - K)), K = 0.95 L; the negative side L- = 1.0 C (Q33
# switching off: Din Sync's limited side), the positive side L+ = 1.8 L- (Q33 saturating). DRIV 0 skips the block:
# today's sound bit for bit. Units: the VCA output after the output coupling (o - dc, before >> SHIFT_OUT).
DRV_DB = 10.0
DRV_G = [int(round(4096 * 10 ** (DRV_DB * r / 127.0 / 20.0))) for r in range(128)]   # Q12
DRV_C = P6_F[256]                                                    # today's ceiling: pin 6's table at its flat end
DRV_LN = DRV_C; DRV_KN = int(round(0.95 * DRV_LN))
DRV_LP = int(round(1.8 * DRV_LN)); DRV_KP = int(round(0.95 * DRV_LP))
DRV_RN = int(round(2 ** 28 / (DRV_LN - DRV_KN)))                     # t = ((|x| - K) * R) >> 6 = 64 u in Q16
DRV_RP = int(round(2 ** 28 / (DRV_LP - DRV_KP)))
DRV_TH = [int(round(math.tanh(j / 64.0) * 2 ** 14)) for j in range(258)]   # tanh(u), u = j/64, Q14
DRV_YLIM = 1 << 22                                                   # y clamped here: (y >> 6) * DRV_G fits 32 bits
DRV_G0 = DRV_G[0]
DRV_WN, DRV_WP = DRV_LN - DRV_KN, DRV_LP - DRV_KP                    # L - K per side
DRV_DN4, DRV_DP4 = 4 * DRV_WN, 4 * DRV_WP                            # |x| - K clamped here (tanh 4 = 0.9993)
assert DRV_G[0] == 4096 and (DRV_YLIM >> 6) * DRV_G[127] < 2 ** 31
assert 4 * (DRV_LN - DRV_KN) * DRV_RN < 2 ** 31 and 4 * (DRV_LP - DRV_KP) * DRV_RP < 2 ** 31   # |x| - K clamped at 4 (L - K)
assert (DRV_LP - DRV_KP) * 2 ** 14 < 2 ** 31
# v7.0: CUT and ENV MOD glide to a new value (a p-lock, an LFO jump) in ~1 ms instead of stepping: the
# knobs' cutoff base and env depth, smoothed at the control rate (Q16 of the Q8-semitone domain)
SMOOTH_K = q15(onepole(0.001))

def _M(b, k):
    import numpy as np
    M = np.zeros((4, 4))
    for col in range(4):
        y = np.zeros(4); y[col] = 1
        y0 = -k * y[3]
        y1 = y[0] + 2 * b * (y0 - y[0] + y[1]); y2 = y[1] + b * (y1 - 2 * y[1] + y[2])
        y3 = y[2] + b * (y2 - 2 * y[2] + y[3]); y4 = y[3] + b * (y3 - 2 * y[3])
        M[:, col] = [y1, y2, y3, y4]
    return M
def _rho(b, k):
    import numpy as np
    return max(abs(np.linalg.eigvals(_M(b, k))))
def _kosc(b):
    lo, hi = 0.0, 400.0
    for _ in range(48):
        m = (lo + hi) / 2
        if _rho(b, m) >= 1: hi = m
        else: lo = m
    return lo
def _wres(b):
    import numpy as np
    ev = np.linalg.eigvals(_M(b, _kosc(b))); return abs(np.angle(ev[np.argmax(abs(ev))]))
def _solve_b(fc):
    lo, hi = 1e-6, 0.49
    for _ in range(40):
        m = (lo + hi) / 2
        if _wres(m) * FS / (2 * math.pi) < fc: lo = m
        else: hi = m
    return lo

def ladder_tables():
    n = S_MAX // 64 + 1
    B, K = [], []
    for i in range(n):
        fc = FC0 * 2 ** (i / 48)
        b = _solve_b(fc); k = _kosc(b)
        B.append(q15(b)); K.append(int(round(k * 256)))
    return B, K

_LC = _ladder_cache()
KD = [int(round(v * 256)) for v in _LC['KD']]                                  # Q8 feedback per dB/ms
_kr = _ixcurve('kr')
KF = [int(round(_LC['KO'][i] / (_LC['K'][i] / 256.0) * _kr[i])) for i in range(len(_kr))]   # Q12
_i0 = int(math.ceil(48 * math.log2(FKN_HZ[0] / FC0)))
KF = [KF[max(i, _i0)] for i in range(len(KF))]      # held below the first knot, as v6.7's KF

# gain compensation vs resonance (Q12): measured so a 110 Hz saw keeps its level within ~3 dB

# ---------------------------------------------------------------- dEVILish (v6.3): the Devil Fish, from an FX slot
# Robin Whittle, "User Manual for the Devil Fish mods to the TB-303" (2019), pp. 4-6, 8, 12-19, 24-25.
# A 303 track whose FX1 or FX2 is the dEVILish module (modules/devilish) reads these twelve knobs
# from that slot's two pages in the live lane (0x80000810 + 72*t: FX1 page 1 +18, FX2 +24, page 2
# +32 more; PARAM_PAGES.md 5a', 5b), locks applied; every other 303 track reads DF_NEUTRAL, which is
# v6.1.1 sample for sample ("Limiting the Devil Fish to TB-303 sounds", p. 8).
#  page 1, the knobs:   0 OVDR  1 FM   2 TRCK  3 VDEC  4 SLID  5 ADEC
#  page 2, the selects: 6 SATK  7 SWP  8 SPD   9 MUFF 10 CUTX 11 ENVX   (SATK a knob, the rest indices)
DF_NAMES = ('OVDR', 'FM', 'TRCK', 'VDEC', 'SLID', 'ADEC', 'SATK', 'SWP', 'SPD', 'MUFF', 'CUTX', 'ENVX')
DF_NEUTRAL = (25, 0, 0, 64, 0, 50, 0, 0, 1, 0, 0, 0)
DF_LABELS = {'SWP': ('ACID', 'WHST', 'SELF'), 'SPD': ('FAST', 'NORM', 'SLOW'),
             'MUFF': ('OFF', 'SOFT', 'HARD'), 'CUTX': ('OFF', 'ON'), 'ENVX': ('OFF', 'ON')}
# OVDR: the VCO into the ladder, none (0) .. normal (25) .. 66.6x normal (127)        [p. 4]
def _ovg(r): return r / 25.0 if r <= 25 else 66.6 ** ((r - 25) / 102.0)
# up to normal (raw <= 25) the v6.1 product exactly, Q15 (pre 7, post 8); above it Q10 (pre 6, post 4)
DF_GIN = [int(round(22938 * r / 25)) if r <= 25 else int(round(0.70 * _ovg(r) * 1024)) for r in range(128)]
DF_GIN_Q15 = 25                   # raw <= this: the Q15 path
# overdrive swamps the resonance, so TB_GCOMP's resonance part would lift the output and clip:
# gcomp = (base + resonance part * K1) * K2, K1 = G^-1.5, K2 = G^-0.3 (calibrated in v6.2), 1 for G <= 1
DF_OCOMP = [4096 if _ovg(r) <= 1 else int(round(4096 * _ovg(r) ** -1.5)) for r in range(128)]
DF_OGAIN = [4096 if _ovg(r) <= 1 else int(round(4096 * _ovg(r) ** -0.3)) for r in range(128)]
# FM: the VCA output (after the Muffler), AC coupled, moves the cutoff per sample           [p. 5, 18-19]
DF_FM_MUL = 96                    # fmq = raw*96: ((vca >> 8) * fmq) >> 12 Q8 st; 127 -> ~47 st at full level
# TRCK: LINEAR in Hz -- "the filter goes up ~2.7 kHz when the oscillator CV goes up an octave"
# at maximum; the zero point is the bottom C of the normal octave (here TUNE 0); a pot "made a
# little more linear" than log, so (raw/127)^1.5                                          [p. 5, 14]
DF_TRK_HZ = [int(round(2700.0 * (r / 127.0) ** 1.5)) for r in range(128)]            # Hz per octave
# VDEC: first half 16 ms .. the 303's long decay; second half that decay with a final level
# from silence (64) to full (127) -- "indefinitely long notes"                            [p. 4]
def _vtau(r): return 0.016 * (VEG_TAU / 0.016) ** (min(r, 64) / 64.0)   # v6.7: VEG_TAU at 64 (v6.6: 1.23 s)
DF_VEG = [q30(math.exp(-CS / (FS * _vtau(r)))) for r in range(128)]
DF_VSUS = [0 if r <= 64 else int(round((r - 64) / 63.0 * ONE30)) for r in range(128)]
# SLID: R = 103.3k (DAC + protection) + 0..500k pot on the 0.22 uF slide cap: 60 .. 360 ms  [p. 16]
DF_SLIDE = [q15(onepole(SLIDE_TAU * (103.3 + 500.0 * r / 127.0) / 103.3)) for r in range(128)]
# SWP: 2 ACID = sweep on, resonance normal; 1 WHST = sweep on, resonance doubled; 0 SELF =
# sweep circuit off (accents reach filter and VCA no more), resonance doubled             [p. 18]
DF_HIRES = 2                      # "double the usual feedback": self-oscillates at mid/high f (the 150 Hz loop HP)
# ADEC: the accented notes' MEG decay, 30 ms .. 3 s to 10 % [p. 4]; 50 = the 303's 200 ms.  v7.9: the circuit at every
# value (ADEC_T, continuous); the entry is ADEC_T's row position a + 2 (2..129), never 0 (0 = no dEVILish = ADEC 50)
DF_ADEC = [r + 2 for r in range(128)]
# SATK: the VOLUME attack of non-accented notes (pp. 4, 24-25: Decay fully ACW with Soft Attack
# fully CW plays nothing). 0 = none, v6.1's instant attack; 1..127 = 90 % in 0.3 .. 30 ms
DF_SATK = [0] + [q30(1.0 - math.exp(-CS / (FS * 0.0003 * 100.0 ** ((r - 1) / 126.0) / math.log(10)))) for r in range(1, 128)]
DF_SATK[0] = TB_SATK                  # v6.7: SATK 0 = the 303's own attack (measured), not none
# SPD: sweep speed (v2.0+): FAST, NORM (the 303), SLOW ("much longer time constant ... can rise
# twice as high")                                                                         [p. 4-5]
# INTERPRETED: FAST = the capacitor read as a change (first accent strong, the next smaller),
# SLOW = charge and discharge 4x slower, the capacitor's sweep doubled
DF_SLOW_CH, DF_SLOW_DIS, DF_SLOW_G = 2, 4, 2      # SLOW: charge /CH, discharge /DIS, the capacitor's sweep x G
DF_FAST_G, DF_FAST_CH = 8, 64                       # FAST: max(0, vin - cap) * G / 16, the cap charging CH x faster
DF_ACH_SLOW = [a // DF_SLOW_CH for a in TB_ACH]
DF_DIS_SLOW = TB_DIS // DF_SLOW_DIS
DF_ACH_FAST = [min(a * DF_FAST_CH, 32767) for a in TB_ACH]
# MUFF: after the VCA; softens the loudest extremes, a square-wave clipping buzz, the bass passes;
# no effect at low level                                                                  [p. 6, 19]
# INTERPRETED: split at ~150 Hz; above it, mode 1 soft-clips and mode 2 hard-clips at DF_MUFF_T
DF_MUFF_LP = q15(onepole(1.0 / (2 * math.pi * 150.0), 1))
DF_MUFF_DLIM = 16 * ((2 ** 31 - 1) // DF_MUFF_LP) - 16      # v7.3: (o - mlo) >> 4 * DF_MUFF_LP fits 32 bits
DF_MUFF_T = int(0.30 * (1 << 20))      # S20: the 303's normal peak at RES 0 is ~0.3 FS here
# CUTX: the cut-off pot's range, higher and lower, to ~5 kHz (an octave above the 303)      [p. 6]
DF_CUTX = [int(round(s_of_hz(157.0 * (4788.0 / 157.0) ** (r / 127)))) for r in range(128)]
# ENVX: the Env Mod pot's range tripled and including none                                [p. 6]
DF_ENVX_MUL = 3

DF_HZ = [int(round(FC0 * 2.0 ** (i * 64 / 3072.0))) for i in range(S_MAX // 64 + 1)]   # TRCK: Hz of a ladder index

# ---------------------------------------------------------------- the distortion pedal (WAVE's +D; v6.x: TB303D / TB303SQD)
# A fixed pedal after the VCA, as the London acid-techno records used: pre-gain, soft clip with a
# small asymmetry (even harmonics), 6 kHz tone lowpass.  The output highpass removes the bias DC.
DIST_GAIN = 5
DIST_BIAS = int(round(0.12 * (1 << 20)))
DIST_TONE = q15(onepole_hz(6000.0))

# v7.9: name_code (a TB303* file name -> the carrier) is gone with the sample way in; test_octa303 keeps its own.
