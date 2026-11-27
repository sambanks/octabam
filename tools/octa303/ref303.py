"""OCTA303 v7.8 golden reference: the integer arithmetic of modules/octa303/octa303.s, in Python.

One engine (TB-303).  Every helper is one assembly idiom.  sim/test_octa303.py runs the assembly
source in cfsim and requires its output to be BIT-IDENTICAL to this model.

v6 CPU work: per-sample multiplies are 'fast' -- ((d >> pre) * c) >> post, one muls.l and two
shifts -- instead of v5's exact split multiply (9 instructions).  CHECK=True asserts every product
stays inside 32 bits; the stress tests run with it on.
"""
import json, os
import o3tables as T

_lc = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ladder_cache.json')
if os.path.exists(_lc):
    _d = json.load(open(_lc)); LB, LK = _d['B'], _d['K']
else:
    LB, LK = T.ladder_tables()
M32 = 0xFFFFFFFF
CHECK = True
PEAK = {}

def s32(x): x &= M32; return x - (1 << 32) if x & 0x80000000 else x
def chk(x, tag=''):
    if CHECK:
        if not (-(1 << 31) <= x < (1 << 31)): raise OverflowError('%s %d' % (tag, x))
        if tag: PEAK[tag] = max(PEAK.get(tag, 0), abs(x))
    return x
def mulq(d, c, s):                                  # exact floor(d*c / 2^s) (control rate)
    hi = chk((d >> s) * c); lo = ((d & ((1 << s) - 1)) * c)
    if CHECK and lo >= (1 << 32): raise OverflowError('lo')
    return chk(hi + (lo >> s))
def mulq15(d, c): return mulq(d, c, 15)
def fm(d, c, pre, post, tag=''):                    # fast: asr pre ; muls.l ; asr post
    return chk((d >> pre) * c, tag) >> post
def mul30(a, b):                                    # a,b >= 0, ~(a*b)>>30
    ah, al, bh, bl = a >> 15, a & 0x7FFF, b >> 15, b & 0x7FFF
    mid = (ah * bl + al * bh) & M32
    return chk(ah * bh + (mid >> 15))
def clamp(x, lo, hi): return lo if x < lo else hi if x > hi else x
def raw(w): return min(w >> 8, 127)
def p_of_word(w0):                                  # v6.4: the word is semitones (Q8), no /5
    return clamp(T.P_CENTER + (w0 - 0x4000), T.P_LO, T.P_HI)
def inc_of_p(p):
    o, r = divmod(p, 3072)
    return (T.INC_TAB[r >> 2] << o) & M32
def blep(phase, inc):
    if phase < inc:
        t = min((phase << 3) // (inc >> 12), 32768); q = 32768 - t
        return -((q * q) >> 15)
    r = (-phase) & M32
    if r < inc and phase != 0:
        t = min((r << 3) // (inc >> 12), 32768); q = 32768 - t
        return (q * q) >> 15
    return 0
def softclip(y):                                    # clamp to +-sqrt2, y - y^3/6  (S20)
    y = clamp(y, -1482910, 1482910)
    xs = y >> 8; x2 = (xs * xs) >> 12; x3 = (x2 * xs) >> 12
    return y - ((x3 * 10923) >> 8)
FIELDS = ('latched', 'wave', 'dist', 'fab', 'phase', 'inc', 'pcur', 'cs', 'meg', 'megs', 'veg',
          'accd', 'acci', 'v34', 'dvc', 'y27', 'amp', 'ampstep', 'hp', 'y1', 'y2', 'y3', 'y4', 'fb',
          'dc', 'tone', 'c1', 'b', 'k', 'gcomp', 'ptgt', 'cut', 'res', 'env', 'dec',
          'gin', 'vegd', 'vsus', 'trkhz', 'fmq', 'sctrl', 'kmul', 'ovca', 'ocomp', 'ogain',
          'slide', 'swp', 'adec', 'satk', 'vatt', 'spd', 'muff', 'mlo', 'cutx', 'envx', 'ginq15', 'nz',
          'gmode', 'gate', 'glvl', 'gstep', 'lstep', 'ltick', 'idle', 'kmax', 'tps', 'gnew', 'gel', 'gend', 'sqi', 'ud', 'sqk', 'accvg', 'osin', 'oslim', 'fine', 'cutb', 'envs', 'smok', 'setsl', 'gsel', 'fcnt', 'fpt', 'fseen', 'gelf', 'mach', 'clg', 'cli', 'cll', 'fskip', 'stopd', 'vp1', 'vp2', 'w2', 'sql', 'flp')
class Track:
    def __init__(self):
        for k in FIELDS: setattr(self, k, 0)
        self.cs = 1
        self.accvg, self.osin, self.oslim = 64, T.DRV_G[0], 0   # v7.8: accvg = ACCV raw (64 = the 303); v7.7: osin = DRIV's gain (Q12)

def note_on(st, code, w):
    st.wave, st.dist, st.fab = code & 1, (code >> 1) & 1, (code >> 2) & 1   # v7.9: bit 2 = R, the factory preset
    acc = raw(w[5])
    st.pcur = clamp(p_of_word(w[0]) + st.fine, T.P_LO, T.P_HI) << 8   # v7.0: FINE
    st.cs = 1
    st.accd = 1 if acc else 0
    st.acci = acc                                   # v7.8: VR7's position (the circuit's tables are by ACCENT raw)
    st.meg = T.ONE30
    st.veg = T.ONE30
    st.vatt = 0 if (st.satk and not acc) else T.ONE30   # SATK: non-accented notes fade in
    st.gnew = 1                                     # v6.5: the gate opens at the next gate_frame

def tdiv(a, b): return -((-a) // b) if a < 0 else a // b   # truncating, as divs.l

def trck(s, d, hz):
    """TRCK, linear in Hz: the cutoff at ladder index s>>6 plus hz*d/3072 Hz (d = Q8 semitones
    from TUNE 0), back to an index by binary search; the low notes can close the filter."""
    i = s >> 6
    f2 = T.DF_HZ[i] + tdiv(hz * d, 3072)
    if f2 <= T.DF_HZ[0]: return 0
    lo, hi = 0, len(T.DF_HZ) - 1                         # largest j with DF_HZ[j] <= f2
    while lo < hi:
        m = (lo + hi + 1) >> 1
        if T.DF_HZ[m] <= f2: lo = m
        else: hi = m - 1
    return (lo << 6) + (s & 63)

def kfb(i, kmul, ud):
    """v6.9: the feedback at ladder index i -- the RES pot's fraction of the oscillation point (KF = KO / LK
    times the shape by frequency) less the decay UD (dB/ms, Q10) times KD (the feedback a dB/ms), never < 0."""
    k = (((LK[i] * kmul) >> 15) * T.KF[i]) >> 12
    k -= chk(ud * T.KD[i], 'ud') >> 10
    return k if k > 0 else 0

def clset(st, i):
    """v7.3: the ladder clip's operating point at ladder index i (0 = the plain soft clip).  ACID only (SWP 2):
    dEVILish's WHST / SELF oscillate on purpose and the clip sets their level, as in v7.1."""
    j = i - T.CL_I0
    if j > 0 and st.swp == 2: st.clg, st.cli, st.cll = T.CL_G[j], T.CL_INV[j], T.CL_LIM[j]
    else: st.clg = 0

def ladder_clip(st, u):
    """v7.3: softclip(u * g) / g at the top of the table, softclip(u) below it."""
    if not st.clg: return softclip(u)
    u = clamp(u, -st.cll, st.cll)
    return fm(softclip(fm(u, st.clg, 4, 8, 'clg')), st.cli, 4, 8, 'cli')

def megf(m, dec, tab=None):
    """v7.8: the MEG's factor for this frame (o3meg.py): MEG_T by DECAY (33 rows, 4 apart, linear) and by level
    (64 points, 6 an octave, linear; level coordinate from ff1 and the mantissa: o3meg.level_of_x).  v7.9: tab =
    ADEC_T for accents, dec = the ADEC row position (o3_megfa)"""
    if tab is None: tab = T.MEG_T
    n = 32 - m.bit_length()                          # ff1: m <= ONE30, so n >= 2
    t = (1 << 32) - (m << n)                         # 2 - the mantissa, Q31: (0, 2^31]
    x = (n - 2) * 393216 + (t >> 15) * 6             # Q16 position on the grid (6 points an octave)
    r, w = dec >> 2, dec & 3
    j = x >> 16
    def lv(row):
        if j >= T.MEG_NLEV - 1: return row[T.MEG_NLEV - 1]
        return row[j] + mulq15(row[j + 1] - row[j], (x & 0xFFFF) >> 1)
    f0 = lv(tab[r])
    if w == 0: return f0
    return f0 + ((chk((lv(tab[r + 1]) - f0) * w, 'megw')) >> 2)

def acf(tab, v):
    """y = i R of a diode in series with R, from AC_F or AC_F27 (32.8 mV steps, linear)"""
    if v <= 0: return 0
    if v > T.AC_VMAX: v = T.AC_VMAX
    j = v >> T.AC_FSH
    return tab[j] + (((tab[j + 1] - tab[j]) * (v & 0x7FFF)) >> 15)

def accent(st, tm):
    """v7.8 (V8A): the accent circuit, two backward-Euler sub-steps (o3tables AC_*): returns the push to the filter
    (Q8 semitones) and the VCA's extra level I27 / I_Q31 (Q14).  tm = the MEG (Q30) into VR7, 0 on normal notes."""
    a, res = st.acci, st.res
    k2 = T.AC_K2[res]
    if st.spd == 1: k2 <<= 2                         # dEVILish SPD FAST: C13 / 4 (INTERPRETED)
    elif st.spd == 3: k2 >>= 2                       # SLOW: C13 x 4, read doubled (INTERPRETED)
    if tm == 0 and st.v34 == 0 and st.y27 == 0 and mul30(st.dvc, k2) == 0:   # at rest: the sub-steps would change
        dw = mul30(st.dvc, T.AC_B1[res])                                    # nothing (exact shortcut, ~1/8 the cost)
        if st.spd == 3: dw <<= 1
        return mul30(dw, T.AC_KSW), 0
    r24 = T.AC_RE[a] + T.AC_RA[res]
    inv = (1 << 29) // r24                           # divu.l: Q29 per ohm
    qre, qrp, q72 = T.AC_RE[a] * inv, T.AC_RP[res] * inv, T.AC_R72N * inv
    dl = ((r24 - T.AC_R0) * T.AC_KLN) >> 16          # ~ nVT ln(R24 / R0), uV
    y24 = 0
    for _ in range(2):
        ve = mul30(tm, T.AC_A1[a]) + mul30(st.v34, T.AC_A2[a])      # VR7's wiper loaded by R119 to C36
        v24 = ve - T.AC_V134 - mul30(st.dvc, T.AC_B1[res])          # D24 + R46 + VR4B towards C13
        y24 = acf(T.AC_F, v24 + dl) if v24 > 0 else 0
        w7 = ve - 2 * mul30(y24, qre)
        if w7 < 0: w7 = 0
        dd = 2 * mul30(y24, q72) - st.dvc                            # C13 (above N134) towards i24 R72
        st.dvc += mul30(dd, k2) if dd >= 0 else -mul30(-dd, k2)
        p = mul30(st.v34, T.AC_AL) + mul30(w7, T.AC_BE)              # C36 with R119, then R120 + D27 into pin 1
        j = st.y27 >> 16
        l69 = T.AC_L69[128] if j >= 128 else T.AC_L69[j] + (((T.AC_L69[j + 1] - T.AC_L69[j]) * ((st.y27 & 0xFFFF) >> 1)) >> 15)
        v27 = p - T.AC_V69 - l69
        st.y27 = acf(T.AC_F27, v27) if v27 > 0 else 0
        st.v34 = p - mul30(st.y27, T.AC_Q27G)
        if st.v34 < 0: st.v34 = 0
    dw = mul30(st.dvc, T.AC_B1[res])
    if st.spd == 3: dw <<= 1
    swq8 = mul30(dw + 2 * mul30(y24, qrp), T.AC_KSW)                  # the wiper above N134, through R72
    return swq8, mul30(st.y27, T.AC_KV)

def ctrl(st):
    st.pcur += mulq15((st.ptgt << 8) - st.pcur, st.slide)              # SLID
    st.inc = inc_of_p(st.pcur >> 8)
    st.sqi = st.pcur >> 16                                             # v7.6: the square's cycle (Q8) by semitone
    st.sqk = T.SQK[st.sqi]
    if st.meg > 0:                                                     # v7.8: the circuit (o3meg.py), every note;
        if st.accd:                                                    # v7.9: accents on ADEC_T, dEVILish's ADEC
            st.meg = mul30(st.meg, megf(st.meg, st.adec or T.ADEC_Q50, T.ADEC_T))   # (0: none = ADEC 50)
        else:
            st.meg = mul30(st.meg, megf(st.meg, st.dec))
    st.megs += mulq15(st.meg - st.megs, T.TB_MEG_ATT)
    d = st.veg - st.vsus                                               # VDEC (the final level may move
    st.veg = st.vsus + mul30(d, st.vegd) if d >= 0 else st.vsus - mul30(-d, st.vegd)   # above the envelope)
    if st.satk:
        st.vatt += mul30(T.ONE30 - st.vatt, st.satk)                     # SATK
        if st.vatt > T.ONE30 - 64: st.vatt = T.ONE30
    cut, res, env = st.cut, st.res, st.env
    swq8, vin = accent(st, st.megs if (st.accd and st.swp) else 0)     # v7.8: the accent circuit (SWP 0: no MEG in)
    if st.envx:                                                        # ENVX: x3, from none
        S = (((T.TB_SLO[127] + (((T.TB_SHI[127] - T.TB_SLO[127]) * res * 258) >> 15)) * T.DF_ENVX_MUL) * env) // 127
    else:
        S = T.TB_SLO[env] + (((T.TB_SHI[env] - T.TB_SLO[env]) * res * 258) >> 15)
    base = T.DF_CUTX[cut] if st.cutx else T.TB_CUT[cut]                 # CUTX
    if not st.smok:                                                    # v7.0: the first control step takes them
        st.cutb, st.envs, st.smok = base << 8, S << 8, 1
    st.cutb += mulq15((base << 8) - st.cutb, T.SMOOTH_K)               # v7.0: ~1 ms glides, no steps
    st.envs += mulq15((S << 8) - st.envs, T.SMOOTH_K)
    base, S = st.cutb >> 8, st.envs >> 8
    s = base + ((((st.megs >> 15) - T.TB_OFF[cut]) * S) >> 15) + swq8
    if st.fab: s += T.TM3_FAB                                          # v7.9: R, TM3 as Roland trims it
    s = clamp(s, 0, T.S_MAX - 1)
    if st.trkhz:
        s = trck(s, (st.pcur >> 8) - T.P_CENTER, st.trkhz)            # TRCK
    st.sctrl = s
    st.kmul = T.TB_KMUL[res] * (1 if st.swp == 2 else T.DF_HIRES)        # SWP 1/0: resonance doubled
    st.ud = T.TB_UD[res]                                               # v6.9: the ring's decay, dB/ms Q10
    i = s >> 6
    st.b = LB[i]; st.c1 = (LB[i] * T.TB_C1R) >> 12
    st.k = kfb(i, st.kmul, st.ud)
    clset(st, i)                                                       # v7.3
    g0 = T.TB_GCOMP[0]
    st.gcomp = ((g0 + (((T.TB_GCOMP[res] - g0) * st.ocomp) >> 12)) * st.ogain) >> 12   # OVDR comp
    st.gcomp = (st.gcomp * T.LG[i]) >> 12                             # v6.7: LG, the level by frequency
    st.w2 = (T.VP_W2[res] * st.ocomp) >> 12                            # v7.4: the VCA pair's RES path (OVDR swamps it)
    v = st.veg if st.vatt >= T.ONE30 else mul30(st.veg, st.vatt)        # SATK (none: v6.1 exactly)
    tgt = (v >> 16) + ((vin * st.accvg) >> 6)                          # Q14; v7.8: + I27 / I_Q31 (pin 1); ACCV
    if st.gmode:                                                       # v6.5: the 303's gate
        st.glvl += mulq15((32767 if st.gate else 0) - st.glvl, T.GATE_K)
        tgt = mulq15(tgt, st.glvl)                                     # v7.8: exact, tgt can pass 2^16
    st.ampstep = (tgt - st.amp) >> 4

def sample(st):
    if st.fmq:                                       # FM: the last VCA sample moves the cutoff, per sample
        st.flp += (st.ovca - st.flp) >> 2              # v9.1: through a one-pole, 1/4 a sample (~2 kHz): extreme FM
        s = clamp(st.sctrl + ((((st.flp >> 8) * st.fmq)) >> 12), 0, T.S_MAX - 1)   # stays wild, not TV static
                                                     # (Marko's choice by ear, 25 Nov 2026, prova2 C)
        i = s >> 6
        st.b = LB[i]; st.c1 = (LB[i] * T.TB_C1R) >> 12
        st.k = kfb(i, st.kmul, st.ud)
        clset(st, i)                                 # v7.3
    inc = st.inc
    ph = st.phase = (st.phase + inc) & M32
    if st.wave == 0:
        x = (ph >> 11) - (1 << 20)
        x -= blep(ph, inc) << 5
    else:
        # v7.6: Q8's square (o3q8.py): the cycle's smooth part from a table (128 points, linear) plus its one hard
        # edge, at the saw's reset, as sqk times the saw (with the saw's polyBLEP)
        s_ = (ph >> 11) - (1 << 20)
        s_ -= blep(ph, inc) << 5
        row = T.SQC[st.sqi]; i = ph >> 25; fr = (ph >> 10) & 0x7FFF
        c0 = row[i]; c1 = row[(i + 1) & 127]
        x = ((c0 + (chk((c1 - c0) * fr, 'sqi') >> 15)) << 5) + fm(s_, st.sqk, 7, 8, 'sqk')
        st.sql += fm(clamp(x - st.sql, -T.SQL_DLIM, T.SQL_DLIM), T.TB_SQLP, 4, 11, 'sqlp')   # softer edges than Q8's alone;
                                                     # v7.6 review: the step clamped so the multiply fits 32 bits
        x = st.sql                                           # (fitted, as v6.9; claude/OCTA303_v76_Q8_studio.md)
    st.hp += fm(x - st.hp, T.TB_PREHP, 4, 11, 'prehp')
    if st.ginq15:                                    # OVDR up to normal: v6.1's product, exactly
        x = fm(x - st.hp, st.gin, 7, 8, 'gin')
    else:                                            # overdrive, to 66.6x
        x = fm(x - st.hp, st.gin, 6, 4, 'gin')
    if st.swp < 2:                                   # SWP 1/0: the analogue noise floor, ~-84 dB, so
        if st.nz == 0: st.nz = 0x1D872B41              # (a Galois LFSR never leaves 0: seed it)
        st.nz = (st.nz >> 1) ^ (0xD0000001 if st.nz & 1 else 0)   # the filter can self-oscillate with no VCO
        x += 64 if st.nz & 1 else -64
    y4 = st.y4
    st.fb += fm(y4 - st.fb, T.TB_FBHP, 4, 11, 'fbhp')
    fb = clamp(y4 - st.fb, -(1 << 23), 1 << 23)
    y0 = ladder_clip(st, x - chk((fb >> 8) * st.k, 'kfb'))   # v7.3: eased at the top (#1011)
    st.y1 += fm(y0 - st.y1 + st.y2, st.c1, 7, 8, 'l1')
    st.y2 += fm(st.y1 - 2 * st.y2 + st.y3, st.b, 7, 8, 'l2')
    st.y3 += fm(st.y2 - 2 * st.y3 + y4, st.b, 7, 8, 'l3')
    st.y4 = y4 + fm(st.y3 - 2 * y4, st.b, 7, 8, 'l4')
    # v7.4: the output is the loop's high-pass (the circuit has one, C25/C27 into Q21, for both), then the VCA's
    # input pair: R121/C21 (72 Hz) from it, R122/C22 (156 Hz) from the RES wiper (weight 2.2 x RES)
    st.vp1 += fm(fb - st.vp1, T.VP_HP1, 4, 11, 'vp1')
    st.vp2 += fm(fb - st.vp2, T.VP_HP2, 4, 11, 'vp2')
    x = (fb - st.vp1) + ((((fb - st.vp2) >> 6) * st.w2) >> 6)
    o = fm(x, st.gcomp, 6, 6, 'gc')
    # v7.6: the VCA is an OTA (IC15 BA6110); its input sees ~3 % of the filter (220k || 100k into R124 2.2k), in the
    # pair's tanh region: OTA_V * softclip(o / OTA_V), the engine's soft clip
    o = clamp(o, -T.OTA_LIM, T.OTA_LIM)
    o = fm(softclip(fm(o, T.OTA_IN, 4, 8, 'otai')), T.OTA_OUT, 4, 11, 'otao')
    o = clamp(o, -T.VCA_LIM, T.VCA_LIM)              # v6.9: the VCA multiply never wraps
    st.amp += st.ampstep
    if st.amp < 0: st.amp = 0
    o = fm(o, st.amp >> 1, 7, 6, 'amp')              # v7.3: four times the room (#1011; v6.9-v7.1: amp, 6, 8)
    if T.P6_ON:                                      # v7.7: the BA662A's pin 6 hits the supply (o3tables P6_*)
        if o < 0: a, K, F = min(-o, T.P6_AMAX), T.P6_K, T.P6_F   # beyond P6_AMAX the table is flat anyway
        else: a, K, F = min(o, T.P6_AMAX), T.P6_KP, T.P6_FP      # v7.8: the positive side p6r x higher
        t = ((a >> 6) * K) >> 2
        i = t >> 16
        if i >= 256: v = F[256]
        else: v = F[i] + (((F[i + 1] - F[i]) * ((t & 0xFFFF) >> 1)) >> 15)
        o = -v if o < 0 else v
    if st.muff:                                      # MUFF: the bass passes, the rest is clipped
        st.mlo += fm(clamp(o - st.mlo, -T.DF_MUFF_DLIM, T.DF_MUFF_DLIM), T.DF_MUFF_LP, 4, 11, 'mlo')   # v7.3: fits 32 bits
        h = o - st.mlo
        if st.muff == 1:
            h = clamp(h, -1048576, 1048576)                      # v6.7: no overflow (softclip saturates far below)
            h = fm(softclip(fm(h, 3413, 2, 8, 'mk')), 9830, 4, 11, 'mt')     # T*softclip(h/T), T = 0.3
        else:
            h = clamp(h, -T.DF_MUFF_T, T.DF_MUFF_T)
        o = st.mlo + h
    st.ovca = o                                      # FM reads the VCA after the Muffler
    if st.dist:
        o = softclip(o * T.DIST_GAIN + T.DIST_BIAS)
        st.tone += fm(o - st.tone, T.DIST_TONE, 7, 8, 'tone')
        o = st.tone
    st.dc += fm(o - st.dc, T.TB_DCHP, 4, 11, 'dc')
    if st.osin == T.DRV_G[0]:                         # v7.7: DRIV 0 = Din Sync's VOLUME: pin 6 is the only ceiling
        return clamp(o - st.dc, -(1 << 24), 1 << 24)
    return drive(st, o - st.dc)

def drive(st, y):
    """v7.7: DRIV = VR8 past Din Sync's position into the output mixer Q33/Q34 (o3tables DRV_*): gain, then the
    soft asymmetric limit, K + (L - K) tanh((|x| - K)/(L - K)) beyond K, from a Q14 tanh table."""
    y = clamp(y, -T.DRV_YLIM, T.DRV_YLIM)
    x = ((y >> 6) * st.osin) >> 6                    # x = y * G, G Q12
    if x < 0: a, L, K, Rr = -x, T.DRV_LN, T.DRV_KN, T.DRV_RN
    else: a, L, K, Rr = x, T.DRV_LP, T.DRV_KP, T.DRV_RP
    if a > K:
        d = min(a - K, 4 * (L - K))
        t = (d * Rr) >> 6                            # 64 u in Q16
        i = t >> 16
        if i >= 256: v = T.DRV_TH[256]
        else: v = T.DRV_TH[i] + (((T.DRV_TH[i + 1] - T.DRV_TH[i]) * ((t & 0xFFFF) >> 1)) >> 15)
        a = K + (((L - K) * v) >> 14)
    return -a if x < 0 else a

def set_df(st, df):
    """dEVILish's twelve knobs (locks applied), or None: DF_NEUTRAL, the 303 of v6.1.1."""
    k = [min(v, 127) for v in (df or T.DF_NEUTRAL)]
    st.gin, st.ocomp, st.ogain = T.DF_GIN[k[0]], T.DF_OCOMP[k[0]], T.DF_OGAIN[k[0]]
    st.ginq15 = int(k[0] <= T.DF_GIN_Q15)
    st.fmq, st.trkhz = k[1] * T.DF_FM_MUL, T.DF_TRK_HZ[k[2]]
    st.vegd, st.vsus = T.DF_VEG[k[3]], T.DF_VSUS[k[3]]
    st.slide, st.adec = T.DF_SLIDE[k[4]], T.DF_ADEC[k[5]]
    st.satk = T.DF_SATK[k[6]]
    st.swp = 2 - min(k[7], 2)                        # ACID 2 (the 303), WHST 1, SELF 0
    st.spd = min(k[8], 2) + 1                        # FAST 1, NORM 2 (the 303), SLOW 3
    st.muff = min(k[9], 2)                           # OFF, SOFT, HARD
    st.cutx, st.envx = int(k[10] >= 1), int(k[11] >= 1)

def set_setup(st, setup, df):
    """v7.0: the TB-303 machine's SETUP page (o3tables.SETUP_NAMES), or None: SETUP_NEUTRAL (until v7.9, a TB303* sample).
    SLID acts only without dEVILish on the track (dEVILish's own SLID wins)."""
    k = [min(v, 127) for v in (setup or T.SETUP_NEUTRAL)]
    st.accvg = k[5]                                  # v7.8: ACCV raw, 64 = the 303
    st.fine = (k[2] - 64) * T.FINE_Q8
    st.osin = T.DRV_G[k[4]]                          # v7.7: DRIV = VR8 past Din Sync's position (o3tables DRV_*)
    st.gsel = 1 if k[1] >= 1 else 0                  # GATE: OFF / 303
    if df is None:
        st.slide = T.DF_SLIDE[k[3]]

def gate_frame(st, seq):
    """v6.5, once a frame (the frame's last call) on a 303 track: seq = (hold, step, tick, slides,
    length[, running]) as the unit reads them -- the track's AMP HOLD from the live lane, the sequencer's step
    word and tick byte, the OR of the track record's trigless-trig and trigless-lock masks (bit s =
    step s), the track's length.
    v6.5d: the gate is timed from the note's START, in ticks (gel), not from the step word: on the
    unit a START reaches the renderer about a tick after the step word moves (measured, 12 Oct 2026:
    the step-word gate closed ~1/3 of a step after the note).  Half a step = tps ticks counted
    twice (gend = tps, +2 tps a tie)."""
    hold, s, k, mask, L = seq[:5]
    run = 1 if (seq[5] if len(seq) > 5 else 1) == 1 else 0   # v7.4: the transport word (0x800065b8): 1 = running;
                                                       # 0 stopped and rewound, 2 stopped by the STOP key (STEM_REC.md)
    if not 1 <= L <= 64: L = 16
    s = s % L
    moved = s != st.lstep or k != st.ltick
    restart = st.idle >= T.GATE_IDLE                   # standing still for GATE_IDLE frames (no transport seen)
    if not run: st.stopd = 1                           # v7.4: a STOP seen; the next move while running is a PLAY
    if s != st.lstep:                                  # a new step: the last one's ticks
        if st.kmax >= 1: st.tps = st.kmax + 1
        st.kmax = 0; st.idle = 0
    elif k != st.ltick: st.idle = 0
    elif st.idle < T.GATE_IDLE: st.idle += 1
    if k > st.kmax: st.kmax = k
    st.lstep, st.ltick = s, k
    if st.tps == 0: st.tps = T.GATE_TPS0
    if moved and st.gel < 4096: st.gel += 1            # ticks since the START
    f = min(st.fcnt + 1, 4095)                         # v7.0: the frames a tick, measured
    if moved and run:                                  # v7.4: a move while stopped (STOP resets the step word) is no tick
        if st.stopd or restart or not st.fseen:        # PLAY (v7.5: also the first move a fresh state sees, the first
                                                       # PLAY after boot): the position reset and the first tick come a frame apart
            st.stopd = 0; st.fskip = T.GATE_FSKIP      # (measured under the port): neither interval is a tick, and
            st.gel = 0; st.gelf = 0                    # the last note's clock restarts (no 1-frame snap before the START)
        if st.fskip: st.fskip -= 1
        elif st.fseen: st.fpt = f
    if moved: st.fseen = 1; f = 0
    st.fcnt = f
    if st.gelf < 65535: st.gelf += 1                   # v7.0: the frames since the START
    if st.gnew:                                        # a 303 START: the note's step, the clock from 0
        st.gnew = 0; st.gate = 1; st.gel = 0; st.gelf = 0
        st.gend = (7 * st.tps + 3) // 6                # v7.0: 3.5 of the step's 6 clocks, doubled (Whittle)
        cur = (s - 1) % L                              # v7.4: the step word holds the NEXT step (measured under the
        st.gstep = (cur + 1) % L if 2 * k >= st.tps else cur   # port: b2 = b4 + 1): the note's step is one less
    if not st.gsel:                                    # v7.0: SETUP's GATE OFF: the AMP decides
        st.gmode = 0; st.glvl = 32767; return
    st.gmode = 1
    if st.idle >= T.GATE_IDLE:                         # the sequencer stopped: the AMP decides
        st.gate = 1; return
    due = (2 * st.gelf >= st.gend * st.fpt) if st.fpt else (2 * st.gel >= st.gend)
    if st.gate and due:                                # 3.5 clocks (+ a step a tie) since the START
        nxt = (st.gstep + 1) % L
        if (mask >> nxt) & 1:                          # the next step slides: still on
            st.gstep = nxt; st.gend += 2 * st.tps
        else:
            st.gate = 0

def render_call(st, w, start, code, n, alive=True, df=None, last=None, seq=None, setup=None):
    """One sy_render call: w = the record's six words as the call found them, start = this is the
    frame's last call (end == 16) and the packer's START bit is set, code = the new voice's carrier
    (SETUP's WAVE on the machine; -1 = not ours), n = the samples this call ships, alive = the CF voice byte,
    df = dEVILish's twelve knobs on this track or None (no dEVILish there).
    Returns None (stock's samples stand) or n output longs (written to L and R)."""
    if start and code >= 0:
        set_df(st, df)                               # SATK decides how the note starts
        set_setup(st, setup, df)                     # v7.0: FINE decides where it starts
    if start:
        if code >= 0:
            note_on(st, code, w); st.latched = 1
        else:
            st.latched = 0
    if st.latched and last and seq is not None:    # v7.0: SETUP's GATE (v6.5's gate, Whittle's length),
        set_df(st, df); set_setup(st, setup, df)     # once a frame, after o3_params, whatever the voice
        gate_frame(st, seq)
    if not st.latched or not alive or n == 0:
        return None
    set_df(st, df)
    set_setup(st, setup, df)
    st.ptgt = clamp(p_of_word(w[0]) + st.fine, T.P_LO, T.P_HI)        # v7.0: FINE
    st.cut, st.res, st.env, st.dec = raw(w[1]), raw(w[2]), raw(w[3]), raw(w[4])
    out = []
    for _ in range(n):
        st.cs -= 1
        if st.cs == 0:
            st.cs = T.CS; ctrl(st)
        v = clamp(sample(st) >> T.SHIFT_OUT, -32767, 32767)
        out.append((v << 16) & M32)
    return out
