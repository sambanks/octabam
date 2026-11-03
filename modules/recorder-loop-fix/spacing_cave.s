| RECORDER LOOP FIX spacing -- hooked at 0x40006e0c, the length converter's last three
| instructions (replayed). Makes a fixed-RLEN recording exactly as long as
| the gap to the next arm, from the current arm alone:
|     q, r = divmod(RLEN x 15,876,000, tempo24)      RLEN recovered from L
|     k    = arm / q                                  arm = 0x46c7fa84[track]
|     L'   = q + floor((k+1)r/D) - floor(k r/D)
| Reads 0x80001814 (tempo24), 0x46c7fa84[track], 172(%sp) (the track).
| Writes nothing but d4, the length; every other path keeps RLEN's L. The
| +/-1 guard refuses an L' further than one sample from L.
| Memoised (2 Nov 2026): the result is a pure function of (L, tempo24,
| arm[track]), which change once a bar, while the cave runs about 1.4 times a
| recording track a frame (six divides each; a PC sampler on Bryan T's MKII
| put it near 1 us a call). rlf_memo[track] keeps {L, D, arm, L'}; when all
| three inputs match, L' comes from the memo, else it is computed exactly as
| before and stored. Tracks past 7 always compute. The memo is in .text and
| addressed pc-relative, so the cave stays position-independent; it starts
| zero, and D = 0 never reaches it, so it cannot match before a first store.
| The arm is read again for the store. Both reads are inside the level-5
| frame interrupt, so only a level-6 or level-7 handler could write the table
| between them, and stock's level-6 eDMA handler (0x40004840..0x40004bd0)
| does not name it: they see the same value.
| tools/verify/verify_recorder_loop_fix.py runs this cave and the ratified
| one (the manifest's SPACING_CAVE_BYTES_V1) call for call and refuses any
| difference.
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
        lea     -32(%sp),%sp
        movem.l %d0-%d3/%d5/%a0-%a2,(%sp) | 32 bytes; the caller's frame is now +36

        move.l  0x80001814,%d1          | d1 = D = tempo24
        beq     keep                    | no tempo: keep RLEN

        move.l  %d4,%d5                 | d5 = L, the memo's key
        suba.l  %a2,%a2                 | a2 = the memo entry, or 0
        move.l  172(%sp),%d0            | track: caller's sp(136) + 4 (return) + 32 (saved)
        moveq   #8,%d2
        cmp.l   %d2,%d0
        bcc.s   compute                 | unsigned: tracks 0..7 only
        lsl.l   #4,%d0                  | 16 bytes an entry
        lea     rlf_memo(%pc),%a2
        adda.l  %d0,%a2
        lsr.l   #2,%d0                  | track x 4
        lea     0x46c7fa84,%a0
        move.l  (%a0,%d0.l),%d2         | the arm sample
        cmp.l   (%a2),%d5
        bne.s   compute
        cmp.l   4(%a2),%d1
        bne.s   compute
        cmp.l   8(%a2),%d2
        bne.s   compute
        move.l  12(%a2),%d4             | the memo's answer
        bra     keep

compute:
        move.l  %d4,%d0
        mulu.l  %d1,%d0                 | L x D
        add.l   #7938000,%d0            | + K/2   (round to nearest)
        move.l  #15876000,%d2           | d2 = K
        divu.l  %d2,%d0                 | d0 = RLEN
        beq     store                   | no length yet: keep RLEN
        mulu.l  %d2,%d0                 | d0 = N = RLEN x K
        move.l  %d0,%d3                 | d3 = N
        divu.l  %d1,%d0                 | d0 = q = N / D
        beq     store                   | degenerate: keep RLEN
        move.l  %d0,%d2                 | d2 = q  (the answer accumulates here)
        mulu.l  %d1,%d0                 | d0 = q x D
        sub.l   %d0,%d3                 | d3 = r = N - q x D
        beq     guard                   | r == 0: integer period, L' = q

        move.l  172(%sp),%d0            | track
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
        bhi     store
        move.l  %d2,%d4                 | substitute
store:
        move.l  %a2,%d0
        beq.s   keep
        move.l  %d5,(%a2)               | {L, D, arm, L'}
        move.l  %d1,4(%a2)
        move.l  172(%sp),%d0
        lsl.l   #2,%d0
        lea     0x46c7fa84,%a0
        move.l  (%a0,%d0.l),%d0
        move.l  %d0,8(%a2)
        move.l  %d4,12(%a2)
keep:
        movem.l (%sp),%d0-%d3/%d5/%a0-%a2
        lea     32(%sp),%sp
        rts

        .balign 4
rlf_memo:
        .space  8*16
