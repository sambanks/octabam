| CF PROBE -- ColdFire headroom probe: how much of the audio frame is spent
| in the per-frame delay routine, and how much more it can carry (4 Sep 2026)
|
| ONE CAVE, TWO ENTRY POINTS.
|   +0x000  probe   hooked from 0x40004b12, the frame routine's ONLY call
|                   site (a pc-relative jsr inside the audio interrupt, run
|                   at IPL 5 between `move.w #0x2500,%sr` and
|                   `move.w #0x2700,%sr`). The hook displaces the jsr AND the
|                   following move-to-SR (8 bytes); the cave calls the
|                   routine itself, times it, burns, then replays the SR
|                   write and returns to 0x40004b1a.
|   +0x100  fmt     a display formatter, registered on HELLO WORLD's GAIN
|                   (schema.FormatterReg offset=0x100). Same signature as
|                   every stock formatter: fmt(char *buf, int value).
|
| THE CLOCK is DMA timer 3, DTCN3 at 0xfc07c00c: the firmware programs
| DTMR3 = 0x000b at 0x400209c0 (bus clock, prescale 1, restart mode) and
| never writes DTRR3, whose reset value is 0xffffffff -- so it is a free
| running 32-bit counter at the internal bus clock, wrapping every 2^32
| ticks. Deltas are taken modulo 2^32. The firmware DOES zero DTCN3 itself
| on some event (`clr.l 0xfc07c00c` at 0x400559a8), and the guard below
| discards any frame whose period is implausible. DMA timer 2's reference
| of 132,000,000 ticks per second (0x40040438) says the bus clock is
| 132 MHz, which makes one 16-sample frame at 44.1 kHz 47,891 ticks -- the
| readout's PERIOD band is the check on that inference. Nothing in the
| arithmetic depends on it: every busy figure is a RATIO to the measured
| period.
|
| PER FRAME:
|     t0 = DTCN3 ; jsr 0x400031a0 ; t1 = DTCN3 ; burn ; t2 = DTCN3
|     routine = t1 - t0        total = t2 - t0        period = t0 - last_t0
|   discarded (not accumulated) when period > LIMIT (1,048,576 ticks, ~22
|   frames) or total > period: the first frame after boot, a counter reset
|   under us, a stalled frame. If EVERY frame is discarded the readout stays
|   "-", which is itself a finding: the hook is not running per frame.
|   Accumulated over a WINDOW of 1,024 frames (~0.37 s) then published to
|   a second block the formatter reads, so no sum can overflow 32 bits and
|   a reading is never half a window old.
|
| THE BURN is the crossfader: iterations = fader * 128, fader read from
| 0x460d16c8 (0..127; the panel and MIDI CC 48 both write it), six
| single-cycle-class instructions per iteration, so fader 127 is on the
| order of two frames of busy time. It is INSIDE the measurement (t2), so
| the readout reports the burn's true cost in ticks and the sweep is
| self-measuring: turn the fader up until something starves, read the
| percentage where it did. Fader 0 = no burn = a pure measurement.
|
| THE READOUT is HELLO WORLD's GAIN knob, banded by its value:
|     96..127  "t<pct>"   mean TOTAL busy (routine + burn) as % of the period
|     64..95   "r<pct>"   mean ROUTINE busy, burn excluded
|     32..63   "x<pct>"   worst single frame's total busy in the window
|      0..31   "<ticks>"  mean period in ticks (47891 expected at 132 MHz)
|   "-" until the first window has been published. The panel redraws a
|   label on a knob change, so nudge GAIN to refresh. (GAIN is also the
|   insert's gain: the bands below 96 attenuate that track. A probe image
|   is not a performance image.)
|
| Registers: the probe uses d0/d1/a0 (dead across the call it wraps: the
| routine clobbers them without reading them) and saves d2/d3. The formatter
| clobbers d0/d1/a0/a1 like every stock formatter and saves d2.
| Position-independent apart from the OS absolutes (pc-relative state).

        .text

| ---- +0x000: the hook target ------------------------------------------
probe:  move.l  %d2,-(%sp)
        move.l  %d3,-(%sp)
        move.l  0xfc07c00c,%d2          | t0
        jsr     0x400031a0              | the per-frame delay routine
        move.l  0xfc07c00c,%d3          | t1
        move.l  0x460d16c8,%d0          | crossfader 0..127
        and.l   #0x7f,%d0
        lsl.l   #7,%d0                  | iterations = fader * 128
        beq.s   noburn
burn:   addq.l  #1,%d1
        addq.l  #1,%d1
        addq.l  #1,%d1
        addq.l  #1,%d1
        subq.l  #1,%d0
        bne.s   burn
noburn: move.l  0xfc07c00c,%d1          | t2
        lea     st(%pc),%a0
        sub.l   %d2,%d3                 | routine = t1 - t0
        sub.l   %d2,%d1                 | total   = t2 - t0
        move.l  %d2,%d0
        sub.l   (%a0),%d0               | period  = t0 - last_t0
        move.l  %d2,(%a0)               | last_t0 = t0
        cmp.l   #0x100000,%d0           | LIMIT: ~22 frames (7.9 ms) -- room
        bhi.s   done                    | for the interrupt to turn out to run
                                        | per 256-sample DMA block rather than
                                        | per frame; unsigned, so a reset
                                        | (negative) fails it too. Sums stay
                                        | under 2^32 at 1,024 x LIMIT.
        cmp.l   %d0,%d1
        bhi.s   done                    | total > period: not a real frame
        add.l   %d3,4(%a0)              | sum_routine
        add.l   %d1,8(%a0)              | sum_total
        add.l   %d0,12(%a0)             | sum_period
        cmp.l   16(%a0),%d1
        bls.s   1f
        move.l  %d1,16(%a0)             | max_total
1:      addq.l  #1,20(%a0)              | n
        move.l  20(%a0),%d0
        cmp.l   #1024,%d0               | WINDOW
        bne.s   done
        move.l  4(%a0),24(%a0)          | publish the window ...
        move.l  8(%a0),28(%a0)
        move.l  12(%a0),32(%a0)
        move.l  16(%a0),36(%a0)
        move.l  20(%a0),40(%a0)
        clr.l   4(%a0)                  | ... and start the next
        clr.l   8(%a0)
        clr.l   12(%a0)
        clr.l   16(%a0)
        clr.l   20(%a0)
        addq.l  #1,44(%a0)              | windows published
done:   move.l  (%sp)+,%d3
        move.l  (%sp)+,%d2
        move.w  #0x2700,%sr             | displaced from 0x40004b16
        rts

| ---- +0x100: the formatter ------------------------------------------
        .org    0x100, 0
fmt:    move.l  %d2,-(%sp)              | buf 8(sp), value 12(sp)
        move.l  12(%sp),%d0
        lea     st(%pc),%a0
        move.l  40(%a0),%d2             | pub_n
        beq.s   none
        lsr.l   #5,%d0                  | band 0..3
        bne.s   band1
        move.l  32(%a0),%d1             | band 0: mean period = pub_period / pub_n
        divu.l  %d2,%d1
        lea     s_d(%pc),%a1
        bra.s   out
band1:  subq.l  #1,%d0
        bne.s   band2
        move.l  32(%a0),%d2             | band 1: max_total * 100 / mean period
        divu.l  40(%a0),%d2
        beq.s   none
        move.l  36(%a0),%d1
        moveq   #100,%d0
        mulu.l  %d0,%d1
        divu.l  %d2,%d1
        lea     s_x(%pc),%a1
        bra.s   out
band2:  move.l  32(%a0),%d2             | bands 2, 3: sum * 100 / sum_period,
        move.l  #100,%d1                | as sum / (sum_period / 100) so the
        divu.l  %d1,%d2                 | product cannot overflow
        beq.s   none
        subq.l  #1,%d0
        bne.s   band3
        move.l  24(%a0),%d1             | band 2: routine
        lea     s_r(%pc),%a1
        bra.s   div
band3:  move.l  28(%a0),%d1             | band 3: total
        lea     s_t(%pc),%a1
div:    divu.l  %d2,%d1
out:    move.l  (%sp)+,%d2              | buf back at 4(sp)
        move.l  %d1,-(%sp)              | value
        move.l  %a1,-(%sp)              | format
        move.l  12(%sp),-(%sp)          | buf
        jsr     0x40013a08              | sprintf(buf, format, value)
        lea     12(%sp),%sp
        rts
none:   move.l  (%sp)+,%d2
        pea     s_none(%pc)
        move.l  8(%sp),-(%sp)           | buf
        jsr     0x40013a08              | sprintf(buf, "-")
        addq.l  #8,%sp
        rts

s_t:    .asciz  "t%d"
s_r:    .asciz  "r%d"
s_x:    .asciz  "x%d"
s_d:    .asciz  "%d"
s_none: .asciz  "-"
        .balign 4
st:     .long   0                       | +0  last_t0
        .long   0, 0, 0, 0, 0           | +4  sum_routine, sum_total,
                                        |     sum_period, max_total, n
        .long   0, 0, 0, 0, 0           | +24 published copies of the five
        .long   0                       | +44 windows published
