| RECORDER LOOP FIX spacing -- hooked at 0x40006e0c, the length converter's last three
| instructions (replayed). Makes a fixed-RLEN recording exactly as long as
| the gap to the next arm, from the current arm alone:
|     q, r = divmod(RLEN x 15,876,000, tempo24)      RLEN recovered from L
|     k    = arm / q                                  arm = 0x46c7fa84[track]
|     L'   = q + floor((k+1)r/D) - floor(k r/D)
| Reads 0x80001814 (tempo24), 0x46c7fa84[track], 164(%sp) (the track).
| Writes nothing but d4, the length; every other path keeps RLEN's L. The
| +/-1 guard refuses an L' further than one sample from L.
| objdump prints every divu.l here as remul (0x4c4x is one encoding family);
| with the extension word's Dq and Dr equal, ColdFire writes the quotient.
| Assemble: m68k-elf-as -mcpu=5475 -o spacing.o spacing_cave.s

        .text
        .globl  rlf_spacing
rlf_spacing:
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
