| DRUMMER -- the machine row: DRUMMER is the sixth row of a track's machine
| list (row 5). A DRUMMER track is a FLEX track (its sample, slices, AMP, FX
| stay FLEX's) signed "DR",1 in the unused NEIGHBOR PLAYBACK bytes of the
| Part (and of its battery copy). Its two pages are the FLEX PLAYBACK bytes
| under DRUMMER's own descriptor (adapter.c dr_track_page): page 1 the live
| knobs, page 2 (SETUP) the configuration.
|
| Derived from ANALOG BD's registration (modules/analog-bassdrum/machine.s,
| repeat98), the measured Machinedrum chooser seams; its engine browser and
| renderer are not taken: a DRUMMER track keeps FLEX's sample pool and the
| stock FLEX renderer. This is the standalone form (no other added machine on
| the list): the manifest declares ANALOG BD, OCTA303 and CX OSC conflicts
| until DRUMMER joins HOOKS' machine_rows.
        .text
        .global dr_machine_name, dr_src_names, dr_main_commit
        .global dr_src_commit, dr_src_commit2, dr_name_a, dr_name_b
        .global dr_setup_row, dr_chooser_row, dr_setup_open, dr_chooser_open
        .global dr_setup_edit6, dr_setup_draw6, dr_resolve_pb, dr_validate
        .global dr_stock_validate, dr_tick_hook, dr_row_type
        .global dr_setup_key, dr_ml_pick, dr_lfo_pb

        .equ    DR_ROW, 5
        .equ    FLEX, 1
        .equ    SRC_CURSOR, 0x460d5c30
        .equ    SRC_FOCUS, 0x460d1a48       | 0 the machine list, 1 a slot list
        .equ    KEY_RIGHT, 0x21
        .equ    KEY_LEFT, 0x34
        .equ    BANK_PTR, 0x46c82456
        .equ    PART_OFF, 0x8ed80
        .equ    SRAM_PART, 0x100a4ece
        .equ    SIG_OFF, 0x2a + 18          | NEIGHBOR's PLAYBACK column
        .equ    PAGE2_GAP, 0x1da - 0x2a
        .equ    PB_TABLE, 0x400d5f38

| d0 = the signature to write (1) or clear (0) is d1; a0 = the Part, d0 the
| track. A first signing seeds the 12 knob bytes with DRUMMER's defaults.
dr_sig_write:
        lea     -16(%sp),%sp
        movem.l %d0-%d2/%a1,(%sp)
        mulu.w  #30,%d0
        lea     SIG_OFF(%a0,%d0.l),%a1
        bsr.s   .sw_one
        move.l  %a0,%d2
        sub.l   (BANK_PTR).l,%d2
        subi.l  #PART_OFF,%d2
        addi.l  #SRAM_PART + SIG_OFF,%d2
        add.l   %d0,%d2
        movea.l %d2,%a1
        bsr.s   .sw_one
        movem.l (%sp),%d0-%d2/%a1
        lea     16(%sp),%sp
        rts
.sw_one:
        tst.l   %d1
        beq.w   .sw_clear
        move.b  (%a1),%d2
        cmpi.b  #'D',%d2
        beq.s   .sw_mark
        move.l  %a0,-(%sp)
        move.l  %d0,-(%sp)
        lea     dr_defaults,%a0
        moveq   #5,%d0
.sw_defaults1:
        move.b  (%a0)+,-12(%a1)
        addq.l  #1,%a1
        subq.l  #1,%d0
        bpl.s   .sw_defaults1
        lea     -6(%a1),%a1
        moveq   #5,%d0
.sw_defaults2:
        move.b  (%a0)+,PAGE2_GAP-12(%a1)
        addq.l  #1,%a1
        subq.l  #1,%d0
        bpl.s   .sw_defaults2
        lea     -6(%a1),%a1
        move.l  (%sp)+,%d0
        move.l  (%sp)+,%a0
.sw_mark:
        move.b  #'D',(%a1)
        move.b  #'R',1(%a1)
        move.b  #1,2(%a1)
        rts
.sw_clear:
        move.b  (%a1),%d2
        cmpi.b  #'D',%d2
        bne.s   .sw_out
        clr.b   (%a1)
        clr.b   1(%a1)
        clr.b   2(%a1)
.sw_out:
        rts

dr_machine_name:
        move.l  4(%sp),%d0
        cmpi.l  #DR_ROW,%d0
        beq.s   1f
        move.l  %d2,-(%sp)
        move.l  8(%sp),%d1
        jmp     (0x400334de).l
1:      lea     dr_name(%pc),%a0
        move.l  %a0,%d0
        rts

        .balign 4
dr_src_names:
        .long   0x400b3eac
        .long   0x400b3e98
        .long   0x400b7c67
        .long   0x400b5413
        .long   0x400b7a63
        .long   dr_name

dr_main_commit:
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a0,(%sp)
        movea.l %a1,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d1,%d0
        cmpi.l  #DR_ROW,%d4
        bne.s   .mc_other
        moveq   #1,%d1
        bsr     dr_sig_write
        moveq   #FLEX,%d4
        bra.s   .mc_store
.mc_other:
        moveq   #0,%d1
        bsr     dr_sig_write
.mc_store:
        movem.l (%sp),%d0-%d1/%a0
        lea     12(%sp),%sp
        .word   0x7710,0x1084,0xd081
        jmp     (0x40079822).l

dr_src_commit:
        pea     (0x4005a61c).l
        bra.s   dr_src_common
dr_src_commit2:
        pea     (0x4005a856).l
dr_src_common:
        move.l  (SRC_CURSOR).l,%d1
        tst.b   dr_ml_pick
        beq.s   1f
        moveq   #DR_ROW,%d1                 | FLEX's slot list opened from DRUMMER's row
1:
        lea     -12(%sp),%sp
        movem.l %d0/%d2/%a0,(%sp)
        movea.l %a1,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d2,%d0
        cmpi.l  #DR_ROW,%d1
        bne.s   .sc_other
        moveq   #1,%d1
        bsr     dr_sig_write
        moveq   #FLEX,%d1
        bra.s   .sc_go
.sc_other:
        move.l  %d1,-(%sp)
        moveq   #0,%d1
        bsr     dr_sig_write
        move.l  (%sp)+,%d1
.sc_go:
        movem.l (%sp),%d0/%d2/%a0
        lea     12(%sp),%sp
        rts

dr_setup_open:
        bsr     dr_pick_end
        move.b  (%a0),%d3
        move.l  %d0,-(%sp)
        mvs.b   %d3,%d0
        bsr     dr_row_type
        move.l  %d0,%d3
        move.l  (%sp)+,%d0
        mvs.b   %d3,%d4
        pea     (0x400bb704).l
        jmp     (0x400585e6).l

dr_setup_edit6:
        cmpi.l  #DR_ROW,%d2
        bne.s   1f
        moveq   #FLEX,%d2
1:      move.l  %d2,%d0
        lsl.l   #3,%d0
        add.l   %d2,%d2
        sub.l   %d2,%d0
        jmp     (0x4003a536).l
dr_setup_draw6:
        cmpi.l  #DR_ROW,%d6
        bne.s   1f
        moveq   #FLEX,%d6
1:      move.l  %d6,%d7
        lsl.l   #3,%d7
        add.l   %d6,%d6
        sub.l   %d6,%d7
        jmp     (0x4003cda0).l

dr_chooser_open:
        mvs.b   (%a0),%d0
        bsr     dr_row_type
        move.l  %d0,-(%sp)
        pea     (0x460e7386).l
        jmp     (0x40078890).l

dr_name_a:
        bsr.s   dr_name_pick
        jmp     (0x4003d722).l
dr_name_b:
        bsr.s   dr_name_pick
        jmp     (0x4004c374).l
dr_name_pick:
        bsr     dr_row_type
        lea     dr_src_names(%pc),%a0
        move.l  (%a0,%d0.l*4),%d1
        rts

dr_setup_row:
        mvs.b   (%a0),%d0
        lea     24(%sp),%sp
        bsr.s   dr_row_type
        jmp     (0x4003c986).l
dr_chooser_row:
        mvs.b   (%a0),%d0
        bsr.s   dr_row_type
        cmp.l   %d0,%d2
        bne.s   1f
        jmp     (0x400786ce).l
1:      jmp     (0x400786fc).l

| d0 = a stored machine type, a0 = its byte in the Part: 5 for a signed
| FLEX track, else d0. Keeps every register but d0.
dr_row_type:
        lea     -20(%sp),%sp
        movem.l %d1/%a0-%a1,8(%sp)
        move.l  %d0,(%sp)
        move.l  %a0,4(%sp)
        jsr     dr_type
        movem.l 8(%sp),%d1/%a0-%a1
        lea     20(%sp),%sp
        rts

dr_resolve_pb:
        mvs.b   %d5,%d0
        bsr     dr_row_type
        cmpi.l  #DR_ROW,%d0
        bne.s   1f
        move.l  %a0,-(%sp)
        jsr     dr_track_page
        addq.l  #4,%sp
        jmp     (0x40031ed6).l
1:      lea     (PB_TABLE).l,%a0
        jmp     (0x40031ece).l

| The LFO destination's name (0x4003bf64): its SRC page is PB_TABLE[the
| stored type], FLEX's knobs (PTCH STRT ...) on a DRUMMER track; DRUMMER's
| page there instead. d1 is read after (0x4003c086), a C call clobbers it.
dr_lfo_pb:
        mvs.b   (%a0),%d0
        bsr     dr_row_type
        cmpi.l  #DR_ROW,%d0
        bne.s   1f
        move.l  %d1,-(%sp)
        move.l  %a0,-(%sp)
        jsr     dr_track_page
        addq.l  #4,%sp
        move.l  (%sp)+,%d1
        movea.l %d0,%a2
        jmp     (0x4003c058).l
1:      lea     (PB_TABLE).l,%a0
        jmp     (0x4003c054).l

dr_validate:
        jmp     dr_validate_part
dr_stock_validate:
        lea     -96(%sp),%sp
        movem.l %d2-%d7/%a2-%fp,(%sp)
        jmp     (0x40002320).l

dr_tick_hook:
        jsr     0x4005213c
        jsr     0x4007e940
        jsr     dr_ui_tick
        jmp     0x40052228

| SRC SETUP's key handler (0x4003d1c0, the key on the stack). RIGHT on
| DRUMMER's row opens FLEX's slot list: the cursor is FLEX's while the list
| is open (stock's slot list, preview and commit all read the cursor), the
| commit signs DRUMMER (dr_src_common), and LEFT puts the cursor back.
dr_setup_key:
        move.l  4(%sp),%d0
        tst.l   (SRC_FOCUS).l
        bne.s   .sk_list
        cmpi.l  #KEY_RIGHT,%d0
        bne.s   .sk_go
        moveq   #DR_ROW,%d1
        cmp.l   (SRC_CURSOR).l,%d1
        bne.s   .sk_go
        moveq   #FLEX,%d1
        move.l  %d1,(SRC_CURSOR).l
        move.b  %d1,dr_ml_pick
        jsr     dr_pick_page
        bra.s   .sk_go
.sk_list:
        cmpi.l  #KEY_LEFT,%d0
        bne.s   .sk_go
        tst.b   dr_ml_pick
        beq.s   .sk_go
        bsr.s   dr_pick_end
        moveq   #DR_ROW,%d1
        move.l  %d1,(SRC_CURSOR).l
        jsr     dr_pick_page
.sk_go:
        move.l  %d2,-(%sp)
        move.l  8(%sp),%d0
        move.l  (SRC_FOCUS).l,%d1
        jmp     (0x4003d1cc).l
| The pick is over. Keeps every register.
dr_pick_end:
        clr.b   dr_ml_pick
        rts
dr_name:
        .asciz  "DRUMMER"
        .section .data
dr_ml_pick:                             | 1 while FLEX's slot list is open from DRUMMER's row
        .byte   0
        .text
        .balign 2
| The 12 knob bytes a track gets when it first becomes DRUMMER:
| live SEED DENS CPLX ORN BRK GHST, config STYL VEL ALT SWNG HUMN VAR (image 61).
        .global dr_defaults
dr_defaults:
        .byte   0, 64, 32, 16, 0, 48
        .byte   0, 64, 64, 64, 64, 64
        .balign 2
