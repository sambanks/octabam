"""VIBRATO -- the float reference the DSP is proven against
(tools/verify/verify_vibrato.py), and the source of the module's tables
(manifest.py loads them from here).

A pitch vibrato: one modulated delay per channel, wet only, MIX blends.
Every shape is a PITCH trajectory p in [-1, 1], pitch ratio 1 + dev p, and
the delay is the integral of -dev p. For the periodic shapes that integral is
closed-form, normalised to +-1 and scaled by the swing H:

    SINE  pitch -cos      -> delay  sin(2 pi phi)         H = dev per / (2 pi)
    TRI   pitch triangle  -> delay  +-4u(1-u), u = 2phi mod 1   H = dev per / 8
    SQR   pitch square    -> delay  triangle, 0 at phi = 0      H = dev per / 4
    RND   a new pitch each half cycle (the square's step rate), integrated:
          x -= 4 u dphi; at each step u = x/2 + n/2 (n uniform in [-1, 1]),
          so the half cycle ends near x = -n and |x| <= 1   H = dev per / 4

per = samples per cycle. A delay slope of +-dev gives pitch ratios 1 -+ dev,
so dev = tanh(cents ln2 / 1200): (1 + dev)/(1 - dev) = 2^(2 cents/1200), the
two extremes exactly 2 DEP apart (a whole-tone trill at DEP 127), the centre
under 3 cents flat at full depth. H is capped at LIM (the 1,024-word line),
which scales the depth and keeps the shape.

The DSP's structure, mirrored here:
  * per block (BLOCK samples; 16 on the unit, 15 in the gates): decode the
    knobs, advance the LFO phase by BLOCK inc, evaluate each channel's delay
    there (a "knot"), and walk the delay to it in a straight line, a
    LOOKAHEAD'th of the way a sample (modulation's mo_knot);
  * SLEW is a one-pole on the knot's offset, per block: c = min(1, dphi /
    (s/4)) with s = SLEW/128 (a time constant of s/4 of a cycle; the DSP
    divides, per block); SLEW 0 is c = 1;
  * the knob tables have 33 entries, at k = 0, 4, .. 128, read at k >> 2 and
    interpolated by the rest (the DSP takes the rest from the knob word's
    bits 17-8, so an LFO's fraction moves it too). The phase increment is
    floored as the DSP's mpy leaves it (a1), since the phase accumulates;
  * SPD's and DEP's knob words glide through two one-poles of 1/32 a block
    (asr, in the word's integers), snapped onto the knob within one
    LFO-fraction LSB and on it at once at init: a hand twist's steps would otherwise each resize
    the swing and move the centre in one block, a train of jumps (gate 8e);
    the swing H follows the glided words at once; the delay's walk is limited to
    1.5 dev a sample (at least 0.006, 10.4 cents), so a knob jump (which
    moves H and the centre 2 + H by tens of samples) is chased at a bounded
    pitch instead of spiking. No shape's own slope exceeds dev, so in steady
    state the limit never engages;
  * a SHP change ducks the wet to dry over 16 blocks, switches once the MIX
    run (which lags the duck) is on 0, snaps the delay to the new shape on
    that block (as at init), and fades back (LOFI2's MODE duck);
    init starts fully ducked;
  * MIX glides: per block the run moves 1/8 of the way to m (1 - e), in a
    straight line over the block (a 128th of the distance a sample), and
    snaps to it once that distance is under 128 LSBs: out = dry + m (wet -
    dry), m = MIX/128, 127 = 1.0. MIX 0 is the dry, exactly;
  * the line: 1,024 words a channel, write phase advanced at the top of each
    sample, the tap read at (phase - delay) blended toward the OLDER
    neighbour, then this sample written.
  * the noise is a 24-bit Galois LFSR (mask 0xE10000, maximal), 16 steps a
    draw, seeded per payload and per instance (the payload's word eor r7 << 8); R draws n_R = n1 + w (n2 - n1), w = WID/128, so WID decorrelates
    the random shape where it phase-offsets the periodic ones.
"""
import math

FS = 44100.0
BLOCK = 15          # the gates' block; the unit's is 16
LOOKAHEAD = 16      # the walks' slope is a 16th of the way to the knot
LINE = 1024
LIM = 500.0         # the largest swing, samples: delay = 2 + H + H F in 2 .. 1002
DMIN = 2.0
DMAX = 1016.0
Q23 = float(1 << 23)
SLOPE_FLOOR = 0x00C49C / Q23    # 0.006 a sample, 10.4 cents: the walk's least limit
GLIDE_SHIFT = 5     # SPD's and DEP's knob glide: two one-poles of 1/32 a block, 11.6 ms each on the unit
GLIDE_STAGES = 2    # one alone has a corner in its velocity at every knob step, and velocity is pitch

SHAPES = {"SINE": 0, "TRI": 1, "SQR": 2, "RND": 3}
# H = dev per FAC: the four shapes' swing per unit of dev * per
FAC = (1 / (2 * math.pi), 1 / 8, 1 / 4, 1 / 4)

LFSR_MASK = 0xE10000
LFSR_STEPS = 16
SEEDS = {"A": 0x5EED01, "B": 0x3C9A57}   # odd, per payload (the asm's subst)
DEFAULT_SEED = SEEDS["A"] ^ (0x6100 << 8)   # FX1 track 1 on payload A


def lfsr_seed(r7, payload="A"):
    """the DSP's init: the payload's word eor r7 << 8 (odd, never zero)"""
    return SEEDS[payload] ^ ((r7 << 8) & 0xFFFFFF)


def _w(v):
    """a positive Q23 word, saturated"""
    return max(0, min(0x7FFFFF, int(round(v * Q23))))


# ---- the knob laws: 33-entry tables at k = 4i, i = 0..32 ------------------
def spd_hz(k):
    """SPD: 0.25 Hz at 0 to 16 Hz at 128, exponential (6 octaves over 128
    steps: 21.3 steps an octave). 94 = 5.4 Hz."""
    return 0.25 * 2.0 ** (3.0 * k / 64.0)


def dep_cents(k):
    """DEP: peak deviation in cents, 100 (k/127)^2: 25 at 64, 30 at 70,
    100 at 127"""
    return 100.0 * (k / 127.0) ** 2


KS = tuple(4 * i for i in range(33))
INC = tuple(int(round(spd_hz(k) / FS * Q23)) for k in KS)          # cycles/sample, Q23
PERW = tuple(_w(FS / spd_hz(k) / (1 << 18)) for k in KS)           # samples/cycle / 2^18
def dev_of(c):
    """the delay slope for a peak of c cents: tanh(c ln2 / 1200)"""
    return math.tanh(c * math.log(2.0) / 1200.0)


def extremes(c):
    """the two pitches, in cents, that dev_of(c) gives: (down, up)"""
    d = dev_of(c)
    return 1200 * math.log2(1 - d), 1200 * math.log2(1 + d)


DEV8 = tuple(_w(8.0 * dev_of(dep_cents(k))) for k in KS)  # 8 dev
FACW = (_w(4 * FAC[0]), _w(4 * FAC[1]), 0x7FFFFF, 0x7FFFFF)         # 16 FAC / 4

TABLE = INC + PERW + DEV8 + FACW      # the manifest's ptable, in this order
T_INC, T_PERW, T_DEV8, T_FAC = 0, 33, 66, 99


def lookup(table, k, floor=False):
    """the DSP's read: entry k >> 2, interpolated by the rest of k (k & 3 and
    an LFO's fraction, k in 1/256 steps)"""
    i = int(k // 4)
    f = (k - 4 * i) / 4.0
    if i >= 32:
        return float(table[32])
    d = f * (table[i + 1] - table[i])
    return table[i] + (math.floor(d) if floor else d)


def mix(k):
    return 1.0 if k >= 127 else k / 128.0


def wid_cycles(k):
    """R's LFO lead in cycles: (k/128)/2, 0 .. 0.496"""
    return int(round(k * 32768)) / Q23


def signed24(s):
    return s - (1 << 24) if s & 0x800000 else s


class Lfsr:
    def __init__(self, seed):
        self.s = seed

    def draw(self):
        for _ in range(LFSR_STEPS):
            lsb = self.s & 1
            self.s >>= 1
            if lsb:
                self.s ^= LFSR_MASK
        return signed24(self.s) / Q23


def shape_f(shape, phi):
    """the normalised delay offset of a periodic shape at phase phi (0..1)"""
    if shape == 0:
        return math.sin(2 * math.pi * phi)
    if shape == 1:
        u = (2 * phi) % 1.0
        g = 4 * u * (1 - u)
        return g if phi < 0.5 else -g
    v = (phi + 0.25) % 1.0
    return 1 - 4 * abs(v - 0.5)


class Line:
    def __init__(self):
        self.buf = [0.0] * LINE
        self.w = 0

    def advance(self):
        self.w = (self.w + 1) & (LINE - 1)

    def write(self, v):
        self.buf[self.w] = v

    def read(self, delay):
        i = int(delay)
        f = delay - i
        t0 = self.buf[(self.w - i) & (LINE - 1)]
        t1 = self.buf[(self.w - i - 1) & (LINE - 1)]
        return t0 + f * (t1 - t0)


class Vibrato:
    def __init__(self, SPD=80, DEP=48, SLEW=0, WID=0, MIX=127, SHP=0, seed=None):
        self.k = dict(SPD=SPD, DEP=DEP, SLEW=SLEW, WID=WID, MIX=MIX, SHP=SHP)
        self.lines = (Line(), Line())
        self.phase = 0                  # Q23 integer, cycles
        self.H = 0.0
        self.off = [0.0, 0.0]
        self.d = [0.0, 0.0]
        self.slope = [0.0, 0.0]
        self.x = [0.0, 0.0]
        self.u = [0.0, 0.0]
        self.noise = Lfsr(DEFAULT_SEED if seed is None else seed)
        self.running = 0
        # the duck and the MIX run in the DSP's integers (Q23 words): the
        # shape switches on the block the run snaps to 0, so the reference
        # must reach it on the same block
        self.ei = 0x7FFFFF              # the duck: fully out at init
        self.mi = 0
        self.mstep_i = 0
        self.primed = False
        self.kw = {}                    # SPD's and DEP's glide stages
        self.trace = []                 # (H, knot L, knot R) per block, for the gates

    def set(self, **kw):
        self.k.update(kw)

    def glide(self, name):
        """the DSP's knob glide, in the knob word's own integers: GLIDE_STAGES
        one-poles in a row, each s += (t - s)/32 a block (asr, a floor), t the
        word for the first and the previous stage's s for the next, snapped
        onto t within 0x100 (one LFO-fraction LSB) and when unprimed (init)"""
        t = int(round(self.k[name] * 65536)) & 0x7FFF00
        ss = self.kw.setdefault(name, [0] * GLIDE_STAGES)
        for i in range(GLIDE_STAGES):
            s = t if not self.primed else ss[i]
            s = t if abs(t - s) < 0x100 else s + ((t - s) >> GLIDE_SHIFT)
            ss[i] = t = s
        return (t & 0x7FFF00) / 65536.0     # vb_tab reads bits 22-8, as for any word

    def block(self):
        k = self.k
        spd = self.glide("SPD")
        dep = self.glide("DEP")
        inc = int(lookup(INC, spd, floor=True))
        dphi_i = BLOCK * inc
        dphi = dphi_i / Q23
        dev8 = lookup(DEV8, dep) / Q23
        per = lookup(PERW, spd) / Q23 * (1 << 18)
        # the duck
        if k["SHP"] != self.running:
            if self.ei >= 0x7FFFFF and self.mi == 0:
                self.running = k["SHP"]
                self.primed = False     # the knots snap on the switch block
            else:
                self.ei = min(0x7FFFFF, self.ei + 0x80000)
        else:
            self.ei = max(0, self.ei - 0x80000)
        shape = self.running
        # the swing
        Ht = min(LIM, dev8 / 8 * per * FAC[shape])
        self.H = Ht
        # the walk's limit, as the DSP holds it: Q11.12 slope LSBs, floored
        smax = math.floor(max(1.5 * dev8 / 8, SLOPE_FLOOR) * 4096) / 4096
        # the phase, n7 on
        p0 = self.phase
        p1 = (p0 + dphi_i) & 0x7FFFFF
        self.phase = p1
        raw = [0.0, 0.0]
        if shape == 3:
            if (p0 >> 22) != (p1 >> 22):         # a half-cycle boundary in this block
                n1 = self.noise.draw()
                n2 = self.noise.draw()
                w = k["WID"] / 128.0
                n = (n1, n1 + w * (n2 - n1))
                for ch in (0, 1):
                    self.u[ch] = self.x[ch] / 2 + n[ch] / 2
            for ch in (0, 1):
                self.x[ch] = max(-1.0, min(1.0, self.x[ch] - 4 * self.u[ch] * dphi))
                raw[ch] = self.H * self.x[ch]
        else:
            wid = wid_cycles(k["WID"])
            for ch in (0, 1):
                phi = ((p1 / Q23) + ch * wid) % 1.0
                raw[ch] = self.H * shape_f(shape, phi)
        # SLEW
        q = k["SLEW"] / 128.0 / 4.0
        c = 1.0 if dphi >= q else dphi / q
        for ch in (0, 1):
            self.off[ch] = raw[ch] if not self.primed else self.off[ch] + c * (raw[ch] - self.off[ch])
        knot = [min(DMAX, max(DMIN, DMIN + self.H + self.off[ch])) for ch in (0, 1)]
        for ch in (0, 1):
            if not self.primed:
                self.d[ch] = knot[ch]
            self.slope[ch] = max(-smax, min(smax, (knot[ch] - self.d[ch]) / LOOKAHEAD))
        self.trace.append((self.H, knot[0], knot[1]))
        # MIX
        mw = 0x7FFFFF if k["MIX"] >= 127 else int(round(k["MIX"] * 65536))
        meff = (mw * (0x7FFFFF - self.ei)) >> 23        # mpy, then a1
        if abs(meff - self.mi) < 128:
            self.mi, self.mstep_i = meff, 0
        else:
            self.mstep_i = (meff - self.mi) >> 7        # asr: a floor
        self.primed = True

    def process(self, L, R, changes=None):
        """L, R: lists of floats. changes: {sample index: {knob: value}},
        applied at the block that contains it."""
        outL, outR = [], []
        for n in range(len(L)):
            if n % BLOCK == 0:
                if changes:
                    for at, kw in changes.items():
                        if n <= at < n + BLOCK:
                            self.set(**kw)
                self.block()
            for ln in self.lines:
                ln.advance()
            self.mi += self.mstep_i
            m = self.mi / Q23
            out = []
            for ch, dry in ((0, L[n]), (1, R[n])):
                self.d[ch] += self.slope[ch]
                tap = self.lines[ch].read(self.d[ch])
                self.lines[ch].write(dry)
                out.append(dry + m * (tap - dry))
            outL.append(out[0])
            outR.append(out[1])
        return outL, outR


if __name__ == "__main__":
    print("table words:", len(TABLE))
    for k in (0, 64, 94, 127):
        print(f"SPD {k}: {spd_hz(k):.3f} Hz inc {int(lookup(INC, k, True))} per {lookup(PERW, k) / Q23 * (1 << 18):.1f}")
    for k in (0, 32, 64, 70, 127):
        print(f"DEP {k}: {dep_cents(k):.1f} cents")
