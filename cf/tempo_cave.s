| BongDelay tempo publish -- ColdFire code cave (24 Aug 2026)
|
| Hooked from 0x40004d40 in the per-frame voice-record writer (0x40004bd2),
| which is the routine that publishes the FX ids into the record the DSP
| receives at x:$208 (one 16-bit halfword -> one 24-bit word, <<8).
| The three displaced instructions are replayed first; then, for a track
| whose FX2 id is one of OUR servers (6 = DELAY, 7 = REVERB), two dead
| halfwords of the record (r6+$6, r6+$7 for FX2) get:
|     +0x24  tempo24            = BPM*24, straight from 0x8000181c
|     +0x26  ticks (Q12.4)      = 42,336,000 / tempo24
|                                = samples per MIDI clock (1/24 beat) * 16
| 0x8000181c is the per-frame tempo latch, clamped 720..7200 by every
| writer, and the frame builder already divides by it unguarded.
| a0 = 0x80000110 + track (id array base), a2 = this track's record.
| Clobbers nothing: d0/d1 are saved.

        .text
cave:
        move.b  0xdbc(%a0),%d2          | displaced: FX2 id
        ext.w   %d2                     | displaced
        move.w  %d2,0x38(%a2)           | displaced: -> record +0x38 (x:$208+$1c)
        move.l  %d0,-(%sp)
        move.l  %d2,%d0
        subq.l  #6,%d0
        cmpi.l  #1,%d0                  | id 6 or 7 -> 0 or 1
        bhi.s   skip
        move.l  %d1,-(%sp)
        move.l  0x8000181c,%d0          | tempo24
        beq.s   nodiv                   | 0 before the first frame-builder
                                        | pass latches it: divu.l by zero
                                        | TRAPS -> the R48 boot hang (B/C/D
                                        | lights on, silent). Publish nothing;
                                        | the DSP side treats 0 as "no sync".
        move.w  %d0,0x24(%a2)           | r6+$6
        move.l  #42336000,%d1
        divu.l  %d0,%d1                 | ticks Q12.4
        move.w  %d1,0x26(%a2)           | r6+$7
nodiv:  move.l  (%sp)+,%d1
skip:   move.l  (%sp)+,%d0
        rts
