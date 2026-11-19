| ZOOM KEEP -- one DRAM unit. GNU as, ColdFire (m68k-elf-as -mcpu=54455). (8thmyth, Nov 2026)
|
| The audio editor keeps its zoom when a slice is auditioned. Stock's slice
| select (0x40071668: a trig in SLICES trig mode picks a slice in the editor)
| calls the view fit 0x40077138(view, start, end, 0), which zooms the SLICE
| page out until the whole slice fits: zoomed in on a marker, every audition
| threw the zoom away. zk_fitkeep stands in for that call (a jsr detour at
| 0x40071712) and only scrolls the slice start into view with the editor's
| own 0x40077004(view, &&frame); it returns 1 ("handled"), so the caller
| skips its own two scrolls.

        .text
        .global zk_fitkeep
zk_fitkeep:
        lea     8(%sp),%a0              | &start (the argument)
        move.l  %a0,zk_p
        pea     zk_p
        move.l  8(%sp),-(%sp)           | view
        jsr     (F_VIEWSHOW).l
        addq.l  #8,%sp
        moveq   #1,%d0
        rts
        .equ    F_VIEWSHOW, 0x40077004  | (view, &&frame): scroll the frame into view, zoom kept

| ---- every page keeps its zoom across tracks (8thmyth, 16 Nov 2026) --------
| Loading a sample into the editor (opening it, or a track key inside it)
| re-fits every page's view to the whole sample with the fit
| 0x40077138(view, start, end, force): TRIM's view 0x400ce724 (jsr at
| 0x4006f87c), SLICE's 0x400ceb14 (0x40071b38) and EDIT's 0x400cef60
| (0x40074110, 0x40074216); measured under the port on the T8 image. None of
| the four callers reads the result. zk_loadkeep stands in for those calls:
| a view that has been fitted once since power-on (frames a pixel, +0x10,
| not 0) keeps its zoom and its first frame (+0x18), the same place in time;
| only a first frame that would leave the screen past the sample's end, or
| before its start, is moved (the end at the right edge; a sample shorter
| than the screen from its start). The margins are the fit's own: the screen
| is (width +0x08 - 24) pixels and the fit starts 10 pixels before `start`.
| A view not yet fitted since power-on gets stock's fit (a bit per view in
| zk_seen: the views hold a default zoom of 3 at boot, measured, so their own
| fields cannot tell).
| LOCK EDIT positions the SLICE view itself after its open, as before.
        .global zk_loadkeep
zk_loadkeep:
        move.l  4(%sp),%a0              | view
        move.l  %a0,%d0
        lsr.l   #2,%d0                  | a bit per view: (view >> 2) & 31 (TRIM 9, SLICE 5, EDIT 24)
        moveq   #31,%d1
        and.l   %d1,%d0
        moveq   #1,%d1
        lsl.l   %d0,%d1
        move.l  zk_seen,%d0
        and.l   %d1,%d0
        bne     1f
        or.l    %d1,zk_seen             | first load since power-on: stock's fit
        jmp     (F_VIEWFIT).l           | the arguments in place
1:      move.l  16(%a0),%d0             | frames a pixel
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        move.l  8(%a0),%d1
        sub.l   #24,%d1                 | the screen in pixels, as the fit counts it
        muls.l  %d0,%d1                 | the screen in frames
        move.l  %d0,%d2
        moveq   #-10,%d3
        muls.l  %d3,%d2                 | -10 pixels in frames: the fit's left margin
        move.l  20(%sp),%d3             | start
        add.l   %d2,%d3                 | lowest first frame
        move.l  24(%sp),%d4             | end
        sub.l   %d2,%d4
        sub.l   %d1,%d4                 | highest first frame: the end 10 pixels in from the right
        move.l  24(%a0),%d0             | first frame now (the previous track's)
        cmp.l   %d4,%d0
        ble     2f
        move.l  %d4,%d0
2:      cmp.l   %d3,%d0
        bge     3f
        move.l  %d3,%d0
3:      move.l  %d0,24(%a0)
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        moveq   #1,%d0
        rts
        .equ    F_VIEWFIT,  0x40077138  | (view, start, end, force): fit the range

        .data
        .balign 4
zk_p:           .long   0               | the pointer F_VIEWSHOW reads
zk_seen:        .long   0               | a bit per editor view fitted since power-on
