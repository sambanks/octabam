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

| ---- constants -----------------------------------------------------------
        .equ    ST_IDLE,       0
        .equ    ST_ARMED,      1
        .equ    ST_RECORDING,  2
        .equ    ST_FINISHING,  3

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
| Reached by `jsr` from 0x40004b12. Performs the two instructions it
| displaced: the call to the per-frame routine, then the SR write.
        .global stems_frame_hook
stems_frame_hook:
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        rts
