| BusDelay TIME's display formatter (fmt(buf, value) -> sprintf). Prints the
| tempo division name while the DSP's sticky snap holds one (the same
| integers as the DSP rule: free = value*256 + 64 samples, ticks = 42,336,000
| / tempo24, snap when |free - ticks*M/16| <= free/16 for M in mtab), else
| milliseconds. Position-independent; `state` (last value, held division)
| lives inside the cave.

        .text
        .global time_fmt
time_fmt:
fmt:    lea     -20(%sp),%sp
        movem.l %d2-%d5/%a2,(%sp)       | 20 bytes: buf 24(sp), value 28(sp)
        move.l  28(%sp),%d0             | value 0..127
        lea     state(%pc),%a2
        move.l  %d0,%d1
        lsl.l   #8,%d1
        add.l   #64,%d1                 | free, samples (the DSP clamps at the line)
        cmp.l   (%a2),%d0
        beq.s   decide                  | knob unchanged: keep held
        move.l  %d0,(%a2)               | last = value
        clr.l   4(%a2)                  | held = 0
        move.l  0x80001814,%d2          | tempo24 (BPM*24)
        beq.s   decide                  | no tempo yet: free
        move.l  #42336000,%d3
        divu.l  %d2,%d3                 | ticks, Q12.4
        move.l  %d1,%d2
        lsr.l   #4,%d2                  | tol = free/16
        lea     mtab(%pc),%a0
        moveq   #0,%d4                  | index
loop:   moveq   #0,%d5
        move.b  (%a0)+,%d5              | M
        mulu.l  %d3,%d5
        lsr.l   #4,%d5                  | d = ticks*M
        sub.l   %d1,%d5
        bpl.s   1f
        neg.l   %d5                     | |d - free|
1:      cmp.l   %d2,%d5
        bcc.s   2f                      | err >= tol: no
        move.l  %d4,4(%a2)
        addq.l  #1,4(%a2)               | held = index + 1 (last match wins)
2:      addq.l  #1,%d4
        cmp.l   #12,%d4
        bne.s   loop
decide: move.l  4(%a2),%d0              | held, 0 = free
        beq.s   free
        lea     strtab(%pc),%a0
        move.w  -2(%a0,%d0.l*2),%d1     | offset of name held-1
        and.l   #0xffff,%d1
        adda.l  %d1,%a0
        move.l  %a0,28(%sp)             | value slot := the name
        movem.l (%sp),%d2-%d5/%a2
        lea     20(%sp),%sp
        jmp     0x40013a08              | sprintf(buf, name)
free:   moveq   #10,%d0
        mulu.l  %d0,%d1
        move.l  #441,%d0
        divu.l  %d0,%d1                 | ms = free*10/441
        move.l  %d1,28(%sp)
        movem.l (%sp),%d2-%d5/%a2
        lea     20(%sp),%sp
        move.l  8(%sp),-(%sp)           | ms
        pea     0x400b465d              | "%d"
        move.l  12(%sp),-(%sp)          | buf
        jsr     0x40013a08              | sprintf(buf, "%d", ms)
        lea     12(%sp),%sp
        rts

mtab:   .byte   2,3,4,6,8,9,12,16,18,24,32,36
        .balign 2
strtab: .word   s0-strtab,s1-strtab,s2-strtab,s3-strtab,s4-strtab
        .word   s5-strtab,s6-strtab,s7-strtab,s8-strtab,s9-strtab
        .word   s10-strtab,s11-strtab
s0:     .asciz  "1/32T"
s1:     .asciz  "1/32"
s2:     .asciz  "1/16T"
s3:     .asciz  "1/16"
s4:     .asciz  "1/8T"
s5:     .asciz  "1/16."
s6:     .asciz  "1/8"
s7:     .asciz  "1/4T"
s8:     .asciz  "1/8."
s9:     .asciz  "1/4"
s10:    .asciz  "1/2T"
s11:    .asciz  "1/4."
        .balign 4
state:  .long   0xffffffff              | last value: none, so the first draw evaluates
        .long   0                       | held
