| BUS SCREEN draw handler (step 2) -- render twelve labelled rows.
|
| The menu engine calls a state's draw member as draw(window_handle): after
| the prologue below the handle is at sp@(44). We draw one string per row
| through the firmware's own text primitive, modelled byte-for-byte on state
| 2's draw (docs/MAINMENU.md 9e):
|
|   DRAW_STRING(context, window, x, y, flags, string)  @ 0x40012bd8
|   pushed FIRST..LAST = string, flags, y, x, window, context
|   so after the jsr: sp@(4)=context sp@(8)=window sp@(12)=x sp@(16)=y
|                     sp@(20)=flags sp@(24)=string  (the emulator reads x/y/string)
|
| context 0x400ba876 and flags 0xffffffff are the constants state 2 passes.
| LABELTAB (0x40bad000 here) is a placeholder the build patches to the cave's
| own pointer-table address -- the one self-reference, resolved in emit().
| Position-independent otherwise: OS absolutes and short branches only.

        .set    LABELTAB, 0x40bad000
        .set    DRAW_STRING, 0x40012bd8
        .set    CONTEXT, 0x400ba876
        .set    NROWS, 12

        .text
draw:   lea     %sp@(-40),%sp
        movem.l %d2-%d6/%a2-%a6,%sp@     | 10 regs -> sp@(44) is the arg
        moveal  %sp@(44),%a4             | the window handle
        tstl    %a4
        beq.s   ddone
        lea     LABELTAB,%a5             | -> the 12-entry pointer table
        moveq   #0,%d3                   | row index 0..11
dloop:  movel   %a5@(0,%d3:l:4),%d2      | d2 = label pointer for this row
        movel   %d3,%d4
        lsll    #3,%d4                   | d4 = row*8
        addql   #8,%d4                   | y = 8 + row*8
        movel   %d2,%sp@-                | string   -> sp@(24)
        pea     0xffffffff               | flags    -> sp@(20)
        movel   %d4,%sp@-                | y        -> sp@(16)
        pea     8                        | x = 8    -> sp@(12)
        movel   %a4,%sp@-                | window   -> sp@(8)
        pea     CONTEXT                  | context  -> sp@(4)
        jsr     DRAW_STRING
        lea     %sp@(24),%sp
        addql   #1,%d3
        moveq   #NROWS,%d0
        cmpl    %d3,%d0
        bgt.s   dloop
ddone:  movem.l %sp@,%d2-%d6/%a2-%a6
        lea     %sp@(40),%sp
        rts
