| DLPUMP -- sends a staged block to a DSP core's X memory, CHUNK words per
| frame interrupt, then the doorbell word one frame later.
|
| dl_pump is called from LOAD METER's lm_in (the frame interrupt's entry, after
| its prologue and entry stamp), where every register is saved and the
| stock frame chain has not started. The transfer is the stock host write
| (FUN_40001b18): destination word, count-1, then three register writes per word;
| only the low 16 bits of each word arrive, so the block is halfwords (the
| DSP copier reassembles the 24-bit code words). The chip-select goes back to
| core A on exit: the frame interrupt sends 0x8c to whichever core is selected.
|
| Under the port a transfer started at the entry of a frame whose ping word
| (0x800000e0, flipped once per frame) is 1 is lost, and one started at ping 0
| arrives whole (tools/verify/verify_dlpump.py, a chunk of 100 words on each
| frame of both phases, core B). The pump therefore sends on ping-0 frames only.
| Whether the unit loses the same frames is open. The PHASE build setting ANY sends on every
| frame (remixes/test/dl-probe-any), to measure it: the copier's sum check counts what arrives.
|
| State, set by whoever arms the pump (dl_state last):
|   dl_core  0 = core A, 1 = core B
|   dl_dest  X word address of the first halfword (0x0000..0x3fff)
|   dl_src   address of the first halfword (.word)
|   dl_left  halfwords to send
|   dl_state 0 idle, 1 sending, 2 doorbell due (set by the pump)

        .equ    HOST,   0x20000000
        .equ    CSEL,   0xfc0a400c
        .equ    CHUNK,  100
        .equ    BELL,   0x2900                  | X staging word the DSP polls
        .equ    LIVE,   0x80000ec4              | the live FX1 and FX2 ids of tracks 1-8
        .equ    STAGE1, 0x2901                  | the first word of a staged message
        .equ    TOAST,  0x4005a2b8              | the firmware's message popup (text, duration)
        .equ    TOAST_TIME, 120                 | 1/60 s ticks: 2 s (stock's own calls use 48)
        .equ    DEBOUNCE, 200                   | idle calls (about 145 ms) an effect is used on a free block before it is loaded
        .equ    REPEAT, 30                      | idle calls (ping-0 frames) between a load and its second send
        .equ    RING,   0xa55a
        .equ    PING,   0                       | the frames whose host writes the port delivers (below)

        .data
        .include "remix.inc"

        .text
        .globl  dl_pump
dl_pump:
        lea     dl_dg,%a1
        addq.l  #1,%a1@                         | DL_DIAG[0]: calls
        move.l  0x800000e0,%d1
        beq.w   dg_p0
        subq.l  #1,%d1
        beq.w   dg_p1
        addq.l  #1,%a1@(12)                     | [3]: ping neither 0 nor 1
        bra.w   dg_ok
dg_p0:  addq.l  #1,%a1@(4)                      | [1]: ping 0
        bra.w   dg_ok
dg_p1:  addq.l  #1,%a1@(8)                      | [2]: ping 1
dg_ok:  move.l  dl_state,%d0
        beq.w   idle
        .if     PHASE_ANY == 0
        moveq   #PING,%d1
        cmp.l   0x800000e0,%d1                  | the frame's ping word
        bne.w   9f
        .endif
        move.l  dl_core,%d4
        subq.l  #1,%d0
        bne.w   2f
        move.l  dl_left,%d2                     | state 1: the next chunk
        cmp.l   #CHUNK,%d2
        bls.w   1f
        moveq   #CHUNK,%d2
1:      move.l  dl_dest,%d1
        move.l  dl_src,%a0
        move.l  %d2,%d5
        bsr.w   dl_xfer
        lea     dl_dg,%a1
        addq.l  #1,%a1@(28)                     | [7]: chunks sent
        lea     dl_dest,%a1
        add.l   %d5,%a1@                        | dest += n
        lea     dl_src,%a1
        add.l   %d5,%d5
        add.l   %d5,%a1@                        | src += 2n
        lea     dl_left,%a1
        move.l  %a1@,%d0
        asr.l   #1,%d5
        sub.l   %d5,%d0
        move.l  %d0,%a1@
        bne.w   8f
        moveq   #2,%d0
        move.l  %d0,dl_state
        bra.w   8f
2:      move.l  #BELL,%d1                       | state 2: the doorbell
        lea     dl_bell,%a0
        moveq   #1,%d2
        bsr.w   dl_xfer
        lea     dl_dg,%a1
        addq.l  #1,%a1@(32)                     | [8]: doorbells sent
        clr.l   dl_state
8:      moveq   #0,%d0
        move.b  %d0,CSEL                        | the frame code expects core A selected
9:      rts

| Idle: compare the effects the tracks use with the ones loaded, on the frames the port delivers.
| One message is armed per call: a load (the effect is used, not loaded, and its block is not
| under a stock reverb) or a withdrawal (loaded and used by no track for GRACE idle calls). Whoever holds a block
| keeps it: a loaded effect is not withdrawn for a reverb, and a reverb is not moved for an effect.
idle:
        .if     PHASE_ANY == 0
        moveq   #PING,%d1
        cmp.l   0x800000e0,%d1
        bne.w   9b
        .endif
        move.l  dl_rwait,%d0                    | a load is sent three times: a later copy replaces one the DSP
        beq.w   4f                              | refused for its checksum
        subq.l  #1,%d0
        move.l  %d0,dl_rwait
        bne.w   9b
        move.l  dl_rk,%d6
        move.l  dl_loaded,%d0
        btst    %d6,%d0
        beq.w   4f                              | withdrawn meanwhile: dropped
        move.l  dl_rsrc,%d1
        move.l  dl_rlen,%d2
        lea     dl_dg,%a1
        addq.l  #1,%a1@(36)                     | [9]: repeats armed
        move.l  dl_rn,%d3
        subq.l  #1,%d3
        move.l  %d3,dl_rn
        beq.w   arm                             | the last repeat
        move.l  #REPEAT,%d3
        move.l  %d3,dl_rwait
        bra.w   arm
4:      lea     dl_dg,%a1
        addq.l  #1,%a1@(16)                     | [4]: idle passes on a delivering frame
        move.l  dl_loaded,%d0
        move.l  %d0,%a1@(40)                    | [10]: loaded bits
        move.l  dl_busy,%d1
        move.l  %d1,%a1@(44)                    | [11]: blocks holding code
        lea     LIVE,%a0
        move.l  %a0@+,%a1@(48)                  | [12..15]: the 16 live ids
        move.l  %a0@+,%a1@(52)
        move.l  %a0@+,%a1@(56)
        move.l  %a0@+,%a1@(60)
        lea     dl_tab,%a2
        moveq   #0,%d6                          | the effect's index
3:      cmp.l   #DL_N,%d6
        bcc.w   9b
        move.l  %a2@,%d2                        | its id
        moveq   #0,%d3                          | used by a track
        lea     LIVE,%a1                        | FX1 ids of tracks 1-8, then FX2's
        moveq   #15,%d4
4:      cmp.b   %a1@+,%d2
        bne.w   5f
        moveq   #1,%d3
5:      subq.l  #1,%d4
        bpl.w   4b
        move.l  dl_loaded,%d0
        btst    %d6,%d0
        sne     %d4                             | d4.b: loaded
        moveq   #0,%d5                          | d5: blocked (not loaded: no home is free; loaded: a reverb reaches its code)
        moveq   #0,%d7                          | d7: loaded and blocked, and another home is free (it can move)
        tst.b   %d4
        bne.w   dl_ld
        bsr.w   dl_pick                         | d1 = a free home, or -1
        tst.l   %d1
        bpl.w   dl_tc
        moveq   #1,%d5
        bra.w   dl_tc
dl_ld:  bsr.w   dl_cur                          | a1 = the current home
        move.l  %a1@(0),%d1
        lea     LIVE+8,%a0
        move.b  %a0@(0,%d1:l),%d2
        bsr.w   dl_rvm
        and.l   %a1@(12),%d2                    | does a reverb on that slot reach the code?
        beq.w   dl_tc
        moveq   #1,%d5
        bsr.w   dl_pick                         | another home (this one is busy)
        tst.l   %d1
        bmi.w   dl_tc
        moveq   #1,%d7
        | Toasts, once per collision, shown at the next page key (dl_key):
        |   the effect is used, not loaded, and no home is free: EVICT Tn FX2 1ST (Tn: its first home's track)
        |   the effect is loaded, a reverb reaches it and it has nowhere to move (the reverb runs dry): EVICT <effect> 1ST
dl_tc:  move.l  dl_ta,%d2
        tst.b   %d4
        bne.w   8f
        tst.l   %d3
        beq.w   8f
        tst.l   %d5
        beq.w   8f
        btst    %d6,%d2
        bne.w   9f
        bset    %d6,%d2
        move.l  %d2,dl_ta
        move.l  %a2@(20),%d1
        move.l  %d1,dl_pend
        bra.w   9f
8:      bclr    %d6,%d2
        move.l  %d2,dl_ta
9:      move.l  dl_tb,%d2
        tst.b   %d4
        beq.w   8f
        tst.l   %d5
        beq.w   8f
        tst.l   %d7
        bne.w   8f                              | it can move: no toast
        btst    %d6,%d2
        bne.w   0f
        bset    %d6,%d2
        move.l  %d2,dl_tb
        move.l  %a2@(24),%d1
        move.l  %d1,dl_pend
        bra.w   0f
8:      bclr    %d6,%d2
        move.l  %d2,dl_tb
0:      tst.b   %d4
        bne.w   6f
        lea     dl_seen,%a1                     | not loaded: for how many idle calls it has been used with a home free
        move.l  %d6,%d1
        lsl.l   #2,%d1
        adda.l  %d1,%a1
        tst.l   %d3
        beq.w   dg_used                         | not used: the count starts over
        tst.l   %d5
        bne.w   dg_used                         | no home is free
        move.l  %a1@,%d1
        addq.l  #1,%d1
        move.l  %d1,%a1@
        cmp.l   #DEBOUNCE,%d1
        bcs.w   7f                              | not yet: a project load writes the ids over a stretch of frames
        clr.l   %a1@
        bsr.w   dl_pick                         | the home to load into
        tst.l   %d1
        bmi.w   7f
        bsr.w   dl_hrec                         | a1 = its record
        move.l  %d1,%d2
        lea     dl_hm,%a0
        move.l  %d6,%d1
        lsl.l   #2,%d1
        move.l  %d2,%a0@(0,%d1:l)               | the effect's home
        move.l  %a1@(16),%d1
        move.l  dl_busy,%d3
        bset    %d1,%d3
        move.l  %d3,dl_busy                     | its block holds code
        move.l  %a1@(4),%d1                     | the staged block
        move.l  %a1@(8),%d2
        bset    %d6,%d0
        move.l  %d1,dl_rsrc
        move.l  %d2,dl_rlen
        move.l  %d6,dl_rk
        move.l  #REPEAT,%d3
        move.l  %d3,dl_rwait
        moveq   #2,%d3
        move.l  %d3,dl_rn                       | two repeats follow the first send
        lea     dl_dg,%a1
        addq.l  #1,%a1@(20)                     | [5]: loads armed
        bra.w   arm
6:      lea     dl_gone,%a1                     | loaded: unused for GRACE idle calls in a row withdraws it
        move.l  %d6,%d1
        lsl.l   #2,%d1
        adda.l  %d1,%a1
        tst.l   %d3
        bne.w   dl_lu
        tst.l   %d5                             | unused: a reverb that reaches its code takes it at once
        beq.w   dg_wait
dg_now: move.l  #GRACE,%a1@
dg_wait:
        move.l  %a1@,%d1
        addq.l  #1,%d1
        move.l  %d1,%a1@
        cmp.l   #GRACE,%d1
        bcs.w   7f                              | still within it
        clr.l   %a1@
        bra.w   dl_wd
dl_lu:  tst.l   %d7                             | used: a reverb reaches its code and another home is free: move it
        beq.w   dg_used
        clr.l   %a1@
        bra.w   dl_wd                           | a move is a withdrawal; the next pass loads the effect elsewhere
dg_used:
        clr.l   %a1@                            | used again: the grace starts over
7:      lea     %a2@(32),%a2
        addq.l  #1,%d6
        bra.w   3b
dl_wd:  bsr.w   dl_cur                          | withdraw effect d6: free its block, clear its bit, send the message
        move.l  %a1@(16),%d1
        move.l  dl_busy,%d2
        bclr    %d1,%d2
        move.l  %d2,dl_busy
        move.l  %a2@(16),%d1                    | the withdraw message
        moveq   #5,%d2
        bclr    %d6,%d0
        lea     dl_dg,%a1
        addq.l  #1,%a1@(24)                     | [6]: withdrawals armed
        bra.w   arm

| ---- homes: a block of the window an effect can be loaded into ----------------------------------------------
| d6 = the effect's index, a2 = its record (dl_tab); each home is 24 bytes: track, staged block, halfwords, the
| mask of reverbs that reach its code, the block's index.
| a2 -> home d1 (0..3): a1 = its record; d1 kept.
dl_hrec:
        move.l  %a2@(8),%a1
        move.l  %d1,%sp@-
1:      tst.l   %d1
        beq.w   2f
        lea     %a1@(24),%a1
        subq.l  #1,%d1
        bra.w   1b
2:      move.l  %sp@+,%d1
        rts

| The effect's current home: d1 = its index, a1 = its record.
dl_cur: lea     dl_hm,%a1
        move.l  %d6,%d1
        lsl.l   #2,%d1
        move.l  %a1@(0,%d1:l),%d1
        bra.w   dl_hrec

| A home the effect can be loaded into now: d1 = its index, or -1. A home is free when no demand effect holds its
| block and the FX2 slot of its block's track is not a stock reverb that reaches the code. A loaded effect's own
| block is busy, so for it this finds another home.
dl_pick:
        lea     %sp@(-24),%sp
        movem.l %d2-%d5/%a0-%a1,%sp@
        moveq   #0,%d4
1:      cmp.l   %a2@(12),%d4
        bcc.w   9f
        move.l  %a2@(8),%a0
        move.l  %d4,%d5
        lsl.l   #3,%d5                          | home index * 24
        move.l  %d5,%d3
        add.l   %d5,%d3
        add.l   %d3,%d5
        adda.l  %d5,%a0
        move.l  %a0@(16),%d5
        move.l  dl_busy,%d3
        btst    %d5,%d3
        bne.w   2f                              | another effect's code is there
        move.l  %a0@(0),%d3
        lea     LIVE+8,%a1
        move.b  %a1@(0,%d3:l),%d2
        bsr.w   dl_rvm
        and.l   %a0@(12),%d2
        bne.w   2f                              | a reverb reaches the code
        move.l  %d4,%d1
        bra.w   8f
2:      addq.l  #1,%d4
        bra.w   1b
9:      moveq   #-1,%d1
8:      movem.l %sp@,%d2-%d5/%a0-%a1
        lea     %sp@(24),%sp
        rts

| d7 = a track: d2 = 1 if it is the track of one of the effect's homes.
dl_ishome:
        move.l  %d3,%sp@-
        move.l  %a0,%sp@-
        moveq   #0,%d2
        move.l  %a2@(8),%a0
        move.l  %a2@(12),%d3
1:      tst.l   %d3
        beq.w   9f
        cmp.l   %a0@(0),%d7
        bne.w   2f
        moveq   #1,%d2
        bra.w   9f
2:      lea     %a0@(24),%a0
        subq.l  #1,%d3
        bra.w   1b
9:      move.l  %sp@+,%a0
        move.l  %sp@+,%d3
        rts

arm:    move.l  %d0,dl_loaded
        move.l  %d1,dl_src
        move.l  %d2,dl_left
        moveq   #1,%d0
        move.l  %d0,dl_core
        move.l  #STAGE1,%d0
        move.l  %d0,dl_dest
        moveq   #1,%d0
        move.l  %d0,dl_state
        rts

| d2 = an FX2 id -> d2 = 1, 2 or 4 for PLATE, SPRING or DARK REV, 0 for any other id (bit i = DLPUMP's REVERBS[i])
dl_rvm: cmp.b   #DL_PLATE,%d2
        bne.w   1f
        moveq   #1,%d2
        rts
1:      cmp.b   #DL_SPRING,%d2
        bne.w   2f
        moveq   #2,%d2
        rts
2:      cmp.b   #DL_DARK,%d2
        bne.w   3f
        moveq   #4,%d2
        rts
3:      moveq   #0,%d2
        rts

| ---- the choosers: refuse a collision, and say so ----------------------------
| Detours at the FX1 and FX2 select handlers' "same effect?" test (0x4005272a, 0x400524ba): d1 is
| the id chosen, d0 the track's current id, d7 the track. The chosen id is refused, and a toast
| says why, when it would collide with whoever holds the block:
|   a demand effect that is not loaded, whose block is under a stock reverb;
|   a stock reverb on the FX2 slot of a loaded effect's block.
| A refusal leaves the handler as if nothing changed.
        .globl  dl_sel_fx1, dl_sel_fx2
dl_sel_fx1:
        cmp.l   %d0,%d1                         | displaced: cmpl %d0,%d1 / beqw (unchanged)
        beq.w   1f
        moveq   #0,%d0
        bsr.w   dl_veto
        tst.l   %d0
        bne.w   2f
        jmp     0x40052730                      | moveb %d1,%a0@: the Part takes the id
2:      bsr.w   dl_toast
1:      jmp     0x4005293a                      | the handler's exit

dl_sel_fx2:
        cmp.l   %d0,%d1
        beq.w   1f
        moveq   #1,%d0
        bsr.w   dl_veto
        tst.l   %d0
        bne.w   2f
        jmp     0x400524c0
2:      bsr.w   dl_toast
1:      jmp     0x400526da

| d0 = the message, shown by the firmware's popup (d0/d1/a0/a1 clobbered as by any stock call).
dl_toast:
        pea     (TOAST_TIME).w
        move.l  %d0,%sp@-
        jsr     TOAST
        addq.l  #8,%sp
        rts

| d0 = 1 for the FX2 chooser, 0 for FX1's; d1, d7 as above. Returns d0 = 0 to go on, or the
| message to refuse with. Every register but d0 is kept.
dl_veto:
        lea     %sp@(-40),%sp
        movem.l %d1-%d7/%a0-%a2,%sp@
        move.l  %d0,%d5
        moveq   #0,%d0
        lea     dl_tab,%a2
        moveq   #0,%d6
2:      cmp.l   #DL_N,%d6
        bcc.w   9f
        move.l  %sp@,%d1                        | the id chosen (the calls below clobber d1)
        move.l  dl_loaded,%d2
        btst    %d6,%d2
        sne     %d4                             | d4.b: loaded
        cmp.l   %a2@,%d1
        bne.w   5f
        tst.b   %d4                             | the effect chosen
        bne.w   9f                              | loaded: goes on
        tst.l   %d5
        beq.w   3f
        bsr.w   dl_ishome
        tst.l   %d2
        bne.w   9f                              | the FX2 chooser on the track of one of its homes replaces what is there
3:      bsr.w   dl_pick                         | is a home free?
        tst.l   %d1
        bpl.w   9f
        move.l  %a2@(20),%d0                    | EVICT Tn FX2 1ST
        bra.w   9f
5:      tst.b   %d4                             | a reverb chosen on the FX2 slot of a loaded effect's current home
        beq.w   7f
        tst.l   %d5
        beq.w   7f
        bsr.w   dl_cur
        cmp.l   %a1@(0),%d7
        bne.w   7f
        move.l  %a2@,%d2                        | ... that a track uses
        lea     LIVE,%a0
        moveq   #15,%d3
dv_scan:
        cmp.b   %a0@+,%d2
        beq.w   dv_used
        subq.l  #1,%d3
        bpl.w   dv_scan
        bra.w   7f                              | unused: it is about to be withdrawn, not a holder
dv_used:
        move.l  %sp@,%d2                        | the reverb chosen: does it reach this home's code?
        bsr.w   dl_rvm
        and.l   %a1@(12),%d2
        beq.w   7f
        bsr.w   dl_pick                         | it does: allowed when the effect has another home to move to
        tst.l   %d1
        bpl.w   7f
        move.l  %a2@(24),%d0                    | EVICT <effect> 1ST
        bra.w   9f
7:      lea     %a2@(32),%a2
        addq.l  #1,%d6
        bra.w   2b
9:      movem.l %sp@,%d1-%d7/%a0-%a2
        lea     %sp@(40),%sp
        rts

| ---- a toast owed by the idle loop, shown at the next page key ---------------------------
| FUN_4005578c(code, edge), the UI task's page-key handler: on a press, a pending message is shown
| (the frame interrupt cannot call the popup). Displaced: its first three instructions.
        .globl  dl_key
dl_key:
        move.l  dl_pend,%d0
        beq.w   1f
        moveq   #1,%d1
        cmp.l   %sp@(8),%d1                     | the press, not the release
        bne.w   1f
        clr.l   dl_pend
        pea     (TOAST_TIME).w
        move.l  %d0,%sp@-
        jsr     TOAST
        addq.l  #8,%sp
1:      move.l  %d3,%sp@-
        move.l  %d2,%sp@-
        move.l  %sp@(12),%a1
        jmp     0x40055794

| d4 core, d1 X word, d2 words, a0 source halfwords
dl_xfer:
        move.b  %d4,CSEL
        moveq   #0x7f,%d0
        addq.l  #2,%d0
        move.w  %d0,HOST
        or.l    #0x4000,%d1
        move.w  %d1,HOST+0x1c
        subq.l  #1,%d2
        move.w  %d2,HOST+0x1c
        addq.l  #1,%d2
        move.l  #0x88,%d0
        move.w  %d0,HOST+4
        move.l  %d2,%d3
3:      move.w  HOST+8,%d0
        and.l   #6,%d0
        beq.w   3b
        moveq   #0,%d1
        move.w  (%a0)+,%d1
        moveq   #0,%d0
        move.w  %d0,HOST+0x14
        move.l  %d1,%d0
        asr.l   #8,%d0
        move.w  %d0,HOST+0x18
        move.w  %d1,HOST+0x1c
        subq.l  #1,%d3
        bne.w   3b
        rts

        .data
        .globl  dl_state, dl_core, dl_dest, dl_src, dl_left, dl_loaded
dl_state: .long 0
dl_core:  .long 0
dl_dest:  .long 0
dl_src:   .long 0
dl_left:  .long 0
dl_loaded: .long 0                      | bit k: effect k is loaded
dl_seen:  .long 0, 0, 0, 0              | per effect: idle calls it has been used, not loaded, on a free block
dl_hm:    .long 0, 0, 0, 0                  | per effect: the index of the home it is loaded in
dl_busy:  .long 0                           | bit b: the demand code in block b (0..3)
dl_gone:  .long 0, 0, 0, 0              | per effect: idle calls it has been loaded and unused
dl_rwait: .long 0                       | idle calls until the load of effect dl_rk is sent again (0: none)
dl_rk:    .long 0
dl_rn:    .long 0                       | repeats still to send for it
dl_rsrc:  .long 0
dl_rlen:  .long 0
dl_ta:    .long 0                       | bit k: the NEEDS toast for effect k has been queued for this collision
dl_tb:    .long 0                       | the same for HOLDS
dl_pend:  .long 0                       | the message waiting for a page key (0: none)
        .globl  dl_dg, DL_DIAG
dl_dg:                                          | DL_DIAG: read over USB (0xc0/0x57, block 3), 16 longs
DL_DIAG:
        .long   0, 0, 0, 0, 0, 0, 0, 0          | calls; ping 0, 1, other; idle passes; loads, withdrawals, chunks, bells
        .long   0, 0, 0, 0, 0, 0, 0, 0          | repeats; loaded bits; (spare); (spare); the 16 live FX ids as 4 longs
dl_bell:  .word RING
