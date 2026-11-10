"""MODULATION v2 -- the float reference the DSP is proven against
(tools/verify/verify_modulation.py), one class per mode, each a transcription
of its source's per-sample law with the station's knob decode in front:

  JUNO  jpcima HeraChorus.dsp (ISC) + pendragon-andyh's Juno-60 measurements:
        two BBD lines on ONE triangle LFO, the right line's inverted; I 0.513
        Hz, II 0.863, sweep 1.54..5.15 ms; I+II 9.75 Hz mono 3.22..3.56 ms;
        dry 0.83 + wet 1.0; the BBD's in/out filters ~10 kHz.
  DIM   Roland SDD-320 (service notes + measurements): two lines in ANTIPHASE
        on one triangle LFO, 0.25 / 0.5 Hz, 5..12 ms; each output = the dry +
        a bass lift + a little same-side wet - the OTHER side's wet through a
        highpass. The mix constants are unpublished: OURS (marked).
  FLNG  Dattorro, Effect Design Part 2 (JAES 1997) Table 6: blend 0.7071,
        feedforward 0.7071, feedback -0.7071; the dry read from a FIXED tap at
        the sweep's centre so the sweep crosses it (through-zero), the wet
        inverted so the crossing nulls.
  PHSR  ChowPhaser (BSD-3), the Schulte Compact Phasing A: a feedback section
        of two RC allpasses (C 15 nF) with feedback around them, then N
        first-order allpasses on one shared coefficient (C 25 nF); the LDR:
        light = 20.1 - 20 lfo, R = 100k (light/0.1)^-0.75; bilinear K = 2 fs.
        Ours: the feedback closes through one sample (ChowPhaser collapses
        the delay-free loop into a warped biquad), the coefficient is decoded
        per block and ramped per sample, the tanh stages are left out.
  COMB  Mutable Instruments Rings string.h/.cc (MIT): a Hermite-read loop
        tuned by DLY, a 3-tap FIR damping filter (brightness = TONE), the
        per-pass gain from a DECAY TIME (rt60 = 0.07 s * 2^(8 lf), lf =
        d(2-d)) so every pitch rings for the same time; the IIR damping
        filter is the MIC_W build's omission; dispersion left out. FDBK's
        sign is ours (negative = odd harmonics).

Every mode's wet passes MIX: out = dry + m (wet - dry), so MIX 0 is the dry
and MIX 127 the wet alone. Sample rate 44,100. Block 15 samples: the knob
decode runs once per block, as the DSP's does.
"""
import math

FS = 44100.0
BLOCK = 15
LOOKAHEAD = 16      # the swept delays' slope and PHSR's coefficient steps: a 16th of the way to the target (the DSP's asr #4; the unit's block is 16, the gates' 15)
LINE = 1024

MODES = {"JUNO": 0, "DIM": 1, "FLNG": 2, "COMB": 3, "PHSR": 4}


# ---- the knob laws (shared with the DSP's per-block decode) -------------------
def rate_inc(k):
    """phase increment per sample, in cycles: (floor((k/128)^2 * 0x780) +
    0x10) / 2^23 -> 0.084 Hz .. 10.0 Hz. The floor is the DSP's: its mpy of
    the squared knob by the integer word 0x780 keeps the integer part."""
    q = k / 128.0
    return (int(q * q * 0x780) + 0x10) / 8388608.0


def depth_samples(k):
    return 480.0 * k / 128.0


def centre_samples(k):
    return 8.0 + 992.0 * k / 128.0


def feedback(k):
    """bipolar: 64 = 0, 0 = -1, 127 = +0.984"""
    return (k - 64) / 64.0


def mix(k):
    return 1.0 if k >= 127 else k / 128.0     # 127 = the wet outright


def tone_coef(k):
    """the BBD proxy one-pole: 0.25 (2 kHz) .. 127 = 1.0, an exact bypass"""
    return 1.0 if k >= 127 else 0.25 + 0.75 * k / 128.0


def width_offset(k):
    """the right channel's LFO lag in cycles: 0 mono .. 0.496 (antiphase)"""
    return (k / 128.0) * 0.5


def tri(phase):
    """-1..1 triangle of a 0..1 phase, 1 at 0, -1 at 0.5 (the DSP's)"""
    return 4.0 * abs((phase % 1.0) - 0.5) - 1.0


def para(phase):
    """the DSP's sine: the parabola 2t - t|t| of the triangle"""
    t = tri(phase)
    return 2.0 * t - t * abs(t)


class OnePole:
    def __init__(self, c):
        self.c = c
        self.s = 0.0

    def lp(self, x):
        self.s += self.c * (x - self.s)
        return self.s

    def hp(self, x):
        return x - self.lp(x)


class Line:
    """a 1,024-word line on an INCREMENTING write phase, ADVANCED at the top
    of every sample (the DSP's order: advance, read the taps at (phase -
    delay) & 1023, then write this sample at the phase); the fraction blends
    toward the OLDER neighbour (the crackle fix)."""
    def __init__(self):
        self.buf = [0.0] * LINE
        self.w = 0

    def advance(self):
        self.w = (self.w + 1) & (LINE - 1)

    def write(self, v):
        self.buf[self.w] = v

    def at(self, delay_int):
        return self.buf[(self.w - delay_int) & (LINE - 1)]

    def read(self, delay):
        i = int(delay)
        f = delay - i
        t0 = self.at(i)
        t1 = self.at(i + 1)
        return t0 + f * (t1 - t0)

    def hermite(self, delay):
        i = int(delay)
        f = delay - i
        xm1, x0, x1, x2 = self.at(i - 1), self.at(i), self.at(i + 1), self.at(i + 2)
        c = (x1 - xm1) * 0.5
        v = x0 - x1
        w = c + v
        a = w + v + (x2 - x0) * 0.5
        b_neg = w + a
        return (((a * f) - b_neg) * f + c) * f + x0


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# =============================================================================
# LOFI: hold + quantise, one counter for both channels. At the LINE WRITE in
# the line modes and COMB (the taps read through the stairs, the ring
# recirculates them), on the wet in PHSR. hold = 1 + floor(k^2 / 256) samples
# (the DSP's mpy + asr 17); the mask on k >> 3 from LOFI_MASK, the DSP's
# P table. The and on the 24-bit word is a floor toward -inf, as the DSP's.
# =============================================================================
LOFI_BITS = (24, 24, 24, 24, 24, 24, 24, 24, 16, 12, 10, 9, 8, 7, 6, 5)   # 24 below 64, then 16 12 10 9 8 7 6 5
LOFI_MASK = tuple((0xffffff << (24 - b)) & 0xffffff for b in LOFI_BITS)


class Lofi:
    def __init__(self, k):
        self.hold = 1 + (k * k) // 256
        self.mask = LOFI_MASK[k >> 3]
        self.cnt = 0
        self.held = [0.0, 0.0]

    def step(self):
        self.cnt += 1
        if self.cnt >= self.hold:
            self.cnt = 0

    def run(self, ch, v):
        if self.cnt == 0:
            self.held[ch] = v
        i = min(int(math.floor(self.held[ch] * 2 ** 23)), 2 ** 23 - 1)   # the DSP's limiter: +1.0 is 0x7fffff
        i = i & 0xffffff & self.mask
        if i >= 2 ** 23:
            i -= 2 ** 24
        return i / 2 ** 23


# =============================================================================
# LINE: JUNO, DIM, FLNG -- two lines, one triangle LFO, per-mode mix weights
# =============================================================================
class LineModes:
    """wet_L = bl*fixed_L + bd*dry_L + ff*LPo(tap_L) + kc*HP(LPo(tap_R)) + kb*LPb(dry_L)
    line_L <- LPi(dry_L) + fb*tap_L ; the R side mirrored.
      JUNO  bl 0      bd 0  ff 1       kc 0   kb 0
      FLNG  bl 0.7071 bd 0  ff -0.7071 kc 0   kb 0
      DIM   bl 0      bd 1  ff 0.25    kc -1  kb 0.5   (OURS: the SDD-320's
            same-side / cross / bass-lift amounts are unpublished; the HP and
            the lift's LP are one-poles at 200 Hz)
    """
    W = {"JUNO": (0.0, 0.0, 1.0, 0.0, 0.0),
         "FLNG": (0.7071 * 0.44668, 0.0, -0.7071 * 0.44668, 0.0, 0.0),   # -7 dB
         "DIM": (0.0, 0.39811, 0.25 * 0.39811, -0.39811, 0.5 * 0.39811)}  # -8 dB
    C200 = 1.0 - math.exp(-2 * math.pi * 200.0 / FS)      # 0.0281

    def __init__(self, mode, RATE, DPTH, FDBK, MIX, TONE, WDTH, DLY, LOFI=0):
        self.bl, self.bd, self.ff, self.kc, self.kb = self.W[mode]
        self.lofi = Lofi(LOFI)
        self.k = dict(RATE=RATE, DPTH=DPTH, FDBK=FDBK, MIX=MIX, TONE=TONE, WDTH=WDTH, DLY=DLY)
        self.lines = (Line(), Line())
        self.phase = 0.0
        c = tone_coef(TONE)
        self.lpi = (OnePole(c), OnePole(c))
        self.lpo = (OnePole(c), OnePole(c))
        self.hp = (OnePole(self.C200), OnePole(self.C200))
        self.lpb = (OnePole(self.C200), OnePole(self.C200))

    def block(self):
        k = self.k
        self.inc = rate_inc(k["RATE"])
        centre = min(centre_samples(k["DLY"]), 1000.0)
        depth = depth_samples(k["DPTH"])
        depth = min(depth, centre - 8.0, 1015.0 - centre)
        self.centre, self.depth = centre, max(depth, 0.0)
        self.fb = feedback(k["FDBK"])
        self.m = mix(k["MIX"])
        self.wid = width_offset(k["WDTH"])

    def knots(self):
        """The swept delays are a straight line per block (the DSP's mo_knot): from where the last block left
        them to the value the LFO has a block (BLOCK samples) on, a LOOKAHEAD'th of the way a sample; the first
        block starts on that value."""
        end = [self.centre + self.depth * tri(self.phase + BLOCK * self.inc + ch * self.wid) for ch in (0, 1)]
        if self.d is None:
            self.d = list(end)
        self.slope = [(end[ch] - self.d[ch]) / LOOKAHEAD for ch in (0, 1)]

    def process(self, L, R):
        """The block-linear sweep the DSP runs. self.dev is its largest distance, in samples, from the sources'
        per-sample LFO (centre + depth * tri(phase))."""
        outL, outR = [], []
        self.d = None
        self.dev = 0.0
        for n in range(len(L)):
            if n % BLOCK == 0:
                self.block()
                self.knots()
            self.phase = (self.phase + self.inc) % 1.0
            dry = (L[n], R[n])
            for ln in self.lines:
                ln.advance()
            self.d = [self.d[ch] + self.slope[ch] for ch in (0, 1)]
            dl = self.d
            for ch in (0, 1):
                ex = self.centre + self.depth * tri(self.phase + ch * self.wid)
                self.dev = max(self.dev, abs(dl[ch] - ex))
            taps = [self.lines[ch].read(dl[ch]) for ch in (0, 1)]
            fixed = [self.lines[ch].read(self.centre) for ch in (0, 1)]
            wo = [self.lpo[ch].lp(taps[ch]) for ch in (0, 1)]
            self.lofi.step()
            for ch in (0, 1):
                v = clamp(self.lpi[ch].lp(dry[ch]) + self.fb * taps[ch], -1.0, 1.0)
                self.lines[ch].write(self.lofi.run(ch, v))
            wet = []
            for ch in (0, 1):
                o = 1 - ch
                w = (self.bl * fixed[ch] + self.bd * dry[ch] + self.ff * wo[ch]
                     + self.kc * self.hp[ch].hp(wo[o]) + self.kb * self.lpb[ch].lp(dry[ch]))
                wet.append(clamp(w, -1.0, 1.0))      # the DSP's limiting store
            outL.append(dry[0] + self.m * (wet[0] - dry[0]))
            outR.append(dry[1] + self.m * (wet[1] - dry[1]))
        return outL, outR


# =============================================================================
# PHSR: ChowPhaser's Schulte model (BSD-3)
# =============================================================================
def ldr_ohms(lfo):
    light = (20.0 + 0.1) - lfo * 20.0
    return 100000.0 * (light / 0.1) ** -0.75


def allpass_b0(R, C):
    """first-order RC allpass, bilinear K = 2 fs: y = b0 x + z ; z = b0 y - x"""
    RC = R * C
    K = 2.0 * FS
    return (RC * K - 1.0) / (RC * K + 1.0)


def phsr_tables(n=33):
    """b0 for the mod stages (25 nF) and the feedback stages (15 nF) over
    lfo = -1..1, the DSP's 33-entry P tables"""
    mod, fb = [], []
    for i in range(n):
        lfo = -1.0 + 2.0 * i / (n - 1)
        R = ldr_ohms(lfo)
        mod.append(allpass_b0(R, 25e-9))
        fb.append(allpass_b0(R, 15e-9))
    return mod, fb


def table_read(tab, u):
    """u in 0..1 over the table, linear interpolation (the DSP's read)"""
    n = len(tab) - 1
    x = clamp(u, 0.0, 1.0) * n
    i = min(int(x), n - 1)
    f = x - i
    return tab[i] + f * (tab[i + 1] - tab[i])


class Allpass1:
    def __init__(self):
        self.z = 0.0

    def run(self, x, b0):
        y = b0 * x + self.z
        self.z = b0 * y - x
        return y


class Phaser:
    STAGES = 8

    def __init__(self, RATE, DPTH, FDBK, MIX, TONE, WDTH, DLY, LOFI=0):
        self.lofi = Lofi(LOFI)
        self.k = dict(RATE=RATE, DPTH=DPTH, FDBK=FDBK, MIX=MIX, WDTH=WDTH, DLY=DLY)
        self.tables = phsr_tables()
        self.phase = 0.0
        self.fbs = [[Allpass1(), Allpass1()] for _ in (0, 1)]
        self.mod = [[Allpass1() for _ in range(self.STAGES)] for _ in (0, 1)]
        self.yprev = [0.0, 0.0]
        self.bm_run = [0.0, 0.0]       # the DSP's init zeroes the ramps
        self.bf_run = [0.0, 0.0]

    def coefs(self, lfo):
        """allpass_b0(ldr_ohms(lfo), 25 nF / 15 nF), read through the tables as the DSP does"""
        u = (lfo + 1.0) * 0.5
        return table_read(self.tables[0], u), table_read(self.tables[1], u)

    def block(self):
        k = self.k
        self.inc = rate_inc(k["RATE"])
        self.phase = (self.phase + BLOCK * self.inc) % 1.0
        depth = k["DPTH"] / 128.0
        wid = width_offset(k["WDTH"])
        self.fb = clamp(feedback(k["FDBK"]), -0.95, 0.95)
        self.m = mix(k["MIX"])
        # STGS on the DLY knob: 2 / 4 / 6 / 8 by quarters
        self.taps = 2 * (1 + min(k["DLY"] // 32, 3))
        self.bm_tgt, self.bf_tgt = [], []
        for ch, ph in ((0, self.phase), (1, self.phase + wid)):
            bm, bf = self.coefs(clamp(depth * para(ph), -1.0, 1.0))
            self.bm_tgt.append(bm)
            self.bf_tgt.append(bf)
        self.dbm = [(self.bm_tgt[ch] - self.bm_run[ch]) / LOOKAHEAD for ch in (0, 1)]
        self.dbf = [(self.bf_tgt[ch] - self.bf_run[ch]) / LOOKAHEAD for ch in (0, 1)]

    def process(self, L, R):
        outL, outR = [], []
        for n in range(len(L)):
            if n % BLOCK == 0:
                self.block()
            outs = []
            for ch, x in ((0, L[n]), (1, R[n])):
                self.bm_run[ch] += self.dbm[ch]
                self.bf_run[ch] += self.dbf[ch]
                bm, bf = self.bm_run[ch], self.bf_run[ch]
                # the chain runs at HALF scale (the DSP's headroom: an allpass
                # cascade peaks above its input, and the DSP's stores clamp
                # at 1.0); yprev is kept halved too, so fb applies as written
                u = clamp(0.5 * x + self.fb * self.yprev[ch], -1.0, 1.0)
                y = self.fbs[ch][1].run(self.fbs[ch][0].run(u, bf), bf)
                self.yprev[ch] = y
                for s in range(self.taps):
                    y = self.mod[ch][s].run(y, bm)
                for s in range(self.taps, self.STAGES):     # the idle stages still run (the DSP unrolls 8)
                    self.mod[ch][s].run(y, bm)
                y = clamp(2.0 * 0.79433 * y, -1.0, 1.0)      # -2 dB trim
                if ch == 0:
                    self.lofi.step()
                y = self.lofi.run(ch, y)
                outs.append(x + self.m * (y - x))
            outL.append(outs[0])
            outR.append(outs[1])
        return outL, outR


# =============================================================================
# COMB: Rings' string loop (MIT)
# =============================================================================
def period_table(n=33):
    """DLY -> the loop's period in samples, 1000 .. 8 exponential (7 octaves,
    ~18 detents an octave), the DSP's 33-entry P table"""
    return [1000.0 * (8.0 / 1000.0) ** (i / (n - 1)) for i in range(n)]


def pow2_table(n=33):
    """T(u) = 2^(-8u), u = 0..1"""
    return [2.0 ** (-8.0 * i / (n - 1)) for i in range(n)]


class Comb:
    RT60_1 = 0.07 * FS          # rt60 at lf = 0, in samples (3,087)

    def __init__(self, RATE, DPTH, FDBK, MIX, TONE, WDTH, DLY, LOFI=0):
        self.lofi = Lofi(LOFI)
        self.k = dict(FDBK=FDBK, MIX=MIX, TONE=TONE, DLY=DLY)
        self.tables = (period_table(), pow2_table())
        self.lines = (Line(), Line())
        self.x1 = [0.0, 0.0]
        self.x2 = [0.0, 0.0]

    def block(self):
        """period = 1000 (8/1000)^(DLY/128); rt60 = RT60_1 2^(8 lf) and gain = 2^(-10 period / rt60), each read
        through the 33-word tables as the DSP does (T(u) = 2^(-8u): 256 T(1 - lf) = 2^(8 lf), T(q) = 2^(-8q))"""
        k = self.k
        self.period = table_read(self.tables[0], k["DLY"] / 128.0)
        fbk = feedback(k["FDBK"])
        self.sign = -1.0 if fbk < 0 else 1.0
        d = abs(fbk)
        lf = d * (2.0 - d)
        rt60 = self.RT60_1 * 256.0 * table_read(self.tables[1], 1.0 - lf)
        q = min(1.25 * self.period / rt60, 1.0)
        self.gain = table_read(self.tables[1], q)
        b = k["TONE"] / 128.0
        self.h0 = (1.0 + b) * 0.5
        self.h1 = (1.0 - b) * 0.25
        self.m = mix(k["MIX"])

    def process(self, L, R):
        outL, outR = [], []
        for n in range(len(L)):
            if n % BLOCK == 0:
                self.block()
            outs = []
            for ch, x in ((0, L[n]), (1, R[n])):
                self.lines[ch].advance()
                s = clamp(self.sign * self.lines[ch].hermite(self.period - 1.0) + x, -1.0, 1.0)
                y = self.gain * (self.h0 * self.x1[ch] + self.h1 * (s + self.x2[ch]))
                self.x2[ch] = self.x1[ch]
                self.x1[ch] = s
                y = clamp(y, -1.0, 1.0)
                if ch == 0:
                    self.lofi.step()
                y = self.lofi.run(ch, y)                        # the sample written
                self.lines[ch].write(y)
                w = 0.25119 * y                                 # -12 dB trim, outside the ring
                outs.append(x + self.m * (w - x))
            outL.append(outs[0])
            outR.append(outs[1])
        return outL, outR


# =============================================================================
# The P table the build loads (manifest.py: DspSection.ptable), each table at
# the offset the DSP reads it: PHSR_MOD 0, PHSR_FB 33, PERIOD 66, POW2 99,
# LOFI_MASK 132. Each word is its value rounded; the nearest sits 0.0049 LSB
# from a rounding boundary, so a last-bit libm difference cannot move one.
# =============================================================================
def q23(v):
    """a fraction to its 24-bit word, rounded; +1.0 is 0x7fffff"""
    return min(round(v * (1 << 23)), 0x7fffff)


PHSR_MOD, PHSR_FB = (tuple(q23(v) for v in t) for t in phsr_tables())
PERIOD = tuple(round(v * 4096) for v in period_table())     # Q11.12 samples
POW2 = tuple(q23(v) for v in pow2_table())
TABLE = PHSR_MOD + PHSR_FB + PERIOD + POW2 + LOFI_MASK


def make(mode, **knobs):
    if mode in LineModes.W:
        return LineModes(mode, **knobs)
    return {"PHSR": Phaser, "COMB": Comb}[mode](**knobs)
