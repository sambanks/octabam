| Recorder seam -- ColdFire code cave (7 Sep 2026, RTOS_FORK 10.17)
|
| Hooked from 0x40006e0c in the per-frame recorder function (0x400068e4),
| at the tail of the fixed-RLEN length converter: the three displaced
| instructions turn the EMAC product into the length (round half up) and
| are replayed first. The stock length is round(RLEN x 15,876,000 / tempo24)
| through a truncated reciprocal, while the sequencer fires each trig at
| floor(event) of an EXACT fractional event, so on a looping recorder trig
| the spacing between arms alternates between floor and ceil of the period
| and the recording is one sample short or long once every 1/eps passes --
| the click Bryan hears at 128 BPM / RLEN 4 (RTOS_FORK 10.16.4-5).
|
| This cave recomputes the length every call from the sequencer's own next
| step event, exactly as the frame builder will quantise it:
|     s_next = 0x46104cf8 + 16 + floor((lane[track] - 0x46104cf0) * r)
|              (dispatcher sample clock; r = -[0x80001820] = 2^31/tempo24,
|               the same macl the frame builder uses at 0x4000aefc)
|     L'     = s_next - arm sample (0x46c7fa84[track], written at the arm)
| and uses L' only when it is within one sample of the stock length, so a
| recording whose next step is not its re-trig keeps its RLEN. The lane
| holds the NEXT STEP, which is the re-trig's step exactly when it matters:
| the end test runs one frame ahead of the arm.
| MACSR is fractional here (the converter's own macl just ran). acc0 free.
| Position-independent: no reference to itself.

        .text
cave:
        move.l  %d0,%d4                 | displaced: product
        addq.l  #1,%d4                  | displaced
        asr.l   #1,%d4                  | displaced: L = round half up
        lea     -20(%sp),%sp
        movem.l %d0-%d3/%a0,(%sp)       | 20 bytes; the caller's frame is now +24
        move.l  160(%sp),%d3            | track: caller's sp(136) + 4 (return) + 20 (saved)
        move.l  %d3,%d0
        lsl.l   #2,%d0
        lea     0x80001904,%a0
        move.l  (%a0,%d0.l),%d0         | lane[track] = next step event, samples x tempo24
        sub.l   0x46104cf0,%d0          | - lookahead
        move.l  0x80001820,%d1
        neg.l   %d1                     | 2^31 / tempo24
        macl    %d0,%d1,%acc0
        movclr.l %acc0,%d0              | n = floor((event - look) / tempo24)
        add.l   0x46104cf8,%d0
        addq.l  #8,%d0
        addq.l  #8,%d0                  | s_next = cf8 + 16 + n
        move.l  %d3,%d1
        lsl.l   #2,%d1
        lea     0x46c7fa84,%a0
        sub.l   (%a0,%d1.l),%d0         | L' = s_next - arm sample
        move.l  %d0,%d1
        sub.l   %d4,%d1                 | L' - L
        addq.l  #1,%d1                  | 0..2 <=> within one sample
        cmpi.l  #2,%d1
        bhi.s   keep
        move.l  %d0,%d4
keep:   movem.l (%sp),%d0-%d3/%a0
        lea     20(%sp),%sp
        rts
