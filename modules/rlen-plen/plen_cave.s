| RLEN PLEN -- a recorder length equal to one loop of the track's pattern.
| Raw 65 (past MAX) on the RLEN slot. Three entries in one cave:
|   cave   hooked at 0x40006da6 (the arm converter's RLEN read, replayed):
|          raw 65 computes L = len x ticks[scale] x 2,646,000 / tempo24
|          (round to nearest) and rejoins the fixed-RLEN path at 0x40006e18
|          with d4 = L; every other raw returns to stock.
|   screen hooked at 0x4002fb10 (the RECORDING SETUP drawer's push of the
|          stock RLEN formatter, replayed with `fmt` pushed instead).
|   fmt    fmt(buf, value): 65 -> "PLEN" (the stock string), else the stock
|          RLEN formatter 0x4002f224 (1..64, MAX).
| Pattern length and scale are read the way the sequencer's step function
| 0x4009da20 reads them: bank 0x800065bd, pattern 0x800065be, record
| 0x400eb034 + p x 0x8ed8 + b x 0x9b340 (scale at +0, length at -1, PER
| TRACK flag at +1); in PER TRACK mode the track record
| 0x400e21e0 + t x 0x91a + the same offset (length +0x50, scale +0x51).
| Ticks per step: the sequencer's table 0x400aba50 (3 4 6 8 12 24 48 for
| 2X .. 1/8X); one tick = 2,646,000 / tempo24 samples.
| Reads: 0x80001814, 0x800065bd/be, the pattern record, 164(%sp) (the track).
| Writes: d4 (the length) on the PLEN path only.
| Assemble: m68k-elf-as -mcpu=5475 -o plen.o plen_cave.s

        .text
        .globl  cave, screen, fmt
cave:
        mvs.b   2(%a4),%d0              | displaced: RLEN raw
        addq.l  #1,%d0                  | displaced
        cmpi.l  #66,%d0                 | raw 65 = PLEN?
        bne     done
        lea     -24(%sp),%sp
        movem.l %d0-%d3/%a0-%a1,(%sp)   | 24 bytes; the caller's frame is now +28

        move.l  0x80001814,%d1          | d1 = D = tempo24
        beq     keep                    | no tempo: stock (the MAX branch)
        mvs.b   0x800065be,%d0          | pattern
        move.l  #0x8ed8,%d2
        muls.l  %d2,%d0
        mvs.b   0x800065bd,%d2          | bank
        move.l  #0x9b340,%d3
        muls.l  %d3,%d2
        add.l   %d2,%d0                 | d0 = record offset
        lea     0x400eb034,%a0
        tst.b   1(%a0,%d0.l)            | PER TRACK?
        beq     patmode
        move.l  164(%sp),%d2            | track: caller's sp(136) + 4 (return) + 24 (saved)
        move.l  #0x91a,%d3
        muls.l  %d3,%d2
        add.l   %d0,%d2
        lea     0x400e21e0,%a0
        mvs.b   0x51(%a0,%d2.l),%d3     | track scale
        mvs.b   0x50(%a0,%d2.l),%d2     | track length
        bra     have
patmode:
        mvs.b   0(%a0,%d0.l),%d3        | pattern scale
        mvs.b   -1(%a0,%d0.l),%d2       | pattern length
have:
        bge     sc0
        clr.l   %d3
sc0:    cmpi.l  #6,%d3
        ble     sc1
        moveq   #6,%d3
sc1:    cmpi.l  #2,%d2
        bge     ln0
        moveq   #2,%d2
ln0:    cmpi.l  #64,%d2
        ble     ln1
        moveq   #64,%d2
ln1:    lea     0x400aba50,%a0
        move.l  (%a0,%d3.l*4),%d3       | ticks per step
        muls.l  %d3,%d2                 | d2 = T = ticks per loop (<= 3072)

        move.l  #2646000,%d0            | samples per tick x tempo24
        move.l  %d0,%d3
        divu.l  %d1,%d0                 | d0 = q
        move.l  %d0,%a1                 | a1 = q
        mulu.l  %d1,%d0
        sub.l   %d0,%d3                 | d3 = r
        move.l  %d2,%d0
        mulu.l  %d3,%d0                 | T x r  (< 3072 x 7200)
        move.l  %d1,%d3
        lsr.l   #1,%d3
        add.l   %d3,%d0                 | + D/2
        divu.l  %d1,%d0                 | floor((T r + D/2) / D)
        move.l  %a1,%d4
        mulu.l  %d2,%d4                 | T x q
        add.l   %d0,%d4                 | d4 = L

        movem.l (%sp),%d0-%d3/%a0-%a1
        lea     24(%sp),%sp
        addq.l  #4,%sp                  | drop the return address
        jmp     0x40006e18              | rejoin: d4 = L, as after the stock conversion
keep:
        movem.l (%sp),%d0-%d3/%a0-%a1
        lea     24(%sp),%sp
done:
        rts

screen:
        move.l  (%sp)+,%d0              | return address (d0 is dead at the site)
        move.l  %d4,-(%sp)              | displaced
        pea     fmt                     | in place of the stock formatter
        move.l  %d0,-(%sp)
        rts

fmt:
        move.l  8(%sp),%d0              | value
        cmpi.l  #65,%d0
        bne     stock
        move.l  #0x400b541c,%d0         | "PLEN"
        move.l  %d0,8(%sp)
        jmp     0x40013a08              | sprintf(buf, "PLEN")
stock:
        jmp     0x4002f224
