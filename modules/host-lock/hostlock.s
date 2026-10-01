| HOST LOCK -- the FX2 chooser changes nothing on T1 and T5, the rig's host
| tracks, so their bus server stays.
|
| RIG HOSTS puts BusDelay on T1's FX2 and BusVerb on T5's; the two engines
| are hidden (no chooser row), so a pick there replaced the server with no
| way back on the unit (RIGPF7BP, 30 Sep 2026). The FX2 chooser's input
| layer has a record per key, 0x1a bytes apart: RIGHT 0x400bc356, YES
| 0x400bc370 (handler word 0x400bc374 = 0x40052474, the stock FX2 machine
| select, whose head Octakit's recipe turns into a jump to her wrapper), NO
| 0x400bc38a (handler 0x4003d440, the chooser closed unchanged). The YES
| word is repointed here (a SymbolRef, stock value asserted): on T1 or T5
| YES does what NO does; on any other track it is the YES it was. Both
| handlers are entered the same way (the dispatch at 0x4003191c pushes d2
| and d4 and calls through a0), so a jump keeps the stack and return as the
| dispatch made them. Every register is preserved.

        .set    TRACK,     0x100b14cc   | the current track, 0 = T1 (Octakit's GK_STOCK_CURRENT_TRACK_PRIMARY)
        .set    YES_FX2,   0x40052474   | the chooser's YES: select the row
        .set    NO_FX2,    0x4003d440   | the chooser's NO: close, nothing changed

        .text
        .global hl_yes
hl_yes:
        move.l  %d0,-(%sp)
        moveq   #0,%d0
        move.b  (TRACK).l,%d0
        beq.s   1f                      | T1: BusDelay's host
        subq.l  #4,%d0
        beq.s   1f                      | T5: BusVerb's host
        move.l  (%sp)+,%d0
        jmp     (YES_FX2).l
1:      move.l  (%sp)+,%d0
        jmp     (NO_FX2).l
