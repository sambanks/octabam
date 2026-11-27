| VIBRATO -- FUNC + turn walks per-knob stops (26 Nov 2026).
|
| LOFI2's func_stops.s, with VIBRATO's tables: the same P+0x12a knob
| handlers (docs/firmware/PARAM_PAGES.md section 2), called by the stock
| knob path 0x40055008 as f(slot, detents, value) -> d0, which it clamps.
| One entry per knob, each naming its stop table and its encoder.
|
|   FUNC held (and PERSONALIZE's FUNCTION + ENCODER not disabled): each
|   detent moves to the next stop strictly above / below the current
|   value; past the last stop the value stays.
|   Otherwise: one unit a detent, x7 with the knob pushed (po_knob's form).
|
| Clobbers d0/d1/a0/a1 (C scratch); d2-d4 saved.

        .set    FUNC_HELD, 0x46c7dd26           | nonzero while [FUNCTION] is down
        .set    FUNC_ENC_OFF, 0x800000a0        | PERSONALIZE: DISABLE FUNCTION + ENCODER
        .set    KEY_HELD, 0x46c7d8de+0x10       | + code * 0x18: nonzero while held (PANEL.md)
        .set    PUSH_CODE, 0x38                 | encoder pushes: key codes 0x38..0x3d = A..F

        .text
        .globl  vb_knob_spd, vb_knob_dep, vb_knob_slew, vb_knob_wid, vb_knob_mix

| ---- entries: a0 = the stop table, d1 = the encoder (0..5 = A..F) ----------
vb_knob_spd:                                    | slot 0, A
        lea     vb_st_7(%pc),%a0
        moveq   #0,%d1
        bra.s   vb_kn_common
vb_knob_dep:                                    | slot 1, B
        lea     vb_st_dep(%pc),%a0
        moveq   #1,%d1
        bra.s   vb_kn_common
vb_knob_slew:                                   | slot 2, C
        lea     vb_st_q5(%pc),%a0
        moveq   #2,%d1
        bra.s   vb_kn_common
vb_knob_wid:                                    | slot 3, D
        lea     vb_st_7(%pc),%a0
        moveq   #3,%d1
        bra.s   vb_kn_common
vb_knob_mix:                                    | slot 5, F
        lea     vb_st_q5(%pc),%a0
        moveq   #5,%d1
|       fall through

| ---- vb_kn_common(a0 table, d1 encoder; args slot, detents, value) -> d0 ---
vb_kn_common:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        move.l  24(%sp),%d0                     | the raw value turned from
        move.l  20(%sp),%d2                     | detents, signed
        tst.l   FUNC_HELD
        beq.s   vb_kn_plain
        tst.l   FUNC_ENC_OFF
        bne.s   vb_kn_plain
        tst.l   %d2
        beq.s   vb_kn_out
        bmi.s   vb_kn_down
| up: the first stop above the value, once a detent
vb_kn_up:
        mvz.b   (%a0),%d3                       | the stop count
        lea     1(%a0),%a1                      | the stops, ascending
vb_kn_u1:
        mvz.b   (%a1)+,%d4
        cmp.l   %d0,%d4
        bgt.s   vb_kn_utake                     | stop > value
        subq.l  #1,%d3
        bne.s   vb_kn_u1
        bra.s   vb_kn_out                       | none above: stay
vb_kn_utake:
        move.l  %d4,%d0
        subq.l  #1,%d2
        bne.s   vb_kn_up
        bra.s   vb_kn_out
| down: the last stop below the value, once a detent
vb_kn_down:
        neg.l   %d2
vb_kn_dn:
        mvz.b   (%a0),%d3
        lea     1(%a0,%d3.l),%a1                | one past the last stop
vb_kn_d1:
        mvz.b   -(%a1),%d4
        cmp.l   %d0,%d4
        blt.s   vb_kn_dtake                     | stop < value
        subq.l  #1,%d3
        bne.s   vb_kn_d1
        bra.s   vb_kn_out                       | none below: stay
vb_kn_dtake:
        move.l  %d4,%d0
        subq.l  #1,%d2
        bne.s   vb_kn_dn
        bra.s   vb_kn_out
| plain: one unit a detent, x7 pushed
vb_kn_plain:
        move.l  %d1,%d3
        addi.l  #PUSH_CODE,%d3                  | the push switch's key code ...
        move.l  %d3,%a1
        add.l   %d3,%d3
        add.l   %a1,%d3                         | * 3 ...
        lsl.l   #3,%d3                          | * 8 = code * 0x18: its key record
        lea     KEY_HELD,%a1
        tst.l   (%a1,%d3.l)
        beq.s   vb_kn_one
        move.l  %d2,%d3                         | pushed: x7
        lsl.l   #3,%d2
        sub.l   %d3,%d2
vb_kn_one:
        add.l   %d2,%d0
vb_kn_out:
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| ---- stop tables: count, then the stops ascending -------------------------
vb_st_7:                                        | SPD octaves 0.25 0.5 1 2 4 8 15.5 Hz;
        .byte   7, 0, 21, 43, 64, 85, 107, 127  | WID 0 30 60 90 120 150 178.6 deg
vb_st_dep:                                      | DEP 0 1.2 4.9 9.9 25.4 50.2 75 100 cents
        .byte   8, 0, 14, 28, 40, 64, 90, 110, 127
vb_st_q5:                                       | SLEW, MIX: quarters
        .byte   5, 0, 32, 64, 96, 127
        .align  2
