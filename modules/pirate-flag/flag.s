| PIRATE FLAG -- the OS's boot animation, replaced by a waving Jolly Roger.
|
| The boot animation (0x400559c6..0x40055b7a, the LED/key-scan task; the
| port's Rtos::Quirks::skipBootLogo names it) runs 560 frames on DTIM3's
| clock: clear the surface (d6), draw the stock sprite field, flush with
| `jsr 0x40013abc` at 0x40055aa2, fade the LEDs. That jsr is detoured here:
| every frame, the flag replaces what stock drew, then the flush runs as
| before. d2 is the frame number there (0..559: 0x40055b72 sets it, nothing
| between 0x40055a24 and the flush writes it); d6 the surface, whose +12 is
| the plane (docs/firmware/PANEL.md section 1).
|
| The cloth waves: column x from the cloth's first column on is moved down
| by 32 sin((x - frame) * 2 pi / 64) x (x - CLOTH) / 1200 rows, so the hoist is
| still and the fly swings up to about three rows. The art is art.py's,
| generated per build into remix.inc (FLAG_COLUMNS, SIN64).
|
| It is the OS image's animation, so a switched-to image shows its own:
| DOOM.OBI shows the flag after an OS SWITCH, a flashed image with this
| module at every power-on. What the bootstrap in NOR draws before the OS
| runs (the logo and the version line) is not the OS's and does not change.

        .include "remix.inc"

        .set    FLUSH, 0x40013abc
        .text
        .global pirate_frame
pirate_frame:
        lea     (-20,%sp),%sp
        movem.l %d2-%d5/%a2,(%sp)
        movea.l %d6,%a0
        movea.l (12,%a0),%a1           | the plane
        lea     pirate_cols,%a2
        moveq   #0,%d3                 | x
1:      move.l  (%a2)+,%d0             | the column: rows 0..31 in d0, 32..63 in d1
        move.l  (%a2)+,%d1
        moveq   #CLOTH,%d4
        cmp.l   %d4,%d3
        blt.s   4f                     | the pole: still
        | k = sin64[(x - frame) & 63] * (x - CLOTH) / 36, in rows
        move.l  %d3,%d4
        sub.l   %d2,%d4
        moveq   #63,%d5
        and.l   %d5,%d4
        lea     pirate_sin,%a0
        move.b  (%a0,%d4.l),%d4
        extb.l  %d4                    | -32..32
        move.l  %d3,%d5
        subi.l  #CLOTH,%d5
        muls.l  %d5,%d4
        move.l  #1200,%d5              | 32 x 111 / 1200: about +-3 rows at the fly
        divs.l  %d5,%d4
        tst.l   %d4
        beq.s   4f
        bmi.s   3f
        | k > 0: the 64-bit column shifted right k bits (towards the top row)
2:      lsr.l   #1,%d1
        btst    #0,%d0
        beq.s   21f
        bset    #31,%d1
21:     lsr.l   #1,%d0
        subq.l  #1,%d4
        bne.s   2b
        bra.s   4f
        | k < 0: shifted left (towards the bottom row)
3:      lsl.l   #1,%d0
        btst    #31,%d1
        beq.s   31f
        bset    #0,%d0
31:     lsl.l   #1,%d1
        addq.l  #1,%d4
        bne.s   3b
4:      move.l  %d0,(%a1)+
        move.l  %d1,(%a1)+
        addq.l  #1,%d3
        cmpi.l  #128,%d3
        blt.s   1b
        | frame 280, mid-animation, kept for verify_pirateflag (the port's
        | plane dump comes long after the animation has gone)
        cmpi.l  #280,%d2
        bne.s   5f
        movea.l %d6,%a0
        movea.l (12,%a0),%a0
        lea     pirate_snap,%a1
        move.l  #256,%d0
6:      move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.s   6b
5:      movem.l (%sp),%d2-%d5/%a2
        lea     (20,%sp),%sp
        jmp     (FLUSH).l              | the flush stock called, returning to it

        .align  2
pirate_cols:
        FLAG_COLUMNS
pirate_sin:
        SIN64
        .align  2
        .global pirate_snap
pirate_snap:
        .space  1024
