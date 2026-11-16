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

        .data
        .balign 4
zk_p:           .long   0               | the pointer F_VIEWSHOW reads
