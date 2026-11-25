| LOFI2 -- FUNC + turn walks per-knob stops (25 Nov 2026).
|
| Each slot's knob handler is the descriptor word at P+0x12a + 4*slot
| (docs/firmware/PARAM_PAGES.md section 2; E+0x176 is slot 5's). The stock
| knob path 0x40055008 calls it as f(slot, detents, value) and clamps the
| return (d0) to [min, min+count-1]. cxosc's po_knob (modules/cxosc/poly.s)
| is the worked example this follows.
|
| One entry per knob, so the handler never depends on the slot number the
| caller passes (page-2 numbering unconfirmed): each entry names its stop
| table and its encoder (for the push test) and joins lf_kn_common.
|
|   FUNC held (and PERSONALIZE's FUNCTION + ENCODER not disabled): each
|   detent moves to the next stop strictly above / below the current
|   value; past the last stop the value stays.
|   Otherwise: one unit a detent, x7 with the knob pushed (po_knob's form).
|
| Clobbers d0/d1/a0/a1 (C scratch); d2-d4 saved. ColdFire: no movem
| predecrement, so the frame is lea + movem as po_knob does.

        .set    FUNC_HELD, 0x46c7dd26           | nonzero while [FUNCTION] is down
        .set    FUNC_ENC_OFF, 0x800000a0        | PERSONALIZE: DISABLE FUNCTION + ENCODER
        .set    KEY_HELD, 0x46c7d8de+0x10       | + code * 0x18: nonzero while held (PANEL.md)
        .set    PUSH_CODE, 0x38                 | encoder pushes: key codes 0x38..0x3d = A..F

        .text
        .globl  lf_knob_freq, lf_knob_mix, lf_knob_fdbk
        .globl  lf_knob_srr, lf_knob_brr, lf_knob_lpf, lf_knob_amph

| ---- entries: a0 = the stop table, d1 = the encoder (0..5 = A..F) ----------
lf_knob_freq:                                   | slot 0, A (octaves for now; RING HIGH's
        lea     lf_st_oct(%pc),%a0              | C table waits on reading MODE/RANGE)
        moveq   #0,%d1
        bra.s   lf_kn_common
lf_knob_mix:                                    | slot 1, B
        lea     lf_st_q5(%pc),%a0
        moveq   #1,%d1
        bra.s   lf_kn_common
lf_knob_fdbk:                                   | slot 2, C (FDBK / GAIN)
        lea     lf_st_q5(%pc),%a0
        moveq   #2,%d1
        bra.s   lf_kn_common
lf_knob_srr:                                    | slot 3, D
        lea     lf_st_srr(%pc),%a0
        moveq   #3,%d1
        bra.s   lf_kn_common
lf_knob_brr:                                    | slot 4, E
        lea     lf_st_brr(%pc),%a0
        moveq   #4,%d1
        bra.s   lf_kn_common
lf_knob_lpf:                                    | slot 5, F
        lea     lf_st_lpf(%pc),%a0
        moveq   #5,%d1
        bra.s   lf_kn_common
lf_knob_amph:                                   | slot 10, page 2: encoder E
        lea     lf_st_q5(%pc),%a0
        moveq   #4,%d1
|       fall through

| ---- lf_kn_common(a0 table, d1 encoder; args slot, detents, value) -> d0 ---
lf_kn_common:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        move.l  24(%sp),%d0                     | the raw value turned from
        move.l  20(%sp),%d2                     | detents, signed
        tst.l   FUNC_HELD
        beq.s   lf_kn_plain
        tst.l   FUNC_ENC_OFF
        bne.s   lf_kn_plain
        tst.l   %d2
        beq.s   lf_kn_out
        bmi.s   lf_kn_down
| up: the first stop above the value, once a detent
lf_kn_up:
        mvz.b   (%a0),%d3                       | the stop count
        lea     1(%a0),%a1                      | the stops, ascending
lf_kn_u1:
        mvz.b   (%a1)+,%d4
        cmp.l   %d0,%d4
        bgt.s   lf_kn_utake                     | stop > value
        subq.l  #1,%d3
        bne.s   lf_kn_u1
        bra.s   lf_kn_out                       | none above: stay
lf_kn_utake:
        move.l  %d4,%d0
        subq.l  #1,%d2
        bne.s   lf_kn_up
        bra.s   lf_kn_out
| down: the last stop below the value, once a detent
lf_kn_down:
        neg.l   %d2
lf_kn_dn:
        mvz.b   (%a0),%d3
        lea     1(%a0,%d3.l),%a1                | one past the last stop
lf_kn_d1:
        mvz.b   -(%a1),%d4
        cmp.l   %d0,%d4
        blt.s   lf_kn_dtake                     | stop < value
        subq.l  #1,%d3
        bne.s   lf_kn_d1
        bra.s   lf_kn_out                       | none below: stay
lf_kn_dtake:
        move.l  %d4,%d0
        subq.l  #1,%d2
        bne.s   lf_kn_dn
        bra.s   lf_kn_out
| plain: one unit a detent, x7 pushed
lf_kn_plain:
        move.l  %d1,%d3
        addi.l  #PUSH_CODE,%d3                  | the push switch's key code ...
        move.l  %d3,%a1
        add.l   %d3,%d3
        add.l   %a1,%d3                         | * 3 ...
        lsl.l   #3,%d3                          | * 8 = code * 0x18: its key record
        lea     KEY_HELD,%a1
        tst.l   (%a1,%d3.l)
        beq.s   lf_kn_one
        move.l  %d2,%d3                         | pushed: x7
        lsl.l   #3,%d2
        sub.l   %d3,%d2
lf_kn_one:
        add.l   %d2,%d0
lf_kn_out:
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| ---- stop tables: count, then the stops ascending -------------------------
lf_st_q5:                                       | MIX, FDBK/GAIN (0 +3 +6 +9 +11.9 dB), AMPH (-90 -45 0 +45 +88.6)
        .byte   5, 0, 32, 64, 96, 127
lf_st_srr:                                      | off 22.05k 16k 11.025k 8k 5.5125k 4k min
        .byte   8, 0, 22, 32, 47, 64, 89, 116, 127
lf_st_brr:                                      | 24 16 12 10 8 6 4 bits, max
        .byte   8, 0, 36, 56, 67, 80, 96, 116, 127
lf_st_lpf:                                      | 100 250 500 1k 2k 4k 8k Hz, off
        .byte   8, 0, 23, 40, 57, 74, 92, 109, 127
lf_st_oct:                                      | FREQ octaves (RING LOW, SHIFT)
        .byte   7, 0, 21, 43, 64, 85, 107, 127
lf_st_c:                                        | FREQ RING HIGH: floor, C2..C7, top (not yet used)
        .byte   8, 0, 3, 24, 45, 67, 88, 109, 127
        .align  2
