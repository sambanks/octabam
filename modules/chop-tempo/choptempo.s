| LAZY CHOP TEMPO -- one DRAM unit. GNU as, ColdFire (m68k-elf-as -mcpu=54455). (8thmyth, Nov 2026)
|
| After YES in LAZY CHOP: the slice-count popup as before, then the tempo the
| chops point to, "BPM 115 (58)", until the next key. Nothing is written to the
| sample. The reading is tools/hw/chop_tempo.py's unit_display in whole numbers
| (tools/hw/chop_tempo_int.py, the reference this code matches line for line):
|
|  1. the gaps between the slices (over 0.04 s; a gap over 6 s counts as 6 s);
|  2. every tempo 60.0..200.0 BPM in 0.1 steps scored by how the gaps sit on its
|     16th / triplet-16th grid (a cos table), times a prior around 120 BPM; the
|     octave by the prior; the runner-up gives a confidence;
|  3. the take's length counts only when it ends on the chops' grid (a loop),
|     and then a whole number of bars confirms and refines the tempo;
|  4. a 4:3 / 3:2 neighbour that explains the chops as plain beats much better
|     replaces the first pick; one that explains them as plainly goes in the
|     brackets (with a dot for the 3:2 dotted / triplet reading), else the
|     half or double tempo.
|
| Tempos are centi-BPM (c = 100 x BPM); positions and gaps samples at 44.1 kHz;
| fixed point Q14 (16384 = 1.0). The tables (cos, prior, loop agreement) come
| from the manifest's remix.inc, computed as the reference computes them.
|
| Entry points:
|  ct_after_yes  a0 = the chopped slot's record; called by LAZY CHOP at YES
|                (built with LC_TEMPO) after its slice-count popup.
|  ct_tick       stands in for `subq.l #1,%d0 ; move.l %d0,0x460d1e6c` in the
|                UI task's 1/60 s popup countdown 0x40056c28: when the
|                slice-count popup's countdown ends, the tempo popup goes up
|                with a long one; any key that changes (pressed or released)
|                ends it, and the key does its own job as well. A popup
|                someone else puts up meanwhile is left alone. State 3 is the
|                gate's way in (ct_req = a record; the line, no popup).
|
| Register use: d0-d1/a0-a1 scratch (C convention); a routine that uses more
| saves them with the lea/movem frame (no pre-decrement movem).

        .include "remix.inc"            | ct_cos, ct_prior_t, ct_la_t

        .equ    Q,          16384
        .equ    C_LO,       6000
        .equ    C_HI,       20000
        .equ    MIN_GAP,    1764        | 0.04 s
        .equ    MAX_GAP,    264600      | 6 s
        .equ    MAX_LEN,    3000000     | longer: no loop of 16 bars or fewer at 60 BPM and up
        .equ    D16,        16537500    | 60 * 44100 * 100 / 16: one beat, gaps >> 4
        .equ    D16_HALF,   8268750
        .equ    D16_IDX,    16149       | D16 / 1024
        .equ    D8_U,       8075        | (60 * 44100 * 100 / 8) >> 12: gaps >> 3 to beats, Q12
        .equ    LA_FLOOR,   2458        | 0.15 x Q
        .equ    NU,         11          | structure units
        .equ    REC_TRIM_S, 300
        .equ    REC_TRIM_E, 304
        .equ    REC_SLICES, 312
        .equ    REC_COUNT,  1092
        .equ    COUNTDOWN,  0x460d1e6c  | the popup countdown (1/60 s ticks)
        .equ    KEYROWS,    0x46100b18  | 8 bytes: the key matrix rows, a bit a held key
        .equ    F_TOAST,    0x4005a2b8  | (text, duration)
        .equ    F_SPRINTF,  0x40013a08

        .text

| ---- entry: LAZY CHOP's YES ------------------------------------------------
        .global ct_after_yes
ct_after_yes:
        lea     -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        clr.l   ct_state
        bsr     ct_prep
        bsr     ct_compute              | d0: 1 = a line in ct_buf
        tst.l   %d0
        beq     1f
        moveq   #1,%d0
        move.l  %d0,ct_state
1:      movem.l (%sp),%d0-%d7/%a0-%a6
        lea     60(%sp),%sp
        rts

| ---- entry: the UI task's popup countdown ----------------------------------
| In: d0 = the countdown as read (non-zero). Out: d0 = the new countdown,
| stored, with the flags of a tst.l on it (stock's bne follows).
        .global ct_tick
ct_tick:
        subq.l  #1,%d0
        lea     -56(%sp),%sp
        movem.l %d1-%d7/%a0-%a6,(%sp)
        move.l  ct_state,%d1
        beq     9f
        cmp.l   #3,%d1
        beq     7f
        cmp.l   #1,%d1
        bne     2f
        tst.l   %d0                     | state 1: the slice-count popup ends now?
        bne     9f
        pea     0x7fff.w                | about 9 minutes: until a key
        pea     ct_buf
        jsr     (F_TOAST).l             | the tempo popup (it sets the countdown)
        addq.l  #8,%sp
        lea     ct_keys,%a0
        move.l  KEYROWS,%d1
        move.l  %d1,(%a0)
        move.l  KEYROWS+4,%d1
        move.l  %d1,4(%a0)
        moveq   #2,%d1
        move.l  %d1,ct_state
        move.l  COUNTDOWN,%d0
        move.l  %d0,ct_cd
        bra     9f
2:      move.l  ct_cd,%d1               | state 2: still ours (a toast resets the countdown)?
        subq.l  #1,%d1
        cmp.l   %d1,%d0
        bne     4f                      | another popup: leave it, forget ours
        move.l  %d0,ct_cd
        lea     ct_keys,%a0
        move.l  KEYROWS,%d1             | a key changed since it went up?
        cmp.l   (%a0),%d1
        bne     3f
        move.l  KEYROWS+4,%d1
        cmp.l   4(%a0),%d1
        bne     3f
        tst.l   %d0
        bne     9f
        bra     4f                      | ran out by itself
3:      moveq   #0,%d0                  | close it this tick (stock's own close follows)
4:      clr.l   ct_state
        bra     9f
7:      move.l  %d0,-(%sp)              | state 3: the gate's request
        move.l  ct_req,%a0
        bsr     ct_prep
        bsr     ct_compute
        move.l  %d0,ct_ok
        clr.l   ct_state
        move.l  (%sp)+,%d0
9:      movem.l (%sp),%d1-%d7/%a0-%a6
        lea     56(%sp),%sp
        move.l  %d0,COUNTDOWN
        tst.l   %d0
        rts

| ---- the slices -> positions, length, gaps ----------------------------------
| a0 = the record. ct_len = trim end - trim start; ct_pos = the slice starts
| from the trim start, sorted, without repeats (ct_np); ct_gaps = the gaps
| over MIN_GAP, capped at MAX_GAP (ct_n); ct_sg = the gaps sorted.
ct_prep:
        lea     -20(%sp),%sp
        movem.l %d2-%d5/%a2,(%sp)
        move.l  REC_TRIM_E(%a0),%d0
        move.l  REC_TRIM_S(%a0),%d3
        sub.l   %d3,%d0
        move.l  %d0,ct_len
        move.l  REC_COUNT(%a0),%d2
        cmp.l   #64,%d2
        bls     1f
        moveq   #64,%d2
1:      lea     REC_SLICES(%a0),%a1
        lea     ct_tmp,%a2
        move.l  %d2,%d4
        beq     3f
2:      move.l  (%a1),%d0
        lea     12(%a1),%a1
        sub.l   %d3,%d0
        bpl     21f
        moveq   #0,%d0
21:     move.l  %d0,(%a2)+
        subq.l  #1,%d4
        bne     2b
3:      lea     ct_tmp,%a0
        move.l  %d2,%d0
        bsr     ct_sort
        lea     ct_tmp,%a1              | without repeats
        lea     ct_pos,%a2
        clr.l   %d4
        moveq   #-1,%d5
        move.l  %d2,%d1
        beq     5f
4:      move.l  (%a1)+,%d0
        cmp.l   %d5,%d0
        beq     41f
        move.l  %d0,(%a2)+
        move.l  %d0,%d5
        addq.l  #1,%d4
41:     subq.l  #1,%d1
        bne     4b
5:      move.l  %d4,ct_np
        lea     ct_pos,%a1
        lea     ct_gaps,%a2
        clr.l   %d2
        subq.l  #1,%d4
        ble     7f
6:      move.l  4(%a1),%d0
        sub.l   (%a1),%d0
        addq.l  #4,%a1
        cmp.l   #MIN_GAP,%d0
        ble     61f
        cmp.l   #MAX_GAP,%d0
        ble     60f
        move.l  #MAX_GAP,%d0
60:     move.l  %d0,(%a2)+
        addq.l  #1,%d2
61:     subq.l  #1,%d4
        bne     6b
7:      move.l  %d2,ct_n
        lea     ct_gaps,%a1
        lea     ct_sg,%a2
        move.l  %d2,%d1
        beq     9f
8:      move.l  (%a1)+,(%a2)+
        subq.l  #1,%d1
        bne     8b
9:      lea     ct_sg,%a0
        move.l  %d2,%d0
        bsr     ct_sort
        movem.l (%sp),%d2-%d5/%a2
        lea     20(%sp),%sp
        rts

| insertion sort, ascending, signed: a0 = longs, d0 = count. Clobbers d0-d1.
ct_sort:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        move.l  %d0,%d2                 | n
        moveq   #1,%d3                  | i
1:      cmp.l   %d2,%d3
        bge     5f
        move.l  (%a0,%d3.l*4),%d0       | key
        move.l  %d3,%d4                 | j
2:      tst.l   %d4
        beq     4f
        move.l  -4(%a0,%d4.l*4),%d1
        cmp.l   %d0,%d1
        ble     4f
        move.l  %d1,(%a0,%d4.l*4)
        subq.l  #1,%d4
        bra     2b
4:      move.l  %d0,(%a0,%d4.l*4)
        addq.l  #1,%d3
        bra     1b
5:      movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| ---- the whole reading -> ct_buf; d0 = 1 when there is a line --------------
        .global ct_compute
ct_compute:
        move.l  ct_n,%d0
        cmp.l   #2,%d0
        bge     1f
        moveq   #0,%d0
        rts
1:      lea     -20(%sp),%sp
        movem.l %d2-%d5/%a2,(%sp)
        bsr     ct_rows                 | r at every 0.1 BPM, once
        bsr     ct_reading              | -> rd_c, rd_alt
        bsr     ct_plainer              | -> rd_c, rd_alt (maybe replaced)
        move.l  rd_c,%d0
        bsr     ct_also                 | -> d0 = the neighbour, 0 = none
        move.l  rd_c,%d2                | c
        clr.l   ct_dot
        tst.l   %d0
        beq     5f
        move.l  %d0,%d3                 | nb
        move.l  %d3,%d4
        lsr.l   #1,%d4                  | br = nb // 2
        move.l  %d3,%d0                 | nb nearer c than br?
        move.l  %d4,%d1
        bsr     ct_closer
        tst.l   %d0
        beq     2f
        move.l  %d3,%d4
2:      move.l  %d3,%d5
        add.l   %d5,%d5                 | 2 nb nearer?
        move.l  %d5,%d0
        move.l  %d4,%d1
        bsr     ct_closer
        tst.l   %d0
        beq     3f
        move.l  %d5,%d4
3:      move.l  %d4,%d0                 | dot: |100 br - 150 c| < 4 c
        moveq   #100,%d1
        mulu.l  %d1,%d0
        move.l  %d2,%d1
        move.l  #150,%d5
        mulu.l  %d5,%d1
        sub.l   %d1,%d0
        bpl     31f
        neg.l   %d0
31:     move.l  %d2,%d1
        lsl.l   #2,%d1
        cmp.l   %d1,%d0
        blt     4f
        move.l  %d4,%d0                 | or |300 br - 200 c| < 9 c
        move.l  #300,%d1
        mulu.l  %d1,%d0
        move.l  %d2,%d1
        move.l  #200,%d5
        mulu.l  %d5,%d1
        sub.l   %d1,%d0
        bpl     32f
        neg.l   %d0
32:     move.l  %d2,%d1
        moveq   #9,%d5
        mulu.l  %d5,%d1
        cmp.l   %d1,%d0
        bge     6f
4:      moveq   #1,%d0
        move.l  %d0,ct_dot
        bra     6f
5:      move.l  rd_alt,%d4              | no neighbour: half or double
6:      cmp.l   #C_HI,%d4
        ble     7f
        lsr.l   #1,%d4
7:      move.l  %d2,ct_c
        move.l  %d4,ct_br
        move.l  %d2,%d0
        bsr     ct_round
        move.l  %d0,%d2
        move.l  %d4,%d0
        bsr     ct_round
        move.l  %d0,%d4
        lea     fmt_line,%a0
        tst.l   ct_dot
        beq     8f
        lea     fmt_dot,%a0
8:      move.l  %d4,-(%sp)
        move.l  %d2,-(%sp)
        move.l  %a0,-(%sp)
        pea     ct_buf
        jsr     (F_SPRINTF).l
        lea     16(%sp),%sp
        .global ct_cdone
ct_cdone:
        movem.l (%sp),%d2-%d5/%a2
        lea     20(%sp),%sp
        moveq   #1,%d0
        rts

| d0 = c -> d0 = whole BPM, an exact .50 to the even one
ct_round:
        move.l  %d2,-(%sp)
        moveq   #100,%d1
        remu.l  %d1,%d2:%d0             | d2 = c % 100
        divu.l  %d1,%d0
        cmp.l   #50,%d2
        bgt     1f
        blt     2f
        btst    #0,%d0
        beq     2f
1:      addq.l  #1,%d0
2:      move.l  (%sp)+,%d2
        rts

| d0 = a, d1 = b, d2 = t -> d0 = 1 when a is nearer t than b, as a ratio
ct_closer:
        lea     -16(%sp),%sp
        movem.l %d3-%d6,(%sp)
        move.l  %d0,%d3                 | a: hi d3, lo d4
        move.l  %d2,%d4
        cmp.l   %d2,%d0
        bcc     1f
        move.l  %d2,%d3
        move.l  %d0,%d4
1:      move.l  %d1,%d5                 | b: hi d5, lo d6
        move.l  %d2,%d6
        cmp.l   %d2,%d1
        bcc     2f
        move.l  %d2,%d5
        move.l  %d1,%d6
2:      mulu.l  %d6,%d3                 | ahi * blo
        mulu.l  %d4,%d5                 | bhi * alo
        moveq   #0,%d0
        cmp.l   %d5,%d3
        bcc     3f
        moveq   #1,%d0
3:      movem.l (%sp),%d3-%d6
        lea     16(%sp),%sp
        rts

| ---- how well the gaps sit on c's grid: d0 = c -> d0 = r (Q14, signed) ----
ct_r_at:
        lea     -36(%sp),%sp
        movem.l %d2-%d7/%a2-%a4,(%sp)
        move.l  %d0,%d7                 | c
        move.l  #D16,%d2
        moveq   #4,%d6                  | sub
        move.l  #0x80000000,%d5         | best
        lea     ct_cos,%a3
        lea     ct_simple,%a4
1:      clr.l   %d4                     | the sum
        lea     ct_gaps,%a2
        move.l  ct_n,%d3
2:      move.l  (%a2)+,%d0
        lsr.l   #4,%d0
        mulu.l  %d7,%d0
        mulu.l  %d6,%d0                 | p = (gap >> 4) * c * sub (< 2^32 up to c = 30900)
        move.l  %d0,%d1
        add.l   #D16_HALF,%d1
        divu.l  %d2,%d1                 | k = round(p / D16): whole grid steps
        move.l  #141,%a0                | 5, 7, 9 ... steps: 0.55
        cmp.l   #32,%d1
        bhi     3f
        tst.b   (%a4,%d1.l)
        beq     3f
        move.l  #256,%a0                | a plausible chop
3:      remu.l  %d2,%d1:%d0             | d1 = p % D16
        move.l  #D16_IDX,%d0
        divu.l  %d0,%d1
        and.l   #1023,%d1
        move.w  (%a3,%d1.l*2),%d0
        ext.l   %d0
        move.l  %a0,%d1
        muls.l  %d1,%d0
        add.l   %d0,%d4
        subq.l  #1,%d3
        bne     2b
        move.l  ct_n,%d0
        lsl.l   #8,%d0                  | n * 256
        divs.l  %d0,%d4                 | r, towards zero
        cmp.l   #6,%d6
        bne     5f
        moveq   #9,%d0
        muls.l  %d0,%d4
        moveq   #10,%d0
        divs.l  %d0,%d4                 | triplets: x 0.9, towards zero
5:      cmp.l   %d5,%d4
        ble     6f
        move.l  %d4,%d5
6:      cmp.l   #6,%d6
        beq     7f
        moveq   #6,%d6
        bra     1b
7:      move.l  %d5,%d0
        movem.l (%sp),%d2-%d7/%a2-%a4
        lea     36(%sp),%sp
        rts

| ---- r at every row (6000 + 10 i), into ct_r -------------------------------
ct_rows:
        lea     -8(%sp),%sp
        movem.l %d2/%a2,(%sp)
        lea     ct_r,%a2
        move.l  #C_LO,%d2
1:      move.l  %d2,%d0
        bsr     ct_r_at
        move.w  %d0,(%a2)+
        add.l   #10,%d2
        cmp.l   #C_HI,%d2
        ble     1b
        movem.l (%sp),%d2/%a2
        lea     8(%sp),%sp
        rts

| d0 = c -> d0 = prior (Q14), the nearest 0.1 BPM row, clamped
ct_prior:
        sub.l   #5995,%d0
        bpl     1f
        moveq   #0,%d0
        bra     2f
1:      moveq   #10,%d1
        divu.l  %d1,%d0
        cmp.l   #1400,%d0
        bls     2f
        move.l  #1400,%d0
2:      lea     ct_prior_t,%a0
        move.w  (%a0,%d0.l*2),%d0
        and.l   #0xffff,%d0
        rts

| d0 = c -> d0 = how well ct_glen is a whole number of bars at c (Q14; Q when ct_glen is 0)
ct_la:
        move.l  ct_glen,%d1
        bne     1f
        move.l  #Q,%d0
        rts
1:      lea     -20(%sp),%sp
        movem.l %d2-%d6,(%sp)
        lsr.l   #4,%d1
        mulu.l  %d0,%d1                 | q = (length >> 4) * c
        move.l  #0x7fffffff,%d5         | best
        lea     ct_bars,%a0
        moveq   #5,%d4
        moveq   #14,%d6
2:      move.l  (%a0)+,%d2
        move.l  #66150000,%d3
        mulu.l  %d2,%d3                 | b bars' q
        move.l  %d1,%d0
        sub.l   %d3,%d0
        bcc     3f
        neg.l   %d0
3:      move.l  %d3,%d2
        lsr.l   %d6,%d2
        divu.l  %d2,%d0                 | |q - den| / (den >> 14)
        cmp.l   %d5,%d0
        bcc     4f
        move.l  %d0,%d5
4:      subq.l  #1,%d4
        bne     2b
        cmp.l   #1024,%d5
        bcs     5f
        move.l  #LA_FLOOR,%d0
        bra     6f
5:      lea     ct_la_t,%a0
        move.w  (%a0,%d5.l*2),%d0
        and.l   #0xffff,%d0
6:      movem.l (%sp),%d2-%d6
        lea     20(%sp),%sp
        rts

| d0 = b -> d0 = the tempo at which ct_len is exactly b bars (centi-BPM, floor)
ct_exact:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        move.l  %d0,%d4
        move.l  ct_len,%d2
        move.l  #1058400000,%d1
        remu.l  %d2,%d3:%d1             | d3 = n % len
        divu.l  %d2,%d1                 | n / len
        mulu.l  %d4,%d1
        mulu.l  %d4,%d3
        divu.l  %d2,%d3
        add.l   %d3,%d1
        move.l  %d1,%d0
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| d0 = r -> d0 = ((r + Q) / 2)^6 (Q14)
ct_f6:
        move.l  %d2,-(%sp)
        add.l   #Q,%d0
        asr.l   #1,%d0
        move.l  %d0,%d1
        mulu.l  %d0,%d1
        moveq   #14,%d2
        lsr.l   %d2,%d1                 | f2
        mulu.l  %d0,%d1
        lsr.l   %d2,%d1                 | f3
        mulu.l  %d1,%d1
        lsr.l   %d2,%d1                 | f6
        move.l  %d1,%d0
        move.l  (%sp)+,%d2
        rts

| d0 = c -> d0 = the octave key: prior, times the loop agreement when ct_glen
ct_okey:
        move.l  %d2,-(%sp)
        move.l  %d0,%d2
        bsr     ct_prior
        tst.l   ct_glen
        beq     1f
        move.l  %d0,-(%sp)
        move.l  %d2,%d0
        bsr     ct_la
        move.l  (%sp)+,%d1
        mulu.l  %d1,%d0
        moveq   #14,%d1
        lsr.l   %d1,%d0
1:      move.l  (%sp)+,%d2
        rts

| ---- the grid scan: d0 = 0 (spacing only) or 1 (with the take's length) ----
| -> gg_c (the pick), gg_conf (Q14), gg_bars (0 = none), gg_loopc
ct_gapgrid:
        lea     -36(%sp),%sp
        movem.l %d2-%d7/%a2-%a4,(%sp)
        clr.l   ct_glen
        tst.l   %d0
        beq     1f
        move.l  ct_len,%d0
        move.l  %d0,ct_glen
1:      lea     ct_r,%a2
        lea     ct_s,%a3
        move.l  #C_LO,%d2               | c
        clr.l   %d6                     | top s
        clr.l   %d7                     | top c
2:      move.w  (%a2)+,%d0
        ext.l   %d0
        bsr     ct_f6
        move.l  %d0,%d3
        move.l  %d2,%d0
        bsr     ct_prior
        mulu.l  %d0,%d3
        moveq   #14,%d1
        lsr.l   %d1,%d3                 | s = f6 * prior
        tst.l   ct_glen
        beq     3f
        move.l  %d2,%d0
        bsr     ct_la
        mulu.l  %d0,%d3
        moveq   #14,%d1
        lsr.l   %d1,%d3                 | * the loop agreement
3:      move.l  %d3,(%a3)+
        cmp.l   %d6,%d3
        bcs     4f
        move.l  %d3,%d6                 | a tie: the higher tempo (the reference sorts descending)
        move.l  %d2,%d7
4:      add.l   #10,%d2
        cmp.l   #C_HI,%d2
        ble     2b
        moveq   #-1,%d5                 | the octave: the first best of top/2, top, 2 top in range
        clr.l   %d3                     | the pick
        move.l  %d7,%d4
        lsr.l   #1,%d4
        bsr     50f
        move.l  %d7,%d4
        bsr     50f
        move.l  %d7,%d4
        add.l   %d4,%d4
        bsr     50f
        bra     55f
50:     cmp.l   #C_LO,%d4
        blt     51f
        cmp.l   #C_HI,%d4
        bgt     51f
        move.l  %d4,%d0
        bsr     ct_okey
        cmp.l   %d5,%d0
        ble     51f
        move.l  %d0,%d5
        move.l  %d4,%d3
51:     rts
55:     move.l  %d3,gg_c
        | the runner-up: the best row (the higher tempo on a tie) with neither
        | x nor its octaves within 3 % of the pick
        lea     ct_s,%a3
        move.l  #C_LO,%d2
        moveq   #-1,%d5                 | best s (none yet)
        move.l  %d3,%d4                 | the pick
8:      move.l  (%a3)+,%d1
        move.l  %d2,%d0
        bsr     ct_inband
        tst.l   %d0
        bne     9f
        cmp.l   %d5,%d1
        blt     9f
        move.l  %d1,%d5
9:      add.l   #10,%d2
        cmp.l   #C_HI,%d2
        ble     8b
        move.l  #Q,%d0
        tst.l   %d5
        bmi     10f
        tst.l   %d6
        beq     10f
        move.l  %d5,%d1
        moveq   #14,%d2
        lsl.l   %d2,%d1
        divu.l  %d6,%d1
        sub.l   %d1,%d0
10:     move.l  %d0,gg_conf
        clr.l   gg_bars
        clr.l   gg_loopc
        tst.l   ct_glen
        beq     13f
        lea     ct_bars,%a4
        moveq   #5,%d5
11:     move.l  (%a4)+,%d2
        move.l  %d2,%d0
        bsr     ct_exact
        move.l  %d0,%d6                 | e
        sub.l   %d3,%d0
        bpl     12f
        neg.l   %d0
12:     cmp.l   %d3,%d0                 | |e - pick| >= pick: not this one (and no overflow below)
        bcc     121f
        move.l  #1000,%d1
        mulu.l  %d1,%d0
        move.l  %d3,%d1
        moveq   #12,%d7
        mulu.l  %d7,%d1
        cmp.l   %d1,%d0
        bcc     121f
        move.l  %d2,gg_bars
        move.l  %d6,gg_loopc
        bra     13f
121:    subq.l  #1,%d5
        bne     11b
13:     movem.l (%sp),%d2-%d7/%a2-%a4
        lea     36(%sp),%sp
        rts

| d0 = x, d4 = the pick -> d0 = 1 when 5000 x, 10000 x or 20000 x lies
| strictly between 9704 and 10305 times the pick. Keeps d1-d7.
ct_inband:
        lea     -12(%sp),%sp
        movem.l %d1-%d3,(%sp)
        move.l  %d4,%d2
        move.l  #9704,%d1
        mulu.l  %d1,%d2                 | low
        move.l  %d4,%d3
        move.l  #10305,%d1
        mulu.l  %d1,%d3                 | high
        move.l  #5000,%d1
        mulu.l  %d0,%d1                 | 5000 x
        cmp.l   %d2,%d1
        bls     1f
        cmp.l   %d3,%d1
        bcs     8f
1:      add.l   %d1,%d1                 | 10000 x
        cmp.l   %d2,%d1
        bls     2f
        cmp.l   %d3,%d1
        bcs     8f
2:      add.l   %d1,%d1                 | 20000 x
        cmp.l   %d2,%d1
        bls     7f
        cmp.l   %d3,%d1
        bcs     8f
7:      moveq   #0,%d0
        bra     9f
8:      moveq   #1,%d0
9:      movem.l (%sp),%d1-%d3
        lea     12(%sp),%sp
        rts

| d0 = c -> d0 = 2c when c < 12000 and 2c <= 20000, else c // 2
ct_alt:
        cmp.l   #12000,%d0
        bge     1f
        move.l  %d0,%d1
        add.l   %d1,%d1
        cmp.l   #C_HI,%d1
        bgt     1f
        move.l  %d1,%d0
        rts
1:      lsr.l   #1,%d0
        rts

| ---- loopish: d0 = 1 when the take (ct_glen) ends on the chops' grid -------
ct_loopish:
        lea     -16(%sp),%sp
        movem.l %d2-%d5,(%sp)
        lea     ct_sg,%a0
        move.l  ct_n,%d2
        move.l  %d2,%d0
        lsr.l   #1,%d0
        move.l  (%a0,%d0.l*4),%d3       | unit = the median gap
        move.l  %d3,%d4                 | the gaps under 3/4 of it: a prefix of the sorted ones
        moveq   #3,%d0
        mulu.l  %d0,%d4                 | 3 unit
        clr.l   %d5                     | m
1:      cmp.l   %d2,%d5
        bge     2f
        move.l  (%a0,%d5.l*4),%d0
        lsl.l   #2,%d0
        cmp.l   %d4,%d0
        bge     2f
        addq.l  #1,%d5
        bra     1b
2:      cmp.l   #2,%d5
        blt     3f
        lsr.l   #1,%d5
        move.l  (%a0,%d5.l*4),%d3
3:      lea     ct_pos,%a0              | t = (length - the last slice) * 100 // unit, floored
        move.l  ct_np,%d0
        move.l  -4(%a0,%d0.l*4),%d1
        move.l  ct_glen,%d0
        sub.l   %d1,%d0
        moveq   #100,%d1
        muls.l  %d1,%d0
        move.l  %d0,%d4
        divs.l  %d3,%d0                 | towards zero
        move.l  %d0,%d1
        muls.l  %d3,%d1
        cmp.l   %d1,%d4
        beq     4f
        tst.l   %d4
        bpl     4f
        subq.l  #1,%d0                  | floor
4:      moveq   #100,%d1                | frac = t mod 100 (0..99)
        move.l  %d0,%d4
        divs.l  %d1,%d4
        muls.l  %d1,%d4
        sub.l   %d4,%d0
        bpl     5f
        add.l   %d1,%d0
5:      move.l  %d1,%d4
        sub.l   %d0,%d4                 | 100 - frac
        cmp.l   %d0,%d4
        bge     6f
        move.l  %d4,%d0
6:      cmp.l   #16,%d0                 | min(frac, 100 - frac) <= 16
        bgt     8f
        move.l  (%a0),%d0               | and the first slice within 0.16 unit of the start
        moveq   #100,%d1
        mulu.l  %d1,%d0
        divu.l  %d3,%d0
        cmp.l   #16,%d0
        bge     8f
        moveq   #1,%d0
        bra     9f
8:      moveq   #0,%d0
9:      movem.l (%sp),%d2-%d5
        lea     16(%sp),%sp
        rts

| ---- the reading: -> rd_c, rd_alt ------------------------------------------
ct_reading:
        lea     -24(%sp),%sp
        movem.l %d2-%d7,(%sp)
        move.l  ct_len,%d7              | the length (0 = no loop)
        cmp.l   #MAX_LEN,%d7
        bls     1f
        clr.l   %d7
1:      moveq   #0,%d0
        bsr     ct_gapgrid              | g
        move.l  gg_c,%d2                | c
        move.l  gg_conf,%d3             | conf
        tst.l   %d7
        beq     3f
        move.l  %d7,ct_glen
        bsr     ct_loopish
        tst.l   %d0
        bne     2f
        clr.l   %d7
        bra     3f
2:      moveq   #1,%d0                  | gl (ct_len is the length here)
        bsr     ct_gapgrid
        tst.l   gg_bars
        beq     3f
        move.l  gg_conf,%d0
        moveq   #10,%d1
        mulu.l  %d1,%d0
        cmp.l   #6*Q,%d0
        blt     3f
        move.l  gg_loopc,%d0
        move.l  %d0,rd_c
        move.l  gg_c,%d0
        bsr     ct_alt
        move.l  %d0,rd_alt
        bra     99f
3:      | even spacing with no clear grid: the gap is a beat
        move.l  ct_n,%d4
        lea     ct_sg,%a0
        move.l  %d4,%d0
        lsr.l   #1,%d0
        move.l  (%a0,%d0.l*4),%d5       | mg
        lea     ct_gaps,%a0
        clr.l   %d6                     | the sum
        move.l  %d4,%d1
4:      move.l  (%a0)+,%d0
        sub.l   %d5,%d0
        asr.l   #6,%d0
        muls.l  %d0,%d0
        add.l   %d0,%d6
        subq.l  #1,%d1
        bne     4b
        divu.l  %d4,%d6                 | var
        move.l  %d5,%d0
        lsr.l   #6,%d0
        mulu.l  %d0,%d0                 | sq
        tst.l   %d0
        beq     6f
        lsl.l   #6,%d0
        subq.l  #1,%d0
        move.l  #10000,%d1
        divu.l  %d1,%d0
        cmp.l   %d0,%d6
        bhi     6f
        move.l  %d3,%d0
        add.l   %d0,%d0
        cmp.l   #Q,%d0
        bge     6f
        move.l  #264600000,%d2
        divu.l  %d5,%d2
5:      cmp.l   #7000,%d2
        bge     51f
        add.l   %d2,%d2
        bra     5b
51:     cmp.l   #18000,%d2
        blt     6f
        lsr.l   #1,%d2
        bra     51b
6:      move.l  %d2,%d0
        bsr     ct_alt
        move.l  %d0,%d3                 | alt
        tst.l   %d7
        beq     98f
        | the loop confirm: the bar count (1..16) nearest c or alt (alt 4 % behind)
        move.l  #0x7fffffff,%d6         | best d + pen
        clr.l   %d5                     | best e (0 = none)
        moveq   #1,%d4                  | b
7:      move.l  %d4,%d0
        bsr     ct_exact
        move.l  %d0,%d7                 | e
        move.l  %d2,%d0
        moveq   #0,%d1
        bsr     80f
        move.l  %d3,%d0
        move.l  #400,%d1
        bsr     80f
        addq.l  #1,%d4
        cmp.l   #16,%d4
        ble     7b
        tst.l   %d5
        beq     98f
        move.l  %d5,%d2
        move.l  %d2,%d0
        bsr     ct_alt
        move.l  %d0,%d3
        bra     98f
80:     move.l  %d0,%a1                 | d0 = cand, d1 = pen; e in d7
        move.l  %d7,%d0
        sub.l   %a1,%d0
        bpl     81f
        neg.l   %d0
81:     cmp.l   %a1,%d0
        bcc     82f                     | far off
        move.l  %d1,-(%sp)
        move.l  #100000,%d1
        mulu.l  %d1,%d0
        move.l  %a1,%d1
        divu.l  %d1,%d0                 | d
        move.l  (%sp)+,%d1
        cmp.l   #1200,%d0
        bge     82f
        add.l   %d1,%d0
        cmp.l   %d6,%d0
        bge     82f
        move.l  %d0,%d6
        move.l  %d7,%d5
82:     rts
98:     move.l  %d2,rd_c
        move.l  %d3,rd_alt
99:     movem.l (%sp),%d2-%d7
        lea     24(%sp),%sp
        rts

| ---- structure: d0 = c, d1 = trip (0/1) -> st_plain, st_on, st_w, st_kc[NU] -
ct_structure:
        lea     -40(%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)
        move.l  %d0,%d7                 | c
        move.l  %d1,%a5                 | trip
        lea     st_kc,%a0
        moveq   #NU,%d0
1:      clr.l   (%a0)+
        subq.l  #1,%d0
        bne     1b
        clr.l   st_on
        clr.l   st_w
        lea     ct_gaps,%a2
        move.l  ct_n,%d6
        move.l  #D8_U,%a4
2:      move.l  (%a2)+,%d0
        lsr.l   #3,%d0
        mulu.l  %d7,%d0
        move.l  %a4,%d1
        divu.l  %d1,%d0                 | u: the gap in beats, Q12
        lea     ct_units,%a3
        moveq   #-1,%d5                 | the best |u - k|
        moveq   #0,%d4                  | its offset (index x 8)
        clr.l   %d3                     | offset
3:      move.l  4(%a3,%d3.l),%d1        | weight
        cmp.l   #60,%d1
        bgt     31f
        cmp.l   #0,%a5
        beq     33f
31:     move.l  %d0,%d2
        sub.l   (%a3,%d3.l),%d2
        bpl     32f
        neg.l   %d2
32:     cmp.l   %d5,%d2
        bcc     33f                     | strictly nearer only: the first of equals
        move.l  %d2,%d5
        move.l  %d3,%d4
33:     addq.l  #8,%d3
        cmp.l   #8*NU,%d3
        blt     3b
        move.l  (%a3,%d4.l),%d1         | k
        move.l  #4096,%d2               | max(4096, k)
        cmp.l   %d2,%d1
        bls     34f
        move.l  %d1,%d2
34:     move.l  %d5,%d0
        moveq   #10,%d1
        mulu.l  %d1,%d0
        cmp.l   %d2,%d0
        bcc     4f
        move.l  4(%a3,%d4.l),%d1
        add.l   %d1,st_w
        addq.l  #1,st_on
        lsr.l   #1,%d4                  | index x 4
        lea     st_kc,%a0
        addq.l  #1,(%a0,%d4.l)
4:      subq.l  #1,%d6
        bne     2b
        clr.l   %d0                     | plain: kinds with 2 or more, weight 100 (any with trip)
        lea     st_kc,%a0
        lea     ct_units,%a3
        moveq   #NU,%d3
5:      move.l  (%a0)+,%d1
        cmp.l   #2,%d1
        blt     6f
        cmp.l   #0,%a5
        bne     51f
        move.l  4(%a3),%d1
        cmp.l   #100,%d1
        bne     6f
51:     addq.l  #1,%d0
6:      addq.l  #8,%a3
        subq.l  #1,%d3
        bne     5b
        move.l  %d0,st_plain
        movem.l (%sp),%d2-%d7/%a2-%a5
        lea     40(%sp),%sp
        rts

| ---- best_oct: d0 = c, d1 = trip -> bo_plain, bo_on, bo_w, bo_x, bo_kc ------
| of c // 2, c, 2c the first with the most (min(plain, 2), w)
ct_bestoct:
        lea     -24(%sp),%sp
        movem.l %d2-%d7,(%sp)
        move.l  %d0,%d2                 | c
        move.l  %d1,%d3                 | trip
        moveq   #-1,%d4                 | best min(plain, 2)
        moveq   #0,%d5                  | best w
        move.l  %d2,%d6
        lsr.l   #1,%d6
        bsr     50f
        move.l  %d2,%d6
        bsr     50f
        move.l  %d2,%d6
        add.l   %d6,%d6
        bsr     50f
        movem.l (%sp),%d2-%d7
        lea     24(%sp),%sp
        rts
50:     move.l  %d6,%d0
        move.l  %d3,%d1
        bsr     ct_structure
        move.l  st_plain,%d0
        cmp.l   #2,%d0
        ble     51f
        moveq   #2,%d0
51:     cmp.l   %d4,%d0
        blt     59f
        bgt     52f
        move.l  st_w,%d1
        cmp.l   %d5,%d1
        ble     59f
52:     move.l  %d0,%d4
        move.l  st_w,%d5
        move.l  %d5,bo_w
        move.l  st_plain,%d0
        move.l  %d0,bo_plain
        move.l  st_on,%d0
        move.l  %d0,bo_on
        move.l  %d6,bo_x
        lea     st_kc,%a0
        lea     bo_kc,%a1
        moveq   #NU,%d0
53:     move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne     53b
59:     rts

| ---- plainer: a 2:3 / 3:4 / 4:3 / 3:2 neighbour of rd_c that explains the
| chops as plain beats much better replaces it -> rd_c, rd_alt
ct_plainer:
        move.l  ct_n,%d0
        cmp.l   #3,%d0
        bge     1f
        rts
1:      lea     -40(%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)
        move.l  rd_c,%d2                | c
        move.l  %d2,%d0
        moveq   #0,%d1
        bsr     ct_bestoct
        move.l  bo_w,%d3                | wcT
        move.l  ct_n,%d0
        moveq   #15,%d1
        mulu.l  %d1,%d0
        add.l   %d0,%d3                 | wcT + 15 n
        moveq   #-1,%d6                 | best w (none)
        clr.l   %d7                     | best x
        lea     ct_ratios_p,%a2
        moveq   #4,%d5
2:      move.l  %d2,%d0                 | b0 = c * num // den
        move.l  (%a2)+,%d1
        mulu.l  %d1,%d0
        move.l  (%a2)+,%d1
        divu.l  %d1,%d0
        move.l  %d0,%a3                 | b0
        move.l  #0x80000000,%a4         | the peak r
        clr.l   %d4                     | its x
        moveq   #-30,%d1                | d
3:      move.l  %d1,-(%sp)
        move.l  #1000,%d0
        add.l   %d1,%d0
        move.l  %a3,%d1
        mulu.l  %d1,%d0
        move.l  #1000,%d1
        divu.l  %d1,%d0                 | x
        move.l  %d0,%a5
        bsr     ct_r_at
        move.l  %a4,%d1
        cmp.l   %d1,%d0
        blt     4f
        bgt     31f
        cmp.l   %a5,%d4                 | equal r: the larger x
        bcc     4f
31:     move.l  %d0,%a4
        move.l  %a5,%d4
4:      move.l  (%sp)+,%d1
        addq.l  #2,%d1
        cmp.l   #30,%d1
        ble     3b
        move.l  %d4,%d0
        moveq   #0,%d1
        bsr     ct_bestoct
        move.l  bo_plain,%d0
        cmp.l   #2,%d0
        blt     5f
        move.l  bo_w,%d0
        cmp.l   %d3,%d0
        blt     5f
        cmp.l   %d6,%d0
        ble     5f
        move.l  %d0,%d6
        move.l  %d4,%d7
5:      subq.l  #1,%d5
        bne     2b
        tst.l   %d6
        bmi     9f
6:      cmp.l   #6000,%d7               | into range
        bge     61f
        add.l   %d7,%d7
        bra     6b
61:     cmp.l   #20000,%d7
        ble     62f
        lsr.l   #1,%d7
        bra     61b
62:     moveq   #-1,%d5                 | the octave by prior, the first best
        clr.l   %d3
        move.l  %d7,%d4
        lsr.l   #1,%d4
        bsr     70f
        move.l  %d7,%d4
        bsr     70f
        move.l  %d7,%d4
        add.l   %d4,%d4
        bsr     70f
        move.l  %d3,rd_c
        move.l  %d3,%d0
        bsr     ct_alt
        move.l  %d0,rd_alt
9:      movem.l (%sp),%d2-%d7/%a2-%a5
        lea     40(%sp),%sp
        rts
70:     cmp.l   #6000,%d4
        blt     71f
        cmp.l   #20000,%d4
        bgt     71f
        move.l  %d4,%d0
        bsr     ct_prior
        cmp.l   %d5,%d0
        ble     71f
        move.l  %d0,%d5
        move.l  %d4,%d3
71:     rts

| ---- also: d0 = c -> d0 = a 4:3 / 3:4 / 3:2 / 2:3 neighbour that explains
| the chops as plainly (dotted / triplet units allowed), 0 = none ------------
ct_also:
        lea     -40(%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)
        move.l  %d0,%d2                 | c
        moveq   #0,%d1
        bsr     ct_bestoct
        move.l  ct_n,%d0
        moveq   #5,%d1
        mulu.l  %d1,%d0                 | 5 n
        move.l  bo_w,%d3
        sub.l   %d0,%d3                 | wc - 5 n
        move.l  bo_on,%d4
        moveq   #100,%d1
        muls.l  %d1,%d4
        sub.l   %d0,%d4                 | on * 100 - 5 n
        clr.l   %d5                     | dotted: the 75-weight kinds' counts
        lea     bo_kc,%a0
        lea     ct_units,%a1
        moveq   #NU,%d0
1:      move.l  4(%a1),%d1
        cmp.l   #75,%d1
        bne     2f
        add.l   (%a0),%d5
2:      addq.l  #4,%a0
        addq.l  #8,%a1
        subq.l  #1,%d0
        bne     1b
        moveq   #-1,%d6                 | best wc2 (none)
        clr.l   %d7                     | best x
        lea     ct_ratios_a,%a2
        move.l  #4,%a4
3:      move.l  %d2,%d0
        move.l  (%a2)+,%d1
        mulu.l  %d1,%d0
        move.l  (%a2)+,%d1
        divu.l  %d1,%d0
        move.l  %d0,%a3                 | x
        moveq   #1,%d1
        bsr     ct_bestoct
        move.l  bo_plain,%d0
        cmp.l   #2,%d0
        blt     6f
        move.l  bo_w,%d0
        cmp.l   %d3,%d0
        bge     4f
        cmp.l   #2,%d5
        blt     6f
        move.l  bo_on,%d0
        moveq   #100,%d1
        muls.l  %d1,%d0
        cmp.l   %d4,%d0
        blt     6f
4:      move.l  bo_w,%d0                | the most wc2, then the larger x
        cmp.l   %d6,%d0
        blt     6f
        bgt     5f
        cmp.l   %a3,%d7
        bcc     6f
5:      move.l  %d0,%d6
        move.l  %a3,%d7
6:      subq.l  #1,%a4
        cmp.l   #0,%a4
        bne     3b
        move.l  %d7,%d0
        movem.l (%sp),%d2-%d7/%a2-%a5
        lea     40(%sp),%sp
        rts

| ---- data -------------------------------------------------------------------
        .data
        .balign 4
ct_bars:    .long   1, 2, 4, 8, 16
ct_ratios_p: .long  2, 3, 3, 4, 4, 3, 3, 2
ct_ratios_a: .long  4, 3, 3, 4, 3, 2, 2, 3
| structure units, Q12 (4096 = one beat), weight in percent; the reference's order
ct_units:   .long   2048, 100, 4096, 100, 8192, 100, 16384, 100, 3072, 75, 6144, 75, 12288, 75
            .long   683, 60, 1365, 60, 2731, 60, 5461, 60
| grid steps a chop plausibly spans: 1, 2, 3, 4, 6, 8, 12, 16, 24, 32
ct_simple:  .byte   0,1,1,1,1,0,1,0,1,0,0,0,1,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1
fmt_line:   .asciz  "BPM %d (%d)"
fmt_dot:    .asciz  "BPM %d (%d.)"
        .balign 4
        .global ct_state, ct_req, ct_buf, ct_ok, ct_c, ct_br
ct_state:   .long   0                   | 0 idle, 1 count popup up, 2 tempo popup up, 3 gate request
ct_req:     .long   0
ct_ok:      .long   0
ct_cd:      .long   0
ct_keys:    .long   0, 0
ct_dot:     .long   0
ct_c:       .long   0
ct_br:      .long   0
ct_len:     .long   0
ct_glen:    .long   0
ct_n:       .long   0
ct_np:      .long   0
gg_c:       .long   0
gg_conf:    .long   0
gg_bars:    .long   0
gg_loopc:   .long   0
rd_c:       .long   0
rd_alt:     .long   0
st_plain:   .long   0
st_on:      .long   0
st_w:       .long   0
bo_plain:   .long   0
bo_on:      .long   0
bo_w:       .long   0
bo_x:       .long   0
st_kc:      .space  4*NU
bo_kc:      .space  4*NU
ct_buf:     .space  32

        .bss
        .balign 4
ct_tmp:     .space  4*64
ct_pos:     .space  4*64
ct_gaps:    .space  4*64
ct_sg:      .space  4*64
ct_s:       .space  4*1401
ct_r:       .space  2*1401
        .balign 4
