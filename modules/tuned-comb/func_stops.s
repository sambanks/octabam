| TUNED COMB -- FUNC + turn walks per-knob stops (26 Nov 2026).
|
| LOFI2's func_stops.s (#1271) and VIBRATO's (#1285), with TUNED COMB's
| tables: P+0x12a knob handlers (docs/firmware/PARAM_PAGES.md section 2),
| called by the stock knob path 0x40055008 as f(slot, detents, value) -> d0,
| which it clamps. One entry per knob, each naming its stop table and its
| encoder; PTCH walks octaves instead of a table.
|
|   FUNC held (and PERSONALIZE's FUNCTION + ENCODER not disabled): each
|   detent moves to the next stop strictly above / below the current
|   value; past the last stop the value stays. PTCH moves 12 (an octave,
|   the note's name kept) a detent, and stays where the octave would leave
|   A#0 .. A8.
|   Otherwise: one unit a detent, x7 with the knob pushed (po_knob's form).
|
| Clobbers d0/d1/a0/a1 (C scratch); d2-d4 saved.

        .set    FUNC_HELD, 0x46c7dd26           | nonzero while [FUNCTION] is down
        .set    FUNC_ENC_OFF, 0x800000a0        | PERSONALIZE: DISABLE FUNCTION + ENCODER
        .set    KEY_HELD, 0x46c7d8de+0x10       | + code * 0x18: nonzero while held (PANEL.md)
        .set    PUSH_CODE, 0x38                 | encoder pushes: key codes 0x38..0x3d = A..F
        .set    PTCH_TOP, 95                    | A8, PTCH's last value (count 96)

        .text
        .globl  tc_knob_ptch, tc_knob_fine, tc_knob_lp, tc_knob_fb, tc_knob_mix

| ---- entries: a0 = the stop table, d1 = the encoder (0..5 = A..F) ----------
tc_knob_fine:                                   | slot 1, B
        lea     tc_st_q5(%pc),%a0
        moveq   #1,%d1
        bra.s   tc_kn_common
tc_knob_lp:                                     | slot 2, C
        lea     tc_st_lp(%pc),%a0
        moveq   #2,%d1
        bra.s   tc_kn_common
tc_knob_fb:                                     | slot 3, D
        lea     tc_st_fb(%pc),%a0
        moveq   #3,%d1
        bra.s   tc_kn_common
tc_knob_mix:                                    | slot 5, F
        lea     tc_st_q5(%pc),%a0
        moveq   #5,%d1
|       fall through

| ---- tc_kn_common(a0 table, d1 encoder; args slot, detents, value) -> d0 ---
tc_kn_common:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        move.l  24(%sp),%d0                     | the raw value turned from
        move.l  20(%sp),%d2                     | detents, signed
        tst.l   FUNC_HELD
        beq.s   tc_kn_plain
        tst.l   FUNC_ENC_OFF
        bne.s   tc_kn_plain
        tst.l   %d2
        beq.s   tc_kn_out
        bmi.s   tc_kn_down
| up: the first stop above the value, once a detent
tc_kn_up:
        mvz.b   (%a0),%d3                       | the stop count
        lea     1(%a0),%a1                      | the stops, ascending
tc_kn_u1:
        mvz.b   (%a1)+,%d4
        cmp.l   %d0,%d4
        bgt.s   tc_kn_utake                     | stop > value
        subq.l  #1,%d3
        bne.s   tc_kn_u1
        bra.s   tc_kn_out                       | none above: stay
tc_kn_utake:
        move.l  %d4,%d0
        subq.l  #1,%d2
        bne.s   tc_kn_up
        bra.s   tc_kn_out
| down: the last stop below the value, once a detent
tc_kn_down:
        neg.l   %d2
tc_kn_dn:
        mvz.b   (%a0),%d3
        lea     1(%a0,%d3.l),%a1                | one past the last stop
tc_kn_d1:
        mvz.b   -(%a1),%d4
        cmp.l   %d0,%d4
        blt.s   tc_kn_dtake                     | stop < value
        subq.l  #1,%d3
        bne.s   tc_kn_d1
        bra.s   tc_kn_out                       | none below: stay
tc_kn_dtake:
        move.l  %d4,%d0
        subq.l  #1,%d2
        bne.s   tc_kn_dn
        bra.s   tc_kn_out
| plain: one unit a detent, x7 pushed
tc_kn_plain:
        move.l  %d1,%d3
        addi.l  #PUSH_CODE,%d3                  | the push switch's key code ...
        move.l  %d3,%a1
        add.l   %d3,%d3
        add.l   %a1,%d3                         | * 3 ...
        lsl.l   #3,%d3                          | * 8 = code * 0x18: its key record
        lea     KEY_HELD,%a1
        tst.l   (%a1,%d3.l)
        beq.s   tc_kn_one
        move.l  %d2,%d3                         | pushed: x7
        lsl.l   #3,%d2
        sub.l   %d3,%d2
tc_kn_one:
        add.l   %d2,%d0
tc_kn_out:
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| ---- PTCH: FUNC walks octaves ------------------------------------------------
tc_knob_ptch:                                   | slot 0, A
        moveq   #0,%d1
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        move.l  24(%sp),%d0
        move.l  20(%sp),%d2
        tst.l   FUNC_HELD
        beq.s   tc_kn_plain
        tst.l   FUNC_ENC_OFF
        bne.s   tc_kn_plain
        tst.l   %d2
        beq.s   tc_kn_out
        bmi.s   tc_oc_dn
tc_oc_up:
        moveq   #12,%d3
        add.l   %d0,%d3
        moveq   #PTCH_TOP,%d4
        cmp.l   %d4,%d3
        bgt.s   tc_kn_out                       | an octave up would pass A8: stay
        move.l  %d3,%d0
        subq.l  #1,%d2
        bne.s   tc_oc_up
        bra.s   tc_kn_out
tc_oc_dn:
        moveq   #-12,%d3
        add.l   %d0,%d3
        bmi.s   tc_kn_out                       | an octave down would pass A#0: stay
        move.l  %d3,%d0
        addq.l  #1,%d2
        bne.s   tc_oc_dn
        bra.s   tc_kn_out

| ---- stop tables: count, then the stops ascending -------------------------
tc_st_q5:                                       | FINE -100 -50 0 +50 +98 cents; MIX quarters
        .byte   5, 0, 32, 64, 96, 127
tc_st_lp:                                       | LP 81 Hz, 125, 250, 500, 1k, 2k, 4k, 8k, open
        .byte   9, 0, 10, 26, 42, 58, 74, 90, 106, 127
tc_st_fb:                                       | FB T60 30 10 5 2 1 0.5 s, none, 0.5 1 2 5 10 30 s
        .byte   13, 0, 12, 19, 28, 34, 41, 64, 87, 94, 100, 109, 116, 127
        .align  2
