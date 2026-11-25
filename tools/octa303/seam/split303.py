"""ref303 cut in two at the hybrid seam (coordination, 19 Nov 2026; v9.1, 25 Nov 2026: the whole voice after u).
cf_front(st) = everything up to u (the oscillator, the input highpass, OVDR's gain, the noise when SWP < 2);
dsp_chain(st, u) = the rest of sample(): FM's coefficients (from the last VCA word, smoothed), the loop, the ladder,
the VCA, pin 6, MUFF, DIST, the output coupling and DRIV.  FM's block moves to the chain's start: it reads only the
last sample's VCA word and writes only the ladder's coefficients, which nothing before u reads.
The integer arithmetic is ref303's own, copied line for line; split_sample(st) == ref303.sample(st) is checked."""
import os, sys
D = os.environ.get('REF303_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, D)
import ref303 as R, o3tables as T
from ref303 import fm, clamp, chk, softclip, ladder_clip, blep, kfb, clset, LB, M32

PEAK = {}
def pk(tag, v):
    a = abs(v)
    if a > PEAK.get(tag, 0): PEAK[tag] = a
    return v

def cf_front(st):
    inc = st.inc
    ph = st.phase = (st.phase + inc) & M32
    if st.wave == 0:
        x = (ph >> 11) - (1 << 20)
        x -= blep(ph, inc) << 5
    else:
        s_ = (ph >> 11) - (1 << 20)
        s_ -= blep(ph, inc) << 5
        row = T.SQC[st.sqi]; i = ph >> 25; fr = (ph >> 10) & 0x7FFF
        c0 = row[i]; c1 = row[(i + 1) & 127]
        x = ((c0 + (chk((c1 - c0) * fr, 'sqi') >> 15)) << 5) + fm(s_, st.sqk, 7, 8, 'sqk')
        st.sql += fm(clamp(x - st.sql, -T.SQL_DLIM, T.SQL_DLIM), T.TB_SQLP, 4, 11, 'sqlp')
        x = st.sql
    st.hp += fm(x - st.hp, T.TB_PREHP, 4, 11, 'prehp')
    if st.ginq15:
        x = fm(x - st.hp, st.gin, 7, 8, 'gin')
    else:
        x = fm(x - st.hp, st.gin, 6, 4, 'gin')
    if st.swp < 2:
        if st.nz == 0: st.nz = 0x1D872B41
        st.nz = (st.nz >> 1) ^ (0xD0000001 if st.nz & 1 else 0)
        x += 64 if st.nz & 1 else -64
    return x

def dsp_chain(st, x, peaks=False):
    P = pk if peaks else (lambda t, v: v)
    P('u', x)
    if st.fmq:                                       # FM (v9.1: smoothed), per sample
        st.flp += (st.ovca - st.flp) >> 2; P('flp', st.flp)
        d = ((st.flp >> 8) * st.fmq) >> 12; P('fmdev', d)
        s = clamp(st.sctrl + d, 0, T.S_MAX - 1)
        i = s >> 6
        st.b = LB[i]; st.c1 = (LB[i] * T.TB_C1R) >> 12
        P('lkm', (R.LK[i] * st.kmul) >> 15)
        st.k = kfb(i, st.kmul, st.ud)
        clset(st, i)
    y4 = st.y4
    st.fb += fm(y4 - st.fb, T.TB_FBHP, 4, 11, 'fbhp'); P('fbst', st.fb)
    fb = clamp(y4 - st.fb, -(1 << 23), 1 << 23); P('fb', fb)
    kx = chk((fb >> 8) * st.k, 'kfb'); P('kfb', kx); P('k', st.k)
    P('lin', x - kx)
    y0 = ladder_clip(st, x - kx); P('y0', y0)
    st.y1 += fm(y0 - st.y1 + st.y2, st.c1, 7, 8, 'l1'); P('y1', st.y1)
    st.y2 += fm(st.y1 - 2 * st.y2 + st.y3, st.b, 7, 8, 'l2'); P('y2', st.y2)
    st.y3 += fm(st.y2 - 2 * st.y3 + y4, st.b, 7, 8, 'l3'); P('y3', st.y3)
    st.y4 = y4 + fm(st.y3 - 2 * y4, st.b, 7, 8, 'l4'); P('y4', st.y4)
    P('c1', st.c1); P('b', st.b)
    st.vp1 += fm(fb - st.vp1, T.VP_HP1, 4, 11, 'vp1'); P('vp1', st.vp1)
    st.vp2 += fm(fb - st.vp2, T.VP_HP2, 4, 11, 'vp2'); P('vp2', st.vp2)
    x = (fb - st.vp1) + ((((fb - st.vp2) >> 6) * st.w2) >> 6); P('vpx', x); P('w2', st.w2)
    o = fm(x, st.gcomp, 6, 6, 'gc'); P('gc', o); P('gcomp', st.gcomp)
    o = clamp(o, -T.OTA_LIM, T.OTA_LIM)
    o = fm(softclip(fm(o, T.OTA_IN, 4, 8, 'otai')), T.OTA_OUT, 4, 11, 'otao'); P('ota', o)
    o = clamp(o, -T.VCA_LIM, T.VCA_LIM)
    st.amp += st.ampstep
    if st.amp < 0: st.amp = 0
    P('amp', st.amp); P('ampstep', st.ampstep)
    o = fm(o, st.amp >> 1, 7, 6, 'amp'); P('vca', o)
    if T.P6_ON:
        if o < 0: a, K, F = min(-o, T.P6_AMAX), T.P6_K, T.P6_F
        else: a, K, F = min(o, T.P6_AMAX), T.P6_KP, T.P6_FP
        t = ((a >> 6) * K) >> 2
        i = t >> 16
        if i >= 256: v = F[256]
        else: v = F[i] + (((F[i + 1] - F[i]) * ((t & 0xFFFF) >> 1)) >> 15)
        o = -v if o < 0 else v
    P('p6', o)
    if st.muff:                                      # MUFF: the bass passes, the rest is clipped
        P('mlod', o - st.mlo)
        st.mlo += fm(clamp(o - st.mlo, -T.DF_MUFF_DLIM, T.DF_MUFF_DLIM), T.DF_MUFF_LP, 4, 11, 'mlo'); P('mlo', st.mlo)
        h = o - st.mlo; P('mh', h)
        if st.muff == 1:
            h = clamp(h, -1048576, 1048576)
            h = fm(softclip(fm(h, 3413, 2, 8, 'mk')), 9830, 4, 11, 'mt')
        else:
            h = clamp(h, -T.DF_MUFF_T, T.DF_MUFF_T)
        o = st.mlo + h; P('muff', o)
    st.ovca = o                                      # FM reads the VCA after the Muffler
    if st.dist:
        o = softclip(o * T.DIST_GAIN + T.DIST_BIAS)
        st.tone += fm(o - st.tone, T.DIST_TONE, 7, 8, 'tone'); P('tone', st.tone)
        o = st.tone
    st.dc += fm(o - st.dc, T.TB_DCHP, 4, 11, 'dc'); P('dcst', st.dc)
    if st.osin == T.DRV_G[0]:
        return P('out', clamp(o - st.dc, -(1 << 24), 1 << 24))
    y = clamp(o - st.dc, -T.DRV_YLIM, T.DRV_YLIM)
    P('drvx', ((y >> 6) * st.osin) >> 6)
    return P('drv', R.drive(st, o - st.dc))

def split_sample(st, peaks=False):
    return dsp_chain(st, cf_front(st), peaks)
