| BBD -- the stop kill reaches BBD as it reaches the stock reverbs.
|
| Stock 0x40004d0c, in the frame's DSP-record pass (0x40004bd4): for a track
| whose bit is set in the kill mask 0x8000184b (all eight from stop-and-rewind,
| 0x400a10fc; one cleared when its track triggers again), an FX2 id of 0x14..0x16
| (PLATE, SPRING, DARK REV) gets slot A, slot F and slot 11 (record +24, +34,
| +53) zeroed every frame. BBD's id joins with slot 11 only: BBD's hidden
| slot 11 is 127 otherwise, and 0 there makes it cut to dry and clear its
| line (bbd.asm).

        .text
        .globl  bbd_kill

bbd_kill:
        mvz.w   56(%a2),%d0                     | the track's FX2 id
        moveq   #BBD_ID,%d1                     | the manifest's fx2_id
        cmp.l   %d1,%d0
        bne.s   1f
        clr.b   53(%a2)                         | BBD: slot 11 = 0
        jmp     0x40004d2e
1:      add.l   #-20,%d0                        | displaced: addil #-20,%d0
        jmp     0x40004d16                      | stock: the reverbs' range test
