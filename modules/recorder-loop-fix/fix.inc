| RECORDER LOOP FIX's hold fixup, included by each hook stub.
| In:  d0/d1 = what the voice's fetch (the (-68,fp) function) returned for
|      index a0: d0 = sample address, d1 = samples there (negative: reverse).
|      Past the recording no block is mapped: d0 = the pool base 0x40a955e0.
| Out: for a recorder-buffer voice (+0x15 negative) fetching forward at
|      exactly END (+0x64) and getting the pool base, d0 = the address of
|      END - 1 and d1 = 1, so the copy repeats the last sample once.
|      Otherwise d0/d1 unchanged.
| Preserves every register but d0/d1/a0; a1 is saved across the fetch call.
fix:    cmpi.l  #ARENA_BASE,%d0
        bne     fixret                  | a mapped block
        tst.l   %d1
        ble     fixret                  | nothing there, or reverse play
        tst.b   (21,%a2)
        bge     fixret                  | not a recorder buffer
        cmpa.l  (100,%a2),%a0
        bne     fixret                  | not index END
        subq.l  #1,%a0
        move.l  %a0,%d0
        bmi     fixnull
        move.l  %d1,-(%sp)              | the stock count, for the fallback
        move.l  %a1,-(%sp)
        move.l  %d0,-(%sp)
        move.l  %a2,-(%sp)
        movea.l (-68,%fp),%a0
        jsr     (%a0)                   | fetch END - 1
        addq.l  #8,%sp
        movea.l (%sp)+,%a1
        cmpi.l  #ARENA_BASE,%d0
        beq     fixback                 | END - 1 unmapped too: stock
        tst.l   %d1
        ble     fixback
        addq.l  #4,%sp                  | drop the saved count
        moveq   #1,%d1                  | one sample: the last one, again
        rts
fixback: move.l (%sp)+,%d1
fixnull: move.l #ARENA_BASE,%d0
fixret: rts
