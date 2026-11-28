"""TUNED COMB -- the float reference the DSP is proven against
(tools/verify/verify_tuned_comb.py), and the source of the module's tables
(manifest.py loads them from here). comb.dsp beside it is the listening
prototype (continuous, per sample, solved exactly).

A feedback comb with a one-pole lowpass in the loop, on stock COMB's page
(PTCH FINE LP FB --- MIX). Stock's loop is SR/f0 samples with the lowpass
inside it, and the lowpass's lag pulls the note flat as LP closes. Here the
loop length L is solved each block so the loop's POLE sits at the sounding
fundamental: z = r e^{jw} with

    z^L (1 - a/z) = g (1 - a)          (y = b x + a y',  b = 1 - a)

FB > 0 sounds f0 (w = 2 pi f0/SR); FB < 0 sounds f0/2 (w = pi f0/SR), stock's
octave-down. With rho = a/r, X = 1 - rho cos w, Y = rho sin w and
psi = atan2(Y, X):

    phase      L = P (1 - k psi_c)      P = SR/f0, psi_c = psi/(2 pi) cycles,
                                       k = 1 (FB > 0) or 2 (FB < 0)
    magnitude  log2 r = (log2(|g| b) - log2|q|) / L,  |q|^2 = X^2 + Y^2

On a change to PTCH, FINE, LP or FB (a cold start, lr = 0): two damped
fixed-point steps, then one a block for six blocks (warm, from the last
block's lr), then the solve is frozen until the next change. Two steps from
cold are within 1.2 cents of the settled solve (0.2 at the 99th percentile),
so a moving knob (a twist, an LFO) tracks to that; held knobs cost nothing. On the
unit circle (r = 1) this is the plain phase-delay correction; a damped pole
lags more, which is why phase delay alone leaves a damped note flat.

The DSP's structure, mirrored here:
  * per block: decode the knobs (the integer and the LFO fraction), the
    pitch s = PTCH + (FINE - 64)/64 semitones above A#0, P and phi0 = 1/P
    from 2^-x (E2), sin/cos of the sounding phase from the stock sine at
    X:0x6c00 (1,024 words, interpolated), b from BLP, the solve with ATN
    (atan, in cycles), LG2 (log2 of a mantissa) and E2, and 1/L by one div:
    phi0 / (1 - k psi_c);
  * the loop length walks to the block's L in a straight line, a LOOKAHEAD'th
    of the way a sample; b and g step per block;
  * the lines: N = 1,533 words a channel plus 3 guard words mirroring words
    0..2, so the four Hermite taps read ascending without a wrap;
    L at the slot base, R at +1,536; L is clamped to LMAX;
  * per sample, each channel: v = herm(L), y += b (v - y), hp = x - dc
    (rounded) and dc += hp/1024 (the input's DC blocker, about 6.9 Hz, outside
    the loop so the pitch is untouched), s = hp + g y (truncated toward zero
    in the DSP: no limit cycle), write s,
    out = dry + m (s - dry);
  * MIX glides as VIBRATO's run: 1/8 of the way a block, in a straight line,
    snapped within 128 LSBs; 127 = 1.0, 0 = the dry exactly.
"""
import math

FS = 44100.0
BLOCK = 15          # the gates' block; the unit's is 16
LOOKAHEAD = 16
Q23 = float(1 << 23)

N = 1533            # data words a channel; +3 guard = 1,536
GUARD = 3
STRIDE = N + GUARD  # R's line at base + 1,536
LMAX = 1530.0       # i + 2 <= N - 1 for the oldest tap
LMIN = 3.0
DCB_SHIFT = 10      # the input's DC blocker: dc += hp / 2^10, about 6.9 Hz

NOTES = 96                       # A#0 .. A8
F_A_SHARP_0 = 440.0 * 2 ** ((22 - 69) / 12)
P0 = FS / F_A_SHARP_0            # 1513.6 samples
RELAX = 0.1
CHANGE_STEPS = 2    # on a change to PTCH FINE LP or FB: a cold start (lr = 0), two steps
SETTLE = 6          # ... then one warm step a block for six blocks, then frozen
HERM_FIX = True
RHO_MAX = 0x7FF000 / Q23         # rho stays under 1 (dead notes only)
G_MIN = 1 / 128                  # |g| floor for the log
G_MAX = 0x7FBE77 / Q23           # 0.998: the most per-pass gain (a positive loop at 1 runs away at DC)
# FB is a decay time: T60 = T60_MIN * T60_SPAN^d, d = |FB - 64|/63 (at most 1), the
# sign the polarity (below 64: inverted, the note an octave down); 64 is no feedback.
T60_MIN, T60_SPAN = 0.05, 600.0  # 0.05 s near the centre, 30 s at +-63 (and -64)
LOG2_SPAN = math.log2(T60_SPAN)  # 9.23 octaves of T60 over the knob
# the pole's radius per sample: log2 r = -3 log2(10) / (SR T60) = -LR0 2^(-LOG2_SPAN d)
LR0 = 3 * math.log2(10) / (FS * T60_MIN)


def _w(v):
    return max(-0x800000, min(0x7FFFFF, int(round(v * Q23))))


# ---- the tables: 33 entries at j/32 (E2: 65 at j/64), interpolated ---------------------------
E2 = tuple(_w(2 ** (-j / 64)) for j in range(65))          # 2^-x, x in [0, 1], 65 entries
LG2 = tuple(_w(math.log2(1 + j / 32) / 2) for j in range(33))  # log2(1+x)/2
ATN = tuple(_w(math.atan(j / 32) / (2 * math.pi) * 4) for j in range(33))  # 4 atan(x)/(2pi)


def lp_fc(k):
    """LP: 16 steps an octave, 20 kHz at 127 (bypassed), 81 Hz at 0"""
    return 20000.0 * 2 ** ((k - 127) / 16)


def lp_b(k):
    return 1.0 if k >= 128 else 1 - math.exp(-2 * math.pi * lp_fc(k) / FS)


BLP = tuple(_w(lp_b(4 * i)) if i < 32 else 0x7FFFFF for i in range(33))

SH = tuple(_w(2.0 ** -n) for n in range(11))                # 2^-n, n = 0..10, the shifts

TABLE = E2 + LG2 + ATN + BLP + SH
T_E2, T_LG2, T_ATN, T_BLP, T_SH = 0, 65, 98, 131, 164


def tab(table, x):
    """entry x*(len-1), interpolated; x in [0, 1]"""
    n = len(table) - 1
    u = x * n
    i = min(n - 1, int(u))
    f = u - i
    return (table[i] + f * (table[i + 1] - table[i])) / Q23


def tab_k(table, k):
    """a knob table: entry k/4 (k with its LFO fraction), interpolated"""
    i = int(k // 4)
    if i >= 32:
        return table[32] / Q23
    f = (k - 4 * i) / 4
    return (table[i] + f * (table[i + 1] - table[i])) / Q23


def exp2n(x):
    """2^-x, x >= 0: E2 on the fraction, a shift by the integer"""
    n = int(x)
    return tab(E2, x - n) / (1 << n)


def log2m(v):
    """log2 v, v > 0: normalised to [1, 2) (the DSP's norm), LG2 on the rest"""
    e = 0
    while v >= 2:
        v /= 2
        e += 1
    while v < 1:
        v *= 2
        e -= 1
    return e + 2 * tab(LG2, v - 1)


def atan2c(y, x):
    """atan2(y, x) in cycles, y >= 0, x > 0: one div, ATN, the octant swap"""
    if y <= x:
        return tab(ATN, y / x) / 4
    return 0.25 - tab(ATN, x / y) / 4


SINE = [math.sin(2 * math.pi * i / 1024) for i in range(1024)]   # stock X:0x6c00 (its words, in the gates)


def sin_c(phi):
    """the stock sine, read at phi cycles and interpolated (VIBRATO's vbs_sin)"""
    u = (phi % 1.0) * 1024
    i = int(u)
    f = u - i
    return SINE[i & 1023] + f * (SINE[(i + 1) & 1023] - SINE[i & 1023])


def knob_b(k):
    return 1.0 if k >= 127 else tab_k(BLP, k)


def fb_sign(k):
    return 0 if word(k) == 0x400000 else (-1 if k < 64 else 1)


def fb_lr(k):
    """log2 of the pole's radius a sample for FB k (k != 64), through the
    DSP's tables: 2^-y = SH[n] E2(frac), y = LOG2_SPAN d"""
    d = min(1.0, abs(word(k) - 0x400000) / (63 * 65536))
    y = LOG2_SPAN * d
    n = int(y)
    return -LR0 * SH[n] / Q23 * tab(E2, y - n)


def fb_g(k):
    return (k - 64) / 64


def word(k):
    """a knob value (with its LFO fraction) as the DSP's masked knob word"""
    return int(round(k * 65536)) & 0x7FFF00


def mix_m(k):
    return 1.0 if k >= 127 else k / 128


def pitch_P(s):
    """P = P0 2^(-s/12) and phi0 = 1/P, for s in [-1, 96] semitones above A#0"""
    u = s / 12
    o = math.floor(u)
    fr = u - o
    P = P0 * tab(E2, fr) / (2 ** o)
    phi0 = (2 / P0) * (2 ** o) * tab(E2, 1 - fr)
    return P, phi0


def rho_of(a, lr):
    """rho = a / r = a 2^y, y = -lr >= 0 = n + frac: a E2(1 - frac) 2^(n + 1),
    the shift into the guard bits, at most RHO_MAX; n >= 3 saturates (no
    note that rings has r under 0.79, so its y is under 1)"""
    y = -lr
    n = int(y)
    if n >= 3:
        return RHO_MAX if a > 0 else 0.0
    return min(RHO_MAX, a * tab(E2, 1 - (y - n)) * 2 ** (n + 1))


def setup(s, lpk, fbk, g=None):
    """the block's pitch and filter, and the loop gain g (the polarity from
    FB; g itself given, or FB's old law for the gates' comparisons)"""
    P, phi0 = pitch_P(s)
    b = knob_b(lpk)
    sign = fb_sign(fbk)
    if g is None:
        g = fb_g(fbk)
    kk = 2 if sign < 0 else 1
    phis = phi0 / kk
    sn, cs = sin_c(phis), sin_c(phis + 0.25)
    lg = log2m(max(abs(g), G_MIN) * max(b, 1e-6))
    return dict(P=P, phi0=phi0, b=b, a=1 - b, g=g, kk=kk, phis=phis, sn=sn, cs=cs, lg=lg, sign=sign)


def psi_of(c, rho):
    return atan2c(rho * c["sn"], 1 - rho * c["cs"])


def step(c, lr):
    """one damped step of the pole iteration, from lr (rho = rho_of(a, lr)):
    the new lr = (F(lr) + RELAX lr)/(1 + RELAX). It converges oscillating
    (ratio about -0.15 undamped), so the damping lands it in a few steps"""
    rho = rho_of(c["a"], lr)
    X, Y = 1 - rho * c["cs"], rho * c["sn"]
    psi = psi_of(c, rho)
    invL = c["phi0"] / (1 - c["kk"] * psi)
    lq = log2m(X * X + Y * Y) / 2
    F = min(0.0, (c["lg"] - lq) * invL)
    return (F + RELAX * lr) / (1 + RELAX)


def length(c, lr):
    """the loop length for lr: L = P (1 - k psi), less the Hermite's error"""
    rho = rho_of(c["a"], lr)
    L = c["P"] * (1 - c["kk"] * psi_of(c, rho))
    if HERM_FIX:
        L -= herm_err(L, c["phis"], c["sn"], c["cs"])
    return max(LMIN, min(LMAX, L))


def law_g(c, lr1):
    """FB's gain: the law's as if LP were open, |g| = 2^(L0 lr1) / |S|, L0 the
    loop on the lowpass's circle (rho = a), S the Hermite read's response at w
    (its loss a pass); at most G_MAX. LP closed then shortens the decay, so the
    comb's DC mode (which LP leaves alone) never rings longer than the note.
    -> (L0, |g|). With LP open (a = 0) L0 is the loop: the closed form."""
    rho = rho_of(c["a"], 0.0)
    L0 = c["P"] * (1 - c["kk"] * psi_of(c, rho))
    lgg = L0 * lr1
    if HERM_FIX:
        # S where the read is once its own phase error is out: the loss a pass
        err = herm_err(L0, c["phis"], c["sn"], c["cs"])
        herm_err(L0 - err, c["phis"], c["sn"], c["cs"])
        lgg -= log2m(herm_err.mag)
    if lgg > math.log2(G_MAX):
        return L0, G_MAX
    y = -lgg
    n = int(y)
    return L0, (0.0 if n > 10 else SH[n] / Q23 * tab(E2, y - n))


def solve(s, lpk, fbk, steps=24):
    """the settled loop length (what the DSP reaches with the knobs held),
    b and g, under the decay-time law"""
    L, b, g, _ = settle(s, lpk, fbk, steps)
    return L, b, g


def settle(s, lpk, fbk, steps=24):
    """-> (L, b, g, iterating): the settled loop for held knobs"""
    sign = fb_sign(fbk)
    if sign == 0:
        c = setup(s, lpk, fbk, 0.0)
        return length(c, 0.0), c["b"], 0.0, False
    c = setup(s, lpk, fbk, 0.0)
    L0, gm = law_g(c, fb_lr(fbk))
    if c["a"] == 0:
        return finish(c, L0), c["b"], sign * gm, False
    c = setup(s, lpk, fbk, sign * gm)
    lr = 0.0
    for _ in range(steps):
        lr = step(c, lr)
    return length(c, lr), c["b"], sign * gm, True


def finish(c, L):
    """the Hermite's correction and the clamp, for a closed-form L"""
    if HERM_FIX:
        L -= herm_err(L, c["phis"], c["sn"], c["cs"])
    return max(LMIN, min(LMAX, L))


def herm_err(D, phis, sn, cs):
    """the Hermite read's own phase-delay error at the sounding fundamental,
    for a read at D (on the unit circle): tau(f) - f, from the four
    Catmull-Rom weights at f = frac D and the taps' phasors at k = -1..2
    (cos/sin of 2w by the double angle)"""
    f = D - int(D)
    wm = -0.5 * f + f * f - 0.5 * f ** 3
    w0 = 1 - 2.5 * f * f + 1.5 * f ** 3
    w1 = 0.5 * f + 2 * f * f - 1.5 * f ** 3
    w2 = -0.5 * f * f + 0.5 * f ** 3
    c2, s2 = 2 * cs * cs - 1, 2 * sn * cs
    re = wm * cs + w0 + w1 * cs + w2 * c2          # S = sum w_k e^{-j w k}
    im = wm * sn - w1 * sn - w2 * s2
    tau = -atan2s(im, re) / (2 * math.pi * phis)   # samples
    herm_err.mag = math.hypot(re, im)              # |S|: the read's loss a pass
    return tau - f


def atan2s(y, x):
    """signed atan2 in radians for |y| < x (the Hermite's small phase)"""
    return math.copysign(2 * math.pi * atan2c(abs(y), x), y)


def solve_exact(s, lpk, fbk, iters=12):
    """the float solve, for the gates: no tables but BLP's own b (the filter
    the loop runs is the table's)"""
    f0 = F_A_SHARP_0 * 2 ** (s / 12)
    P = FS / f0
    b = knob_b(lpk)
    a = 1 - b
    g = fb_g(fbk)
    w = 2 * math.pi * f0 / FS / (2 if g < 0 else 1)
    r = 1.0
    for _ in range(iters):
        rho = a / r
        ps = math.atan2(rho * math.sin(w), 1 - rho * math.cos(w))
        L = P - ps / w
        mag = math.hypot(1 - rho * math.cos(w), rho * math.sin(w))
        r = min(1.0, max(0.05, (max(abs(g), G_MIN) * b / mag) ** (1 / L)))
    rho = a / r
    return P - math.atan2(rho * math.sin(w), 1 - rho * math.cos(w)) / w


class Line:
    def __init__(self):
        self.buf = [0.0] * STRIDE
        self.w = 0          # where the last sample went

    def herm(self, d):
        i = int(d)
        f = d - i
        j = (self.w - i - 1) % N                 # y2, the oldest
        y2, y1, y0, ym = self.buf[j:j + 4]
        c1 = 0.5 * (y1 - ym)
        c2 = ym - 2.5 * y0 + 2 * y1 - 0.5 * y2
        c3 = 0.5 * (y2 - ym) + 1.5 * (y0 - y1)
        return ((c3 * f + c2) * f + c1) * f + y0

    def push(self, v):
        self.w = (self.w + 1) % N
        self.buf[self.w] = v
        if self.w < GUARD:
            self.buf[self.w + N] = v


def sat(v):
    return max(-1.0, min(0x7FFFFF / Q23, v))


class TunedComb:
    def __init__(self, PTCH=47, FINE=64, LP=127, FB=112, MIX=127):
        self.k = dict(PTCH=PTCH, FINE=FINE, LP=LP, FB=FB, MIX=MIX)
        self.lines = (Line(), Line())
        self.y = [0.0, 0.0]
        self.dc = [0.0, 0.0]            # the input's DC blocker, per channel
        self.d = 0.0
        self.slope = 0.0
        self.b = 1.0
        self.g = 0.0
        self.lr = 0.0
        self.L = 0.0
        self.words = None
        self.left = 0
        self.capped = False
        self.neg = False                # the last solve's polarity (FB < 64)
        self.pending = None             # a split change's steps: (c, g, steps, knobs)
        self.Lk = None                  # the knobs L is solved for
        self.mi = 0
        self.mstep_i = 0
        self.primed = False
        self.trace = []

    def set(self, **kw):
        self.k.update(kw)

    def block(self):
        k = self.k
        words = (int(k["PTCH"]) << 16, word(k["FINE"]), word(k["LP"]), word(k["FB"]))
        split_b = self.pending is not None
        if split_b:                            # the steps of last block's change (no knobs read)
            c, g, steps, self.Lk = self.pending
            self.pending = None
            self.b, self.g = c["b"], g
            for _ in range(steps):
                self.lr = step(c, self.lr)
            self.L = length(c, self.lr)
            change = False
            steps = 0
        else:
            change = not self.primed or words != self.words
        if change:
            # a small change (each knob's move over its limit -- PTCH 1
            # semitone, FINE 8, FB and LP 4 -- summing to at most 1) from a
            # block that was iterating: one warm step from the last lr; any
            # other a cold start and two (the DSP's sum, in its words)
            moved = (abs(words[0] - self.words[0]) + (abs(words[1] - self.words[1]) >> 3)
                     + (abs(words[3] - self.words[3]) >> 2) + (abs(words[2] - self.words[2]) >> 2)
                     if self.primed else 1 << 30)
            warm = self.capped and moved <= 0x10000 and (k["FB"] < 64) == self.neg
            # a warm PTCH, FINE or FB move takes two steps all the same (a
            # split change's steps come every other block); LP alone one
            pitch_moved = self.primed and (abs(words[0] - self.words[0]) + (abs(words[1] - self.words[1]) >> 3)
                                           + (abs(words[3] - self.words[3]) >> 2)) != 0
            self.words, self.left = words, SETTLE
            steps = 1 if warm and not pitch_moved else CHANGE_STEPS
            if not warm:
                self.lr = 0.0
        elif self.left and not split_b:
            self.left -= 1
            steps = 1
        else:
            steps = 0
        if steps:
            s = min(NOTES - 1, k["PTCH"]) + (k["FINE"] - 64) / 64
            sign = fb_sign(k["FB"])
            self.neg = k["FB"] < 64
            if change:                         # a change: the law's gain first
                b0, g0 = self.b, self.g
                self.capped = False
                c = setup(s, k["LP"], k["FB"], 0.0)
                self.b, self.g, self.left = c["b"], 0.0, 0
                if sign == 0:
                    self.L = length(c, 0.0)
                else:
                    L0, gm = law_g(c, fb_lr(k["FB"]))
                    self.g = sign * gm
                    if c["a"] == 0:                # LP open: the closed form
                        self.L = finish(c, L0)
                    else:                          # LP closed: the iteration at that gain
                        self.capped, self.left = True, SETTLE
            if sign != 0 and self.capped and change and self.primed:
                # split (LP closed, after the first block): the steps and L
                # next block, b and g with them; this block keeps the last
                self.pending = (setup(s, k["LP"], k["FB"], self.g), self.g, steps, dict(k))
                self.b, self.g = b0, g0
            elif sign != 0 and self.capped:
                c = setup(s, k["LP"], k["FB"], self.g)
                self.b = c["b"]
                for _ in range(steps):
                    self.lr = step(c, self.lr)
                self.L = length(c, self.lr)
        if steps and self.pending is None:
            self.Lk = dict(k)                  # the knobs L is solved for (a split's: next block)
        L = self.L
        if not self.primed:
            self.d = L
        self.slope = (L - self.d) / LOOKAHEAD
        self.trace.append(L)
        mw = 0x7FFFFF if k["MIX"] >= 127 else int(round(k["MIX"] * 65536))
        if abs(mw - self.mi) < 128:
            self.mi, self.mstep_i = mw, 0
        else:
            self.mstep_i = (mw - self.mi) >> 7
        self.primed = True

    def process(self, L, R, changes=None):
        outL, outR = [], []
        for n in range(len(L)):
            if n % BLOCK == 0:
                if changes:
                    for at, kw in changes.items():
                        if n <= at < n + BLOCK:
                            self.set(**kw)
                self.block()
            self.mi += self.mstep_i
            m = self.mi / Q23
            self.d += self.slope
            out = []
            for ch, dry in ((0, L[n]), (1, R[n])):
                ln = self.lines[ch]
                v = ln.herm(self.d)
                self.y[ch] += self.b * (v - self.y[ch])
                # the loop's input without its DC: a positive loop's gain at DC is
                # 1/(1 - g), up to 500, and a source's DC under -60 dBFS came out
                # of it near -17 dBFS. hp rounded to a word (a floor is a DC the
                # loop would hold); the dry path keeps the input as it is
                hp = round((dry - self.dc[ch]) * Q23) / Q23
                self.dc[ch] += hp / (1 << DCB_SHIFT)
                s = sat(hp + self.g * self.y[ch])
                ln.push(s)
                out.append(dry + m * (s - dry))
            outL.append(out[0])
            outR.append(out[1])
        return outL, outR


if __name__ == "__main__":
    print("table words:", len(TABLE))
