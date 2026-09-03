| BusDelay TIME display formatter -- ColdFire code cave #2 (24 Aug 2026)
|
| Registered as TIME's P+0x0ca ("A") formatter with B = 0: stock DELAY
| TIME's own configuration (a plain dial that prints whatever A writes).
| Signature, shared by every stock formatter (docs/PARAM_PAGES.md section 7):
|     void fmt(char *buf, int value)      4(sp) = buf, 8(sp) = value
| Prints the division name ("1/8", "1/16T") while the DSP holds one, else
| the free time in ms. It replicates the DSP's STICKY SNAP rule with the
| same integers, so the two agree except at a tolerance edge:
|     free   = value*128 + 64                       (samples)
|     ticks  = 42,336,000 / tempo24                  (samples per MIDI clock, Q12.4)
|     d(M)   = ticks*M >> 4       for M in 2,3,4,6,8,9,12,16,18,24 clocks
|     held   = the LAST M with |d - free| < free/16; re-evaluated only when
|              value differs from the last draw -- a tempo change never
|              un-snaps, a knob move always re-evaluates. tempo 0 = free.
| State lives in this cave (the OS image runs from RAM). It is per PANEL,
| not per track: viewing another track's TIME re-evaluates, which is right.
| Clobbers d0/d1/a0/a1 like every stock formatter; saves the rest.
| Position-independent (pc-relative) apart from the two OS absolutes.

        .text
fmt:    lea     -20(%sp),%sp
        movem.l %d2-%d5/%a2,(%sp)       | 20 bytes: buf 24(sp), value 28(sp)
        move.l  28(%sp),%d0             | value 0..127
        lea     state(%pc),%a2
        move.l  %d0,%d1
        lsl.l   #7,%d1
        add.l   #64,%d1                 | free, samples
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
        cmp.l   #10,%d4
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

mtab:   .byte   2,3,4,6,8,9,12,16,18,24
        .balign 2
strtab: .word   s0-strtab,s1-strtab,s2-strtab,s3-strtab,s4-strtab
        .word   s5-strtab,s6-strtab,s7-strtab,s8-strtab,s9-strtab
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
        .balign 4
state:  .long   0xffffffff              | last value: none, so the first draw evaluates
        .long   0                       | held
