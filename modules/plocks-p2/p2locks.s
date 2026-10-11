| PLOCKS P2 -- per-step parameter locks for page 2 of FX1 and FX2.
|
| Stock's step record is 32 lock bytes, page 1 of the five pages; every
| byte of the pattern is used (docs/firmware/STEP_LOCKS.md). This unit
| keeps page 2 in its own table and runs it beside stock's lock pipeline:
|
| * STORE (.bss, 1,572,864 B): 12 bytes a step, bank x pattern x track x
|   step; byte j = FX1 page-2 slot j (0..5), FX2 slot j-6 (6..11); 0xff =
|   not locked. Filled with 0xff by plk_init.
| * RECORD: with a SETUP window open (0x460d175c) on the FX1 or FX2 page
|   (0x460d1684 = 3 / 4) and trigs held (0x460d174a), stock sends a knob
|   turn to the page-1 lock editor 0x400508e4, which locks the page-1
|   slot behind the window. plk_edit takes that turn as a page-2 lock on
|   every held step instead: the slot's encoder hook and clamp, FUNC held
|   removes.
| * PLAYBACK mirrors the stock stages: the sequencer's record builder
|   0x4009d1e8 (track, bank, pattern, step, n) fills a per-track staging
|   record (n = -1) or pending slot n -> P2STAGE / P2PEND; staging ->
|   pending slot 0 (0x4009b858, 0x4009c038); the reset of every pending
|   slot (0x4009b220); the frame ISR's pending -> trig record (0x4000bafe)
|   and the MIDI-note trig's own record (0x4000b770) -> P2REC; and at
|   0x4000c59e, where stock's restore and apply paths join: the Part's
|   page-2 byte back for every slot the last trig locked (skipped, as
|   stock skips its restore, on flag bit 6), then P2REC into the live
|   lane's page-2 bytes (0x80000810 + 72t + 50 + j), consumed unless flag
|   bit 2. The frame builder copies the lane into the DSP record every
|   frame, and SCENES P2's morph reads the lane as the knob, so a scene
|   lerps from the locked value as stock's page-1 morph does.
| * plk_dial: SCENES P2's page-2 dial hooks call it with no scene held:
|   with trigs held it returns the first held step's lock.

        .set    WINDOW,     0x460d175c      | long: the open window (0 = none)
        .set    PAGEKIND,   0x460d1684      | long: 3 = FX1, 4 = FX2
        .set    HELD,       0x460d174a      | word: held trig keys
        .set    STEPPAGE,   0x460d174c      | long: the step page's first step
        .set    MIDITRK,    0x80000012      | long: nonzero on a MIDI track
        .set    UI_TRACK,   0x100b14cc
        .set    UI_PART,    0x100b14cf
        .set    UI_PTN,     0x100b14d0
        .set    DBPTR,      0x46c82456
        .set    BLOB,       0x400e21e0
        .set    BANK_STRIDE, 0x9b340
        .set    PART_STRIDE, 0x18b2
        .set    ID1_OFF,    0x8ed80
        .set    ID2_OFF,    0x8ed88
        .set    P2_OFF,     0x8f07e         | part: FX1 page 2 slot 0, +track*30; FX2 at +6
        .set    DESC1,      0x400d5f58
        .set    DESC2,      0x400d5fdc
        .set    ENC_DEFAULT, 0x4003240c
        .set    DIRTY,      0x40027e00
        .set    REDRAW,     0x46c7d244
        .set    KROWS,      0x46100b18
        .set    KFUNC,      0x2d
        .set    TRK_BANK,   0x8000182a
        .set    TRK_PART,   0x80001832
        .set    LANES,      0x80000810
        .set    LANE_P2,    50              | lane byte of FX1 page-2 slot 0
        .set    REC,        12              | bytes a step
        .set    STORE_LEN,  16*16*8*64*REC
        .set    MAGIC,      0x504c4b32      | 'PLK2'
        .set    TRACK_B,    64*REC          | bytes a track
        .set    CLIP,       0x460c8122      | stock's clipboard
        .set    UNDO,       0x460bf218      | stock's undo buffer
        .set    PTN_STRIDE, 0x8ed8
        .set    TRK_STRIDE, 0x91a
        .set    BANK_B,     16*8*TRACK_B    | a bank's page 2: 98,304 B
        .set    F_OPEN,     0x40016864      | (fo, path, mode, buffer, size) -> <0 error
        .set    F_READ,     0x40016564      | (fo, dst, n) -> 1
        .set    F_WRITE,    0x400166b8      | (fo, src, n) -> 1
        .set    F_CLOSE,    0x4001677c      | (fo)
        .set    F_COPY,     0x40016388      | (dst path, src path, 0) -> <0 error
        .set    PROJDIR,    0x40025230      | (0, 0) -> the project directory
        .set    SPRINTF,    0x40013a08
        .set    IOB_LEN,    0x1000
        .set    NV,         0x100f8600      | CS1: the current bank's page 2, sparse (see nv_save)
        .set    NV_END,     0x100fbdf0      | MIDI SCENES' CS1 copy follows (0x100fbdf0..0x100ffe00)
        .set    NV_MAX,     (NV_END-NV-16)/3
        .set    NV_MAGIC,   0x50324e56      | 'P2NV'
        .set    CUR_BANK,   0x80000002

        .text
        .globl  plk_edit, plk_fill_slide, plk_fill_plain, plk_s2p_a, plk_s2p_b
        .globl  plk_reset, plk_p2r, plk_note, plk_apply, plk_dial, plk_init, STORE
        .globl  plk_place, plk_clrlocks, plk_clrtrack, plk_tcopy, plk_tpaste, plk_memcpy
        .globl  plk_st_bankw_pre, plk_st_bankcopy, plk_st_loadall_pre, plk_st_loadmask_pre
        .globl  plk_st_newproj, plk_st_tocs1, plk_st_fromcs1, plk_st_answer
        .extern store_refuse


| ---------------------------------------------------------------- record ----
| Entry state of 0x400508e4: sp@(4) = slot (0..5), sp@(8) = ticks.
plk_edit:
        tstl    WINDOW
        beq.s   pe_stock
        movel   PAGEKIND,%d0
        subql   #3,%d0
        cmpil   #1,%d0
        bhi.s   pe_stock
        movel   %sp@(4),%d1
        cmpil   #5,%d1
        bhi.s   pe_stock
        tstw    HELD
        beq.s   pe_stock
        tstl    MIDITRK
        beq.s   pe_do
pe_stock:
        lea     %sp@(-80),%sp          | the displaced prologue, then on
        movem.l %d2-%d7/%a2-%fp,%sp@
        jmp     0x400508ec

| d2 slot, d3 ticks, d4 track, d5 part, d6 kind (0 FX1, 1 FX2), d7 held
| mask; a2 descriptor, a3 the Part's page-2 byte, a4 the step's lock (step
| 0), a5 the encoder hook.
pe_do:  lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        bsr.w   plk_init
        movel   %sp@(48),%d2
        movel   %sp@(52),%d3
        movel   PAGEKIND,%d6
        subql   #3,%d6
        moveq   #0,%d4
        moveb   UI_TRACK,%d4
        moveq   #0,%d5
        moveb   UI_PART,%d5
        movel   DBPTR,%d0
        movel   #PART_STRIDE,%d1
        mulu.l  %d5,%d1
        addl    %d1,%d0
        moveal  %d0,%a6                | a6 = the edited part's window
        | descriptor from the slot's effect id
        movel   %a6,%d1
        addl    %d4,%d1
        tstl    %d6
        beq.s   pe_i1
        addil   #ID2_OFF,%d1
        moveal  %d1,%a0
        moveq   #0,%d1
        moveb   %a0@,%d1
        lea     DESC2,%a0
        bra.s   pe_i2
pe_i1:  addil   #ID1_OFF,%d1
        moveal  %d1,%a0
        moveq   #0,%d1
        moveb   %a0@,%d1
        lea     DESC1,%a0
pe_i2:  moveal  %a0@(0,%d1:l:4),%a2
        movel   %a2,%d0
        beq.w   pe_done                | no effect on the slot
        movel   %d2,%d1
        addql   #6,%d1
        lsll    #2,%d1
        moveal  %a2,%a0
        addal   %d1,%a0
        moveal  %a0@(0x12a),%a5        | the slot's encoder hook
        movel   %a5,%d1
        bne.s   pe_h
        lea     ENC_DEFAULT,%a5
pe_h:   | j = kind*6 + slot
        movel   %d6,%d1
        movel   %d1,%d0
        addl    %d1,%d1
        addl    %d0,%d1
        addl    %d1,%d1                | kind*6
        addl    %d2,%d1
        movel   %d1,%sp@-              | sp@ = j
        | the Part's page-2 byte
        moveq   #30,%d0
        mulu.l  %d4,%d0
        addl    %d1,%d0
        addil   #P2_OFF,%d0
        addl    %a6,%d0
        moveal  %d0,%a3
        | the lock of step 0: STORE + (((bank*16 + ptn)*8 + track)*64)*12 + j
        movel   DBPTR,%d0
        subil   #BLOB,%d0
        movel   #BANK_STRIDE,%d1
        divu.l  %d1,%d0                | bank
        lsll    #4,%d0
        moveq   #0,%d1
        moveb   UI_PTN,%d1
        addl    %d1,%d0
        lsll    #3,%d0
        addl    %d4,%d0
        lsll    #6,%d0
        moveq   #REC,%d1
        mulu.l  %d1,%d0
        addl    %sp@+,%d0
        addil   #STORE,%d0
        moveal  %d0,%a4
        moveq   #0,%d7
        movew   HELD,%d7
pe_loop:
        tstl    %d7
        beq.w   pe_commit
        movel   %d7,%d0
        negl    %d0
        andl    %d7,%d0                | the lowest held bit
        eorl    %d0,%d7
        ff1     %d0                    | 31 - bit
        moveq   #31,%d1
        subl    %d0,%d1
        addl    STEPPAGE,%d1           | the step
        cmpil   #63,%d1
        bhi.s   pe_loop
        moveq   #REC,%d0
        mulu.l  %d0,%d1
        lea     %a4@(0,%d1:l),%a1      | a1 = this step's lock
        moveq   #0,%d0
        moveb   KROWS+(KFUNC>>3),%d0
        btst    #(KFUNC&7),%d0
        beq.s   pe_turn
        moveb   #0xff,%a1@             | FUNC held: remove
        bra.s   pe_loop
pe_turn:
        moveq   #0,%d0
        moveb   %a1@,%d0
        cmpil   #0xff,%d0
        bne.s   pe_cur
        moveb   %a3@,%d0               | unlocked: from the Part's value
pe_cur: movel   %a1,%sp@-
        movel   %d0,%sp@-              | hook(slot2, ticks, current) -> d0
        movel   %d3,%sp@-
        movel   %d2,%sp@-
        jsr     %a5@
        lea     %sp@(12),%sp
        moveal  %sp@+,%a1
        mvs.w   %d0,%d0
        movel   %d2,%d1
        addql   #6,%d1
        lsll    #2,%d1
        moveal  %a2,%a0
        addal   %d1,%a0
        movel   %a0@(0x6a),%d1         | clamp to min .. min + count - 1
        cmpl    %d1,%d0
        bge.s   pe_c1
        movel   %d1,%d0
pe_c1:  addl    %a0@(0x9a),%d1
        subql   #1,%d1
        cmpl    %d1,%d0
        ble.s   pe_c2
        movel   %d1,%d0
pe_c2:  moveb   %d0,%a1@
        bra.w   pe_loop
pe_commit:
        bsr.w   ui_bank                | CS1, when it holds this bank
        bsr.w   nv_touch
        | the stock lock editor's marks: the bank edited, the project
        | edited, the dirty call; the slot's redraw
        movel   DBPTR,%d0
        addil   #0x9b332,%d0
        moveal  %d0,%a0
        moveq   #1,%d0
        movel   %d0,%a0@
        movel   %d0,0x100f8598
        movel   %d0,EDITED
        jsr     DIRTY
        movel   %d2,%d1
        movel   %d1,%d0
        lsll    #2,%d0
        addl    %d0,%d1
        addql   #1,%d1
        lsll    #2,%d1
        lea     REDRAW,%a0
        moveq   #20,%d0
        movel   %d0,%a0@(0,%d1:l)
pe_done:
        moveq   #0,%d0
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| -------------------------------------------------------------- playback ----
| fill: the record builder 0x4009d1e8's two fill paths. Its frame: sp@(108)
| track (also d7), sp@(112) bank, sp@(116) pattern, sp@(120) step,
| sp@(124) n (-1 = the staging record).
plk_fill_slide:
        bsr.w   fill
        movel   %d7,%d4                | the displaced instructions, then on
        lsll    #5,%d4
        moveal  %sp@(78),%a0
        jmp     0x4009d70c
plk_fill_plain:
        bsr.w   fill
        movel   %d7,%d1
        lsll    #5,%d1
        moveal  %sp@(78),%a0
        jmp     0x4009d8ce

| fill (a bsr: the frame is 4 further up). Keeps every register.
fill:   lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        movel   INITED,%d0
        cmpil   #MAGIC,%d0
        bne.s   fl_out
        movel   %sp@(20+112),%d0       | bank
        lsll    #4,%d0
        addl    %sp@(20+116),%d0       | pattern
        lsll    #3,%d0
        addl    %d7,%d0                | track
        lsll    #6,%d0
        addl    %sp@(20+120),%d0       | step
        moveq   #REC,%d1
        mulu.l  %d1,%d0
        addil   #STORE,%d0
        moveal  %d0,%a0                | a0 = the step's page-2 locks
        movel   %sp@(20+124),%d0       | n
        bmi.s   fl_stage
        lsll    #3,%d0
        addl    %d7,%d0
        moveq   #REC,%d1
        mulu.l  %d1,%d0
        lea     P2PEND,%a1
        bra.s   fl_copy
fl_stage:
        moveq   #REC,%d0
        mulu.l  %d7,%d0
        lea     P2STAGE,%a1
fl_copy:
        addal   %d0,%a1
        movel   %a0@+,%a1@+
        movel   %a0@+,%a1@+
        movel   %a0@,%a1@
fl_out: movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        rts

| staging -> pending slot 0 for track d0>>5 (both sites have d0 = t<<5).
plk_s2p_a:
        bsr.w   s2p
        moveal  %d0,%a0
        addal   #0x46c76ac0,%a0
        jmp     0x4009b860
plk_s2p_b:
        bsr.w   s2p
        moveal  %d0,%a0
        addal   #0x46c76ac0,%a0
        jmp     0x4009c040
s2p:    lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        lsrl    #5,%d0
        moveq   #REC,%d1
        mulu.l  %d1,%d0
        lea     P2STAGE,%a0
        addal   %d0,%a0
        lea     P2PEND,%a1
        addal   %d0,%a1
        movel   %a0@+,%a1@+
        movel   %a0@+,%a1@+
        movel   %a0@,%a1@
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        rts

| 0x4009b220: stock resets every pending slot to 0xff; so do we.
plk_reset:
        lea     P2PEND,%a0
        moveq   #-1,%d0
        moveq   #(3*8*REC/4),%d1
rs_loop:
        movel   %d0,%a0@+
        subql   #1,%d1
        bne.s   rs_loop
        movel   %d2,%sp@-              | the displaced instructions, then on
        lea     0x80006500,%a1
        jmp     0x4009b228

| 0x4000bafe, the frame ISR: pending slot d5 (n*8 + t) -> the trig record of
| track sp@(114). d1-d4/d6-d7/a4-a5 are loaded by the displaced moveml.
plk_p2r:
        moveq   #REC,%d1
        mulu.l  %d5,%d1
        lea     P2PEND,%a4
        addal   %d1,%a4
        moveq   #REC,%d1
        mulu.l  %sp@(114),%d1
        lea     P2REC,%a5
        addal   %d1,%a5
        movel   %a4@+,%a5@+
        movel   %a4@+,%a5@+
        movel   %a4@,%a5@
        movem.l %a0@,%d1-%d4/%d6-%d7/%a4-%a5
        movem.l %d1-%d4/%d6-%d7/%a4-%a5,%a2@
        jmp     0x4000bb06

| 0x4000b770: a MIDI note's trig carries its own record (a PTCH lock);
| page 2 has none. sp@(192) = track*32.
plk_note:
        movel   %sp@(192),%d1
        lsrl    #5,%d1
        moveq   #REC,%d2
        mulu.l  %d2,%d1
        lea     P2REC,%a4
        addal   %d1,%a4
        moveq   #-1,%d1
        movel   %d1,%a4@+
        movel   %d1,%a4@+
        movel   %d1,%a4@
        movem.l %a1@,%d1-%d4/%d6-%d7/%a4-%a5
        movem.l %d1-%d4/%d6-%d7/%a4-%a5,%a0@
        jmp     0x4000b778

| 0x4000c59e, the frame ISR, where the restore and apply paths join:
| a4 = the trig's flags (bit 31: no apply, bit 6: no restore, bit 2: keep
| the record), sp@(114) = track.
plk_apply:
        lea     %sp@(-36),%sp
        movem.l %d0-%d4/%a0-%a3,%sp@
        movel   INITED,%d0
        cmpil   #MAGIC,%d0
        bne.w   ap_out
        movel   %sp@(36+114),%d4       | d4 = track
        moveq   #72,%d0
        mulu.l  %d4,%d0
        addil   #LANES+LANE_P2,%d0
        moveal  %d0,%a1                | a1 = the lane's page-2 bytes
        lea     P2MASK,%a2
        addal   %d4,%a2
        addal   %d4,%a2                | a2 = the track's mask (word)
        movel   %a4,%d0
        btst    #6,%d0
        bne.s   ap_apply
        moveq   #0,%d3
        movew   %a2@,%d3
        beq.s   ap_apply
        clrw    %a2@
        lea     TRK_BANK,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d4:l),%d0
        cmpil   #0xff,%d0
        beq.s   ap_apply
        moveq   #0,%d1
        moveb   %a0@(8,%d4:l),%d1      | part
        movel   #BANK_STRIDE,%d2
        mulu.l  %d2,%d0
        movel   #PART_STRIDE,%d2
        mulu.l  %d2,%d1
        addl    %d1,%d0
        moveq   #30,%d1
        mulu.l  %d4,%d1
        addl    %d1,%d0
        addil   #BLOB+P2_OFF,%d0
        moveal  %d0,%a0                | a0 = the Part's page-2 bytes
        moveq   #0,%d2
ap_rest:
        btst    %d2,%d3
        beq.s   ap_rn
        moveb   %a0@(0,%d2:l),%d0
        moveb   %d0,%a1@(0,%d2:l)
ap_rn:  addql   #1,%d2
        cmpil   #REC,%d2
        bne.s   ap_rest
ap_apply:
        movel   %a4,%d0
        bmi.s   ap_out
        moveq   #REC,%d0
        mulu.l  %d4,%d0
        lea     P2REC,%a3
        addal   %d0,%a3                | a3 = the trig's page-2 record
        moveq   #0,%d3
        movew   %a2@,%d3
        moveq   #0,%d2
ap_loop:
        moveq   #0,%d0
        moveb   %a3@(0,%d2:l),%d0
        cmpil   #0xff,%d0
        beq.s   ap_next
        moveb   %d0,%a1@(0,%d2:l)
        bset    %d2,%d3
        movel   %a4,%d1
        btst    #2,%d1
        bne.s   ap_next
        moveq   #-1,%d1
        moveb   %d1,%a3@(0,%d2:l)
ap_next:
        addql   #1,%d2
        cmpil   #REC,%d2
        bne.s   ap_loop
        movew   %d3,%a2@
ap_out: movem.l %sp@,%d0-%d4/%a0-%a3
        lea     %sp@(36),%sp
        movel   %a4,%d0                | the displaced test, then on
        movew   %d0,%ccr
        bmi.s   ap_skip
        jmp     0x4000c5a4
ap_skip:
        jmp     0x4000c614

| ------------------------------------------------------------ operations ----
| MUL12 d, a: d *= 12 (a is scratch).
        .macro  MUL12 d, a
        moveal  \d,\a
        addl    \d,\d
        addl    \a,\d
        lsll    #2,\d
        .endm

| track_ptr: d0 = bank, d1 = pattern, d2 = track -> a0 = the track's 768
| bytes. Clobbers d0.
track_ptr:
        lsll    #4,%d0
        addl    %d1,%d0
        lsll    #3,%d0
        addl    %d2,%d0
        moveal  %d0,%a0
        addl    %d0,%d0
        addl    %a0,%d0                | x3
        lsll    #8,%d0                 | x768
        addil   #STORE,%d0
        moveal  %d0,%a0
        rts

| ui_bank -> d0 = the bank the panel edits (from the Part DB pointer).
ui_bank:
        movel   %d1,%sp@-
        movel   DBPTR,%d0
        subil   #BLOB,%d0
        movel   #BANK_STRIDE,%d1
        divu.l  %d1,%d0
        movel   %sp@+,%d1
        rts

| fill12: a0 = 12 bytes -> 0xff. Clobbers nothing.
fill12: movel   %d0,%sp@-
        moveq   #-1,%d0
        movel   %d0,%a0@
        movel   %d0,%a0@(4)
        movel   %d0,%a0@(8)
        movel   %sp@+,%d0
        rts

| copy12: a0 -> a1, 12 bytes. Clobbers nothing.
copy12: movel   %a0@,%a1@
        movel   %a0@(4),%a1@(4)
        movel   %a0@(8),%a1@(8)
        rts

| 0x4006036e, placing a trig: stock fills the step's 32 lock bytes with
| 0xff right after; page 2 goes too. d3 = the step after the replay.
plk_place:
        lsll    #4,%d6                 | the displaced instructions
        movel   %a5,%d3
        addl    %d6,%d3
        lea     %sp@(-16),%sp
        movem.l %d0-%d2/%a0,%sp@
        bsr.w   plk_init
        bsr.w   ui_bank
        moveq   #0,%d1
        moveb   UI_PTN,%d1
        moveq   #0,%d2
        moveb   UI_TRACK,%d2
        bsr.w   track_ptr
        moveq   #REC,%d0
        mulu.l  %d3,%d0
        addal   %d0,%a0
        bsr.w   fill12
        bsr.w   ui_bank
        bsr.w   nv_touch
        movem.l %sp@,%d0-%d2/%a0
        lea     %sp@(16),%sp
        jmp     0x40060374

| 0x40040e14(pattern, track, page, mask): clear the held steps' locks.
plk_clrlocks:
        lea     %sp@(-20),%sp
        movem.l %d0-%d3/%a0,%sp@
        bsr.w   plk_init
        bsr.w   ui_bank
        movel   %sp@(24),%d1           | pattern
        movel   %sp@(28),%d2           | track
        bsr.w   track_ptr
        moveq   #0,%d1
        moveb   %sp@(35),%d1           | page
        lsll    #4,%d1
        moveq   #0,%d3
        movew   %sp@(38),%d3           | mask
        bsr.w   clr_mask               | a0 track, d1 first step, d3 mask
        bsr.w   ui_bank
        bsr.w   nv_touch
        movem.l %sp@,%d0-%d3/%a0
        lea     %sp@(20),%sp
        lea     %sp@(-44),%sp          | the displaced prologue, then on
        movem.l %d2-%d7/%a2-%fp,%sp@
        jmp     0x40040e1c

| clr_mask: a0 = track, d1 = the page's first step, d3 = mask. Clobbers d0, d3, a1.
clr_mask:
        movel   %a0,%sp@-
        movel   %a0,%sp@-              | sp@ = the track
cm_loop:
        tstl    %d3
        beq.s   cm_done
        movel   %d3,%d0
        negl    %d0
        andl    %d3,%d0
        eorl    %d0,%d3
        ff1     %d0
        negl    %d0
        addil   #31,%d0                | the bit
        addl    %d1,%d0                | the step
        MUL12   %d0,%a1
        moveal  %sp@,%a0
        addal   %d0,%a0
        bsr.w   fill12
        bra.s   cm_loop
cm_done:
        addql   #4,%sp
        moveal  %sp@+,%a0
        rts

| 0x40039df4(pattern, track, flags): bit 0 clears the track's steps and
| their locks; page 2 goes with them.
plk_clrtrack:
        movel   %sp@(12),%d0
        btst    #0,%d0
        beq.s   ct_out
        lea     %sp@(-16),%sp
        movem.l %d0-%d2/%a0,%sp@
        bsr.w   plk_init
        bsr.w   ui_bank
        movel   %sp@(20),%d1
        movel   %sp@(24),%d2
        bsr.w   track_ptr
        moveq   #-1,%d0
        movel   #TRACK_B/4,%d1
ct_loop:
        movel   %d0,%a0@+
        subql   #1,%d1
        bne.s   ct_loop
        bsr.w   ui_bank
        bsr.w   nv_touch
        movem.l %sp@,%d0-%d2/%a0
        lea     %sp@(16),%sp
ct_out: lea     %sp@(-60),%sp          | the displaced prologue, then on
        movem.l %d2-%d7/%a2-%fp,%sp@
        jmp     0x40039dfc

| buf_of: d0 = a stock buffer address -> a1 = its page-2 mirror, or 0.
buf_of: lea     P2BUF0,%a1
        cmpil   #CLIP,%d0
        beq.s   bo_rts
        lea     P2BUF1,%a1
        cmpil   #UNDO,%d0
        beq.s   bo_rts
        suba.l  %a1,%a1
bo_rts: rts

| 0x4002bf38(clip, pattern, track, page, mask): a trig copy writes one
| record a held step, record b = the step's bit on the page. Page 2 goes
| to the buffer's mirror at b*12.
plk_tcopy:
        lea     %sp@(-28),%sp
        movem.l %d0-%d4/%a0-%a1,%sp@
        bsr.w   plk_init
        movel   %sp@(32),%d0           | clip
        bsr.w   buf_of
        movel   %a1,%d0
        beq.s   tc_out
        bsr.w   ui_bank
        movel   %sp@(36),%d1
        movel   %sp@(40),%d2
        bsr.w   track_ptr              | a0 = the track
        moveq   #0,%d4
        moveb   %sp@(47),%d4
        lsll    #4,%d4                 | the page's first step
        moveq   #0,%d3
        movew   %sp@(50),%d3           | mask
        movel   %a0,%d2
tc_loop:
        tstl    %d3
        beq.s   tc_out
        movel   %d3,%d0
        negl    %d0
        andl    %d3,%d0
        eorl    %d0,%d3
        ff1     %d0
        negl    %d0
        addil   #31,%d0                | b
        movel   %a1,%sp@-
        movel   %d0,%d1
        MUL12   %d1,%a0
        addal   %d1,%a1                | the record's mirror
        addl    %d4,%d0
        MUL12   %d0,%a0
        moveal  %d2,%a0
        addal   %d0,%a0                | the step
        bsr.w   copy12
        moveal  %sp@+,%a1
        bra.s   tc_loop
tc_out: movem.l %sp@,%d0-%d4/%a0-%a1
        lea     %sp@(28),%sp
        lea     %sp@(-64),%sp          | the displaced prologue, then on
        movem.l %d2-%d7/%a2-%fp,%sp@
        jmp     0x4002bf40

| 0x4002cb52, inside the trig paste 0x4002c89c(clip, pattern, track, ...)
| before its lock loop: d4 = the source record, d5 = the destination step;
| the frame's arguments at sp@(96).
plk_tpaste:
        addal   #0x1001614f,%a0        | the displaced instruction
        lea     %sp@(-20),%sp
        movem.l %d0-%d2/%a0-%a1,%sp@
        bsr.w   plk_init
        movel   %sp@(20+96),%d0        | clip
        bsr.w   buf_of
        movel   %a1,%d0
        beq.s   tp_out
        moveq   #REC,%d0
        mulu.l  %d4,%d0
        addal   %d0,%a1                | the record's mirror
        movel   %a1,%sp@-
        bsr.w   ui_bank
        movel   %sp@(24+100),%d1
        movel   %sp@(24+104),%d2
        bsr.w   track_ptr
        moveq   #REC,%d0
        mulu.l  %d5,%d0
        addal   %d0,%a0                | the destination step
        moveal  %a0,%a1
        moveal  %sp@+,%a0
        bsr.w   copy12
        bsr.w   ui_bank
        bsr.w   nv_touch
tp_out: movem.l %sp@,%d0-%d2/%a0-%a1
        lea     %sp@(20),%sp
        jmp     0x4002cb58

| memcpy(dst, src, n), at the stock call sites that copy patterns and
| tracks (memcpy itself runs before the loader has placed this unit): a
| pattern (0x8ed8) or a track (0x91a) copied between the bank RAM, the
| clipboard and the undo buffer takes its page 2 along, in the same
| shape. memcpy clobbers d0, d1, a0, a1.
plk_memcpy:
        movel   %sp@(12),%d0
        cmpil   #TRK_STRIDE,%d0
        beq.s   mc_go
        cmpil   #PTN_STRIDE,%d0
        bne.w   mc_stock
mc_go:  movel   INITED,%d1
        cmpil   #MAGIC,%d1
        bne.w   mc_stock
        lea     %sp@(-12),%sp
        movem.l %d2-%d4,%sp@
        movel   %sp@(12+8),%d0         | src
        bsr.w   p2loc                  | -> a0, d1 = track
        movel   %a0,%d0
        beq.w   mc_out
        movel   %d1,%d3
        moveal  %a0,%a1
        movel   %sp@(12+4),%d0         | dst
        bsr.w   p2loc
        movel   %a0,%d0
        beq.w   mc_out
        movel   %a0,%d4                | a0 = src, a1 = dst
        moveal  %a1,%a0
        moveal  %d4,%a1
        movel   #TRACK_B/4,%d2         | longs: one track ...
        movel   %sp@(12+12),%d0
        cmpil   #PTN_STRIDE,%d0
        bne.s   mc_copy
        orl     %d1,%d3                | ... or a whole pattern, both at track 0
        bne.w   mc_out
        lsll    #3,%d2
mc_copy:
        movel   %a0@+,%a1@+
        subql   #1,%d2
        bne.s   mc_copy
        movel   %a1,%d0                | a1 is past the copy: its start's bank
        subil   #TRACK_B,%d0
        movel   %sp@(12+12),%d1
        cmpil   #PTN_STRIDE,%d1
        bne.s   mc_t
        subil   #7*TRACK_B,%d0
mc_t:   subil   #STORE,%d0
        bcs.s   mc_out
        movel   #BANK_B,%d1
        divu.l  %d1,%d0
        cmpil   #16,%d0
        bcc.s   mc_out
        bsr.w   nv_touch               | CS1, when it holds that bank
mc_out: movem.l %sp@,%d2-%d4
        lea     %sp@(12),%sp
mc_stock:
        jmp     0x40020898             | stock memcpy, the caller's frame as it was

| p2loc: d0 = an address -> a0 = the page-2 track block that mirrors it
| (a track's start in a bank's patterns, the clipboard or the undo
| buffer), d1 = its track; a0 = 0 otherwise. Clobbers d0, d1, d4.
p2loc:  movel   %d0,%d1
        subil   #CLIP,%d1
        bcs.w   pl_undo
        cmpil   #8*TRK_STRIDE,%d1
        bcc.w   pl_undo
        lea     P2BUF0,%a0
        bra.w   pl_buf
pl_undo:
        movel   %d0,%d1
        subil   #UNDO,%d1
        bcs.w   pl_ram
        cmpil   #8*TRK_STRIDE,%d1
        bcc.w   pl_ram
        lea     P2BUF1,%a0
pl_buf: movel   %d1,%d0                | d1 = the offset in the buffer
        movel   #TRK_STRIDE,%d4
        divu.l  %d4,%d0                | track
        mulu.l  %d0,%d4
        cmpl    %d4,%d1
        bne.w   pl_none                | not a track's start
        movel   #TRACK_B,%d4
        mulu.l  %d0,%d4
        addal   %d4,%a0
        movel   %d0,%d1
        rts
pl_ram: movel   %d0,%d1
        subil   #BLOB,%d1
        bcs.w   pl_none
        cmpil   #16*BANK_STRIDE,%d1
        bcc.w   pl_none
        movel   #BANK_STRIDE,%d4
        movel   %d1,%d0
        divu.l  %d4,%d0                | bank
        mulu.l  %d0,%d4
        subl    %d4,%d1                | the offset in the bank
        cmpil   #16*PTN_STRIDE,%d1
        bcc.w   pl_none
        moveal  %d0,%a0                | a0 = bank
        movel   #PTN_STRIDE,%d4
        movel   %d1,%d0
        divu.l  %d4,%d0                | pattern
        mulu.l  %d0,%d4
        subl    %d4,%d1                | the offset in the pattern
        movel   %a0,%d4
        lsll    #4,%d4
        addl    %d0,%d4
        moveal  %d4,%a0                | a0 = bank*16 + pattern
        movel   #TRK_STRIDE,%d4
        movel   %d1,%d0
        divu.l  %d4,%d0                | track
        mulu.l  %d0,%d4
        cmpl    %d4,%d1
        bne.w   pl_none
        cmpil   #8,%d0
        bcc.w   pl_none
        movel   %a0,%d4
        lsll    #3,%d4
        addl    %d0,%d4
        movel   %d0,%d1                | the track, returned
        moveal  %d4,%a0
        addl    %d4,%d4
        addl    %a0,%d4                | x3
        lsll    #8,%d4                 | x768
        addil   #STORE,%d4
        moveal  %d4,%a0
        rts
pl_none:
        suba.l  %a0,%a0
        rts

| ----------------------------------------------------------------- files ----
| One file a bank beside stock's, p2lkNN.work and p2lkNN.strd: 16 bytes of
| header ('P2LK', version 1, bank, length) then the bank's 98,304 bytes.
| Stock writes bankNN.work from RAM and copies .work <-> .strd on a store
| or a reload; the same happens here, by name.

| path: d0 = bank, a0 = format -> PATH. The C convention: d0, d1, a0, a1
| are the callee's.
path:   lea     %sp@(-8),%sp
        movem.l %d2/%a2,%sp@
        movel   %d0,%d2
        addql   #1,%d2
        moveal  %a0,%a2
        clrl    %sp@-
        clrl    %sp@-
        jsr     PROJDIR
        addql   #8,%sp
        movel   %d2,%sp@-
        movel   %d0,%sp@-
        movel   %a2,%sp@-
        pea     PATH
        jsr     SPRINTF
        lea     %sp@(16),%sp
        movem.l %sp@,%d2/%a2
        lea     %sp@(8),%sp
        rts

| fopen: a0 = path, a1 = mode -> d0 (< 0: failed).
fopen:  pea     IOB_LEN
        pea     IOB
        movel   %a1,%sp@-
        movel   %a0,%sp@-
        pea     FOBJ
        jsr     F_OPEN
        lea     %sp@(20),%sp
        rts

| fio: a0 = buffer, d0 = length, a1 = F_READ or F_WRITE -> d0 (1 = done).
fio:    movel   %d0,%sp@-
        movel   %a0,%sp@-
        pea     FOBJ
        jsr     %a1@
        lea     %sp@(12),%sp
        rts

fclose: pea     FOBJ
        jsr     F_CLOSE
        addql   #4,%sp
        rts

| bank_at: d0 = bank -> a0 = its page 2 in STORE.
bank_at:
        movel   #BANK_B,%d1
        mulu.l  %d1,%d0
        addil   #STORE,%d0
        moveal  %d0,%a0
        rts

| blank: d0 = bank -> its page 2 all 0xff. Keeps d2-d7/a2-a6.
blank:  bsr.w   bank_at
        moveq   #-1,%d0
        movel   #BANK_B/4,%d1
bl_loop:
        movel   %d0,%a0@+
        subql   #1,%d1
        bne.s   bl_loop
        rts

| hdr: d0 = bank -> HDR filled.
hdr:    lea     HDR,%a0
        movel   #0x50324c4b,%a0@       | 'P2LK'
        moveq   #1,%d1
        movel   %d1,%a0@(4)
        movel   %d0,%a0@(8)
        movel   #BANK_B,%d1
        movel   %d1,%a0@(12)
        rts

| write_bank: d0 = bank -> p2lkNN.work from RAM. Keeps d2-d7/a2-a6.
write_bank:
        movel   NWMASK,%d1
        btst    %d0,%d1
        beq.s   wb_go
        rts                            | a refused file is never written over
wb_go:  movel   %d2,%sp@-
        movel   %d0,%d2
        movel   BKMASK,%d1
        btst    %d2,%d1
        beq.s   wb_nb
        bclr    %d2,%d1
        movel   %d1,BKMASK
        movel   %d2,%d0                | the refused file kept as p2lkNN.bak
        lea     FMT_WORK,%a0
        bsr.w   path
        lea     PATH,%a0
        lea     PSRC,%a1
wb_cp:  moveb   %a0@+,%a1@+
        bne.s   wb_cp
        movel   %d2,%d0
        lea     FMT_BAK,%a0
        bsr.w   path
        clrl    %sp@-
        pea     PSRC
        pea     PATH
        jsr     F_COPY
        lea     %sp@(12),%sp
wb_nb:
        lea     FMT_WORK,%a0
        bsr.w   path
        lea     PATH,%a0
        lea     MODE_W,%a1
        bsr.w   fopen
        tstl    %d0
        bmi.s   wb_out
        movel   %d2,%d0
        bsr.w   hdr
        lea     HDR,%a0
        moveq   #16,%d0
        lea     F_WRITE,%a1
        bsr.w   fio
        movel   %d2,%d0
        bsr.w   bank_at
        movel   #BANK_B,%d0
        lea     F_WRITE,%a1
        bsr.w   fio
        bsr.w   fclose
wb_out: movel   %sp@+,%d2
        rts

| read_bank: d0 = bank -> RAM from p2lkNN.work; a missing or foreign file
| reads as no locks. Keeps d2-d7/a2-a6.
read_bank:
        movel   %d2,%sp@-
        movel   %d0,%d2
        movel   NWMASK,%d1
        bclr    %d2,%d1
        movel   %d1,NWMASK
        lea     FMT_WORK,%a0
        bsr.w   path
        lea     PATH,%a0
        lea     MODE_R,%a1
        bsr.w   fopen
        tstl    %d0
        bmi.s   rb_blank
        lea     HDR,%a0
        moveq   #16,%d0
        lea     F_READ,%a1
        bsr.w   fio
        subql   #1,%d0
        bne.s   rb_bad
        lea     HDR,%a0
        movel   %a0@,%d0
        cmpil   #0x50324c4b,%d0
        bne.s   rb_bad
        movel   %a0@(4),%d0            | the version hdr writes
        subql   #1,%d0
        bne.s   rb_bad
        movel   %a0@(12),%d0
        cmpil   #BANK_B,%d0
        bne.s   rb_bad
        movel   %d2,%d0
        bsr.w   bank_at
        movel   #BANK_B,%d0
        lea     F_READ,%a1
        bsr.w   fio
        subql   #1,%d0
        bne.s   rb_bad
        bsr.w   fclose
        bra.s   rb_out
rb_bad: bsr.w   fclose
        movel   NWMASK,%d1             | an unusable file: kept, and offered to the prompt
        bset    %d2,%d1
        movel   %d1,NWMASK
        moveq   #0,%d0
        movel   %d2,%d1
        jsr     store_refuse
rb_blank:
        movel   %d2,%d0
        bsr.w   blank
rb_out: movel   %sp@+,%d2
        rts

| bankw_pre (d1 = the mask): inside stock's bank write 0x400917c8, after the
| project directory is made and before the first bankNN.work. Ours go
| first, the same banks.
plk_st_bankw_pre:
        bsr.w   plk_init
        moveq   #0,%d3
        movew   %d1,%d3                | the mask
        moveq   #0,%d4                 | bank
sb_loop:
        btst    %d4,%d3
        beq.s   sb_next
        movel   %d4,%d0
        bsr.w   write_bank
sb_next:
        addql   #1,%d4
        cmpil   #16,%d4
        bne.s   sb_loop
        rts

| bankcopy (d0 = dst, d1 = src): after the stock file copy (dst, src, 0) at
| the bank store, bank reload, project store and project reload sites. When
| both are bankNN files, p2lkNN follows; a missing source leaves an empty
| destination (a bank stored before PLOCKS P2 has no page-2 locks).
plk_st_bankcopy:
        movel   %d0,%d4                | dst
        moveal  %d1,%a0                | src
        lea     PSRC,%a1
        bsr.w   rename
        tstl    %d0
        beq.w   fc_out
        moveal  %d4,%a0
        lea     PATH,%a1
        bsr.w   rename
        tstl    %d0
        beq.w   fc_out
        clrl    %sp@-
        pea     PSRC
        pea     PATH
        jsr     F_COPY
        lea     %sp@(12),%sp
        tstl    %d0
        bpl.w   fc_out
        lea     PATH,%a0               | no source: an empty destination
        lea     MODE_W,%a1
        bsr.w   fopen
        tstl    %d0
        bmi.w   fc_out
        moveq   #-1,%d0                | the bank is in HDR's slot; unused
        bsr.w   hdr
        lea     HDR,%a0
        moveq   #16,%d0
        lea     F_WRITE,%a1
        bsr.w   fio
        lea     IOB,%a0
        moveq   #-1,%d0
        movel   #IOB_LEN/4,%d1
fc_fill:
        movel   %d0,%a0@+
        subql   #1,%d1
        bne.s   fc_fill
        moveq   #BANK_B/IOB_LEN,%d2
fc_wr:  lea     IOB,%a0
        movel   #IOB_LEN,%d0
        lea     F_WRITE,%a1
        bsr.w   fio
        subql   #1,%d2
        bne.s   fc_wr
        bsr.w   fclose
fc_out: rts

| rename: a0 = a stock path, a1 = 260 bytes -> a1 = the same path with its
| "/bankNN." made "/p2lkNN."; d0 = 0 when the path names no bank file.
rename: movel   %a1,%sp@-
        moveal  %a0,%a2                | a2 = the last "/bank" seen
        suba.l  %a3,%a3
        moveq   #0,%d0
rn_copy:
        moveb   %a0@+,%d1
        moveb   %d1,%a1@+
        addql   #1,%d0
        cmpil   #259,%d0
        bcc.s   rn_none
        tstb    %d1
        beq.s   rn_end
        cmpib   #'/',%d1
        bne.s   rn_copy
        moveb   %a0@,%d1
        cmpib   #'b',%d1
        bne.s   rn_copy
        moveb   %a0@(1),%d1
        cmpib   #'a',%d1
        bne.s   rn_copy
        moveb   %a0@(2),%d1
        cmpib   #'n',%d1
        bne.s   rn_copy
        moveb   %a0@(3),%d1
        cmpib   #'k',%d1
        bne.s   rn_copy
        moveal  %a1,%a3                | a3 = where "bank" lands in the copy
        bra.s   rn_copy
rn_end: movel   %a3,%d0
        beq.s   rn_none
        moveb   #'p',%a3@+
        moveb   #'2',%a3@+
        moveb   #'l',%a3@+
        moveb   #'k',%a3@
        moveal  %sp@+,%a1
        moveq   #1,%d0
        rts
rn_none:
        moveal  %sp@+,%a1
        moveq   #0,%d0
        rts

| loadall: at the project load's bank load (0x40090504) -- every bank's
| page 2 from its file.
plk_st_loadall_pre:
        bsr.w   plk_init
        bsr.w   reset_pipe
        clrl    NEEDFILE
        moveq   #0,%d3
la_loop:
        movel   %d3,%d0
        bsr.w   read_bank
        movel   %d3,%d0
        bsr.w   nv_touch
        addql   #1,%d3
        cmpil   #16,%d3
        bne.s   la_loop
        rts

| loadmask (d1 = the mask): at the masked bank loads (0x400905d4) -- the
| masked banks.
plk_st_loadmask_pre:
        bsr.w   plk_init
        moveq   #0,%d3
        movew   %d1,%d3                | the mask
        moveq   #0,%d4
lm_loop:
        btst    %d4,%d3
        beq.s   lm_next
        movel   %d4,%d0
        bsr.w   read_bank
        movel   %d4,%d0
        bsr.w   nv_touch
lm_next:
        addql   #1,%d4
        cmpil   #16,%d4
        bne.s   lm_loop
        movel   NEEDFILE,%d0           | the power-up's CS1 bank with no copy there
        beq.s   lm_done
        clrl    NEEDFILE
        subql   #1,%d0
        movel   %d0,%d4
        bsr.w   read_bank
        movel   %d4,%d0
        bsr.w   nv_save
lm_done:
        rts

| answer (d0 = IGNORE / OVERWRITE / BACKUP, d1 = the bank) for a refused
| p2lkNN.work: BACKUP has the bank's next write copy the file to p2lkNN.bak
| first (the answer runs in the UI task, the write in the engine task, where
| the card is used); then the bank may be written (its locks are in RAM as
| none) at the next bank write.
plk_st_answer:
        tstl    %d0
        beq.s   an_out
        movel   %d1,%d2
        cmpil   #2,%d0
        bne.s   an_clear
        movel   BKMASK,%d0
        bset    %d2,%d0
        movel   %d0,BKMASK             | write_bank copies the file first
an_clear:
        movel   NWMASK,%d0
        bclr    %d2,%d0
        movel   %d0,NWMASK
an_out: rts

| newproj: a new, empty project (0x400909d8): no page-2 locks.
plk_st_newproj:
        clrl    NWMASK
        lea     %sp@(-8),%sp
        movem.l %d0-%d1,%sp@
        movel   INITED,%d0             | uninitialised: plk_init fills it anyway
        cmpil   #MAGIC,%d0
        bne.s   np_init
        moveq   #0,%d0
np_loop:
        movel   %d0,%sp@-
        bsr.w   blank
        movel   %sp@+,%d0
        addql   #1,%d0
        cmpil   #16,%d0
        bne.s   np_loop
        bsr.s   reset_pipe
        bra.s   np_out
np_init:
        bsr.w   plk_init
np_out: movem.l %sp@,%d0-%d1
        lea     %sp@(8),%sp
        rts

| reset_pipe: the pipeline records to 0xff, the masks to 0. Keeps registers.
reset_pipe:
        lea     %sp@(-12),%sp
        movem.l %d0-%d1/%a0,%sp@
        moveq   #-1,%d0
        lea     P2STAGE,%a0
        moveq   #((8+24+8)*REC/4),%d1
rp_loop:
        movel   %d0,%a0@+
        subql   #1,%d1
        bne.s   rp_loop
        lea     P2MASK,%a0
        clrl    %a0@+
        clrl    %a0@+
        clrl    %a0@+
        clrl    %a0@
        movem.l %sp@,%d0-%d1/%a0
        lea     %sp@(12),%sp
        rts

FMT_WORK:
        .asciz  "%s/p2lk%02d.work"
FMT_BAK:
        .asciz  "%s/p2lk%02d.bak"
MODE_R: .asciz  "r"
MODE_W: .asciz  "w"
        .align  4

| ------------------------------------------------------------------- CS1 ----
| Stock keeps the current bank in CS1 (0x10000000), the memory that holds
| over a power-off: 0x4000faf0(bank) copies a bank there, every edit writes
| through, and at power-up 0x40025770 checks it and 0x4000fbb4(bank) puts
| it back; the firmware's own load then reads every OTHER bank from the
| card (mask 0xfffb at 0x40084d60). The page-2 locks of that bank go the
| same way, sparse, in CS1's unused top (0x100f8600..0x100fbdf0, no stock
| reference and no module's; written only by stock's whole-CS1 init):
|   +0 'P2NV' (written last), +4 bank, +8 count, +12 sum of the entries,
|   +16 entries of 3 bytes: step index (bank-relative, 17 bits) << 7 | value.
| More locks than fit (NV_MAX), or an interrupted write, leave no magic:
| the power-up then reads that bank's p2lkNN.work instead.

| nv_save: d0 = bank -> CS1 holds its page 2. Keeps every register.
| Two tasks call it: the UI task (prio 3) and the engine task (prio 1), and
| the UI task preempts the engine task at any instruction, so a save can
| start and finish inside another's. Each start takes a ticket (NVGEN, with
| NVBANK, under SR 0x2700); the entry loop compares its ticket with NVGEN
| every four bytes, and the commit (count, sum, magic) runs under 0x2700
| after the same compare. A save that finds a newer ticket starts over from
| NVBANK, the newest request's bank, so the last writer to start is the one
| whose entries stand and the magic is never set over a mixture. The mask
| covers a few instructions; the scan of up to BANK_B bytes runs unmasked.
nv_save:
        lea     %sp@(-40),%sp
        movem.l %d0-%d5/%a0-%a1,%sp@
        move.w  %sr,%d1
        move.w  %d1,%sp@(36)           | the caller's SR
        move.w  #0x2700,%sr
        movel   %d0,NVBANK
        addql   #1,NVGEN
        movel   NVGEN,%d1
        movel   %d1,%sp@(32)           | this save's ticket
        move.w  %sp@(36),%d1
        move.w  %d1,%sr
ns_again:
        movel   NVBANK,%d0
        lea     NV,%a1
        clrl    %a1@                   | no magic while it is written
        movel   %d0,%a1@(4)
        bsr.w   bank_at                | a0 = the bank's page 2
        lea     %a1@(16),%a1
        moveq   #0,%d2                 | count
        moveq   #0,%d3                 | sum
        moveq   #0,%d4                 | index
ns_loop:
        movel   %sp@(32),%d1
        cmpl    NVGEN,%d1
        bne.w   ns_again               | a newer save started meanwhile
        cmpil   #BANK_B,%d4
        bcc.s   ns_done
        movel   %a0@(0,%d4:l),%d0      | four at a time past the empty ones
        moveq   #-1,%d1
        cmpl    %d1,%d0
        bne.s   ns_byte
        addql   #4,%d4
        bra.s   ns_loop
ns_byte:
        moveq   #3,%d5
ns_b4:  moveq   #0,%d0
        moveb   %a0@(0,%d4:l),%d0
        cmpil   #0xff,%d0
        beq.s   ns_next
        cmpil   #0x7f,%d0
        bhi.s   ns_fail                | not a knob value: no copy
        cmpil   #NV_MAX,%d2
        bcc.s   ns_fail                | does not fit: no copy
        movel   %d4,%d1
        lsll    #7,%d1
        orl     %d0,%d1                | the entry
        addl    %d1,%d3
        moveb   %d1,%a1@(2)
        lsrl    #8,%d1
        moveb   %d1,%a1@(1)
        lsrl    #8,%d1
        moveb   %d1,%a1@
        addql   #3,%a1
        addql   #1,%d2
ns_next:
        addql   #1,%d4
        subql   #1,%d5
        bpl.s   ns_b4
        bra.s   ns_loop
ns_fail:
        moveq   #-1,%d2                | commit nothing, magic stays clear
ns_done:
        move.w  #0x2700,%sr
        movel   %sp@(32),%d1
        cmpl    NVGEN,%d1
        beq.s   ns_commit
        move.w  %sp@(36),%d1           | a newer save started: unmask, start over
        move.w  %d1,%sr
        bra.w   ns_again
ns_commit:
        tstl    %d2
        bmi.s   ns_end
        lea     NV,%a1
        movel   %d2,%a1@(8)
        movel   %d3,%a1@(12)
        movel   #NV_MAGIC,%d0
        movel   %d0,%a1@
ns_end: move.w  %sp@(36),%d1
        move.w  %d1,%sr
        movem.l %sp@,%d0-%d5/%a0-%a1
        lea     %sp@(40),%sp
        rts

| nv_apply: d0 = bank -> 1 in d0 when CS1 held that bank's page 2 and it
| is in STORE now; 0 otherwise (STORE untouched).
nv_apply:
        lea     %sp@(-28),%sp
        movem.l %d1-%d5/%a0-%a1,%sp@
        movel   %d0,%d5
        lea     NV,%a1
        movel   %a1@,%d0
        cmpil   #NV_MAGIC,%d0
        bne.s   na_no
        cmpl    %a1@(4),%d5
        bne.s   na_no
        movel   %a1@(8),%d2
        cmpil   #NV_MAX,%d2
        bhi.s   na_no
        lea     %a1@(16),%a0           | the sum first
        moveq   #0,%d3
        movel   %d2,%d4
na_sum: subql   #1,%d4
        bmi.s   na_chk
        bsr.s   nv_entry
        addl    %d1,%d3
        bra.s   na_sum
na_chk: cmpl    %a1@(12),%d3
        bne.s   na_no
        movel   %d5,%d0
        bsr.w   blank
        movel   %d5,%d0
        bsr.w   bank_at
        moveal  %a0,%a1                | a1 = the bank's page 2
        lea     NV+16,%a0
na_put: subql   #1,%d2
        bmi.s   na_yes
        bsr.s   nv_entry
        movel   %d1,%d0
        lsrl    #7,%d0                 | index
        andil   #0x7f,%d1              | value
        cmpil   #BANK_B,%d0
        bcc.s   na_put
        moveb   %d1,%a1@(0,%d0:l)
        bra.s   na_put
na_yes: movel   %d5,NVBANK
        moveq   #1,%d0
        bra.s   na_out
na_no:  moveq   #0,%d0
na_out: movem.l %sp@,%d1-%d5/%a0-%a1
        lea     %sp@(28),%sp
        rts

| nv_entry: a0 = an entry -> d1 = its 24 bits, a0 past it. Clobbers d0.
nv_entry:
        moveq   #0,%d1
        moveb   %a0@+,%d1
        lsll    #8,%d1
        moveq   #0,%d0
        moveb   %a0@+,%d0
        orl     %d0,%d1
        lsll    #8,%d1
        moveb   %a0@+,%d0
        orl     %d0,%d1
        rts

| nv_touch: d0 = a bank whose page 2 changed -> CS1 again when it is the
| bank CS1 holds. Keeps every register.
nv_touch:
        movel   %d1,%sp@-
        movel   NVBANK,%d1
        cmpl    %d0,%d1
        bne.s   nt_out
        bsr.w   nv_save
nt_out: movel   %sp@+,%d1
        rts

| tocs1 (d0 = the bank): stock copies the bank into CS1; its page 2 goes too.
plk_st_tocs1:
        movel   %d0,%d3
        bsr.w   plk_init
        movel   %d3,%d0
        bra.w   nv_save

| fromcs1 (d0 = the bank): the power-up's 0x4000fbb4(bank) call at
| 0x40025808 has put the bank back from CS1; its page 2 comes with it -- or,
| when CS1 has no copy of it, from its file at the first bank load (the card
| is not mounted yet).
plk_st_fromcs1:
        movel   %d0,%d3
        bsr.w   plk_init
        movel   %d3,%d0
        movel   %d0,%d1
        bsr.w   nv_apply
        tstl    %d0
        bne.s   fc1_out
        addql   #1,%d1
        movel   %d1,NEEDFILE
        subql   #1,%d1
        movel   %d1,NVBANK
fc1_out:
        rts

| ------------------------------------------------------------------ dial ----
| plk_dial: d0 = the value the dial would draw, d6 = kind (0 FX1, 1 FX2),
| d4 = slot2 -> d0. With trigs held on an audio track: the first held
| step's lock, when there is one. Keeps everything but d0.
plk_dial:
        lea     %sp@(-16),%sp
        movem.l %d0-%d2/%a0,%sp@       | sp@ = the fallback
        movel   INITED,%d1
        cmpil   #MAGIC,%d1
        bne.w   dl_out
        tstw    HELD
        beq.w   dl_out
        tstl    MIDITRK
        bne.w   dl_out
        moveq   #0,%d0
        movew   HELD,%d0
        movel   %d0,%d1
        negl    %d1
        andl    %d1,%d0
        ff1     %d0
        moveq   #31,%d2
        subl    %d0,%d2
        addl    STEPPAGE,%d2           | d2 = the first held step
        cmpil   #63,%d2
        bhi.w   dl_out
        movel   DBPTR,%d0
        subil   #BLOB,%d0
        movel   #BANK_STRIDE,%d1
        divu.l  %d1,%d0
        lsll    #4,%d0
        moveq   #0,%d1
        moveb   UI_PTN,%d1
        addl    %d1,%d0
        lsll    #3,%d0
        moveb   UI_TRACK,%d1
        addl    %d1,%d0
        lsll    #6,%d0
        addl    %d2,%d0
        moveq   #REC,%d1
        mulu.l  %d1,%d0
        movel   %d6,%d1
        movel   %d1,%d2
        addl    %d1,%d1
        addl    %d2,%d1
        addl    %d1,%d1                | kind*6
        addl    %d4,%d1
        addl    %d1,%d0
        addil   #STORE,%d0
        moveal  %d0,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        cmpil   #0xff,%d0
        beq.w   dl_out
        movel   %d0,%sp@               | the lock replaces the fallback
dl_out: movem.l %sp@,%d0-%d2/%a0
        lea     %sp@(16),%sp
        rts

| ------------------------------------------------------------------ init ----
| plk_init: once, STORE and the pipeline records to 0xff. Keeps registers.
plk_init:
        lea     %sp@(-12),%sp
        movem.l %d0-%d1/%a0,%sp@
        movel   INITED,%d0
        cmpil   #MAGIC,%d0
        beq.s   in_out
        moveq   #-1,%d0
        lea     STORE,%a0
        movel   #(STORE_LEN+2*8*TRACK_B)/4,%d1
in_loop:
        movel   %d0,%a0@+
        subql   #1,%d1
        bne.s   in_loop
        lea     P2STAGE,%a0
        moveq   #((8+24+8)*REC/4),%d1
in_l2:  movel   %d0,%a0@+
        subql   #1,%d1
        bne.s   in_l2
        lea     P2MASK,%a0
        clrl    %a0@+
        clrl    %a0@+
        clrl    %a0@+
        clrl    %a0@
        movel   #MAGIC,%d0
        movel   %d0,INITED
in_out: movem.l %sp@,%d0-%d1/%a0
        lea     %sp@(12),%sp
        rts

| In .text: the depacked window is RAM. P2STAGE, P2PEND and P2REC are
| contiguous (plk_init fills them as one run).
        .align  4
INITED: .long   0
NVBANK: .long   -1                      | the bank whose page 2 CS1 holds
BKMASK:  .long 0                        | banks whose refused p2lkNN.work is copied to .bak at the next write
NWMASK:  .long 0                        | banks whose p2lkNN.work was refused: not written
NEEDFILE: .long 0                       | bank + 1: read it from its file at the next bank load
NVGEN:  .long   0                       | counts nv_save starts (see nv_save)
EDITED: .long   0                       | set by a page-2 lock edit (the file pass reads it)
P2STAGE: .fill  8*REC,1,0xff            | the staging record, by track
P2PEND: .fill   24*REC,1,0xff           | pending slots n = 0..2, index n*8 + track
P2REC:  .fill   8*REC,1,0xff            | the trig record, by track
P2MASK: .fill   8,2,0                   | bits: the slots the last trig locked, by track

        .section .bss
        .align  4
STORE:  .space  STORE_LEN
P2BUF0: .space  8*TRACK_B               | the clipboard's page 2, track-shaped (trig copies: record b at b*12)
P2BUF1: .space  8*TRACK_B               | the undo buffer's
FOBJ:   .space  24                      | the stock file object
HDR:    .space  16
PATH:   .space  260
PSRC:   .space  260
        .align  4
IOB:    .space  IOB_LEN                 | the stock file layer's buffer
