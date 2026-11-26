| LOAD METER -- the frame interrupt's share of the ColdFire, for BRAIN's
| LOAD view.
|
| The frame interrupt (vector 0x41, handler 0x4000aad0, ~2,756 a second at
| 362.8 us) is stamped at its entry and at its epilogue on DTCN3, DMA timer
| 3's free-running count (132 MHz bus clock; CF METER and the OS read it
| too). Each exit adds the interrupt's duration to a sum and keeps the
| longest; every WIN counts (0.5 s) the window is published to lm_stats and
| a new one starts. BRAIN's LOAD view reads it as LM_STATS (its defsym)
| and shows the share and the longest interrupt.
|
| Interrupts are masked at level 5 inside the handler, so the stamps and
| the sums are not shared with anything that can preempt them.

        .equ    DTCN3,  0xfc07c00c
        .equ    WIN,    66000000                | 0.5 s at 132 MHz
        .equ    BODY,   0x4000aad8              | the handler after its displaced prologue
        .include "remix.inc"                    | HK_FRAME_ENTRY, HK_FRAME_TAIL (modules/hooks)

        .text
| ---- 0x4000aad0: the handler's first instructions, then the entry stamp --
        .globl  lm_in
lm_in:
        .if     HK_FRAME_ENTRY == 0             | bridged by HOOKS: it replays the prologue
        lea     %sp@(-252),%sp                  | displaced: lea %sp@(-252),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@            | displaced: moveml %d0-%fp,%sp@
        .endif
        move.l  DTCN3,%d0                       | every register is saved: d0 is free
        move.l  %d0,lm_t0
        .weak   dl_pump                         | DLPUMP, when the remix carries it
        move.l  #dl_pump,%d0
        move.l  %d0,%a0                         | (movea keeps the flags) here, two before the call:
        beq.s   1f                              | no address-use stall
        jsr     %a0@
        .if     HK_FRAME_ENTRY
1:      rts                                     | HOOKS goes on to the body
        .else
1:      jmp     BODY
        .endif

| ---- 0x4000d9a6: the epilogue, every exit path --------------------------
| d0-a6 are saved at (sp) and restored below, so every register is free.
        .globl  lm_out
lm_out:
        move.l  DTCN3,%d2                       | now
        move.l  %d2,%d0
        sub.l   lm_t0,%d0                       | this interrupt's duration
        add.l   %d0,lm_sum
        addq.l  #1,lm_cnt
        addq.l  #1,lm_irqs                      | every frame interrupt, for verify_load_meter
        cmp.l   lm_max,%d0
        bls.s   1f
        move.l  %d0,lm_max
1:      move.l  %d2,%d1
        sub.l   lm_w0,%d1                       | the window so far
        cmp.l   #WIN,%d1
        bcs.s   2f
        lea     lm_stats,%a0                    | publish: seq, window, sum, count, longest
        move.l  %d1,%a0@(4)
        move.l  lm_sum,%d0                      | ColdFire: no absolute-to-displaced move
        move.l  %d0,%a0@(8)
        move.l  lm_cnt,%d0
        move.l  %d0,%a0@(12)
        move.l  lm_max,%d0
        move.l  %d0,%a0@(16)
        addq.l  #1,%a0@                         | the seq last: a reader sees a whole window
        move.l  %d2,lm_w0
        clr.l   lm_sum
        clr.l   lm_cnt
        clr.l   lm_max
        .if     HK_FRAME_TAIL
2:      rts                                     | HOOKS replays the epilogue
        .else
2:      movem.l %sp@,%d0-%d7/%a0-%a6            | displaced
        lea     %sp@(252),%sp                   | displaced
        rte                                     | displaced
        .endif

| ---- 0x4000d310: the DSP meter's bytes, before the recorder reads MAIN ---
| Core 0 (dsp_meter.asm) puts 17 bytes in the low byte of MAIN's first 17
| longs at 0x80005e60 (channel 6's buffer, docs/firmware/STEM_REC.md section
| 18.6); stock has zero there. They are copied out and zeroed here, before
| the stock recorder (0x400068e4, called at 0x4000d340), USB's audio
| producer and STEMS read the buffer, so every reader sees stock's bytes. A record whose
| magic, sum, period (PMIN..PMAX timer-0 counts) or busy (at most its
| period) is wrong counts as bad and changes nothing else. The displaced
| `tstl 0x800018fe` is replayed last: the `bne` after it reads its flags.
| lm_dsp: seq (good records), bad, then per core {busy, period} now and at
| the peak since lm_dsp_reset was last set (a busy/period ratio, compared by
| cross-multiplying: both below 2^16), then two reserved bytes (zero).
        .equ    MAIN_LO, 0x80005e63             | long 0's lowest byte
        .equ    PMIN,   20000                   | timer 0 (CLK/2) counts a frame: 36,256 nominal
        .equ    PMAX,   60000
        .globl  lm_scrub
lm_scrub:
        lea     %sp@(-24),%sp
        movem.l %d0-%d3/%a0-%a1,%sp@
        addq.l  #1,lm_scrubs                    | every pass, for verify_load_meter
        lea     MAIN_LO,%a0
        lea     lm_raw,%a1
        moveq   #15,%d1                         | bytes 0..15: the meter record, summed
        moveq   #0,%d2                          | the sum of bytes 0..15
1:      mvz.b   %a0@,%d0
        clr.b   %a0@
        addq.l  #4,%a0
        move.b  %d0,%a1@+
        add.l   %d0,%d2
        subq.l  #1,%d1
        bpl.s   1b
        moveq   #6,%d1                          | bytes 16..22: its sum byte, then OTOP's record
2:      move.b  %a0@,%a1@+
        clr.b   %a0@
        addq.l  #4,%a0
        subq.l  #1,%d1
        bpl.s   2b
        lea     lm_raw,%a1
        and.l   #0xff,%d2                       | here, between the lea and the load: no address-use stall
        mvz.b   %a1@,%d0
        cmp.l   #0xa5,%d0
        bne.w   9f
        mvz.b   %a1@(16),%d0
        cmp.l   %d2,%d0
        bne.w   9f
        tst.l   lm_dsp_reset                    | the view opened: the peaks start again
        beq.s   3f
        clr.l   lm_dsp_reset
        lea     lm_dsp+24,%a0
        clr.l   %a0@+
        clr.l   %a0@+
        clr.l   %a0@+
        clr.l   %a0@
        lea     lm_dsum,%a0                     | and the sums
        clr.l   %a0@+
        clr.l   %a0@+
        clr.l   %a0@
3:      lea     lm_raw+2,%a1                    | core 0, then core 1
        lea     lm_dsp+8,%a0
        bsr.w   lm_core
        bne.s   9f
        lea     lm_raw+8,%a1
        lea     lm_dsp+16,%a0
        bsr.w   lm_core
        bne.s   9f
        mvz.b   lm_raw+14,%d0
        move.l  %d0,lm_dsp+40                   | TUE frames, mod 256
        move.b  lm_raw+15,%d0
        move.l  %d0,lm_dsp+44                   | ROE frames, mod 256
        move.l  lm_dsp+8,%d0                    | the sums since the reset: busy per core,
        add.l   %d0,lm_dsum                     | and the records in them
        move.l  lm_dsp+16,%d0
        add.l   %d0,lm_dsum+4
        addq.l  #1,lm_dsum+8
        addq.l  #1,lm_dsp                       | seq: a good record
        bsr.w   lm_otop
        bra.s   8f
9:      addq.l  #1,lm_dsp+4                     | bad
8:      movem.l %sp@,%d0-%d3/%a0-%a1
        lea     %sp@(24),%sp
        tst.l   0x800018fe                      | displaced
        jmp     0x4000d316

| OTOP's record, bytes 17..22 of lm_raw: $b4, a slot (0..15), its cost (three
| bytes, timer-0 counts), the sum of those five. Good: lm_ot[slot] takes the
| cost as its last and adds it to its sum, count and maximum; lm_ot_reset
| (set by the view when it opens) clears them first.
lm_otop:
        lea     lm_raw+17,%a1
        moveq   #0,%d2                          | the sum, and the loop's index: set before the first load,
        moveq   #4,%d1                          | they keep the lea and the index from their loads
        mvz.b   %a1@,%d0
        cmp.l   #0xb4,%d0
        bne.s   2f
1:      mvz.b   %a1@(0,%d1:l),%d0
        add.l   %d0,%d2
        subq.l  #1,%d1
        bpl.s   1b
        and.l   #0xff,%d2
        mvz.b   %a1@(5),%d0
        cmp.l   %d2,%d0
        bne.s   2f
        tst.l   lm_ot_reset
        beq.s   3f
        clr.l   lm_ot_reset
        lea     lm_ot,%a0
        moveq   #15,%d1
4:      clr.l   %a0@+
        clr.l   %a0@+
        clr.l   %a0@+
        clr.l   %a0@+
        subq.l  #1,%d1
        bpl.s   4b
3:      mvz.b   %a1@(1),%d1
        cmp.l   #15,%d1
        bhi.s   2f
        asl.l   #4,%d1                          | lm_ot[slot], before the call (lm_u24 keeps a0 and d1)
        lea     lm_ot,%a0
        add.l   %d1,%a0
        lea     %a1@(2),%a1
        bsr.w   lm_u24
        move.l  %d0,%a0@                        | last
        add.l   %d0,%a0@(4)                     | sum
        addq.l  #1,%a0@(8)                      | count
        cmp.l   %a0@(12),%d0
        bls.s   2f
        move.l  %d0,%a0@(12)                    | maximum
2:      rts

| a1 = a core's six bytes (busy, period, high first), a0 = its {busy, period}
| now, then (+16) its peak; Z clear when the record is implausible
lm_core:
        bsr.s   lm_u24
        move.l  %d0,%d2                         | busy
        bsr.s   lm_u24
        move.l  %d0,%d3                         | period
        cmp.l   #PMIN,%d3
        bcs.s   1f
        cmp.l   #PMAX,%d3
        bhi.s   1f
        cmp.l   %d3,%d2
        bhi.s   1f
        move.l  %d2,%a0@                        | now
        move.l  %d3,%a0@(4)
        move.l  %a0@(20),%d1                    | no peak yet: this one
        beq.s   3f
        move.l  %a0@(16),%d0                    | busy * peak period > peak busy * period?
        mulu.l  %d3,%d0
        mulu.l  %d2,%d1
        cmp.l   %d0,%d1
        bls.s   2f
3:      move.l  %d2,%a0@(16)
        move.l  %d3,%a0@(20)
2:      moveq   #0,%d0                          | Z set: plausible
        rts
1:      moveq   #1,%d0
        rts

| three bytes at a1 (high first) -> d0; a1 past them
lm_u24:
        mvz.b   %a1@+,%d0
        lsl.l   #8,%d0
        move.b  %a1@+,%d0
        lsl.l   #8,%d0
        move.b  %a1@+,%d0
        rts

        .data
        .balign 4
        .globl  lm_dsp, lm_dsp_reset, LM_DSP
| seq, bad, core 0 {busy, period}, core 1 {busy, period}, core 0 peak,
| core 1 peak, TUE, ROE -- timer-0 counts (CLK/2)
LM_DSP:
lm_dsp: .long   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
lm_dsp_reset: .long 0
        .globl  lm_scrubs, lm_irqs, lm_dsum
lm_scrubs: .long 0                              | lm_scrub's passes
lm_irqs: .long  0                               | frame interrupts (lm_out)
| core 0 busy, core 1 busy, records: summed since the reset. The port's
| timer moves in 1,024-count steps (the vendored emulator updates timers
| every 2,048 instructions), so one frame's busy cannot resolve a small
| change; the mean over many frames can (verify_load_meter calibrate)
lm_dsum: .long  0, 0, 0
lm_raw: .space  24
        .balign 4
        .globl  lm_ot, LM_OT, lm_ot_reset
| OTOP: per slot (0..7 core 0's FX1, FX2 of position 0, 1, 2, 3; 8..15 core 1's)
| {last, sum, count, maximum} cost in timer-0 counts (CLK/2: a frame is
| 36,256), then the flag that clears them
LM_OT:
lm_ot:  .space  256
lm_ot_reset: .long 0
        .balign 4
        .globl  lm_stats, LM_STATS              | LM_STATS: the name BRAIN's defsym takes (brain_lm)
LM_STATS:
lm_stats: .long 0, 0, 0, 0, 0                   | seq, window counts, sum counts, interrupts, longest counts
lm_t0:  .long   0
lm_w0:  .long   0
lm_sum: .long   0
lm_cnt: .long   0
lm_max: .long   0
