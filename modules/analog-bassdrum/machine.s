| ANALOG BD's own seams beside its machine row. The row itself -- the list,
| SRC SETUP, the signature, the validator -- is MACHINES's (modules/machines,
| docs/specs/MACHINES.md): ANALOG BD is a client, with its page (control.c
| ab_mc_page) and its defaults (engine.c ab_mc_defaults). Here: the engine
| pool (808/909) that the track's double-tap and the list's RIGHT open.
        .text
| Stock track double-tap enters the sample-slot window at 400791e4.
| AB opens the stock scrolling engine list. Save the
| caller's volatile registers before asking the signature predicate.
        .global ab_pool_open
ab_pool_open:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     ab_selected_source
        tst.l   %d0
        bne.s   .pool_source
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        .global ab_stock_pool_open
ab_stock_pool_open:
        move.l  %a2,-(%sp)
        tst.l   (0x460e70e0).l
        jmp     (0x400791ec).l
.pool_source:
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        jmp     ab_engine_open

| Only the Analog BD browser replaces the generic list drawer.
        .global ab_list_draw
ab_list_draw:
        lea -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr ab_engine_draw
        tst.l %d0
        beq.s .list_stock
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 16(%sp),%sp
        rts
.list_stock:
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 16(%sp),%sp
        lea -24(%sp),%sp
        movem.l %d2-%d3/%a2-%a5,(%sp)
        jmp (0x4006d78c).l

| Stock machine headings offer the right-chevron only for STATIC/FLEX.
| Analog BD has a pool too, so use the same stock format for its row.
        .global ab_pool_title
ab_pool_title:
        moveq #1,%d6
        cmp.l ab_mc_row,%d0                | our row on the list (MACHINES)
        bne.s .title_stock
        lea -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr ab_selected_source
        tst.l %d0
        beq.s .title_unsigned
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 16(%sp),%sp
        bra.s .title_pool
.title_unsigned:
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 16(%sp),%sp
.title_stock:
        cmp.l %d0,%d6
        bcs.s .title_plain
.title_pool:
        jmp (0x40077b62).l
.title_plain:
        jmp (0x40077b70).l
