| REC CS1 SKIP -- stock 0x4000432c, the recorder control-record update the
| write path calls about 1.5 times a recording track a frame, with its CS1
| writes skipped when CS1 already holds the value. The arithmetic is stock's,
| instruction for instruction (docs/firmware/RECORDER.md):
|
|   a1 = len, floored at 64 when non-zero; [0x46c938c4 + 44*id + 16] = a1
|   unless flag or len == 0: with r = 0x100d38f0 + 1096*id (CS1),
|     d2 = max(len, 0); d3 = min(max([r+300], 0), d2)
|     d1 = min(max(len, d3), d2);  a1 = min(max([r+308], d3), d1)
|     under 0x2700: [r+300] = d3, [r+304] = d1, [r+308] = a1
|     [r+296].b = 0; under 0x2700: [r+276] = [0x8000181c], [r+280] = -[0x80001820]
|
| CS1 is slow: about 0.5 us a read or a write on a MKII (a PC sampler on
| Bryan T's unit, 1 Nov 2026), and in steady play under the ColdFire port
| 358,300 of 358,316 of these writes stored the value already there.
|
| [r+300] and [r+308]: stock reads both for the arithmetic, so the write is
| skipped when the value read equals the new one, and CS1 ends as stock
| leaves it. Between the read and the write only a level-6 or level-7
| handler could store there, and none does (the port's writers of these
| fields are this routine, the write path, project load and the engine and
| arm tasks, none of which runs inside the frame interrupt).
|
| [r+276], [r+280], [r+296].b and [r+304]: RCS_MIRROR keeps a copy in DRAM,
| rcs_m[id] = {valid, 276, 280, 304, 296, turn}, for id 0..7 (any other id
| writes all four, as stock), and skips a write the copy says is already
| there. Other code also writes these fields (project load, the engine and
| arm tasks), so each call reads ONE of the four from CS1, in turn, and a
| mismatch drops the copy: that call writes all four again. A value another
| writer stores therefore stands for at most four calls of that track (about
| a millisecond at one call a frame) where stock would overwrite it at the
| next call. With RCS_MIRROR 0 only the [r+300]/[r+308] skips remain, and CS1
| is stock's after every call.
|
| tools/verify/verify_rec_cs1_skip.py runs this routine and stock's side by
| side and holds it to exactly that.
| SPDX-License-Identifier: MIT
        .set    RCS_MIRROR, 1                   | 0: only the two writes it reads for ([r+300], [r+308])
        .text
        .globl  rcs_update
| jmp'd in place of the routine's first two instructions: the whole routine.
| Args (C): id 4(sp), len 8(sp), flag 12(sp); d2-d5/a2-a3 saved here (stock
| saves d2-d3; the rest are this version's).
|
| RCS_MIRROR: the copy and its one check read a call (above). Under the port
| six other writers stored into these fields; a static search finds 87
| candidate stores at these offsets.
rcs_update:
        lea     -24(%sp),%sp
        movem.l %d2-%d5/%a2-%a3,(%sp)
        move.l  28(%sp),%d1                     | id
        movea.l 32(%sp),%a1                     | len
        tst.l   %a1
        beq.s   1f
        moveq   #64,%d0
        cmp.l   %a1,%d0
        ble.s   1f
        movea.w #64,%a1
1:      moveq   #44,%d0
        muls.l  %d1,%d0
        lea     0x46c938c4,%a0
        move.l  %a1,16(%a0,%d0.l)
        tst.l   36(%sp)                         | flag
        bne     9f
        tst.l   %a1
        beq     9f
        move.l  #1096,%d0
        muls.l  %d1,%d0
        movea.l %d0,%a0
        adda.l  #0x100d38f0,%a0
        move.l  %a1,%d2
        bge.s   2f
        clr.l   %d2
2:      move.l  300(%a0),%d1
        move.l  %d1,%d4                         | [r+300] as read
        move.l  %d1,%d0                         | max(d1, 0), as stock does it
        not.l   %d0
        add.l   %d0,%d0
        subx.l  %d0,%d0
        and.l   %d0,%d1
        move.l  %d2,%d3
        cmp.l   %d2,%d1
        bge.s   3f
        move.l  %d1,%d3
3:      move.l  %d3,%d1
        cmpa.l  %d3,%a1
        ble.s   4f
        move.l  %a1,%d1
4:      cmp.l   %d1,%d2
        bge.s   5f
        move.l  %d2,%d1
5:      movea.l 308(%a0),%a2                    | [r+308] as read
        move.l  %d3,%d0
        cmpa.l  %d3,%a2
        ble.s   6f
        move.l  %a2,%d0
6:      movea.l %d1,%a1
        cmp.l   %d1,%d0
        bge.s   7f
        movea.l %d0,%a1
| the copy: a3 = &rcs_m[id] for id 0..7, else 0; d2 = 1 when the copy is
| valid and the field read in turn still matches it, else 0
7:      suba.l  %a3,%a3
        moveq   #0,%d2
.if RCS_MIRROR
        move.l  28(%sp),%d0
        moveq   #8,%d5
        cmp.l   %d5,%d0
        bcc.s   20f                             | unsigned: 0..7 only
        move.l  %d0,%d5                         | id * 24
        lsl.l   #3,%d0
        lsl.l   #4,%d5
        add.l   %d5,%d0
        lea     rcs_m,%a3
        adda.l  %d0,%a3
        move.l  (%a3),%d2                       | valid
        move.l  20(%a3),%d5                     | turn
        addq.l  #1,20(%a3)
        moveq   #3,%d0
        and.l   %d0,%d5
        beq.s   11f
        subq.l  #1,%d5
        beq.s   12f
        subq.l  #1,%d5
        beq.s   13f
        moveq   #0,%d0                          | turn 3: [r+296].b
        move.b  296(%a0),%d0
        cmp.l   16(%a3),%d0
        bra.s   19f
11:     move.l  276(%a0),%d0
        cmp.l   4(%a3),%d0
        bra.s   19f
12:     move.l  280(%a0),%d0
        cmp.l   8(%a3),%d0
        bra.s   19f
13:     move.l  304(%a0),%d0
        cmp.l   12(%a3),%d0
19:     beq.s   20f
        moveq   #0,%d2                          | CS1 changed under the copy: write all four
20:
.endif
        move.w  %sr,%d0
        move.w  #0x2700,%sr
        cmp.l   %d4,%d3
        beq.s   71f
        move.l  %d3,300(%a0)
71:     tst.l   %d2
        beq.s   73f
        cmp.l   12(%a3),%d1
        beq.s   74f
73:     move.l  %d1,304(%a0)
        move.l  %a3,%d5
        beq.s   74f
        move.l  %d1,12(%a3)
74:     cmpa.l  %a2,%a1
        beq.s   72f
        move.l  %a1,308(%a0)
72:     move.w  %d0,%sr
        tst.l   %d2
        beq.s   75f
        tst.l   16(%a3)
        beq.s   76f
75:     clr.b   296(%a0)
        move.l  %a3,%d5
        beq.s   76f
        clr.l   16(%a3)
76:     move.w  %sr,%d0
        move.w  #0x2700,%sr
        move.l  0x8000181c,%d1
        tst.l   %d2
        beq.s   77f
        cmp.l   4(%a3),%d1
        beq.s   78f
77:     move.l  %d1,276(%a0)
        move.l  %a3,%d5
        beq.s   78f
        move.l  %d1,4(%a3)
78:     move.l  0x80001820,%d1
        neg.l   %d1
        tst.l   %d2
        beq.s   79f
        cmp.l   8(%a3),%d1
        beq.s   80f
79:     move.l  %d1,280(%a0)
        move.l  %a3,%d5
        beq.s   80f
        move.l  %d1,8(%a3)
80:     move.w  %d0,%sr
        move.l  %a3,%d5
        beq.s   9f
        moveq   #1,%d5
        move.l  %d5,(%a3)                       | the copy now matches CS1
9:      movem.l (%sp),%d2-%d5/%a2-%a3
        lea     24(%sp),%sp
        rts

        .bss
        .balign 4
| rcs_m[8]: {valid, [r+276], [r+280], [r+304], [r+296].b, turn}; zero at boot = not valid
rcs_m:  .space  8*24
