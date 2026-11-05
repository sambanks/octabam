| SLOW LFO -- MULT 1/2X, 1/4X and 1/8X on the audio and MIDI tracks' LFOs.
|
| MULT is stored as a shift count, 0..6 (1X..64X): the LFO engine adds
| SPD x tempo to a phase accumulator each pass, counts the accumulator's
| wraps (modulus 496125) and shifts that count left by MULT. Values 7, 8
| and 9 are new: the engine's step (SPD x tempo) is shifted right by 1, 2
| or 3 before it is accumulated, and the left shift is 0. So 1/2X runs at
| half of 1X, still from the project tempo. The audio engine (0x4000cfa8)
| and the MIDI engine (0x40003c0e) are the same code; both get both hooks.
| The two pages' MULT counts go 7 -> 10 (manifest pokes) and the shared
| formatter prints the three new labels.
|
| In every engine hook a2 is the LFO record, d2 the LFO index, so the MULT
| byte is 0x24(a2, d2.l), as stock reads it.

        .text
        .global sl_rate_audio, sl_mult_audio, sl_rate_midi, sl_mult_midi, sl_format

        .equ    SPRINTF, 0x40013a08

| The engine's rate step, displaced: `mulsl %d3,%d6` (d6 = SPD x tempo) and
| `movel #8657,%d0` (the reciprocal the next macl uses). d0 is free until
| that load, which is replayed last.
.macro  RATE back
        muls.l  %d3,%d6
        mvz.b   (0x24,%a2,%d2.l),%d0
        subq.l  #7,%d0
        bmi.s   1f                      | MULT 0..6: stock
        addq.l  #1,%d0
        asr.l   %d0,%d6                 | 7, 8, 9: step / 2, / 4, / 8
1:      move.l  #8657,%d0
        jmp     (\back).l
.endm

| The engine's MULT load, displaced: `mvzb 0x24(a2,d2.l),%d4` and
| `cmpl %d3,%d6` (its flags reach the stock `blts`). d0 is live here (the
| wrap count), so only d4 is touched.
.macro  MULT back
        mvz.b   (0x24,%a2,%d2.l),%d4
        cmpi.l  #6,%d4
        bls.s   1f
        moveq   #0,%d4                  | 7, 8, 9: no left shift
1:      cmp.l   %d3,%d6
        jmp     (\back).l
.endm

sl_rate_audio:  RATE 0x4000cfba
sl_mult_audio:  MULT 0x4000cfdc
sl_rate_midi:   RATE 0x40003c20
sl_mult_midi:   MULT 0x40003c42

| The MULT formatter (0x4003bda4, both pages): `f(char *out, int value)`
| writes sprintf(out, "%dX", 1 << value). Values 7, 8, 9 write their own
| label; every other value replays the two displaced instructions.
sl_format:
        move.l  8(%sp),%d1
        moveq   #7,%d0
        cmp.l   %d0,%d1
        blt.s   .Lstock
        moveq   #9,%d0
        cmp.l   %d0,%d1
        bgt.s   .Lstock
        subq.l  #7,%d1
        lea     (sl_labels).l,%a0
        move.l  (%a0,%d1.l*4),-(%sp)
        move.l  8(%sp),-(%sp)           | out (4(sp) before the push)
        jsr     (SPRINTF).l
        addq.l  #8,%sp
        rts
.Lstock:
        move.l  8(%sp),%d1
        move.l  %d1,%d0
        jmp     (0x4003bdaa).l

        .balign 4
sl_labels:
        .long   sl_half, sl_quarter, sl_eighth
sl_half:
        .asciz  "1/2X"
sl_quarter:
        .asciz  "1/4X"
sl_eighth:
        .asciz  "1/8X"
        .balign 2
