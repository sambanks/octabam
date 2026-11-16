| LOCK EDIT -- one DRAM unit. GNU as, ColdFire (m68k-elf-as -mcpu=54455). (8thmyth, Nov 2026)
|
| [TRIG] + [BANK] in grid recording opens the audio editor on the held step's
| sample (its sample lock, else the track's own) on the SLICE page, with the
| slice that step plays selected and in view:
|   SLIC on, the sample sliced: slice STRT / 2 (stock's: STRT 8 and 9 both
|     play slice 5, measured under the port), at most the last slice.
|   Otherwise (SLIC off, or no slices): the frame stock starts the step from,
|     trim start + STRT x trim length / 128 (measured: STRT 64 of a
|     22050..88200 trim plays from 55125); the slice starting there is
|     selected, else the view is centred on that frame.
| STRT is the step's lock (the byte is the value, 0xff none) or the Part's.
| While the trig is held the page's encoders edit that slice (stock's).
| A trig's hold event would open the lock popup and shut the editor, so
| le_trighold drops it while the editor is up. Otherwise [BANK] is stock's.

        .equ    CUR_TRACK,  0x100b14cc
        .equ    F_REC,      0x4006da78     | () -> the edited slot's record, 0 if none
        .equ    REC_TRIM_S, 300
        .equ    REC_TRIM_E, 304
        .equ    REC_SLICES, 312            | 64 x {start, end, loop}
        .equ    REC_COUNT,  1092

        .text
        .global le_bank, le_trighold

| ---- [TRIG] + [BANK] in grid recording: the editor on that step's sample ----
| A pointer swap on [BANK]'s press in both MKI key tables (stock 0x4007af80).
| In grid recording (0x460d1736) on an audio track (0x80000012 = 0) with a
| trig held (mask 0x460d174a, page base 0x460d174c): the audio editor opens
| on the step's sample lock (byte 31 of its record), or without one on the
| track's sample as [TRACK]+[BANK] picks it (the Part's slot byte), through
| stock's calls 0x4006de34(type, slot) + 0x4006e160(); then the bookkeeping
| stock's p-lock store does (0x4004f766..f792), so the trig's release leaves
| the step alone, and [BANK]'s tap state 0 so its release does nothing.
| Otherwise stock's [BANK]. (octalab's shortcut, INPUT.md section 9; written
| here from its notes.)
        .equ    F_BANKPRESS, 0x4007af80
        .equ    F_AEDSET,   0x4006de34     | (type, slot)
        .equ    F_AEDOPEN,  0x4006e160
        .equ    F_TRIGKEY,  0x40060ce0          | the grid's TRIG press/hold/release
        .equ    F_LOCKPOPDN, 0x40024b84         | the sample-lock popup's own close (none up: nothing)
        .equ    AED_WIN,    0x460e5e4c          | the editor's window, 0 when shut
        .equ    GRID_REC,   0x460d1736
        .equ    HELD_TRIGS, 0x460d174a     | u16, a bit a trig key
        .equ    HELD_PAGE,  0x460d174c     | u16, the step page's first step
        .equ    MIDI_TRACK, 0x80000012
        .equ    BANK_BLOB,  0x46c82456     | the bank's RAM blob
        .equ    CUR_PART,   0x100b14cf
        .equ    CUR_PTN,    0x80000004
le_bank:
        tst.l   (GRID_REC).l
        beq     8f
        tst.l   (MIDI_TRACK).l
        bne     8f
        moveq   #0,%d0
        move.w  (HELD_TRIGS).l,%d0
        tst.l   %d0
        beq     8f
        lea     -16(%sp),%sp
        movem.l %d2-%d5,(%sp)
        ff1.l   %d0                     | the first held trig from the top bit
        moveq   #31,%d2
        sub.l   %d0,%d2                 | its key 0-15
        moveq   #0,%d0
        move.w  (HELD_PAGE).l,%d0
        add.l   %d0,%d2                 | d2 = the step, 0-63
        moveq   #0,%d3
        move.b  (CUR_TRACK).l,%d3
        and.l   #7,%d3                  | d3 = the track
        move.l  (BANK_BLOB).l,%a0
        moveq   #0,%d0
        move.b  (CUR_PART).l,%d0
        move.l  #0x18b2,%d1
        mulu.l  %d1,%d0
        add.l   #0x8ed80,%d0
        add.l   %a0,%d0
        move.l  %d0,%a1                 | a1 = the Part (RAM)
        moveq   #0,%d4
        move.b  0x22(%a1,%d3.l),%d4     | the machine type: 0 STATIC, 1 FLEX
        cmp.l   #1,%d4
        bhi     7f                      | THRU, NEIGHBOR, PICKUP: stock's [BANK]
        moveq   #0,%d0
        move.b  (CUR_PTN).l,%d0
        move.l  #0x8ed8,%d1
        mulu.l  %d1,%d0
        add.l   %d0,%a0
        move.l  %d3,%d0
        move.l  #0x91a,%d1
        mulu.l  %d1,%d0
        add.l   %d0,%a0                 | a0 = the track's TRAC
        move.l  %d2,%d0
        lsl.l   #5,%d0
        moveq   #0,%d5
        move.b  0x78(%a0,%d0.l),%d5     | the step's sample lock, 0xff none
        cmp.l   #0xff,%d5
        bne     3f
        move.l  %d3,%d0                 | none: the Part's slot byte for the machine
        move.l  %d0,%d1
        lsl.l   #2,%d1
        add.l   %d1,%d0                 | 5t
        add.l   %d4,%d0
        add.l   #0x2ca,%d0              | (an index's displacement is 8 bits on ColdFire)
        moveq   #0,%d5
        move.b  0(%a1,%d0.l),%d5
        bset    #31,%d5                 | (flag: the track's own sample)
3:      move.l  %d2,%d0                 | the step's STRT and the track's SLIC, for the
        lsl.l   #5,%d0                  | SLICE page's selection (le_sel, below)
        moveq   #0,%d1
        move.b  0x5a(%a0,%d0.l),%d1     | STRT lock: track + 0x59 + 32 step + 1 (0xff none)
        cmp.l   #0xff,%d1               | (the byte is STRT itself, measured: STRT 64 = 64)
        bne     5f
        move.l  %d3,%d0                 | none: the Part's STRT (values + 30t + 6 machine + 1)
        moveq   #30,%d1                 | (no mulu.l #imm on ColdFire)
        mulu.l  %d1,%d0
        move.l  %d4,%d1
        add.l   %d1,%d1                 | 2 m
        add.l   %d1,%d0
        add.l   %d1,%d0
        add.l   %d1,%d0                 | + 6 m
        add.l   #PART_VALS+1,%d0
        moveq   #0,%d1
        move.b  0(%a1,%d0.l),%d1
5:      move.l  %d1,le_strt
        move.l  %d3,%d0                 | SLIC: the Part's SETUP + 30t + 6 machine + 1
        moveq   #30,%d1                 | (no mulu.l #imm on ColdFire)
        mulu.l  %d1,%d0
        move.l  %d4,%d1
        add.l   %d1,%d1                 | 2 m
        add.l   %d1,%d0
        add.l   %d1,%d0
        add.l   %d1,%d0                 | + 6 m
        add.l   #PART_SETUP+1,%d0
        moveq   #0,%d1
        move.b  0(%a1,%d0.l),%d1
        move.l  %d1,le_slic
        jsr     (F_LOCKPOPDN).l         | a held trig's lock popup down first: the editor
                                        | opens only with no popup up
        move.l  %d5,%d0
        and.l   #0xff,%d0
        move.l  %d0,-(%sp)
        move.l  %d4,-(%sp)
        jsr     (F_AEDSET).l
        addq.l  #8,%sp
        moveq   #AED_SLICEPG,%d0        | open on the SLICE page (the page it enters is
        move.l  %d0,(AED_PAGE).l        | the one last used: 0x4006e160 -> 0x4006ddb4)
        jsr     (F_AEDOPEN).l
        tst.l   (AED_WIN).l
        beq     6f
        bsr     le_sel                | the step's slice selected
6:
        moveq   #1,%d0                  | stock's p-lock store bookkeeping
        move.l  %d0,(0x460d173a).l
        move.l  %d0,(0x460d1750).l
        moveq   #0,%d0
        move.w  %d0,(0x460d1a9e).l
        move.w  %d0,(0x460d1aa0).l
        move.w  %d0,(0x460d1aa2).l
        move.w  %d0,(0x460d1aa4).l
        move.w  %d0,(0x460d1aa6).l
        move.w  %d0,(0x460d10dc).l
        clr.l   (0x460e73c2).l          | [BANK]'s tap state: its release does nothing
                                        | (no popup: 0x4006e160 opens the editor a moment
                                        | later and only with none up; a "LOCK: FLEX n"
                                        | toast here kept it shut. The editor names the sample.)
        movem.l (%sp),%d2-%d5
        lea     16(%sp),%sp
        rts
7:      movem.l (%sp),%d2-%d5
        lea     16(%sp),%sp
8:      jmp     (F_BANKPRESS).l

| LOCK EDIT: select the held step's slice on the SLICE page just opened, with
| the editor's own select (0x40071668(type, slot, n): marker, selection and,
| with lc_fitkeep, the view). SLIC on: n = STRT / 2, at most the last slice
| (stock's: the voice's slice +32 = live STRT >> 1, measured under the port).
| SLIC off: the slice holding the frame STRT / 128 of the way through the trim.
| Clobbers d0-d1/a0-a1.
le_sel:
        jsr     (F_REC).l
        tst.l   %d0
        beq     9f
        move.l  %d0,%a0
        move.l  REC_COUNT(%a0),%d1
        move.l  le_strt,%d0
        tst.l   le_slic
        beq     2f
        tst.l   %d1                     | SLIC on: slice STRT / 2 (stock's, measured:
        ble     2f                      | STRT 8 and 9 both play slice 5). A sample with
                                        | no slices plays from STRT / 128 as with SLIC off
                                        | (measured: STRT 64 -> 44100 of 88200): the frame
        lsr.l   #1,%d0
        cmp.l   %d1,%d0
        blt     5f
        move.l  %d1,%d0
        subq.l  #1,%d0                  | at most the last slice
        bra     5f
2:      lea     -8(%sp),%sp             | SLIC off: the frame stock starts from,
        movem.l %d2-%d3,(%sp)           | trim start + STRT (trim length) / 128 (measured:
        move.l  REC_TRIM_E(%a0),%d2     | STRT 64 on a 22050..88200 trim plays from 55125)
        sub.l   REC_TRIM_S(%a0),%d2
        move.l  %d2,%d3
        and.l   #127,%d3
        mulu.l  %d0,%d3
        lsr.l   #7,%d3                  | (length mod 128) STRT / 128
        lsr.l   #7,%d2
        mulu.l  %d0,%d2                 | + (length / 128) STRT: exact, no overflow
        add.l   %d2,%d3
        add.l   REC_TRIM_S(%a0),%d3     | d3 = the frame
        tst.l   %d1
        ble     6f                      | no slices: show the frame
        move.l  %d3,%d2
        add.l   #LE_TOL,%d2             | a slice starting just after it counts (grid rounding)
        lea     REC_SLICES(%a0),%a1
        cmp.l   (%a1),%d2
        blt     6f                      | before the first slice
        moveq   #0,%d0                  | the last slice starting at or before it
3:      addq.l  #1,%d0
        cmp.l   %d1,%d0
        bge     4f
        lea     12(%a1),%a1
        cmp.l   (%a1),%d2
        bge     3b
        lea     -12(%a1),%a1
4:      subq.l  #1,%d0
        cmp.l   4(%a1),%d3
        bcc     6f                      | past that slice's end (a gap): show the frame
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
5:      move.l  %d0,le_idx
        move.l  %d0,-(%sp)
        move.l  (AED_SLOTID).l,-(%sp)
        move.l  (AED_TYPEID).l,-(%sp)
        jsr     (F_SLICESEL).l
        lea     12(%sp),%sp
        jsr     (F_REC).l               | the whole slice in view, start to end: the
        tst.l   %d0                     | editor's own fit, forced (flag 1: it zooms in
        beq     9f                      | too); the zoom on a later audition is kept
        move.l  %d0,%a0                 | (ZOOM KEEP, when in the remix). (8thmyth, H7: opening on the start
        move.l  le_idx,%d0            | alone left it too zoomed in)
        move.l  %d0,%d1
        add.l   %d1,%d1                 | 2n
        add.l   %d0,%d1                 | 3n
        lsl.l   #2,%d1                  | 12n
        move.l  %a0,%a1                 | (an index's displacement is 8 bits on ColdFire)
        add.l   %d1,%a1
        lea     REC_SLICES(%a1),%a1
        move.l  %d2,-(%sp)              | a quarter of the slice's length either side
        move.l  (%a1),%d0               | (8thmyth, H10: a bit further out)
        move.l  4(%a1),%d1
        move.l  %d1,%d2
        sub.l   %d0,%d2
        lsr.l   #2,%d2
        add.l   %d2,%d1                 | end + margin
        sub.l   %d2,%d0                 | start - margin, not below 0
        bcc     1f
        moveq   #0,%d0
1:      move.l  (%sp)+,%d2
        pea     1.w
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        pea     (AED_VIEW).l
        jsr     (F_VIEWFIT).l
        lea     16(%sp),%sp
9:      rts
6:      move.l  REC_TRIM_E(%a0),%d1     | no slice holds the frame: fit the frame +-
        sub.l   REC_TRIM_S(%a0),%d1     | 1/8 of the trim, so it sits mid-screen
        lsr.l   #3,%d1
        beq     8f
        move.l  %d3,%d0
        add.l   %d1,%d0
        cmp.l   REC_TRIM_E(%a0),%d0
        bls     7f
        move.l  REC_TRIM_E(%a0),%d0
7:      sub.l   %d1,%d3
        bcs     71f
        cmp.l   REC_TRIM_S(%a0),%d3
        bcc     72f
71:     move.l  REC_TRIM_S(%a0),%d3
72:     pea     1.w
        move.l  %d0,-(%sp)
        move.l  %d3,-(%sp)
        pea     (AED_VIEW).l
        jsr     (F_VIEWFIT).l
        lea     16(%sp),%sp
8:      movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts
        .equ    LE_TOL,     64              | frames (1.5 ms)
        .equ    AED_VIEW,   0x400ceb14      | the SLICE page's view
        .equ    F_VIEWFIT,  0x40077138      | (view, start, end, force): fit the range
        .equ    AED_PAGE,   0x460e5e5c      | the editor's page (0 TRIM, 1 SLICE, ...)
        .equ    AED_SLICEPG, 1
        .equ    AED_TYPEID, 0x46c8d1a0      | the editor's sample type and slot (0x40071668 checks them)
        .equ    AED_SLOTID, 0x46c8d19c
        .equ    F_SLICESEL, 0x40071668      | (type, slot, n): select slice n
        .equ    PART_VALS,  0x2a            | a Part's machine values (file 0x33, RAM = file - 9)
        .equ    PART_SETUP, 0x1da           | a Part's machine SETUP (file 0x1e3)

| grid TRIG hold (key, event): with the editor up (opened by [TRIG]+[BANK] on
| a held trig) the hold's lock popup would shut it, so the hold is dropped
le_trighold:
        tst.l   (AED_WIN).l
        bne     1f
        jmp     (F_TRIGKEY).l
1:      rts

        .data
        .balign 4
le_idx:         .long   0               | the slice selected
le_strt:        .long   0               | the held step's STRT
le_slic:        .long   0               | the track's SLIC
