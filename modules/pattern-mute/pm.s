| PATTERN MUTE -- a second mute layer saved with the pattern, as on the Digitakt II.
|
| Stock keeps one mute state per project: bits 8-15 of 0x80000008 (audio
| tracks 1-8) and of 0x8000000c (MIDI tracks 1-8), a set bit = muted. This
| unit keeps two layers. GLOBAL is stock's state, saved in project.work.
| PATTERN is stored in the pattern. The word stock and every reader see is
| their OR, so MUTE MODE, the LEDs, the MIXER page and MIDI need no change.
|
| Every stock writer of a mute word is followed by a store to a battery SRAM
| mirror (0x100b14d4 audio, 0x100b14d8 MIDI). That store is replaced by
| pm_mirror_a / pm_mirror_m. They read the word stock just wrote, find the bits that
| differ from the effective word published last, give those bits to the
| layer being edited, then republish the OR and store the GLOBAL layer in
| the mirror, so power-off never folds pattern mutes into the global state.
|
| Layer select: a double press of FUNC (two presses within 300 ms). The layer is
| bit 0 of the battery SRAM byte 0x100b14dd, so it survives power-off.
| Stock does nothing on a lone FUNC press. The layer applies to the next
| edit, whichever stock path makes it (FUNC+track, MIXER trig keys, MIDI).
|
| Storage: bit 0 of byte 40 of audio track record k of a pattern's file
| chunk is audio track k+1, bit 1 is MIDI track k+1. In RAM the byte is at
| bank + pattern * 0x8ed8 + 31 + 2330 * k. Measured: the byte is zero in
| every record of the test project, and a SAVE PROJECT round trip returns it
| unchanged. The current bank's CS1 copy (0x1001614e, same layout) is kept
| equal to RAM.

        .include "remix.inc"

        .text
        .globl  pm_mirror_a
        .globl  pm_mirror_m
        .globl  pm_load_a
        .globl  pm_load_m
        .globl  pm_save_a
        .globl  pm_save_m
        .globl  pm_pat_commit
        .globl  pm_func_press
        .globl  pm_ui_tick
        .globl  pm_gl_a, pm_gl_m, pm_pa, pm_pm, pm_ef_a, pm_ef_m, pm_rdy_a, pm_rdy_m
        .balign 2

        .equ    WORD_A,     0x80000008      | solo 0-7, mute 8-15, cue 16-23
        .equ    WORD_M,     0x8000000c      | MIDI: solo 0-7, mute 8-15
        .equ    MIR_A,      0x100b14d4
        .equ    MIR_M,      0x100b14d8
        .equ    PATNO,      0x80000004
        .equ    BANKPTR,    0x46c82456      | the current bank's RAM blob
        .equ    CS1_PAT,    0x1001614e      | the current bank's pattern copy in CS1
        .equ    PAT_STRIDE, 0x8ed8
        .equ    REC_OFF,    31              | audio track record, byte 40 of the file record
        .equ    REC_STRIDE, 2330
        .equ    EDIT_LONG,  0x9b332         | bank + this: "written by the next bank write"
        .equ    EDIT_FLAG,  0x100f8598
        .equ    MUTE_BITS,  0xff00
        .equ    NOTIFY,     0x4005a2b8      | (text, duration), key-handler context
        .equ    MUTE_VIEW,  0x4007c458      | the mute view's refresh, stock calls it after an edit
        .equ    FUNC_STOCK, 0x4004e954      | FUNC's stock press handler
        .equ    TOAST_TIME, 0x30
        .equ    LAYER_B,    0x100b14dd      | battery SRAM: the layer (bit 0), a state-block byte stock never uses
        .equ    SET_LED,    0x40013784      | set_led(id, ticks): ticks of 120 Hz
        .equ    UI_NEXT,    0x400316a0      | the call the UI loop's hook site displaced (the key-repeat tick)
        .equ    CUR_TRACK,  0x80000000      | current track 0-7 in the current mode
        .equ    LED_TICKS,  6
        .equ    DTCN3,      0xfc07c00c      | DMA timer 3 count, 132 MHz free-run
        .equ    DOUBLE_WINDOW, 39600000     | 300 ms

| One mirror hook per word. In: the stock store just ran, the word holds
| stock's new value N. Out: the word holds the effective value, the mirror
| holds N with the GLOBAL layer in its mute bits; d0-d3 and the CCR are
| preserved except that the caller's own store has been replaced.
        .macro  MIRROR_HOOK name, word, mirror, rdy, gl, pa, ef, force=0
\name:
        lea     -20(%sp),%sp
        movem.l %d0-%d4,(%sp)
        move.w  %sr,%d4
        move.w  #0x2700,%sr
        move.l  \word,%d0                   | N
        tst.b   \rdy
        bne.s   1f
        moveq   #1,%d2
        move.b  %d2,\rdy                    | the first write after power-up is the
        move.l  %d0,%d1                     | restore or the load: it is the GLOBAL layer
        and.l   #MUTE_BITS,%d1
        move.l  %d1,\gl
        clr.l   \pa
        move.l  %d0,\ef
1:      move.l  %d0,%d1
        move.l  \ef,%d2
        eor.l   %d2,%d1
        and.l   #MUTE_BITS,%d1              | the mute bits stock changed
        beq.s   3f
        move.l  %d1,%d2
        not.l   %d2                         | d2 = keep mask
        move.l  %d0,%d3
        and.l   %d1,%d3                     | d3 = new values of the changed bits
        .if     !\force
        mvz.b   LAYER_B,%d1
        btst    #0,%d1
        bne.s   2f
        .endif
        move.l  \gl,%d1
        and.l   %d2,%d1
        or.l    %d3,%d1
        move.l  %d1,\gl
        .if     !\force
        bra.s   3f
2:      move.l  \pa,%d1
        and.l   %d2,%d1
        or.l    %d3,%d1
        move.l  %d1,\pa
        move.w  %d4,%sr
        bsr     pm_store_pat                | the pattern layer changed: write it back
        move.w  #0x2700,%sr
        .endif
3:      move.l  %d0,%d3
        and.l   #~MUTE_BITS,%d3             | solo and cue bits as stock wrote them
        move.l  \gl,%d1
        or.l    \pa,%d1
        and.l   #MUTE_BITS,%d1
        or.l    %d3,%d1                     | effective word
        move.l  %d1,\word
        move.l  %d1,\ef
        move.l  \gl,%d1
        and.l   #MUTE_BITS,%d1
        or.l    %d3,%d1                     | mirror: GLOBAL layer only
        move.l  %d1,\mirror
        move.w  %d4,%sr
        movem.l (%sp),%d0-%d4
        lea     20(%sp),%sp
        rts
        .endm

        MIRROR_HOOK pm_mirror_a, WORD_A, MIR_A, pm_rdy_a, pm_gl_a, pm_pa, pm_ef_a
        MIRROR_HOOK pm_mirror_m, WORD_M, MIR_M, pm_rdy_m, pm_gl_m, pm_pm, pm_ef_m
| The project load's own writes (the settings parser) always set the GLOBAL layer.
        MIRROR_HOOK pm_load_a, WORD_A, MIR_A, pm_rdy_a, pm_gl_a, pm_pa, pm_ef_a, 1
        MIRROR_HOOK pm_load_m, WORD_M, MIR_M, pm_rdy_m, pm_gl_m, pm_pm, pm_ef_m, 1

| The project writer's two loads of the mute byte (mvz.b 0x8000000a,%d0 and
| mvz.b 0x8000000e,%d0) save the GLOBAL layer in project.work.
pm_save_a:
        tst.b   pm_rdy_a
        beq.s   1f
        mvz.b   pm_gl_a+2,%d0
        rts
1:      mvz.b   WORD_A+2,%d0
        rts

pm_save_m:
        tst.b   pm_rdy_m
        beq.s   1f
        mvz.b   pm_gl_m+2,%d0
        rts
1:      mvz.b   WORD_M+2,%d0
        rts

| Replaces `move.b %d0,0x80000003` in the UI-side pattern commit
| (0x40062142). The commit runs after a pattern change and after a project
| load. It loads the pattern layer of the current pattern and republishes
| the effective words.
pm_pat_commit:
        move.b  %d0,0x80000003              | the displaced store
        lea     -36(%sp),%sp
        movem.l %d0-%d6/%a0-%a1,(%sp)
        mvz.b   PATNO,%d0
        move.l  #PAT_STRIDE,%d1
        mulu.l  %d1,%d0
        add.l   #REC_OFF,%d0
        move.l  BANKPTR,%a0
        lea     (%a0,%d0.l),%a0
        moveq   #0,%d2                      | k
        moveq   #0,%d5                      | audio pattern layer
        moveq   #0,%d6                      | MIDI pattern layer
1:      mvz.b   (%a0),%d3
        move.l  %d2,%d4
        add.l   #8,%d4                      | bit 8 + k
        btst    #0,%d3
        beq.s   2f
        bset    %d4,%d5
2:      btst    #1,%d3
        beq.s   3f
        bset    %d4,%d6
3:      lea     REC_STRIDE(%a0),%a0
        addq.l  #1,%d2
        cmp.l   #8,%d2
        bne.s   1b
        move.w  %sr,%d4
        move.w  #0x2700,%sr
        move.l  %d5,pm_pa
        move.l  %d6,pm_pm
        moveq   #0,%d3                      | 1 when a word changed
        | audio
        move.l  WORD_A,%d0
        tst.b   pm_rdy_a
        beq.s   4f
        move.l  %d0,%d1
        move.l  pm_ef_a,%d2
        eor.l   %d2,%d1
        and.l   #MUTE_BITS,%d1
        beq.s   5f
4:      moveq   #1,%d2
        move.b  %d2,pm_rdy_a                   | the word moved without a hook: GLOBAL
        move.l  %d0,%d1
        and.l   #MUTE_BITS,%d1
        move.l  %d1,pm_gl_a
5:      move.l  %d0,%d1
        and.l   #~MUTE_BITS,%d1
        move.l  pm_gl_a,%d2
        or.l    pm_pa,%d2
        and.l   #MUTE_BITS,%d2
        or.l    %d2,%d1
        cmp.l   %d0,%d1
        beq.s   6f
        moveq   #1,%d3
6:      move.l  %d1,WORD_A
        move.l  %d1,pm_ef_a
        | MIDI
        move.l  WORD_M,%d0
        tst.b   pm_rdy_m
        beq.s   7f
        move.l  %d0,%d1
        move.l  pm_ef_m,%d2
        eor.l   %d2,%d1
        and.l   #MUTE_BITS,%d1
        beq.s   8f
7:      moveq   #1,%d2
        move.b  %d2,pm_rdy_m
        move.l  %d0,%d1
        and.l   #MUTE_BITS,%d1
        move.l  %d1,pm_gl_m
8:      move.l  %d0,%d1
        and.l   #~MUTE_BITS,%d1
        move.l  pm_gl_m,%d2
        or.l    pm_pm,%d2
        and.l   #MUTE_BITS,%d2
        or.l    %d2,%d1
        cmp.l   %d0,%d1
        beq.s   9f
        moveq   #1,%d3
9:      move.l  %d1,WORD_M
        move.l  %d1,pm_ef_m
        move.w  %d4,%sr
        tst.l   %d3
        beq.s   10f
        jsr     MUTE_VIEW
10:     movem.l (%sp),%d0-%d6/%a0-%a1
        lea     36(%sp),%sp
        rts

| Write both pattern-layer words into the current pattern's records (RAM
| and the CS1 copy) and mark the bank edited, as stock's Part paste does.
pm_store_pat:
        lea     -32(%sp),%sp
        movem.l %d0-%d5/%a0-%a1,(%sp)
        mvz.b   PATNO,%d0
        move.l  #PAT_STRIDE,%d1
        mulu.l  %d1,%d0
        add.l   #REC_OFF,%d0
        move.l  BANKPTR,%a0
        lea     (%a0,%d0.l),%a0
        move.l  #CS1_PAT,%a1
        lea     (%a1,%d0.l),%a1
        moveq   #0,%d2
1:      moveq   #0,%d3
        move.l  %d2,%d4
        add.l   #8,%d4
        move.l  pm_pa,%d5
        btst    %d4,%d5
        beq.s   2f
        moveq   #1,%d3
2:      move.l  pm_pm,%d5
        btst    %d4,%d5
        beq.s   3f
        addq.l  #2,%d3
3:      mvz.b   (%a0),%d5
        and.l   #0xfc,%d5
        or.l    %d3,%d5
        move.b  %d5,(%a0)
        move.b  %d5,(%a1)
        lea     REC_STRIDE(%a0),%a0
        lea     REC_STRIDE(%a1),%a1
        addq.l  #1,%d2
        cmp.l   #8,%d2
        bne.s   1b
        move.l  BANKPTR,%a0
        move.l  #EDIT_LONG,%d1
        moveq   #1,%d0
        move.l  %d0,(%a0,%d1.l)
        move.l  %d0,EDIT_FLAG
        movem.l (%sp),%d0-%d5/%a0-%a1
        lea     32(%sp),%sp
        rts

| FUNC's press record in both stock key tables points here. The key layer
| calls a press handler with (code, edge) on the stack: edge 1 a press, 2 a
| repeat while held. Two presses within DOUBLE_WINDOW counts of the free-run
| timer DTCN3 flip the layer. Every call continues to stock's handler, which
| sets the FUNC-held flag.
pm_func_press:
        moveq   #1,%d0
        cmp.l   8(%sp),%d0
        bne.s   9f
        move.l  DTCN3,%d0
        mvz.b   pm_tap,%d1
        beq.s   8f
        move.l  %d0,%d1
        sub.l   pm_tap_t,%d1
        cmp.l   #DOUBLE_WINDOW,%d1
        bhi.s   8f
        clr.l   %d1
        move.b  %d1,pm_tap                  | the pair is used up
        mvz.b   LAYER_B,%d0
        and.l   #1,%d0
        eori.l  #1,%d0
        move.b  %d0,LAYER_B                 | battery SRAM: survives power-off
        lea     pm_txt_glob:l,%a0
        tst.l   %d0
        beq.s   1f
        lea     pm_txt_pat:l,%a0
1:      moveq   #TOAST_TIME,%d1
        move.l  %d1,-(%sp)
        move.l  %a0,-(%sp)
        jsr     NOTIFY
        addq.l  #8,%sp
        bra.s   9f
8:      move.l  %d0,pm_tap_t
        moveq   #1,%d1
        move.b  %d1,pm_tap
9:      jmp     FUNC_STOCK

| The UI loop's call at 0x40052228 (jsr 0x400316a0, the key-repeat tick, 60 Hz) reaches this
| first. While the PATTERN layer is active it holds the second colour bit of
| the current track's key lit, so the key shows both colours; stock lights
| only the first for the selected track. set_led(id, ticks) is stock's own
| LED API: the bit clears when its countdown ends, and the countdown here is
| three UI ticks.
pm_ui_tick:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        mvz.b   LAYER_B,%d0
        btst    #0,%d0
        beq.s   9f
        mvz.b   CUR_TRACK,%d0
        and.l   #7,%d0
        move.l  %d0,%d1
        lsr.l   #2,%d1
        addq.l  #5,%d1                      | track keys: rows 5 and 6
        lsl.l   #3,%d1
        and.l   #3,%d0
        add.l   %d0,%d0
        add.l   %d0,%d1
        addq.l  #1,%d1                      | the odd bit
        moveq   #LED_TICKS,%d0
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        jsr     SET_LED
        addq.l  #8,%sp
9:      movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        jmp     UI_NEXT

        .data
        .balign 4
pm_gl_a:        .long   0                   | GLOBAL layer, audio (bits 8-15)
pm_gl_m:        .long   0
pm_pa:          .long   0                   | PATTERN layer of the current pattern
pm_pm:          .long   0
pm_ef_a:        .long   0                   | the effective word published last
pm_ef_m:        .long   0
pm_rdy_a:       .byte   0
pm_rdy_m:       .byte   0
pm_tap:         .byte   0                   | 1 when pm_tap_t holds a FUNC press
        .balign 4
pm_tap_t:       .long   0
pm_txt_glob:    .asciz  "GLOBAL MUTE"
pm_txt_pat:     .asciz  "PATTERN MUTE"
