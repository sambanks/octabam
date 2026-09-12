| STEM REC -- T1 to the card while the sequencer plays (proof of concept).
|
| Design: docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md.
| Every stock address below, with its evidence: docs/firmware/STEM_REC.md.
|
| Three parts share the state words below:
|   stems_action      MAIN MENU > CONTROL > STEM REC, in the UI task
|   stems_frame_hook  the per-frame tap, in the audio interrupt at IPL 5
|   stems_task        our own RTOS task: the ring to the card
| The state is one aligned long, so every read and write of it is one
| instruction. The action and the hook write it; the task writes only IDLE.

| ---- stock facts (docs/firmware/STEM_REC.md) ----------------------------
        .equ    TRANSPORT,     0x800065b8   | long; 1 = running, 0 or 2 = stopped (Task 2)
        .equ    TRANSPORT_RUNNING, 1        | the ONLY value that means playing   (Task 2)
        .equ    CARD_MOUNTED,  0x460d1cb8   | long; 0 = no card                   (Task 8)
        .equ    FRAME_ROUTINE, 0x400031a0   | the displaced call
        .equ    MODE_W,        0x400b328b   | "w": opens without truncating
        .equ    PING,          0x800000e0   | the read-back half selector  (Task 3)
        .equ    PING_XOR,      0            | half = (PING ^ PING_XOR) & 1  (Task 3)
        .equ    READBACK,      0x80003190   | core 1's read-back, tracks 1-4
        .equ    T1_OFFSET,     0x100        | T1's block in a half: the THIRD 0x80 slot (Task 11)

| ---- constants -----------------------------------------------------------
        .equ    ST_IDLE,       0
        .equ    ST_ARMED,      1
        .equ    ST_RECORDING,  2
        .equ    ST_FINISHING,  3
        .equ    RING_SIZE,     0x400000     | = DramRegion stems_ring
        .equ    FRAME_BYTES,   64           | 16 stereo 16-bit samples
        .equ    MAX_FRAMES,    41344        | 15.0 s
        .equ    ERR_OVERFLOW,  1

        .text

| ---- state -----------------------------------------------------------------
        .balign 4
        .global stems_state, stems_status, stems_task_made
stems_state:     .long   ST_IDLE
stems_status:    .long   0          | the last error, 0 = none
stems_task_made: .long   0
stems_wr:        .long   0          | bytes the hook has put in the ring
stems_rd:        .long   0          | bytes the task has taken out
stems_frames:    .long   0          | frames recorded

| ---- the menu row -------------------------------------------------------
        .global stems_label, stems_zero
        .equ    stems_zero, 0       | the row's window, pad, child and id
stems_label:
        .asciz  "STEM REC"
        .balign 2

| ---- the menu action: action(0), in the UI task ------------------------
| d0-d1/a0-a1 are scratch; everything else is preserved.
        .global stems_action
stems_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        tst.l   CARD_MOUNTED        | no card: do nothing at all
        beq.s   .La_out
        move.w  %sr,%d2
        move.w  #0x2700,%sr         | no frame hook between read and write
        move.l  stems_state,%d0
        tst.l   %d0
        bne.s   .La_busy
        clr.l   stems_wr            | IDLE: a fresh recording
        clr.l   stems_rd
        clr.l   stems_frames
        clr.l   stems_status
        moveq   #ST_ARMED,%d1
        move.l  TRANSPORT,%d0       | running iff exactly 1 (Task 2)
        subq.l  #TRANSPORT_RUNNING,%d0
        bne.s   .La_set             | 0 or 2: stopped
        moveq   #ST_RECORDING,%d1   | already playing: start at the next frame
        bra.s   .La_set
.La_busy:
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .La_notarmed
        moveq   #ST_IDLE,%d1        | ARMED: cancel
        bra.s   .La_set
.La_notarmed:
        moveq   #ST_RECORDING,%d1
        cmp.l   %d1,%d0
        bne.s   .La_unmask          | FINISHING: ignored
        moveq   #ST_FINISHING,%d1   | RECORDING: stop
.La_set:
        move.l  %d1,stems_state
.La_unmask:
        move.w  %d2,%sr
.La_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| ---- the frame hook: in the audio interrupt, IPL 5 ---------------------
| Reached by `jsr` from 0x40004b12. Calls nothing but the routine it
| displaced; uses no RTOS service; loops are bounded. In IDLE its whole
| cost is one test and one branch. The copy runs BEFORE the stock routine,
| which reads the same block (spec section 4).
        .global stems_frame_hook
stems_frame_hook:
        tst.l   stems_state
        beq.w   .Lh_stock           | IDLE
        lea     -32(%sp),%sp
        movem.l %d0-%d5/%a0-%a1,(%sp)
        move.l  stems_state,%d0
        moveq   #ST_FINISHING,%d1
        cmp.l   %d1,%d0
        beq.w   .Lh_out             | FINISHING: the task owns the ring now
        move.l  TRANSPORT,%d2       | running iff exactly 1 (Task 2)
        subq.l  #TRANSPORT_RUNNING,%d2   | Z set while the sequencer plays
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .Lh_rec
        tst.l   %d2                 | ARMED
        bne.w   .Lh_out             | still stopped (0 or 2)
        moveq   #ST_RECORDING,%d0   | the first playing frame is recorded
        move.l  %d0,stems_state
        bra.s   .Lh_copy
.Lh_rec:                            | RECORDING
        tst.l   %d2
        beq.s   .Lh_copy
        moveq   #ST_FINISHING,%d0   | the sequencer stopped: 0 (end, rewind) or 2 (STOP key)
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_copy:
        move.l  stems_wr,%d3
        move.l  %d3,%d0
        sub.l   stems_rd,%d0        | bytes in the ring
        cmpi.l  #RING_SIZE-FRAME_BYTES,%d0
        bls.s   .Lh_room
        moveq   #ERR_OVERFLOW,%d0   | would overwrite unwritten audio: stop
        move.l  %d0,stems_status
        moveq   #ST_FINISHING,%d0
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_room:
        move.l  PING,%d4            | the half holding this frame (Task 3)
        eori.l  #PING_XOR,%d4
        moveq   #1,%d5
        and.l   %d5,%d4
        moveq   #10,%d5
        lsl.l   %d5,%d4             | * 0x400
        movea.l %d4,%a0
        adda.l  #READBACK+T1_OFFSET,%a0
        move.l  %d3,%d0
        andi.l  #RING_SIZE-1,%d0
        movea.l %d0,%a1
        adda.l  #stems_ring,%a1
| Each sample is one long on the host port: its top 16 bits, then its low
| 8 bits shifted up. Keep the top halves of L and R as one long.
        .rept   16
        move.l  (%a0)+,%d0          | L
        move.l  (%a0)+,%d1          | R
        swap    %d1
        move.w  %d1,%d0             | L top 16 : R top 16
        move.l  %d0,(%a1)+
        .endr
        moveq   #FRAME_BYTES,%d0
        add.l   %d0,%d3
        move.l  %d3,stems_wr        | publish after the data
        move.l  stems_frames,%d0
        addq.l  #1,%d0
        move.l  %d0,stems_frames
        cmpi.l  #MAX_FRAMES,%d0
        bcs.s   .Lh_out
        moveq   #ST_FINISHING,%d0   | 15 seconds
        move.l  %d0,stems_state
.Lh_out:
        movem.l (%sp),%d0-%d5/%a0-%a1
        lea     32(%sp),%sp
.Lh_stock:
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        rts
