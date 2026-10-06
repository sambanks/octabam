| INPUT HOLD -- audio through the inputs keeps playing, at its level, while
| a project loads; the new project's own levels, tempo and Part take over
| when it is read, as stock.
|
| Stock, measured under the port (1.40C): every project load runs the
| settings reset 0x40025848 first. It writes the factory output block into
| the battery-backed copy (GAIN 64, DIR 0, MASTER_TRACK 0, PHONES_MIX 64...)
| and makes it live with memcpy(0x80000020 <- 0x100b1480, 0x4c) at
| 0x40025a86; it also sets 120 BPM and zeroes the current Part. The frame
| interrupt sends the live DIR bytes to the DSP every frame (0x4000d174,
| 0x4000d1b0), so the inputs are silent until project.work's [SETTINGS]
| parse stores the new levels, ~2 s later under the port.
|
| Here, while holding, the reset changes nothing audible (the live block,
| the tempo and the current Part stay), the current Part's data and the
| pickup's input routing survive the load (below), and [SETTINGS]/[STATES]
| then apply the new project's values as stock.
| - ih_prep_defaults (0x40025a80): the live block is written over the
|   defaults in the copy BEFORE the memcpy, so it never changes, not for
|   one frame.
| - ih_boot_restore (0x4001fb78): a power-up that restores the saved state
|   (measured with --cs1-in --no-post) has a valid live block at once.
|
| Live and saved bytes are in the same order: GAIN CD, GAIN AB, DIR CD, DIR AB.
| Assemble: m68k-elf-as -mcpu=5407 -o hold.o hold.s

        .set    LIVE_MIX,   0x8000002e  | GAIN_CD GAIN_AB DIR_CD DIR_AB, live
        .set    SAVED_MIX,  0x100b148e  | the same four, battery-backed copy
        .set    LIVE_GATE,  0x80000058  | GATE_AB GATE_CD INPUT_DELAY_COMPENSATION
        .set    SAVED_GATE, 0x100b14b8
        .set    MEMCPY,     0x40020898
        .set    BOOT_RESTORE, 0x40025770

        .text
        .global ih_boot_restore, ih_prep_defaults
        .global ih_isr_pick, ih_isr_keep, ih_part_applied
        .global ih_load_init, ih_part_init, ih_part_reset, ih_tempo_reset

| jsr from 0x4001fb78 (was: jsr 0x40025770). Returns to 0x4001fb7e through
| the stock routine's rts.
ih_boot_restore:
        move.l  %d0,-(%sp)
        moveq   #1,%d0
        move.b  %d0,ih_have
        move.l  (%sp)+,%d0
        jmp     BOOT_RESTORE

| jsr from 0x40025a80 (was: lea 0x40020898,%a2; the jsr (%a2) follows).
| Latches the hold for this load; a2 = memcpy as stock leaves it.
| While holding, every output setting the reset would make live is given its
| live value first, so the reset changes nothing audible:
|   0x2e..0x37  GAIN_CD GAIN_AB DIR_CD DIR_AB PHONES_MIX MAIN_TO_CUE
|               MASTER_TRACK MAIN_LEVEL CUE_LEVEL CUE_STUDIO_MODE
|   0x58..0x5a  GATE_AB GATE_CD INPUT_DELAY_COMPENSATION
| (reset values 64 64 0 0 64 0 0 64 64 0 / 127 127 0). All of them then take
| the new project's value when [SETTINGS] is read, once, as stock ends up.
| The first reset after boot (empty battery memory, 0x4001fb80) runs as
| stock -- the live block is not yet valid there -- and makes it valid; a
| power-up that restores the saved state (ih_boot_restore) is valid at once.
ih_prep_defaults:
        move.l  %d0,-(%sp)
        move.b  ih_have,%d0
        move.b  %d0,ih_hold
        beq.s   1f
        move.l  LIVE_MIX,%d0            | 0x2e..0x31
        move.l  %d0,SAVED_MIX
        move.l  LIVE_MIX+4,%d0          | 0x32..0x35
        move.l  %d0,SAVED_MIX+4
        move.w  LIVE_MIX+8,%d0          | 0x36..0x37
        move.w  %d0,SAVED_MIX+8
        move.w  LIVE_GATE,%d0           | 0x58..0x59
        move.w  %d0,SAVED_GATE
        move.b  LIVE_GATE+2,%d0         | 0x5a
        move.b  %d0,SAVED_GATE+2
        moveq   #1,%d0                  | the pickup words are held until
        move.b  %d0,ih_load             | the new part is applied
        clr.l   ih_ticks
1:      moveq   #1,%d0                  | from here on the live block is valid
        move.b  %d0,ih_have
        move.l  (%sp)+,%d0
        lea     MEMCPY,%a2
        rts

| jmp from 0x40025aaa (was: move.b d0,0x100b14cf; d0 = 0), in the reset:
| the current Part. Stock zeroes it with bank/pattern/track and copies the
| block live (0x40025ae8, 0x100b14cc -> 0x80000000, 0x16 B), so for the
| length of the load the engine plays Part A -- measured on a project with
| Part B current and T5 THRU on inputs C/D: 0x80000003 1 -> 0 at the reset, 0 -> 1 at the
| [STATES] parse, and the THRU path is gone in between (~3 dB on the unit).
| While holding, the Part in use stays; [STATES] PART= still sets the new
| project's.
ih_part_reset:
        tst.b   ih_hold
        bne.s   1f
        move.b  %d0,0x100b14cf          | displaced
1:      jmp     0x40025ab0

| jsr from 0x400258cc (was: jsr 0x4009c708 with `pea 0xb40` before it; the
| caller pops it at 0x40025a64): the reset's tempo, 120 BPM. Stock runs the
| load at 120 and sets the project's tempo from [SETTINGS] (that project under
| the port: track records' tempo word 0x0f78 -> 0x0b40 -> 0x0f78), so tempo-
| synced effects jump for the load. While levels are held (ih_have: ih_hold
| is latched later, at 0x40025a80), the tempo in use stays.
ih_tempo_reset:
        tst.b   ih_have
        bne.s   1f
        jmp     0x4009c708              | stock: its rts returns to the caller
1:      rts

| ---- the pickup's input monitoring ---------------------------------------
| Every frame the interrupt sends the active pickup track (0x461054f8) and
| its recorder input routing (records at 0x80000c94 + 12*track) in frame
| words +0x58/+0x5a/+0x5c -- but only while that track's machine in the
| current Part is PICKUP (type 4, Part +0x8eda2); otherwise 8/0/0, and the
| inputs stop passing through the track. A project load wipes the Parts at
| the reset and applies the new current Part only when its bank is read
| (0x400907e4, ~75 % of the bar on a unit): a track monitoring the inputs
| through a PICKUP drops out for that span (~3 dB on the unit with DIR AB
| also up). While ih_load is set, the interrupt resends the words it last
| sent; the part apply clears it (a 20 s ceiling in frames clears it too).

| jmp from 0x4000d206 (was: move.l 0x461054f8,%d1). a2 = the frame record.
| ih_load 1: loading (ceiling 55,000 frames, ~20 s). ih_load 2: the Part is
| applied but stock reads the active pickup track as none (> 7) for a few
| frames after it (measured: 6 -> 8 -> 6 across the apply); hold on until
| it is a track again, ceiling 2,000 frames (~0.7 s).
ih_isr_pick:
        tst.b   ih_load
        bne.s   1f
3:      move.l  0x461054f8,%d1          | displaced: stock computes them
        jmp     0x4000d20c
1:      addq.l  #1,ih_ticks             | d0/d1 are dead on the held path
        move.b  ih_load,%d0
        moveq   #2,%d1
        cmp.b   %d1,%d0
        bne.s   4f
        move.l  0x461054f8,%d1          | after the apply: a track again?
        moveq   #7,%d0
        cmp.l   %d1,%d0
        bcs.s   5f
        clr.b   ih_load                 | yes: stock from this frame
        bra.s   3b
5:      move.l  ih_ticks,%d0
        cmpi.l  #2000,%d0
        bra.s   6f
4:      move.l  ih_ticks,%d0
        cmpi.l  #55000,%d0              | ~20 s of 362.8 us frames
6:      bcs.s   2f
        clr.b   ih_load
        clr.b   ih_skipwipe
2:      move.l  ih_s58,%d0              | +0x58 track, +0x5a routing
        move.l  %d0,(88,%a2)
        move.w  ih_s5c,%d0              | +0x5c routing
        move.w  %d0,(92,%a2)
        jmp     0x4000d2a0              | d0 is reloaded there

| jmp from 0x4000d2a0 (was: movea.l 0x800000ec,%a0), the join of every path
| above: keep what was sent. d0 is dead here (reloaded at 0x4000d2a6).
ih_isr_keep:
        move.l  (88,%a2),%d0
        move.l  %d0,ih_s58
        move.w  (92,%a2),%d0
        move.w  %d0,ih_s5c
        movea.l 0x800000ec,%a0          | displaced
        jmp     0x4000d2a6

| jsr from 0x400907e4 (was: jsr 0x40009094, the current bank's Part apply
| inside the load's masked bank load). The arguments sit above our return
| address, so it is parked while the stock routine runs.
ih_part_applied:
        move.l  (%sp)+,ih_ret
        jsr     0x40009094
        clr.b   ih_skipwipe
        tst.b   ih_load
        beq.s   1f
        move.l  %d0,-(%sp)
        moveq   #2,%d0                  | hand over to the interrupt's
        move.b  %d0,ih_load             | after-apply hold
        clr.l   ih_ticks
        move.l  (%sp)+,%d0
1:
        move.l  ih_ret,-(%sp)
        rts

| ---- the current Part through LOAD PROJECT ------------------------------
| LOAD PROJECT (0x40085336) calls the empty-project init 0x400909d8 from
| 0x4008534c; its first step 0x4000fd34 -> 0x4000fc78 re-initialises the
| working bank at 0x400e21e0 -- 16 patterns, then each Part via 0x40005638 --
| and copies it to the other 15 slots. The current Part's machines (a THRU
| or PICKUP passing the inputs), levels and FX are gone until the bank file
| is read and the Part applied (0x400907e4). While a LOAD PROJECT holds, the
| init skips the CURRENT Part of the working bank (its live block; the saved
| copy at +0x9504a is initialised as stock): the Part keeps playing as it
| was until the bank file replaces it. A bank file that fails to load leaves
| that Part in the new project instead of an empty one.

| jsr from 0x4008534c (was: jsr 0x400909d8), LOAD PROJECT only.
ih_load_init:
        tst.b   ih_have
        beq.s   1f
        move.l  %d0,-(%sp)
        moveq   #1,%d0
        move.b  %d0,ih_skipwipe
        move.b  %d0,ih_load
        clr.l   ih_ticks
        move.b  0x100b14cf,%d0          | the Part being heard: the one kept,
        move.b  %d0,ih_part             | whatever the new project selects
        move.l  (%sp)+,%d0
1:      jsr     0x400909d8
        rts                             | the skip lasts until the Part apply:
                                        | the bank reader (0x4008e0e6) inits
                                        | the slot again before the file

| (measured 6 Oct 2026: the second init of the working bank, from the bank
| reader just before bank01.work is read, wiped the current Part as late as
| ~75 %; ih_part_applied and the interrupt's ceiling end the skip.)

| jmp from 0x4000fcd4 (was: pea (0,%a2,%d0.l) / jsr (%a4) = 0x40005638, the
| live Part block's init). Rejoins at 0x4000fcda; the pea stays on the stack
| either way (the caller pops it). d3 = Part index, a2 = bank base; d0 is
| dead after (0x4000fcda rebuilds from d2).
ih_part_init:
        pea     (0,%a2,%d0.l)
        tst.b   ih_skipwipe
        beq.s   1f
        cmpa.l  #0x400e21e0,%a2         | the working bank only
        bne.s   1f
        mvz.b   ih_part,%d0             | the Part current at the load's start
        cmp.l   %d3,%d0
        bne.s   1f
        jmp     0x4000fcda              | keep it
1:      jsr     0x40005638
        jmp     0x4000fcda

| State. The unit sits in the OS image in SDRAM, copied from flash at every
| boot, so all of it starts at 0.
        .even
ih_ret:   .long 0                       | ih_part_applied's return address
ih_ticks: .long 0                       | frames since the reset set ih_load
ih_s58:   .long 0                       | frame words +0x58/+0x5a last sent
ih_s5c:   .word 0                       | frame word +0x5c last sent
ih_have: .byte  0                       | 1: levels are established, hold them
ih_hold: .byte  0                       | this load's latch (ih_have at the reset)
ih_load: .byte  0                       | 1: between the reset and the Part apply
ih_skipwipe: .byte 0                    | 1: LOAD PROJECT, until the Part apply
ih_part: .byte  0                       | the Part kept (current at the load)
        .even
