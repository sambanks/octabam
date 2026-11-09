| CX OSC LFO destinations:
|   Stock 0..29: PLAYBACK / AMP / LFO / FX names via po_lfdname (Tim 2.10) so
|   a CX track lists PTCH RATO INDX FINE FOLD MIX, not Flex STRT/LEN/... .
|   PMTR 30 = CAR, 31 = MOD, 32 = SYMM, 33 = FDBK (private words).
| DEC / PWM are not destinations. Tim private-word pattern
| (octatrick-modules lfo_destinations.inc.s): offsets apply every audio
| frame into sy_cxparm / sy_cxfb. LFO_P / LFO_DESC_LEN / LFO_STATE /
| UI_TRACK / CURVALS / CV_STRIDE / CV_SETUP / FLEX_P come from poly.s.
        .set    LF_MID, 16256            | 63.5 << 8
        .set    LF_LAST, 33              | CAR..FDBK (DEC skipped)
        .set    LFD_ENC, 0x4003249c
        .set    LFD_STORE, 0x4003932c
        .set    LFD_RESOLVER, 0x40031da4 | page resolver (track, kind) -> descriptor
        .set    LFD_MACHTAB, 0x400d5f38  | PLAYBACK descriptors by machine
        .set    LFD_MASTER, 0x400d2e8a   | resolver answer for the master track
        .set    LFD_FMT_RET, 0x4003c058  | stock PMTR formatter after descriptor pick
        .global cx_lfo_standalone, cx_lfo_frame, cx_lfo_apply, cx_lfo_page
        .global cx_lfo_stage, cx_lfo_move, cx_lfo_draw, cx_lfo_edit, cx_lfo_pmtr_edit
        .global cx_lfo_morph, po_lfdname

| po_lfdname: 0x4003bff0 (jmp, 8 B; HOOKS LFO_NAME chain with OCTA303). Stock
| `mvs.b (a0),d0; lea LFD_MACHTAB,a0` then picks a2 = tbl[machine]. A FLEX pick
| becomes the page resolver's PLAYBACK descriptor (CX OSC's page on a CX track)
| so LFO SETUP prints PTCH RATO INDX FINE FOLD MIX. Entered as at the site
| (a0 = machine byte, d1 = track); last in the LFO_NAME chain — no MC_NEXT.
po_lfdname:
        mvs.b   (%a0),%d0                | displaced: the machine
        lea     LFD_MACHTAB,%a0          | displaced
        movea.l (%a0,%d0.l*4),%a2        | stock pick
        cmpa.l  #FLEX_P,%a2
        bne     cx_ln_stock              | not FLEX table: stock resume after lea
        move.l  %d1,-(%sp)               | keep track across resolver
        clr.l   -(%sp)                   | page kind 0: PLAYBACK
        move.l  %d1,-(%sp)               | the track
        jsr     LFD_RESOLVER             | d0 = descriptor (d0/d1/a0/a1 clobber; d2-d5 kept)
        addq.l  #8,%sp
        move.l  (%sp)+,%d1
        cmpi.l  #LFD_MASTER,%d0
        beq     cx_ln_flex
        tst.l   %d0
        beq     cx_ln_flex
        movea.l %d0,%a2                  | CX (or other) PLAYBACK page
        jmp     LFD_FMT_RET
cx_ln_flex:
        movea.l #FLEX_P,%a2              | plain FLEX names
        jmp     LFD_FMT_RET
cx_ln_stock:
        jmp     0x4003c054               | after the lea: index PB_TABLE

| Depth-hook: d2 LFO, d4 PMTR, a4 track state, a2 page. d0 depth / a1 dest out.
cx_lfo_apply:
        mvs.w   0x12(%a2,%d2.l*2),%d0
        lea     (%a0,%d4.l*2),%a1
        tst.l   %d4
        beq     cx_la_ptch               | (Tim 2.20) PMTR 0 = PTCH: synth unit is 5× sample
        cmpi.l  #30,%d4
        bcs     cx_la_out
        lea     -20(%sp),%sp
        movem.l %d0-%d3/%a0,(%sp)
        move.l  %d2,%d3
        move.l  %a4,%d2
        subi.l  #LFO_STATE,%d2
        lsr.l   #3,%d2
        cmpi.l  #8,%d2
        bcc     cx_la_discard
        jsr     po_signed:l
        tst.l   %d0
        beq     cx_la_discard
        move.l  %d2,%d0
        add.l   %d0,%d0
        add.l   %d2,%d0
        add.l   %d3,%d0                  | track*3 + LFO
        lea     cx_lf_targets:l,%a0
        clr.b   (%a0,%d0.l)
        cmpi.l  #LF_LAST,%d4
        bhi     cx_la_sink
        move.b  %d4,(%a0,%d0.l)
cx_la_sink:
        lea     cx_lf_scratch:l,%a1
        adda.l  %d0,%a1
        adda.l  %d0,%a1
        bra     cx_la_mid
cx_la_discard:
        lea     cx_lf_discard:l,%a1
cx_la_mid:
        move.w  #LF_MID,(%a1)
        movem.l (%sp),%d0-%d3/%a0
        lea     20(%sp),%sp
cx_la_out:
        rts

| PTCH on a CX OSC track: one semitone = five sample PTCH units (sy_word), so
| stock DEP was 5× too deep. Scale depth ÷5 (0.2 semitone / unit, as FLEX).
| Full DEP 0x7f00 → 0x8000 first, matching stock's full-depth correction.
cx_la_ptch:
        tst.l   %d0
        beq     cx_la_out
        lea     -12(%sp),%sp
        movem.l %d1-%d2/%a0,(%sp)
        move.l  %d0,%d1
        move.l  %a4,%d2
        subi.l  #LFO_STATE,%d2
        lsr.l   #3,%d2
        cmpi.l  #8,%d2
        bcc     cx_lap_keep
        jsr     po_signed:l
        tst.l   %d0
        beq     cx_lap_keep
        cmpi.l  #0x7f00,%d1
        bne     cx_lap_fifth
        move.l  #0x8000,%d1
cx_lap_fifth:
        moveq   #5,%d0
        divs.l  %d0,%d1
cx_lap_keep:
        move.l  %d1,%d0
        movem.l (%sp),%d1-%d2/%a0
        lea     12(%sp),%sp
        rts

cx_lfo_standalone:
        bsr     cx_lfo_apply
        jmp     0x40003cac

cx_lfo_frame:                            | frame-builder depth site (0x4000d03e)
        bsr     cx_lfo_apply
        jmp     0x4000d046

| d2 = track: add live PMTR 30..33 offsets into sy_cxparm CMOR/MMOR/SYMM and
| sy_cxfb (FDBK). Clobbers d0/d1/d3/a0; d2 preserved.
cx_lfo_morph:
        cmpi.l  #8,%d2
        bcc     cx_lm_out
        lea     -24(%sp),%sp
        movem.l %d2/%d4-%d7/%a1,(%sp)    | 0=track; d4..d7 accumulators live
        move.l  %d2,%d3
        add.l   %d3,%d3
        add.l   %d2,%d3                  | track*3
        moveq   #0,%d4                   | CMOR offset (<<8)
        moveq   #0,%d5                   | MMOR
        moveq   #0,%d6                   | SYMM
        moveq   #0,%d7                   | FDBK
        moveq   #0,%d1
cx_lm_each:
        lea     cx_lf_targets:l,%a0
        mvz.b   (%a0,%d3.l),%d0
        cmpi.l  #30,%d0
        bcs     cx_lm_next
        cmpi.l  #LF_LAST,%d0
        bhi     cx_lm_next
        lea     cx_lf_scratch:l,%a0
        mvs.w   (%a0,%d3.l*2),%d2
        subi.l  #LF_MID,%d2
        cmpi.l  #30,%d0
        beq     cx_lm_add_cmor
        cmpi.l  #31,%d0
        beq     cx_lm_add_mmor
        cmpi.l  #32,%d0
        beq     cx_lm_add_symm
        add.l   %d2,%d7                  | 33 FDBK
        bra     cx_lm_next
cx_lm_add_cmor:
        add.l   %d2,%d4
        bra     cx_lm_next
cx_lm_add_mmor:
        add.l   %d2,%d5
        bra     cx_lm_next
cx_lm_add_symm:
        add.l   %d2,%d6
cx_lm_next:
        addq.l  #1,%d3
        addq.l  #1,%d1
        cmpi.l  #3,%d1
        bne     cx_lm_each
        move.l  (%sp),%d2                | track
        lea     sy_cxparm(%pc),%a0
        lsl.l   #2,%d2
        asr.l   #8,%d4
        mvz.b   2(%a0,%d2.l),%d0         | CMOR
        add.l   %d4,%d0
        bsr     cx_lm_clamp
        move.b  %d0,2(%a0,%d2.l)
        asr.l   #8,%d5
        mvz.b   3(%a0,%d2.l),%d0         | MMOR
        add.l   %d5,%d0
        bsr     cx_lm_clamp
        move.b  %d0,3(%a0,%d2.l)
        asr.l   #8,%d6
        mvz.b   1(%a0,%d2.l),%d0         | SYMM
        add.l   %d6,%d0
        bsr     cx_lm_clamp
        move.b  %d0,1(%a0,%d2.l)
        move.l  (%sp),%d2                | track -> FDBK from CURVALS + LFO
        move.l  %d2,%d1
        move.l  #CV_STRIDE,%d0
        mulu.l  %d0,%d1
        lea     CURVALS+CV_SETUP,%a1
        mvz.b   4(%a1,%d1.l),%d0         | SETUP E
        asr.l   #8,%d7
        add.l   %d7,%d0
        bsr     cx_lm_clamp
        lea     sy_cxfb(%pc),%a0
        move.b  %d0,(%a0,%d2.l)
        movem.l (%sp),%d2/%d4-%d7/%a1
        lea     24(%sp),%sp
cx_lm_out:
        rts

| d0 in/out: clamp 0..127. Flags from cmp kept for callers that care.
cx_lm_clamp:
        bpl     cx_lm_cmax
        moveq   #0,%d0
cx_lm_cmax:
        cmpi.l  #127,%d0
        ble     cx_lm_cok
        moveq   #127,%d0
cx_lm_cok:
        rts

cx_lf_ui_desc:
        lea     -12(%sp),%sp
        movem.l %d2/%a0-%a1,(%sp)
        move.l  #LFO_P,%d0
        tst.b   0x80000012
        bne     cx_lf_ui_out
        mvz.b   UI_TRACK,%d2
        jsr     po_signed:l
        tst.l   %d0
        beq     cx_lf_ui_stock
        bsr     cx_lf_build
        lea     cx_lf_desc:l,%a0
        move.l  %a0,%d0
        bra     cx_lf_ui_out
cx_lf_ui_stock:
        move.l  #LFO_P,%d0
cx_lf_ui_out:
        movem.l (%sp),%d2/%a0-%a1
        lea     12(%sp),%sp
        rts

cx_lf_build:
        lea     -12(%sp),%sp
        movem.l %d0/%a0-%a1,(%sp)
        tst.b   cx_lf_built:l
        bne     cx_lf_build_out
        lea     LFO_P,%a0
        lea     cx_lf_desc:l,%a1
        move.l  #LFO_DESC_LEN,%d0
cx_lf_copy:
        move.b  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne     cx_lf_copy
        lea     cx_lf_desc:l,%a1
        moveq   #34,%d0                  | PMTR count 34 (0..33)
        move.l  %d0,0x9a+24(%a1)
        lea     cx_lf_pmtr_fmt:l,%a0
        move.l  %a0,0xca+24(%a1)
        lea     cx_lf_built:l,%a0
        move.b  #1,(%a0)
cx_lf_build_out:
        movem.l (%sp),%d0/%a0-%a1
        lea     12(%sp),%sp
        rts

cx_lfo_page:
        move.l  #LFO_P,%d0
        mvz.b   %d5,%d2
        cmpi.l  #1,%d2
        bne     cx_lfo_page_out
        move.l  #6322,%d2
        muls.l  %d1,%d2
        add.l   %a1,%d2
        move.l  %d0,-(%sp)
        movea.l %d2,%a0
        move.l  %d3,%d0
        jsr     po_sig:l
        move.l  %d0,%d2
        move.l  (%sp)+,%d0
        cmpi.l  #1,%d2
        bne     cx_lfo_page_out
        bsr     cx_lf_build
        lea     cx_lf_desc:l,%a1
        move.l  %a1,%d0
cx_lfo_page_out:
        jmp     0x40031ed6

cx_lfo_stage:
        subq.l  #4,%sp
        move.l  %d0,-(%sp)
        bsr     cx_lf_ui_desc
        move.l  %d0,4(%sp)
        move.l  (%sp)+,%d0
        jmp     0x4005848e
cx_lfo_move:
        subq.l  #4,%sp
        move.l  %d0,-(%sp)
        bsr     cx_lf_ui_desc
        move.l  %d0,4(%sp)
        move.l  (%sp)+,%d0
        jmp     0x4003a462
cx_lfo_draw:
        move.l  %d0,-(%sp)
        bsr     cx_lf_ui_desc
        movea.l %d0,%a4
        move.l  (%sp)+,%d0
        jmp     0x400574d2
cx_lfo_edit:
        move.l  %d0,-(%sp)
        bsr     cx_lf_ui_desc
        movea.l %d0,%a3
        move.l  (%sp)+,%d0
        jmp     0x40039026

cx_lf_pmtr_fmt:
        lea     -8(%sp),%sp
        movem.l %d0/%a0,(%sp)
        move.l  16(%sp),%d0
        cmpi.l  #30,%d0
        bcs     cx_lf_pmtr_stock
        cmpi.l  #LF_LAST,%d0
        bhi     cx_lf_pmtr_stock
        movea.l 12(%sp),%a0
        cmpi.l  #30,%d0
        beq     cx_lf_pmtr_cmor
        cmpi.l  #31,%d0
        beq     cx_lf_pmtr_mmor
        cmpi.l  #32,%d0
        beq     cx_lf_pmtr_symm
        move.b  #'F',(%a0)+              | 33 FDBK
        move.b  #'D',(%a0)+
        move.b  #'B',(%a0)+
        move.b  #'K',(%a0)+
        bra     cx_lf_pmtr_tag
cx_lf_pmtr_cmor:                         | PMTR 30 = CAR (matches SETUP A)
        move.b  #'C',(%a0)+
        move.b  #'A',(%a0)+
        move.b  #'R',(%a0)+
        clr.b   (%a0)+
        bra     cx_lf_pmtr_tag
cx_lf_pmtr_mmor:                         | PMTR 31 = MOD (matches SETUP B)
        move.b  #'M',(%a0)+
        move.b  #'O',(%a0)+
        move.b  #'D',(%a0)+
        clr.b   (%a0)+
        bra     cx_lf_pmtr_tag
cx_lf_pmtr_symm:
        move.b  #'S',(%a0)+
        move.b  #'Y',(%a0)+
        move.b  #'M',(%a0)+
        move.b  #'M',(%a0)+
cx_lf_pmtr_tag:
        clr.b   (%a0)
        move.b  #'S',1(%a0)
        move.b  #'R',2(%a0)
        move.b  #'C',3(%a0)
        clr.b   4(%a0)
        movem.l (%sp),%d0/%a0
        lea     8(%sp),%sp
        rts
cx_lf_pmtr_stock:
        movem.l (%sp),%d0/%a0
        lea     8(%sp),%sp
        jmp     0x4003bf64

cx_lfo_pmtr_edit:
        lea     -12(%sp),%sp
        movem.l %d4/%d6/%a2,(%sp)
        moveq   #29,%d6
        mvz.b   UI_TRACK,%d2
        jsr     po_signed:l
        tst.l   %d0
        beq     cx_lf_pmtr_bound
        moveq   #LF_LAST,%d6
cx_lf_pmtr_bound:
        move.l  %d3,%d0
        cmp.l   %d6,%d0
        bls     cx_lf_pmtr_pos
        move.l  %d6,%d0
cx_lf_pmtr_pos:
        bsr     cx_lf_pmtr_map
        move.l  %d0,%d7
        move.l  %d5,-(%sp)
        clr.l   -(%sp)
        jsr     LFD_ENC
        addq.l  #8,%sp
        add.l   %d7,%d0
        bpl     cx_lf_pmtr_max
        moveq   #0,%d0
cx_lf_pmtr_max:
        cmp.l   %d6,%d0
        ble     cx_lf_pmtr_val
        move.l  %d6,%d0
cx_lf_pmtr_val:
        move.l  %d0,%d7
        move.l  %d0,%d2
        bsr     cx_lf_pmtr_map
        move.l  %d0,%d3
        movem.l (%sp),%d4/%d6/%a2
        lea     12(%sp),%sp
        jmp     LFD_STORE

cx_lf_pmtr_map:
        cmpi.l  #6,%d0
        bcs     cx_lf_map_out
        cmpi.l  #12,%d0
        bcs     cx_lf_map_plus
        cmpi.l  #18,%d0
        bcc     cx_lf_map_out
        subq.l  #6,%d0
        rts
cx_lf_map_plus:
        addq.l  #6,%d0
cx_lf_map_out:
        rts

        .balign 4
cx_lf_scratch:
        .fill   24,2,0
cx_lf_targets:
        .fill   24,1,0
cx_lf_discard:
        .word   0
cx_lf_built:
        .byte   0
        .balign 4
cx_lf_desc:
        .fill   LFO_DESC_LEN,1,0
        .balign 4
