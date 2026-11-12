| FRAME GUARD -- a frame interrupt that enters late waits out the window in
| which the DSP's frame exchange stalls.
|
| The frame interrupt (vector 0x41, handler 0x4000aad0) is raised by the DSP
| once a frame (362.8 us) and starts the transfer chain that sends the DSP
| its next frame. A long frame interrupt (475-585 us at START and at a
| program change, every image measured) makes the next one enter late.
| Measured on Sam's MKII, 12 Nov 2026, 33 logged first STARTs (octabam,
| USB capture open and closed): entered up to 149 us late, one back-to-back
| frame interrupt follows and the unit runs on (8); entered 155 us or more
| late, the DSP skips one frame and the unit runs on (23); the two that
| stalled entered 149 and 155 us late, were followed by two back-to-back
| frame interrupts, the second before its grid time, and then by none (the
| sequencer holds step 1 until a power-cycle). With the guard: 32 first
| STARTs and 192 program changes without a stall (20-channel USB capture),
| every guarded entry followed by the one skipped frame. README.md has the
| table and what the guard does not cover.
|
| fg_late is this entry's lateness against the DSP's frame grid: the
| previous lateness plus the interval between entries less a frame (TGRID,
| 0.5 us over the nominal so an error decays), floored at 0 and taken modulo
| a frame. An entry between LLO and LHI late waits until it is LHI late.
| Interrupts are masked at level 5 here, as in the rest of the handler.
| SPDX-License-Identifier: MIT

        .equ    DTCN3,  0xfc07c00c              | DMA timer 3's count, 132 MHz
        .equ    BODY,   0x4000aad8              | the handler after its displaced prologue
        .equ    TGRID,  47960                   | a frame + 0.5 us
        .equ    LLO,    14520                   | 110 us
        .equ    LHI,    25080                   | 190 us
        .include "remix.inc"                    | HK_FRAME_ENTRY (modules/hooks)

        .text
        .globl  fg_in
fg_in:
        .if     HK_FRAME_ENTRY == 0             | bridged by HOOKS: it replays the prologue
        lea     %sp@(-252),%sp                  | displaced: lea %sp@(-252),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@            | displaced: moveml %d0-%fp,%sp@
        .endif
        move.l  DTCN3,%d0                       | every register is saved
        move.l  %d0,%d1
        sub.l   fg_prev,%d1                     | the interval between entries
        move.l  %d0,fg_prev
        cmp.l   #4*TGRID,%d1
        bcc.s   2f                              | the first frame, or a gap: on time
        add.l   fg_late,%d1
        sub.l   #TGRID,%d1
        bpl.s   3f
2:      moveq   #0,%d1
3:      cmp.l   #TGRID,%d1
        bcs.s   4f
        sub.l   #TGRID,%d1
        bra.s   3b
4:      move.l  %d1,fg_late
        cmp.l   #LLO,%d1
        bls.s   6f
        cmp.l   #LHI,%d1
        bcc.s   6f
        move.l  #LHI,%d2
        sub.l   %d1,%d2                         | counts to wait
5:      move.l  DTCN3,%d3
        sub.l   %d0,%d3
        cmp.l   %d2,%d3
        bcs.s   5b
        addq.l  #1,fg_waits
        .if     HK_FRAME_ENTRY
6:      rts                                     | HOOKS goes on to the next participant
        .else
6:      jmp     BODY
        .endif

        .data
        .balign 4
        .globl  fg_waits
fg_prev: .long  0                               | the previous entry's stamp
fg_late: .long  0                               | its lateness, timer counts
fg_waits: .long 0                               | entries that waited
