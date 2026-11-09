"""The WAVE engine (engine.c) in Python integers, and the command stream that drives it.

One stream (cmds.bin) drives three executors that must agree sample for sample: this model, the
engine built for the host (harness/drive.c) and the ColdFire build under Unicorn (harness/run_cf.py).

Stream: per 16-sample block, u32 n then n records of four big-endian u32 (op, a, b, c):
  0 pos(a)            frame position target, Q16 (signed)
  1 on(a, b, c)       voice a, increment b, gain c (Q31)
  2 off(a)
  3 init(a, b)        attack and release steps, Q31 (first block only)
  4 note(a, b, c)     wcf_note: p Q8 semitones (signed), chord shape, voices
  5 knobs(a, b, c)    wcf_knobs: frame position, voicing spread, pitch glide (raw 0..127)
  8 amp(a)            wcf_amp: a = atk | hold << 8 | rel << 16 | start << 24 (raw 0..127, start 0/1)
  9 clock(a)          wcf_clock: the sequencer's step word
  7 scale(a)          wcf_scale: the pitch-class mask notes snap onto, 0 = none
  6 setup(a, b)       wcf_setup: a = vibr | vrat << 8 | oct << 16 | detn << 24, b = comp | mode << 8
"""
import math
import struct

import tables

_EXP2, _TC = tables.exp2_tab(), tables.tc_tab()
_LFO, _COMP, _GLIDE = tables.lfo_tab(), tables.comp_tab(), tables.glide_tab()
_AMP_ATK, _AMP_REL, _AMP_HOLD = tables.AMP_ATK_STEP, tables.AMP_REL_K, tables.AMP_HOLD128
_GAIN_N = [0, 1717986918, 858993459, 572662306, 429496730]

NV, FLEN, NFR, BLOCK, SR = 4, 1024, 8, 16, 44100
POS_MAX = (NFR - 1) << 16
ONE27, ATK_TGT_Q27, REL_TARGET, POS_SLEW = 1 << 27, 135559905, -1342177, 8
IDLE, ATTACK, SUSTAIN, RELEASE = range(4)


def mul(a, b):
    return (a * b) >> 31


def s32(x):
    x &= 0xffffffff
    return x - (1 << 32) if x & 0x80000000 else x


class Engine:
    def __init__(self):
        flat = [s for f in tables.frames() for s in f]
        self.table = flat
        self.v = [dict(phase=0, inc=0, inc_tgt=0, incm=0, gain=0, env=0, mode=IDLE, gate=0, gate_prev=0) for _ in range(NV)]
        self.pos = self.pos_tgt = 0
        self.atk, self.rel = _TC[20], _TC[60]            # wcf_init's fixed attack and release
        self.lfo_ph = self.lfo_inc = self.lfo_amp = 0
        self.drive = self.makeup = 0
        self.poly = self.next = 0
        self.spread = 0
        self.glide = 1 << 28
        self.amp_cur = self.amp_tgt = 0
        self.amp_on = self.amp_htim = 0
        self.frames = self.fstep = 0
        self.last_step = -1
        self.fps = 345
        self.scale = 0
        self.tune_off = 0
        self.detn = 0

    def cmd(self, op, a, b, c):
        if op == 0:
            self.pos_tgt = max(0, min(POS_MAX, s32(a)))
        elif op == 1:
            v = self.v[a]
            v["inc_tgt"] = b & 0xffffffff
            if v["mode"] == IDLE:
                v["inc"] = v["inc_tgt"]
            v["gain"], v["gate"], v["gate_prev"] = s32(c), 1, 0
        elif op == 2:
            self.v[a]["gate"] = 0
        elif op == 3:
            self.atk, self.rel = s32(a), s32(b)
        elif op == 4:
            self.note(s32(a), b, c)
        elif op == 5:
            self.knobs(a, b, c)
        elif op == 7:
            self.scale = a & 0xfff
        elif op == 8:
            self.amp(a & 0xff, (a >> 8) & 0xff, (a >> 16) & 0xff, (a >> 24) & 0xff)
        elif op == 9:
            self.clock(a)
        elif op == 6:
            self.setup(a & 0xff, (a >> 8) & 0xff, (a >> 16) & 0xff, (a >> 24) & 0xff, b & 0xff, (b >> 8) & 0xff)

    def setup(self, vibr, vrat, oct_, detn, comp, mode):
        vibr, vrat, comp = min(vibr, 127), min(vrat, 127), min(comp, 127)
        oct_ = min(oct_, 2)
        self.detn = min(detn, 127)
        self.lfo_amp = vibr * 16909320
        self.lfo_inc = _LFO[vrat]
        self.drive, self.makeup = _COMP[comp]
        self.poly = 1 if mode else 0
        self.tune_off = (oct_ - 1) * 12 * 256

    def clock(self, step):
        self.frames += 1
        if step == self.last_step:
            return
        first = self.last_step < 0
        self.last_step = step
        d = self.frames - self.fstep
        self.fstep = self.frames
        if not first and d >= 16:
            self.fps = d

    def amp(self, atk, hold, rel, start):
        atk, hold, rel = min(atk, 127), min(hold, 127), min(rel, 127)
        g = self.amp_cur
        if start:
            self.amp_on = 1
            self.amp_htim = 0 if hold >= 127 else ((_AMP_HOLD[hold] * self.fps) >> 7) + 1
        releasing = not self.amp_on
        if self.amp_on and self.amp_htim:
            self.amp_htim -= 1
            if self.amp_htim == 0:
                self.amp_on = 0
                releasing = True
        if releasing:
            k = _AMP_REL[rel]
            if k:
                d = mul(g, k << 15)
                if d < (1 << 15):
                    d = 1 << 15
                g -= d
                if g <= (64 << 15):
                    g = 0
        elif g < (1 << 30):
            g += _AMP_ATK[atk] << 15
            if g > (1 << 30):
                g = 1 << 30
        self.amp_tgt = g

    def detune(self, v, n):
        return ((2 * v - (n - 1)) * self.detn * 11) >> 6

    def snap(self, p):
        m = self.scale
        if not m:
            return p
        n = ((p + 128 + 120 * 256) >> 8) + 1080
        pc = n % 12
        for d in range(7):
            if m & (1 << ((pc - d) % 12)):
                return p - 256 * d
            if m & (1 << ((pc + d) % 12)):
                return p + 256 * d
        return p

    def note(self, p, chrd, voic):
        voic = max(1, min(NV, voic))
        if self.poly:
            v = self.next
            if v >= voic:
                v = 0
            self.cmd(1, v, inc_of_p(self.snap(p + self.tune_off) + self.detune(v, voic)), _GAIN_N[voic])
            self.next = v + 1
            for k in range(voic, NV):
                self.cmd(2, k, 0, 0)
            return
        lift = self.spread >> 5
        for v in range(NV):
            if v < voic:
                iv = tables.CHORDS[chrd & 31][v] + (12 if 1 <= v <= lift else 0)
                self.cmd(1, v, inc_of_p(self.snap(p + self.tune_off + 256 * iv) + self.detune(v, voic)), _GAIN_N[voic])
            else:
                self.cmd(2, v, 0, 0)
        self.next = 0

    def knobs(self, fram, sprd, glid):
        fram, sprd, glid = min(fram, 127), min(sprd, 127), min(glid, 127)
        self.cmd(0, (fram * POS_MAX) // 127, 0, 0)
        self.spread = sprd
        self.glide = _GLIDE[glid]

    def render(self, n):
        out = []
        pmul = 1 << 30
        if self.lfo_amp:
            sgn = s32(self.lfo_ph ^ 0x80000000)
            tri = (sgn ^ (sgn >> 31)) - (1 << 30)
            pl = mul(tri, self.lfo_amp)
            x = mul(pl, 357913941)
            y = mul(x, 1488522236)
            y2 = mul(y, y)
            y3 = mul(y2, y)
            pmul = (1 << 30) + y + y2 + mul(y3, 1431655765)
            self.lfo_ph = (self.lfo_ph + self.lfo_inc * n) & 0xffffffff
        for v in self.v:
            v["inc"] = (v["inc"] + mul(s32(v["inc_tgt"]) - s32(v["inc"]), self.glide)) & 0xffffffff
            v["incm"] = v["inc"] if pmul == (1 << 30) else (mul(v["inc"], pmul) << 1) & 0xffffffff
        ag, tgt, dg = self.amp_cur, self.amp_tgt, 0
        if ag == 0 and tgt == 0:
            return [0] * n
        if tgt != ag:
            q = abs(tgt - ag) // n
            dg = -q if tgt < ag else q
        for _ in range(n):
            self.pos += (self.pos_tgt - self.pos) >> POS_SLEW
            idx = self.pos >> 16
            fa = (self.pos & 0xffff) << 15
            cur, nxt = idx * FLEN, (idx + 1) * FLEN
            t = self.table
            total = 0
            for v in self.v:
                g = v["gate"]
                if g and not v["gate_prev"]:
                    v["mode"] = ATTACK
                elif not g and v["gate_prev"]:
                    v["mode"] = RELEASE
                v["gate_prev"] = g
                env = v["env"]
                if v["mode"] == ATTACK:
                    env += mul(self.atk, ATK_TGT_Q27 - env)
                    if env > ONE27:
                        env, v["mode"] = ONE27, SUSTAIN
                elif v["mode"] == RELEASE:
                    env += mul(self.rel, REL_TARGET - env)
                    if env < 0:
                        env, v["mode"] = 0, IDLE
                v["env"] = env
                if v["mode"] == IDLE:
                    continue
                ph = v["phase"]
                i = ph >> 22
                fr = (ph >> 8) & 0x3fff
                j = (i + 1) & (FLEN - 1)
                a1, a2, b1, b2 = t[cur + i], t[cur + j], t[nxt + i], t[nxt + j]
                a = (a1 << 12) + ((fr * (a2 - a1)) >> 2)
                b = (b1 << 12) + ((fr * (b2 - b1)) >> 2)
                s = a + mul(b - a, fa)
                v["phase"] = (ph + v["incm"]) & 0xffffffff
                total += s32(mul(mul(s, v["gain"]), env) << 4)
            total = s32(total)
            if self.drive:
                tt = mul(total, self.drive)
                tt = max(-(1 << 22), min(1 << 22, tt))
                tt <<= 8
                t3 = mul(mul(tt, tt), tt)
                yy = tt - (mul(t3, 715827883) << 2)
                total = mul(yy, self.makeup)
            ag += dg
            out.append(s32(mul(total, ag) << 1))
        self.amp_cur = tgt
        return out


def inc_of_p(p):
    """wcf.c wcf_inc: the phase increment of p, Q8 semitones above C3 (TUNE 0)."""
    p = max(-48 * 256, min(48 * 256, p))
    k = (p >> 3) + 3072
    rem = p & 7
    o, kk = k // 384 - 8, k % 384
    e0, e1 = _EXP2[kk], _EXP2[kk + 1]
    e = e0 + (((e1 - e0) * rem) >> 3)
    inc = mul((tables.base_inc() << 6) & 0xffffffff, e) >> 4
    return ((inc << o) if o >= 0 else (inc >> -o)) & 0xffffffff


def q31(x):
    return max(-(1 << 31), min((1 << 31) - 1, int(round(x * (1 << 31)))))


def inc_of(hz):
    return int(round(hz / SR * 4294967296.0)) & 0xffffffff


def scenario():
    """A list of blocks, each a list of (op, a, b, c): a chord, a position sweep and jump, a release and a retrigger."""
    atk = q31(1 - math.exp(-1 / (0.004 * SR)))
    rel = q31(1 - math.exp(-1 / (0.05 * SR)))
    blocks = [[] for _ in range(2200)]
    blocks[0] = [(3, atk, rel, 0), (0, 0, 0, 0)]
    for v, hz in enumerate((220.0, 277.18, 329.63, 440.0)):
        blocks[1 + v].append((1, v, inc_of(hz), q31(0.2 * 100 / 127)))
    for k in range(200, 1000, 40):                       # a slow sweep through the table
        blocks[k].append((0, int((k - 200) / 800 * POS_MAX), 0, 0))
    blocks[1100].append((0, 6 << 16, 0, 0))              # a jump: the slew takes over
    blocks[1300] += [(2, v, 0, 0) for v in range(NV)]    # release
    blocks[1500].append((1, 0, inc_of(110.0), q31(0.2)))  # retrigger one voice, another pitch and gain
    blocks[1501].append((1, 1, inc_of(1760.0), q31(0.1)))
    blocks[1800] += [(2, 0, 0, 0), (2, 1, 0, 0)]
    return blocks


def scenario_note():
    """The note layer: knobs, then notes with chords and voice counts, a retrigger, an out-of-range pitch."""
    blocks = [[] for _ in range(2400)]
    blocks[0] = [(5, 0, 0, 0)]
    blocks[1] = [(4, 0, 0, 1)]                               # C3, one voice
    blocks[300] = [(4, 12 * 256, 3, 3)]                      # C5 major, three voices
    blocks[600] = [(5, 40, 40, 20), (4, -5 * 256 + 100, 11, 4)]    # a fractional pitch, dom7, four voices
    blocks[900] = [(5, 127, 70, 100)]
    blocks[1000] = [(4, 7 * 256, 31, 4)]
    blocks[1300] = [(4, 60 * 256, 5, 4)]                     # past the clamp
    blocks[1600] = [(4, -60 * 256, 0, 0)]                    # below it, voic 0 -> 1
    blocks[1800] = [(4, 3 * 256, 7, 9)]                      # voic 9 -> 4
    blocks[2000] = [(5, 0, 127, 127)]
    # SETUP: vibrato, an octave up and a fine tune, then drive and a lower level, then back to neutral
    blocks[1200] = [(7, 0xAB5, 0, 0)]                      # C major
    blocks[1201] = [(4, 0, 4, 4)]                          # a minor chord snaps
    blocks[1260] = [(4, 2 * 256, 7, 3)]
    blocks[1320] = [(7, 0x5AD, 0, 0)]                      # another mask
    blocks[1321] = [(4, 5 * 256, 3, 4)]
    blocks[1380] = [(7, 0, 0, 0)]                          # no scale
    blocks[1381] = [(4, 5 * 256, 4, 4)]
    blocks[100] = [(6, 60 | 50 << 8 | 2 << 16 | 70 << 24, 0 | 0 << 8, 0)]
    blocks[101] = [(4, 0, 4, 3)]
    blocks[700] = [(6, 0 | 30 << 8 | 0 << 16 | 64 << 24, 80 | 1 << 8, 0)]
    blocks[701] = [(4, 5 * 256, 3, 4)]
    blocks[760] = [(4, 7 * 256, 3, 4)]                       # POLY: notes on the next voices
    blocks[820] = [(4, 12 * 256, 3, 4)]
    blocks[880] = [(4, 16 * 256, 3, 4)]
    blocks[940] = [(4, 19 * 256, 3, 4)]                      # the fifth takes voice 0 again
    blocks[1000] = [(4, -5 * 256, 3, 2)]                     # a pool of two
    blocks[1100] = [(6, 127 | 127 << 8 | 1 << 16 | 20 << 24, 127 | 0 << 8, 0)]
    blocks[1101] = [(4, 0, 0, 2)]
    blocks[1700] = [(6, 0 | 0 << 8 | 1 << 16 | 64 << 24, 0 | 0 << 8, 0)]
    blocks[1701] = [(4, 0, 0, 1)]
    return blocks


def with_amp(blocks, atk=0, hold=127, rel=127, starts=(), step_every=0):
    """Every block is a frame: the machine calls wcf_clock and wcf_amp once a frame (start = a START this frame). The first block
    starts the AMP (ATK 0, HOLD INF, REL INF opens in 16 frames)."""
    out = []
    for i, b in enumerate(blocks):
        ops = list(b)
        if step_every:
            ops.append((9, i // step_every, 0, 0))
        st = 1 if (i == 0 or i in starts) else 0
        ops.append((8, atk | hold << 8 | rel << 16 | st << 24, 0, 0))
        out.append(ops)
    return out


def scenario_amp():
    """The AMP laws on a stream: notes with finite and infinite HOLD and REL, several ATKs, a warm START, the sequencer's step word
    moving every 22 frames (fps)."""
    n = 3200
    blocks = [[] for _ in range(n)]
    segs = [(0, 0, 127, 127), (400, 40, 24, 50), (1000, 70, 30, 90), (1600, 0, 127, 20), (2000, 10, 20, 127), (2600, 0, 36, 40)]
    starts = {1: (4, 0, 3, 3), 401: (4, 3 * 256, 4, 3), 1001: (4, 7 * 256, 3, 2), 1601: (4, 0, 3, 3), 1620: (4, 4 * 256, 3, 3),
              2001: (4, 12 * 256, 3, 3), 2601: (4, 0, 3, 4), 2640: (4, 5 * 256, 3, 4)}
    for i in range(n):
        atk, hold, rel = [sg[1:] for sg in segs if sg[0] <= i][-1]
        blocks[i].append((9, i // 22, 0, 0))
        if i in starts:
            blocks[i].append(starts[i])
        blocks[i].append((8, atk | hold << 8 | rel << 16 | (1 if i in starts else 0) << 24, 0, 0))
    return blocks


def write_stream(path, blocks):
    with open(path, "wb") as f:
        for b in blocks:
            f.write(struct.pack(">I", len(b)))
            for r in b:
                f.write(struct.pack(">IIII", *[x & 0xffffffff for x in r]))


def run(blocks):
    e = Engine()
    out = []
    for b in blocks:
        for r in b:
            e.cmd(*r)
        out += e.render(BLOCK)
    return out
