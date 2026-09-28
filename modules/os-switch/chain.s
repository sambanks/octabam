| OS SWITCH, the chainloader -- a ROM cave the OS entry detours into, at the
| first instruction after it parks the bootstrap's argument:
|
|   0x40000412  movea.l #0x48000000,%sp   ->  jmp osw_chain
|
| Nothing has run yet: no DSP upload (0x40001e50, the boot site), no cache
| set-up, no interrupts. If the mailbox at OSW_MBOX holds a switch the
| running image staged before it reset (switch.s), this copies the staged
| image over OS_ENTRY and calls it exactly as the bootstrap called us: the
| same argument on the stack, the same CACR. Otherwise it resumes the
| entry. Every refusal falls through to the normal boot -- never a hang --
| and leaves a status word for the next image's OS SWITCH row to show.
|
| The mailbox is cleared BEFORE the staged image runs: an image that hangs
| costs one reset, never a loop (a reset keeps SDRAM; the next boot finds
| no mailbox and boots this image).
|
| Runs from ROM (this cave is inside the image) until the copy, so the copy
| itself runs from a stub it places at OSW_STUB, outside the range it
| overwrites.

        .include "remix.inc"

        .text
        .global osw_chain
osw_chain:
        lea     (OSW_MBOX).l,%a1
        move.l  (MB_MAGIC,%a1),%d0
        cmpi.l  #OSW_MAGIC,%d0
        bne.w   nombox
        move.l  (MB_LEN,%a1),%d2
        move.l  (MB_HASH,%a1),%d3
        eor.l   %d2,%d0
        eor.l   %d3,%d0
        cmp.l   (MB_CHECK,%a1),%d0
        bne.w   nombox
        clr.l   (MB_MAGIC,%a1)          | one-shot, before anything below can fail
        tst.l   %d2
        beq.w   badsize
        cmpi.l  #OSW_MAXLEN,%d2
        bhi.w   badsize
        cmpi.l  #OS_VEROFF+2,%d2
        bcs.w   badsize
        | The entry of the staged image would compare its bootstrap version
        | with NOR's and, if newer, REPROGRAM THE BOOTSTRAP (0x4000f9b4) --
        | the recovery path. Only a staged image whose version is NOR's own
        | may run.
        lea     (OSW_IMG+OS_VEROFF).l,%a0
        mvz.w   (%a0),%d0
        mvz.w   (NOR_BOOTVER).w,%d1
        cmp.l   %d1,%d0
        bne.w   badver
        lea     (OSW_IMG).l,%a0
        move.l  %d2,%d0
        moveq   #0,%d1
hashloop:
        move.l  %d1,%d4
        lsl.l   #5,%d1
        add.l   %d4,%d1
        moveq   #0,%d4
        move.b  (%a0)+,%d4
        add.l   %d4,%d1
        subq.l  #1,%d0
        bne.s   hashloop
        cmp.l   %d3,%d1
        bne.w   badhash
        move.l  #ST_BOOT,%d0
        move.l  %d0,(MB_STATUS,%a1)
        | the stub, out of the way of the copy
        lea     stub(%pc),%a0
        lea     (OSW_STUB).l,%a2
        moveq   #(stub_end-stub)/2,%d0
stubcopy:
        move.w  (%a0)+,(%a2)+
        subq.l  #1,%d0
        bne.s   stubcopy
        move.l  (OS_ARGCELL).l,%d1      | the bootstrap's argument, read before it is overwritten
        lea     (OSW_IMG).l,%a0
        lea     (OS_ENTRY).l,%a2
        move.l  %d2,%d0
        jmp     (OSW_STUB).l

nombox:
        | "BOOT" in the status means the chainloader handed over on this
        | boot and this image is the one it handed to (a staged image that
        | carries OS SWITCH runs this cave too): keep that as "RUN ".
        move.l  (MB_STATUS,%a1),%d1
        move.l  #ST_NONE,%d0
        cmpi.l  #ST_BOOT,%d1
        bne.s   1f
        move.l  #ST_RUN,%d0
        bra.s   1f
badsize:
        move.l  #ST_SIZE,%d0
        bra.s   1f
badver:
        move.l  #ST_BVER,%d0
        bra.s   1f
badhash:
        move.l  #ST_HASH,%d0
1:      move.l  %d0,(MB_STATUS,%a1)
resume:
        movea.l #0x48000000,%sp         | the displaced instruction
        jmp     (OS_RESUME).l

| The stub: a0 = stage, a2 = OS_ENTRY, d0 = length, d1 = the argument.
| Caches off and invalidated for the copy, then the bootstrap's own exit
| state, then the entry as the bootstrap calls it (bootstrap 0x2d3c:
| `move.l 0x8000050a,-(%sp) ; jsr 0x40000400`). Position-independent.
        .align  2
stub:
        move.l  #CACR_OFF,%d4
        movec   %d4,%cacr
        nop
copy:
        move.l  (%a0)+,(%a2)+
        subq.l  #4,%d0
        bgt.s   copy
        move.l  #CACR_BOOT,%d4
        movec   %d4,%cacr
        nop
        move.l  %d1,-(%sp)
        jsr     (OS_ENTRY).l
halt:
        bra.s   halt
stub_end:
