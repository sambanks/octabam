| BROWSE PATH GUARD -- the sample browser's three path builders stop at the
| 260-byte buffers they write, instead of writing past them.
|
| The browser keeps three 260-byte path buffers at 0x460e48f0, 0x460e49f8
| and 0x460e4afc, then its current folder at 0x460e4c00. It fills them with
| an unbounded strcat (0x40013f94, twice, at 0x4006a59e / 0x4006a5b2) and an
| unbounded sprintf "%s/%s" (0x40013a08, at 0x4006a822 and 0x4006a89e). A
| file whose full path passes 259 characters wrote over the next buffer: at
| 0x4006a822 over the current folder, which then reads empty or garbage, and
| the browser stops opening until a power cycle.
| Each site loads the routine's address as a 4-byte operand; the manifest
| points those operands here. These keep at most 259 characters and the NUL.
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
