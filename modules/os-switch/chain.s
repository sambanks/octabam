| OS SWITCH, the chainloader's gate -- a ROM cave the OS entry detours into,
| at the first instruction after it parks the bootstrap's argument:
|
|   0x40000412  movea.l #0x48000000,%sp   ->  jmp osw_chain
|
| Nothing has run yet: no DSP upload (0x40001e50, the boot site), no cache
| set-up, no interrupts. The gate is as small as it can be, because ROM
| caves are what full remixes run out of (bottleservice-ret: MODULATION's
| label formatters did not fit beside the whole chainloader, 29 Sep 2026).
| It only decides: with a mailbox, it spends it -- BEFORE anything else,
| so an image that hangs costs one reset, never a loop (a reset, even a
| quick power-cycle, keeps SDRAM) -- checks that the chainloader's body
| the switcher placed at OSW_BODY is whole (its longs sum to MB_BODYSUM),
| and runs it; the body (osw_body in switch.s) checks the stage and hands
| over, or comes back to `resume`. Without one it records the boot for OS
| SWITCH's list and resumes the entry. Every refusal falls through to the
| normal boot -- never a hang.

        .include "remix.inc"

        .text
        .global osw_chain
osw_chain:
        .if     TRACE
        | BOOT TRACE's note 1 (modules/boot-trace), inline: this cave
        | cannot rely on another cave's symbols
        move.l  #0x90,%d1
        bsr.w   txmidi
        moveq   #1,%d1
        bsr.w   txmidi
        moveq   #0x7f,%d1
        bsr.w   txmidi
        .endif
        lea     (OSW_MBOX).l,%a1
        move.l  (MB_MAGIC,%a1),%d0
        cmpi.l  #OSW_MAGIC,%d0
        bne.s   nombox
        clr.l   (MB_MAGIC,%a1)          | one-shot, before anything below can fail
        move.l  (MB_BODYLEN,%a1),%d1
        beq.s   badbody
        cmpi.l  #OSW_BODYMAX,%d1
        bhi.s   badbody
        lea     (OSW_BODY).l,%a0
        moveq   #0,%d2
1:      add.l   (%a0)+,%d2
        subq.l  #1,%d1
        bne.s   1b
        cmp.l   (MB_BODYSUM,%a1),%d2
        bne.s   badbody
        lea     osw_resume(%pc),%a2     | where the body comes back to on a refusal
        jmp     (OSW_BODY).l            | a1 = the mailbox
badbody:
        move.l  #ST_HASH,%d0
        bra.s   2f
nombox:
        | "BOOT" in the status means the chainloader handed over on this
        | boot and this image is the one it handed to (a staged image that
        | carries OS SWITCH runs this cave too): keep that as "RUN ".
        move.l  (MB_STATUS,%a1),%d1
        move.l  #ST_NONE,%d0
        cmpi.l  #ST_BOOT,%d1
        bne.s   2f
        move.l  #ST_RUN,%d0
2:      move.l  %d0,(MB_STATUS,%a1)
        .global osw_resume
osw_resume:
        .if     TRACE
        | BOOT TRACE's note 12: back to the entry (velocity: the status's last byte)
        lea     (OSW_MBOX).l,%a1
        move.l  #0x90,%d1
        bsr.w   txmidi
        moveq   #12,%d1
        bsr.w   txmidi
        move.l  (MB_STATUS,%a1),%d1
        andi.l  #0x7f,%d1
        bsr.w   txmidi
        .endif
        movea.l #0x48000000,%sp         | the displaced instruction
        jmp     (OS_RESUME).l

        .if     TRACE
txmidi:
        move.l  #200000,%d2
1:      move.b  (0xfc060004).l,%d0
        btst    #2,%d0
        bne.s   2f
        subq.l  #1,%d2
        bne.s   1b
2:      move.b  %d1,(0xfc06000c).l
        rts
        .endif
