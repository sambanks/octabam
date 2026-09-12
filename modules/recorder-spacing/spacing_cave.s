| Recorder spacing -- ColdFire code cave (12 Sep 2026, RTOS_FORK 10.56)
|
| Hooked from 0x40006e0c in the per-frame recorder function (0x400068e4),
| at the tail of the fixed-RLEN length converter: the three displaced
| instructions turn the EMAC product into the length and are replayed
| first.  The converter's length is CONSTANT for a whole loop while the
| sequencer arms at floor(k x period) -- an alternating spacing -- so on
| the passes where they disagree the buffer's wrap splices two input
| moments two samples apart instead of one.  That is the -26 dB scuff on
| alternate bars measured on OCTABAM82 (RTOS_FORK 10.53), and it vanishes
| when the recording is exactly as long as the gap to the next arm.
|
| recorder-seam asked the LANE for the next event and was falsified: on a
| one-trig-per-bar lane the event resolves to the past, L' came out 0 and
| its guard refused all 1,200 calls (10.55).  This cave never asks.  The
| sequencer arms at floor(k x N/D) with N = RLEN x 15,876,000 and
| D = tempo24, so with q, r = divmod(N, D) every spacing is q plus a
| Bresenham overflow, and the residue is recoverable from the CURRENT arm
| alone because arm_k = k x q + floor(k x r/D) with floor(k x r/D) < q,
| which makes k = arm/q exact (past 165,000 passes at RLEN 16 / 128).
| RLEN comes back out of the stock length -- RLEN = round(L x D / K) --
| which is what lets this be state-free: no scratch word, no residue kept
| across passes, no ledger claim but the hook itself.
|
|     RLEN = (L x D + K/2) / K                 K = 15,876,000
|     N    = RLEN x K                          <= 1,016,064,000, fits in 32
|     q    = N / D  ;  r = N - q x D           (V4e has no remu.l)
|     r == 0  ->  L' = q                       clean tempo: q == L, a no-op
|     k    = arm / q                           arm = 0x46c7fa84[track]
|     L'   = q + floor((k+1)r/D) - floor(k x r/D)
|
| The last line replaces the model's explicit residue: the overflow test
| acc + r >= D is exactly floor((k+1)r/D) > floor(k x r/D), so two divides
| do it and no remainder is ever formed.  Validated against the
| sequencer's own grid on 115,200 (tempo, RLEN, pass) triples, and over
| all 11,208 (tempo, RLEN) pairs in 60.0..200.0 the result stays within
| one sample of the stock length -- so the +/-1 guard is kept, and at
| every tempo whose period is an integer q equals the stock length and
| this cave writes back the value that was already there.
|
| Reads:  0x80001814 (tempo24), 0x46c7fa84[track] (the arm sample the
|         firmware stores at the state-1 commit), 164(%sp) (the track).
| Writes: nothing but d4, the length.
| Position-independent: no reference to itself.
|
| Every divide is guarded: D == 0, RLEN == 0 and q == 0 all fall through
| to the stock length rather than trapping in a boot-critical path.  The
| divides also set Z from the QUOTIENT (Musashi's divl handler, and the
| CFPRM), which is what each `beq` after one tests.
|
| ⚠️ DO NOT "FIX" THE DISASSEMBLY.  objdump prints every `divu.l %dN,%dM`
| here as `remul %dN,%dM,%dM` -- 0x4c4x is one encoding family and GNU
| names it after the remainder form.  On ColdFire the extension word's
| bits 12-14 are the dividend/quotient register Dq and bits 0-2 the
| remainder register Dr, and the QUOTIENT is written only when Dr == Dq
| (`vendor/mc68k/Musashi/m68kops.c` m68k_op_divl_32_d, and the CFPRM's
| DIVU.L <ea>,Dx, whose extension is exactly that).  `divu.l %d1,%d0`
| assembles to 4c41 0000 -- Dq = Dr = d0 -- so d0 gets the quotient, which
| is what this cave wants.  The distinct-register spelling
| `remu.l %d1,%d3:%d0` is a remainder-ONLY instruction and leaves the
| quotient unwritten, so there is no way to get both from one divide here:
| that is why r is formed as N - q x D.

        .text
cave:
        move.l  %d0,%d4                 | displaced: product
        addq.l  #1,%d4                  | displaced
        asr.l   #1,%d4                  | displaced: L = (product + 1) >> 1
        lea     -24(%sp),%sp
        movem.l %d0-%d3/%a0-%a1,(%sp)   | 24 bytes; the caller's frame is now +28

        move.l  0x80001814,%d1          | d1 = D = tempo24
        beq     keep                    | no tempo: keep RLEN

        move.l  %d4,%d0
        mulu.l  %d1,%d0                 | L x D
        add.l   #7938000,%d0            | + K/2   (round to nearest)
        move.l  #15876000,%d2           | d2 = K
        divu.l  %d2,%d0                 | d0 = RLEN
        beq     keep                    | no length yet: keep RLEN
        mulu.l  %d2,%d0                 | d0 = N = RLEN x K
        move.l  %d0,%d3                 | d3 = N
        divu.l  %d1,%d0                 | d0 = q = N / D
        beq     keep                    | degenerate: keep RLEN
        move.l  %d0,%d2                 | d2 = q  (the answer accumulates here)
        mulu.l  %d1,%d0                 | d0 = q x D
        sub.l   %d0,%d3                 | d3 = r = N - q x D
        beq     guard                   | r == 0: integer period, L' = q

        move.l  164(%sp),%d0            | track: caller's sp(136) + 4 (return) + 24 (saved)
        lsl.l   #2,%d0
        lea     0x46c7fa84,%a0
        move.l  (%a0,%d0.l),%d0         | d0 = arm_k, this pass's arm sample
        divu.l  %d2,%d0                 | d0 = k = arm / q
        mulu.l  %d3,%d0                 | d0 = k x r        (< q x D + D, fits)
        move.l  %d0,%a1                 | a1 = k x r
        add.l   %d3,%d0                 | d0 = (k+1) x r
        move.l  %a1,%d3                 | d3 = k x r        (r is finished with)
        divu.l  %d1,%d0                 | d0 = floor((k+1)r / D)
        divu.l  %d1,%d3                 | d3 = floor(k x r / D)
        sub.l   %d3,%d0                 | d0 = the Bresenham overflow, 0 or 1
        add.l   %d0,%d2                 | d2 = L' = q + overflow

guard:
        move.l  %d2,%d0
        sub.l   %d4,%d0
        addq.l  #1,%d0                  | 0..2 <=> within one sample
        cmpi.l  #2,%d0
        bhi     keep
        move.l  %d2,%d4                 | substitute
keep:
        movem.l (%sp),%d0-%d3/%a0-%a1
        lea     24(%sp),%sp
        rts
