"""OCTA303 hybrid at the source seam: the ColdFire half and the record (coordination, 19 Nov 2026; code written by Claude).

The ColdFire keeps ref303 up to u (split303.cf_front) and the control step; per frame it ships one record in the
track's source slot, in place of the finished samples.  The DSP (o3h.asm) renders the rest (split303.dsp_chain).

THE RECORD (v9.1, 25 Nov 2026: every voice; 84 DSP words per track; each word carries one 16-bit half of a ColdFire long, high half first, in its
low 16 bits; the bits above are not trusted and are masked):
  w0   $a303            signature (stock: the high half of the sample count, always 0; ANALOG BD: $ab09)
  w1   flags            bit 0: a new voice (the DSP zeroes its 16 state words first)
  w2   $0303            signature
  w3   start | np << 8  the first sample this frame renders (0..15; samples before it are silent) and the number of
                        pieces (1..3).  The pieces cover [start, 16) exactly
  w4.. pieces, 15 halves each: n, c1, b, k, clg, cli, cll hi, cll lo, w2, gcomp, amp hi, amp lo, ampstep (signed),
                        flags, osin.  flags: bit 0 FM, bits 2..1 MUFF (0 off, 1 SOFT, 2 HARD), bit 3 DIST, bit 4
                        SWP ACID (the ladder clip's operating point), bit 5 KEEP: no FM now, but FM has moved the
                        coefficients since the last control step, so they stay the last FM sample's (ref303 keeps them
                        until its next control step); the DSP ignores the piece's c1 b k clg cli cll then.  With FM the DSP sets c1 b k and the clip per
                        sample, and the piece's c1 b k clg carry sctrl kmul ud fmq instead.  osin: DRIV's gain (Q12)
  w52+2i  u of sample i, high half, low half (a signed 32-bit long)
A piece is a run of samples with the same control words: one starts at each render call and after each control step.
amp is the VCA level at the piece's first sample, before its step: the DSP does amp = max(0, amp + step) per sample;
the ColdFire keeps the same level as max(0, amp + n * step) at the piece's end (exact: the step is constant)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split303 as S
R, T = S.R, S.T
SIG0, SIG1, W_U, W_PC, PIECE = 0xA303, 0x0303, 52, 4, 15
MAXP = 3

def hybrid_ok(st):
    """v9.1: always (every voice is the seam's).  v9.0 carried no FM, MUFF, DIST or DRIV; Voice.call's ColdFire branch
    and CHAIN are kept for that history and for a build without the seam, and are not reached with it."""
    return True

def flags(st):
    """the piece's flags; FM's KEEP bit: st.fmd = an FM piece opened since the last control step (an empty one is
    dropped, and then a control step follows at once and clears it)"""
    f = (1 if st.fmq else 0) | st.muff << 1 | (8 if st.dist else 0) | (16 if st.swp == 2 else 0)
    if st.fmq: st.fmd = 1
    elif getattr(st, 'fmd', 0): f |= 32
    return f

class Frame:
    def __init__(self):
        self.u = [0] * 16; self.pieces = []; self.start = None; self.cur = None; self.pos = 0; self.new = 0
    def open(self, st):
        if st.fmq: c = [st.sctrl, st.kmul, st.ud, st.fmq]
        else: c = [st.c1, st.b, st.k, st.clg]
        self.cur = [0] + c + [st.cli, st.cll, st.w2, st.gcomp, st.amp, st.ampstep, flags(st), st.osin]
    def close(self, st):
        c = self.cur; self.cur = None
        if not c or c[0] == 0: return
        st.amp = max(0, c[9] + c[0] * c[10])
        self.pieces.append(c)
    def words(self):
        """the record's 84 halves (None when this frame rendered nothing: no signature, the stock samples stand)"""
        if not self.pieces: return None
        assert len(self.pieces) <= MAXP, len(self.pieces)
        assert self.start + sum(p[0] for p in self.pieces) == 16, (self.start, [p[0] for p in self.pieces])
        w = [0] * 84
        w[0], w[1], w[2], w[3] = SIG0, self.new, SIG1, self.start | len(self.pieces) << 8
        for j, (n, c1, b, k, clg, cli, cll, w2, gc, amp, step, fl, osin) in enumerate(self.pieces):
            assert 1 <= n <= 16 and 0 <= cll < 1 << 23 and 0 <= amp < 1 << 23 and -32768 <= step < 32768
            for v in (c1, b, k, clg, cli, w2, gc, fl, osin): assert 0 <= v < 65536, v
            w[W_PC + PIECE * j: W_PC + PIECE * (j + 1)] = [n, c1, b, k, clg, cli, cll >> 16, cll & 0xFFFF, w2, gc,
                                                           amp >> 16, amp & 0xFFFF, step & 0xFFFF, fl, osin]
        for i, u in enumerate(self.u):
            u &= 0xFFFFFFFF; w[W_U + 2 * i], w[W_U + 2 * i + 1] = u >> 16, u & 0xFFFF
        return w

def render_call(st, w, start, code, n, fr, alive=True, df=None, last=None, seq=None, setup=None):
    """ref303.render_call with the sample loop cut at u: the ColdFire half.  Returns the number of samples it covered
    (0 = stock's samples stand for this call)."""
    if start and code >= 0:
        R.set_df(st, df); R.set_setup(st, setup, df)
    if start:
        if code >= 0: R.note_on(st, code, w); st.latched = 1
        else: st.latched = 0
    if st.latched and last and seq is not None:
        R.set_df(st, df); R.set_setup(st, setup, df); R.gate_frame(st, seq)
    if not st.latched or not alive or n == 0:
        fr.pos += n; return 0
    R.set_df(st, df); R.set_setup(st, setup, df)
    st.ptgt = R.clamp(R.p_of_word(w[0]) + st.fine, T.P_LO, T.P_HI)
    st.cut, st.res, st.env, st.dec = R.raw(w[1]), R.raw(w[2]), R.raw(w[3]), R.raw(w[4])
    if fr.start is None: fr.start = fr.pos
    fr.open(st)
    for _ in range(n):
        st.cs -= 1
        if st.cs == 0:
            fr.close(st); st.cs = T.CS; R.ctrl(st); st.fmd = 0; fr.open(st)
        fr.u[fr.pos] = S.cf_front(st); fr.pos += 1; fr.cur[0] += 1
    fr.close(st)
    return n

def dsp_model(dst, words):
    """the DSP half in Python (split303.dsp_chain over the record): the 16 output words X:0.. (v << 8, L = R)"""
    out = [0] * 16
    if words is None: return None
    if words[1] & 1:
        for a in ('fb', 'y1', 'y2', 'y3', 'y4', 'vp1', 'vp2', 'dc', 'amp', 'ovca', 'flp', 'mlo', 'tone'): setattr(dst, a, 0)
    start, np_ = words[3] & 0xFF, words[3] >> 8
    i = start
    for j in range(np_):
        p = words[W_PC + PIECE * j: W_PC + PIECE * (j + 1)]
        n = p[0]
        fl = p[13]
        dst.fmq = 0
        if fl & 1: dst.sctrl, dst.kmul, dst.ud, dst.fmq = p[1:5]
        elif not fl & 32: dst.c1, dst.b, dst.k, dst.clg = p[1:5]
        if not fl & 32: dst.cli = p[5]; dst.cll = p[6] << 16 | p[7]
        dst.w2, dst.gcomp = p[8], p[9]
        dst.amp = p[10] << 16 | p[11]; dst.ampstep = p[12] - 65536 if p[12] & 0x8000 else p[12]
        dst.muff, dst.dist, dst.swp, dst.osin = (fl >> 1) & 3, (fl >> 3) & 1, 2 if fl & 16 else 0, p[14]
        for _ in range(n):
            u = words[W_U + 2 * i] << 16 | words[W_U + 2 * i + 1]
            if u & 0x80000000: u -= 1 << 32
            v = R.clamp(S.dsp_chain(dst, u) >> T.SHIFT_OUT, -32767, 32767)
            out[i] = (v << 8) & 0xFFFFFF; i += 1
    return out

# ---------------------------------------------------------------- the whole ColdFire call on an O3_SEAM build
CHAIN = ('y1', 'y2', 'y3', 'y4', 'fb', 'dc', 'tone', 'ovca', 'mlo', 'vp1', 'vp2', 'flp')

class Voice:
    """octa303.s with O3_SEAM = 1, one track: st = its ColdFire state, hmode = H_MODE (1: the DSP has the chain)."""
    def __init__(self):
        self.st = R.Track(); self.hmode = 0; self.fr = None
    def call(self, w, start, code, n, df=None, setup=None, last=None, seq=None, frame_start=False):
        """one sy_render call; returns the longs it leaves in the header's L/R pairs (None: stock's stand)."""
        st = self.st
        if frame_start or self.fr is None: self.fr = Frame()
        fr = self.fr
        if start and code >= 0:
            R.set_df(st, df); R.set_setup(st, setup, df)
        if start:
            if code >= 0: R.note_on(st, code, w); st.latched = 1
            else: st.latched = 0
        if st.latched and last and seq is not None:
            R.set_df(st, df); R.set_setup(st, setup, df); R.gate_frame(st, seq)
        if not st.latched or n == 0:
            fr.pos += n; return None
        R.set_df(st, df); R.set_setup(st, setup, df)
        st.ptgt = R.clamp(R.p_of_word(w[0]) + st.fine, T.P_LO, T.P_HI)
        st.cut, st.res, st.env, st.dec = R.raw(w[1]), R.raw(w[2]), R.raw(w[3]), R.raw(w[4])
        fr.last_hyb = hybrid_ok(st)
        if hybrid_ok(st):
            if fr.start is None: fr.start = fr.pos
            fr.open(st)
            for _ in range(n):
                st.cs -= 1
                if st.cs == 0:
                    fr.close(st); st.cs = T.CS; R.ctrl(st); st.fmd = 0; fr.open(st)
                fr.u[fr.pos] = S.cf_front(st); fr.pos += 1; fr.cur[0] += 1
            fr.close(st)
            return [0] * n
        if self.hmode:                       # back from the DSP: the ColdFire's chain from rest
            for a in CHAIN: setattr(st, a, 0)
            self.hmode = 0
        out = []
        for _ in range(n):
            st.cs -= 1
            if st.cs == 0:
                st.cs = T.CS; R.ctrl(st)
            v = R.clamp(R.sample(st) >> T.SHIFT_OUT, -32767, 32767)
            out.append((v << 16) & R.M32)
        fr.pos += n
        return out
    def frame_end(self):
        """after the frame's last call: the record (None: not written)"""
        words = self.fr.words() if self.fr and getattr(self.fr, 'last_hyb', False) else None
        if words is not None:
            if not self.hmode: words[1] |= 1
            self.hmode = 1
        return words
