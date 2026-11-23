| MACHINES -- the detours of the track's machine list, SRC SETUP and the
| Part validator, once for every client (docs/specs/MACHINES.md). Each stub
| asks mc_row_type for a track's row: 5 + the client's index for a signed
| track, else the stored machine. The tables (MC_END, mc_src_names, ...) are
| the remix's: remix.inc, from manifest.py machines_inc.
|
| The stubs are ANALOG BD's registration (modules/analog-bassdrum/machine.s,
| repeat98) as DRUMMER carried it, for rows 5 .. MC_END-1; the list's drawer
| and row box are HOOKS' machine_rows forms (sambanks), which scroll.
        .text
        .include "remix.inc"
        .global mc_machine_name, mc_name_a, mc_name_b
        .global mc_setup_row, mc_chooser_box, mc_chooser_name
        .global mc_setup_open, mc_chooser_open, mc_setup_edit6, mc_setup_draw6
        .global mc_main_commit, mc_src_commit, mc_src_commit2
        .global mc_validate_entry, mc_stock_validate, mc_tick, mc_resolve_pb
        .global mc_lfo_pb, mc_setup_key, mc_row_type

        .equ    ROW0, 5
        .equ    MC_SLOT_BIT, 8              | mc_flags: the client plays the base's slot
        .equ    SRC_CURSOR, 0x460d5c30
        .equ    SRC_FOCUS, 0x460d1a48       | 0 the machine list, 1 a slot list
        .equ    KEY_RIGHT, 0x21
        .equ    KEY_LEFT, 0x34
        .equ    PART_OFF, 0x8ed80
        .equ    PB_TABLE, 0x400d5f38
        .equ    MC_LIST, 0x460e7386         | the list: +0 top row, +8 cursor, +16 rows

| Branches to `out` unless the row in `reg` is a client's (5 .. MC_END-1).
        .macro  mc_if_client reg, out
        cmpi.l  #ROW0,\reg
        bcs     \out
        cmpi.l  #MC_END,\reg
        bcc     \out
        .endm

| d0 = a stored machine type, a0 = its byte in the Part -> d0 = the row.
| Keeps every register but d0.
mc_row_type:
        lea     -20(%sp),%sp
        movem.l %d1/%a0-%a1,8(%sp)
        move.l  %d0,(%sp)
        move.l  %a0,4(%sp)
        jsr     mc_type
        movem.l 8(%sp),%d1/%a0-%a1
        lea     20(%sp),%sp
        rts

| d0 = a client's row -> d0 = its mc_flags word. Keeps every register but d0.
mc_row_flags:
        move.l  %a0,-(%sp)
        lea     mc_flags-4*ROW0,%a0
        move.l  (%a0,%d0.l*4),%d0
        movea.l (%sp)+,%a0
        rts

| 0x400334d8, the name of row 4(sp): a client's name, else stock's formatter.
mc_machine_name:
        move.l  4(%sp),%d0
        mc_if_client %d0, 1f
        lea     mc_src_names,%a0
        move.l  (%a0,%d0.l*4),%d0
        movea.l %d0,%a0
        rts
1:      move.l  %d2,-(%sp)
        move.l  8(%sp),%d1
        jmp     (0x400334de).l

| 0x4003d718 / 0x4004c36a, d0 a stored type, a0 its byte: d1 = the name.
mc_name_a:
        bsr.s   mc_name_pick
        jmp     (0x4003d722).l
mc_name_b:
        bsr.s   mc_name_pick
        jmp     (0x4004c374).l
mc_name_pick:
        bsr     mc_row_type
        lea     mc_src_names,%a0
        move.l  (%a0,%d0.l*4),%d1
        rts

| 0x4003c980, SRC SETUP's highlighted row.
mc_setup_row:
        mvs.b   (%a0),%d0
        lea     24(%sp),%sp
        bsr     mc_row_type
        jmp     (0x4003c986).l

| 0x40078678, the list's drawer: the name of row top + d2 on screen row d2,
| none past the last row.
mc_chooser_name:
        move.l  (MC_LIST).l,%d0
        add.l   %d2,%d0
        cmp.l   (MC_LIST+16).l,%d0
        bge.s   1f
        move.l  %d0,-(%sp)
        movea.l %d3,%a0
        jsr     (%a0)
        move.l  %d0,-(%sp)
        moveq   #-1,%d1
        move.l  %d1,-(%sp)
        pea     1(%a2)
        pea     0x5.w
        move.l  %d4,-(%sp)
        pea     (0x400ba876).l
        movea.l %d7,%a1
        jsr     (%a1)
        lea     28(%sp),%sp
1:      jmp     (0x400786a2).l

| 0x400786c8, a0 the UI track's machine byte: the box on screen row d2 when
| the track's row is top + d2.
mc_chooser_box:
        mvs.b   (%a0),%d0
        bsr     mc_row_type
        move.l  (MC_LIST).l,%d1
        add.l   %d2,%d1
        cmp.l   %d1,%d0
        bne.s   1f
        cmp.l   (MC_LIST+16).l,%d1
        bge.s   1f
        jmp     (0x400786d4).l
1:      jmp     (0x400786fc).l

| 0x400585dc, SRC SETUP opens on the track's row; a pick is over.
mc_setup_open:
        clr.b   mc_pick
        move.b  (%a0),%d3
        move.l  %d0,-(%sp)
        mvs.b   %d3,%d0
        bsr     mc_row_type
        move.l  %d0,%d3
        move.l  (%sp)+,%d0
        mvs.b   %d3,%d4
        pea     (0x400bb704).l
        jmp     (0x400585e6).l

| 0x40078886, the list opens on the track's row.
mc_chooser_open:
        mvs.b   (%a0),%d0
        bsr     mc_row_type
        move.l  %d0,-(%sp)
        pea     (0x460e7386).l
        jmp     (0x40078890).l

| 0x4003a52e, SETUP's editor, d2 the row: a client's row edits its base's
| bytes. A client without the base's slot leaves the slot unedited (a3 = 0:
| the slot field).
mc_setup_edit6:
        mc_if_client %d2, 2f
        move.l  %d2,%d0
        bsr     mc_row_flags
        btst    #MC_SLOT_BIT,%d0
        bne.s   1f
        move.l  %a3,-(%sp)
        tst.l   (%sp)+
        bne.s   1f
        jmp     (0x4003a624).l
1:      andi.l  #0xff,%d0
        move.l  %d0,%d2
2:      move.l  %d2,%d0
        lsl.l   #3,%d0
        add.l   %d2,%d2
        sub.l   %d2,%d0
        jmp     (0x4003a536).l

| 0x4003cd98, SETUP's drawer, d6 the row: a client's row draws its base's.
mc_setup_draw6:
        mc_if_client %d6, 1f
        move.l  %d0,-(%sp)
        move.l  %d6,%d0
        bsr     mc_row_flags
        andi.l  #0xff,%d0
        move.l  %d0,%d6
        move.l  (%sp)+,%d0
1:      move.l  %d6,%d7
        lsl.l   #3,%d7
        add.l   %d6,%d6
        sub.l   %d6,%d7
        jmp     (0x4003cda0).l

| 0x4007981c, the list's commit: a1 the bank, d0 part * size, d1 the track,
| d4 the row. mc_commit signs or unsigns and gives the machine to store.
mc_main_commit:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        movea.l %a1,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d4,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %a0,-(%sp)
        jsr     mc_commit
        lea     12(%sp),%sp
        move.l  %d0,%d4
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        .word   0x7710,0x1084,0xd081        | mvs.b (a0),d3 ; move.b d4,(a0) ; add.l d1,d0
        jmp     (0x40079822).l

| 0x4005a616 / 0x4005a850, SRC SETUP's commits: a1 the bank, d0 part * size,
| d2 the track -> d1 the machine to store. A pick commits its client's row.
mc_src_commit:
        pea     (0x4005a61c).l
        bra.s   mc_src_common
mc_src_commit2:
        pea     (0x4005a856).l
mc_src_common:
        move.l  (SRC_CURSOR).l,%d1
        tst.b   mc_pick
        beq.s   1f
        moveq   #0,%d1
        move.b  mc_pick,%d1
1:      lea     -12(%sp),%sp
        movem.l %d0/%a0-%a1,(%sp)
        movea.l %a1,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d1,-(%sp)
        move.l  %d2,-(%sp)
        move.l  %a0,-(%sp)
        jsr     mc_commit
        lea     12(%sp),%sp
        move.l  %d0,%d1
        movem.l (%sp),%d0/%a0-%a1
        lea     12(%sp),%sp
        rts

| 0x40002318, the Part validator (machines.c mc_validate), and stock's.
mc_validate_entry:
        jmp     mc_validate
mc_stock_validate:
        lea     -96(%sp),%sp
        movem.l %d2-%d7/%a2-%fp,(%sp)
        jmp     (0x40002320).l

| 0x4005221e, the UI tick: the clients' pages and ticks (mc_ui_tick).
mc_tick:
        jsr     0x4005213c
        jsr     0x4007e940
        jsr     mc_ui_tick
        jmp     0x40052228

| 0x40031e74, the PLAYBACK page resolver, d5 the stored type, a0 its byte:
| a client's track shows its client's page.
mc_resolve_pb:
        mvs.b   %d5,%d0
        bsr     mc_row_type
        mc_if_client %d0, 1f
        move.l  %a0,-(%sp)
        move.l  %d0,-(%sp)
        jsr     mc_page
        addq.l  #8,%sp
        jmp     (0x40031ed6).l
1:      lea     (PB_TABLE).l,%a0
        jmp     (0x40031ece).l

| 0x4003bff0, LFO SETUP's destination names, a0 the machine byte: a client's
| track names its client's knobs. d1 is read after (0x4003c086).
mc_lfo_pb:
        mvs.b   (%a0),%d0
        bsr     mc_row_type
        mc_if_client %d0, 1f
        move.l  %d1,-(%sp)
        move.l  %a0,-(%sp)
        move.l  %d0,-(%sp)
        jsr     mc_page
        addq.l  #8,%sp
        move.l  (%sp)+,%d1
        movea.l %d0,%a2
        jmp     (0x4003c058).l
1:      lea     (PB_TABLE).l,%a0
        jmp     (0x4003c054).l

| 0x4003d1c0, SRC SETUP's key handler, the key at 4(sp). RIGHT on the row of
| a client that plays its base's slot opens the base's slot list: the cursor
| is the base's while the list is open (stock's list, preview and commit read
| it), the commit signs the client (mc_src_common), and LEFT puts it back.
mc_setup_key:
        move.l  4(%sp),%d0
        tst.l   (SRC_FOCUS).l
        bne.s   .sk_list
        cmpi.l  #KEY_RIGHT,%d0
        bne.s   .sk_go
        move.l  (SRC_CURSOR).l,%d1
        mc_if_client %d1, .sk_go
        move.l  %d1,%d0
        bsr     mc_row_flags
        btst    #MC_SLOT_BIT,%d0
        beq.s   .sk_go
        move.b  %d1,mc_pick
        andi.l  #0xff,%d0
        move.l  %d0,(SRC_CURSOR).l
        jsr     mc_pick_page
        bra.s   .sk_go
.sk_list:
        cmpi.l  #KEY_LEFT,%d0
        bne.s   .sk_go
        tst.b   mc_pick
        beq.s   .sk_go
        moveq   #0,%d1
        move.b  mc_pick,%d1
        clr.b   mc_pick
        move.l  %d1,(SRC_CURSOR).l
        jsr     mc_pick_page
.sk_go:
        move.l  %d2,-(%sp)
        move.l  8(%sp),%d0
        move.l  (SRC_FOCUS).l,%d1
        jmp     (0x4003d1cc).l
        .balign 2
