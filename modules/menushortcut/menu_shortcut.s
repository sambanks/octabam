| MAIN MENU -> the bus effects' own FX2 page  (ColdFire code cave, 3 Sep 2026)
|
| Two rows in the CONTROL submenu, REVERB and DELAY, whose action selects the
| track HOSTING that server and opens its EFFECT 2 SETUP window. The path is
| docs/MAINMENU.md section 7, traced end to end there:
|
|   0x80000012      non-zero = MIDI mode, where page kind 4 resolves track+8
|   0x460d1684      current page kind (long), byte mirror at 0x46c7d8d8
|   0x40064bc0      close MAIN MENU -- the full stock cleanup, and stock
|                   itself calls it from handler context ([NO])
|   0x40083bf8      select a track: clamps, writes both globals, tears down
|                   the old track, restages the page, redraws, moves the LED
|   0x4005996c      open EFFECT 2 SETUP (takes no arguments; toggles)
|
| WHICH TRACK. Not hardcoded: the handler scans the eight per-track FX2 id
| bytes at 0x80000ecc for the id it wants (7 = ChonVerb, 6 = BongDelay) and
| selects the one that matches. The base is 0x80000110 + track + 0xdbc, the
| same byte modules/tempo-sync/tempo_cave.s reads through its own hook.
| ⚠️ If that address is wrong the scan simply never matches, and the handler
| falls through to opening the CURRENT track's page -- wrong screen, not a
| crash. That degradation is the reason it scans rather than trusting.
|
| Only d0 is live on entry (the engine calls action(0)); d1, d2 and a0 are
| scratch.

        .text
hrev:   moveq   #7,%d0                  | ChonVerb's FX2 id
        bra.s   hcom
hdly:   moveq   #6,%d0                  | BongDelay's FX2 id
hcom:   tst.l   0x80000012              | MIDI mode? kind 4 would resolve
        bne.s   hout                    | track+8 -- bail, menu stays open
        moveq   #4,%d1
        move.l  %d1,0x460d1684          | current page kind = FX2
        move.b  %d1,0x46c7d8d8          | the byte mirror the key path writes
        lea     0x80000ecc,%a0          | the eight per-track FX2 id bytes
        moveq   #0,%d1                  | track index
hscan:  move.b  (%a0)+,%d2
        and.l   #0xff,%d2
        cmp.l   %d0,%d2
        beq.s   hfound
        addq.l  #1,%d1
        cmpi.l  #8,%d1
        blt.s   hscan
        moveq   #-1,%d1                 | not hosted anywhere: leave the
hfound: move.l  %d1,-(%sp)              | track selection alone
        jsr     0x40064bc0              | close the MAIN MENU first
        move.l  (%sp)+,%d1
        tst.l   %d1
        blt.s   hopen
        move.l  %d1,-(%sp)
        jsr     0x40083bf8              | select the host track
        addq.l  #4,%sp
hopen:  jsr     0x4005996c              | open EFFECT 2 SETUP
hout:   rts
