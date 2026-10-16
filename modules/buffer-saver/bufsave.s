| BUFFER SAVER -- SAVE PROJECT first offers to save the recorder
| buffers holding a take not yet saved: each to the card under an automatic
| name, assigned to itself (stock's ASSIGN TO SELF), so a reload of the
| project brings the take back.
|
| Hooks:
|   arm_mark   (0x400069d6) the recorder's per-track take start (LIMIT
|              written, d3 = track 0..7): marks buffer d3 in `pending`.
|              Recorder buffer n belongs to track n (object id 128 + n).
|   load_clear (0x4008534c, the engine's LOAD PROJECT case) clears
|              `pending`: what the load brings back is saved already.
|   save_gate  (0x40063890) the PROJECT menu's SAVE, which FUNC + PROJ also
|              reaches (0x400648fc). With a marked buffer that has audio and
|              is not recording, it asks SAVE SAMPLES?; NO, or nothing to
|              save, runs stock's SAVE unchanged.
|
| YES saves the marked buffers one at a time, lowest first, the way stock's
| SAVE ALL RECORDINGS does (0x4003108c): 0x460be9e8/ec = FLEX / 128 + n,
| mode 0x460bcfc8 = 2 (assign to self, no menu), done callback 0x46c8d198,
| the name in 0x460be9f0, then the naming keyboard's own confirm
| 0x40024288(1) instead of the keyboard. Stock writes the WAV and its .ot,
| assigns the buffer to the file and calls the done callback (0x40022d80)
| with the result. The name is stock's suggestion R<n>-YYMMDD-HHMM
| (0x400b39ef, 0x400819fc); if that file exists, -2, -3 .. -99 is added, so
| nothing is overwritten. After the last buffer, stock's SAVE runs.
|
| A buffer's mark is cleared only when its save reports success. A failed
| save shows stock's error and stops the chain before the project save; the
| mark stays, so the next SAVE PROJECT offers it again.
|
| Measured under the port on stock (15 Oct 2026, the handoff note): mode 2
| assigns to self; the project then records SLOT=129 PATH=../AUDIO/<name>
| and a reload refills the buffer. This unit's own behaviour: not yet run.
        .text
        .global arm_mark
        .global load_clear
        .global save_gate

        .equ    KIND, 0x460be9e8        | the sample save's object kind (1 = FLEX)
        .equ    OBJ, 0x460be9ec         | ... and object id (recorder buffer n = 128 + n)
        .equ    NAME, 0x460be9f0        | ... and file name, no extension
        .equ    MODE, 0x460bcfc8        | 2 = save, then assign to self with no menu
        .equ    DONE_A, 0x46c8d194      | done callbacks: A after the WAV (mode 0),
        .equ    DONE_B, 0x46c8d198      | B after the assignment (modes 1, 2)
        .equ    POOL_READY, 0x46105408  | non-zero once the sample pool is up
        .equ    STATE, 0x46c922c4       | slot state records, 44 B; +16 = length in frames
        .equ    SET_DIR, 0x100f8480     | the set's directory
        .equ    SAVE_TO, 0x800000a4     | SAVE SAMPLES TO: non-zero = the project
        .equ    FILE_EXISTS, 0x46c823fa | pointer to the file-exists test

| 0x400069d6 displaced: move.l %d0,(0,%a0,%d3.l*4) / moveq #1,%d2.
arm_mark:
        move.l  %d0,(0,%a0,%d3.l*4)
        moveq   #1,%d2
        bset    %d3,pending             | bit d3 of the byte: buffer d3 has a new take
        jmp     (0x400069dc).l

| 0x4008534c displaced: jsr 0x400909d8 ("jsr" detour: returns to 0x40085352).
load_clear:
        jsr     (0x400909d8).l
        clr.b   pending
        rts

| 0x40063890 displaced: lea -12(%sp),%sp / move.l %d2,-(%sp). Called with
| one argument (FUNC + PROJ passes 0; stock's SAVE reads it only on the
| path where it is ignored).
save_gate:
        bsr     ready
        tst.l   %d0
        bne.s   .sg_ask
stock_save:
        lea     -12(%sp),%sp
        move.l  %d2,-(%sp)
        jmp     (0x40063896).l          | stock's SAVE, unchanged
.sg_ask:
        pea     answer
        pea     3                       | YES / NO
        pea     ask_lines
        pea     2                       | two lines
        pea     (0x400b3820).l          | "SAVE PROJECT"
        jsr     (0x4006d57c).l
        lea     20(%sp),%sp
        rts

| The dialog's callback (it closes before calling): 0 = YES.
answer:
        tst.l   4(%sp)
        bne.s   stock_save
        clr.l   tried
        bra.s   next_buffer

| Stock's done callback for one buffer, (result): < 0 = failed.
chain_done:
        tst.l   4(%sp)
        bmi.s   .cd_stop
        move.l  current,%d0
        bclr    %d0,pending             | saved: the take is on the card
        bra.s   next_buffer
.cd_stop:
        rts

| Save the lowest ready buffer not tried in this chain; with none left,
| stock's SAVE.
next_buffer:
        bsr     ready
        move.l  tried,%d1
        not.l   %d1
        and.l   %d1,%d0
        beq.s   stock_save
        moveq   #0,%d1
.nb_find:
        btst    %d1,%d0
        bne.s   .nb_found
        addq.l  #1,%d1
        bra.s   .nb_find
.nb_found:
        move.l  %d1,current
        move.l  tried,%d0
        bset    %d1,%d0
        move.l  %d0,tried
        bsr     make_name
        moveq   #1,%d0
        move.l  %d0,KIND
        move.l  current,%d0
        addi.l  #128,%d0
        move.l  %d0,OBJ
        moveq   #2,%d0
        move.l  %d0,MODE
        clr.l   DONE_A
        lea     chain_done,%a0
        move.l  %a0,DONE_B
        pea     1
        jsr     (0x40024288).l          | the naming keyboard's confirm: save, then assign
        addq.l  #4,%sp
        rts

| d0 <- the buffers (bit n) marked, with audio, and not recording.
| Keeps d2-d7/a2-a6.
ready:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        moveq   #0,%d3                  | result
        tst.l   POOL_READY
        beq.s   .rd_done
        moveq   #0,%d2                  | buffer
.rd_loop:
        moveq   #0,%d0
        move.b  pending,%d0
        btst    %d2,%d0
        beq.s   .rd_next
        move.l  %d2,%d0
        addi.l  #128,%d0
        moveq   #44,%d1
        muls.l  %d1,%d0
        addi.l  #STATE,%d0
        movea.l %d0,%a0
        tst.l   16(%a0)
        ble.s   .rd_next                | empty
        move.l  %d2,-(%sp)
        jsr     (0x40004268).l          | the recorder's state: non-zero = armed or recording
        addq.l  #4,%sp
        tst.b   %d0
        bne.s   .rd_next
        bset    %d2,%d3
.rd_next:
        addq.l  #1,%d2
        moveq   #8,%d0
        cmp.l   %d0,%d2
        blt.s   .rd_loop
.rd_done:
        move.l  %d3,%d0
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| NAME <- R<current+1>-YYMMDD-HHMM, with -2 .. -99 added while that file
| exists where stock will write it (0x40024288's path).
make_name:
        lea     -8(%sp),%sp
        movem.l %d2/%a2,(%sp)
        jsr     (0x400819fc).l          | "YYMMDD-HHMM"
        move.l  %d0,-(%sp)
        move.l  current,%d0
        addq.l  #1,%d0
        move.l  %d0,-(%sp)
        pea     (0x400b39ef).l          | "R%d-%s"
        pea     base_name
        jsr     (0x40013a08).l          | sprintf
        lea     16(%sp),%sp
        moveq   #1,%d2                  | k: 1 = the name as it is
.mn_try:
        cmpi.l  #1,%d2
        bne.s   .mn_suffix
        pea     base_name
        pea     fmt_plain
        bra.s   .mn_print
.mn_suffix:
        move.l  %d2,-(%sp)
        pea     base_name
        pea     fmt_suffix
.mn_print:
        pea     (NAME).l
        jsr     (0x40013a08).l
        lea     12(%sp),%sp
        cmpi.l  #1,%d2
        beq.s   .mn_path
        addq.l  #4,%sp                  | the suffix call's extra argument
.mn_path:
        tst.l   SAVE_TO
        beq.s   .mn_set
        jsr     (0x40024eec).l
        tst.l   %d0
        beq.s   .mn_set
        clr.l   -(%sp)
        clr.l   -(%sp)
        jsr     (0x40025230).l          | the project's directory
        addq.l  #8,%sp
        pea     (NAME).l
        move.l  %d0,-(%sp)
        pea     (0x400b3a95).l          | "%s/%s.wav"
        bra.s   .mn_fmt
.mn_set:
        pea     (NAME).l
        pea     (SET_DIR).l
        pea     (0x400b3a85).l          | "%s/AUDIO/%s.wav"
.mn_fmt:
        pea     path
        jsr     (0x40013a08).l
        lea     16(%sp),%sp
        pea     path
        movea.l FILE_EXISTS,%a0
        jsr     (%a0)
        addq.l  #4,%sp
        tst.l   %d0
        beq.s   .mn_done                | free
        addq.l  #1,%d2
        moveq   #99,%d0
        cmp.l   %d0,%d2
        ble.w   .mn_try
.mn_done:
        movem.l (%sp),%d2/%a2
        lea     8(%sp),%sp
        rts

fmt_plain:
        .asciz  "%s"
fmt_suffix:
        .asciz  "%s-%d"
ask_l1:
        .asciz  "UNSAVED RECORDINGS!"
ask_l2:
        .asciz  "SAVE SAMPLES?"

        .data
        .balign 4
ask_lines:
        .long   ask_l1, ask_l2
current:
        .long   0                       | the buffer being saved
tried:
        .long   0                       | buffers tried in this chain (bit n)
base_name:
        .space  64
path:
        .space  256
pending:
        .byte   0                       | buffers with a take not yet saved (bit n)
        .balign 4
