"""v7.8: the TB-303's MEG (filter envelope) as its circuit, for every note (claude/OCTA303_blocco3_accento.md, V8A;
taccuino sez. 5).  From the Roland service notes' main board (= the x0xb0x netlist):

    C62 1 uF --R (accents: R138 68k + IC12 4066 Ron 200; normal notes: R138 + VR6 DECAY)--D28--D29--N50
    N50: R117 22k from +5.333 V, D26 to ground;  the filter sees C62 through the Q40/Q41 Darlington,
    loaded by the Q39 2SK30 JFET (IDSS 2 mA, |Vp| 1 V).

1N4148 diodes (n 1.752) with Is scaled so that DECAY at its minimum (and every accent) falls to 10 % in 200 ms, and
VR6's part scaled so that DECAY 127 does in 2.5 s: both numbers are Roland's ("DECAY VR MIN T = 200 ms, MAX T =
2.5 sec", service notes p. 5).  Between them the pot's law is the model's own (o3tables TB_MEG: the -20 dB time by
DECAY).  Nothing here is fitted to a recording.

The decay is not exponential (the diodes stretch the tail), so the engine steps it with a factor per control frame
that depends on DECAY and on the level: tables(...) returns that factor, Q30, on a grid of 33 DECAY rows (0, 4, ...,
124, and a row at "128" extrapolated so that 127 is exact) by 64 levels (6 per octave; see level_of_x).  Slow
(~2 min in Python): o3tables caches the result (meg_cache.json).
"""
import math

VT, N = 0.02585, 1.752
IS0 = 2.52e-9                                  # 1N4148 SPICE
FR = 16 / 44100.0                              # the control frame (o3tables CS)
KS = 127 / 7.0                                 # the level grid of the study table: u = -ln(level) * 127 / 7
NROW, NLEV, LPO = 33, 64, 6                    # engine grid: DECAY rows, levels, levels per octave


def _meg_out(vc, idss=2e-3, vp=1.0, Is=1e-14, beta=200.0):
    """the Darlington's output for C62 at vc: vc - vo = Vbe40(I / beta) + Vbe41(I), I = the JFET's at vds = vo"""
    def jf(vo):
        x = vo / vp
        return idss if x >= 1 else idss * (2 * x - x * x)
    lo, hi = 0.0, max(vc, 0.0)
    for _ in range(80):
        vo = (lo + hi) / 2; i = max(jf(vo), 1e-15)
        vb = VT * math.log(1 + i / Is) + VT * math.log(1 + i / beta / Is)
        lo, hi = (vo, hi) if vo + vb < vc else (lo, vo)
    return (lo + hi) / 2


def _chain(np, Is):
    """the discharge chain's voltage without R (D28 + D29 + N50) on a grid of currents"""
    I = np.logspace(-13, -2.5, 4000)
    vd = N * VT * np.log1p(I / Is)
    v50 = []
    for i in I:
        lo, hi = 0.0, 1.0
        for _ in range(50):
            v = (lo + hi) / 2; f = i + (5.333 - v) / 22e3 - Is * (math.exp(v / (N * VT)) - 1)
            lo, hi = (v, hi) if f > 0 else (lo, v)
        v50.append(v)
    return I, 2 * vd + np.array(v50)


def _run(np, VO_VC, VO, I, G, R, T, dt=1e-4, v0=11.2):
    """C62 from v0 through R and the chain, T seconds: the MEG's output over its peak"""
    vcg = I * R + G; vc = v0; n = int(T / dt); out = np.empty(n)
    for k in range(n):
        out[k] = np.interp(vc, VO_VC, VO); vc -= np.interp(vc, vcg, I, left=0.0) * dt / 1e-6
    return out / out[0]


def _t10(np, e, dt=1e-4): return np.argmax(e < 0.1) * dt * 1e3


def _row(np, e, dt):
    """per-frame factor vs u = -ln(level) * 127 / 7, 128 points (the study's table: the mean factor in each bin)"""
    tf = np.arange(0, (len(e) - 1) * dt, FR); ef = np.interp(tf, np.arange(len(e)) * dt, e)   # inside the run (review: past its end the
                                                                         # factor read 1.0, a stuck tail)
    u = -np.log(np.maximum(ef[:-1], 1e-12)); f = ef[1:] / np.maximum(ef[:-1], 1e-12); F = []
    for gq in np.arange(128) / KS:
        m = (u >= gq - 0.5 / KS) & (u < gq + 0.5 / KS) & (ef[:-1] > 1e-6)
        F.append(float(np.mean(f[m])) if m.any() else (F[-1] if F else 0.5))
    return F


def study_rows(t10_s, tmin_ms=200.0, tmax_ms=2500.0):
    """the factor rows by DECAY (128 x 128, row 0 = the accents and DECAY 0), t10_s[d] = the model's -20 dB time
    by DECAY; Is solved for tmin_ms (DECAY 0), VR6's part scaled for tmax_ms (DECAY 127)."""
    import numpy as np
    VO_VC = np.linspace(0.0, 12.0, 2401); VO = np.array([_meg_out(v) for v in VO_VC])
    RA = 68e3 + 200.0
    lo, hi = 1.0, 200.0                                    # Is / s: DECAY 0 at 10 % in tmin_ms
    for _ in range(18):
        m = math.sqrt(lo * hi); I, G = _chain(np, IS0 / m); t = _t10(np, _run(np, VO_VC, VO, I, G, RA, 0.6))
        lo, hi = (m, hi) if t < tmin_ms else (lo, m)
    s = math.sqrt(lo * hi); I, G = _chain(np, IS0 / s)
    R127 = t10_s[127] / math.log(10) / 1e-6; lo, hi = 0.5, 1.2   # VR6's part: DECAY 127 at 10 % in tmax_ms
    for _ in range(16):
        k = (lo + hi) / 2; t = _t10(np, _run(np, VO_VC, VO, I, G, 68e3 + k * (R127 - 68e3), 4.0, 4e-4), 4e-4)
        lo, hi = (k, hi) if t < tmax_ms else (lo, k)
    kv = (lo + hi) / 2
    rows = [_row(np, _run(np, VO_VC, VO, I, G, RA, 1.4), 1e-4)]
    for d in range(1, 128):
        R = 68e3 + kv * (t10_s[d] / math.log(10) / 1e-6 - 68e3); T = min(8.0, max(1.0, 4 * t10_s[d]))
        dt = 1e-4 if t10_s[d] < 0.4 else 4e-4
        rows.append(_row(np, _run(np, VO_VC, VO, I, G, R, T, dt), dt))
    return rows, s, kv


def level_of_x(x):
    """the engine's level coordinate: x = o + t, level = 2^-o (1 - t / 2): linear in the level within each octave
    (what ff1 and the mantissa give at no cost), continuous at the octave edges"""
    o = math.floor(x); t = x - o
    return 2.0 ** -o * (1.0 - t / 2.0)


def study_factor(row, level):
    """the study's (twin's) per-frame factor at a level: linear in u, 0.5 past u = 126 (sim.c ctrl)"""
    u = -math.log(level) * KS if level > 1e-9 else 1e9
    if u >= 126.0: return 0.5
    k = int(u); fr = u - k
    return row[k] * (1 - fr) + row[k + 1] * fr


def tables(t10_s):
    """the engine's table: NROW x NLEV Q30 factors (row r = DECAY 4r; row 32 extrapolated so DECAY 127 is exact)"""
    rows, s, kv = study_rows(t10_s)
    def erow(d): return [study_factor(rows[d], level_of_x(j / float(LPO))) for j in range(NLEV)]
    E = [erow(4 * r) for r in range(32)]
    e127 = erow(127)
    E.append([a + (b - a) * 4.0 / 3.0 for a, b in zip(E[31], e127)])
    Q = [[int(round(min(v, 1.0 - 2 ** -30) * (1 << 30))) for v in row] for row in E]
    return Q, s, kv, rows


# ---------------------------------------------------------------- v7.9: dEVILish ADEC, continuous (OCTA303_v79_tarature.md sec. 3)
# The Devil Fish's Accent Decay pot (30 ms .. 3 s, DF manual p. 4) in the accent's discharge path in place of IC12's
# short: every ADEC is the same circuit (C62, the diodes at the Is already fixed by Roland's 200 ms, the Darlington),
# with one resistance R in place of R138 + Ron.  R is solved for the time to 10 % of the law below; ADEC 50 is the 303
# (R138 + Ron, MEG_T's row 0, copied so it is the same bits).  Rows sit at ADEC 4r - 2 (r = 0..33): ADEC a reads the
# row position q = a + 2 (row q >> 2, weight q & 3), so ADEC 50 is exactly row 13.
ADEC_NROW, ADEC_Q50 = 34, 52


def adec_t10(a):
    """the MEG's time to 10 % (s) at ADEC a: 30 ms at 0, 200 ms at 50, 3.0 s at 127; geometric on each side"""
    return 0.2 * (0.15 ** ((50 - a) / 50.0) if a <= 50 else 15.0 ** ((a - 50) / 77.0))


def adec_tables(is_scale, row50):
    """ADEC_NROW x NLEV Q30 factors (the format of tables()); row50 = MEG_T[0]; returns (rows, R by row in ohm)"""
    import numpy as np
    VO_VC = np.linspace(0.0, 12.0, 2401); VO = np.array([_meg_out(v) for v in VO_VC])
    I, G = _chain(np, IS0 / is_scale)
    rows, rs = [], []
    for r in range(ADEC_NROW):
        a = 4 * r - 2
        if a == 50:
            rows.append(list(row50)); rs.append(68e3 + 200.0); continue
        t = adec_t10(a); dt = 1e-5 if t < 0.1 else (1e-4 if t < 0.4 else 4e-4)
        lo, hi = 1e3, 3e6                                   # R: bisection in log R on the time to 10 %
        for _ in range(28):
            R = math.sqrt(lo * hi); e = _run(np, VO_VC, VO, I, G, R, 2.0 * t + 0.01, dt)
            tt = _t10(np, e, dt) / 1e3 if (e < 0.1).any() else float('inf')   # not down to 10 % in the run: too slow
            lo, hi = (R, hi) if tt < t else (lo, R)
        R = math.sqrt(lo * hi)
        e = _run(np, VO_VC, VO, I, G, R, 7.0 * t, dt)      # 7 x its own time to 10 %: every row's run ends where
                                                             # MEG_T's row 0 (1.4 s at 200 ms) does, so the held tail
                                                             # past the run's end (_row) moves with ADEC (review, 7 Nov)
        row = _row(np, e, dt)
        rows.append([int(round(min(study_factor(row, level_of_x(j / float(LPO))), 1.0 - 2 ** -30) * (1 << 30)))
                     for j in range(NLEV)])
        rs.append(R)
    return rows, rs
