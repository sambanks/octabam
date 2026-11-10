| DRUMMER phase 2 probe (never shipped): can a module, right after the sequencer's step builder,
| add a trig to an empty step, move a trig in time, and choose the slice the FLEX voice starts?
|
| dp_step   detour at 0x400a2d82, the instruction after `jsr 0x4009d1e8` (the step builder) in the
|           sequencer tick; d5 = the track, 0x800064d0[t] = the step index just built (0-based).
|           Track 1 only, pattern of probe_steps.py DR_SPARSE (trigs on steps 0, 4, 8, 12):
|             step 2  (empty) -> a trig: 0x46c7a810 = 29, 0x46c7a14c = 1, 0x46c7a830 = 0,
|                                0x46c77bfa = the last value stock wrote; staged locks all 0xff
|                                but STRT (byte 1) = 14 -> slice 7
|             step 4  (+12)   -> micro-timing word 0x46c7a830 = 0
|             step 6  (empty) -> a trig as step 2, micro-timing 7938000 (stock's +12 at 120 BPM)
|             step 8, 12      -> the next T1 voice start is forced to slice 9 by dp_start
| dp_start  the FLEX entry of the voice-start table (0x400d6458, stock 0x4000f450(track, slot)):
|           when a force is pending for the track, the page record's STRT byte (0x80000510 +
|           ping*0x180 + 48t + 2) is set to 2*slice and SLIC (+0x19) to 1 for the stock start, then
|           restored.
| Counters (dp_hits) let the gate see each branch ran. All state in .data (TRAPS trap-dram-bss).

        .set    STEPCTR, 0x800064d0
        .set    KIND,    0x46c7a810
        .set    MTIME,   0x46c7a830
        .set    COUNT,   0x46c7a14c
        .set    LEN7BFA, 0x46c77bfa
        .set    STAGE,   0x46c7aa24
        .set    PING,    0x800000e0
        .set    PAGEREC, 0x80000510
        .set    STOCK_START, 0x4000f450
        .set    PENDING, 0x80001558

        .text
        .globl  dp_step
dp_step:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        tst.l   %d5
        bne.w   .Ldone
        lea     KIND,%a0
        move.l  (%a0),%d0
        moveq   #29,%d1
        cmp.l   %d1,%d0
        bne.s   .Lnolen
        move.l  LEN7BFA,%d0                     | remember stock's value on a real trig
        move.l  %d0,dp_len
.Lnolen:
        mvz.b   STEPCTR,%d0
        moveq   #2,%d1
        cmp.l   %d1,%d0
        bne.s   .Ln2
        clr.l   %d1
        bsr.w   dp_inject
        addq.l  #1,dp_hits
        bra.w   .Ldone
.Ln2:   moveq   #4,%d1
        cmp.l   %d1,%d0
        bne.s   .Ln4
        clr.l   MTIME
        addq.l  #1,dp_hits+4
        bra.w   .Ldone
.Ln4:   moveq   #6,%d1
        cmp.l   %d1,%d0
        bne.s   .Ln6
        move.l  #7938000,%d1
        bsr.w   dp_inject
        addq.l  #1,dp_hits+8
        bra.s   .Ldone
.Ln6:   moveq   #8,%d1
        cmp.l   %d1,%d0
        beq.s   .Lforce
        moveq   #12,%d1
        cmp.l   %d1,%d0
        bne.s   .Ldone
.Lforce:
        moveq   #9,%d1
        move.b  %d1,dp_force
        addq.l  #1,dp_hits+12
.Ldone:
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        mvz.b   0x8000668d,%d0                  | the displaced instruction
        jmp     0x400a2d88

| d1 = micro-timing word; track 1 (index 0)
dp_inject:
        move.l  %d1,MTIME
        moveq   #29,%d0
        move.l  %d0,KIND
        moveq   #1,%d0
        move.l  %d0,COUNT
        move.l  dp_len,%d0
        move.l  %d0,LEN7BFA
        lea     STAGE,%a0
        moveq   #-1,%d0
        moveq   #7,%d1
.Lfill: move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bpl.s   .Lfill
        moveq   #14,%d0
        move.b  %d0,STAGE+1                     | STRT lock 14 -> slice 7
        moveq   #40,%d0
        move.b  %d0,PENDING+15                  | VOL 40 in the pending lock block (0x80001558 + 32t)
        rts

        .globl  dp_start
dp_start:                                       | (track, slot) on the stack, as 0x4000f450
        lea     -12(%sp),%sp
        movem.l %d2/%a2-%a3,(%sp)
        move.l  16(%sp),%d0                     | track
        clr.l   %d2
        tst.l   %d0
        bne.s   .Lplain
        mvz.b   dp_force,%d1
        cmp.l   #0xff,%d1
        beq.s   .Lplain
        moveq   #-1,%d0
        move.b  %d0,dp_force
        move.l  PING,%d2
        move.l  #0x180,%d0
        mulu.l  %d0,%d2
        add.l   #PAGEREC,%d2
        move.l  %d2,%a2                         | track 1's page record
        mvz.b   2(%a2),%d0
        move.b  %d0,dp_saved
        mvz.b   0x19(%a2),%d0
        move.b  %d0,dp_saved+1
        add.l   %d1,%d1
        move.b  %d1,2(%a2)                      | STRT = 2 * slice
        moveq   #1,%d0
        move.b  %d0,0x19(%a2)                   | SLIC on
        moveq   #80,%d0                         | VOL 80 applied as stock applies a lock (0x4000c5ac):
        move.b  %d0,0x80000810+15               |   live lane T1 + 15
        lsl.l   #8,%d0
        move.w  %d0,0x80000a50+30               |   DSP halfword T1 + 2*15, value << 8
        move.l  0x80001538,%d0
        bset    #15,%d0                         |   restore bit: stock puts the Part's VOL back at the next trig
        move.l  %d0,0x80001538
        addq.l  #1,dp_hits+16
.Lplain:
        move.l  20(%sp),-(%sp)                  | slot
        move.l  20(%sp),-(%sp)                  | track (16 + 4)
        jsr     STOCK_START
        addq.l  #8,%sp
        tst.l   %d2
        beq.s   .Lout
        move.l  %d2,%a2
        move.b  dp_saved,%d0
        move.b  %d0,2(%a2)
        move.b  dp_saved+1,%d0
        move.b  %d0,0x19(%a2)
.Lout:  movem.l (%sp),%d2/%a2-%a3
        lea     12(%sp),%sp
        rts

        .data
        .balign 4
        .globl  dp_hits
dp_hits:  .long 0, 0, 0, 0, 0                   | inject 2, mtime 4, inject 6, force armed, force used
dp_len:   .long 15876000
dp_force: .byte 0xff
dp_saved: .byte 0, 0
        .balign 2
