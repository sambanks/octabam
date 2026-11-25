| BROWSE PATH GUARD -- the sample browser's three path builders stop at the
| 260-byte buffers they write, instead of writing past them.
|
| The browser keeps three 260-byte path buffers at 0x460e48f0, 0x460e49f8
| and 0x460e4afc, then its current folder at 0x460e4c00. It fills them with
| an unbounded strcat and sprintf "%s/%s":
|
|   buffer      routine        loaded at (operand)       called at
|   0x460e48f0  strcat 13f94   lea 0x4006a598 (a59a)     jsr %a2@ 0x4006a59e, 0x4006a5b2
|   0x460e4afc  sprintf 13a08  lea 0x4006a7de (a7e0)     jsr %a4@ 0x4006a822
|   0x460e49f8  sprintf 13a08  jsr 0x4006a89e (a8a0)     the same jsr
|
| a2 and a4 are loaded once in their functions (0x4006a554..0x4006a5c6,
| 0x4006a79c..0x4006a8d8) and called only at the sites listed, so every
| call through the three operands writes one of the three buffers. A file
| whose full path passes 259 characters wrote over the next variable: the
| LOADING... flag 0x460e49f4 after the first buffer, the current folder after
| the third, and the browser stopped opening until a power cycle.
| The manifest points the three operands (the addresses in brackets) here. These keep at most 259 characters and the NUL.
| A path cut short names no file, so the row reads ERR, as stock shows for a
| path the filesystem refuses (259 characters is also its limit).
| SPDX-License-Identifier: MIT

        .equ    PATHMAX, 259                    | characters a 260-byte buffer holds

        .text
        .globl  bpg_cat, bpg_join

| bpg_cat(dst, src): strcat into a 260-byte buffer. Returns dst.
bpg_cat:
        movea.l 4(%sp),%a0                      | dst
        movea.l 8(%sp),%a1                      | src
        move.l  %a0,%d0
        moveq   #0,%d1                          | d1 = characters so far
1:      tst.b   (%a0)
        beq.s   2f
        addq.l  #1,%a0
        addq.l  #1,%d1
        bra.s   1b
2:      cmpi.l  #PATHMAX,%d1
        bcc.s   3f
        move.b  (%a1)+,(%a0)
        beq.s   4f
        addq.l  #1,%a0
        addq.l  #1,%d1
        bra.s   2b
3:      clr.b   (%a0)
4:      rts

| bpg_join(dst, fmt, a, b): sprintf(dst, "%s/%s", a, b) into a 260-byte
| buffer; fmt is "%s/%s" at both sites. Returns the characters written.
bpg_join:
        movea.l 4(%sp),%a0                      | dst
        movea.l 12(%sp),%a1                     | a
        moveq   #0,%d0
        bsr.s   9f
        cmpi.l  #PATHMAX,%d0
        bcc.s   8f
        move.b  #47,(%a0)+                      | '/'
        addq.l  #1,%d0
        movea.l 16(%sp),%a1                     | b
        bsr.s   9f
8:      clr.b   (%a0)
        rts
| copy a1 to a0 while d0 < PATHMAX; stops on the source's NUL (not copied)
9:      cmpi.l  #PATHMAX,%d0
        bcc.s   7f
        move.b  (%a1)+,%d1
        beq.s   7f
        move.b  %d1,(%a0)+
        addq.l  #1,%d0
        bra.s   9b
7:      rts
