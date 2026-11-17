| PATTERN MUTE -- a second mute layer kept per pattern, as on the Digitakt II.
|
| Stock keeps one mute state per project: bits 8-15 of 0x80000008 (audio
| tracks 1-8) and of 0x8000000c (MIDI tracks 1-8), a set bit = muted. This
| unit keeps two layers. GLOBAL is stock's state, saved in project.work.
| PATTERN is kept per pattern (pm_tab). The word stock and every reader see is
| their OR, so MUTE MODE, the LEDs, the MIXER page and MIDI need no change.
|
| Every stock writer of a mute word is followed by a store to a battery SRAM
| mirror (0x100b14d4 audio, 0x100b14d8 MIDI). That store is replaced by
| pm_mirror_a / pm_mirror_m. They read the word stock just wrote, find the bits that
| differ from the effective word published last, give those bits to the
| layer being edited, then republish the OR and store the GLOBAL layer in
| the mirror, so power-off never folds pattern mutes into the global state.
|
| Layer select: a double press of FUNC (two presses within 300 ms). The layer is
| bit 0 of the battery SRAM byte 0x100b14dd, so it survives power-off.
| Stock does nothing on a lone FUNC press. The layer applies to the next
| edit, whichever stock path makes it (FUNC+track, MIXER trig keys, MIDI).
|
| Storage: pm_tab, two bytes per pattern of every bank (bank * 32 +
| pattern * 2: the audio tracks' bits, then the MIDI tracks'), bit k = track
| k+1. It is kept out of Elektron's pattern data. Until 16 Nov 2026 the layer
| was bit 0/1 of byte 40 of each audio track record, which is the low byte of
| the track's one-shot trig mask: a step-1 one-shot muted its track and a
| PATTERN-layer unmute deleted it (sambanks/octabam#1143, 8thmyth, on an MKI
| and under the port). pm_tab is saved in pmute.work beside the bank files
| (a STORE client, as scenes.work), and the current bank's 32 bytes are
| copied to CS1 on every edit, so an unsaved edit survives a power cycle as
| stock's bank does.
|
| pmute.work: 'PMTW', version 1, payload length 512, CRC-32 of the payload;
| then pm_tab. A file that is not that is listed by STORE and never written
| over (pm_nowrite); the banks it would have filled stay empty.
| CS1 (0x100fbdc0..0x100fbdf0, the top 48 bytes of PLOCKS P2's former range):
| 'PMCS' (written last), bank, sum (the bank and the 32 bytes as 8 longs,
| added), reserved; then the bank's 32 bytes.

        .include "remix.inc"

        .text
        .globl  pm_mirror_a
        .globl  pm_mirror_m
        .globl  pm_load_a
        .globl  pm_load_m
        .globl  pm_save_a
        .globl  pm_save_m
        .globl  pm_pat_commit
        .globl  pm_func_press
        .globl  pm_ui_tick
        .globl  pm_gl_a, pm_gl_m, pm_pa, pm_pm, pm_ef_a, pm_ef_m, pm_rdy_a, pm_rdy_m
        .globl  pm_tab, pm_tap
        .globl  pm_st_loadall_pre, pm_st_loadmask_pre, pm_st_newproj, pm_st_bankw_post
        .globl  pm_st_pstore_pre, pm_st_pstore_post, pm_st_preload_post, pm_st_tocs1
        .globl  pm_st_fromcs1, pm_st_answer
        .extern store_path, store_fopen, store_fread, store_fwrite, store_fclose, store_crc32, store_refuse
        .balign 2

        .equ    WORD_A,     0x80000008      | solo 0-7, mute 8-15, cue 16-23
        .equ    WORD_M,     0x8000000c      | MIDI: solo 0-7, mute 8-15
        .equ    MIR_A,      0x100b14d4
        .equ    MIR_M,      0x100b14d8
        .equ    PATNO,      0x80000004
        .equ    BANKPTR,    0x46c82456      | the current bank's RAM blob
        .equ    CUR_BANK,   0x80000002      | byte: the current bank
        .equ    CS1_BASE,   0x100fbdc0      | 16 bytes of header, then the current bank's 32
        .equ    CS1_DATA,   0x100fbdd0
        .equ    CS1_MAGIC,  0x504d4353      | 'PMCS'
        .equ    FMAGIC,     0x504d5457      | 'PMTW'
        .equ    TAB_B,      512             | 16 banks x 16 patterns x 2 bytes
        .equ    F_COPY,     0x40016388      | (dst path, src path, 0) -> <0 error
        .equ    PANEL_ROWS, 0x46100b18      | the panel parser's held keys: row n, bit b = key n*8+b
        .equ    FUNC_ROW,   5               | FUNC is key 0x2d: row 5, bit 5
        .equ    FUNC_BIT,   0x20
        .equ    CLIENT_ID,  11              | STORE's refusal registry (store/manifest.py CLIENT_IDS)
        .equ    EDIT_LONG,  0x9b332         | bank + this: "written by the next bank write"
        .equ    EDIT_FLAG,  0x100f8598
        .equ    MUTE_BITS,  0xff00
        .equ    NOTIFY,     0x4005a2b8      | (text, duration), key-handler context
        .equ    MUTE_VIEW,  0x4007c458      | the mute view's refresh, stock calls it after an edit
        .equ    FUNC_STOCK, 0x4004e954      | FUNC's stock press handler
        .equ    TOAST_TIME, 0x30
        .equ    LAYER_B,    0x100b14dd      | battery SRAM: the layer (bit 0), a state-block byte stock never uses
        .equ    SET_LED,    0x40013784      | set_led(id, ticks): ticks of 120 Hz
        .equ    UI_NEXT,    0x400316a0      | the call the UI loop's hook site displaced (the key-repeat tick)
        .equ    CUR_TRACK,  0x80000000      | current track 0-7 in the current mode
        .equ    LED_TICKS,  6
        .equ    DTCN3,      0xfc07c00c      | DMA timer 3 count, 132 MHz free-run
        .equ    DOUBLE_WINDOW, 39600000     | 300 ms

| One mirror hook per word. In: the stock store just ran, the word holds
| stock's new value N. Out: the word holds the effective value, the mirror
| holds N with the GLOBAL layer in its mute bits; d0-d3 and the CCR are
| preserved except that the caller's own store has been replaced.
        .macro  MIRROR_HOOK name, word, mirror, rdy, gl, pa, ef, force=0
\name:
        lea     -20(%sp),%sp
        movem.l %d0-%d4,(%sp)
        move.w  %sr,%d4
        move.w  #0x2700,%sr
        move.l  \word,%d0                   | N
        tst.b   \rdy
        bne.s   1f
        moveq   #1,%d2
        move.b  %d2,\rdy                    | the first write after power-up is the
        move.l  %d0,%d1                     | restore or the load: it is the GLOBAL layer
        and.l   #MUTE_BITS,%d1
        move.l  %d1,\gl
        clr.l   \pa
        move.l  %d0,\ef
1:      move.l  %d0,%d1
        move.l  \ef,%d2
        eor.l   %d2,%d1
        and.l   #MUTE_BITS,%d1              | the mute bits stock changed
        beq.s   3f
        move.l  %d1,%d2
        not.l   %d2                         | d2 = keep mask
        move.l  %d0,%d3
        and.l   %d1,%d3                     | d3 = new values of the changed bits
        .if     !\force
        mvz.b   LAYER_B,%d1
        btst    #0,%d1
        bne.s   2f
        .endif
        move.l  \gl,%d1
        and.l   %d2,%d1
        or.l    %d3,%d1
        move.l  %d1,\gl
        .if     !\force
        bra.s   3f
2:      move.l  \pa,%d1
        and.l   %d2,%d1
        or.l    %d3,%d1
        move.l  %d1,\pa
        move.w  %d4,%sr
        bsr     pm_store_pat                | the pattern layer changed: write it back
        move.w  #0x2700,%sr
        .endif
3:      move.l  %d0,%d3
        and.l   #~MUTE_BITS,%d3             | solo and cue bits as stock wrote them
        move.l  \gl,%d1
        or.l    \pa,%d1
        and.l   #MUTE_BITS,%d1
        or.l    %d3,%d1                     | effective word
        move.l  %d1,\word
        move.l  %d1,\ef
        move.l  \gl,%d1
        and.l   #MUTE_BITS,%d1
        or.l    %d3,%d1                     | mirror: GLOBAL layer only
        move.l  %d1,\mirror
        move.w  %d4,%sr
        movem.l (%sp),%d0-%d4
        lea     20(%sp),%sp
        rts
        .endm

        MIRROR_HOOK pm_mirror_a, WORD_A, MIR_A, pm_rdy_a, pm_gl_a, pm_pa, pm_ef_a
        MIRROR_HOOK pm_mirror_m, WORD_M, MIR_M, pm_rdy_m, pm_gl_m, pm_pm, pm_ef_m
| The project load's own writes (the settings parser) always set the GLOBAL layer.
        MIRROR_HOOK pm_load_a, WORD_A, MIR_A, pm_rdy_a, pm_gl_a, pm_pa, pm_ef_a, 1
        MIRROR_HOOK pm_load_m, WORD_M, MIR_M, pm_rdy_m, pm_gl_m, pm_pm, pm_ef_m, 1

| The project writer's two loads of the mute byte (mvz.b 0x8000000a,%d0 and
| mvz.b 0x8000000e,%d0) save the GLOBAL layer in project.work.
pm_save_a:
        tst.b   pm_rdy_a
        beq.s   1f
        mvz.b   pm_gl_a+2,%d0
        rts
1:      mvz.b   WORD_A+2,%d0
        rts

pm_save_m:
        tst.b   pm_rdy_m
        beq.s   1f
        mvz.b   pm_gl_m+2,%d0
        rts
1:      mvz.b   WORD_M+2,%d0
        rts

| Replaces `move.b %d0,0x80000003` in the UI-side pattern commit
| (0x40062142). The commit runs after a pattern change and after a project
| load. It loads the pattern layer of the current pattern and republishes
| the effective words.
pm_pat_commit:
        move.b  %d0,0x80000003              | the displaced store
        lea     -36(%sp),%sp
        movem.l %d0-%d6/%a0-%a1,(%sp)
        bsr     pm_slot                     | a0 = this pattern's two bytes in pm_tab
        mvz.b   (%a0),%d5
        lsl.l   #8,%d5                      | audio pattern layer, bits 8-15
        mvz.b   1(%a0),%d6
        lsl.l   #8,%d6                      | MIDI pattern layer
        move.w  %sr,%d4
        move.w  #0x2700,%sr
        move.l  %d5,pm_pa
        move.l  %d6,pm_pm
        moveq   #0,%d3                      | 1 when a word changed
        | audio
        move.l  WORD_A,%d0
        tst.b   pm_rdy_a
        beq.s   4f
        move.l  %d0,%d1
        move.l  pm_ef_a,%d2
        eor.l   %d2,%d1
        and.l   #MUTE_BITS,%d1
        beq.s   5f
4:      moveq   #1,%d2
        move.b  %d2,pm_rdy_a                   | the word moved without a hook: GLOBAL
        move.l  %d0,%d1
        and.l   #MUTE_BITS,%d1
        move.l  %d1,pm_gl_a
5:      move.l  %d0,%d1
        and.l   #~MUTE_BITS,%d1
        move.l  pm_gl_a,%d2
        or.l    pm_pa,%d2
        and.l   #MUTE_BITS,%d2
        or.l    %d2,%d1
        cmp.l   %d0,%d1
        beq.s   6f
        moveq   #1,%d3
6:      move.l  %d1,WORD_A
        move.l  %d1,pm_ef_a
        | MIDI
        move.l  WORD_M,%d0
        tst.b   pm_rdy_m
        beq.s   7f
        move.l  %d0,%d1
        move.l  pm_ef_m,%d2
        eor.l   %d2,%d1
        and.l   #MUTE_BITS,%d1
        beq.s   8f
7:      moveq   #1,%d2
        move.b  %d2,pm_rdy_m
        move.l  %d0,%d1
        and.l   #MUTE_BITS,%d1
        move.l  %d1,pm_gl_m
8:      move.l  %d0,%d1
        and.l   #~MUTE_BITS,%d1
        move.l  pm_gl_m,%d2
        or.l    pm_pm,%d2
        and.l   #MUTE_BITS,%d2
        or.l    %d2,%d1
        cmp.l   %d0,%d1
        beq.s   9f
        moveq   #1,%d3
9:      move.l  %d1,WORD_M
        move.l  %d1,pm_ef_m
        move.w  %d4,%sr
        tst.l   %d3
        beq.s   10f
        jsr     MUTE_VIEW
10:     movem.l (%sp),%d0-%d6/%a0-%a1
        lea     36(%sp),%sp
        rts

| a0 = the current pattern's two bytes in pm_tab (CUR_BANK * 32 + PATNO * 2).
| Clobbers d0, d1.
pm_slot:
        mvz.b   CUR_BANK,%d0
        and.l   #15,%d0
        lsl.l   #5,%d0
        mvz.b   PATNO,%d1
        and.l   #15,%d1
        add.l   %d1,%d1
        add.l   %d1,%d0
        lea     pm_tab,%a0
        add.l   %d0,%a0
        rts

| Write both pattern-layer words into pm_tab, copy the bank to CS1, and mark
| the bank edited as stock's Part paste does, so SAVE PROJECT runs the bank
| writer and pmute.work follows it.
pm_store_pat:
        lea     -32(%sp),%sp
        movem.l %d0-%d5/%a0-%a1,(%sp)
        bsr     pm_slot
        move.l  pm_pa,%d0
        lsr.l   #8,%d0
        move.b  %d0,(%a0)
        move.l  pm_pm,%d0
        lsr.l   #8,%d0
        move.b  %d0,1(%a0)
        moveq   #1,%d0
        move.l  %d0,pm_dirty
        mvz.b   CUR_BANK,%d0
        bsr     pm_cs1
        move.l  BANKPTR,%a0
        move.l  #EDIT_LONG,%d1
        moveq   #1,%d0
        move.l  %d0,(%a0,%d1.l)
        move.l  %d0,EDIT_FLAG
        movem.l (%sp),%d0-%d5/%a0-%a1
        lea     32(%sp),%sp
        rts

| ---- the CS1 copy of the current bank's 32 bytes ------------------------
| pm_cs1: d0 = the bank. Writes header and data under the interrupt mask, the
| magic last, so a power-off mid-write leaves no magic. Keeps every register.
pm_cs1:
        lea     -24(%sp),%sp
        movem.l %d0-%d3/%a0-%a1,(%sp)
        move.w  %sr,%d3
        move.w  #0x2700,%sr
        and.l   #15,%d0
        lea     CS1_BASE,%a1
        clr.l   (%a1)                       | no magic while it is written
        move.l  %d0,4(%a1)
        move.l  %d0,%d2                     | the sum starts with the bank
        lsl.l   #5,%d0
        lea     pm_tab,%a0
        add.l   %d0,%a0
        lea     CS1_DATA,%a1
        moveq   #8,%d1
1:      move.l  (%a0)+,%d0
        move.l  %d0,(%a1)+
        add.l   %d0,%d2
        subq.l  #1,%d1
        bne.s   1b
        lea     CS1_BASE,%a1
        move.l  %d2,8(%a1)
        move.l  #CS1_MAGIC,%d0
        move.l  %d0,(%a1)
        move.w  %d3,%sr
        movem.l (%sp),%d0-%d3/%a0-%a1
        lea     24(%sp),%sp
        rts

| pm_cs1_restore: d0 = the bank. A whole, matching copy replaces that bank's
| 32 bytes (and the file is due: CS1 may hold edits it lacks); otherwise the
| bank is read from pmute.work at the next masked load (pm_needfile).
pm_cs1_restore:
        lea     -24(%sp),%sp
        movem.l %d0-%d3/%a0-%a1,(%sp)
        and.l   #15,%d0
        move.l  %d0,%d3
        lea     CS1_BASE,%a1
        move.l  (%a1),%d1
        cmp.l   #CS1_MAGIC,%d1
        bne.s   8f
        cmp.l   4(%a1),%d3
        bne.s   8f
        move.l  %d3,%d2
        lea     CS1_DATA,%a0
        moveq   #8,%d1
1:      add.l   (%a0)+,%d2
        subq.l  #1,%d1
        bne.s   1b
        cmp.l   8(%a1),%d2
        bne.s   8f
        move.l  %d3,%d0
        lsl.l   #5,%d0
        lea     pm_tab,%a1
        add.l   %d0,%a1
        lea     CS1_DATA,%a0
        moveq   #8,%d1
2:      move.l  (%a0)+,(%a1)+
        subq.l  #1,%d1
        bne.s   2b
        moveq   #1,%d0
        move.l  %d0,pm_dirty
        bra.s   9f
8:      addq.l  #1,%d3
        move.l  %d3,pm_needfile
9:      movem.l (%sp),%d0-%d3/%a0-%a1
        lea     24(%sp),%sp
        rts

| ---- pmute.work ----------------------------------------------------------
| pm_clear: d1 = a bank mask -> those banks' 32 bytes zero. Clobbers d0, d2, a0.
pm_clear:
        moveq   #0,%d2
1:      btst    %d2,%d1
        beq.s   3f
        move.l  %d2,%d0
        lsl.l   #5,%d0
        lea     pm_tab,%a0
        add.l   %d0,%a0
        moveq   #8,%d0
2:      clr.l   (%a0)+
        subq.l  #1,%d0
        bne.s   2b
3:      addq.l  #1,%d2
        cmp.l   #16,%d2
        bne.s   1b
        rts

| pm_write -> d0 = 0 when pmute.work holds pm_tab.
pm_write:
        move.l  %d2,-(%sp)
        tst.l   pm_backup
        beq.s   1f
        clr.l   pm_backup                   | the refused file kept as pmute.bak
        lea     FMT_WORK,%a0
        lea     pm_psrc,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     FMT_BAK,%a0
        lea     pm_path,%a1
        moveq   #0,%d0
        jsr     store_path
        clr.l   -(%sp)
        pea     pm_psrc
        pea     pm_path
        jsr     F_COPY
        lea     12(%sp),%sp
1:      lea     pm_tab,%a0
        move.l  #TAB_B,%d0
        moveq   #0,%d1
        jsr     store_crc32
        move.l  %d0,pm_hdr+12
        move.l  #FMAGIC,%d0
        move.l  %d0,pm_hdr
        moveq   #1,%d0
        move.l  %d0,pm_hdr+4
        move.l  #TAB_B,%d0
        move.l  %d0,pm_hdr+8
        lea     FMT_WORK,%a0
        lea     pm_path,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     pm_path,%a0
        lea     MODE_W,%a1
        lea     pm_ctx,%a2
        jsr     store_fopen
        tst.l   %d0
        bmi.s   8f
        lea     pm_hdr,%a0
        moveq   #16,%d0
        jsr     store_fwrite
        move.l  %d0,%d2
        lea     pm_tab,%a0
        move.l  #TAB_B,%d0
        jsr     store_fwrite
        subq.l  #1,%d0
        bne.s   7f
        subq.l  #1,%d2
        bne.s   7f
        jsr     store_fclose
        moveq   #0,%d0
        bra.s   9f
7:      jsr     store_fclose
8:      addq.l  #1,pm_cnt_ioerr
        moveq   #-1,%d0
9:      move.l  (%sp)+,%d2
        rts

pm_write_if_dirty:
        tst.l   pm_dirty
        beq.s   1f
        tst.l   pm_nowrite
        bne.s   1f
        bsr     pm_write
        tst.l   %d0
        bne.s   1f
        clr.l   pm_dirty
1:      rts

| pm_read: d1 = a bank mask -> d0 = 0 those banks read, 1 no file, 2 a file
| that is not pmute.work version 1 or fails its CRC (pm_tab untouched then).
pm_read:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        move.l  %d1,%d3
        lea     FMT_WORK,%a0
        lea     pm_path,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     pm_path,%a0
        lea     MODE_R,%a1
        lea     pm_ctx,%a2
        jsr     store_fopen
        tst.l   %d0
        bpl.s   1f
        moveq   #1,%d0
        bra.w   9f
1:      lea     pm_hdr,%a0
        moveq   #16,%d0
        jsr     store_fread
        subq.l  #1,%d0
        bne.w   7f
        lea     pm_hdr,%a0
        move.l  (%a0),%d0
        cmp.l   #FMAGIC,%d0
        bne.w   7f
        moveq   #1,%d0
        cmp.l   4(%a0),%d0
        bne.w   7f
        move.l  8(%a0),%d0
        cmp.l   #TAB_B,%d0
        bne.w   7f
        lea     pm_stage,%a0
        move.l  #TAB_B,%d0
        jsr     store_fread
        subq.l  #1,%d0
        bne.w   7f
        jsr     store_fclose
        lea     pm_stage,%a0
        move.l  #TAB_B,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmp.l   pm_hdr+12,%d0
        bne.w   6f
        moveq   #0,%d2
2:      btst    %d2,%d3
        beq.s   4f
        move.l  %d2,%d0
        lsl.l   #5,%d0
        lea     pm_stage,%a0
        add.l   %d0,%a0
        lea     pm_tab,%a1
        add.l   %d0,%a1
        moveq   #8,%d1
3:      move.l  (%a0)+,(%a1)+
        subq.l  #1,%d1
        bne.s   3b
4:      addq.l  #1,%d2
        cmp.l   #16,%d2
        bne.s   2b
        moveq   #0,%d0
        bra.s   9f
7:      jsr     store_fclose
6:      addq.l  #1,pm_cnt_bad
        moveq   #2,%d0
9:      movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        rts

| pm_load: d1 = a bank mask: those banks from pmute.work; empty when it has
| none (a new project, or one saved before pmute.work existed); empty and never
| overwritten when it is refused.
pm_load:
        move.l  %d1,pm_mask
        bsr     pm_read
        tst.l   %d0
        beq.s   9f
        move.l  %d0,-(%sp)
        move.l  pm_mask,%d1
        bsr     pm_clear
        move.l  (%sp)+,%d0
        cmp.l   #2,%d0
        bne.s   9f
        moveq   #1,%d0
        move.l  %d0,pm_nowrite
        moveq   #CLIENT_ID,%d0              | STORE's list: the prompt offers what to do with it
        moveq   #0,%d1
        jsr     store_refuse
9:      rts

| pm_copy: a0 = the source format, a1 = the destination format: one of the
| project's pmute files copied over the other -> d0 < 0 on an error.
pm_copy:
        move.l  %a1,-(%sp)
        lea     pm_psrc,%a1
        moveq   #0,%d0
        jsr     store_path
        move.l  (%sp)+,%a0
        lea     pm_path,%a1
        moveq   #0,%d0
        jsr     store_path
        clr.l   -(%sp)
        pea     pm_psrc
        pea     pm_path
        jsr     F_COPY
        lea     12(%sp),%sp
        rts

| ---- STORE's handlers (modules/store/store.s); each may clobber every register
pm_st_loadall_pre:
        clr.l   pm_nowrite
        clr.l   pm_dirty
        clr.l   pm_needfile
        move.l  #0xffff,%d1
        bra     pm_load

pm_st_loadmask_pre:                         | d1 = the mask
        move.l  pm_needfile,%d0
        beq.s   1f
        clr.l   pm_needfile
        subq.l  #1,%d0
        moveq   #1,%d2
        lsl.l   %d0,%d2
        or.l    %d2,%d1
1:      bra     pm_load

pm_st_newproj:
        move.l  #0xffff,%d1
        bsr     pm_clear
        clr.l   pm_nowrite
        clr.l   pm_needfile
        moveq   #1,%d0
        move.l  %d0,pm_dirty
        mvz.b   CUR_BANK,%d0
        bra     pm_cs1

pm_st_bankw_post:
pm_st_pstore_pre:
        bra     pm_write_if_dirty

pm_st_pstore_post:                          | the project store: pmute.work -> pmute.strd
        tst.l   pm_nowrite
        bne.s   1f
        lea     FMT_WORK,%a0
        lea     FMT_STRD,%a1
        bra     pm_copy
1:      rts

pm_st_preload_post:                         | the project reload: pmute.strd -> pmute.work
        lea     FMT_STRD,%a0
        lea     FMT_WORK,%a1
        bsr     pm_copy
        tst.l   %d0
        bmi.s   1f
        clr.l   pm_nowrite
        clr.l   pm_dirty
        move.l  #0xffff,%d1
        bsr     pm_load
        mvz.b   CUR_BANK,%d0
        bra     pm_cs1
1:      rts

pm_st_tocs1:                                | d0 = the bank
        bra     pm_cs1

pm_st_fromcs1:                              | d0 = the bank
        bra     pm_cs1_restore

| pm_st_answer: d0 = IGNORE / OVERWRITE / BACKUP for a refused pmute.work.
| OVERWRITE leaves the banks it would have filled empty and writes the file at
| the next save; BACKUP has that write copy the file to pmute.bak first.
pm_st_answer:
        tst.l   %d0
        beq.s   9f
        cmp.l   #2,%d0
        bne.s   1f
        moveq   #1,%d0
        move.l  %d0,pm_backup
1:      clr.l   pm_nowrite
        moveq   #1,%d0
        move.l  %d0,pm_dirty
9:      rts

| pm_others -> d0 = the held keys other than FUNC (0: none), from the panel
| parser's row states (8 bytes, row n bit b = key n*8+b; FUNC 0x2d is row 5's
| 0x20, bit 21 of the second long). Measured under the port, 17 Nov 2026: FUNC,
| T2 and trig 1 set 0x20 in row 5, 0x02 in row 2, 0x01 in row 0 while held.
| Keeps every other register.
pm_others:
        move.l  PANEL_ROWS+4,%d0
        and.l   #~(FUNC_BIT << ((7 - FUNC_ROW) * 8)),%d0
        or.l    PANEL_ROWS,%d0
        rts

| FUNC's press record in both stock key tables points here. The key layer
| calls a press handler with (code, edge) on the stack: edge 1 a press, 2 a
| repeat while held. Two presses within DOUBLE_WINDOW counts of the free-run
| timer DTCN3 flip the layer, when no other key was held between them: a
| pending first press is dropped by pm_ui_tick as soon as another key is held,
| and a press made while one is held neither starts nor ends a pair. Until 16
| Nov 2026 FUNC+track or FUNC+trig pressed twice within 300 ms flipped the
| layer (sambanks/octabam#1143). Every call continues to stock's handler,
| which sets the FUNC-held flag.
pm_func_press:
        moveq   #1,%d0
        cmp.l   8(%sp),%d0
        bne.s   9f
        bsr     pm_others
        tst.l   %d0
        beq.s   0f
        clr.l   %d1
        move.b  %d1,pm_tap                  | another key is held: no pair
        bra.s   9f
0:      move.l  DTCN3,%d0
        mvz.b   pm_tap,%d1
        beq.s   8f
        move.l  %d0,%d1
        sub.l   pm_tap_t,%d1
        cmp.l   #DOUBLE_WINDOW,%d1
        bhi.s   8f
        clr.l   %d1
        move.b  %d1,pm_tap                  | the pair is used up
        mvz.b   LAYER_B,%d0
        and.l   #1,%d0
        eori.l  #1,%d0
        move.b  %d0,LAYER_B                 | battery SRAM: survives power-off
        lea     pm_txt_glob:l,%a0
        tst.l   %d0
        beq.s   1f
        lea     pm_txt_pat:l,%a0
1:      moveq   #TOAST_TIME,%d1
        move.l  %d1,-(%sp)
        move.l  %a0,-(%sp)
        jsr     NOTIFY
        addq.l  #8,%sp
        bra.s   9f
8:      move.l  %d0,pm_tap_t
        moveq   #1,%d1
        move.b  %d1,pm_tap
9:      jmp     FUNC_STOCK

| The UI loop's call at 0x40052228 (jsr 0x400316a0, the key-repeat tick, 60 Hz) reaches this
| first. While the PATTERN layer is active it holds the second colour bit of
| the current track's key lit, so the key shows both colours; stock lights
| only the first for the selected track. set_led(id, ticks) is stock's own
| LED API: the bit clears when its countdown ends, and the countdown here is
| three UI ticks.
pm_ui_tick:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        tst.b   pm_tap                      | a pending FUNC press: dropped once another key is held
        beq.s   1f
        bsr     pm_others
        tst.l   %d0
        beq.s   1f
        clr.l   %d0
        move.b  %d0,pm_tap
1:      mvz.b   LAYER_B,%d0
        btst    #0,%d0
        beq.s   9f
        mvz.b   CUR_TRACK,%d0
        and.l   #7,%d0
        move.l  %d0,%d1
        lsr.l   #2,%d1
        addq.l  #5,%d1                      | track keys: rows 5 and 6
        lsl.l   #3,%d1
        and.l   #3,%d0
        add.l   %d0,%d0
        add.l   %d0,%d1
        addq.l  #1,%d1                      | the odd bit
        moveq   #LED_TICKS,%d0
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        jsr     SET_LED
        addq.l  #8,%sp
9:      movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        jmp     UI_NEXT

        .data
        .balign 4
pm_gl_a:        .long   0                   | GLOBAL layer, audio (bits 8-15)
pm_gl_m:        .long   0
pm_pa:          .long   0                   | PATTERN layer of the current pattern
pm_pm:          .long   0
pm_ef_a:        .long   0                   | the effective word published last
pm_ef_m:        .long   0
pm_rdy_a:       .byte   0
pm_rdy_m:       .byte   0
pm_tap:         .byte   0                   | 1 when pm_tap_t holds a FUNC press
        .balign 4
pm_tap_t:       .long   0
pm_txt_glob:    .asciz  "GLOBAL MUTE"
pm_txt_pat:     .asciz  "PATTERN MUTE"
        .balign 4
pm_dirty:       .long   0                   | pmute.work is due
pm_nowrite:     .long   0                   | pmute.work was refused: never overwritten
pm_backup:      .long   0                   | the next write first copies pmute.work to pmute.bak
pm_needfile:    .long   0                   | bank + 1: no CS1 copy, read it at the next masked load
pm_mask:        .long   0
pm_cnt_bad:     .long   0                   | pmute.work refused
pm_cnt_ioerr:   .long   0                   | pmute.work not written
pm_tab:         .fill   TAB_B, 1, 0         | the PATTERN layer: bank * 32 + pattern * 2: audio, MIDI
FMT_WORK:       .asciz  "%s/pmute.work"
FMT_STRD:       .asciz  "%s/pmute.strd"
FMT_BAK:        .asciz  "%s/pmute.bak"
MODE_R:         .asciz  "r"
MODE_W:         .asciz  "w"

        .section .bss
        .balign 4
pm_stage:       .space  TAB_B               | pmute.work read here before it is applied
pm_ctx:         .space  4120                | STORE_CTX
pm_hdr:         .space  16
pm_path:        .space  260
pm_psrc:        .space  260
