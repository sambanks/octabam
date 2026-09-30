| octabam DOOM -- the glue the firmware calls: the two boot hooks, the
| stack switch Doom runs on, and the input layer.
|
| SPDX-License-Identifier: GPL-2.0-or-later

        .text

| ---- the boot hooks: OS SWITCH's boot picker sites (manifest.py) ------
| 0x4002574c (a jmp detour over `pea PROJNAME`): the named project's
| (re)load post. DOOM takes the boot, or hands it to OS SWITCH's picker
| exactly as its own detour would have reached it. d0-d1/a0-a1 are kept
| for the hand-over.
        .global doom_projpost
doom_projpost:
        lea     (-16,%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     doom_boot
        tst.l   %d0
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     (16,%sp),%sp
        beq.s   1f
        rts                             | held, as the picker holds it
1:      jmp     osw_bootpick

| 0x4002573e (a jsr detour over `jsr 0x400228dc`): the last-set mount's
| LOADING FILES post, the boot's only post on a unit whose SRAM knows the
| card.
        .global doom_files
doom_files:
        lea     (-16,%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     doom_boot
        tst.l   %d0
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     (16,%sp),%sp
        beq.s   1f
        rts
1:      jmp     osw_bootfiles

| ---- doom_run(fn, stack_top): fn() on Doom's own stack ----------------
| The UI task's stack is 2 KB (docs/firmware/KERNEL.md); Doom's renderer
| and printf want far more. Interrupts and task switches taken while fn
| runs land on this stack too, which is only memory. Returns 0, or the
| code doom_bail was given (never 0).
        .global doom_run, doom_bail
doom_run:
        lea     (-44,%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  (48,%sp),%a0            | fn
        move.l  (52,%sp),%d0            | stack top
        move.l  %sp,doom_saved_sp
        move.l  %d0,%sp
        jsr     (%a0)
        moveq   #0,%d0
doom_back:
        move.l  doom_saved_sp,%sp
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     (44,%sp),%sp
        rts

doom_bail:
        move.l  (4,%sp),%d0
        bra.s   doom_back

| ---- the deferred call's message, as 0x40063660 posts it: {u8 21, u32 fn}
        .global doom_msg
        .align  2
doom_msg:
        .byte   21, 0
        .long   doom_frame
        .word   0

| ---- the input layer: {0, keys, encoders, 0, 0, -1, -1} ---------------
| Every key code 0x00..0x3f has a record, so nothing falls through to the
| stock layers below while Doom has the panel. Key records are 26 B
| {code, 0, press, release, repeat, aux, 0, delay.w, rate.w}; the handlers
| are called (code, pressed). Encoder records 22 B {index, 0, handler,
| 16 B}, called (index, delta). (modules/dj-decks/screen.s, measured.)
        .global doom_layer
        .align  2
doom_layer:
        .long   0, doom_keys, doom_encs, 0, 0, -1, -1
doom_keys:
        .set    k, 0
        .rept   64
        .byte   k, 0
        .if     k == 0x2d
        .long   doom_kdown, doom_kup, 0, doom_funclayer, 0   | FUNC: its sub-layer while held
        .else
        .long   doom_kdown, doom_kup, 0, 0, 0
        .endif
        .word   0, 0
        .set    k, k + 1
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
| While a modifier key is held the dispatch uses the layer its record's
| +0xe names (stock FUNC's is 0x400bfa32, CUE's 0x400bf2a0: {0, keys,
| encs, ...}, read from the image 30 Sep 2026). So FUNC + key reaches this
| table, not the one above: STOP goes home, everything else as without.
doom_funclayer:
        .long   0, doom_fkeys, doom_encs, 0, 0, -1, -1
doom_fkeys:
        .set    k, 0
        .rept   64
        .byte   k, 0
        .if     k == 0x27
        .long   doom_home, 0, 0, 0, 0
        .else
        .long   doom_kdown, doom_kup, 0, 0, 0
        .endif
        .word   0, 0
        .set    k, k + 1
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
doom_encs:
        .set    e, 0
        .rept   7
        .byte   e, 0
        .long   doom_enc, 0, 0, 0, 0
        .set    e, e + 1
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0

        .data
        .align  2
doom_saved_sp:
        .long   0
