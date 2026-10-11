| SPECTRUM SHPE's display formatter (fmt(buf, value) -> sprintf), registered
| on page-2 slot 7: "LP" at 0, "BP" at 64, "HP" at 127, the number
| everywhere else. Display only: the stored and delivered value stays
| 0..127. In the modes whose MODE rename names the slot "---" (LADR, ISO,
| VOWL) it prints the number, as the plain knob did: slot 7's name is read
| from the clone (CLONE_SPECTRUM is the page descriptor P, a build export;
| the twelve 6-byte names sit at P+0x16, slot 7's at P+0x40).

        .text
        .globl  shpe_fmt
shpe_fmt:
fmt:    moveq   #0,%d1
        move.b  CLONE_SPECTRUM+0x40,%d1 | slot 7's name, first byte
        cmpi.l  #0x2d,%d1               | '-': a mode that hides SHPE
        beq.s   num
        move.l  8(%sp),%d1              | value 0..127
        lea     lp(%pc),%a0
        tst.l   %d1
        beq.s   print
        lea     bp(%pc),%a0
        cmpi.l  #64,%d1
        beq.s   print
        lea     hp(%pc),%a0
        cmpi.l  #127,%d1
        beq.s   print
num:    lea     0x400b465d,%a0          | "%d"
print:  move.l  8(%sp),-(%sp)           | value (a name has no conversion)
        move.l  %a0,-(%sp)              | the format
        move.l  12(%sp),-(%sp)          | buf
        jsr     0x40013a08              | sprintf(buf, format, value)
        lea     12(%sp),%sp
        rts
lp:     .asciz  "LP"
bp:     .asciz  "BP"
hp:     .asciz  "HP"
