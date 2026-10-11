| RECORDER LOOP FIX hold, the crossfade copy's guard -- hooked at 0x400085d8 (sub.l
| d0,d5 / cmp.l d2,d5 / bge.s), where the crossfade copy caps a voice reading
| the buffer its own recorder is writing at END - the further of its two read
| positions (+0x48, +0x4c). At END the cap is 0 and stock stops the voice
| (0x40008722). Here, at exactly END, with both reads forward and +0x17
| clear, the read at END takes END - 1 instead (a3 for +0x48, d7 for +0x4c)
| and the copy runs one sample. Otherwise, or when END - 1 has no sample,
| stock.
| In: d5 = END, d0 = the further position, d2 = count so far, d4/d1 = the
| two fetches' counts (sign = direction), a3/d7 = their addresses. Rejoins
| at 0x400085e0 (tst.l d2).
| Assemble: m68k-elf-as -mcpu=5475 -o hold_xguard.o hold_xguard.s
        .text
        .globl  rlf_hold_xguard
rlf_hold_xguard:
stub:   addq.l  #4,%sp                  | the return address: rejoin below
        sub.l   %d0,%d5                 | displaced: samples before END
        cmp.l   %d2,%d5
        bge     capped
        move.l  %d5,%d2                 | displaced (0x400085de)
capped: tst.l   %d2
        bgt     done
        tst.l   %d5
        bne     done                    | past END: stock
        tst.l   %d4
        ble     done                    | reverse play
        tst.l   %d1
        ble     done
        tst.b   (23,%a2)
        bne     done                    | the wrapping layout: stock
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
        move.l  (100,%a2),%d5
        cmp.l   (72,%a2),%d5
        bne     notA
        movea.l %d0,%a3                 | +0x48 at END: its last sample
notA:   cmp.l   (76,%a2),%d5
        bne     notB
        move.l  %d0,%d7                 | +0x4c at END: its last sample
notB:   moveq   #1,%d2                  | one sample, again
back:   move.l  (%sp)+,%d1
done:   jmp     0x400085e0
