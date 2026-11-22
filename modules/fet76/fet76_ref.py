"""FET76 references.

1. `FET76` -- the 1176LN in floating point (the circuit's equations, the loop linearised as the DSP does it;
   method="exact" solves it exactly). What the module is MEASURED against, and what the examples were made with.
2. `fixed()` -- fet76.asm, instruction for instruction, in integers (the SUPER OD model's primitives:
   modules/distorx/distorx_ref.py). The gate requires the assembled code to match it bit for bit.
"""
import math
import numpy as np

FS = 44100.0
CA, CB = 0.022e-6, 0.22e-6           # C27, C22 (manual, Fig. 5)
RX = 220e3                           # ASSUMED: the coupling of the two capacitors
ATK_FAST, ATK_SLOW = 20e-6, 800e-6   # manual: attack 20 .. 800 us
REL_FAST, REL_SLOW = 0.050, 1.1      # manual: release 50 ms .. 1.1 s
# The loop's ratio is (1 + T + 2u) / (1 + u): 1 + T at the threshold, falling towards 2:1 deep in (the FET's
# 1/Vov law). The buttons' "4, 8, 12, 20" are taken as the AVERAGE over the first 10 dB of gain reduction:
# T = 2.162 / (10 ** (10 / (ratio - 1) / 20) - 1). So the knee is softer at 4:1 and harder at 20:1 (Moore, Fig. 1).
def _t_for(ratio): return 2.162 / (10 ** (10.0 / (ratio - 1) / 20) - 1)
BUTTONS = {                          # T (diode bias), threshold (dBFS peak at INPT 64, ASSUMED)
    "4": (_t_for(4), -20.0), "8": (_t_for(8), -17.0), "12": (_t_for(12), -15.0), "20": (_t_for(20), -13.0),
}
T_ALL = _t_for(16)                   # UA: "somewhere between 12:1 and 20:1"
RATIO_NAMES = ("4", "8", "12", "20", "ALL")
EPS_LN, EPS_BLUE = 0.06, 0.35        # ASSUMED: the FET's Vds^2 residue with and without the LN network
EPS_CAP = 0.5                        # ... and ALL's x8, capped
D_SCALE = 0.5                        # ASSUMED: the residue's size (sets the THD at limiting, < 0.5 % per the manual)
E_MAX = 6.0                          # ASSUMED: the side-chain amplifier's swing (Q7-Q10 run into their rails), in u units:
                                     # without it a big step would charge C27 at once and ATK would not matter


def knob_db(v):
    """INPT / OUTP 0..127 -> -30 .. +30 dB (64 = 0 dB)."""
    return (v - 64) * 30.0 / 63.5


def attack_tau(atk):
    """ATK 1..127 -> 800 us .. 20 us, log (the 1176's dial 1 .. 7). 0 = off."""
    k = (atk - 1) / 126.0
    return ATK_SLOW * (ATK_FAST / ATK_SLOW) ** k


def release_tau(rel):
    """REL 0..127 -> 1.1 s .. 50 ms, log (held compression)."""
    k = rel / 127.0
    return REL_SLOW * (REL_FAST / REL_SLOW) ** k


def button(ratio):
    if ratio == "ALL":
        S = sum(T / 10 ** (thr / 20) for T, thr in BUTTONS.values())
        return S, T_ALL
    T, thr = BUTTONS[ratio]
    return T / 10 ** (thr / 20), T


class FET76:
    def __init__(self, fs=FS, INPT=64, OUTP=64, ATK=100, REL=64, RATIO="20", MIX=127, REV="LN", method="dsp"):
        self.fs = fs
        self.method = method
        self.gin = 10 ** (knob_db(INPT) / 20)
        self.gout = 10 ** (knob_db(OUTP) / 20)
        self.on = ATK > 0
        allb = RATIO == "ALL"
        self.S, self.T = button(RATIO)
        tau_a = attack_tau(max(ATK, 1)) * (3.0 if allb else 1.0)
        self.ka = 1 - math.exp(-1 / (fs * tau_a))
        rr = release_tau(REL) / (CA + CB)                          # Rr from the held-compression time
        self.kxa = 1 - math.exp(-1 / (fs * RX * CA))               # A -> B through Rx, seen from A
        self.kxb = 1 - math.exp(-1 / (fs * RX * CB))               # ... and from B
        self.kr = 1 - math.exp(-1 / (fs * rr * CB))                # B released through Rr
        self.eps = min((EPS_BLUE if REV == "BLUE" else EPS_LN) * (8.0 if allb else 1.0), EPS_CAP)
        self.mix = MIX / 127.0
        self.uA = 0.0
        self.uB = 0.0
        self.kdc = 1 - math.exp(-2 * math.pi * 8.0 / fs)          # the coupling capacitors: the residue has no DC
        self.mL = self.mR = 0.0

    @staticmethod
    def ceiling(y):
        # the class-A output stage: 0.5 % THD at full scale (+22 dBm, manual), then it runs out of swing
        # (limited first, as the DSP: the cubic alone would fold back over 7x full scale)
        y = min(max(y, -1.0), 1.0)
        return y - 0.02 * y * y * y

    def run(self, L, R=None):
        L = np.asarray(L, float); R = L if R is None else np.asarray(R, float)
        n = len(L); oL = np.empty(n); oR = np.empty(n); gr = np.empty(n)
        S, T, ka, kxa, kxb, kr = self.S, self.T, self.ka, self.kxa, self.kxb, self.kr
        uA, uB, gin, eps = self.uA, self.uB, self.gin, self.eps
        for i in range(n):
            aL, aR = L[i] * gin, R[i] * gin
            A = max(abs(aL), abs(aR))
            # the two capacitors share their charge through Rx, B leaks through Rr (explicit: slow)
            d = uA - uB
            uA -= d * kxa
            uB += d * kxb - uB * kr
            if self.on:
                # the diode charges A when the rectified output S|y| - T is above it; y = A / (1 + u). The loop is
                # closed inside the sample: u' = (1-ka) uA + ka (S A G(u') - T), with G linearised at uA:
                #   w = ka S A G0^2,  lam = w / (1 + w),  u' = (1-lam)((1-ka) uA - ka T) + lam (1 + 2 uA)
                # (one division, no square root: what the DSP does; method="exact" solves the quadratic)
                g0 = 1.0 / (1.0 + uA)
                if S * A * g0 - T > uA:
                    if self.method == "exact":
                        B = (1 - ka) * uA - ka * T
                        u = 0.5 * (-(1 - B) + math.sqrt((1 - B) ** 2 + 4 * (B + ka * S * A)))
                    else:
                        w = ka * S * A * g0 * g0
                        lam = w / (1 + w)
                        u = (1 - lam) * ((1 - ka) * uA - ka * T) + lam * (1 + 2 * uA)
                    if u > (1 - ka) * uA + ka * E_MAX:                 # the side chain's rail
                        u = (1 - ka) * uA + ka * E_MAX
                    uA = max(u, uA)
            g = 1.0 / (1.0 + uA)
            # the FET's square-law residue: an even harmonic that grows with gain reduction
            dist = eps * D_SCALE * uA * g * g * g
            eL, eR = dist * aL * aL, dist * aR * aR
            self.mL += (eL - self.mL) * self.kdc; self.mR += (eR - self.mR) * self.kdc
            vL = aL * g + eL - self.mL
            vR = aR * g + eR - self.mR
            yL = self.ceiling(vL * self.gout)
            yR = self.ceiling(vR * self.gout)
            oL[i] = L[i] + self.mix * (yL - L[i])
            oR[i] = R[i] + self.mix * (yR - R[i])
            gr[i] = g
        self.uA, self.uB = uA, uB
        return oL, oR, gr


# =============================================================================
# 2. the module, bit for bit
# =============================================================================
import importlib.util as _ilu
import pathlib as _pl
_HERE = _pl.Path(__file__).resolve().parent
sys_path_added = False
import sys as _sys
_sys.path.insert(0, str(_HERE.parents[1] / "tools"))
import toolpath  # noqa: E402,F401
_spec = _ilu.spec_from_file_location("fet76_manifest", _HERE / "manifest.py")
M = _ilu.module_from_spec(_spec); _spec.loader.exec_module(M)
_spec = _ilu.spec_from_file_location("superod_ref_prims", _HERE.parent / "distorx/distorx_ref.py")
P = _ilu.module_from_spec(_spec); _spec.loader.exec_module(P)
s24, lim, a1, a0, acc, mpy, clb_normf, _w56 = P.s24, P.lim, P.a1, P.a0, P.acc, P.mpy, P.clb_normf, P._w56
Q = M.CONSTQ
C = {k: s24(v) for k, v in Q.items() if not k.endswith("_AT")}
PT = [s24(v) for v in M.PTABLE]


def normf(A, cnt):
    """normf cnt,a: right by cnt (> 0), left by -cnt (< 0)."""
    return _w56(A << -cnt) if cnt < 0 else (A >> cnt)


def div24(num, den):
    """f76_div: andi #$fe,ccr / do #24 div x0,a / move a0,y1; 0 <= num < den."""
    assert 0 <= num < den, (num, den)
    return (num << 23) // den


def tab(word, base):
    """f76_tab: the P table at base + (word >> 18), interpolated by the low 18 bits."""
    idx = (word >> 18) + base
    frac = lim(acc(word & 0x3FFFF) << 5)
    t0, t1 = PT[idx], PT[idx + 1]
    return acc(t0) + mpy(frac, lim(acc(t1) - acc(t0)))


def exp2(A):
    """f76_exp: a = g (bits/32) -> (mantissa, normf count)."""
    g = lim(A)
    n = g >> 18
    cnt = -(n + 1)
    u = g & 0x3FFFF
    idx = u >> 13
    frac = lim(acc(u & 0x1FFF) << 10)
    t0, t1 = PT[Q["EXP_AT"] + idx], PT[Q["EXP_AT"] + idx + 1]
    mant = lim(acc(t0) + mpy(frac, lim(acc(t1) - acc(t0))))
    return mant, cnt


def block_constants(kn):
    """The per-block decode, from the page words kn[slot] (value << 16 | frac)."""
    st = {}
    for slot, gm, gc, off in ((0, "GINm", "GINc", "GINOFF"), (1, "GOm", "GOc", "GOUTOFF")):
        w = kn.get(slot, 0) & 0x7FFFFF
        x = lim(acc(w) - acc(0x400000))
        A = mpy(x, C["GK"]) + acc(C[off])
        st[gm], st[gc] = exp2(A)
    c = st["GOc"]                                 # split: no normf left by more than 7 (the guard bits)
    st["GOc"], st["GOc2"] = max(c, -7), c - max(c, -7)
    v = (kn.get(4, 0) & 0x7F0000) >> 16
    v = min(v, 4)
    row = Q["BTN_AT"] + 8 * v
    st["YT"], st["IS4"], st["SW"], st["T64"] = PT[row], PT[row + 1], PT[row + 2], PT[row + 3]
    abishift, abi = PT[row + 4], PT[row + 5]
    w = (kn.get(2, 0) & 0x7FFFFF) - abishift
    if w < 0x010000:
        w = 0x010000
    st["ka"] = lim(tab(w, Q["KA_AT"]))
    if (kn.get(2, 0) & 0x7F0000) == 0:
        st["YT"] = 0x7FFFFF                       # OFF
    st["kr"] = lim(tab(kn.get(3, 0) & 0x7FFFFF, Q["KR_AT"]))
    blue = 1 if (kn.get(0xc, 0) & 0x7F0000) else 0
    st["eps"] = PT[Q["EPS_AT"] + blue + 2 * abi]
    m = kn.get(5, 0) & 0x7F0000
    st["mix"] = 0x7FFFFF if m == 0x7F0000 else m
    return st


def _chan(a32, m, st, DZ2, g2):
    """f76_chan."""
    A = mpy(a32, a32)
    A = mpy(lim(A), DZ2) << 1
    e = lim(A)
    d = lim(acc(e) - acc(m))
    m = lim(acc(m) + mpy(d, C["KDC"]))
    A = acc(e) - acc(m)
    A = A + mpy(a32, g2) + mpy(a32, g2)
    v = lim(A)
    A = normf(mpy(v, st["GOm"]), st["GOc"])
    z = lim(normf(acc(lim(A)), st["GOc2"]))
    z2 = lim(mpy(z, z))
    z3 = lim(mpy(z, z2))
    A = acc(z) - mpy(z3, C["C002"])
    return lim(A), m


def init_state():
    return {"uA": 0, "uB": 0, "g2": 0x400000, "mL": 0, "mR": 0}


def fixed(Lq, Rq, kn_words, frames=16, state=None, trace=None):
    """Bit-exact render. kn_words: dict slot -> page word (or a list of such dicts, one per block)."""
    Lq = [int(v) for v in Lq]; Rq = [int(v) for v in Rq]
    n = len(Lq)
    S = state or init_state()
    outL, outR = [0] * n, [0] * n
    per_block = isinstance(kn_words, list)
    for b0 in range(0, n, frames):
        kn = kn_words[b0 // frames] if per_block else kn_words
        st = block_constants(kn)
        for i in range(b0, min(n, b0 + frames)):
            aL = lim(normf(mpy(Lq[i], st["GINm"]), st["GINc"]))
            aR = lim(normf(mpy(Rq[i], st["GINm"]), st["GINc"]))
            AL, AR = abs(acc(aL)), abs(acc(aR))
            Abig = AL if AR < AL else AR
            Aw = lim(Abig)
            # C27 <-> C22
            uA, uB = S["uA"], S["uB"]
            d = lim(acc(uA) - acc(uB))
            uA = lim(acc(uA) - mpy(d, C["KXA"]))
            uB = lim(acc(uB) + mpy(d, C["KXB"]) - mpy(uB, st["kr"]))
            # charge test
            g2 = S["g2"]
            A = mpy(Aw, g2) << 1
            yG = lim(A)
            t = lim(A - acc(st["YT"]))
            # lam
            yGG = lim(mpy(yG, g2) << 1)
            kyGG = lim(mpy(yGG, st["ka"]))
            W = mpy(kyGG, st["SW"])
            hi, lo = a1(W), a0(W)
            den = W + acc(0x000200)
            e, dn = clb_normf(den)
            dx = lim(dn)
            A = (acc(hi) | lo)
            A = normf(A, e)
            num = a1(A)
            lam = div24(num, dx)
            # u'
            A = acc(uA) - mpy(uA, st["ka"])
            A = A >> 2
            A = A - mpy(st["T64"], st["ka"]) - mpy(st["T64"], st["ka"])
            c32 = lim(A)
            A = acc(c32) - mpy(c32, lam)
            B = A << 2
            h = lim(acc(uA) + acc(0x080000))
            B = B + mpy(h, lam) + mpy(h, lam)
            A = acc(uA) - mpy(uA, st["ka"]) + mpy(C["EMAX8"], st["ka"])
            if B > A:
                B = A
            if B < acc(uA):
                B = acc(uA)
            unew = lim(B)
            rhs = mpy(uA, st["IS4"])
            if acc(t) > rhs:
                uA = unew
            # G
            g2 = div24(0x080000, uA + 0x100000)
            # DZ/2
            q = lim(mpy(g2, g2)); q = lim(mpy(q, g2)); q = lim(mpy(q, uA))
            DZ2 = lim(mpy(q, st["eps"]) << 9)
            wl, S["mL"] = _chan(aL, S["mL"], st, DZ2, g2)
            wr, S["mR"] = _chan(aR, S["mR"], st, DZ2, g2)
            S["uA"], S["uB"], S["g2"] = uA, uB, g2
            if trace is not None:
                trace.append((uA, uB, g2, lam))
            for src, dst, wet in ((Lq, outL, wl), (Rq, outR, wr)):
                dv = src[i]
                A = (acc(wet) - acc(dv)) >> 1
                A = (mpy(lim(A), st["mix"]) << 1) + acc(dv)
                dst[i] = lim(A)
    return outL, outR, S


def page_words(INPT=64, OUTP=64, ATK=100, REL=64, RATI=3, MIX=127, REV=0, frac=0):
    """The page words dsp_host / the frame builder write for these knobs."""
    kn = {k: 0 for k in range(16)}
    for slot, v in enumerate((INPT, OUTP, ATK, REL, RATI, MIX)):
        kn[slot] = ((v & 0x7F) << 16) | ((frac & 0xFF) << 8)
    kn[0xc] = (REV & 0xFF) << 16
    return kn
