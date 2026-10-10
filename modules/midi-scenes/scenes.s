| MIDI SCENES -- scene locks for the eight MIDI tracks, phase 1.
|
| Original author of the behaviour: bkkbrls-del (midisc, MIDISC2.1). This
| file is a fresh GNU-as write-up of what his image does at the stock sites
| below, measured against it under the port (tools/verify/verify_scenes.py);
| none of his code or data is copied or linked.
|
| Stock keeps scene locks for the audio tracks only (Part +0x662: 16 scenes x
| 8 tracks x 32 B). The tests of 0x80000012 (MIDI track mode) in the scene
| hold, the encoder press and the lock-offset paths send MIDI mode away from
| them. This unit adds a second table, MSC, with the same shape:
|
|     MSC[scene << 8 | track << 5 | flat],  0xff = no lock
|
| flat = MIDI page * 6 + knob (NOTE 0, LFO 1, ARP 2, CTRL1 3, CTRL2 4;
| flats 0..29). Phase 1 keeps MSC, the scene clipboard and the mix state in
| this unit's DRAM and writes nothing to a Part, a bank file or CS1. MSC is
| one table: the Part window it belongs to is the displayed Part
| (0x100b14cf) and a Part change does not swap it (phase 2).
|
| Sites (all stock addresses; the manifest holds the bytes they replace):
|
|   B1  0x400534ce 0x40052ece  scene A / B held, encoder turned: the value
|                              goes to MSC, the mix runs at the current XF
|   B2  0x4004e348             knob readout: the held scene's lock
|   B3  0x40053a9e 0x40054392  scene held, encoder pressed: the lock cleared
|   B4  0x40034754 0x4003493e  lock LEDs scan MSC (the empty-scan branches
|       0x40034764 0x40034950  are removed, the scene-block base is MSC)
|   B5  0x40031f44             scene pad lit when MSC holds a lock for it
|   B6  0x400343bc 0x400343e8  per-track and per-page lock offsets
|       0x4003445e 0x4003448e
|   B7  0x4003f3a2 0x40061e78  XF: the locked parameters morph between the
|       0x40062c32             two scenes and go out as CCs
|   B8  0x40052a10 0x40052ae0  scene pad press / assign: mix at the XF
|   B11 (the mix)              track t reads and writes only track t's rows
|   B29 0x40062f24 0x40062fbe  CLEAR / COPY / PASTE SCENE rows
|       0x40062e3c
|   B30 0x400434ca             encoder press, MIDI mode: overlay refresh
|
| B9 (scene pad release) is stock's own sequence at 0x40054cb6..0x40054cd2
| and needs no site. Not here: B10, B12..B28, B31..B33.
|
| Registers at the sites follow what the stock functions leave free: the
| hold, press and pad functions save d2-d7/a2.. in their prologues, so the
| hooks may use d0-d7/a0-a1 once their own arguments are read.

        .set    PARTSZ,         0x18b2          | one Part in the bank window
        .set    SCENE_ASSIGN,   0x8ed90         | bank: scene A id, scene B id (0xff = none)
        .set    PART_LIVE,      0x8f162         | bank: MIDI track params, 32 B per track
        .set    MIDI_MODE,      0x80000012      | long: nonzero in MIDI track mode
        .set    SCENE_HELD,     0x460d169c      | long: 1 scene A held, 2 scene B held
        .set    PAGE_MODE,      0x460d1684      | long: 0 NOTE .. 4 CTRL2
        .set    XF_RAM,         0x460d16c8      | long: crossfader position
        .set    PART_DISP,      0x100b14cf      | byte: displayed Part
        .set    TRACK_DISP,     0x100b14cc      | byte: displayed track
        .set    BANK_PTR,       0x46c82456      | long: current bank's RAM base
        .set    REC,            0x46c76dc0      | MIDI track records, 0x44 B each
        .set    REC_STRIDE,     0x44
        .set    LOCK_MASK,      0x8000664e      | u32 per track: bit = param locked by the playing step
        .set    CC_TX,          0x4009eec8      | (track, flat, value, quiet): MIDI-track emitter
        .set    UI_OVERLAY,     0x4004d948      | (-1): redraws the knob overlay
        .set    PRESS_UI,       0x400418e0      | the stock encoder-press refresh
        .set    CLIPBOARD_TYPE, 0x460d0ffa      | long: 0x10 = a scene is on the clipboard
        .set    NOLOCK,         0xff
        .set    ST_VALID,       0               | scn_state long: a mix has run
        .set    ST_XF,          4               | scn_state long: the XF position it mixed

        .text
        .globl  scn_hold_a, scn_hold_b, scn_dial, scn_enc_a, scn_enc_b
        .globl  scn_taddi, scn_paddi, scn_pad, scn_press, scn_done
        .globl  scn_morph, scn_xf1, scn_xf2, scn_clear, scn_copy, scn_paste
        .globl  scn_msc, scn_clip, scn_state

| ===================================================== B1: hold + turn ====

| 0x400534ce, 0x40052ece: `tstl 0x80000012 / bne bail` in the scene-hold
| function (d3 = knob 0..5, d6 = signed delta). Audio mode continues at
| the stock instruction after the test.
scn_hold_a:
        tstl    MIDI_MODE
        beq.s   1f
        moveq   #0,%d0                  | scene A
        bsr.w   hold_store
        tstl    %d0
        beq.s   2f
        jmp     0x40053a36              | stock epilogue: redraw, return
2:      jmp     0x40053a5c              | no scene assigned: return
1:      jmp     0x400534d8

scn_hold_b:
        tstl    MIDI_MODE
        beq.s   1f
        moveq   #1,%d0                  | scene B
        bsr.w   hold_store
        tstl    %d0
        beq.s   2f
        jmp     0x40053464
2:      jmp     0x4005348c
1:      jmp     0x40052ed8

| hold_store: d0 = 0 / 1 (scene A / B), d3 = knob, d6 = delta. The held
| scene's lock for the displayed track and the knob becomes (its value, or
| the Part's unlocked value when it had none) + delta, clamped; the mix runs.
| Returns d0 = 1, or 0 when the Part has no scene assigned to that key.
| Clobbers d1-d2, d4-d5, a0-a1.
hold_store:
        bsr.w   row_offset              | d1 = MSC offset of the row, -1 = none
        tstl    %d1
        bmi.s   8f
        bsr.w   flat_of_knob            | d5 = flat; keeps d1
        addl    %d5,%d1
        lea     scn_msc:l,%a1
        addal   %d1,%a1                 | a1 -> the lock
        mvzb    %a1@,%d1
        cmpil   #NOLOCK,%d1
        bne.s   2f
        bsr.w   part_value              | d1 = the Part's unlocked value
2:      addl    %d6,%d1
        bsr.w   clamp                   | d1 = 0..127, the ARP limits
        moveb   %d1,%a1@
        bsr.w   mix
        moveq   #1,%d0
        rts
8:      moveq   #0,%d0
        rts

| flat_of_knob: d5 = (PAGE_MODE * 6 + d3) & 31. Clobbers d0.
flat_of_knob:
        movel   PAGE_MODE,%d0
        movel   %d0,%d5
        lsll    #3,%d5
        addl    %d0,%d0
        subl    %d0,%d5
        addl    %d3,%d5
        andil   #31,%d5
        rts

| part_window: a0 = the displayed Part's window in the current bank.
| Clobbers d0-d1.
part_window:
        mvzb    PART_DISP,%d0
        movel   #PARTSZ,%d1
        mulsl   %d1,%d0
        moveal  BANK_PTR,%a0
        addal   %d0,%a0
        rts

| row_offset: d0 = 0 / 1 (scene A / B) -> d1 = (scene << 8) + (displayed
| track << 5), the offset of that scene's row for the displayed track in
| MSC; d1 = -1 when the Part has no scene assigned to that key.
| Clobbers d0, a0.
row_offset:
        movel   %d0,%sp@-
        bsr.w   part_window             | clobbers d0-d1
        movel   %sp@+,%d1
        addal   #SCENE_ASSIGN,%a0
        mvzb    %a0@(0,%d1:l),%d0
        cmpil   #NOLOCK,%d0
        bne.s   1f
        moveq   #-1,%d1
        rts
1:      andil   #15,%d0
        lsll    #8,%d0
        mvzb    TRACK_DISP,%d1
        andil   #7,%d1
        lsll    #5,%d1
        addl    %d0,%d1
        rts

| part_value: d1 = the displayed Part's unlocked value for the displayed
| track and flat d5 (Part +0x3e2, 32 B per MIDI track). Clobbers d0, a0.
part_value:
        bsr.w   part_window
        addal   #PART_LIVE,%a0
        mvzb    TRACK_DISP,%d0
        andil   #7,%d0
        lsll    #5,%d0
        addl    %d5,%d0
        mvzb    %a0@(0,%d0:l),%d1
        rts

| clamp: d1 (signed) -> 0..127; on the ARP page (2) the knobs LEG, MODE, SPD,
| RNGE (flats 13..16) stop at 1, 6, 95, 7. d5 = flat. Clobbers d0, d2.
clamp:
        tstl    %d1
        bpl.s   1f
        moveq   #0,%d1
        rts
1:      movel   PAGE_MODE,%d0
        cmpil   #2,%d0
        bne.s   5f
        movel   %d5,%d0
        subil   #12,%d0                 | knob on the ARP page
        moveq   #1,%d2
        cmpil   #1,%d0
        beq.s   4f
        moveq   #6,%d2
        cmpil   #2,%d0
        beq.s   4f
        moveq   #95,%d2
        cmpil   #3,%d0
        beq.s   4f
        moveq   #7,%d2
        cmpil   #4,%d0
        bne.s   5f
4:      cmpl    %d2,%d1
        bls.s   9f
        movel   %d2,%d1
9:      rts
5:      cmpil   #128,%d1
        bcs.s   9b
        moveq   #127,%d1
        rts

| ======================================================= B2: the readout ====

| 0x4004e348, in the knob readout (d5 = flags, a4 = knob 0..5): with a scene
| held and a lock stored for the knob, the readout shows that lock (d5 bit 0
| set, d0 = value); otherwise stock's own value computation.
scn_dial:
        movel   SCENE_HELD,%d0
        beq.s   live
        cmpil   #2,%d0
        bhi.s   live
        movel   %d1,%sp@-
        movel   %d2,%sp@-
        movel   %d3,%sp@-
        movel   %a0,%sp@-
        movel   %a1,%sp@-
        subql   #1,%d0                  | 0 = A, 1 = B
        bsr.w   row_offset
        tstl    %d1
        bmi.s   miss
        movel   PAGE_MODE,%d2
        movel   %d2,%d0
        lsll    #3,%d0
        addl    %d2,%d2
        subl    %d2,%d0                 | page * 6
        addl    %a4,%d0                 | + knob
        addl    %d0,%d1
        lea     scn_msc:l,%a0
        mvzb    %a0@(0,%d1:l),%d0
        cmpil   #NOLOCK,%d0
        beq.s   miss
        cmpil   #128,%d0
        bcc.s   miss
        moveq   #1,%d1
        orl     %d1,%d5
        moveal  %sp@+,%a1
        moveal  %sp@+,%a0
        movel   %sp@+,%d3
        movel   %sp@+,%d2
        movel   %sp@+,%d1
        jmp     0x4004e382
miss:   moveal  %sp@+,%a1
        moveal  %sp@+,%a0
        movel   %sp@+,%d3
        movel   %sp@+,%d2
        movel   %sp@+,%d1
live:   mvzb    TRACK_DISP,%d0          | the displaced stock sequence
        movel   PAGE_MODE,%d2
        mvzb    PART_DISP,%d1
        lsll    #5,%d0
        movel   #PARTSZ,%d3
        mulsl   %d3,%d1
        addl    %d1,%d0
        movel   %d2,%d1
        lsll    #3,%d1
        addl    %d2,%d2
        subl    %d2,%d1
        addl    %d1,%d0
        addl    BANK_PTR,%d0
        addl    %a4,%d0
        moveal  %d0,%a0
        addal   #PART_LIVE,%a0
        mvzb    %a0@,%d0
        jmp     0x4004e382

| ===================================================== B3: encoder press ====

| 0x40053a9e, 0x40054392: `tstl 0x80000012 / bne bail` in the encoder-press
| functions (d4 = event code, 56..61 = encoder 1..6). In MIDI mode they
| return to the stock bail address; with a scene held the press first
| clears that knob's lock.
scn_enc_a:
        tstl    MIDI_MODE
        beq.s   1f
        movel   SCENE_HELD,%d0
        beq.s   2f
        bsr.w   unlock
2:      jmp     0x40054350
1:      jmp     0x40053aa8

scn_enc_b:
        tstl    MIDI_MODE
        beq.s   1f
        movel   SCENE_HELD,%d0
        beq.s   2f
        bsr.w   unlock
2:      jmp     0x40054c52
1:      jmp     0x4005439c

| unlock: d4 = event code. The held scene's lock for the displayed track
| and encoder d4 - 56 becomes "none", the mix runs, the overlay redraws.
| Preserves every register.
unlock:
        lea     %sp@(-28),%sp
        movem.l %d0-%d3/%d5/%a0-%a1,%sp@
        movel   %d4,%d3
        subil   #56,%d3
        cmpil   #5,%d3
        bhi.s   9f
        bsr.w   flat_of_knob            | d5
        movel   SCENE_HELD,%d0
        subql   #1,%d0                  | 0 = A, 1 = B
        bsr.w   row_offset
        tstl    %d1
        bmi.s   9f
        addl    %d5,%d1
        lea     scn_msc:l,%a0
        moveq   #-1,%d0                  | 0xff in the byte
        moveb   %d0,%a0@(0,%d1:l)
        bsr.w   mix
        pea     0xffffffff
        jsr     UI_OVERLAY
        addql   #4,%sp
9:      movem.l %sp@,%d0-%d3/%d5/%a0-%a1
        lea     %sp@(28),%sp
        rts

| ============================================== B4, B6: lock LEDs, offsets ====

| 0x400343e8, 0x40034764, 0x40034950 (d0) and 0x4003448e (d1): `addil
| #0x8f3e2,Dn` turns a window-relative scene-block offset into an address.
| In MIDI mode the base becomes MSC. d0 / d1 are the address the stock
| code built from the bank, the displayed Part and the scene / track
| offset; those two terms come off and MSC goes on.
scn_taddi:
        tstl    MIDI_MODE
        beq.s   1f
        movel   %d1,%sp@-
        movel   %d2,%sp@-
        mvzb    PART_DISP,%d1
        movel   #PARTSZ,%d2
        mulsl   %d1,%d2
        subl    %d2,%d0
        movel   BANK_PTR,%d1
        subl    %d1,%d0
        addil   #scn_msc,%d0
        movel   %sp@+,%d2
        movel   %sp@+,%d1
        rts
1:      addil   #0x8f3e2,%d0
        rts

scn_paddi:
        tstl    MIDI_MODE
        beq.s   1f
        movel   %d0,%sp@-
        movel   %d2,%sp@-
        mvzb    PART_DISP,%d0
        movel   #PARTSZ,%d2
        mulsl   %d0,%d2
        subl    %d2,%d1
        movel   BANK_PTR,%d0
        subl    %d0,%d1
        addil   #scn_msc,%d1
        movel   %sp@+,%d2
        movel   %sp@+,%d0
        rts
1:      addil   #0x8f3e2,%d1
        rts

| ============================================================ B5: pad ====

| 0x40031f44: the pad-has-locks function's prologue (`lea sp@(-28),sp /
| moveml d2-d7/a2,sp@`), argument = scene. Any lock in MSC[scene] lights the
| pad in every mode; none continues with stock's audio check.
scn_pad:
        lea     %sp@(-28),%sp
        movem.l %d2-%d7/%a2,%sp@
        movel   %sp@(32),%d0
        andil   #15,%d0
        lsll    #8,%d0
        lea     scn_msc:l,%a0
        addal   %d0,%a0
        movel   #256,%d1
1:      mvzb    %a0@,%d0
        cmpil   #NOLOCK,%d0
        bne.s   2f
        addql   #1,%a0
        subql   #1,%d1
        bne.s   1b
        movel   %sp@(32),%d0
        jmp     0x40031f4c
2:      moveq   #1,%d0
        movem.l %sp@,%d2-%d7/%a2
        lea     %sp@(28),%sp
        rts

| ================================================ B8, B30: scene keys ====

| 0x400434ca: `jsr 0x400418e0 / movel sp@+,d2` after a scene key sets
| SCENE_HELD. In MIDI mode the knob overlay is redrawn.
scn_press:
        jsr     PRESS_UI
        tstl    MIDI_MODE
        beq.s   1f
        pea     0xffffffff
        jsr     UI_OVERLAY
        addql   #4,%sp
1:      movel   %sp@+,%d2
        jmp     0x4007e8d8

| 0x40052a10, 0x40052ae0: `jmp 0x4007e8d8` at the end of the scene recall
| paths: the mix at the current XF, in any mode.
scn_done:
        bsr.w   mix
        jmp     0x4007e8d8

| ================================================================ B7: XF ====

| 0x40061e78: after the panel handler's CC 48 out (`jsr 0x40033e3c`).
scn_xf1:
        bsr.w   mix
        mvs.b   0x8000004a,%d0
        jmp     0x40061e7e

| 0x40062c32: after the second XF publish.
scn_xf2:
        bsr.w   mix
        mvz.b   0x80000003,%d0
        jmp     0x40062c38

| 0x4003f3a2: `jmp 0x4003577c`, the tail of the audio morph. Once a mix has
| run, an XF position it has not mixed yet is mixed. d0 is live here.
scn_morph:
        movel   %d0,%sp@-
        tstl    scn_state+ST_VALID
        beq.s   1f
        movel   XF_RAM,%d0
        cmpl    scn_state+ST_XF,%d0
        beq.s   1f
        bsr.w   mix
1:      movel   %sp@+,%d0
        jmp     0x4003577c

| mix: for each MIDI track t and flat f the value at the XF position x is
|
|     lock A, lock B   -> (A, B), the unlocked side (no lock) reading the
|                         Part's value
|     one lock         -> that lock on its end; the Part's value on the other
|     none             -> the Part's value (record written, nothing sent)
|
| v = A at weight 0, B at weight 127, A + ((B - A) * w >> 7) between, with
| w = 127 - (x & 127). Scenes A and B are the displayed Part's assignments.
| v & 127 goes to the track record REC + 0x44 t + f; when it changed, the
| stock emitter sends it (CC_TX caches per CC number). Flats 18..29 also
| lose bit f of the track's lock-mask long. Preserves every register.
mix:
        lea     %sp@(-52),%sp
        movem.l %d0-%d7/%a0-%a4,%sp@
        moveal  BANK_PTR,%a0
        cmpal   #0,%a0
        beq.w   mix_out
        bsr.w   part_window             | a0 = the Part's window
        moveal  %a0,%a4
        addal   #PART_LIVE,%a4          | a4 -> its unlocked values, 32 B per track
        addal   #SCENE_ASSIGN,%a0
        subal   %a2,%a2                 | a2 = scene A's rows, 0 = no scene
        mvzb    %a0@,%d0
        cmpil   #NOLOCK,%d0
        beq.s   1f
        andil   #15,%d0
        lsll    #8,%d0
        lea     scn_msc:l,%a2
        addal   %d0,%a2
1:      subal   %a3,%a3                 | a3 = scene B's rows
        mvzb    %a0@(1),%d0
        cmpil   #NOLOCK,%d0
        beq.s   2f
        andil   #15,%d0
        lsll    #8,%d0
        lea     scn_msc:l,%a3
        addal   %d0,%a3
2:      movel   XF_RAM,%d5
        andil   #127,%d5
        moveq   #127,%d0
        subl    %d5,%d0
        movel   %d0,%d5                 | d5 = w
        moveq   #0,%d6                  | d6 = track
mix_track:
        moveq   #0,%d7                  | d7 = flat
mix_flat:
        movel   %d6,%d0
        lsll    #5,%d0
        addl    %d7,%d0                 | d0 = t * 32 + f
        movel   #NOLOCK,%d3             | d3 = lock A
        movel   %a2,%d1
        beq.s   3f
        mvzb    %a2@(0,%d0:l),%d3
3:      movel   #NOLOCK,%d4             | d4 = lock B
        movel   %a3,%d1
        beq.s   4f
        mvzb    %a3@(0,%d0:l),%d4
4:      cmpil   #NOLOCK,%d3
        bne.s   5f
        cmpil   #NOLOCK,%d4
        beq.s   mix_free
5:      cmpil   #NOLOCK,%d3
        bne.s   6f
        mvzb    %a4@(0,%d0:l),%d3       | A unlocked: the Part's value
6:      cmpil   #NOLOCK,%d4
        bne.s   7f
        mvzb    %a4@(0,%d0:l),%d4
7:      movel   %d3,%d2
        tstl    %d5
        beq.s   9f
        movel   %d4,%d2
        cmpil   #127,%d5
        beq.s   9f
        subl    %d3,%d2
        mulsl   %d5,%d2
        asrl    #7,%d2
        addl    %d3,%d2
9:      andil   #127,%d2
        movel   #REC_STRIDE,%d1
        mulsl   %d6,%d1
        addl    %d7,%d1
        lea     REC,%a0
        addal   %d1,%a0                 | a0 -> the record's byte
        mvzb    %a0@,%d1
        moveb   %d2,%a0@
        cmpl    %d2,%d1
        beq.s   mix_ctl
        clrl    %sp@-                   | CC_TX (track, flat, value, 0)
        movel   %d2,%sp@-
        movel   %d7,%sp@-
        movel   %d6,%sp@-
        jsr     CC_TX
        lea     %sp@(16),%sp
        bra.s   mix_ctl
mix_free:                               | no lock on either side
        mvzb    %a4@(0,%d0:l),%d2
        andil   #127,%d2
        movel   #REC_STRIDE,%d1
        mulsl   %d6,%d1
        addl    %d7,%d1
        lea     REC,%a0
        addal   %d1,%a0
        moveb   %d2,%a0@
mix_ctl:
        cmpil   #18,%d7
        bcs.s   mix_next
        movel   %d6,%d0
        lsll    #2,%d0
        moveal  %d0,%a0
        addal   #LOCK_MASK,%a0
        moveq   #1,%d0
        lsll    %d7,%d0
        notl    %d0
        andl    %d0,%a0@
mix_next:
        addql   #1,%d7
        cmpil   #30,%d7
        bcs.w   mix_flat
        addql   #1,%d6
        cmpil   #8,%d6
        bcs.w   mix_track
        lea     scn_state:l,%a0
        moveq   #1,%d0
        movel   %d0,%a0@(ST_VALID)
        movel   XF_RAM,%d0
        movel   %d0,%a0@(ST_XF)
mix_out:
        movem.l %sp@,%d0-%d7/%a0-%a4
        lea     %sp@(52),%sp
        rts

| ====================================================== B29: scene rows ====

| 0x40062f24: CLEAR SCENE, jsr 0x40038c30(scene). MSC[scene] is wiped, the
| mix runs, stock clears the audio scene.
scn_clear:
        movel   %d0,%sp@-
        movel   %d1,%sp@-
        movel   %a0,%sp@-
        movel   %sp@(16),%d0
        andil   #15,%d0
        lsll    #8,%d0
        lea     scn_msc:l,%a0
        addal   %d0,%a0
        movel   #256,%d1
1:      moveb   #NOLOCK,%a0@
        addql   #1,%a0
        subql   #1,%d1
        bne.s   1b
        moveal  %sp@+,%a0
        movel   %sp@+,%d1
        movel   %sp@+,%d0
        bsr.w   mix
        jmp     0x40038c30

| 0x40062fbe: COPY SCENE, jsr 0x400274cc(part, scene). MSC[scene] goes to
| the clipboard, stock copies the audio scene.
scn_copy:
        movel   %d0,%sp@-
        movel   %d1,%sp@-
        movel   %a0,%sp@-
        movel   %a1,%sp@-
        movel   %sp@(24),%d0
        andil   #15,%d0
        lsll    #8,%d0
        lea     scn_msc:l,%a0
        addal   %d0,%a0
        lea     scn_clip:l,%a1
        movel   #256,%d1
1:      moveb   %a0@+,%d0
        moveb   %d0,%a1@+
        subql   #1,%d1
        bne.s   1b
        moveal  %sp@+,%a1
        moveal  %sp@+,%a0
        movel   %sp@+,%d1
        movel   %sp@+,%d0
        jmp     0x400274cc

| 0x40062e3c: PASTE SCENE, jsr 0x40027578(part, scene). When a scene is on
| the clipboard the clipboard goes to MSC[scene]; stock pastes the audio
| scene.
scn_paste:
        movel   CLIPBOARD_TYPE,%d0
        cmpil   #0x10,%d0
        bne.s   2f
        movel   %d0,%sp@-
        movel   %d1,%sp@-
        movel   %a0,%sp@-
        movel   %a1,%sp@-
        movel   %sp@(24),%d0
        andil   #15,%d0
        lsll    #8,%d0
        lea     scn_msc:l,%a1
        addal   %d0,%a1
        lea     scn_clip:l,%a0
        movel   #256,%d1
1:      moveb   %a0@+,%d0
        moveb   %d0,%a1@+
        subql   #1,%d1
        bne.s   1b
        moveal  %sp@+,%a1
        moveal  %sp@+,%a0
        movel   %sp@+,%d1
        movel   %sp@+,%d0
2:      jmp     0x40027578

| ======================================================================= data

        .section .data
        .align  4
scn_state:
        .long   0
        .long   -1
scn_msc:
        .fill   4096, 1, 0xff           | the lock table
scn_clip:
        .fill   256, 1, 0xff            | the scene clipboard
