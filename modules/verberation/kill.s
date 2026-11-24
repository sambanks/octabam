| VERBERATION -- the stop kill reaches VERBERATION and its rows as it reaches the
| stock reverbs.
|
| Stock 0x40004d0c, in the frame's DSP-record pass (0x40004bd4): for a track
| whose bit is set in the kill mask 0x8000184b (all eight from stop-and-rewind,
| 0x400a10fc; one cleared when its track triggers again), an FX2 id of 0x14..0x16
| (PLATE, SPRING, DARK REV) gets slot A, slot F and slot 11 (record +24, +34,
| +53) zeroed every frame. VERBERATION uses every slot, and 0 is a value each
| of those can hold, so a track on VERBERATION's id or on one of its rows (VERB
| PLATE, ROOM and HALL take 0x14..0x16 in octabam-verbs) gets MODE's knob field
| (slot 6, record +48: x:(r6+$c) bits 16-23) set to 127 instead, a value MODE
| (four values) never has; the stock zeroing is skipped. verberation.asm cuts to
| dry and clears its tank and state while it reads 127.

        .include "remix.inc"                    | VB_IDS: the ids this remix gave VERBERATION and its rows
        .text
        .globl  vb_kill

vb_kill:
        mvz.w   56(%a2),%d0                     | the track's FX2 id
        VB_IDS                                  | beq.s 2f on each of VERBERATION's ids
        add.l   #-20,%d0                        | displaced: addil #-20,%d0
        jmp     0x40004d16                      | stock: the reverbs' range test
2:      moveq   #0x7f,%d1
        move.b  %d1,48(%a2)                     | MODE = 127: the kill's mark
        jmp     0x40004d2e
