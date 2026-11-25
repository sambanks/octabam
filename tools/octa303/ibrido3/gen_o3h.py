"""Generates o3h.asm: OCTA303's hybrid voice at the source seam, DSP half (coordination, 19 Nov 2026; code written by
Claude).  The glue (the seam's jsr, the record, the pieces) and the chain from u to the output word, integer-exact
against ref303 (split303.dsp_chain).  The record format is hyb.py's docstring.  v9.1 (25 Nov 2026): the whole voice
after u -- FM (smoothed, 1/4 a sample), MUFF SOFT/HARD, DIST and DRIV join the smooth chain, so every voice plays here.

Every ref303 fm(d, c, pre, post) = floor(floor(d / 2^pre) * c / 2^post) is done as: d in an accumulator (56-bit,
exact); asr #pre; A = acc1; mpy A,c (the 48-bit product = 2*A*c, exact); asl #(23 - post); acc1 = the result, acc0
the dropped fraction.  Exact while A, c < 2^23 and the result < 2^23 (split303/stress.py, extreme.py).

Only instruction forms with a stock site in the 1.40C payloads, or a row of CHIP.md's instruction-form register
(sam/main), are used (trap-chip-form; checked by forms2.py).  Branches go forward only (trap-bra-back), no `rep`, no
`tfr`, no `cmp a,b` (trap-asm), mpy only in the orders stock uses (y0,x0 / x1,y0 / y1,x1 / x0,x0), no label a prefix
of another (oh + two digits + a letter, all five characters).

Memory: the voice's block of 64 words at X:STATE + 2 * x:$418 (x:$418 = 0/$20/$40/$60, the track within the core):
its 32 state words, then the piece's control block (r7 + CB); in stock's unreferenced X:$7a92-$7fff, in the 8K block
no DMA touches
(FAILURE_MODES "dense core work in a DMA's memory block").  The tables are the section's ptable (PTABLE below), read
with p:( (the build rewrites them to x:( in the stock curve bank); its base is the one $fab1e0 literal, kept in the
control block with the sub-tables' addresses.  Output: X:0 + 2i = X:0 + 2i + 1 = v << 8, as the stock
source writes the ColdFire's v << 16 sample (P:0x3d0..0x3d2, 0x40f..0x41a)."""
import os, sys
sys.path.insert(0, os.environ.get('REF303_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
import o3tables as T

import ref303 as R
STATE = 0x7C00                         # four voice blocks of 64 words (x:$418 * 2): the state, then the control
NSTATE, CB, NCTL = 32, 32, 30       # block at +CB (all of it by r7: the (r7+N) forms are stock's own)
# state X:(r7+n): 24-bit words, the ladder's four 32-bit (low 24 bits here, the high byte at +8)
(S_FB, S_Y1, S_Y2, S_Y3, S_Y4, S_VP1, S_VP2, S_DC, S_AMP, S_FBV, S_Y0V, S_OV, S_Y1H, S_Y2H, S_Y3H, S_Y4H,
 S_FLP, S_MLO, S_TONE, S_OVC, S_KC1, S_KB, S_KK, S_KCLG, S_KCLI, S_KCLL, S_KCLN, S_T1, S_T2) = range(29)
HI = {S_Y1: S_Y1H, S_Y2: S_Y2H, S_Y3: S_Y3H, S_Y4: S_Y4H}
# control block X:(r6+n): P_N..P_OSIN decoded from the piece by the glue (its 15 halves in order), the rest derived
(P_N, P_C1, P_B, P_K, P_CLG, P_CLI, P_CLL, P_CLN, P_W2, P_GC, P_AMP0, P_STEP, P_FLG, P_OSIN,
 P_SCT, P_KM, P_UD, P_FMQ, P_FMF, P_MUF, P_DIS, P_ACI, P_DRV, P_TB, P_FMT, P_CLT, P_DRT, P_DRC, P_ANY, P_TBP) = range(30)
assert NCTL == 30 and S_T2 < NSTATE
W_U, W_PC, PIECE = 52, 4, 15
PTAB = '$fab1e0'                       # schema.DspSection.ptable: the tables below, one block
# FM's table: per ladder index i the four words LB LK KF KD (kfb's inputs and the ladder's b); the clip's: per j = i -
# CL_I0 the three words CL_G CL_INV CL_LIM; DRIV's tanh; DRIV's constants per side (+ then -): K, 4 (L - K), R, L - K
FMT = [v for i in range(len(R.LB)) for v in (R.LB[i], R.LK[i], T.KF[i], T.KD[i])]
CLT = [v for j in range(len(T.CL_G)) for v in (T.CL_G[j], T.CL_INV[j], T.CL_LIM[j])]
DRC = [T.DRV_KP, 4 * (T.DRV_LP - T.DRV_KP), T.DRV_RP, T.DRV_LP - T.DRV_KP,
       T.DRV_KN, 4 * (T.DRV_LN - T.DRV_KN), T.DRV_RN, T.DRV_LN - T.DRV_KN]
O_P6, O_FMT = 0, 516
O_CLT = O_FMT + len(FMT); O_DRT = O_CLT + len(CLT); O_DRC = O_DRT + len(T.DRV_TH)
ptable = list(T.P6_F) + list(T.P6_FP) + FMT + CLT + list(T.DRV_TH) + DRC
assert len(T.P6_F) == 258 and len(T.P6_FP) == 258 and len(T.DRV_TH) == 258 and len(ptable) == O_DRC + 8
assert all(0 <= v < 1 << 23 for v in ptable)
assert len(R.LB) == len(R.LK) == len(T.KF) == len(T.KD) and ((T.S_MAX - 1) >> 6) < len(R.LB)
assert ((T.S_MAX - 1) >> 6) - T.CL_I0 < len(T.CL_G)

L = []
_lab = {}
def e(s): L.append('        ' + s)
def lab(name):
    L.append(name + ':')
def neg24(v): return (1 << 24) - v

def fm(acc, pre, coef, post):
    """acc = d (exact) -> acc1 = fm(d, coef, pre, post); coef is a load into x0 ('#>N' or 'x:(r6+N)')"""
    if pre: e('asr     #%d,%s,%s' % (pre, acc, acc))
    e('move    %s,x0' % coef)                # (v9.1: before the a1 read, so the shift's result is settled:
    e('move    %s1,y0' % acc)                # DSP_AUDIT T25, one stall less; the same registers written)
    e('mpy     y0,x0,%s' % acc)
    s = 23 - post
    e('asl     #%d,%s,%s' % (s, acc, acc))

def ld32(acc, st):
    """acc2:acc1 = the 32-bit state (acc0 = 0)"""
    e('move    x:(r7+%d),%s' % (HI[st], acc))
    e('move    x:(r7+%d),%s0' % (st, acc))
    e('asl     #24,%s,%s' % (acc, acc))

def st32a(st):
    """the 32-bit state from a2:a1 (b is clobbered).  v9.1: the shift first, so neither move reads an accumulator
    the instruction before it wrote (DSP_AUDIT T25: two stalls less)"""
    e('asr     #24,a,b')
    e('move    a1,x:(r7+%d)' % st)
    e('move    b1,x:(r7+%d)' % HI[st])

def softclip_inline():
    clamp_a('#>1482910', '#>%d' % neg24(1482910))
    for s in ('move    a1,x1', 'move    x1,a', 'asr     #8,a,a', 'move    a1,x0', 'mpy     x0,x0,a', 'asl     #11,a,a',
              'move    a1,y0', 'mpy     y0,x0,a', 'asl     #11,a,a', 'move    a1,y0', 'move    #>10923,x0',
              'mpy     y0,x0,a', 'asl     #15,a,a', 'move    a1,x0', 'move    x1,a', 'sub     x0,a'):
        e(s)
def clamp_a(hi, lo_neg):
    """a = clamp(a, -lo, hi): the upper bound through y1, the lower through x0 (both 56-bit compares)"""
    e('move    %s,y1' % hi)
    e('cmp     y1,a')
    e('tge     y1,a')
    e('move    %s,x0' % lo_neg)
    e('cmp     x0,a')
    e('tlt     x0,a')

L.append('; o3h -- generated by gen_o3h.py (OCTA303 hybrid, the DSP half at the source seam).  Do not edit.')
# ================================================================== the seam
lab('oh01s')
e('move    a,x:>$20e')                 # the stock instruction the jsr replaced
e('move    x:>$209,r4')                # this track's source record
e('move    x:(r4),a')
e('and     #>$ffff,a')                 # (and leaves a2: the half's untrusted bit 23 sign-extended)
e('move    a1,x0')
e('move    x0,a')
e('move    #>$a303,x0')
e('cmp     x0,a')
e('bne     oh02n')
e('move    x:(r4+2),a')
e('and     #>$ffff,a')
e('move    a1,x0')
e('move    x0,a')
e('move    #>$0303,x0')
e('cmp     x0,a')
e('beq     oh03y')
lab('oh02n')
e('rts')                               # not ours: the stock source (a, x0, r4 and the flags are its to reload)
lab('oh03y')
e('move    x:>$20b,a')                 # the next track's FLEX ring base, as the stock source advances it
e('add     #>$80,a')
e('move    a,x:>$20b')
for m in (0, 1, 4, 6, 7):              # linear (stock's source leaves m6 linear; the others are linear here)
    e('move    #>$ffffff,m%d' % m)
# v10.0 (vFable's review of v9.1): a record whose sizes do not add up is not rendered.  start + the pieces' n must
# be 16 (hyb.Frame.words asserts it; octa303.s writes it so): else the zero fill (2 * start words) or a piece (2 n
# words) could write past X:0..31.  A record that fails renders 32 zeros (silence) and continues after the source.
# (A refused record that carried w1 = 1, a new voice, does not clear the state: the next record has w1 = 0 and the
# voice goes on from the old state.  Only a damaged record can be refused: octa303.s always writes start + n = 16.)
e('move    x:(r4+3),a')
e('and     #>$ff,a')
e('move    a1,x0')
e('move    x0,b')                      # b = start
e('move    x:(r4+3),a')
e('lsr     #8,a')
e('and     #>$3,a')
e('move    a1,y1')                     # y1 = the pieces (0..3)
for j, lb in enumerate(('oh34a', 'oh35b', 'oh36c')):
    e('move    y1,a')
    e('move    #>%d,x0' % j)
    e('cmp     x0,a')
    e('ble     %s' % lb)               # piece j absent
    e('move    x:(r4+%d),a' % (W_PC + PIECE * j))
    e('and     #>$ffff,a')
    e('move    a1,x0')
    e('add     x0,b')
    lab(lb)
e('move    #>16,x0')
e('cmp     x0,b')
e('beq     oh37k')
e('move    #0,r3')
e('clr     b')
e('do      #32,oh38z')
e('move    b,x:(r3)+')
lab('oh38z')
e('bra     oh08d')
lab('oh37k')
e('move    x:>$418,a')                 # the voice's block (64 words)
e('asl     a')
e('add     #>$%x,a' % STATE)
e('move    a,r5')
e('lua     (r5+0),r7')
e('move    x:(r4+1),a')                # a new voice: its state from zero
e('and     #>$1,a')
e('move    a1,x1')
e('move    x1,a')
e('beq     oh04o')
e('lua     (r7+0),r1')
e('clr     a')
e('do      #%d,oh05z' % NSTATE)
e('move    a,x:(r1)+')
lab('oh05z')
lab('oh04o')
e('move    #0,r3')                     # the output, X:0 as the stock source writes it
e('move    x:(r4+3),a')
e('and     #>$ff,a')                   # start: the silent samples first
e('move    a1,x1')
e('move    x1,a')
e('asl     a')
e('move    a1,x1')                     # 2 * start
e('move    r4,b')                      # u of the first sample rendered: w44 + 2 * start
e('add     #<%d,b' % W_U)
e('add     x1,b')
e('move    b,r0')
e('tst     a')
e('beq     oh06f')
e('clr     b')
e('do      a,oh07f')
e('move    b,x:(r3)+')
lab('oh07f')
lab('oh06f')
e('move    x:(r4+3),a')
e('lsr     #8,a')
e('and     #>$3,a')                    # the pieces
e('move    a1,x1')
e('move    x1,a')
e('beq     oh08d')
e('lua     (r7+%d),r6' % CB)            # the tables' addresses, once a frame
e('move    #>%s,x0' % PTAB)
e('move    x0,x:(r6+%d)' % P_TB)
for slot, off in ((P_TBP, 258), (P_FMT, O_FMT), (P_CLT, O_CLT), (P_DRT, O_DRT), (P_DRC, O_DRC)):
    e('move    x0,b')
    e('add     #>%d,b' % off)
    e('move    b1,x:(r6+%d)' % slot)
e('move    #>%d,n4' % W_PC)
e('move    (r4)+n4')
e('do      a,oh09p')
e('lua     (r7+%d),r6' % CB)            # decode one piece into the control block
for f in ('n', 'c1', 'b', 'k', 'clg', 'cli'):
    e('move    x:(r4)+,b')
    e('and     #>$ffff,b')
    e('move    b1,x0')
    e('move    x0,x:(r6)+')
e('move    x:(r4)+,b')                 # cll: 32 bits, then -cll
e('and     #>$ffff,b')
e('asl     #16,b,b')
e('clr     a')
e('add     b,a')
e('move    x:(r4)+,b')
e('and     #>$ffff,b')
e('move    b1,x0')
e('add     x0,a')
e('move    a,x:(r6)+')
e('neg     a')
e('move    a,x:(r6)+')
for f in ('w2', 'gc'):
    e('move    x:(r4)+,b')
    e('and     #>$ffff,b')
    e('move    b1,x0')
    e('move    x0,x:(r6)+')
e('move    x:(r4)+,b')                 # amp: 32 bits
e('and     #>$ffff,b')
e('asl     #16,b,b')
e('clr     a')
e('add     b,a')
e('move    x:(r4)+,b')
e('and     #>$ffff,b')
e('move    b1,x0')
e('add     x0,a')
e('move    a,x:(r6)+')
e('move    x:(r4)+,b')                 # ampstep: signed 16
e('and     #>$ffff,b')
e('asl     #8,b,b')
e('move    b1,x0')
e('move    x0,b')
e('asr     #8,b,b')
e('move    b,x:(r6)+')
for f in ('flags', 'osin'):
    e('move    x:(r4)+,b')
    e('and     #>$ffff,b')
    e('move    b1,x0')
    e('move    x0,x:(r6)+')
e('lua     (r7+%d),r6' % CB)
for k in range(4):                     # with FM the piece's c1 b k clg are sctrl kmul ud fmq
    e('move    x:(r6+%d),x0' % (P_C1 + k))
    e('move    x0,x:(r6+%d)' % (P_SCT + k))
for slot, sh, m in ((P_FMF, 0, 1), (P_MUF, 1, 3), (P_DIS, 3, 1), (P_ACI, 4, 1)):
    e('move    x:(r6+%d),a' % P_FLG)  # (16 bits, decoded clean: a2 = 0)
    if sh: e('lsr     #%d,a' % sh)
    e('and     #>%d,a' % m)
    e('move    a1,x:(r6+%d)' % slot)
e('move    x:(r6+%d),a' % P_OSIN)      # DRIV on: OSIN != DRV_G0
e('move    #>%d,x0' % T.DRV_G[0])
e('move    #0,y1')
e('move    #>1,b')
e('cmp     x0,a')
e('teq     y1,b')
e('move    b1,x:(r6+%d)' % P_DRV)
e('move    x:(r6+%d),a' % P_FLG)      # MUFF or DIST: one test a sample skips both when neither is on
e('and     #>$e,a')
e('move    a1,x:(r6+%d)' % P_ANY)
e('move    x:(r6+%d),a' % P_FLG)      # KEEP: the coefficients of the last FM sample (the state's copy)
e('lsr     #5,a')
e('and     #>1,a')
e('beq     oh18k')
for k in range(7):
    e('move    x:(r7+%d),x0' % (S_KC1 + k))
    e('move    x0,x:(r6+%d)' % (P_C1 + k))
lab('oh18k')
e('bsr     oh10c')
for k in range(7):                     # the piece's last coefficients, for a KEEP piece later (FM's, or the control
    e('move    x:(r6+%d),x0' % (P_C1 + k))   # step's: a KEEP comes only after an FM piece, which writes them)
    e('move    x0,x:(r7+%d)' % (S_KC1 + k))
lab('oh09p')
lab('oh08d')
e('move    ssh,x0')                    # the seam's return: to the stock code after the source instead
e('move    x0,a')
e('move    #>$426,x0')                 # payload A: returns to P:0x39e, continues at P:0x426
e('cmp     #>$39e,a')
e('beq     oh11r')
e('move    #>$221,x0')                 # payload B: P:0x1a4 -> P:0x221
lab('oh11r')
e('move    x0,ssh')
e('nop')                               # (stock never returns right after a write to ssh)
e('rts')
# ================================================================== the chain, one piece
lab('oh10c')
e('move    x:(r6+%d),x0' % P_AMP0)
e('move    x0,x:(r7+%d)' % S_AMP)
e('move    x:(r6),b')
e('tst     b')
e('beq     oh12x')                     # n = 0 never comes (a do of 0 would run 65,536 times)
e('do      b,oh12x')
# ---- FM (v9.1): flp += (ovca - flp) >> 2; s = clamp(sctrl + fm(flp, fmq, 8, 12), 0, S_MAX - 1); i = s >> 6;
#      b = LB[i], c1 = fm(LB[i], C1R, 0, 12), k = max(0, fm(fm(LK[i], kmul, 0, 15), KF[i], 0, 12) - fm(ud, KD[i], 0, 10)),
#      and the clip by j = i - CL_I0 on ACID (else clg = 0)
e('move    x:(r6+%d),b' % P_FMF)
e('tst     b')
e('beq     oh19f')
e('move    x:(r7+%d),a' % S_OVC)
e('move    x:(r7+%d),x0' % S_FLP)
e('sub     x0,a')
e('asr     #2,a,a')
e('add     x0,a')                      # a1 = flp (a0: the dropped bits; every use below takes a1 or floors)
e('move    a1,x:(r7+%d)' % S_FLP)
fm('a', 8, 'x:(r6+%d)' % P_FMQ, 12)
e('move    x:(r6+%d),x0' % P_SCT)
e('add     x0,a')
clamp_a('#>%d' % (T.S_MAX - 1), '#0')
e('asr     #6,a,a')
e('move    a1,x1')                     # x1 = i (kept to the clip)
e('move    x1,a')
e('asl     #2,a,a')
e('move    x:(r6+%d),x0' % P_FMT)
e('add     x0,a')
e('move    a,r1')                      # four words a ladder index
e('nop')
e('move    p:(r1)+,x0')                # LB
e('move    x0,x:(r6+%d)' % P_B)
e('move    x0,a')
fm('a', 0, '#>%d' % T.TB_C1R, 12)
e('move    a1,x:(r6+%d)' % P_C1)
e('move    p:(r1)+,a')                 # LK
fm('a', 0, 'x:(r6+%d)' % P_KM, 15)
fm('a', 0, 'p:(r1)+', 12)              # x KF
e('move    a1,y1')
e('move    p:(r1)+,b')                 # KD
fm('b', 0, 'x:(r6+%d)' % P_UD, 10)
e('move    b1,x0')
e('move    y1,a')
e('sub     x0,a')
e('move    #0,x0')
e('tst     a')
e('tlt     x0,a')
e('move    a1,x:(r6+%d)' % P_K)
e('move    x:(r6+%d),b' % P_ACI)        # the clip: ACID only, and j > 0
e('tst     b')
e('beq     oh20n')
e('move    x1,a')
e('move    #>%d,x0' % T.CL_I0)
e('sub     x0,a')
e('ble     oh20n')
e('move    a1,x0')
e('asl     a')
e('add     x0,a')                      # 3 j
e('move    x:(r6+%d),x0' % P_CLT)
e('add     x0,a')
e('move    a,r1')
e('nop')
e('move    p:(r1)+,x0')
e('move    x0,x:(r6+%d)' % P_CLG)
e('move    p:(r1)+,x0')
e('move    x0,x:(r6+%d)' % P_CLI)
e('move    p:(r1),a')
e('move    a1,x:(r6+%d)' % P_CLL)
e('neg     a')
e('move    a1,x:(r6+%d)' % P_CLN)
e('bra     oh19f')
lab('oh20n')
e('move    #0,x0')
e('move    x0,x:(r6+%d)' % P_CLG)
lab('oh19f')
# ---- the loop highpass: fbst += fm(y4 - fbst, FBHP, 4, 11); fb = clamp(y4 - fbst, +-2^23)
ld32('a', S_Y4)
e('move    x:(r7+%d),x0' % S_FB)
e('sub     x0,a')
fm('a', 4, '#>%d' % T.TB_FBHP, 11)
e('move    x:(r7+%d),x0' % S_FB)
e('add     x0,a')
e('move    a,x:(r7+%d)' % S_FB)
e('move    a1,x1')
ld32('a', S_Y4)
e('sub     x1,a')
e('move    a,x1')                      # limiting move: the clamp (+2^23 would land on 2^23 - 1; never reached)
e('move    x1,x:(r7+%d)' % S_FBV)
# ---- u: the record's two halves -> a (32-bit, exact)
e('move    x:(r0)+,a')
e('asl     #16,a,a')                   # the untrusted bits above the half leave the accumulator
e('move    x:(r0)+,b')
e('and     #>$ffff,b')
e('move    b1,x0')
e('add     x0,a')
# ---- kx = (fb >> 8) * k ; lin = u - kx
e('move    x1,b')
fm('b', 8, 'x:(r6+%d)' % P_K, 0)
e('sub     b,a')                       # b0 = 0 here
# ---- the ladder's clip on a
e('move    x:(r6+%d),b' % P_CLG)
e('tst     b')
e('bne     oh13g')
softclip_inline()
e('bra     oh14l')
lab('oh13g')
clamp_a('x:(r6+%d)' % P_CLL, 'x:(r6+%d)' % P_CLN)
fm('a', 4, 'x:(r6+%d)' % P_CLG, 8)
e('bsr     oh30s')
fm('a', 4, 'x:(r6+%d)' % P_CLI, 8)
e('move    a1,x1')
e('move    x1,a')
lab('oh14l')
e('move    a1,x:(r7+%d)' % S_Y0V)
# ---- the ladder, 32-bit states
def stage(coef, st):
    fm('a', 7, 'x:(r6+%d)' % coef, 8)
    e('move    #0,a0')
    ld32('b', st)
    e('add     b,a')
    st32a(st)
def stage2(coef, st):
    fm('a', 7, 'x:(r6+%d)' % coef, 8)
    e('move    #0,a0')
    e('add     b,a')
    st32a(st)
e('move    x:(r7+%d),a' % S_Y0V)
ld32('b', S_Y2)
e('add     b,a')
ld32('b', S_Y1)
e('sub     b,a')
stage2(P_C1, S_Y1)
for (st, nxt) in ((S_Y2, S_Y3), (S_Y3, S_Y4)):
    ld32('b', nxt)
    e('add     b,a')
    ld32('b', st)
    e('sub     b,a')
    e('sub     b,a')
    stage2(P_B, st)
ld32('b', S_Y4)
e('sub     b,a')
e('sub     b,a')
stage2(P_B, S_Y4)
# ---- the VCA's input pair: vp += fm(fb - vp, HP, 4, 11)
def hp(state, coef):
    e('move    x:(r7+%d),a' % S_FBV)
    e('move    x:(r7+%d),x1' % state)
    e('sub     x1,a')
    fm('a', 4, '#>%d' % coef, 11)
    e('move    a1,x0')
    e('move    x1,a')
    e('add     x0,a')
    e('move    a,x:(r7+%d)' % state)
hp(S_VP1, T.VP_HP1)
e('move    a1,x0')
e('move    x:(r7+%d),b' % S_FBV)
e('sub     x0,b')                      # b = fb - vp1
hp(S_VP2, T.VP_HP2)
e('move    a1,x0')
e('move    x:(r7+%d),a' % S_FBV)
e('sub     x0,a')                      # a = fb - vp2
fm('a', 6, 'x:(r6+%d)' % P_W2, 6)
e('add     b,a')                       # a = x (a0: a fraction < 1 over an integer: the next floor is the same)
# ---- level: o = fm(x, gcomp, 6, 6); clamp OTA_LIM; the OTA; clamp VCA_LIM
fm('a', 6, 'x:(r6+%d)' % P_GC, 6)
clamp_a('#>%d' % T.OTA_LIM, '#>%d' % neg24(T.OTA_LIM))
fm('a', 4, '#>%d' % T.OTA_IN, 8)
softclip_inline()
fm('a', 4, '#>%d' % T.OTA_OUT, 11)
clamp_a('#>%d' % T.VCA_LIM, '#>%d' % neg24(T.VCA_LIM))
e('move    a1,x1')                     # o, clean, into b
e('move    x1,b')
# ---- the VCA: amp = max(0, amp + step); o = fm(o, amp >> 1, 7, 6)
e('move    x:(r7+%d),a' % S_AMP)
e('move    x:(r6+%d),x0' % P_STEP)
e('add     x0,a')
e('move    #0,x0')
e('tst     a')
e('tlt     x0,a')
e('move    a1,x:(r7+%d)' % S_AMP)
e('asr     a')
e('move    a1,x0')
e('asr     #7,b,b')
e('move    b1,y0')
e('mpy     y0,x0,b')
e('asl     #17,b,b')
e('move    b,x0')                      # limiting: past 2^23 pin 6's table is flat anyway (|o| >= 1.9M)
e('move    x0,b')
e('move    x0,x:(r7+%d)' % S_OV)
# ---- pin 6: o -> sign(o) * F(64 |o| / L), linear between 257 points
e('move    x:(r6+%d),r1' % P_TB)       # P6_F, the negative side
e('move    #>%d,y1' % T.P6_K)
e('tst     b')
e('blt     oh15k')
e('move    #>%d,y1' % T.P6_KP)
e('move    x:(r6+%d),r1' % P_TBP)
lab('oh15k')
e('abs     b')                         # |o| < 2^23 <= P6_AMAX: the table's own clamp never acts here
e('asr     #6,b,b')
e('move    b1,x1')
e('mpy     y1,x1,b')                   # 2 * (|o| >> 6) * K
e('asl     #5,b,b')                    # b1 = i = floor(AK / 2^18), b0 = the rest << 5
e('move    b0,a')
e('lsr     #9,a')                      # a1 = (t & 0xFFFF) >> 1
e('move    a1,y0')
e('clr     a       b,n1')
e('move    #>256,x0')
e('cmp     x0,b')
e('bge     oh16f')
e('move    (r1)+n1')
e('move    p:(r1)+,x0')
e('move    p:(r1),a')
e('sub     x0,a')
e('move    a1,x1')
e('mpy     x1,y0,a')
e('asl     #8,a,a')
e('move    a1,x1')
e('move    x0,a')
e('add     x1,a')
e('bra     oh17s')
lab('oh16f')
e('move    #>256,n1')
e('lua     (r1)+n1,r1')
e('move    p:(r1),a')
lab('oh17s')
e('move    a1,y1')
e('neg     a')
e('move    x:(r7+%d),b' % S_OV)
e('tst     b')
e('tge     y1,a')                      # o >= 0: +v
# ---- MUFF (v9.1): mlo += fm(o - mlo, LP, 4, 11) (|o - mlo| < 2^21 here: its clamp at DF_MUFF_DLIM never acts);
#      h = o - mlo; SOFT: fm(softclip(fm(clamp(h, +-2^20), 3413, 2, 8)), 9830, 4, 11); HARD: clamp(h, +-T); o = mlo + h
assert T.DF_MUFF_DLIM > 1 << 22
e('move    x:(r6+%d),b' % P_ANY)        # neither MUFF nor DIST: past both
e('tst     b')
e('beq     oh24d')
e('move    x:(r6+%d),b' % P_MUF)
e('tst     b')
e('beq     oh21m')
e('move    a1,x1')
e('move    x:(r7+%d),x0' % S_MLO)
e('sub     x0,a')
fm('a', 4, '#>%d' % T.DF_MUFF_LP, 11)
e('move    x:(r7+%d),x0' % S_MLO)       # (fm took x0)
e('add     x0,a')
e('move    a1,x:(r7+%d)' % S_MLO)
e('move    a1,x0')
e('move    x1,a')
e('sub     x0,a')                      # h
e('move    #>1,x0')
e('cmp     x0,b')
e('bne     oh22h')
clamp_a('#>1048576', '#>%d' % neg24(1048576))
fm('a', 2, '#>3413', 8)
e('bsr     oh30s')
fm('a', 4, '#>9830', 11)
e('bra     oh23e')
lab('oh22h')
clamp_a('#>%d' % T.DF_MUFF_T, '#>%d' % neg24(T.DF_MUFF_T))
lab('oh23e')
e('move    a1,x0')
e('move    x:(r7+%d),a' % S_MLO)
e('add     x0,a')
lab('oh21m')
e('move    a1,x:(r7+%d)' % S_OVC)       # FM reads the VCA after the Muffler
# ---- DIST: o = softclip(o * GAIN + BIAS); tone += fm(o - tone, TONE, 7, 8); o = tone
assert T.DIST_GAIN == 5
e('move    x:(r6+%d),b' % P_DIS)
e('tst     b')
e('beq     oh24d')
e('move    a1,x0')
e('asl     #2,a,a')
e('add     x0,a')
e('add     #>%d,a' % T.DIST_BIAS)
e('bsr     oh30s')
e('move    x:(r7+%d),x0' % S_TONE)
e('sub     x0,a')
fm('a', 7, '#>%d' % T.DIST_TONE, 8)
e('move    x:(r7+%d),x0' % S_TONE)
e('add     x0,a')
e('move    a1,x:(r7+%d)' % S_TONE)
e('move    a1,x1')
e('move    x1,a')
e('bra     oh33o')
lab('oh24d')
e('move    a1,x:(r7+%d)' % S_OVC)       # (neither: the VCA's word as it is)
lab('oh33o')
# ---- output coupling: dc += fm(o - dc, DCHP, 4, 11); v = clamp((o - dc) >> SHIFT_OUT, +-32767)
e('move    a1,x1')
e('move    x:(r7+%d),x0' % S_DC)
e('sub     x0,a')
fm('a', 4, '#>%d' % T.TB_DCHP, 11)
e('move    x:(r7+%d),x0' % S_DC)
e('add     x0,a')
e('move    a,x:(r7+%d)' % S_DC)
e('move    a1,x0')
e('move    x1,a')
e('sub     x0,a')                      # y = o - dc
# ---- DRIV (v9.1): y = clamp(y, +-YLIM); x = fm(y, osin, 6, 6) (to 2^24: a2 holds it); a = |x|; past the side's K:
#      d = min(a - K, 4 (L - K)), t = d R (Q22: i = t >> 22, fraction 15 bits), v = TH[i] (+ linear), a = K + fm(v, L - K, 0, 14)
e('move    x:(r6+%d),b' % P_DRV)
e('tst     b')
e('beq     oh25v')
clamp_a('#>%d' % T.DRV_YLIM, '#>%d' % neg24(T.DRV_YLIM))
fm('a', 6, 'x:(r6+%d)' % P_OSIN, 6)
e('move    #0,a0')                     # the integer x, exact in a2:a1
e('move    x:(r6+%d),r1' % P_DRC)      # the + side's constants
e('move    a,b')                       # (limited: only its sign is kept)
e('move    b,x:(r7+%d)' % S_T1)
e('tst     b')
e('bge     oh26p')
e('move    #>4,n1')
e('nop')
e('move    (r1)+n1')                   # the - side's
lab('oh26p')
e('abs     a')
e('move    p:(r1)+,x0')                # K
e('move    x0,x:(r7+%d)' % S_T2)
e('cmp     x0,a')
e('ble     oh27k')                     # |x| <= K: x as it is
e('sub     x0,a')
e('move    p:(r1)+,y1')                # 4 (L - K)
e('cmp     y1,a')
e('tge     y1,a')
e('move    a1,x1')
e('move    p:(r1)+,y1')                # R
e('mpy     y1,x1,b')                   # 2 d R
e('asl     #1,b,b')                    # b1 = i = floor(d R / 2^22), b0 = the rest << 2
e('move    b0,a')
e('lsr     #9,a')                      # a1 = ((d R) >> 7) & 0x7fff
e('move    a1,y0')
e('move    p:(r1)+,x0')                # L - K
e('move    x0,x:(r7+%d)' % S_OV)        # (S_OV is free after pin 6)
e('move    x:(r6+%d),r1' % P_DRT)
e('move    #>256,x0')
e('cmp     x0,b')
e('bge     oh28f')
e('clr     a       b,n1')
e('lua     (r1)+n1,r1')
e('move    p:(r1)+,x0')
e('move    p:(r1),a')
e('sub     x0,a')
e('move    a1,x1')
e('mpy     x1,y0,a')
e('asl     #8,a,a')
e('move    a1,x1')
e('move    x0,a')
e('add     x1,a')
e('bra     oh29s')
lab('oh28f')
e('move    #>256,n1')
e('lua     (r1)+n1,r1')
e('move    p:(r1),a')
lab('oh29s')
fm('a', 0, 'x:(r7+%d)' % S_OV, 14)
e('move    a1,x0')
e('move    x:(r7+%d),a' % S_T2)
e('add     x0,a')
lab('oh27k')
e('move    a1,y1')                     # (|x| <= K < 2^23, or K + ...: a1 is all of it)
e('neg     a')
e('move    x:(r7+%d),b' % S_T1)
e('tst     b')
e('tge     y1,a')                      # x >= 0: +a
lab('oh25v')
e('asr     #%d,a,a' % T.SHIFT_OUT)
e('move    a1,x1')                     # the floor, a0 cleared (the shift below would carry a0 into the word)
e('move    x1,a')
clamp_a('#>32767', '#>%d' % neg24(32767))
e('asl     #8,a,a')
e('move    a,x:(r3)+')                 # L and R: v << 8
e('move    a,x:(r3)+')
lab('oh12x')
e('rts')
# ================================================================== softclip: a -> a
# clamp(s, +-1482910); s - ((((s >> 8)^2 >> 12) * (s >> 8) >> 12) * 10923 >> 8)
lab('oh30s')
clamp_a('#>1482910', '#>%d' % neg24(1482910))
e('move    a1,x1')
e('move    x1,a')
e('asr     #8,a,a')
e('move    a1,x0')
e('mpy     x0,x0,a')
e('asl     #11,a,a')
e('move    a1,y0')
e('mpy     y0,x0,a')
e('asl     #11,a,a')
e('move    a1,y0')
e('move    #>10923,x0')
e('mpy     y0,x0,a')
e('asl     #15,a,a')
e('move    a1,x0')
e('move    x1,a')
e('sub     x0,a')
e('rts')

import re
# the control block through r7 (stock has the (r7+N) forms, not (r6+N)): x:(r6+n) -> x:(r7+CB+n)
L = [re.sub(r'x:\(r6\+(\d+)\)', lambda m: 'x:(r7+%d)' % (CB + int(m.group(1))), l) for l in L]
L = [l.replace('x:(r6),', 'x:(r7+%d),' % CB) for l in L]
assert not any(re.search(r'x:\(r6\+', l) for l in L) and CB + NCTL <= 63

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'o3h.asm'
    open(out, 'w').write('\n'.join(L) + '\n')
    if len(sys.argv) > 2:
        open(sys.argv[2], 'w').write(' '.join('%06x' % (w & 0xFFFFFF) for w in ptable) + '\n')
