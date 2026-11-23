"""VCA160 references.

1. `VCA160` -- the 160 in floating point: the true-RMS detector (mean square
   through one time constant), the dB-domain threshold and ratio, a perfect
   VCA. What the module is MEASURED against, and what the manual's numbers
   are checked on.
2. `fixed()` -- vca160.asm, instruction for instruction, in integers (the
   SUPER OD model's primitives: modules/distorx/distorx_ref.py), the bus tap
   included. The gate requires the assembled code to match it bit for bit.
"""
import importlib.util
import math
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import toolpath  # noqa: E402,F401

_spec = importlib.util.spec_from_file_location("vca160_manifest", HERE / "manifest.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
_spec = importlib.util.spec_from_file_location("superod_ref_prims", HERE.parent / "distorx/distorx_ref.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)
FS = M.FS
s24, lim, a1, a0, acc, mpy, and_imm, add_imm, clb_normf = (
    P.s24, P.lim, P.a1, P.a0, P.acc, P.mpy, P.and_imm, P.add_imm, P.clb_normf)


# =============================================================================
# 1. the 160, float
# =============================================================================
def ratio_k(rati):
    """COMPRESSION knob (0..127) -> k, the fraction of the dB above threshold
    taken off: ratio = 1/(1 - k)."""
    x = min(rati / 127.0, 1.0)
    w = x * 127 / 128
    if w <= M.RATI_160 / 128:
        return M.K_160 * w * 128 / M.RATI_160
    return 1.0 + (w - M.RATI_160 / 128) * 128 / (127 - M.RATI_160)


def threshold_db(thrs):
    return M.THR_LO + min(thrs / 127.0, 1.0) * (M.THR_HI - M.THR_LO)


class VCA160:
    def __init__(self, fs=FS, THRS=96, RATI=50, OUT=64, KNEE=0, MIX=127):
        self.fs = fs
        self.alpha = 1.0 - math.exp(-1.0 / (fs * M.TAU))
        self.T = threshold_db(THRS)
        self.k = ratio_k(RATI)
        self.out_db = (OUT - 64) * M.OUT_DB / 63.5
        self.soft = KNEE != 0
        self.mix = 1.0 if MIX >= 127 else MIX / 128.0
        self.S = 0.0

    def gain_db(self, ms):
        """The detector's state -> the VCA's gain in dB (and the state)."""
        L = 10 * math.log10(max(self.S, 2.0 ** -23))
        over = L - self.T
        if self.soft:
            W = M.KNEE_DB
            d = min(max(over + W / 2, 0.0), W)
            oe = over if over > W / 2 else d * d / (2 * W)
        else:
            oe = max(over, 0.0)
        g = -self.k * oe + self.out_db
        return min(max(g, -96.0), 24.0)

    def run(self, L, R, key_ms=None):
        """key_ms: None (self), or a per-SAMPLE mean square of the key."""
        L = np.asarray(L, float); R = np.asarray(R, float)
        oL, oR, gains = np.empty_like(L), np.empty_like(R), np.empty_like(L)
        for n in range(len(L)):
            ms = (L[n] ** 2 + R[n] ** 2) / 2 if key_ms is None else key_ms[n]
            self.S += self.alpha * (ms - self.S)
            g = 10 ** (self.gain_db(ms) / 20)
            gains[n] = g
            oL[n] = L[n] + self.mix * (L[n] * g - L[n])
            oR[n] = R[n] + self.mix * (R[n] * g - R[n])
        return oL, oR, gains


# =============================================================================
# 2. the module, bit for bit
# =============================================================================
Q = M.CONSTQ
C = {k: s24(v) for k, v in Q.items() if k != "EXP_AT"}
PT = [s24(v) for v in M.PTABLE]
REC_A, REC_B, LEVEL_AT = M.REC_A, M.REC_B, M.LEVEL_AT


def tap(frames_lr):
    """dbt_tap: the block's 16 frames (32 words, L R interleaved) -> its word."""
    A = 0
    for w in frames_lr:
        A += mpy(w, w)
    return lim(A >> 5)


def bus_address(track):
    """Where track (0-based) publishes its level: payload B's half for T1..T4.
    Each track has a record of four words (BEAT COUNT LAST LEVEL)."""
    rec = REC_B + 4 * track if track < 4 else REC_A + 4 * (track - 4)
    return rec + LEVEL_AT


def block_constants(kn, bus):
    """kn: the page words as dsp_host packs them, a dict slot -> word (page 1
    words 0..5, page 2's word $c); bus: {address: word}."""
    st = {}
    w = lambda k: kn[k] & 0x7FFFFF

    def stretch(word):
        return lim(acc(word) + mpy(word, C["STRETCH"]))
    x = stretch(w(0))
    st["T"] = lim(acc(C["THLO"]) + mpy(x, C["THSPAN"]))
    # RATI
    wr = w(1)
    k160 = lim(mpy(wr, C["K1"]))
    A = acc(wr) - acc(C["WRAT"])
    A = mpy(lim(A), C["K2Q"]) << 2
    A = add_imm(A, 0x400000)
    k160a = lim(A)
    st["kh"] = k160 if acc(wr) - acc(C["WRAT"]) <= 0 else k160a
    # OUT
    A = acc(w(2)) - acc(0x400000)
    st["OUTb"] = lim(mpy(lim(A), C["OUTK"]))
    # KNEE
    st["soft"] = (kn[0xc] & 0x7F0000) >> 16 != 0
    # MIX
    m = kn[4] & 0x7F0000
    st["mix"] = 0x7FFFFF if m == 0x7F0000 else m
    # KEY
    key = (kn[3] & 0x7F0000) >> 16
    st["keyon"] = 1 <= key <= 8
    t = (key - 1) & 7
    addr = (0x037FE0 if t > 3 else 0x03FFF0) + 4 * t + LEVEL_AT   # the record's LEVEL word
    st["keyword"] = bus.get(addr, 0)
    return st


def fixed(Lq, Rq, kn_words, bus_per_block=None, frames=16, state=None):
    """Bit-exact render. kn_words: dict slot -> page word (or a list of such
    dicts, one per block). bus_per_block: list of {address: word} (the bus as
    the proc reads it in that block), or None (all zeros)."""
    Lq = [int(v) for v in Lq]; Rq = [int(v) for v in Rq]
    n = len(Lq)
    S = state or {"hi": 0, "lo": 0}
    outL, outR = [0] * n, [0] * n
    per_block = isinstance(kn_words, list)
    for b0 in range(0, n, frames):
        bi = b0 // frames
        kn = kn_words[bi] if per_block else kn_words
        bus = bus_per_block[bi] if bus_per_block is not None else {}
        st = block_constants(kn, bus)
        for i in range(b0, min(n, b0 + frames)):
            A = mpy(Lq[i], Lq[i]) + mpy(Rq[i], Rq[i])
            ms = lim(A >> 1)
            if st["keyon"]:
                ms = st["keyword"]
            A = acc(ms) - acc(S["hi"])
            Bv = mpy(lim(A), C["ALPHA"])
            A = ((S["hi"] << 24) | S["lo"]) + Bv
            if A < acc(1):
                A = acc(1)
            S["hi"], S["lo"] = a1(A), a0(A)
            e, A = clb_normf(A)
            A = (A - acc(0x400000)) << 1
            u = a1(A)
            idx = u >> 18
            frac = lim(acc(u & 0x3FFFF) << 5)
            t0, t1 = PT[idx], PT[idx + 1]
            A = acc(t0) + mpy(frac, lim(acc(t1) - acc(t0)))
            A = A + (acc(e) << 18)
            # the knee
            A = A - acc(st["T"])
            over = lim(A)
            A = A + acc(C["W2"])
            if A < 0:
                A = 0
            if A > acc(C["W32"]):
                A = acc(C["W32"])
            d = lim(A)
            A = mpy(lim(mpy(d, d)), C["IW8"]) << 3
            soft = lim(A)
            oe_soft = acc(over) if acc(over) > acc(C["W2"]) else acc(soft)
            oe_hard = acc(over) if over >= 0 else 0
            oe = lim(oe_soft) if st["soft"] else lim(oe_hard)
            # g
            A = -mpy(oe, st["kh"]) + acc(st["OUTb"])
            if A < acc(C["TMIN"]):
                A = acc(C["TMIN"])
            if A > acc(C["TMAX"]):
                A = acc(C["TMAX"])
            g = lim(A)
            nexp = a1(acc(g) >> 18)
            cnt = -(nexp + 1)
            u = g & 0x3FFFF
            idx = u >> 13
            frac = lim(acc(u & 0x1FFF) << 10)
            t0, t1 = PT[Q["EXP_AT"] + idx], PT[Q["EXP_AT"] + idx + 1]
            mant = lim(acc(t0) + mpy(frac, lim(acc(t1) - acc(t0))))

            def vca(x):
                A = mpy(x, mant)
                A = P._w56(A << -cnt) if cnt < 0 else (A >> cnt)
                return lim(A)
            wl, wr_ = vca(Lq[i]), vca(Rq[i])
            for src, dst, wet in ((Lq, outL, wl), (Rq, outR, wr_)):
                dv = src[i]
                A = (acc(wet) - acc(dv)) >> 1
                A = (mpy(lim(A), st["mix"]) << 1) + acc(dv)
                dst[i] = lim(A)
    return outL, outR, S


def page_words(THRS=96, RATI=50, OUT=64, KEY=0, MIX=127, KNEE=0, frac=0):
    """The page words dsp_host / the frame builder write for these knobs."""
    kn = {k: 0 for k in range(16)}
    for slot, v in enumerate((THRS, RATI, OUT, KEY, MIX, 0)):
        kn[slot] = ((v & 0x7F) << 16) | ((frac & 0xFF) << 8)
    kn[0xc] = (KNEE & 0xFF) << 16
    return kn
