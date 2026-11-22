| trigmode.s -- TRACK TRIG MODE: each audio track keeps its own CHROMATIC /
| SLOTS / SLICES trig mode, saved with the project.
|
| The trig mode is the long 0x460d16f0 (0 TRACKS, 1 CHROMATIC, 2 SLOTS,
| 3 SLICES, 4 QUICK MUTE, 5 DELAY CONTROL). Stock keeps one for every track
| and saves none. TM_NV holds one byte per audio track: 1..3, or 0 = not
| set yet (the track takes whatever mode is showing); any other value reads
| as 0. TM_NV is battery RAM (CS1, unused by stock): a power-up restores the
| project from CS1 without parsing project.work (27 Oct 2026, on the MKI:
| the modes were saved, and gone after a power cycle, while they lived in
| DRAM), so the table must survive there as stock's own settings do.
|
| tm_up / tm_down (FUNC + UP / DOWN, 0x40051f88 / 0x40051f18, the store of
|          the new mode): a step between CHROMATIC / SLOTS / SLICES is kept
|          for the current track. TRACKS, QUICK MUTE and DELAY CONTROL stay
|          global: they are not kept and a track change leaves them showing.
|          A step out of a global mode lands on the track's own mode (the
|          list's cursor moved to it) and writes nothing; a track with none
|          keeps the pick. (28 Oct 2026, on the MKI: stepping out of QUICK
|          MUTE overwrote the track's saved mode with whatever was passed.)
| tm_trk   (audio track select 0x40083bf8, after the track is stored): if
|          the mode showing is 1..3 and the new track has one, show it.
| tm_boot  (after the load's bank read, 0x40084d66, on a project load and
|          at power-up): the current track's own mode, if it has one, is
|          shown. Hooked after the call, not on it: KITS (via STORE) tells
|          the power-up's bank load by its return address 0x40084d66.
| tm_save  (project writer 0x40088288, before [/SETTINGS]): writes
|          "#TRIG_MODES=dddddddd" -- one digit a track, T1 first.
| tm_load  (project parser 0x400866c4, entry): an applying parse (second
|          argument nonzero) forgets every track's mode, so a project
|          without the line starts all unset.
| tm_line  (parser, each line's first-character test 0x400867a2): the
|          "#TRIG_MODES=" line fills TM_NV on an applying parse. Stock
|          skips every line starting with '#', and stops a load on a key it
|          does not know, so the comment keeps the project loading on stock.
|
| Audio tracks only: every hook is gated on 0x80000012 == 0 (MIDI tracks
| not shown; stock's own test). In MIDI mode 0x80000000 holds the MIDI track.

        .set    TM_NV,     0x100f85e8   | CS1, 8 bytes (manifest claim)
        .set    TMODE,     0x460d16f0   | trig mode 0..5
        .set    UI_TRACK,  0x100b14cc   | current track (CS1 mirror of 0x80000000)
        .set    MIDI_MODE, 0x80000012   | nonzero: MIDI tracks shown
        .set    DRAW_MODE, 0x4004581c   | trig-mode label + trig LEDs
        .set    TRK_PREP,  0x40097460   | displaced call in the track select
        .set    TRK_JOIN,  0x40083c40
        .set    UP_JOIN,   0x40051f8e
        .set    DOWN_JOIN, 0x40051f1e
        .set    BOOT_JOIN, 0x40084d6c   | blts, on tstl d0
        .set    MLIST,     0x46c7d330   | the mode list: top, offset, cursor, rows, count
        .set    WRITE,     0x400166b8   | (file, buf, len) -> < 0 on error
        .set    SAVE_JOIN, 0x40088da6
        .set    END_SET,   0x400b84c2   | "[/SETTINGS]\r\n"
        .set    LOAD_JOIN, 0x400866cc
        .set    LINE_JOIN, 0x400867a8
        .set    LINE_NEXT, 0x40088224   | parser: on to the next line

        .text
        .globl  tm_up, tm_down, tm_trk, tm_boot, tm_save, tm_load, tm_line

| ---- 0x40051f88 / 0x40051f18: FUNC + UP / DOWN stores the new mode ----------
| Displaced: movel %a0@,0x460d16f0. d0/d1/a1 are free here.
tm_up:
        bsr.s   tm_pick
        jmp     UP_JOIN

tm_down:
        bsr.s   tm_pick
        jmp     DOWN_JOIN

tm_pick:
        movel   TMODE,%d1               | the mode before the step
        movel   %a0@,TMODE
        tstl    MIDI_MODE
        bne.w   9f
        movel   TMODE,%d0
        bsr.w   tm_pt                   | the new mode per track?
        bne.w   9f                      | global: not kept
        movel   %d1,%d0
        bsr.w   tm_pt
        beq.s   5f                      | per track to per track: keep it
        moveq   #0,%d1
        moveb   UI_TRACK,%d1
        bsr.w   tm_own
        beq.s   5f                      | out of a global mode, no own mode yet
        movel   %d1,TMODE               | out of a global mode: the track's own
        movel   %d2,%sp@-
        lea     MLIST,%a1
        movel   %a1@,%d0                | top
        cmpl    %d0,%d1
        bge.s   1f
        movel   %d1,%d0                 | above the window: it starts there
1:      movel   %d0,%d2
        addl    %a1@(12),%d2            | top + rows
        cmpl    %d2,%d1
        blt.s   2f
        movel   %d1,%d0
        subl    %a1@(12),%d0
        addql   #1,%d0                  | below it: it ends there
2:      movel   %d0,%a1@
        movel   %d1,%a1@(8)
        subl    %d0,%d1
        movel   %d1,%a1@(4)
        movel   %sp@+,%d2
        rts
5:      movel   TMODE,%d0
        moveq   #0,%d1
        moveb   UI_TRACK,%d1
        lea     TM_NV,%a1
        moveb   %d0,%a1@(0,%d1:l)
9:      rts

| tm_pt: d0 = a mode -> Z set when it is CHROMATIC / SLOTS / SLICES.
tm_pt:
        subql   #1,%d0
        cmpil   #2,%d0
        bhi.s   1f
        cmpl    %d0,%d0                 | Z
        rts
1:      moveq   #1,%d0                  | Z clear
        rts

| tm_own: d1 = track -> d1 = its own mode 1..3, or 0 (Z set). Uses a1.
tm_own:
        lea     TM_NV,%a1
        moveb   %a1@(0,%d1:l),%d1
        andil   #0xff,%d1
        cmpil   #3,%d1
        bls.s   1f
        moveq   #0,%d1                  | not a mode: battery RAM never written
1:      tstl    %d1
        rts

| ---- 0x40083c3a: audio track select, d2 = the new track ---------------------
| Displaced: jsr 0x40097460.
tm_trk:
        jsr     TRK_PREP
        tstl    MIDI_MODE
        bne.s   9f
        movel   TMODE,%d0
        moveq   #1,%d1
        cmpl    %d1,%d0
        blt.s   9f
        moveq   #3,%d1
        cmpl    %d1,%d0
        bgt.s   9f
        movel   %d2,%d1
        bsr     tm_own
        beq.s   9f                      | not set: keep what is showing
        cmpl    %d1,%d0
        beq.s   9f
        movel   %d1,TMODE
        jsr     DRAW_MODE
9:      jmp     TRK_JOIN

| ---- 0x40084d66: a project load / the power-up, after the bank read ---------
| d0 = the read's result, tested again here for the join's blts. The screen
| is redrawn after the load, so only the mode is set here.
| Displaced: lea %sp@(16),%sp ; tstl %d0
tm_boot:
        lea     %sp@(16),%sp
        tstl    MIDI_MODE
        bne.s   9f
        movel   %d0,%sp@-
        moveq   #0,%d1
        moveb   UI_TRACK,%d1
        bsr     tm_own
        beq.s   8f
        movel   %d1,TMODE
8:      movel   %sp@+,%d0
9:      tstl    %d0
        jmp     BOOT_JOIN

| ---- 0x40088da0: project writer, before "[/SETTINGS]" -----------------------
| d3 = the file. Displaced: pea 0x400b84c2.
tm_save:
        lea     tm_text+12,%a0          | after "#TRIG_MODES="
        moveq   #0,%d1
1:      movel   %d1,%sp@-
        bsr     tm_own
        addil   #'0',%d1
        moveb   %d1,%a0@+
        movel   %sp@+,%d1
        addql   #1,%d1
        moveq   #8,%d0
        cmpl    %d0,%d1
        blt.s   1b
        pea     tm_text_end-tm_text
        pea     tm_text
        movel   %d3,%sp@-
        jsr     WRITE                   | an error shows on stock's next write
        lea     %sp@(12),%sp
        pea     END_SET
        jmp     SAVE_JOIN

| ---- 0x400866c4: project parser entry (file, apply) -------------------------
| Displaced: lea %sp@(-1468),%sp ; moveml %d2-%d7/%a2-%fp,%sp@
tm_load:
        tstl    %sp@(8)
        beq.s   1f
        clrl    TM_NV
        clrl    TM_NV+4
1:      lea     %sp@(-1468),%sp
        moveml  %d2-%d7/%a2-%fp,%sp@
        jmp     LOAD_JOIN

| ---- 0x400867a2: parser, a line read; d3 = the line --------------------------
| %sp@(58) nonzero = a checking parse (apply nothing). a0/a1 are kept: the
| stock path below is not read for them. d0/d1 are the displaced pair's.
| Displaced: moveb %sp@(1167),%d1 ; mvsb %d1,%d0
tm_line:
        lea     %sp@(-8),%sp
        moveml  %a0-%a1,%sp@
        moveal  %d3,%a0
        lea     tm_text,%a1
        moveq   #11,%d1                 | "#TRIG_MODES=" is 12 characters
1:      moveb   %a0@+,%d0
        cmpb    %a1@+,%d0
        bne.s   8f
        subql   #1,%d1
        bge.s   1b
        tstl    %sp@(58+8)
        bne.s   7f
        lea     TM_NV,%a1
        moveq   #7,%d1
2:      moveq   #0,%d0
        moveb   %a0@+,%d0
        subil   #'0',%d0
        cmpil   #3,%d0
        bhi.s   7f                      | short or bad line: keep what was read
        moveb   %d0,%a1@+
        subql   #1,%d1
        bge.s   2b
7:      moveml  %sp@,%a0-%a1
        lea     %sp@(8),%sp
        jmp     LINE_NEXT               | a comment either way
8:      moveml  %sp@,%a0-%a1
        lea     %sp@(8),%sp
        .ifdef  TM_QZ
| SCALE QUANTIZER in the image (8thmyth, 16 Nov 2026): it reads its own
| "#SEQUENCER_..." / "#SYNTH_GLIDE=" lines at this same site, so this
| module's manifest takes the site (Override) and every other line goes on
| to qz_ld_line, which replays the displaced instructions itself.
        jmp     qz_ld_line
        .else
        moveb   %sp@(1167),%d1
        mvsb    %d1,%d0
        jmp     LINE_JOIN
        .endif

        .data
tm_text:                                | tm_save writes the digits in place
        .ascii  "#TRIG_MODES=00000000\r\n"
tm_text_end:
