| REPITCH -- TSTR value 4 for STATIC and FLEX, on the SRC SETUP page and as a
| sample's own TIMESTRETCH attribute (reached through SETUP TSTR = AUTO).
|
| A REPITCH track is, to the voice renderer, a track on OFF: it resolves
| TSTR to 0 and renders dry, forwards and backwards, advancing the sample by
| the frames the DSP consumed. Its playback increment, shared by the
| ColdFire source supplier and the DSP voice command, is the neutral-pitch
| increment (RATE still applies) scaled by project_bpm24 / sample_bpm24,
| recomputed every frame. PTCH is not applied and its knob draws empty.
| Values 0..3 keep their stock paths; PICKUP is never REPITCH.
        .text

        .global tstr_fmt
        .global rate_gate
        .global pitch_gate
        .global rate_hook
        .global tstr_resolve
        .global ptch_widget
        .global attr_label
        .global attr_up
        .global attr_down

        .equ    LANES, 0x80000510       | per-track ColdFire records, 48 B; SETUP page at +24
        .equ    VOICES, 0x800049d8      | per-track voices, 168 B; bound settings at +8, machine at +20
        .equ    PICKUP, 4               | voice +20
        .equ    STATES, 0x80004898      | per-track 40 B states; the builder's is at [CUR_STATE]
        .equ    CUR_STATE, 0x800062a4
        .equ    UI_TRACK, 0x80000000
        .equ    PROJECT_BPM24, 0x8000181c
        .equ    TSTR_REPITCH, 4
        .equ    TSTR_AUTO, 1
        .equ    BPM24_MIN, 720          | the firmware's own tempo range, 30..300 BPM
        .equ    BPM24_MAX, 7200
        .equ    INC_MAX, 0x08000000     | 2x: stock's own ceiling (PTCH +12)

| d1 = track -> d0 = the bound sample's BPMx24 when REPITCH is in force on
| the track (SETUP TSTR = REPITCH, or AUTO with the sample's TSMODE =
| REPITCH), the track is not a PICKUP and the sample carries a tempo in
| range; 0 otherwise. Every other register is preserved.
rp_source:
        lea     -12(%sp),%sp
        movem.l %d1-%d2/%a0,(%sp)
        moveq   #0,%d0
        moveq   #7,%d2
        cmp.l   %d2,%d1
        bhi.s   .rs_out
        moveq   #48,%d2
        mulu.l  %d1,%d2
        lea     (LANES).l,%a0
        move.b  28(%a0,%d2.l),%d0       | SETUP TSTR, zero-extended
        move.l  %d0,%d2
        move.l  #168,%d0
        mulu.l  %d0,%d1
        lea     (VOICES).l,%a0
        moveq   #PICKUP,%d0
        cmp.b   20(%a0,%d1.l),%d0       | a pickup keeps stock's grains
        bne.s   .rs_bound
        moveq   #0,%d0
        bra.s   .rs_out
.rs_bound:
        movea.l 8(%a0,%d1.l),%a0        | the bound sample's settings
        moveq   #0,%d0
        move.l  %a0,%d1
        beq.s   .rs_out
        moveq   #TSTR_REPITCH,%d1
        cmp.l   %d1,%d2
        beq.s   .rs_on
        moveq   #TSTR_AUTO,%d1
        cmp.l   %d1,%d2
        bne.s   .rs_out
        moveq   #TSTR_REPITCH,%d1
        cmp.l   0x110(%a0),%d1          | the sample's own TSMODE
        bne.s   .rs_out
.rs_on:
        move.l  0x114(%a0),%d1          | the sample's BPMx24
        cmpi.l  #BPM24_MIN,%d1
        blt.s   .rs_out
        cmpi.l  #BPM24_MAX,%d1
        bgt.s   .rs_out
        move.l  %d1,%d0
.rs_out:
        movem.l (%sp),%d1-%d2/%a0
        lea     12(%sp),%sp
        rts

| void fmt(char *buf, int raw). The caller already supplied sprintf's buf at
| 4(sp); replacing raw at 8(sp) with a format string makes the stock sprintf
| tail print it verbatim. Four characters: the widget cell is 18 px and the
| font 4 px a character.
tstr_fmt:
        move.l  8(%sp),%d0
        moveq   #TSTR_REPITCH,%d1
        cmp.l   %d1,%d0
        bhi.s   .unknown
        lea     .labels(%pc),%a0
        move.w  (%a0,%d0.l*2),%d1
        andi.l  #0xffff,%d1
        adda.l  %d1,%a0
        move.l  %a0,8(%sp)
        jmp     (0x40013a08).l
.unknown:
        lea     (0x400b442a).l,%a0        | stock "???"
        move.l  %a0,8(%sp)
        jmp     (0x40013a08).l

.labels:
        .word   .off-.labels,.auto-.labels,.norm-.labels,.beat-.labels
        .word   .rpch-.labels
.off:   .asciz  "OFF"
.auto:  .asciz  "AUTO"
.norm:  .asciz  "NORM"
.beat:  .asciz  "BEAT"
.rpch:  .asciz  "RPCH"
        .balign 2

| 0x4000406a, the playback-increment builder shared by STATIC/FLEX/PICKUP:
| d3 is free from its entry to 0x40004176, so it carries this track's
| sample BPMx24 (0 = not REPITCH) to the two hooks below. Then the
| displaced `btst #4,67(sp); bne` (the recompute flag, set on the
| per-frame call).
rate_gate:
        lea     -8(%sp),%sp
        movem.l %d0-%d1,(%sp)
        move.l  (CUR_STATE).l,%d1
        subi.l  #STATES,%d1
        moveq   #40,%d3
        divu.l  %d3,%d1                  | the track
        bsr     rp_source
        move.l  %d0,%d3
        movem.l (%sp),%d0-%d1
        lea     8(%sp),%sp
        btst    #4,67(%sp)               | displaced
        bne.s   .rg_compute
        jmp     (0x40004072).l
.rg_compute:
        jmp     (0x4000407a).l

| 0x4000409e: the PTCH word is not applied on a REPITCH track; neutral
| (0x4000) takes the same table path as PTCH 0.
pitch_gate:
        tst.l   %d3
        bne.s   .pg_neutral
        .word   0x71d6                   | displaced: mvz.w (%a6),%d0
        bra.s   .pg_cmp
.pg_neutral:
        move.l  #0x4000,%d0
.pg_cmp:
        .word   0xa346                   | displaced: mov3q #1,%d6
        .word   0x0c40,0x4000            | displaced: cmpi.w #0x4000,%d0
        jmp     (0x400040a6).l

| 0x40004100: finish the stock rate (RATE applied), then scale it by
| project/sample tempo, exactly: q*project + (r*project)/source with
| q, r = increment divmod source, both products bounded by the 720..7200
| range. Clamped to 2x.
rate_hook:
        .word   0xa1c0                   | displaced: movclr.l %acc0,%d0 (V4e)
        asr.l   %d6,%d0                  | displaced
        tst.l   %d3
        beq.s   .rh_store
        lea     -12(%sp),%sp
        movem.l %d1-%d2/%d4,(%sp)
        move.l  (PROJECT_BPM24).l,%d2
        cmpi.l  #BPM24_MIN,%d2
        blt.s   .rh_restore
        cmpi.l  #BPM24_MAX,%d2
        bgt.s   .rh_restore
        move.l  %d0,%d1
        divu.l  %d3,%d1                  | q
        move.l  %d1,%d4
        mulu.l  %d3,%d4
        sub.l   %d4,%d0                  | r
        mulu.l  %d2,%d1
        mulu.l  %d2,%d0
        divu.l  %d3,%d0
        add.l   %d1,%d0
        cmpi.l  #INC_MAX,%d0
        bls.s   .rh_restore
        move.l  #INC_MAX,%d0
.rh_restore:
        movem.l (%sp),%d1-%d2/%d4
        lea     12(%sp),%sp
.rh_store:
        move.l  %d0,36(%a3)              | displaced; CPU and DSP both use it
        jmp     (0x40004108).l

| 0x40007d96, in the voice renderer: d1 is the track's TSTR just resolved
| (SETUP, or the sample's TSMODE for AUTO). REPITCH resolves to OFF, so every
| renderer site that reads the result (voice +24) takes stock's dry path:
| the ratio block (0x40007ede), the rate choice (0x40008210, 0x400089de),
| the stretch-overflow flag (0x400081b2, 0x4000898a) and, the one the
| first two gates missed, the position advance (0x4000886c, 0x40008e42),
| which on any nonzero value moves the sample by OUTPUT samples instead of
| the frames the DSP consumed. Stock's next line still turns a PICKUP's 0
| into 2. Then the displaced `mvs.b 20(%a2),%d0; moveq #4,%d2`.
tstr_resolve:
        moveq   #TSTR_REPITCH,%d2
        cmp.l   %d2,%d1
        bne.s   .tr_stock
        moveq   #0,%d1
.tr_stock:
        .word   0x712a,0x0014            | displaced: mvs.b 20(%a2),%d0
        moveq   #4,%d2                   | displaced
        jmp     (0x40007d9c).l

| PTCH's widget on the STATIC/FLEX page (was the stock knob 0x400479b4,
| args (a, b, index, value, flags, formatter, canvas)). On a REPITCH track
| the knob is drawn from a copy of the arguments with value -1, which the
| stock knob draws as its frame alone (0x40047a0e).
ptch_widget:
        moveq   #0,%d1
        move.b  (UI_TRACK).l,%d1
        bsr     rp_source
        tst.l   %d0
        bne.s   .pw_off
        jmp     (0x400479b4).l
.pw_off:
        move.l  28(%sp),-(%sp)          | canvas
        move.l  28(%sp),-(%sp)          | formatter
        move.l  28(%sp),-(%sp)          | flags
        moveq   #-1,%d0
        move.l  %d0,-(%sp)              | value
        move.l  28(%sp),-(%sp)          | index
        move.l  28(%sp),-(%sp)
        move.l  28(%sp),-(%sp)
        jsr     (0x400479b4).l
        lea     28(%sp),%sp
        rts

| Audio editor ATTR, the TIMESTRETCH row. 0x4006e71c: d0 is the sample's
| TSMODE and not 0/2/3; stock prints "ERROR" for anything else.
attr_label:
        moveq   #TSTR_REPITCH,%d1
        cmp.l   %d1,%d0
        bne.s   .al_error
        pea     .repitch(%pc)
        jmp     (0x4006e878).l
.al_error:
        pea     (0x400b94f6).l           | stock "ERROR"
        jmp     (0x4006e878).l
.repitch:
        .asciz  "REPITCH"
        .balign 2

| 0x4006ee56, value up: d0 = TSMODE (not 0), a0 = the settings. Stock steps
| 2 -> 3 and stops; 3 -> REPITCH is the new top.
attr_up:
        moveq   #2,%d1
        cmp.l   %d0,%d1
        beq.s   .au_step
        moveq   #3,%d1
        cmp.l   %d0,%d1
        bne.s   .au_done
.au_step:
        addq.l  #1,%d0
        move.l  %d0,272(%a0)
.au_done:
        jmp     (0x4006eef0).l

| 0x4006ef7c, value down: stock steps 3 -> 2 -> 0; REPITCH -> 3 first.
attr_down:
        move.l  272(%a0),%d0             | displaced
        moveq   #2,%d1
        cmp.l   %d0,%d1
        bne.s   .ad_upper
        clr.l   272(%a0)
        bra.s   .ad_done
.ad_upper:
        moveq   #3,%d1
        cmp.l   %d0,%d1
        beq.s   .ad_step
        moveq   #TSTR_REPITCH,%d1
        cmp.l   %d0,%d1
        bne.s   .ad_done
.ad_step:
        subq.l  #1,%d0
        move.l  %d0,272(%a0)
.ad_done:
        jmp     (0x4006f026).l
