| pageloop.s -- PAGE LOOP: loop one 16-step page of one track, in time.
|
| In GRID RECORDING, hold PAGE and tap trig 1..4: the current track (audio
| or MIDI) loops that page; the same combo again (or a pattern / bank
| change) ends it. Other tracks play on, and on the way out the track is
| exactly where it would have been.
|
| The play step 0x800064d0[t] (audio t = 0..7, MIDI 8..15) IS the track's
| position: the tick adds one per step (0x400a3d72 audio, 0x400a3e8c MIDI)
| and clears it at the track's length (0x400a3d90, 0x400a3eb0). Every
| reader -- trig test, locks, micro timing, the playhead LED -- uses it.
| For the looped track this module keeps the true position in pl_true
| and stores page*16 + (true & 15) % span instead; the wrap compare still
| sees the true position, so pattern-end handling (0x400a536c) is stock's.
| A value in the step that is not the one we stored was put there by
| someone else (transport start, a resync): it becomes the true position.
| Leaving the loop stores the true position again at the next step.
|
| Tick context: RAM reads and writes of our own .data only, no UI or
| kernel calls. pl_key runs from the PAGE held layer (a key handler).

        .set    DBPTR,     0x46c82456
        .set    UI_TRACK,  0x100b14cc
        .set    UI_PTN,    0x100b14d0
        .set    MIDI_MODE, 0x80000012   | nonzero: MIDI tracks shown
        .set    PLAY_PTN,  0x800065be   | playing pattern
        .set    PLAY_BANK, 0x800065bd   | playing bank
        .set    NO_FLIP,   0x460d1754   | set: PAGE release keeps the page
        .set    PTN_STR,   0x8ed8
        .set    TRK_STR,   0x91a
        .set    PAT_LEN,   0x8e53       | pattern length, steps (NORMAL)
        .set    PAT_PER,   0x8e55       | nonzero = PER TRACK
        .set    TRK_LEN,   0x50         | audio TRAC: its length (PER TRACK)
        .set    TOAST,     0x4005a2b8   | (string, duration): key handlers only
        .set    TRK_END,   0x400a536c   | stock's end-of-track call (track)
        .set    INC_A_GO,  0x400a3d7a
        .set    WRAP_A_GO, 0x400a3d96
        .set    INC_M_GO,  0x400a3e94
        .set    WRAP_M_GO, 0x400a3eba
        .set    START_A_GO, 0x4009bcbe
        .set    START_M_GO, 0x4009bdec
        .set    STEP,      0x800064d0   | next step per track (16)
        .set    CUR_OFF,   16           | STEP+16: the step playing (0x800064e0)

        .text
        .globl  pl_inc_a, pl_wrap_a, pl_inc_m, pl_wrap_m, pl_start_a, pl_start_m
        .globl  pl_key, PL_KEYS
        .globl  pl_trk, pl_page, pl_exit, pl_true

| ---- 0x400a3d72: audio step + 1. a1 = &step[d3], d3 = track 0..7 ---------
| Displaced: moveb %a1@,%d0 ; addql #1,%d0 ; moveb %d0,%d1 ; moveb %d0,%a1@.
| Out: d1 = the true next step (stock compares it with the length).
pl_inc_a:
        cmpl    pl_trk,%d3
        beq.s   1f
        cmpl    pl_exit,%d3
        beq.s   1f
        moveb   (%a1),%d0
        addql   #1,%d0
        moveb   %d0,%d1
        moveb   %d0,(%a1)
        jmp     INC_A_GO
1:      movel   %d3,%d0
        moveal  %a1,%a0
        bsr.w   pl_adv
        jmp     INC_A_GO

| ---- 0x400a3d90: audio wrap. Displaced: moveal %sp@(152),%a0 ; clrb %a0@ --
pl_wrap_a:
        moveal  152(%sp),%a0
        cmpl    pl_trk,%d3
        bne.s   1f
        bsr.w   pl_wrap
        jmp     WRAP_A_GO
1:      clrb    (%a0)
        jmp     WRAP_A_GO

| ---- 0x400a3e8c: MIDI step + 1. a2 = &step[d3], d3 = 8..15 ---------------
| Displaced: moveb %a2@,%d0 ; addql #1,%d0 ; moveb %d0,%d1 ; moveb %d0,%a2@.
pl_inc_m:
        cmpl    pl_trk,%d3
        beq.s   1f
        cmpl    pl_exit,%d3
        beq.s   1f
        moveb   (%a2),%d0
        addql   #1,%d0
        moveb   %d0,%d1
        moveb   %d0,(%a2)
        jmp     INC_M_GO
1:      movel   %d3,%d0
        moveal  %a2,%a0
        bsr.w   pl_adv
        jmp     INC_M_GO

| ---- 0x400a3eb0: MIDI wrap. Displaced: clrb %a2@ ; movel %d3,-(sp) ;
| jsr 0x400a536c (the rejoin pops the argument).
pl_wrap_m:
        moveal  %a2,%a0
        cmpl    pl_trk,%d3
        bne.s   1f
        bsr.w   pl_wrap
        bra.s   2f
1:      clrb    (%a0)
2:      movel   %d3,-(%sp)
        jsr     TRK_END
        jmp     WRAP_M_GO

| ---- 0x4009bcb6 / 0x4009bde6: transport start (and resync) has just set
| every track's step from its position word; d2 = the track (audio 0..7,
| MIDI 8..15). The looped track's becomes its page's step before any trig
| of it fires.
| Audio displaced: moveal %sp@(48),%a3 ; moveb %a1@,%a3@(32).
pl_start_a:
        moveal  48(%sp),%a3
        moveb   (%a1),32(%a3)
        cmpl    pl_trk,%d2
        bne.s   1f
        bsr.s   pl_restart
1:      jmp     START_A_GO

| MIDI displaced: moveb %a0@,%fp@(40) ; st %d0.
pl_start_m:
        moveb   (%a0),40(%fp)
        cmpl    pl_trk,%d2
        bne.s   1f
        bsr.s   pl_restart
1:      st      %d0
        jmp     START_M_GO

| The start writes both the step about to play (STEP+16, CUR) and the next
| one (STEP): both hold true positions. Keep the next as the truth, store
| the page's step in both. Clobbers d0 only.
pl_restart:
        movel   %a0,-(%sp)
        lea     STEP,%a0
        addal   %d2,%a0
        moveq   #0,%d0
        moveb   CUR_OFF(%a0),%d0
        bsr.s   pl_map
        moveb   %d0,CUR_OFF(%a0)
        moveq   #0,%d0
        moveb   (%a0),%d0
        movel   %d0,pl_true
        bsr.s   pl_map
        movel   %d0,pl_last
        moveb   %d0,(%a0)
        moveal  (%sp)+,%a0
        rts

| ---- the shadow ----------------------------------------------------------

| One step of the looped (or leaving) track d0, its step byte at a0.
| Out: d1 = true next. Clobbers d0.
pl_adv:
        movel   %d2,-(%sp)
        movel   %d0,%d2
        bsr.w   pl_check                | a pattern / bank change: leave
        moveq   #0,%d0
        moveb   (%a0),%d0
        cmpl    pl_last,%d0
        beq.s   1f
        movel   %d0,pl_true             | not ours: someone set the position
1:      movel   pl_true,%d1
        addql   #1,%d1
        movel   %d1,pl_true
        movel   %d1,%d0
        cmpl    pl_exit,%d2
        bne.s   2f
        moveq   #-1,%d2                 | leaving: the true step, done
        movel   %d2,pl_exit
        bra.s   3f
2:      bsr.s   pl_map
3:      movel   %d0,pl_last
        moveb   %d0,(%a0)
        movel   (%sp)+,%d2
        rts

| The looped track wraps: its step is the page's first, the truth 0.
| a0 = the step byte. Clobbers d0.
pl_wrap:
        moveq   #0,%d0
        movel   %d0,pl_true
        bsr.s   pl_map
        movel   %d0,pl_last
        moveb   %d0,(%a0)
        rts

| d0 := pl_base + (d0 & 15) % pl_span. Clobbers nothing else.
pl_map:
        andil   #15,%d0
1:      cmpl    pl_span,%d0
        bcs.s   2f
        subl    pl_span,%d0
        bra.s   1b
2:      addl    pl_base,%d0
        rts

| The playing pattern or bank is not the one the loop started on: leave.
pl_check:
        tstl    pl_trk
        bmi.s   9f
        moveq   #0,%d0
        moveb   PLAY_PTN,%d0
        cmpl    pl_ptn,%d0
        bne.s   1f
        moveb   PLAY_BANK,%d0
        cmpl    pl_bank,%d0
        beq.s   9f
1:      movel   pl_trk,%d0
        movel   %d0,pl_exit
        moveq   #-1,%d0
        movel   %d0,pl_trk
9:      rts

| ---- PAGE held + trig 1..4 (grid recording) -------------------------------
| Stack: 4(sp) = key code 0..3 = the page, 8(sp) = event.
pl_key:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        moveq   #1,%d0
        movel   %d0,NO_FLIP             | as stock's PAGE + STOP: no page flip
        movel   16(%sp),%d3             | page
        andil   #3,%d3
        moveq   #0,%d2
        moveb   UI_TRACK,%d2
        andil   #7,%d2
        tstl    MIDI_MODE
        beq.s   1f
        addql   #8,%d2                  | MIDI track t is 8 + t
1:      cmpl    pl_trk,%d2              | same track and page: off
        bne.s   2f
        cmpl    pl_page,%d3
        bne.s   2f
        movel   %d2,pl_exit
        moveq   #-1,%d0
        movel   %d0,pl_trk
        lea     T_OFF:l,%a0
        bra.w   9f
2:      bsr.w   pl_length               | d0 = steps of this track
        movel   %d3,%d1
        lsll    #4,%d1
        subl    %d1,%d0                 | steps on that page
        bgt.s   3f
        lea     T_NONE:l,%a0            | the pattern is shorter
        bra.s   9f
3:      moveq   #16,%d4
        cmpl    %d4,%d0
        ble.s   4f
        movel   %d4,%d0
4:      movel   pl_trk,%d4              | another track looping: it leaves
        bmi.s   5f
        cmpl    %d2,%d4
        beq.s   5f
        movel   %d4,pl_exit
5:      moveq   #-1,%d4
        movel   %d4,pl_trk              | off while the state changes
        cmpl    pl_exit,%d2
        bne.s   6f
        movel   %d4,pl_exit
6:      movel   %d4,pl_last             | resync from the step on entry
        movel   %d0,pl_span
        movel   %d3,pl_page
        movel   %d1,pl_base
        moveq   #0,%d0
        moveb   PLAY_PTN,%d0
        movel   %d0,pl_ptn
        moveb   PLAY_BANK,%d0
        movel   %d0,pl_bank
        movel   %d2,pl_trk              | last: the tick reads it
        lea     T_PAGE:l,%a0
        movel   %d3,%d0
        addil   #'1',%d0
        moveb   %d0,T_DIGIT-T_PAGE(%a0)
9:      pea     0x30
        movel   %a0,-(%sp)
        jsr     TOAST
        addql   #8,%sp
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| d0 := the shown pattern's length in steps for track d2 (PER TRACK: an
| audio track's own; a MIDI track uses the pattern's). Clobbers d1, a0.
pl_length:
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulsl   %d1,%d0
        addal   %d0,%a0                 | pattern
        movel   #PAT_PER,%d1
        tstb    (%a0,%d1.l)
        beq.s   1f
        moveq   #8,%d1
        cmpl    %d1,%d2
        bge.s   1f                      | MIDI: the pattern's length
        movel   %d2,%d0
        movel   #TRK_STR,%d1
        mulsl   %d1,%d0
        addil   #TRK_LEN,%d0
        bra.s   2f
1:      movel   #PAT_LEN,%d0
2:      moveq   #0,%d1
        moveb   (%a0,%d0.l),%d1
        movel   %d1,%d0
        rts

| ---- the PAGE held layer's key rows (26 bytes each) -------------------------
| {code, 0, press, release, 0, 0, 0, flags}. The first three are stock's
| rows at 0x400bee88 (REC / PLAY / STOP), then trig 1..4, then the end.
        .balign 2
PL_KEYS:
        .byte   0x29, 0
        .long   0x4005e94c, 0, 0, 0, 0
        .word   0, 0
        .byte   0x28, 0
        .long   0x4005e728, 0, 0, 0, 0
        .word   0, 0
        .byte   0x27, 0
        .long   0x4005e4f4, 0, 0, 0, 0
        .word   0, 0
        .irp    k, 0, 1, 2, 3
        .byte   \k, 0
        .long   pl_key, 0, 0, 0, 0
        .word   0, 0
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0

T_OFF:  .asciz  "LOOP OFF"
T_NONE: .asciz  "NO SUCH PAGE"

        .data
        .balign 4
pl_trk:  .long  -1                      | looped track: 0..7 audio, 8..15 MIDI; -1 off
pl_page: .long  0
pl_exit: .long  -1                      | track that left: true step at its next step
pl_true: .long  0                       | the looped track's true position
pl_last: .long  -1                      | the step we last stored
pl_span: .long  16
pl_base: .long  0                       | page * 16
pl_ptn:  .long  0
pl_bank: .long  0
T_PAGE:  .ascii "LOOP PAGE "
T_DIGIT: .asciz "1"
