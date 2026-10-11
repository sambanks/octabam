| RECORDER LOOP FIX hold, the plain copy's guard -- hooked at 0x40008716 (suba.l d0,a1
| / cmpa.l d2,a1 / bge.s), where the copy caps a voice reading the buffer its
| own recorder is writing (+0x14 = 1, recorder position +0x34 past END) at
| END - index. At index END the cap is 0: stock stops the voice (0x40008722)
| and zero-fills the rest of the frame (0x4000872c). Here, at exactly END,
| the copy takes one sample from END - 1 instead (d3 = its address, d2 = 1).
| Past END, or when END - 1 has no sample, stock.
| In: a1 = END, d0 = index, d2 = count so far, d1 = the fetch's count (sign
| = direction), d3 = the fetched address. Rejoins at 0x4000871e (tst.l d2).
| Assemble: m68k-elf-as -mcpu=5475 -o hold_guard.o hold_guard.s
        .text
        .globl  rlf_hold_guard
rlf_hold_guard:
stub:   addq.l  #4,%sp                  | the return address: rejoin below
        suba.l  %d0,%a1                 | displaced: samples before END
        cmpa.l  %d2,%a1
        bge     capped
        move.l  %a1,%d2                 | displaced (0x4000871c)
capped: tst.l   %d2
        bgt     done
        cmpa.l  #0,%a1
        bne     done                    | past END: stock
        tst.l   %d1
        ble     done                    | reverse play
        move.l  (100,%a2),%d0
        subq.l  #1,%d0
        bmi     done
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        move.l  %a2,-(%sp)
        movea.l (-68,%fp),%a0
        jsr     (%a0)                   | fetch END - 1
        addq.l  #8,%sp
        cmpi.l  #ARENA_BASE,%d0
        beq     back                    | END - 1 unmapped: stock
        tst.l   %d1
        ble     back
        move.l  %d0,%d3                 | the last sample's address
        moveq   #1,%d2                  | one sample: the last one, again
back:   move.l  (%sp)+,%d1
done:   jmp     0x4000871e
