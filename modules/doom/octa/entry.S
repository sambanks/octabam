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

| ---- sound: the frame transfer machine's state 7 (0x40004bc0) -----------
| USB AUDIO IN's mechanism (modules/usb-audio-in-ab/usbaudio_in.s, whose
| detour this is; a remix carries one of the two). The transfer IRQ saved
| d0-d1/a0-a1. The first visit per frame builds the block (doom_audio.c)
| and starts one more host-port transfer to core 0 at $6320 -- the idle
| bank + $320 after the DSP's mask, read by doom_mix.asm next frame; that
| transfer's completion is the second visit, which runs the displaced stock
| state 7 (the frame IRQ unmask).
        .set    STATE7_DONE,  0x40004bc8  | the transfer IRQ's movem restore + rte
        .set    FRAME_UNMASK, 0xfc04801d  | stock state 7's write (INTC0 CIMR <- 1)
        .set    EDMA_SADDR,   0xfc045000
        .set    EDMA_NBYTES,  0xfc045008
        .set    EDMA_CITER,   0xfc045014
        .set    EDMA_BITER,   0xfc04501c
        .set    EDMA_START,   0xfc04401e
        .set    CORE_SEL,     0xfc0a400c
        .set    HOST_ICR,     0x20000000
        .set    HOST_CVR,     0x20000004
        .set    HOST_DATA,    0x2000001c
        .set    DSP_DEST,     0x6320
        .set    TX_BYTES,     128         | word 0 + 32 halfwords + pad: two minor loops of 64
        .global doom_state7
doom_state7:
        tst.b   doom_s7busy
        bne.w   2f
        moveq   #1,%d0
        move.b  %d0,doom_s7busy
        lea     (-44,%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        jsr     doom_audio_block
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     (44,%sp),%sp
        clr.b   %d0
        move.b  %d0,(CORE_SEL).l          | core 0
        moveq   #64,%d1
        move.l  %d1,(EDMA_NBYTES).l
        move.l  #(doom_tx+0x08000000),%d1
        move.l  %d1,(EDMA_SADDR).l
        move.w  #0x81,%d0
        move.w  %d0,(HOST_ICR).l
        move.w  #DSP_DEST,%d1
        move.w  %d1,(HOST_DATA).l
        move.w  #TX_BYTES/2-1,%d0
        move.w  %d0,(HOST_DATA).l
        move.w  #0x88,%d1
        move.w  %d1,(HOST_CVR).l
        move.w  #(0x8000+TX_BYTES/64),%d0 | E_LINK, TX_BYTES/64 minor loops
        move.w  %d0,(EDMA_CITER).l
        move.w  %d0,(EDMA_BITER).l
        clr.b   %d1
        move.b  %d1,(EDMA_START).l
        jmp     (STATE7_DONE).l
2:      clr.b   doom_s7busy
        moveq   #1,%d1                    | stock state 7, displaced
        move.b  %d1,(FRAME_UNMASK).l
        jmp     (STATE7_DONE).l

        .data
        .align  2
doom_saved_sp:
        .long   0
doom_s7busy:
        .byte   0
