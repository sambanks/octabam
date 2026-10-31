| Granular source hooks; GNU as -mcpu=5475.
        .text
        .align  4
        .global gr_page, gr_pool_read

| The stock page resolver's table load (d0 = machine, a0 = table, d3 = track,
| d1 = part, a1 = bank) has already been asserted by the manifest.
gr_page:
        move.l  0(%a0,%d0.l*4),%d0
        move.l  %d3,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %a1,-(%sp)
        move.l  %d0,-(%sp)
        jsr     gr_resolve_page
        lea     16(%sp),%sp
        jmp     0x40031ed6

| Adapt the stock page-aware pool walker, which returns data in d0 and the
| contiguous frame count in d1, to the C out-parameter convention.
gr_pool_read:
        lea     -12(%sp),%sp
        movem.l %d2/%a2-%a3,(%sp)
        move.l  16(%sp),%d2
        move.l  20(%sp),%d0
        movea.l 24(%sp),%a2
        movea.l 28(%sp),%a3
        move.l  #1,-(%sp)
        move.l  %d0,-(%sp)
        move.l  %d2,-(%sp)
        jsr     0x4009499c
        lea     12(%sp),%sp
        move.l  %d0,(%a2)
        move.l  %d1,(%a3)
        movem.l (%sp),%d2/%a2-%a3
        lea     12(%sp),%sp
        rts
