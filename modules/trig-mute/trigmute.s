| trigmute.s -- TRIG MUTE: GRID RECORDING, hold a step and press FUNC to
| mute or unmute that trig. A muted trig keeps its locks and its condition
| but does not play; its red LED blinks.
|
| The mute lives in the trig word's condition (TRAC + 0x89a + 2 * step,
| bits 6-0; PARAM_PAGES.md 5g). Stock uses 0 (none) .. 64 (8:8); a muted
| trig holds condition + 65 (65..127), so 7:8 and 8:8 cannot be muted. The
| pattern carries it: stock's save, load, battery copy, copy and paste need
| nothing. Placing or removing a trig clears the condition, and the mute.
| Stock firmware plays a muted trig (> 64 = no condition) and shows ERR.
|
| tmu_gate (step handler 0x4009d34e, the condition test): a muted trig
|          skips as a failed condition does -- no trig, no locks; recorder
|          trigs still run.
| tmu_lbl  (condition label 0x4002ce78): shows the trig's own condition.
| tmu_rd / tmu_wr (condition edit 0x4002da60, audio path): the knob edits
|          the trig's own condition and keeps the mute (7:8 / 8:8 clamp to
|          6:8 while muted).
| tmu_led  (lock-flash pass 0x400340e4, its exit): every muted trig on the
|          shown page gets its red LED inverted for half the period.
| tmu_func (the trig-held layer's key rows, repointed): FUNC with step keys
|          held toggles their mute. Elsewhere FUNC is stock's.

        .set    DBPTR,     0x46c82456   | the current bank
        .set    MIRROR,    0x1001614e   | its battery copy
        .set    UI_TRACK,  0x100b14cc
        .set    UI_PTN,    0x100b14d0
        .set    MIDI_MODE, 0x80000012
        .set    GRID,      0x460d1736   | grid recording on
        .set    EDIT,      0x460d5db4
        .set    HELD,      0x460d174a   | u16: trig keys held (bit = key)
        .set    HELD_BASE, 0x460d174c   | step of key 0 (page * 16)
        .set    PAGE,      0x460d1e04   | shown page
        .set    RELFLAGS,  0x460d1a9e   | five u16: what a trig key's release does
        .set    PTN_STR,   0x8ed8
        .set    TRK_STR,   0x91a
        .set    TWORD,     0x89a        | trig words, 2 a step
        .set    DIRTY,     0x9b332      | bank + this: bank changed
        .set    DIRTY_NV,  0x100f8598
        .set    MARK,      0x40027e00
        .set    REFRESH,   0x4009da20   | (track)
        .set    TOAST,     0x4005a2b8   | (string, duration)
        .set    SET_LED,   0x40013784   | (id, ticks): invert the LED for ticks
        .set    FUNC_DN,   0x4004e954   | stock FUNC press
        .set    FUNC_UP,   0x400568e4   | stock FUNC release
        .set    TRIG_POP,  0x460d1014   | the trig popup (LEFT / RIGHT with a step held)
        .set    EVAL,      0x400a5164
        .set    GATE_JOIN, 0x4009d354
        .set    LBL_JOIN,  0x4002ce82
        .set    RD_JOIN,   0x4002db38
        .set    WR_JOIN,   0x4002db7a
        .set    MUTED,     65           | condition + MUTED = muted

        .text
        .globl  tmu_gate, tmu_lbl, tmu_rd, tmu_wr, tmu_led, tmu_func, TMU_KEYS

| ---- 0x4009d34e: the step's condition test ---------------------------------
| Args on the stack: track, step, condition (bits 6-0), first.
| Displaced: jsr 0x400a5164.
tmu_gate:
        movel   %sp@(8),%d0
        moveq   #64,%d1
        cmpl    %d1,%d0
        bgt.w   1f
        jsr     EVAL
        jmp     GATE_JOIN
1:      moveq   #1,%d0                  | muted: as a failed condition
        jmp     GATE_JOIN

| ---- 0x4002ce78: the condition label, d0 = condition -----------------------
| Displaced: movel %sp@(32),%d0 ; movel #0x400b37df,%d2
tmu_lbl:
        movel   %sp@(32),%d0
        movel   #0x400b37df,%d2
        moveq   #64,%d1
        cmpl    %d1,%d0
        ble.w   1f
        moveq   #MUTED,%d1
        subl    %d1,%d0
1:      jmp     LBL_JOIN

| ---- 0x4002daea: the condition edit reads an audio trig's condition ---------
| Displaced: moveb %a0@(1,%d0:l:2),%d0 ; moveq #127,%d1 ; andl %d1,%d0
tmu_rd:
        moveb   %a0@(1,%d0:l:2),%d0
        moveq   #127,%d1
        andl    %d1,%d0
        clrl    tmu_em
        moveq   #64,%d1
        cmpl    %d1,%d0
        ble.w   1f
        moveq   #MUTED,%d1
        subl    %d1,%d0
        moveq   #1,%d1
        movel   %d1,tmu_em
1:      jmp     RD_JOIN

| ---- 0x4002db72: ... and writes it back, d2 = the new condition 0..64 -------
| Displaced: moveq #127,%d3 ; andl %d3,%d2 ; movew #1165,%d3
tmu_wr:
        moveq   #127,%d3
        andl    %d3,%d2
        tstl    tmu_em
        beq.w   1f
        moveq   #62,%d3
        cmpl    %d3,%d2
        ble.w   2f
        movel   %d3,%d2
2:      moveq   #MUTED,%d3
        addl    %d3,%d2
1:      movew   #1165,%d3
        jmp     WR_JOIN

| tmu_trac: a0 = the shown audio track's record in the current bank, d0 =
| its offset from the bank (for the battery copy). Uses d1.
tmu_trac:
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulsl   %d1,%d0
        moveq   #0,%d1
        moveb   UI_TRACK,%d1
        movel   %d0,-(%sp)
        movel   #TRK_STR,%d0
        mulsl   %d0,%d1
        movel   (%sp)+,%d0
        addl    %d1,%d0
        moveal  DBPTR,%a0
        addal   %d0,%a0
        rts

| ---- 0x40034346: the lock-flash pass's exit (its frame still on the stack) --
| d4 = the steps shown on the page (stock's, set on every path to here).
| Displaced: moveml %sp@,%d2-%d6/%a2-%a5 ; lea %sp@(36),%sp -- then rts.
tmu_led:
        tstl    GRID
        beq.w   9f
        tstl    MIDI_MODE
        bne.w   9f
        tstl    EDIT
        bne.w   9f
        bsr     tmu_trac
        moveal  %a0,%a2                 | track record
        moveq   #0,%d2                  | key 0..15
        movel   PAGE,%d3
        lsll    #4,%d3                  | step of key 0
1:      cmpl    %d4,%d2
        bge.w   9f
        movel   %d3,%d1
        addl    %d2,%d1                 | step
        moveal  %a2,%a0
        bsr     tmu_sample
        beq.w   2f
        lea     %a2@(TWORD+1),%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l:2),%d0
        moveq   #127,%d5
        andl    %d5,%d0
        moveq   #64,%d5
        cmpl    %d5,%d0
        ble.w   2f
        pea     15
        movel   %d2,%d0
        addl    %d0,%d0                 | red LED of the key
        movel   %d0,-(%sp)
        jsr     SET_LED
        addql   #8,%sp
2:      addql   #1,%d2
        bra.s   1b
9:      moveml  %sp@,%d2-%d6/%a2-%a5
        lea     %sp@(36),%sp
        rts

| tmu_sample: d1 = step, a0 = track record -> d0 nonzero (Z clear) when the
| step has a sample trig. Keeps d1.
tmu_sample:
        movel   %d1,-(%sp)
        cmpil   #32,%d1
        bge.w   1f
        movel   %a0@(4),%d0
        bra.w   2f
1:      movel   %a0@,%d0
        subil   #32,%d1
2:      lsrl    %d1,%d0
        moveq   #1,%d1
        andl    %d1,%d0
        movel   (%sp)+,%d1
        tstl    %d0
        rts

| ---- FUNC in the trig-held layer: 4(sp) = key, 8(sp) = edge -----------------
tmu_func:
        moveq   #1,%d0
        cmpl    %sp@(8),%d0
        beq.s   1f
        tstl    %sp@(8)
        bne.s   0f                      | hold: nothing
        tstl    tmu_ate                 | release: ours if the press was
        beq.w   9f
        clrl    tmu_ate
0:      rts
1:        tstl    GRID
        beq.w   8f
        tstl    MIDI_MODE
        bne.w   8f
        moveq   #0,%d0
        movew   HELD,%d0
        tstl    %d0
        beq.w   8f
        lea     %sp@(-28),%sp
        moveml  %d2-%d6/%a2-%a3,%sp@
        moveq   #1,%d1
        movel   %d1,tmu_ate             | its release is ours too: stock's
        movel   %d0,%d6                 | would close the trig popup
        bsr     tmu_trac
        moveal  %a0,%a2                 | track record
        moveal  #MIRROR,%a3
        addal   %d0,%a3                 | its battery copy
        lea     T_NONE:l,%a1
        movel   %a1,tmu_msg
        moveq   #0,%d2                  | key
1:      btst    %d2,%d6
        beq.w   5f
        movel   %d2,%d1
        addl    HELD_BASE,%d1           | step
        moveq   #63,%d0
        cmpl    %d0,%d1
        bhi.w   5f
        moveal  %a2,%a0
        bsr     tmu_sample
        beq.w   5f                      | no sample trig: nothing to mute
        lea     %a2@(TWORD+1),%a0
        moveq   #0,%d3
        moveb   %a0@(0,%d1:l:2),%d3
        movel   %d3,%d4
        andil   #0x80,%d4               | micro-timing bit kept
        andil   #0x7f,%d3
        moveq   #64,%d0
        cmpl    %d0,%d3
        ble.w   2f
        moveq   #MUTED,%d0              | muted: unmute
        subl    %d0,%d3
        lea     T_OFF:l,%a1
        bra.w   4f
2:      moveq   #62,%d0
        cmpl    %d0,%d3
        ble.w   3f
        lea     T_HIGH:l,%a1            | 7:8 / 8:8: no room
        movel   %a1,tmu_msg
        bra.w   5f
3:      moveq   #MUTED,%d0
        addl    %d0,%d3
        lea     T_ON:l,%a1
4:      movel   %a1,tmu_msg
        orl     %d4,%d3
        lea     %a2@(TWORD+1),%a0
        moveb   %d3,%a0@(0,%d1:l:2)
        lea     %a3@(TWORD+1),%a0
        moveb   %d3,%a0@(0,%d1:l:2)
        moveq   #1,%d5
        movel   %d5,tmu_dirty
5:      addql   #1,%d2
        moveq   #16,%d0
        cmpl    %d0,%d2
        blt.w   1b
        moveq   #-1,%d0                 | the release does nothing: no remove,
        eorl    %d6,%d0                 | no ACCENT step
        lea     RELFLAGS,%a0
        moveq   #4,%d1
6:      movew   %a0@,%d2
        andl    %d0,%d2
        movew   %d2,%a0@+
        subql   #1,%d1
        bge.s   6b
        tstl    tmu_dirty
        beq.w   7f
        clrl    tmu_dirty
        moveal  DBPTR,%a0
        addal   #DIRTY,%a0
        moveq   #1,%d0
        movel   %d0,%a0@
        movel   %d0,DIRTY_NV
        jsr     MARK
        moveq   #0,%d0
        moveb   UI_TRACK,%d0
        movel   %d0,-(%sp)
        jsr     REFRESH
        addql   #4,%sp
7:      tstl    TRIG_POP                | the trig popup open: no toast (it
        bne.s   3f                      | would close the popup)
        pea     0x30
        movel   tmu_msg,-(%sp)
        jsr     TOAST
        addql   #8,%sp
3:
        moveml  %sp@,%d2-%d6/%a2-%a3
        lea     %sp@(28),%sp
        rts
8:      jmp     FUNC_DN                 | not ours: stock FUNC
9:      jmp     FUNC_UP

| ---- the trig-held layer's key rows (26 bytes each), 0x400bec0a + FUNC ------
| {code, 0, press, release, hold, sub-map, 0, delay, flags}
        .balign 2
TMU_KEYS:
        .irp    k, 0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d
        .byte   \k, 0
        .long   0x4005040c, 0x4005040c, 0, 0, 0
        .word   0, 0
        .endr
        .irp    k, 0x34, 0x21
        .byte   \k, 0
        .long   0x400435c4, 0, 0x400435c4, 0, 0
        .word   0x000f, 0x0004
        .endr
        .irp    k, 0x20, 0x33
        .byte   \k, 0
        .long   0x400434d8, 0, 0, 0, 0
        .word   0, 0
        .endr
        .byte   0x29, 0
        .long   0x4005f9f4, 0, 0, 0, 0
        .word   0, 0
        .byte   0x28, 0
        .long   0x4005f82c, 0, 0, 0, 0
        .word   0, 0
        .byte   0x27, 0
        .long   0x4005f5d4, 0, 0, 0, 0
        .word   0, 0
        .byte   0x31, 0
        .long   0x40043d88, 0x40043d88, 0, 0, 0
        .word   0, 0
        .byte   0x32, 0
        .long   0x40040f90, 0, 0, 0, 0
        .word   0, 0
        .byte   0x2a, 0
        .long   0x40043e00, 0x40043e00, 0, 0, 0
        .word   0, 0
        .byte   0x2d, 0
        .long   tmu_func, tmu_func, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0

T_ON:   .asciz  "TRIG MUTED"
T_OFF:  .asciz  "TRIG UNMUTED"
T_HIGH: .asciz  "CAN'T MUTE 7:8 8:8"
T_NONE: .asciz  "NO TRIG TO MUTE"

        .data
        .balign 4
tmu_em:    .long 0                      | the edited trig is muted
tmu_msg:   .long 0
tmu_dirty: .long 0
tmu_ate:   .long 0                      | FUNC's press was a mute: so is its release
