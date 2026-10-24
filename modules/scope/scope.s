| scope.s -- SCOPE: OSC + XY.
|
| BASELINE: LSCOPE X — hold-then-drop (OSC/XY).
|
| DOWN+TEMPO opens; UP+TEMPO -> TUNER. No WFRAME / RULE; BOX = rim clear only.
| UP/DOWN switch visual, reset A-F, toast. RIGHT help / LEFT back.
| ENC A push = GAIN default + clear session peak.
| CUE release = toggle G/P HUD (not while held).
|
|   OSC   A GAIN  B TIME   (C-F ---)
|   XY    A GAIN  B TIME   (C-F ---)
|   ALL   A GAIN  B TIME   (C-F ---)
|
| OSC = mono polyline. XY = L→X/R→Y. ALL = 8-track level strips.
| Peak: max(|L|,|R|) recent ring. Clip '!': only when peak is 0 dBFS.

        .set    KROWS,     0x46100b18
        .set    KDOWN,     0x20
        .set    KUP,       0x33
        .set    TRACK,     0x80000000
        .set    RB_BASE,   0x80003190
        .set    RB_PREV,   0x800000e4
        .set    TEMPOWIN,  0x460d16a0
        .set    SCRDIRTY,  0x46c7c72c
        .set    UIQUEUE,   0x460d1664
        .set    WCREATE,   0x4005829c
        .set    WDESTROY,  0x40055db4
        .set    CLEAR,     0x40035624
        .set    VLINE,     0x40011b94
        .set    BOX,       0x40012254   | rim wipe only (CLEAR leaves 1px)
        .set    FONT,      0x400ba876
        .set    TEXT,      0x40012bd8
        .set    LPUSH,     0x40031494
        .set    LPOP,      0x4003146c
        .set    NOTIFY,    0x4005a2b8
        .set    TEMPO_GO,  0x40059ef6
        .set    UI_GO,     0x40056c78
        .set    ISR_GO,    0x4000d9a0

        .set    WINW,      128
        .set    WINH,      64
        .set    MID,       32
        .set    NRING,     8192
        .set    TURING,    4096
        .set    SC_PERIOD, 46
        .set    TU_PERIOD, 400
        .set    GAIN_DEF,  20          | centre = 0 dB; knob 0..40 → ±20 dB
        .set    GAIN_MAX,  40
        .set    GAIN_DIV,  0x4000      | OSC px scale at 0 dB
        .set    XY_DIV,    0x1400      | XY hotter — FS blows past the bezel
        .set    VIZ_MAX,   2           | OSC / XY / ALL
        .set    TIME_MAX,  9
        .set    TIME_FULL, 6
        .set    TIME_DEF,  3
        .set    TIME_SLOW, 3           | enc ticks per TIME step (less sensitive)
        .set    HOLD_FRAMES, 120       | ≥2 s @ ~60 Hz draw — peak + clip
        .set    METER_N,   256         | recent ring samples for P / !
        .set    XY_MAX,    192         | connected samples per frame
        .set    ALL_N,     64          | samples/track in ALL grid
        .set    ALL_CW,    64          | cell W (2 cols)
        .set    ALL_CH,    16          | cell H (4 rows)
        .set    TOAST_DUR, 0x30
        .set    KENCA,     0x38
        .set    X0,        3           | inset — no edge chrome
        .set    X1,        120
        .set    YLO,       3
        .set    YHI,       60
        .set    XY_CX,     64          | XY centre
        .set    HUD_TX,    2
        .set    HUD_TY,    54

        .text
        .globl  sc_tempo, sc_frame, sc_tick, sc_open, sc_close, sc_draw
        .globl  sc_enc, sc_viz_up, sc_viz_down, sc_help_on, sc_help_off
        .globl  sc_gain_rst, sc_hud_tog

        .extern tu_win, tu_wr, tu_frames, tu_ring
        .extern tu_open, tu_close, tu_analyse, tu_draw

| ---- TEMPO ------------------------------------------------------------
sc_tempo:
        moveq   #0,%d0
        moveb   KROWS+(KDOWN>>3),%d0
        btst    #(KDOWN&7),%d0
        bne.s   do_scope
        moveq   #0,%d0
        moveb   KROWS+(KUP>>3),%d0
        btst    #(KUP&7),%d0
        bne.s   do_tuner
        tstl    TEMPOWIN
        jmp     TEMPO_GO

do_scope:
        tstl    tu_win
        beq.s   1f
        jsr     tu_close
1:      tstl    sc_win
        bne.w   sc_close
        bra.w   sc_open

do_tuner:
        tstl    sc_win
        beq.s   2f
        bsr.w   sc_close
2:      tstl    tu_win
        beq.s   3f
        jsr     tu_close
        rts
3:      jsr     tu_open
        rts

| ---- frame_isr --------------------------------------------------------
sc_frame:
        movel   %d1,0x80004800
        tstl    sc_win
        bne.s   fill_sc
        tstl    tu_win
        bne.w   fill_tu
        jmp     ISR_GO

fill_sc:
        movel   RB_PREV,%d0
        lsll    #8,%d0
        lsll    #2,%d0
        moveq   #0,%d1
        moveb   TRACK,%d1
        andil   #7,%d1
        lsll    #7,%d1
        addl    %d1,%d0
        addil   #RB_BASE,%d0
        moveal  %d0,%a0
        movel   sc_wr,%d2
        lea     sc_ring_l,%a1
        lea     sc_ring_r,%a2
        bsr.w   sc_stride
        moveq   #16,%d3
fs1:    movel   %a0@+,%d0
        movel   %a0@+,%d1
        swap    %d0
        swap    %d1
        addql   #1,sc_decim
        movel   sc_decim,%d5
        cmpl    %d4,%d5
        bcs.s   fs_skip
        clrl    sc_decim
        movew   %d0,%a1@(0,%d2:l:2)
        movew   %d1,%a2@(0,%d2:l:2)
        addql   #1,%d2
        andil   #NRING-1,%d2
fs_skip:
        subql   #1,%d3
        bne.s   fs1
        movel   %d2,sc_wr
| ALL rings: same TIME decim as OSC (d4 from sc_stride)
        addql   #1,sc_all_decim
        movel   sc_all_decim,%d5
        cmpl    %d4,%d5
        bcs.w   fs_all_skip
        clrl    sc_all_decim
        movel   sc_all_wr,%d2
        lea     sc_all,%a1
        moveq   #0,%d5                 | track 0..7
fs_t:   movel   RB_PREV,%d0
        lsll    #8,%d0
        lsll    #2,%d0
        movel   %d5,%d1
        lsll    #7,%d1                 | t*0x80
        addl    %d1,%d0
        addil   #RB_BASE,%d0
        moveal  %d0,%a0
        movel   %a0@,%d0
        movel   %a0@(4),%d1
        swap    %d0
        swap    %d1
        ext.l   %d0
        ext.l   %d1
        asrl    #1,%d0
        asrl    #1,%d1
        addl    %d1,%d0                | mono
        asrl    #2,%d0
        movew   %d0,%a1@(0,%d2:l:2)
        lea     %a1@(ALL_N*2),%a1
        addql   #1,%d5
        moveq   #8,%d0
        cmpl    %d0,%d5
        blt.s   fs_t
        addql   #1,%d2
        moveq   #ALL_N-1,%d0
        andl    %d0,%d2
        movel   %d2,sc_all_wr
fs_all_skip:
        addql   #1,sc_frames
        jmp     ISR_GO

fill_tu:
        movel   RB_PREV,%d0
        lsll    #8,%d0
        lsll    #2,%d0
        moveq   #0,%d1
        moveb   TRACK,%d1
        andil   #7,%d1
        lsll    #7,%d1
        addl    %d1,%d0
        addil   #RB_BASE,%d0
        moveal  %d0,%a0
        movel   tu_wr,%d2
        lea     tu_ring,%a1
        moveq   #16,%d3
1:      movel   %a0@+,%d0
        movel   %a0@+,%d1
        asrl    #1,%d0
        asrl    #1,%d1
        addl    %d1,%d0
        swap    %d0
        movew   %d0,%a1@(0,%d2:l:2)
        addql   #1,%d2
        andil   #TURING-1,%d2
        subql   #1,%d3
        bne.s   1b
        movel   %d2,tu_wr
        addql   #1,tu_frames
        jmp     ISR_GO

| ---- UI tick ----------------------------------------------------------
sc_tick:
        tstl    sc_win
        beq.s   try_tu
        movel   sc_frames,%d0
        cmpil   #SC_PERIOD,%d0
        blt.s   tick_done
        clrl    sc_frames
        bsr.w   sc_draw
        bra.s   tick_done
try_tu:
        tstl    tu_win
        beq.s   tick_done
        movel   tu_frames,%d0
        cmpil   #TU_PERIOD,%d0
        blt.s   tick_done
        clrl    tu_frames
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        jsr     tu_analyse
        jsr     tu_draw
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
tick_done:
        pea     UIQUEUE
        jmp     UI_GO

| ---- viz switch -------------------------------------------------------
sc_viz_up:
        movel   sc_viz,%d0
        addql   #1,%d0
        cmpil   #VIZ_MAX,%d0
        ble.s   1f
        moveq   #0,%d0
1:      movel   %d0,sc_viz
        bra.s   sc_viz_toast

sc_viz_down:
        movel   sc_viz,%d0
        subql   #1,%d0
        bpl.s   1f
        moveq   #VIZ_MAX,%d0
1:      movel   %d0,sc_viz
sc_viz_toast:
        bsr.w   sc_viz_defs
        tstl    sc_viz
        bne.s   1f
        lea     T_OSC,%a0
        bra.s   3f
1:      moveq   #1,%d0
        cmpl    sc_viz,%d0
        bne.s   2f
        lea     T_XY,%a0
        bra.s   3f
2:      lea     T_ALL,%a0
3:      pea     TOAST_DUR
        movel   %a0,%sp@-
        jsr     NOTIFY
        addql   #8,%sp
        bra.w   sc_draw

sc_viz_defs:
        moveq   #GAIN_DEF,%d0
        movel   %d0,sc_gain
        clrl    sc_time_acc
        clrl    sc_e
        clrl    sc_f
        moveq   #TIME_DEF,%d0
        movel   %d0,sc_time
        clrl    sc_c
        clrl    sc_d
        rts

sc_help_on:
        moveq   #1,%d0
        movel   %d0,sc_help
        bra.w   sc_draw
sc_help_off:
        clrl    sc_help
        bra.w   sc_draw

| CUE release: show/hide G/P HUD (press ignored — "when not held").
sc_hud_tog:
        movel   sc_hud_on,%d0
        eoril   #1,%d0
        movel   %d0,sc_hud_on
        bra.w   sc_draw

| ---- encoders ---------------------------------------------------------
sc_enc:
        movel   4(%sp),%d1
        movel   8(%sp),%d0
        beq.s   enc_rts
        moveq   #5,%d2
        cmpl    %d2,%d1
        bhi.s   enc_rts
| unused: C D E F (GAIN+TIME only)
        moveq   #2,%d2
        cmpl    %d2,%d1
        bhs.s   enc_rts                | C..F unused
| B: TIME uses TIME_SLOW
enc_b:  moveq   #1,%d2
        cmpl    %d2,%d1
        bne.s   enc_ok
        addl    %d0,sc_time_acc
        movel   sc_time_acc,%d5
        moveq   #TIME_SLOW,%d2
        cmpl    %d2,%d5
        blt.s   enc_tn
1:      subl    %d2,sc_time_acc
        moveq   #1,%d0
        bra.s   enc_ok
enc_tn: negl    %d2
        cmpl    %d2,%d5
        bgt.s   enc_rts
        moveq   #TIME_SLOW,%d2
        addl    %d2,sc_time_acc
        moveq   #-1,%d0
enc_ok: movel   %d1,%d4
        lea     sc_p,%a0
        movel   %a0@(0,%d4:l:4),%d1
        addl    %d0,%d1
        bsr.w   sc_clamp_p
        movel   %d1,%a0@(0,%d4:l:4)
        bra.w   sc_draw
enc_rts:rts

sc_gain_rst:
        moveq   #GAIN_DEF,%d0
        movel   %d0,sc_gain
        clrl    sc_peak_live
        clrl    sc_peak_hold
        clrl    sc_peak_tmr
        clrl    sc_clip_tmr
        bra.w   sc_draw

sc_clamp_p:
        moveq   #0,%d2
        moveq   #GAIN_MAX,%d3
        tstl    %d4
        beq.s   cp_do                  | A GAIN
        moveq   #1,%d5
        cmpl    %d5,%d4
        bne.w   2f                     | only A/B live
        moveq   #TIME_MAX,%d3          | B TIME
cp_do:  cmpl    %d2,%d1
        bge.s   1f
        movel   %d2,%d1
1:      cmpl    %d3,%d1
        ble.s   2f
        movel   %d3,%d1
2:      rts

| ---- open / close -----------------------------------------------------
sc_open:
        pea     sc_close
        pea     1
        clrl    %sp@-
        clrl    %sp@-
        pea     WINH
        pea     WINW
        jsr     WCREATE
        lea     %sp@(24),%sp
        movel   %d0,sc_win
        beq.w   9f
        pea     SC_LAYER
        jsr     LPUSH
        addql   #4,%sp
        clrl    sc_frames
        clrl    sc_wr
        clrl    sc_decim
        clrl    sc_viz
        clrl    sc_help
        clrl    sc_clip
        clrl    sc_peak_live
        clrl    sc_peak_hold
        clrl    sc_peak_tmr
        clrl    sc_clip_tmr
        clrl    sc_time_acc
        lea     sc_ring_l,%a0          | kill garbage spikes before audio
        movel   #NRING,%d0
1:      clrw    %a0@+
        subql   #1,%d0
        bne.s   1b
        lea     sc_ring_r,%a0
        movel   #NRING,%d0
2:      clrw    %a0@+
        subql   #1,%d0
        bne.s   2b
        clrl    sc_all_wr
        clrl    sc_all_decim
        lea     sc_all,%a0
        movel   #8*ALL_N,%d0
3:      clrw    %a0@+
        subql   #1,%d0
        bne.s   3b
        bsr.w   sc_viz_toast
9:      rts

sc_close:
        tstl    sc_win
        beq.s   9f
        clrl    sc_help
        pea     sc_win
        jsr     WDESTROY
        addql   #4,%sp
        pea     SC_LAYER
        jsr     LPOP
        addql   #4,%sp
9:      rts

| ---- primitives -------------------------------------------------------
sc_text:
        movel   %a0,%sp@-
        pea     -1
        movel   %d1,%sp@-
        movel   %d0,%sp@-
        movel   %a5,%sp@-
        pea     FONT
        jsr     TEXT
        lea     %sp@(24),%sp
        rts

sc_vline:
        pea     1
        movel   %d2,%sp@-
        movel   %d1,%sp@-
        movel   %d0,%sp@-
        movel   %a5,%sp@-
        jsr     VLINE
        lea     %sp@(20),%sp
        rts

| pixel at (d0,d1) via 1-tall VLINE
sc_pixel:
        movel   %d1,%d2
        bra.w   sc_vline

| Bresenham (xy_x0,xy_y0) -> (xy_x1,xy_y1). Clobbers d0-d3.
sc_line:
        movel   xy_x1,%d0
        subl    xy_x0,%d0
        movel   %d0,%d2                | dx raw
        bpl.s   ln_dx
        negl    %d0
ln_dx:  movel   %d0,xy_dx
        movel   xy_y1,%d0
        subl    xy_y0,%d0
        movel   %d0,%d3                | dy raw
        bpl.s   ln_dy
        negl    %d0
ln_dy:  movel   %d0,xy_dy
        moveq   #1,%d0
        tstl    %d2
        bpl.s   ln_sx
        moveq   #-1,%d0
ln_sx:  movel   %d0,xy_sx
        moveq   #1,%d0
        tstl    %d3
        bpl.s   ln_sy
        moveq   #-1,%d0
ln_sy:  movel   %d0,xy_sy
        movel   xy_dx,%d0
        subl    xy_dy,%d0
        movel   %d0,xy_err
ln_lp:  movel   xy_x0,%d0
        movel   xy_y0,%d1
        bsr.w   sc_pixel
        movel   xy_x0,%d0
        cmpl    xy_x1,%d0
        bne.s   ln_go
        movel   xy_y0,%d0
        cmpl    xy_y1,%d0
        beq.s   ln9
ln_go:  movel   xy_err,%d0
        addl    %d0,%d0                | e2 = 2*err
        movel   xy_dy,%d1
        negl    %d1
        cmpl    %d1,%d0
        ble.s   ln_y
        movel   xy_err,%d1
        subl    xy_dy,%d1
        movel   %d1,xy_err
        movel   xy_x0,%d1
        addl    xy_sx,%d1
        movel   %d1,xy_x0
ln_y:   movel   xy_dx,%d1
        cmpl    %d1,%d0
        bge.w   ln_lp
        movel   xy_err,%d1
        addl    xy_dx,%d1
        movel   %d1,xy_err
        movel   xy_y0,%d1
        addl    xy_sy,%d1
        movel   %d1,xy_y0
        bra.w   ln_lp
ln9:    rts

| sample -> y in YLO..YHI. Scratch d0-d3 only (draw_osc keeps col in d6!).
| XY uses XY_DIV (much hotter) so the figure hits the bezel at 0 dB.
sc_to_y:
        movel   %d0,%d1
        moveq   #0,%d3
        tstl    %d1
        bpl.s   ty1
        moveq   #1,%d3
        negl    %d1
ty1:    movel   sc_gain,%d2
        mulsl   %d2,%d1
        movel   #GAIN_DIV,%d2
        tstl    sc_viz
        beq.s   ty2
        movel   #XY_DIV,%d2
ty2:    divul   %d2,%d1
        moveq   #MID,%d0
        tstl    %d3
        beq.s   ty3
        subl    %d1,%d0
        bra.s   ty4
ty3:    addl    %d1,%d0
ty4:    cmpil   #YLO,%d0
        bge.s   ty5
        moveq   #YLO,%d0
ty5:    cmpil   #YHI,%d0
        ble.s   ty9
        moveq   #YHI,%d0
ty9:    rts

| sample -> x in X0..X1 (XY). Scratch d0-d3 only (step lives in d5).
sc_to_x:
        movel   %d0,%d1
        moveq   #0,%d3
        tstl    %d1
        bpl.s   tx1
        moveq   #1,%d3
        negl    %d1
tx1:    movel   sc_gain,%d2
        mulsl   %d2,%d1
        movel   #XY_DIV,%d2
        divul   %d2,%d1
        moveq   #XY_CX,%d0
        tstl    %d3
        beq.s   tx3
        subl    %d1,%d0
        bra.s   tx4
tx3:    addl    %d1,%d0
tx4:    cmpil   #X0,%d0
        bge.s   tx5
        moveq   #X0,%d0
tx5:    cmpil   #X1,%d0
        ble.s   tx9
        moveq   #X1,%d0
tx9:    rts

sc_span:
        movel   sc_time,%d1
        moveq   #TIME_FULL,%d2
        cmpl    %d2,%d1
        ble.s   1f
        movel   %d2,%d1
1:      moveq   #64,%d0
        addl    %d0,%d0
        tstl    %d1
        beq.s   9f
2:      lsll    #1,%d0
        subql   #1,%d1
        bne.s   2b
9:      cmpil   #NRING,%d0
        bls.s   8f
        movel   #NRING,%d0
8:      rts

sc_stride:
        moveq   #1,%d4
        movel   sc_time,%d0
        moveq   #TIME_FULL,%d1
        cmpl    %d1,%d0
        bls.s   9f
        subl    %d1,%d0
1:      lsll    #1,%d4
        subql   #1,%d0
        bne.s   1b
9:      rts

sc_mix_at:
        lea     sc_ring_l,%a0
        lea     sc_ring_r,%a1
        movew   %a0@(0,%d2:l:2),%d0
        ext.l   %d0
        movew   %a1@(0,%d2:l:2),%d1
        ext.l   %d1
        asrl    #1,%d0                 | mono (L+R)/2
        asrl    #1,%d1
        addl    %d1,%d0
        rts

| start index in d2 for span d7 (free-run: now − span).
sc_start:
        movel   sc_wr,%d2
        subl    %d7,%d2
        andil   #NRING-1,%d2
        rts

| ---- draw -------------------------------------------------------------
sc_draw:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   sc_win,%d0
        beq.w   dexit
        moveal  %d0,%a5
        lea     %a5@(36),%a5
        movel   %a5,%sp@-
        jsr     CLEAR
        addql   #4,%sp
| CLEAR leaves a 1px rim — help TEXT / clip invert stuck there. Wipe all.
        pea     0                      | mode clear
        pea     WINH-1
        pea     WINW-1
        pea     0
        pea     0
        movel   %a5,%sp@-
        jsr     BOX
        lea     %sp@(24),%sp
        tstl    sc_help
        bne.w   draw_help
        moveq   #2,%d0
        cmpl    sc_viz,%d0
        beq.w   draw_all
        bsr.w   sc_span
        movel   %d0,%d7
        bsr.w   sc_start
        tstl    sc_viz
        bne.w   draw_xy

| OSC: polyline through consecutive samples (classic scope)
draw_osc:
        movel   %d2,%a2
| seed prev y from first sample — do NOT start at MID (looked like 0 on left)
        moveq   #X0,%d6
        movel   %a2,%d2
        bsr.w   sc_mix_at
        bsr.w   sc_to_y
        movel   %d0,%d3
        addql   #1,%d6
ecol:
        movel   %d6,%d0
        subql   #X0,%d0
        moveq   #X1-X0,%d1
        mulsl   %d7,%d0
        divul   %d1,%d0
        addl    %a2,%d0
        andil   #NRING-1,%d0
        movel   %d0,%d2
        movel   %d3,-(%sp)
        bsr.w   sc_mix_at
        bsr.w   sc_to_y
        movel   %d0,%d5
        movel   (%sp)+,%d3
        movel   %d5,%d2
        movel   %d3,%d1
        cmpl    %d1,%d2
        bge.s   e8
        movel   %d1,%d0
        movel   %d2,%d1
        movel   %d0,%d2
e8:
| skip flat rail on clamp Y (was the sticky top/bottom white line)
        cmpil   #YLO,%d1
        bne.s   e8b
        cmpl    %d1,%d2
        beq.s   eskip
e8b:    cmpil   #YHI,%d1
        bne.s   e8c
        cmpl    %d1,%d2
        beq.s   eskip
e8c:    movel   %d6,%d0
        bsr.w   sc_vline
eskip:  movel   %d5,%d3
        addql   #1,%d6
        cmpil   #X1,%d6
        ble.w   ecol
        bsr.w   sc_meter_scan
        bsr.w   sc_peak_commit
        tstl    sc_hud_on
        beq.w   draw_done
        bsr.w   sc_hud
        bra.w   draw_done

| XY Lissajous: L→X, R→Y. Connect samples (not a dot cloud).
draw_xy:
        clrl    xy_have
        bsr.w   sc_span
        movel   %d0,%d6                | full span
        movel   %d0,%d7
        cmpil   #XY_MAX,%d7
        bls.s   xy_n
        movel   #XY_MAX,%d7
xy_n:   tstl    %d7
        bne.s   xy_st
        moveq   #1,%d7
xy_st:  moveq   #1,%d5                 | step through span
        cmpl    %d7,%d6
        bls.s   xy_go
        movel   %d6,%d0
        divul   %d7,%d0
        tstl    %d0
        beq.s   xy_go
        movel   %d0,%d5
xy_go:  movel   sc_wr,%d2
        subl    %d6,%d2
        andil   #NRING-1,%d2
xy_lp:  lea     sc_ring_l,%a0
        lea     sc_ring_r,%a1
        movew   %a0@(0,%d2:l:2),%d0
        ext.l   %d0
        movew   %a1@(0,%d2:l:2),%d1
        ext.l   %d1
        movel   %d2,-(%sp)             | ring idx
        movel   %d5,-(%sp)             | step
        movel   %d7,-(%sp)             | count
        movel   %d1,-(%sp)             | R sample
        bsr.w   sc_to_x
        movel   %d0,xy_x1
        movel   (%sp)+,%d0             | R
        bsr.w   sc_to_y
        movel   %d0,xy_y1
        tstl    xy_have
        beq.s   xy_seed
        bsr.w   sc_line                | prev (x0,y0) -> (x1,y1)
        bra.s   xy_adv
xy_seed:moveq   #1,%d0
        movel   %d0,xy_have
        movel   xy_x1,%d0
        movel   xy_y1,%d1
        bsr.w   sc_pixel
xy_adv: movel   xy_x1,%d0
        movel   %d0,xy_x0
        movel   xy_y1,%d0
        movel   %d0,xy_y0
        movel   (%sp)+,%d7
        movel   (%sp)+,%d5
        movel   (%sp)+,%d2
        addl    %d5,%d2
        andil   #NRING-1,%d2
        subql   #1,%d7
        bne.w   xy_lp
        bsr.w   sc_meter_scan
        bsr.w   sc_peak_commit
        tstl    sc_hud_on
        beq.w   draw_done
        bsr.w   sc_hud
        bra.w   draw_done



| ---- ALL: 4x2 mini OSC (T1-4 left col, T5-8 right; mid divider) -------
| Cell t <-> sc_all[t] 1:1 (slot±1 remaps were the wrong way).
draw_all:
        moveq   #64,%d0                | centre divider
        moveq   #0,%d1
        moveq   #63,%d2
        bsr.w   sc_vline
        moveq   #0,%d6                 | track 0..7 = T1..T8
al_tr:  movel   %d6,%d0
        asrl    #2,%d0                 | col 0..1
        movel   %d6,%d1
        moveq   #3,%d2
        andl    %d2,%d1                | row bits 0..3
        eorl    %d2,%d1                | flip: T1 top (was upside-down)
        moveq   #ALL_CW,%d2
        mulsl   %d2,%d0                | x0 = col*64
        moveq   #ALL_CH,%d2
        mulsl   %d2,%d1                | y0 = row*16
        movel   %d0,al_x0
        movel   %d1,al_y0
        moveq   #ALL_CH/2,%d2
        addl    %d2,%d1
        movel   %d1,al_mid
        lea     sc_all,%a0
        movel   %d6,%d0
        moveq   #ALL_N,%d1
        addl    %d1,%d1
        mulsl   %d1,%d0
        addl    %d0,%a0                | &sc_all[t]
        movel   sc_all_wr,%d2
        moveq   #0,%d7
        movel   al_x0,%d5
        movew   %a0@(0,%d2:l:2),%d0
        ext.l   %d0
        movel   %d6,-(%sp)
        movel   %d7,-(%sp)
        movel   %a0,-(%sp)
        movel   %d2,-(%sp)
        movel   %d5,-(%sp)
        bsr.w   al_to_y
        movel   %d0,%d3
        movel   (%sp)+,%d5
        movel   (%sp)+,%d2
        movel   (%sp)+,%a0
        movel   (%sp)+,%d7
        movel   (%sp)+,%d6
        addql   #1,%d5
        addql   #1,%d7
        addql   #1,%d2
        moveq   #ALL_N-1,%d0
        andl    %d0,%d2
al_col: moveq   #ALL_N,%d0
        cmpl    %d0,%d7
        bge.w   al_nx
        movew   %a0@(0,%d2:l:2),%d0
        ext.l   %d0
        movel   %d6,-(%sp)
        movel   %d7,-(%sp)
        movel   %a0,-(%sp)
        movel   %d2,-(%sp)
        movel   %d5,-(%sp)
        movel   %d3,-(%sp)
        bsr.w   al_to_y
        movel   %d0,%d4
        movel   (%sp)+,%d3
        movel   (%sp)+,%d5
        movel   (%sp)+,%d2
        movel   (%sp)+,%a0
        movel   (%sp)+,%d7
        movel   (%sp)+,%d6
        movel   %d4,%d2
        movel   %d3,%d1
        cmpl    %d1,%d2
        bge.s   al_or
        movel   %d1,%d0
        movel   %d2,%d1
        movel   %d0,%d2
al_or:  movel   %d5,%d0
        movel   %d6,-(%sp)
        movel   %d7,-(%sp)
        movel   %a0,-(%sp)
        movel   %d4,-(%sp)
        movel   %d5,-(%sp)
        bsr.w   sc_vline
        movel   (%sp)+,%d5
        movel   (%sp)+,%d3
        movel   (%sp)+,%a0
        movel   (%sp)+,%d7
        movel   (%sp)+,%d6
        addql   #1,%d5
        addql   #1,%d7
        movel   sc_all_wr,%d2
        addl    %d7,%d2
        moveq   #ALL_N-1,%d0
        andl    %d0,%d2
        bra.w   al_col
al_nx:  addql   #1,%d6
        moveq   #8,%d0
        cmpl    %d0,%d6
        blt.w   al_tr
        bra.w   draw_done

| d0=sample -> y in cell using al_y0/al_mid/GAIN. Scratch d0-d3.
al_to_y:
        movel   %d0,%d1
        moveq   #0,%d3
        tstl    %d1
        bpl.s   ay1
        moveq   #1,%d3
        negl    %d1
ay1:    movel   sc_gain,%d2
        mulsl   %d2,%d1
        movel   #GAIN_DIV,%d2
        divul   %d2,%d1
        moveq   #ALL_CH/2-2,%d0        | max half-cell (6)
        cmpl    %d0,%d1
        ble.s   ay2
        movel   %d0,%d1
ay2:    movel   al_mid,%d0
        tstl    %d3
        beq.s   ay3
        subl    %d1,%d0
        bra.s   ay4
ay3:    addl    %d1,%d0
ay4:    movel   al_y0,%d2
        cmpl    %d2,%d0
        bge.s   ay5
        movel   %d2,%d0
ay5:    moveq   #ALL_CH-1,%d1
        addl    %d1,%d2                | y0+ALL_CH-1
        cmpl    %d2,%d0
        ble.s   ay9
        movel   %d2,%d0
ay9:    rts

| |d0| for int16; saturates -32768 -> 0x7fff
sc_abs16:
        tstl    %d0
        bpl.s   9f
        negl    %d0
        bvc.s   9f
        movel   #0x7fff,%d0
9:      rts

| Peak meter sample at d2: max(|L|,|R|) — mono (L+R)/2 under-reads music.
sc_meter_abs:
        lea     sc_ring_l,%a0
        lea     sc_ring_r,%a1
        movew   %a0@(0,%d2:l:2),%d0
        ext.l   %d0
        bsr.s   sc_abs16
        movel   %d0,%d1
        movew   %a1@(0,%d2:l:2),%d0
        ext.l   %d0
        bsr.s   sc_abs16
        cmpl    %d1,%d0
        bge.s   9f
        movel   %d1,%d0
9:      rts

| Recent ring → sc_peak_live (max |L|,|R|).
sc_meter_scan:
        clrl    sc_peak_live
        movel   sc_wr,%d2
        movel   #METER_N,%d7
ms1:    subql   #1,%d2
        andil   #NRING-1,%d2
        movel   %d7,-(%sp)
        bsr.s   sc_meter_abs
        movel   (%sp)+,%d7
        cmpl    sc_peak_live,%d0
        ble.s   ms_n
        movel   %d0,sc_peak_live
ms_n:   subql   #1,%d7
        bne.s   ms1
        rts

| Peak hold-then-drop. '!' only when displayed peak is 0 dBFS.
sc_peak_commit:
        movel   sc_peak_live,%d0
        cmpl    sc_peak_hold,%d0
        blt.s   pk_tmr
        movel   %d0,sc_peak_hold
        movel   #HOLD_FRAMES,%d1
        movel   %d1,sc_peak_tmr
        bra.s   pk_clip
pk_tmr: movel   sc_peak_tmr,%d1
        beq.s   pk_drop
        subql   #1,sc_peak_tmr
        bra.s   pk_clip
pk_drop:movel   %d0,sc_peak_hold
pk_clip:movel   sc_peak_hold,%d0
        bsr.w   sc_to_db
        tstl    %d0
        bne.s   cl_tmr                 | only P 0dB
        movel   #HOLD_FRAMES,%d1
        movel   %d1,sc_clip_tmr
        rts
cl_tmr: tstl    sc_clip_tmr
        beq.s   pk9
        subql   #1,sc_clip_tmr
pk9:    rts

| "G±NNdB P-NNdB " / "…!" — clip hold shows trailing '!'.
sc_hud:
        lea     sc_hudbuf,%a1
        moveb   #0x47,%a1@+            | 'G'
        bsr.w   sc_gain_db
        tstl    %d1
        bne.s   hud_gs
        moveb   #0x2b,%a1@+
        bra.s   hud_gn
hud_gs: moveb   #0x2d,%a1@+
hud_gn: bsr.w   sc_put2
        moveb   #0x64,%a1@+
        moveb   #0x42,%a1@+
        moveb   #0x20,%a1@+
        moveb   #0x50,%a1@+            | 'P'
        movel   sc_peak_hold,%d0
        bsr.w   sc_to_db
        tstl    %d0
        bne.s   hud_m
        moveb   #0x20,%a1@+
        moveb   #0x30,%a1@+
        bra.s   hud_du
hud_m:  moveb   #0x2d,%a1@+
        bsr.w   sc_put2
hud_du: moveb   #0x64,%a1@+
        moveb   #0x42,%a1@+
        tstl    sc_clip_tmr
        beq.s   hud_pad
        moveb   #0x21,%a1@+            | '!'
        bra.s   hud_z
hud_pad:moveb   #0x20,%a1@+
hud_z:  clrb    %a1@
        lea     sc_hudbuf,%a0
        moveq   #HUD_TX,%d0
        moveq   #HUD_TY,%d1
        bra.w   sc_text

| Gain knob -> HUD dB: (gain - 20) as ±0..20. Scratch d0/d1/d3.
sc_gain_db:
        movel   sc_gain,%d0
        moveq   #GAIN_DEF,%d3
        moveq   #0,%d1                 | +
        cmpl    %d3,%d0
        beq.s   gd_z
        bgt.s   gd_hi
        moveq   #1,%d1                 | −
        subl    %d0,%d3
        movel   %d3,%d0
        rts
gd_hi:  subl    %d3,%d0
        rts
gd_z:   moveq   #0,%d0
        rts

| |sample| -> dB below FS (0..90), ~1 dB steps (*9/8 toward 0x7fff).
sc_to_db:
        tstl    %d0
        bne.s   db1
        moveq   #90,%d0
        rts
db1:    cmpil   #0x7fff,%d0
        blt.s   db2
        moveq   #0,%d0
        rts
db2:    moveq   #0,%d1
db3:    cmpil   #0x7fff,%d0
        bcc.s   db4
        movel   %d0,%d2
        lsrl    #3,%d2
        addl    %d2,%d0
        addql   #1,%d1
        cmpil   #90,%d1
        blt.s   db3
db4:    movel   %d1,%d0
        rts

sc_put2:
        moveq   #0,%d1
1:      cmpil   #10,%d0
        bcs.s   2f
        subil   #10,%d0
        addql   #1,%d1
        bra.s   1b
2:      addil   #0x30,%d1
        moveb   %d1,%a1@+
        addil   #0x30,%d0
        moveb   %d0,%a1@+
        rts

draw_done:
        moveq   #1,%d0
        movel   %d0,SCRDIRTY
dexit:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| TEXT clobbers a0/a1 — park label table in a2 (saved by sc_draw movem).
draw_help:
        tstl    sc_viz
        bne.s   1f
        lea     H_OSC_TTL,%a0
        lea     H_OSC_TAB,%a2
        bra.s   3f
1:      moveq   #1,%d0
        cmpl    sc_viz,%d0
        bne.s   2f
        lea     H_XY_TTL,%a0
        lea     H_XY_TAB,%a2
        bra.s   3f
2:      lea     H_ALL_TTL,%a0
        lea     H_ALL_TAB,%a2
3:      moveq   #2,%d0
        moveq   #54,%d1                | inset — avoid CLEAR rim
        bsr.w   sc_text
        movel   %a2@(0),%a0
        moveq   #2,%d0
        moveq   #40,%d1
        bsr.w   sc_text
        movel   %a2@(4),%a0
        moveq   #44,%d0
        moveq   #40,%d1
        bsr.w   sc_text
        movel   %a2@(8),%a0
        moveq   #86,%d0
        moveq   #40,%d1
        bsr.w   sc_text
        movel   %a2@(12),%a0
        moveq   #2,%d0
        moveq   #24,%d1
        bsr.w   sc_text
        movel   %a2@(16),%a0
        moveq   #44,%d0
        moveq   #24,%d1
        bsr.w   sc_text
        movel   %a2@(20),%a0
        moveq   #86,%d0
        moveq   #24,%d1
        bsr.w   sc_text
        lea     H_FOOT,%a0
        moveq   #2,%d0
        moveq   #8,%d1                 | was 2 — painted sticky bottom rim
        bsr.w   sc_text
        bra.w   draw_done

T_OSC:  .asciz  "SCOPE OSC"
T_XY:   .asciz  "SCOPE XY"
T_ALL:  .asciz  "SCOPE ALL"
H_OSC_TTL:  .asciz "SCOPE OSC"
H_XY_TTL:   .asciz "SCOPE XY"
H_FOOT: .asciz  "CUE=HUD  LEFT=BACK"
H_OA:   .asciz  "A GAIN"
H_OB:   .asciz  "B TIME"
H_OC:   .asciz  "C ---"
H_OD:   .asciz  "D ---"
H_OE:   .asciz  "E ---"
H_OF:   .asciz  "F ---"
H_XA:   .asciz  "A GAIN"
H_XB:   .asciz  "B TIME"
H_XC:   .asciz  "C ---"
H_XD:   .asciz  "D ---"
H_XE:   .asciz  "E ---"
H_XF:   .asciz  "F ---"
H_ALL_TTL: .asciz "SCOPE ALL"
H_AA:   .asciz  "A GAIN"
H_AB:   .asciz  "B TIME"
H_AC:   .asciz  "C ---"
H_AD:   .asciz  "D ---"
H_AE:   .asciz  "E ---"
H_AF:   .asciz  "F ---"
        .balign 4
H_OSC_TAB:
        .long   H_OA, H_OB, H_OC, H_OD, H_OE, H_OF
H_XY_TAB:
        .long   H_XA, H_XB, H_XC, H_XD, H_XE, H_XF
H_ALL_TAB:
        .long   H_AA, H_AB, H_AC, H_AD, H_AE, H_AF
SC_LAYER:
        .long   0, SC_KEYS, SC_ENCS, 0, 0, -1, -1
SC_KEYS:
        .byte   0x18, 0
        .long   sc_close, 0, 0, 0, 0
        .word   0, 0
        .byte   0x31, 0
        .long   sc_close, 0, 0, 0, 0
        .word   0, 0
        .byte   0x32, 0
        .long   sc_close, 0, 0, 0, 0
        .word   0, 0
        .byte   0x20, 0
        .long   sc_viz_down, 0, 0, 0, 0
        .word   0, 0
        .byte   0x33, 0
        .long   sc_viz_up, 0, 0, 0, 0
        .word   0, 0
        .byte   0x21, 0
        .long   sc_help_on, 0, 0, 0, 0
        .word   0, 0
        .byte   0x34, 0
        .long   sc_help_off, 0, 0, 0, 0
        .word   0, 0
        .byte   0x2a, 0                | CUE — toggle HUD on release
        .long   0, sc_hud_tog, 0, 0, 0
        .word   0, 0
        .byte   KENCA, 0
        .long   sc_gain_rst, 0, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
SC_ENCS:
        .byte   0, 0
        .long   sc_enc, 0, 0, 0, 0
        .byte   1, 0
        .long   sc_enc, 0, 0, 0, 0
        .byte   2, 0
        .long   sc_enc, 0, 0, 0, 0
        .byte   3, 0
        .long   sc_enc, 0, 0, 0, 0
        .byte   4, 0
        .long   sc_enc, 0, 0, 0, 0
        .byte   5, 0
        .long   sc_enc, 0, 0, 0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0

        .data
        .balign 4
        .globl  sc_win, sc_wr, sc_frames, sc_viz
sc_p:
sc_gain:     .long GAIN_DEF
sc_time:     .long TIME_DEF
sc_c:        .long 0
sc_d:        .long 0
sc_e:        .long 0
sc_f:        .long 0
sc_win:      .long 0
sc_wr:       .long 0
sc_frames:   .long 0
sc_viz:      .long 0
sc_help:     .long 0
sc_hud_on:   .long 1                   | CUE release toggles G/P HUD
sc_decim:    .long 0
sc_clip:     .long 0
sc_peak_live: .long 0
sc_peak_hold: .long 0                  | held peak (snap after timer)
sc_peak_tmr: .long 0                   | frames left in peak hold
sc_clip_tmr: .long 0                   | frames left showing '!'
sc_time_acc: .long 0                   | enc B ticks toward TIME_SLOW
sc_hudbuf:   .space 24                 | "G±NNdB P-NNdB!"
xy_have:     .long 0
xy_x0:       .long 0
xy_y0:       .long 0
xy_x1:       .long 0
xy_y1:       .long 0
xy_dx:       .long 0
xy_dy:       .long 0
xy_sx:       .long 0
xy_sy:       .long 0
xy_err:      .long 0
sc_all_wr:    .long 0
sc_all_decim: .long 0                  | TIME stride for ALL fill
al_x0:        .long 0
al_y0:        .long 0
al_mid:       .long 0
sc_all:       .space 8*ALL_N*2        | ALL mini rings (T1..T8)
sc_ring_l:   .space NRING*2
sc_ring_r:   .space NRING*2
