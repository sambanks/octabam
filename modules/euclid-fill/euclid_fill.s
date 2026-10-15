| euclid_fill.s -- EUCLID FILL: TRACK + PAGE opens a standalone Euclid page.
|
| With any track key held, PAGE toggles this window instead of stock's
| pattern-page / SCALE path. FUNC + PAGE (SCALE SETUP) stays stock: it
| rides the FUNC layer, not this opener.
|
| Window rows: STEPS (read-only = pattern length), PULSE, ROT — same
| names/ranges as filter EUCLID. STEPS tracks SCALE SETUP length
| (NORMAL: +0x8e53; PER TRACK: first target track's TRAC+0x50). Encoder A
| = PULSE, B = ROT, C = RAND VEL, D = RAND PTCH; UP/DOWN / LEFT/RIGHT / LEVEL edit
| the focused row. CUE places a free random mask with exactly PULSE hits.
| ROT still shifts it. RAND VEL (0..100): AMP VOL locks, display delta -63..0.
| RAND PTCH (0..100): RANGE of random in-scale PTCH on every hit (not a
| probability). 100 → ±PIT_RAD (±2 oct FM/SY; sample ±PIT_SAMP). PC test
| is (ROOT+st) mod 12 vs SCALE_AT. Sample raw=64+5·st; FM/SY raw=64+st.
| Editing PULSE leaves free mode. YES writes the bar + locks. NO /
| TRACK+PAGE / PAGE closes.
|
| Trig write: mask 0 of each target TRAC in the bank blob and its battery
| mirror at 0x1001614e, then dirty + 0x40027e00 (erase-empty's recipe).

        .set    HELD,      0x460fab40   | held track keys, bit t
        .set    UI_TRACK,  0x100b14cc
        .set    UI_PTN,    0x100b14d0
        .set    DBPTR,     0x46c82456
        .set    MIRROR,    0x1001614e
        .set    DIRTY_G,   0x100f8598
        .set    DIRTY_OFF, 0x9b332
        .set    NOTIFY,    0x40027e00
        .set    TOAST,     0x4005a2b8
        .set    PTN_STR,   0x8ed8
        .set    TRK_STR,   0x91a
        .set    PAT_LEN,   0x8e53       | pattern length (NORMAL scale)
        .set    PAT_PER,   0x8e55       | nonzero = PER TRACK
        .set    TRK_LEN,   0x50         | track length inside TRAC

        .set    WCREATE,   0x4005829c
        .set    WFRAME,    0x40056f4c
        .set    WDESTROY,  0x40055db4
        .set    CLEAR,     0x40035624
        .set    FONT,      0x400ba876   | small UI font, 6 px (tuner.s)
        .set    TEXT,      0x40012bd8   | (font, surf, x, y, limit, str)
        .set    TWIDTH,    0x40012f30   | (font, limit, str) -> pixels
        .set    RULE,      0x40011910   | (surf, x, y, x2, 1)
        .set    BOX,       0x40012254   | (surf, x1, y1, x2, y2, mode)
        .set    SPRINTF,   0x40013a08
        .set    LPUSH,     0x40031494
        .set    LPOP,      0x4003146c
        .set    SCRDIRTY,  0x46c7c72c
        .set    TEMPO24,   0x80001814   | entropy seed (same as RND NAME)
        .set    CLOCKEST,  0x80001818

        .set    PAGE_GO,   0x4004ffcc   | after the displaced 8-byte prologue
        | Compact TEMPO-class box. y counts UP from the bottom.
        .set    WINW,      92
        .set    WINH,      64
        .set    Y_TITLE,   52          | WINH-12
        .set    Y_RULE,    49
        .set    Y_ROW0,    41          | STEPS
        .set    Y_ROW1,    34          | PULSE
        .set    Y_ROW2,    27          | ROT
        .set    Y_ROW3,    20          | RAND VEL
        .set    Y_ROW4,    13          | RAND PTCH
        .set    Y_PAT,     3
        .set    PAT_H,     4
        .set    X_LAB,     10          | label column (">" sits at 3)
        .set    X_VAL,     88          | value right edge (WINW-4)
        .set    LOCK0,     0x59        | step records (STEP_LOCKS.md)
        .set    LOCK_STEP, 32
        .set    LOCK_VOL,  15          | AMP VOL flat index
        .set    LOCK_PTCH, 0           | PLAYBACK PTCH flat index
        .set    SCALE_AT,  0x400d2ca8  | quantizer: jmp qz_scale_mask
        .set    UI_BANK,   0x100b14cf  | bank index (qz_is_synth's Part walk)
        .set    PART_STR,  6322        | Part stride in the bank blob
        .set    SIG_OFF,   0x8edbc     | NEIGHBOR col: "FM",1 when FM SYNTH chosen
        .set    NV_ROOT,   0x100b14ee  | SCALE QUANTIZER ROOT 0..11 (C..B)
        | RAND PTCH = range 0..100 → rad = max_rad*pct/100 (min 1 if pct>0).
        | PIT_RAD 24 = ±2 oct FM/SY; PIT_SAMP 12 = sample PLAYBACK max |st|.
        .set    PIT_RAD,   24
        .set    PIT_SAMP,  12

        .text
        .globl  ef_page, ef_open, ef_close, ef_draw, ef_fill
        .globl  ef_yes, ef_no, ef_up, ef_down, ef_left, ef_right, ef_level, ef_enc
        .globl  ef_cue

| ---- 0x4004ffc4: PAGE press/release. Track held -> toggle Euclid. --------
| Displaced prologue: lea -16(sp),sp ; movem.l d2-d4/a2,(sp).
| On entry the stack is still stock's (keycode @4, event @8).
ef_page:
        tstl    ef_win
        bne.s   1f                      | open: any PAGE press closes
        tstl    HELD
        beq.s   9f                      | no track held: stock PAGE
1:      moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   8f                      | press only
        tstl    ef_win
        bne.w   ef_close
        bra.w   ef_open
8:      rts
9:      lea     -16(%sp),%sp            | displaced prologue
        movem.l %d2-%d4/%a2,(%sp)
        jmp     PAGE_GO

| ---- open / close -------------------------------------------------------
ef_open:
        movel   HELD,%d0
        bne.s   1f
        moveq   #0,%d0
        moveb   UI_TRACK,%d0
        andil   #7,%d0
        moveq   #1,%d1
        lsll    %d0,%d1
        movel   %d1,%d0
1:      movel   %d0,ef_targets
        bsr.w   ef_sync_len             | STEPS := pattern / track length
        pea     ef_close
        pea     5                       | TEMPO class: mutual eviction
        clrl    %sp@-
        clrl    %sp@-
        pea     WINH
        pea     WINW
        jsr     WCREATE
        lea     %sp@(24),%sp
        movel   %d0,ef_win
        beq.s   9f
        movel   %d0,%sp@-
        jsr     WFRAME
        addql   #4,%sp
        pea     EF_LAYER
        jsr     LPUSH
        addql   #4,%sp
        clrl    ef_cursor
        clrl    ef_free                 | open in Euclid mode
        bra.w   ef_draw
9:      rts

| STEPS from the UI pattern's length (NORMAL: +0x8e53; PER TRACK: first
| target track's TRAC+0x50). Same sources as RLEN PLEN / DIRECT JUMP.
| Offsets past ±32K use an address register + add (ColdFire d16 limit).
ef_sync_len:
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulu.l  %d1,%d0
        addal   %d0,%a0                 | a0 = pattern base
        movel   %a0,%d1
        addil   #PAT_PER,%d1
        moveal  %d1,%a1
        tst.b   %a1@
        beq.s   sl_pat
        moveq   #0,%d2                  | first set bit in ef_targets
        movel   ef_targets,%d3
sl_bit: btst    %d2,%d3
        bne.s   sl_trk
        addql   #1,%d2
        moveq   #8,%d0
        cmpl    %d0,%d2
        bcs.s   sl_bit
        moveq   #0,%d2
        moveb   UI_TRACK,%d2
        andil   #7,%d2
sl_trk: movel   %d2,%d0
        movel   #TRK_STR,%d1
        mulu.l  %d1,%d0
        addil   #TRK_LEN,%d0
        moveb   %a0@(0,%d0:l),%d0
        extb.l  %d0
        bra.s   sl_clamp
sl_pat: movel   %a0,%d1
        addil   #PAT_LEN,%d1
        moveal  %d1,%a1
        moveb   %a1@,%d0
        extb.l  %d0
sl_clamp:
        moveq   #1,%d1
        cmpl    %d1,%d0
        bge.s   sl1
        moveq   #1,%d0
sl1:    moveq   #64,%d1
        cmpl    %d1,%d0
        ble.s   sl2
        moveq   #64,%d0
sl2:    movel   %d0,ef_steps
        movel   ef_pulses,%d1
        cmpl    %d0,%d1
        ble.s   sl3
        movel   %d0,ef_pulses
sl3:    movel   ef_rot,%d1
        subql   #1,%d0
        cmpl    %d0,%d1
        ble.s   sl4
        movel   %d0,ef_rot
sl4:    rts

ef_close:
        tstl    ef_win
        beq.s   9f
        pea     ef_win
        jsr     WDESTROY
        addql   #4,%sp
        pea     EF_LAYER
        jsr     LPOP
        addql   #4,%sp
9:      rts

ef_no:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   9f
        bra.w   ef_close
9:      rts

ef_yes:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   9f
        bsr.w   ef_fill
        pea     0x30
        pea     T_FILLED
        jsr     TOAST
        addql   #8,%sp
        bra.w   ef_draw
9:      rts

| ---- cursor / values (0=PULSE, 1=ROT, 2=RAND VEL, 3=RAND PTCH; STEPS = len) ----
ef_up:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   9f
        tstl    ef_cursor
        beq.s   8f
        subql   #1,ef_cursor
        bra.w   ef_draw
8:      moveq   #3,%d0                  | wrap to RAND PTCH
        movel   %d0,ef_cursor
        bra.w   ef_draw
9:      rts

ef_down:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   9f
        movel   ef_cursor,%d0
        addql   #1,%d0
        moveq   #4,%d1
        cmpl    %d1,%d0
        bcs.s   1f
        clrl    %d0
1:      movel   %d0,ef_cursor
        bra.w   ef_draw
9:      rts

ef_left:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   9f
        moveq   #-1,%d0
        bra.w   ef_nudge
9:      rts

ef_right:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   9f
        moveq   #1,%d0
        bra.w   ef_nudge
9:      rts

| CUE: free random mask with exactly PULSE hits among STEPS (uniform over
| k-subsets). PULSE unchanged; ROT still applies. Press only.
ef_cue:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.w   ef_cue_rts
        bsr.w   ef_sync_len
        move.l  ef_steps,%d5            | n
        moveq   #1,%d0
        cmpl    %d0,%d5
        bge.s   1f
        moveq   #1,%d5
1:      moveq   #64,%d0
        cmpl    %d0,%d5
        ble.s   2f
        moveq   #64,%d5
2:      move.l  ef_pulses,%d4           | k
        tstl    %d4
        bpl.s   21f
        clrl    %d4
21:     cmpl    %d5,%d4
        ble.s   22f
        move.l  %d5,%d4
        move.l  %d4,ef_pulses
22:     lea     ef_mask,%a0
        moveq   #7,%d0
0:      clrb    %a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   0b
        moveq   #0,%d2                  | placed so far
cplace: cmpl    %d4,%d2
        bcc.w   cdone
        | pick among the (n - placed) free slots.
        | ef_rng clobbers d0/d1 — park the divisor; a live d1 here was
        | 1664525 and remul made an unreachable rank → cwalk spun forever.
        move.l  %d5,%d1
        sub.l   %d2,%d1                 | free count > 0
        movel   %d1,-(%sp)
        bsr.w   ef_rng
        move.l  %d0,%d3                 | dividend
        movel   (%sp)+,%d1              | divisor
        | ColdFire: remul Dr,Du_rem,Dc_div — NOT divu.w (illegal on 5407)
        remul   %d1,%d0,%d3             | d0 = d3 % d1
        move.l  %d0,%d3                 | target rank 0..free-1
        moveq   #0,%d6                  | step
        moveq   #0,%d7                  | free seen
cwalk:  cmpl    %d5,%d6
        bcc.w   cdone                   | defense: never walk past n
        | is bit d6 set?
        move.l  %d6,%d1
        lsr.l   #3,%d1
        lea     ef_mask,%a0
        move.b  %a0@(0,%d1:l),%d0
        andil   #0xff,%d0               | ColdFire: MOVE.B leaves upper bits
        move.l  %d6,%d1
        andil   #7,%d1
        btst    %d1,%d0
        bne.s   cskip                   | already on: not free
        cmpl    %d3,%d7
        beq.s   cset
        addql   #1,%d7
cskip:  addql   #1,%d6
        bra.s   cwalk
cset:   | set bit d6
        move.l  %d6,%d1
        lsr.l   #3,%d1
        lea     ef_mask,%a0
        addal   %d1,%a0
        move.l  %d6,%d1
        andil   #7,%d1
        moveq   #1,%d0
        lsll    %d1,%d0
        move.b  %a0@,%d1
        or.l    %d0,%d1
        move.b  %d1,%a0@
        addql   #1,%d2
        bra.w   cplace
cdone:  moveq   #1,%d0
        move.l  %d0,ef_free
        clrl    ef_cursor
        bra.w   ef_draw
ef_cue_rts:
        rts

| Numerical Recipes LCG (same constants as RND NAME). Seed from tempo/clock.
ef_rng:
        move.l  ef_rng_state,%d0
        bne.s   1f
        move.l  TEMPO24,%d0
        move.l  CLOCKEST,%d1
        eor.l   %d1,%d0
        eor.l   #0xA5A5A5A5,%d0
        bne.s   1f
        moveq   #1,%d0
1:      move.l  #1664525,%d1
        mulu.l  %d1,%d0
        add.l   #1013904223,%d0
        move.l  %d0,ef_rng_state
        rts

| d2=step i, d4=k (euclid), d5=n, d6=rot -> d7=1 if that cell is on.
| Free mode: bit (i+n-rot)%n of ef_mask. Euclid: (idx·k)%n < k.
ef_hit:
        move.l  %d2,%d3
        addl    %d5,%d3
        subl    %d6,%d3
1:      cmpl    %d5,%d3
        bcs.s   2f
        subl    %d5,%d3
        bra.s   1b
2:      moveq   #0,%d7
        tstl    ef_free
        beq.s   4f
        | free: test bit d3 in ef_mask
        move.l  %d3,%d1
        lsr.l   #3,%d1
        lea     ef_mask,%a0
        move.b  %a0@(0,%d1:l),%d0
        andil   #0xff,%d0
        move.l  %d3,%d1
        andil   #7,%d1
        btst    %d1,%d0
        beq.s   3f
        moveq   #1,%d7
3:      rts
4:      tstl    %d4
        beq.s   3b
        move.l  %d3,%d0
        mulu.w  %d4,%d0                 | idx * k
        remul   %d5,%d1,%d0             | d1 = (idx*k) % n
        cmpl    %d4,%d1
        bcc.s   3b
        moveq   #1,%d7
        rts

| Encoder A/B/C/D: (index @4, delta @8). A=PULSE B=ROT C=RAND VEL D=RAND PTCH.
ef_enc:
        movel   4(%sp),%d1              | encoder index
        moveq   #3,%d0
        cmpl    %d0,%d1
        bhi.s   9f                      | E-F: ignore
        movel   %d1,ef_cursor           | 0..3
        movel   8(%sp),%d0
        beq.s   9f
        bra.w   ef_nudge
9:      rts

| LEVEL encoder: (index @4, delta @8) — same ABI as TEMPO BUS / stock
| TLEVEL. Use the full signed long (panel coalesces unread detents past ±127).
ef_level:
        movel   8(%sp),%d0
        beq.w   ef_nudge_rts
        bra.w   ef_nudge
| LEFT/RIGHT enter with d0 = ±1 already. Edits PULSE or ROT only.
| ef_sync_len clobbers d0-d3/a0/a1 — park the signed delta on the stack
| first. Without that, L/R become the track index (dead on T1) and every
| encoder turn nudges upward only.
ef_nudge:
        movel   %d0,-(%sp)              | park signed delta
        bsr.w   ef_sync_len             | STEPS stays = pattern length
        movel   (%sp)+,%d2              | restore delta
        movel   ef_cursor,%d1
        lea     ef_pulses,%a0
        tstl    %d1
        beq.s   1f
        lea     ef_rot,%a0
        moveq   #1,%d0
        cmpl    %d0,%d1
        beq.s   1f
        lea     ef_velrnd,%a0
        moveq   #2,%d0
        cmpl    %d0,%d1
        beq.s   1f
        lea     ef_pitrnd,%a0           | cursor 3
1:      movel   %a0@,%d0
        addl    %d2,%d0
        movel   ef_cursor,%d1
        tstl    %d1
        bne.s   4f
        | PULSE 0..STEPS — leaves free/random mode (back to Euclid)
        clrl    ef_free
        tstl    %d0
        bpl.s   21f
        clrl    %d0
21:     movel   ef_steps,%d3
        cmpl    %d3,%d0
        ble.s   3f
        movel   %d3,%d0
        bra.s   3f
4:      moveq   #1,%d3
        cmpl    %d3,%d1
        bne.s   5f
        | ROT 0..STEPS-1 (keeps free mode)
        tstl    %d0
        bpl.s   41f
        clrl    %d0
41:     movel   ef_steps,%d3
        subql   #1,%d3
        cmpl    %d3,%d0
        ble.s   3f
        movel   %d3,%d0
        bra.s   3f
5:      | RAND VEL / RAND PTCH 0..100
        tstl    %d0
        bpl.s   51f
        clrl    %d0
51:     moveq   #100,%d3
        cmpl    %d3,%d0
        ble.s   3f
        movel   %d3,%d0
3:      movel   %d0,%a0@
        bra.w   ef_draw
ef_nudge_rts:
        rts

| ---- draw helpers (y up from bottom; TEXT limit = -1) -------------------
| ef_text: d0=x, d1=y, a0=str; a5=surf. Clobbers d0/d1/a0/a1.
ef_text:
        movel   %a0,%sp@-
        pea     -1
        movel   %d1,%sp@-
        movel   %d0,%sp@-
        movel   %a5,%sp@-
        pea     FONT
        jsr     TEXT
        lea     %sp@(24),%sp
        rts

| ef_rtext: right-align a0 at x=d0, row d1. MUST reload a0 after TWIDTH
| (tuner parks the string in a6; we park the pointer in ef_rstr).
ef_rtext:
        movel   %a0,ef_rstr
        movel   %d0,ef_rx
        movel   %d1,ef_ry
        movel   %a0,%sp@-
        pea     -1
        pea     FONT
        jsr     TWIDTH
        lea     %sp@(12),%sp
        movel   ef_rx,%d1
        subl    %d0,%d1
        tstl    %d1
        bpl.s   1f
        moveq   #0,%d1                  | clamp if wider than the box
1:      movel   %d1,%d0
        movel   ef_ry,%d1
        movel   ef_rstr,%a0
        bra.w   ef_text

| ---- draw ---------------------------------------------------------------
| EUCLID  T1
| ─────────────
|  STEPS     16     (pattern length; not editable)
| >PULSE      5
|  ROT        0
|  RAND VEL       0
|  RAND PTCH       0
| ■··■··■··■··     (preview)
ef_draw:
        tstl    ef_win
        beq.w   d9
        bsr.w   ef_sync_len             | STEPS := pattern length every paint
        lea     %sp@(-48),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   ef_win,%a2
        lea     %a2@(36),%a5
        movel   %a5,%sp@-
        jsr     CLEAR
        addql   #4,%sp

        moveq   #4,%d0
        moveq   #Y_TITLE,%d1
        lea     T_TITLE,%a0
        bsr.w   ef_text
        bsr.w   ef_fmt_tracks
        moveq   #X_VAL,%d0
        moveq   #Y_TITLE,%d1
        lea     ef_buf,%a0
        bsr.w   ef_rtext
        pea     1
        pea     WINW-4
        pea     Y_RULE
        pea     4
        movel   %a5,%sp@-
        jsr     RULE
        lea     %sp@(20),%sp

        moveq   #0,%d2
drow:   lea     L_STEPS,%a4
        moveq   #Y_ROW0,%d3
        tstl    %d2
        beq.s   dlbl
        lea     L_PULSES,%a4
        moveq   #Y_ROW1,%d3
        moveq   #1,%d0
        cmpl    %d2,%d0
        beq.s   dlbl
        lea     L_ROT,%a4
        moveq   #Y_ROW2,%d3
        moveq   #2,%d0
        cmpl    %d2,%d0
        beq.s   dlbl
        lea     L_VEL,%a4
        moveq   #Y_ROW3,%d3
        moveq   #3,%d0
        cmpl    %d2,%d0
        beq.s   dlbl
        lea     L_PIT,%a4
        moveq   #Y_ROW4,%d3
| cursor 0=PULSE .. 3=RAND PTCH; STEPS never focused
dlbl:   tstl    %d2
        beq.s   dlab
        movel   %d2,%d0
        subql   #1,%d0
        cmpl    ef_cursor,%d0
        bne.s   dlab
        moveq   #3,%d0
        movel   %d3,%d1
        lea     T_MARK,%a0
        bsr.w   ef_text
dlab:   moveq   #X_LAB,%d0
        movel   %d3,%d1
        movel   %a4,%a0
        bsr.w   ef_text

        lea     ef_steps,%a0
        tstl    %d2
        beq.s   dval
        lea     ef_pulses,%a0
        moveq   #1,%d0
        cmpl    %d2,%d0
        beq.s   dval
        lea     ef_rot,%a0
        moveq   #2,%d0
        cmpl    %d2,%d0
        beq.s   dval
        lea     ef_velrnd,%a0
        moveq   #3,%d0
        cmpl    %d2,%d0
        beq.s   dval
        lea     ef_pitrnd,%a0
dval:   movel   %a0@,-(%sp)
        lea     VFMT,%a1                | STEPS / PULSE / ROT: "%d"
        moveq   #3,%d0
        cmpl    %d0,%d2
        bcs.s   1f
        lea     VFMT_PCT,%a1            | RAND VEL / RAND PTCH: "%d%%"
1:      movel   %a1,-(%sp)
        pea     ef_buf
        jsr     SPRINTF
        lea     %sp@(12),%sp
        moveq   #X_VAL,%d0
        movel   %d3,%d1
        lea     ef_buf,%a0
        bsr.w   ef_rtext

        addql   #1,%d2
        moveq   #5,%d0
        cmpl    %d0,%d2
        bcs.w   drow

        bsr.w   ef_draw_pat

        moveq   #1,%d0
        movel   %d0,SCRDIRTY
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(48),%sp
d9:     rts

| ef_fmt_tracks: write "T135" (1-based) for ef_targets into ef_buf.
ef_fmt_tracks:
        lea     ef_buf,%a0
        moveb   #0x54,%a0@+             | 'T'
        moveq   #0,%d2
        movel   ef_targets,%d3
        bne.s   1f
        moveb   #0x2d,%a0@+             | '-'
        clrb    %a0@
        rts
1:      btst    %d2,%d3
        beq.s   2f
        moveq   #0x31,%d0               | '1'
        addl    %d2,%d0
        moveb   %d0,%a0@+
2:      addql   #1,%d2
        moveq   #8,%d0
        cmpl    %d0,%d2
        bcs.s   1b
        clrb    %a0@
        rts

| ef_draw_pat: bar of n cells; a5 = surf. Euclid or free+rot via ef_hit.
ef_draw_pat:
        movel   ef_steps,%d5
        moveq   #1,%d0
        cmpl    %d0,%d5
        bge.s   p1
        moveq   #1,%d5
p1:     moveq   #64,%d0
        cmpl    %d0,%d5
        ble.s   p2
        moveq   #64,%d5
p2:     movel   ef_pulses,%d4
        tstl    %d4
        bpl.s   p3
        clrl    %d4
p3:     cmpl    %d5,%d4
        ble.s   p4
        movel   %d5,%d4
p4:     movel   ef_rot,%d6
        tstl    %d6
        bpl.s   p5
        clrl    %d6
p5:     cmpl    %d5,%d6
        bcs.s   p6
        clrl    %d6
p6:     moveq   #0,%d2                  | step i
ploop:
        | x0 = 4 + i*(WINW-8)/n
        movel   %d2,%d0
        moveq   #WINW-8,%d1
        mulu.w  %d1,%d0
        divul   %d5,%d0                 | 32/32 like tuner.s
        addql   #4,%d0
        movel   %d0,%a1                 | park x0
        | x1 = 4 + (i+1)*(WINW-8)/n - 2
        movel   %d2,%d1
        addql   #1,%d1
        moveq   #WINW-8,%d3
        mulu.w  %d3,%d1
        divul   %d5,%d1
        addql   #2,%d1
        movel   %d1,%a2                 | park x1
        bsr.w   ef_hit                  | d7 = on/off
        movel   %a1,%d0                 | x0
        movel   %a2,%d1                 | x1
        cmpl    %d0,%d1
        bge.s   pbox
        movel   %d0,%d1                 | at least 1 px wide
pbox:   tstl    %d7
        beq.s   prest
        pea     1
        pea     Y_PAT+PAT_H
        movel   %d1,%sp@-
        pea     Y_PAT
        movel   %d0,%sp@-
        movel   %a5,%sp@-
        jsr     BOX
        lea     %sp@(24),%sp
        bra.s   pnext
prest:  pea     1
        pea     Y_PAT+1
        movel   %d1,%sp@-
        pea     Y_PAT
        movel   %d0,%sp@-
        movel   %a5,%sp@-
        jsr     BOX
        lea     %sp@(24),%sp
pnext:  addql   #1,%d2
        cmpl    %d5,%d2
        bcs.w   ploop
        rts

| ---- fill: Euclidean trigs + optional AMP VOL locks on ef_targets ------
ef_fill:
        bsr.w   ef_sync_len             | n = pattern length
        lea     %sp@(-36),%sp
        movem.l %d2-%d7/%a2-%a4,%sp@
        movel   ef_targets,%d7
        beq.w   fout
        moveal  DBPTR,%a2
        moveq   #0,%d2
        moveb   UI_PTN,%d2
        movel   #PTN_STR,%d0
        mulu.l  %d0,%d2
        addal   %d2,%a2                 | a2 = pattern base in blob

        movel   ef_steps,%d5
        moveq   #1,%d0
        cmpl    %d0,%d5
        bge.s   1f
        moveq   #1,%d5
1:      moveq   #64,%d0
        cmpl    %d0,%d5
        ble.s   2f
        moveq   #64,%d5
2:      movel   ef_pulses,%d4
        tstl    %d4
        bpl.s   3f
        clrl    %d4
3:      cmpl    %d5,%d4
        ble.s   4f
        movel   %d5,%d4
4:      movel   ef_rot,%d3
        tstl    %d3
        bpl.s   5f
        clrl    %d3
5:      cmpl    %d5,%d3
        bcs.s   6f
        clrl    %d3
6:      movel   %d3,%d6                 | rot

        moveq   #0,%d2                  | track
tloop:  btst    %d2,%d7
        jbeq    tnext                   | ColdFire: no Bcc.W; jcc picks size
        movel   %d2,%d0
        movel   #TRK_STR,%d1
        mulu.l  %d1,%d0
        lea     %a2@(0,%d0:l),%a3       | a3 = TRAC
        movel   %d2,ef_trk              | track for PTCH encoding (synth vs sample)
        movel   %d5,-(%sp)
        movel   %d4,-(%sp)
        movel   %d6,-(%sp)
        movel   %a3,-(%sp)
        bsr.w   ef_write_mask
        lea     %sp@(16),%sp
        | battery mirror: mask 0 (8 B) + VOL/PTCH locks on rewritten steps
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulu.l  %d1,%d0
        movel   %d2,%d1
        movel   #TRK_STR,%d3
        mulu.l  %d3,%d1
        addl    %d1,%d0
        addil   #MIRROR,%d0
        moveal  %d0,%a4
        moveq   #7,%d0
mcopy:  moveb   %a3@(0,%d0:l),%d1
        moveb   %d1,%a4@(0,%d0:l)
        subql   #1,%d0
        bpl.s   mcopy
        | mirror VOL + PTCH lock bytes for steps 0..n-1 (d5 = n)
        moveq   #0,%d0
mvloop: cmpl    %d5,%d0
        jbcc    tnext
        movel   %d0,%d1
        lsll    #5,%d1
        addil   #LOCK0+LOCK_VOL,%d1
        moveb   %a3@(0,%d1:l),%d3
        moveb   %d3,%a4@(0,%d1:l)
        movel   %d0,%d1
        lsll    #5,%d1
        addil   #LOCK0+LOCK_PTCH,%d1
        moveb   %a3@(0,%d1:l),%d3
        moveb   %d3,%a4@(0,%d1:l)
        addql   #1,%d0
        bra.s   mvloop
tnext:  addql   #1,%d2
        moveq   #8,%d0
        cmpl    %d0,%d2
        jbcs    tloop

        moveal  DBPTR,%a0
        addal   #DIRTY_OFF,%a0
        moveq   #1,%d0
        movel   %d0,%a0@
        moveal  #DIRTY_G,%a0
        movel   %d0,%a0@
        jsr     NOTIFY
fout:   movem.l %sp@,%d2-%d7/%a2-%a4
        lea     %sp@(36),%sp
        rts

| ef_write_mask(trac, rot, k, n) -- stack args after bsr. Clears then sets
| hits on steps 0..n-1 of mask 0 (Euclid or free+rot via ef_hit).
| RAND VEL>0: AMP VOL = 64-(r*pct)/100, r in 0..63 (display -63..0).
| RAND PTCH>0: every hit gets an in-scale PTCH lock within ±rad (range knob);
| else clear PTCH. Leaves n..63 alone.
ef_write_mask:
        lea     -28(%sp),%sp
        movem.l %d2-%d7/%a2,(%sp)
        moveal  32(%sp),%a2             | 28 + 4 return = 32
        movel   36(%sp),%d6             | rot
        movel   40(%sp),%d4             | k
        movel   44(%sp),%d5             | n
        moveq   #0,%d2
1:      cmpl    %d5,%d2
        bcc.w   9f
        bsr.w   ef_bit_addr
        moveb   %a0@,%d1
        move.l  %d0,%d3
        not.l   %d3
        and.l   %d3,%d1
        moveb   %d1,%a0@
        bsr.w   ef_hit
        tstl    %d7
        beq.w   7f
        bsr.w   ef_bit_addr
        moveb   %a0@,%d1
        or.l    %d0,%d1
        moveb   %d1,%a0@
        | RAND VEL > 0 -> VOL in 1..64 (display -63..0); else clear VOL lock
        movel   ef_velrnd,%d3
        tstl    %d3
        beq.s   6f
        bsr.w   ef_rng
        andil   #0x3f,%d0               | r = 0..63
        mulu.w  %d3,%d0                 | r*pct
        moveq   #100,%d1
        divu.l  %d1,%d0                 | (r*pct)/100 = drop 0..63
        moveq   #64,%d1
        subl    %d0,%d1                 | VOL = 64 - drop (1..64)
        movel   %d1,%d0
        bra.s   5f
6:      moveq   #-1,%d0                 | 0xff = no lock
5:      movel   %d2,%d1
        lsll    #5,%d1
        addil   #LOCK0+LOCK_VOL,%d1
        moveb   %d0,%a2@(0,%d1:l)
        | RAND PTCH: range → in-scale PTCH lock on every hit
        bsr.w   ef_write_ptch
        bra.s   8f
7:      | no hit: clear VOL + PTCH locks on this step
        moveq   #-1,%d0
        movel   %d2,%d1
        lsll    #5,%d1
        addil   #LOCK0+LOCK_VOL,%d1
        moveb   %d0,%a2@(0,%d1:l)
        movel   %d2,%d1
        lsll    #5,%d1
        addil   #LOCK0+LOCK_PTCH,%d1
        moveb   %d0,%a2@(0,%d1:l)
8:      addql   #1,%d2
        bra.w   1b
9:      movem.l (%sp),%d2-%d7/%a2
        lea     28(%sp),%sp
        rts

| ef_write_ptch: on hit step d2 / trac a2.
| RAND PTCH=0 / no quantizer / SCALE OFF -> clear PTCH.
| Else rad = max(1, max_rad*pct/100): EVERY hit gets a lock (range, not
| probability — a probability left most hits on the Part root).
| Pick uniform among st in [-rad..+rad] whose absolute PC (ROOT+st) mod 12
| is in SCALE_AT (PTCH 64 = scale root, same as po_snap).
| FM/SY: raw=64+st (max_rad=PIT_RAD). Sample: raw=64+5·st (max_rad=PIT_SAMP).
| Clamp raw to 0..127 before store (sample encode of |st|>12 wrapped to a
| byte the Part clamp turned into 0 = display -64 on synth).
| Caller keeps n in d5 and rot in d6 — park across the pick.
ef_write_ptch:
        movel   ef_pitrnd,%d3           | pct 0..100
        tstl    %d3
        beq.w   ep_clear
        move.w  SCALE_AT,%d0
        andil   #0xffff,%d0
        move.l  #0x4ef9,%d1
        cmpl    %d1,%d0
        bne.w   ep_clear
        movel   %d2,-(%sp)
        movel   %d3,-(%sp)
        movel   %d4,-(%sp)
        movel   %d5,-(%sp)
        movel   %d6,-(%sp)
        movel   %d7,-(%sp)
        jsr     SCALE_AT                | d0 = mask (0 = OFF)
        movel   (%sp)+,%d7
        movel   (%sp)+,%d6
        movel   (%sp)+,%d5
        movel   (%sp)+,%d4
        movel   (%sp)+,%d3
        movel   (%sp)+,%d2
        tstl    %d0
        beq.w   ep_clear
        movel   %d2,-(%sp)              | park step
        movel   %d5,-(%sp)              | park n
        movel   %d6,-(%sp)              | park rot
        movel   %d4,-(%sp)              | park pulses
        movel   %d0,%d7                 | mask
        bsr.w   ef_is_synth
        moveq   #PIT_RAD,%d4            | max_rad
        tstl    %d0
        bne.s   1f
        moveq   #PIT_SAMP,%d4
1:      movel   %d0,-(%sp)              | park is_synth
        | rad = max(1, max_rad * pct / 100)
        movel   %d4,%d0
        mulu.w  %d3,%d0
        moveq   #100,%d1
        divu.l  %d1,%d0
        tstl    %d0
        bne.s   2f
        moveq   #1,%d0
2:      movel   %d0,%d4                 | d4 = rad
        moveq   #0,%d0
        moveb   NV_ROOT,%d0
        movel   %d0,%d6                 | d6 = ROOT
        | count st in [-rad..+rad] with (ROOT+st)%12 in mask
        moveq   #0,%d3
        move.l  %d4,%d1
        negl    %d1                     | d1 = st = -rad
ep_cnt: move.l  %d1,%d0
        addl    %d6,%d0                 | ROOT+st
ep_cm:  tstl    %d0
        bpl.s   ep_cp
        addil   #12,%d0
        bra.s   ep_cm
ep_cp:  moveq   #12,%d5
        cmpl    %d5,%d0
        bcs.s   ep_ck
        subl    %d5,%d0
        bra.s   ep_cp
ep_ck:  btst    %d0,%d7
        beq.s   ep_cn
        addql   #1,%d3
ep_cn:  addql   #1,%d1
        move.l  %d4,%d0
        addql   #1,%d0                  | rad+1
        cmpl    %d0,%d1
        blt.w   ep_cnt                  | while st <= rad  (st < rad+1)
        tstl    %d3
        beq.w   ep_clear_rad
        | rank = rng % count
        bsr.w   ef_rng
        move.l  %d0,%d1
        movel   %d3,%d5
        remul   %d5,%d0,%d1             | d0 = rank
        move.l  %d0,%d3
        move.l  %d4,%d1
        negl    %d1                     | st = -rad
        moveq   #0,%d5                  | cursor
ep_pk:  move.l  %d4,%d0
        addql   #1,%d0
        cmpl    %d0,%d1
        bge.w   ep_clear_rad
        move.l  %d1,%d0
        addl    %d6,%d0
ep_pm:  tstl    %d0
        bpl.s   ep_pp
        addil   #12,%d0
        bra.s   ep_pm
ep_pp:  moveq   #12,%d2
        cmpl    %d2,%d0
        bcs.s   ep_pq
        subl    %d2,%d0
        bra.s   ep_pp
ep_pq:  btst    %d0,%d7
        beq.s   ep_ps
        cmpl    %d3,%d5
        beq.s   ep_got
        addql   #1,%d5
ep_ps:  addql   #1,%d1
        bra.s   ep_pk
ep_got: | d1 = st; encode
        move.l  %d1,%d3                 | st
        movel   (%sp)+,%d0              | is_synth
        tstl    %d0
        beq.s   ep_samp
        moveq   #64,%d0
        addl    %d3,%d0                 | synth: 64+st
        bra.s   ep_clamp
ep_samp: move.l  %d3,%d0
        moveq   #5,%d1
        muls.l  %d1,%d0
        addi.l  #64,%d0                 | sample: 64+5·st
ep_clamp: tstl    %d0
        bpl.s   ep_chi
        moveq   #0,%d0
ep_chi: moveq   #127,%d1
        cmpl    %d1,%d0
        ble.s   ep_ok
        moveq   #127,%d0
ep_ok:  movel   (%sp)+,%d4              | pulses
        movel   (%sp)+,%d6              | rot
        movel   (%sp)+,%d5              | n
        movel   (%sp)+,%d2              | step
        bra.s   ep_store
ep_clear_rad:
        movel   (%sp)+,%d0              | drop is_synth
        movel   (%sp)+,%d4
        movel   (%sp)+,%d6
        movel   (%sp)+,%d5
        movel   (%sp)+,%d2
        moveq   #-1,%d0
        bra.s   ep_store
ep_clear:
        moveq   #-1,%d0
ep_store:
        movel   %d2,%d1
        lsll    #5,%d1
        addil   #LOCK0+LOCK_PTCH,%d1
        moveb   %d0,%a2@(0,%d1:l)
        rts

| ef_is_synth: d0 := 1 when ef_trk's Part NEIGHBOR sig is "FM",1 or "SY",1
| (machine-list synth; same encoding as qz_fmtrack). Else 0. Clobbers
| d0/d1/a0/a1 only — caller parks what it needs.
ef_is_synth:
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_BANK,%d0
        move.l  #PART_STR,%d1
        muls.l  %d1,%d0
        addal   %d0,%a0                 | Part
        move.l  ef_trk,%d0
        mulu.w  #30,%d0
        lea     %a0@(0,%d0:l),%a1
        addal   #SIG_OFF,%a1            | NEIGHBOR column
        moveq   #0,%d0
        moveb   2(%a1),%d0
        subql   #1,%d0
        bne.s   eis_no                  | not kind 1
        moveq   #0,%d0
        movew   (%a1),%d0
        cmpil   #0x464d,%d0             | "FM"
        beq.s   eis_yes
        cmpil   #0x5359,%d0             | "SY"
        bne.s   eis_no
eis_yes: moveq   #1,%d0
        rts
eis_no: moveq   #0,%d0
        rts

| d2=step, a2=trac -> a0=&byte, d0=bitmask. Clobbers d0,d1,a0.
ef_bit_addr:
        movel   %d2,%d1
        lsr.l   #3,%d1
        moveq   #7,%d0
        subl    %d1,%d0
        lea     %a2@(0,%d0:l),%a0
        movel   %d2,%d1
        andil   #7,%d1
        moveq   #1,%d0
        lsll    %d1,%d0
        rts

| ---- layer --------------------------------------------------------------
        .balign 4
EF_LAYER:
        .long   0, EF_KEYS, EF_ENCS, 0, 0, -1, -1
EF_KEYS:
        .byte   0x1b, 0                 | PAGE closes
        .long   ef_close, 0, 0, 0, 0
        .word   0, 0
        .byte   0x31, 0                 | YES
        .long   ef_yes, 0, 0, 0, 0
        .word   0, 0
        .byte   0x32, 0                 | NO
        .long   ef_no, 0, 0, 0, 0
        .word   0, 0
        .byte   0x33, 0                 | UP
        .long   ef_up, 0, 0, 0, 0
        .word   0, 0
        .byte   0x20, 0                 | DOWN
        .long   ef_down, 0, 0, 0, 0
        .word   0, 0
        .byte   0x34, 0                 | LEFT
        .long   ef_left, 0, 0, 0, 0
        .word   0, 0
        .byte   0x21, 0                 | RIGHT
        .long   ef_right, 0, 0, 0, 0
        .word   0, 0
        .byte   0x2a, 0                 | CUE = random PULSE
        .long   ef_cue, 0, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
EF_ENCS:
        .byte   0, 0                    | A = PULSE
        .long   ef_enc, 0, 0, 0, 0
        .byte   1, 0                    | B = ROT
        .long   ef_enc, 0, 0, 0, 0
        .byte   2, 0                    | C = RAND VEL
        .long   ef_enc, 0, 0, 0, 0
        .byte   3, 0                    | D = RAND PTCH
        .long   ef_enc, 0, 0, 0, 0
        .byte   6, 0                    | LEVEL = focused row
        .long   ef_level, 0, 0, 0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0

T_TITLE:  .asciz "EUCLID"
T_FILLED: .asciz "EUCLID FILL"
T_MARK:   .asciz ">"
L_STEPS:  .asciz "STEPS"
L_PULSES: .asciz "PULSE (A)"
L_ROT:    .asciz "ROT (B)"
L_VEL:    .asciz "RAND VEL (C)"
L_PIT:    .asciz "RAND PTCH (D)"
VFMT:     .asciz "%d"
VFMT_PCT: .asciz "%d%%"
        .balign 4

        .data
        .balign 4
        .globl  ef_win, ef_steps, ef_pulses, ef_rot, ef_velrnd, ef_pitrnd
        .globl  ef_cursor, ef_targets
ef_win:     .long 0
ef_steps:   .long 16
ef_pulses:  .long 5                     | match filter EUCLID default
ef_rot:     .long 0
ef_velrnd:  .long 0                     | 0..100; 0 = no AMP VOL lock
ef_pitrnd:  .long 0                     | 0..100; prob of in-scale PTCH lock
ef_cursor:  .long 0
ef_targets: .long 0
ef_rng_state: .long 0                   | LCG; 0 -> seed from tempo/clock
ef_free:    .long 0                     | nonzero: draw/write ef_mask + ROT
ef_mask:    .space 8                    | free pattern bits 0..63
ef_trk:     .long 0                     | current fill target track (0..7)
ef_rx:      .long 0
ef_ry:      .long 0
ef_rstr:    .long 0
ef_buf:     .space 24
