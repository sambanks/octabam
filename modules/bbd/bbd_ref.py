"""Float reference for bbd.asm: the same chain, the same per-call structure.

The DSP is proven against this (README.md has the design notes: Pade tanh,
cascaded biquads, per-call coefficients, one tap, mono). render() takes
interleaved stereo floats and a knob list per call, and returns stereo.
"""
import math

SR = 44100
STAGES = (1024, 4096)
# The clock is integer-exact with the DSP (Q23 words), so the two tick on the
# same samples. P16 = clock period in samples / 16 = A + B * value / 128:
# 2 * 44100 * (0.25 + 0.75u) / 10240 samples, u = value / 127.
Q23 = 1 << 23
P16_A, P16_B = 0x113a00, 0x34162c
ALPHA_G = 0x2522                       # 20 ms clock glide
ONE16 = Q23 // 16                      # one sample of clock time
ALPHA_C = 1.0 / 442.0                  # 10 ms compander averager, T/(tau+T)
ALPHA_S = 1.0 / 16.0                   # FDBK and TONE gains, once a call (~256 samples)
ALPHA_M = 1.0 / 32.0                   # MIX and the stage-change fade
LP200 = 0.028093012974530263           # tilt split, one pole at 200 Hz
# FREQ: the tilt's peak, 400 * 5^(v/127) Hz, Q 1.5, unity peak. Polynomials in u = v/128
# (highest power first) for b0/2, -a1/2 and -a2/2, as the DSP evaluates them per call.
BP_B0H = (0.009452, 0.009285, 0.015277, 0.009295)
BP_NA1H = (-0.035066, 0.006, -0.041804, -0.033192, 0.979723)
BP_NA2H = (0.018903, 0.01857, 0.030553, -0.481409)
DC_R = 0.9985752414269434              # 10 Hz DC blocker
NOISE = 0.000632                       # bucket noise, full scale
EPS = 1e-5
GP_POLY = (1.049345, 0.461198, 0.306334)    # 10^(0.45u) - 1, u = 0..1: +-9 dB
CL_POLY = (-1.030412, 0.500651, -0.115924)  # 10^(-0.45u) - 1
LCG_M, LCG_C, SEED = 1664525, 1013904223 & 0xffffff, 0x5a5a5b
CLEAR_CALLS, FADE_CALLS = 16, 16
# Butterworth sections, ascending Q: AA = 8th order, recon = 7th + 2nd
AA_Q = (0.5097955791041592, 0.6013448869350453, 0.8999762231364156, 2.5629154477415055)
RC_Q = (0.5549581320873712, 0.7071067811865476, 0.8019377358048383, 2.246979603717467)


def poly3(c, u):
    return u * (c[0] + u * (c[1] + u * c[2]))


# HPF: a 2-pole Butterworth HPF at 400 * 20^((v-127)/126) Hz; K = KMAX2 * 2^-e / 2 through
# LIM's 2^-f fit, e = log2(20) (127-v)/126, from the DSP's Q23 words
PRE_E8 = 0x463f9d / Q23                # e/8 per (127 - v)/128
PRE_KMAX2 = 0x074bf7 / Q23             # 2 tan(pi 400 / sr)


def hp_coefs(K):
    """b0 b1 b2 a1 a2 of the HPF for K = tan(pi fc / sr)."""
    d = 1 + math.sqrt(2) * K + K * K
    return (1 / d, -2 / d, 1 / d, 2 * (K * K - 1) / d, (1 - math.sqrt(2) * K + K * K) / d)


LIM_POW = (-0.019755, 0.1152969, -0.3455381, 0.4999493)   # 2^-f / 2, f = 0..1


def horner(c, u):
    y = 0.0
    for k in c:
        y = y * u + k
    return y


def sat(v):
    return max(-1.0, min(1.0 - 1 / Q23, v))


def limit(w):
    """The output stage: linear to 0.5, then 0.5 + 2e - 2e^2 (e = (|w| - 0.5) / 2),
    reaching exactly 1.0 with zero slope at |w| = 1.5. Only what leaves the effect."""
    e = min((abs(w) - 0.5) / 2, 0.5)
    return w if e <= 0 else math.copysign(0.5 + 2 * e - 2 * e * e, w)


def tan_series(t):
    t2 = t * t
    return t + t * t2 * (1 / 3 + t2 * (2 / 15 + t2 * (17 / 315 + t2 * 62 / 2835)))


def coefs(p16):
    """DF1 sections for the cutoff sr/(3P), as the DSP computes them."""
    K = tan_series(0.0654498 / p16)
    K2 = K * K
    def bq(q):
        d = 1 + K / q + K2
        b0 = K2 / d
        return (b0, 2 * b0, b0, -2 * (K2 - 1) / d, -(1 - K / q + K2) / d)
    d1 = 1 + K
    one = (K / d1, K / d1, (1 - K) / d1)
    return [bq(q) for q in AA_Q], one, [bq(q) for q in RC_Q]


def sections(p16):
    """The nine in DSP order: anti-alias 0..3, the real pole, reconstruction 0..3."""
    aa, one, rc = coefs(p16)
    return aa + [one] + rc


class BBD:
    def __init__(self):
        self.clear = CLEAR_CALLS
        self.fade = 0
        self.stage = None
        self.lcg = SEED
        self.probe = None                            # per-sample hook for tests: probe(self, v)
        self.hp_s = [0.0] * 4                        # HPF x1 x2 y1 y2
        self.pk = 0.0                                # HPF's K, gliding (zeroed by init only)
        self.reset()

    def reset(self):
        self.snap = True
        self.p16 = self.t16 = 0                      # Q23 integers
        self.prev_in = 0.0
        self.held = 1 / 16                           # poly(0): the DC every bucket carries,
        self.avg_c, self.prev_q = 1.0, 1.0          # warm start: the compressor's last output = 1
        self.avg_e = 0.0
        self.dc_x, self.dc_y = 1 / 16, 0.0          # already through the filters: a quiet start
        self.l = 0.0
        self.bp = [0.0] * 4                          # w1 w2 y1 y2
        self.bpc = [0.0] * 3                         # b0/2, -a1/2, -a2/2, glided
        self.fb = self.mg = 0.0
        self.cl, self.ch, self.gp = 1.0, 1.0, 0.0
        self.aa = [[0.0, 0.0] for _ in range(5)]     # boundaries: in, after each section
        self.rc = [[1 / 16, 1 / 16] for _ in range(6)]
        self.wet = 0.0
        self.ring = None
        self.wp = 0

    def call(self, frames, knobs):
        """frames: list of (L, R); knobs: 12 values 0..127.
        TIME 0, FDBK 1, FRZ 2, TONE 3, FREQ 4, MIX 5, STGS 6, LIM 8, HPF 10, kill flag 11 (0 = kill)."""
        sidx = min(knobs[6], 1)
        if knobs[11] == 0 and not self.clear:        # the stop kill: dry and clear now
            self.clear, self.fade = CLEAR_CALLS, 0
        if self.clear:
            self.clear -= 1
            if self.clear == 1:                      # the call before the reset: all nine for TIME's clock
                self.coef = sections((P16_A + (P16_B * knobs[0] >> 7)) / Q23)
            if not self.clear:
                self.reset()
                self.stage = sidx
                self.ring = [0.0] * (STAGES[sidx] - 1)   # the tap: stages - 1 ticks
            return list(frames)
        if sidx != self.stage and not self.fade:
            self.fade = FADE_CALLS
        fading = bool(self.fade)
        if self.fade:
            self.fade -= 1
            if not self.fade:
                self.clear = CLEAR_CALLS
        p_t = P16_A + (P16_B * knobs[0] >> 7)
        if self.snap:
            self.p16 = p_t
        fb_t = knobs[1] / 128
        t = (knobs[3] - 64) / 64
        if t >= 0:
            cl_t, ch_t, gp_t = 1 + poly3(CL_POLY, t), 1 + poly3(GP_POLY, t), 0.0
        else:
            cl_t, ch_t, gp_t = 1.0, 1.0, poly3(GP_POLY, -t)
        m_t = 1.0 if knobs[5] == 127 else knobs[5] / 128
        if fading:
            m_t = 0.0
        self.cl += ALPHA_S * (cl_t - self.cl)
        self.ch += ALPHA_S * (ch_t - self.ch)
        self.gp += ALPHA_S * (gp_t - self.gp)
        self.fb += ALPHA_S * (fb_t - self.fb)
        # LIM: above T = 2^(-3.5v/127) (0: off, 127: 2^-3.5) the expander's envelope scales
        # FDBK by (T/env)^2, so self-oscillation settles near T; even dB steps a value
        e = 3.499782999565999 * knobs[8] / 127
        lim_t = 2 * horner(LIM_POW, e - int(e)) / 2 ** int(e)
        # FRZ below 127 fades the input out of the line and takes FDBK h of the way
        # up to sustain, 127/128 over TONE's peak gain (never down: an oscillating
        # loop keeps its FDBK, and LIM its level); 127 loops the line itself exactly
        hold, frozen = knobs[2] / 128, knobs[2] == 127
        sustain = (127 / 128) / (max(self.cl, self.ch) + self.gp)
        fbh = self.fb + hold * max(0.0, sustain - self.fb)
        self.fbe = fbh * (1.0 if self.avg_e <= lim_t else (lim_t / self.avg_e) ** 2)
        fu = knobs[4] / 128
        bp_t = [horner(c, fu) for c in (BP_B0H, BP_NA1H, BP_NA2H)]
        self.bpc = bp_t if self.snap else [c + ALPHA_S * (n - c) for c, n in zip(self.bpc, bp_t)]
        # HPF (slot 10): 0 OFF, else the HPF; K glides like FREQ
        hp_on = knobs[10] > 0
        e = 8 * PRE_E8 * (127 - knobs[10]) / 128
        pk_t = PRE_KMAX2 * horner(LIM_POW, e - int(e)) / 2 ** int(e)
        self.pk = pk_t if self.snap else self.pk + ALPHA_S * (pk_t - self.pk)
        self.hp_c = hp_coefs(self.pk)
        # one of the nine sections follows the clock each call, all nine after a reset
        new = sections(self.p16 / Q23)
        if self.snap:                                # the nine came a call before the reset: the last now
            self.coef[8], self.rot, self.snap = new[8], 0, False
        else:
            self.coef[self.rot] = new[self.rot]
            self.rot = (self.rot + 1) % 9
        aa, one, rc = self.coef[:4], self.coef[4], self.coef[5:]
        out = []
        for L, R in frames:
            self.p16 += ALPHA_G * (p_t - self.p16) >> 23
            self.mg += ALPHA_M * (m_t - self.mg)
            mono = self._hp((L + R) / 2, hp_on)
            # tone on the previous wet: tilt split + unity-peak bandpass
            w = self.wet
            self.l += LP200 * (w - self.l)
            h = w - self.l
            w1, w2, y1, y2 = self.bp
            b0h, na1h, na2h = self.bpc
            bp = 2 * (b0h * (w - w2) + na1h * y1 + na2h * y2)
            self.bp = [w, w1, bp, y1]
            x = mono * (1 - hold) + self.fbe * (self.cl * self.l + self.ch * h + self.gp * bp)
            # Pade tanh folded into the 2:1 feedback compressor's divide
            x = max(-3.0, min(3.0, x))
            self.avg_c += ALPHA_C * (abs(self.prev_q) - self.avg_c)
            q = x * (27 + x * x) / ((27 + 9 * x * x) * (self.avg_c + EPS))
            q = max(-2.0, min(2.0, q))
            self.prev_q = q
            v = self._cascade(q, aa, self.aa)
            # the clocked bucket line
            if self.t16 > self.p16:
                frac = min((self.t16 - self.p16) * 16, Q23 - 1) / Q23
                s = frac * v + (1 - frac) * self.prev_in
                raw = self.ring[self.wp]
                self.ring[self.wp] = raw if frozen else s
                self.wp = (self.wp + 1) % len(self.ring)
                raw = raw - raw * raw / 166 - raw ** 3 / 32 + 1 / 16
                self.lcg = (self.lcg * LCG_M + LCG_C) & 0xffffff
                n = (self.lcg - (1 << 24) if self.lcg & 0x800000 else self.lcg) / (1 << 23)
                self.held = raw + NOISE * n
                self.t16 -= self.p16
            self.prev_in = v
            self.t16 += ONE16
            # reconstruction: one pole, then the 7th's pairs and the 2nd
            b = self.rc
            x1 = b[0][0]
            yo = one[0] * self.held + one[1] * x1 + one[2] * b[1][0]
            b[0][:] = [self.held, x1]
            y = self._cascade(yo, rc, b[1:])
            self.dc_y = y - self.dc_x + DC_R * self.dc_y
            self.dc_x = y
            self.avg_e += ALPHA_C * (abs(self.dc_y) - self.avg_e)
            self.wet = self.dc_y * self.avg_e
            w = limit(self.wet)
            # MIX: the wet rises to unity by 64 with the dry whole, then the dry fades
            # out by 127; a sum past full scale saturates, as the DSP's move does
            gw, k = min(1.0, 2 * self.mg), max(0.0, 2 * self.mg - 1)
            out.append((sat(L - k * L + gw * w), sat(R - k * R + gw * w)))
            if self.probe:
                self.probe(self, v)
        return out

    def _hp(self, x, on):
        if not on:                                   # skipped: its state waits
            return x
        b0, b1, b2, a1, a2 = self.hp_c
        x1, x2, y1, y2 = self.hp_s
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        self.hp_s = [x, x1, y, y1]
        return y

    @staticmethod
    def _cascade(x, sections, bounds):
        for k, (b0, b1, b2, na1, na2) in enumerate(sections):
            i1, i2 = bounds[k]
            o1, o2 = bounds[k + 1]
            y = b0 * x + b1 * i1 + b2 * i2 + na1 * o1 + na2 * o2
            bounds[k][:] = [x, i1]
            x = y
        last = bounds[len(sections)]
        last[:] = [x, last[0]]
        return x


def render(stereo, knob_calls, frames=16):
    """stereo: list of (L, R); knob_calls: one 12-value knob list per call."""
    fx, out = BBD(), []
    for i, knobs in enumerate(knob_calls):
        out += fx.call(stereo[i * frames:(i + 1) * frames], knobs)
    return out
