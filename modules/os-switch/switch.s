| OS SWITCH, the switcher -- a CONTROL row that boots an OS image from the
| card without writing the flash.
|
|   MAIN MENU > CONTROL > OS SWITCH   (a seventh row, after METRONOME)
|
| [YES] on the row lists the card root's `.OBI` files (the stock directory
| scan OS UPGRADE uses for `.BIN`, 0x4007f598) and offers the first in the
| stock confirm dialog (0x4006d57c, OS UPGRADE's): YES boots it, NO offers
| the next. YES stops playback exactly as OS UPGRADE's does (0x40063660)
| and defers the load to the UI task through the same queue; the load
| runs OS UPGRADE's pre-flash sequence (stop, sync the project, wait for
| the card to go idle: 0x40080444..0x40080480), reads the file into the
| stage, writes the mailbox and resets the unit the way OS UPGRADE does
| after it flashes (interrupts masked, the panel queue flushed, spin:
| 0x4007fe6c..0x4007fe7c). The chainloader (chain.s) takes it from there.
|
| An `.OBI` is the raw image the bootstrap would depack to 0x40000400:
| `out/mainos_bus.bin` of any build, or the stock MAIN OS itself
| (`make obi`). It is checked here before anything is stopped for good:
| the OS entry's first instruction, a length that fits the stage, and the
| bootstrap version word equal to NOR's.
|
| The reset: stock never resets itself after OS UPGRADE (its last screen
| is "UPGRADE DONE / PLEASE REBOOT!", then it spins until a power-cycle),
| so this requests a soft reset through the reset controller (RCR
| SOFTRST, 0xfc0a0000 bit 7, MCF54455 RM). MEASURED on an MKII, 29 Sep
| 2026 (build 1): a bare soft reset brings the bootstrap back, and the
| boot then hangs on the OCTABAM screen with the keys dimmer than at
| power-on. The panel controller is not reset with the ColdFire, and the
| bootstrap's first exchange (0x128: send `60 00`, then block with no
| timeout until the panel reports key rows 0x25..0x27) never completes.
| So on an MKII the panel is first sent `60 02`, the command the OS's own
| loader handshake (0x4001f4dc) opens with at every boot, which puts it in
| its start-up state; the bootstrap's `60 00` then finds it as a power-on
| does (INFERRED from the bootstrap and the OS's handshake; build 3 tests
| it). An MKI's panel gets no handshake from the OS and is left alone.

        .include "remix.inc"

        .set    DIRSCAN,   0x4007f598   | (dir, table, ext, 0, 0) -> count; OS UPGRADE's
        .set    DIRTAB,    0x46c8d1b8   | its table: 12-byte records {name*, is_dir, -}
        .set    DIALOG,    0x4006d57c   | (title, nlines, lines*, 3, callback(answer: 0 = YES))
        .set    MESSAGE,   0x4005a2b8   | (text, 0x60): the popup OS UPGRADE reports errors with
        .set    DEFER,     0x40000c3c   | (queue, record {byte 21, long fn}): run fn in the UI task
        .set    UIQUEUE,   0x460d17ce
        .set    PLAYING,   0x400448dc
        .set    FS_OPEN,   0x46c8242a   | FS vtable slots (docs/firmware/STORAGE.md)
        .set    FS_CLOSE,  0x46c82422
        .set    FS_SIZE,   0x46c8241e
        .set    FS_READ,   0x46c82426   | (fd, buf, sectors)
        .set    STR_R,     0x400b3289   | "r"
        .set    STR_SLASH, 0x400b36a6   | "/"
        .set    STR_IOERR, 0x400b767e   | "IO ERROR"
        .set    STR_NOTOS, 0x400b7694   | "NOT A VALID OS FILE"
        .set    STR_WAIT,  0x400b68c2   | "WAIT"
        .set    STR_PLAY1, 0x400b5815   | "PLAYBACK WILL BE"
        .set    OS_FIRST,  0x4fefffe4   | the entry's `lea (-28,%sp),%sp`
        .set    UART1_FLUSH, 0x40010a4c
        .set    RCR,       0xfc0a0000
        .set    UART1_USR, 0xfc064004   | the panel link: bit 3 = TXEMP (the bootstrap's putc, 0x20)
        .set    UART1_UTB, 0xfc06400c
        .set    MKII_FLAG, 0x46c8d18c   | 1 on an MKII (docs/firmware/PANEL.md 4c)
        .set    HI08_CVR,  0x20000004   | the host command register: bit 7 HC, bits 6..0 the vector / 2
        .set    DSP_SELECT, 0xfc0a400c  | which core's host port the window shows (0, 1): the upload's own
        .set    PARK_HC,   0x0092       | HC | $12: vector P:$24, dsp_park.asm's osw_dsp
        .set    NMAX, 32                | .OBI files listed
        .set    NLEN, 24                | bytes kept of each name

        .text

| ---- the CONTROL rows: stock's six, from the user's own image, then ours ----
        .global osw_rows
        .align  4
osw_rows:
        CONTROL_ROWS                    | remix.inc: .incbin of 0x400cc5a8, 6 x 0x18
        .long   osw_label, 0, osw_action, 0, 0, 0
osw_label:
        .asciz  "OS SWITCH"
str_title:
        .asciz  "OS SWITCH"
str_obi:
        .asciz  "OBI"
str_none:
        .asciz  "NO .OBI FILES ON THE CARD"
str_boot:
        .asciz  "BOOT "
str_next:
        .asciz  "NO: NEXT FILE  "
str_now:
        .asciz  "NOW: "
str_flashed:
        .asciz  "NOW: THE FLASHED OS"
str_hash:
        .asciz  "LAST: STAGE LOST (HASH)"
str_bver:
        .asciz  "LAST: WRONG BOOTSTRAP"
str_size:
        .asciz  "LAST: BAD SIZE"
str_bootver:
        .asciz  "OTHER BOOTSTRAP VERSION"
str_spin:
        .asciz  " (SPIN)"
str_rcr:
        .asciz  " (RCR)"
        .align  2

| ---- row action: scan, offer the first ----------------------------------
        .global osw_action
osw_action:
        lea     (-8,%sp),%sp
        movem.l %d2/%a2,(%sp)
        clr.l   -(%sp)
        clr.l   -(%sp)
        pea     str_obi
        pea     (DIRTAB).l
        pea     (STR_SLASH).l
        jsr     (DIRSCAN).l
        lea     (20,%sp),%sp
        | keep the files, drop the directories: names into our own list
        lea     (DIRTAB).l,%a2
        lea     names,%a1
        moveq   #0,%d2                  | files kept
        move.l  %d0,%d1
        ble.s   2f
1:      tst.l   (4,%a2)
        bne.s   3f
        cmpi.l  #NMAX,%d2
        bcc.s   3f
        move.l  (%a2),%a0
        move.l  %d2,%d0
        mulu.w  #NLEN,%d0
        lea     (%a1,%d0.l),%a0
        move.l  (%a2),-(%sp)
        move.l  %a0,-(%sp)
        bsr.w   strcpy24
        addq.l  #8,%sp
        lea     names,%a1
        addq.l  #1,%d2
3:      lea     (12,%a2),%a2
        subq.l  #1,%d1
        bne.s   1b
2:      move.l  %d2,count
        clr.l   idx
        tst.l   %d2
        bne.s   4f
        pea     (0x60).w
        pea     str_none
        jsr     (MESSAGE).l
        addq.l  #8,%sp
        bra.s   5f
4:      bsr.w   offer
5:      movem.l (%sp),%d2/%a2
        lea     (8,%sp),%sp
        rts

| ---- the dialog for names[idx] --------------------------------------------
offer:
        lea     (-8,%sp),%sp
        movem.l %d2/%a2,(%sp)
        | line 1: "BOOT <name>?"
        lea     line1,%a2
        clr.b   (%a2)
        pea     str_boot
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        bsr.w   curname
        move.l  %a0,-(%sp)
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        pea     str_q
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        | line 2: "NO: NEXT FILE  i/N"
        lea     line2,%a2
        clr.b   (%a2)
        pea     str_next
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        move.l  idx,%d0
        addq.l  #1,%d0
        bsr.w   putnum
        move.b  #'/',(%a0)+
        clr.b   (%a0)
        move.l  count,%d0
        lea     line2,%a2
        bsr.w   putnum
        | line 3: what is running, from the chainloader's status word
        bsr.w   statusline
        pea     osw_answer
        pea     (3).w
        pea     lines
        pea     (3).w
        pea     str_title
        jsr     (DIALOG).l
        lea     (20,%sp),%sp
        movem.l (%sp),%d2/%a2
        lea     (8,%sp),%sp
        rts
str_q:
        .asciz  "?"
        .align  2

| a0 = names[idx]
curname:
        move.l  idx,%d0
        mulu.w  #NLEN,%d0
        lea     names,%a0
        lea     (%a0,%d0.l),%a0
        rts

| append the decimal d0 (0..99) to the string at a2; returns a0 = its end
putnum:
        move.l  %a2,%a0
1:      tst.b   (%a0)+
        bne.s   1b
        subq.l  #1,%a0
        divu.w  #10,%d0
        tst.w   %d0
        beq.s   2f
        move.l  %d0,%d1
        addi.l  #'0',%d1
        move.b  %d1,(%a0)+
2:      swap    %d0
        addi.l  #'0',%d0
        move.b  %d0,(%a0)+
        clr.b   (%a0)
        rts

statusline:
        move.l  %a2,-(%sp)
        lea     line3,%a2
        clr.b   (%a2)
        lea     (OSW_MBOX).l,%a1
        move.l  (MB_STATUS,%a1),%d0
        lea     str_hash,%a0
        cmpi.l  #ST_HASH,%d0
        beq.s   9f
        lea     str_bver,%a0
        cmpi.l  #ST_BVER,%d0
        beq.s   9f
        lea     str_size,%a0
        cmpi.l  #ST_SIZE,%d0
        beq.s   9f
        lea     str_flashed,%a0
        cmpi.l  #ST_RUN,%d0
        bne.s   9f
        pea     str_now
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        pea     (OSW_MBOX+MB_NAME).l
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        | which reset brought it here: OS UPGRADE's spin, or the RCR request
        lea     (OSW_MBOX).l,%a1
        move.l  (MB_RESET,%a1),%d0
        lea     str_rcr,%a0
        cmpi.l  #RS_RCR,%d0
        beq.s   9f
        lea     str_spin,%a0
        cmpi.l  #RS_SPIN,%d0
        beq.s   9f
        lea     str_q,%a0
9:      move.l  %a0,-(%sp)
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        move.l  (%sp)+,%a2
        rts

| ---- the dialog's answer ----------------------------------------------------
        .global osw_answer
osw_answer:
        tst.l   (4,%sp)
        bne.s   no
        | YES: OS UPGRADE's own stop (0x40063660), then the load in the UI task
        jsr     (0x400a10c8).l
        pea     (-1).w
        jsr     (0x40008fe4).l
        pea     (1).w
        jsr     (0x40022cd4).l
        addq.l  #8,%sp
        pea     rec_load
        pea     (UIQUEUE).l
        jsr     (DEFER).l
        clr.l   (%sp)
        pea     (STR_WAIT).l
        jsr     (MESSAGE).l
        lea     (12,%sp),%sp
        rts
no:     move.l  idx,%d0
        addq.l  #1,%d0
        cmp.l   count,%d0
        bcc.s   1f
        move.l  %d0,idx
        pea     rec_offer
        pea     (UIQUEUE).l
        jsr     (DEFER).l
        addq.l  #8,%sp
        rts
1:      clr.l   idx
        rts

        .global osw_reoffer
osw_reoffer:
        bra.w   offer

| ---- the load, in the UI task ----------------------------------------------
        .global osw_load
osw_load:
        lea     (-24,%sp),%sp
        movem.l %d2-%d5/%a2-%a3,(%sp)
        jsr     (0x4006d4a8).l          | as OS UPGRADE's deferred step (0x4006370c)
        | OS UPGRADE's pre-flash sequence (0x40080444..0x40080480)
        jsr     (0x400a10c8).l
        pea     (-1).w
        jsr     (0x40006820).l
        jsr     (0x40091cdc).l
        addq.l  #4,%sp
1:      pea     (0x46c901b8).l
        jsr     (0x400009dc).l
        addq.l  #4,%sp
        tst.l   %d0
        beq.s   2f
        clr.l   -(%sp)
        pea     (0x2710).w
        jsr     (0x40020c7c).l
        addq.l  #8,%sp
        bra.s   1b
        | "/" + name
2:      lea     path,%a2
        move.b  #'/',(%a2)
        clr.b   (1,%a2)
        bsr.w   curname
        move.l  %a0,-(%sp)
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        pea     (STR_R).l
        move.l  %a2,-(%sp)
        move.l  (FS_OPEN).l,%a0
        jsr     (%a0)
        addq.l  #8,%sp
        move.l  %d0,%d5                 | fd
        bmi.w   ioerr
        move.l  %d5,-(%sp)
        move.l  (FS_SIZE).l,%a0
        jsr     (%a0)
        addq.l  #4,%sp
        move.l  %d0,%d4                 | length
        cmpi.l  #OS_VEROFF+2,%d4
        bcs.w   notos_close
        cmpi.l  #OSW_MAXLEN,%d4
        bhi.w   notos_close
        | read it, eight sectors at a time as OS UPGRADE does, straight into the stage
        move.l  %d4,%d3
        addi.l  #511,%d3
        moveq   #9,%d0
        lsr.l   %d0,%d3                 | sectors left
        lea     (OSW_IMG).l,%a3
3:      tst.l   %d3
        beq.s   4f
        moveq   #8,%d2
        cmp.l   %d3,%d2
        bls.s   5f
        move.l  %d3,%d2
5:      move.l  %d2,-(%sp)
        move.l  %a3,-(%sp)
        move.l  %d5,-(%sp)
        move.l  (FS_READ).l,%a0
        jsr     (%a0)
        lea     (12,%sp),%sp
        sub.l   %d2,%d3
        moveq   #9,%d0
        lsl.l   %d0,%d2
        add.l   %d2,%a3
        bra.s   3b
4:      move.l  %d5,-(%sp)
        move.l  (FS_CLOSE).l,%a0
        jsr     (%a0)
        addq.l  #4,%sp
        | is it an OS image, and one this bootstrap may run?
        move.l  (OSW_IMG).l,%d0
        cmpi.l  #OS_FIRST,%d0
        bne.w   notos
        lea     (OSW_IMG+OS_VEROFF).l,%a0
        mvz.w   (%a0),%d0
        mvz.w   (NOR_BOOTVER).w,%d1
        cmp.l   %d1,%d0
        bne.w   bootver
        | the hash the chainloader checks
        lea     (OSW_IMG).l,%a0
        move.l  %d4,%d0
        moveq   #0,%d1
6:      move.l  %d1,%d2
        lsl.l   #5,%d1
        add.l   %d2,%d1
        moveq   #0,%d2
        move.b  (%a0)+,%d2
        add.l   %d2,%d1
        subq.l  #1,%d0
        bne.s   6b
        | the mailbox, MAGIC last
        lea     (OSW_MBOX).l,%a1
        move.l  %d4,(MB_LEN,%a1)
        move.l  %d1,(MB_HASH,%a1)
        move.l  #OSW_MAGIC,%d0
        eor.l   %d4,%d0
        eor.l   %d1,%d0
        move.l  %d0,(MB_CHECK,%a1)
        bsr.w   curname
        move.l  %a0,-(%sp)
        pea     (OSW_MBOX+MB_NAME).l
        clr.b   (OSW_MBOX+MB_NAME).l
        bsr.w   strcat
        addq.l  #8,%sp
        lea     (OSW_MBOX).l,%a1
        move.l  #RS_SPIN,%d0
        move.l  %d0,(MB_RESET,%a1)
        move.l  #OSW_MAGIC,%d0
        move.l  %d0,(MB_MAGIC,%a1)
        .global osw_reset
osw_reset:
        | interrupts off, the panel's queue drained (OS UPGRADE's own
        | first two steps, 0x4007fe6c..0x4007fe78)
        move.w  #0x2700,%sr
        jsr     (UART1_FLUSH).l
        | both DSP cores into their parked loaders: the soft reset below
        | does not reset the DSP, and the next OS's upload needs a ROM
        bsr.w   osw_park
        lea     (OSW_MBOX).l,%a1
        move.l  %d0,(MB_PARK,%a1)
        .if     TRACE
        | BOOT TRACE's note 13: velocity = the cores that took the park command
        move.l  %d0,%d3
        move.l  #0x90,%d1
        bsr.w   txmidi
        moveq   #13,%d1
        bsr.w   txmidi
        move.l  %d3,%d1
        bsr.w   txmidi
        move.l  #200000,%d2             | let the last byte leave before the reset: TXEMP
3:      move.b  (0xfc060004).l,%d0
        btst    #3,%d0
        bne.s   4f
        subq.l  #1,%d2
        bne.s   3b
4:
        .endif
        | MKII: the panel back to its start-up state, `60 02`, so the
        | bootstrap's `60 00` after the reset gets its key report
        tst.l   (MKII_FLAG).l
        beq.s   9f
        moveq   #0x60,%d1
        bsr.w   putpanel
        moveq   #0x02,%d1
        bsr.w   putpanel
        bsr.w   txempty
        move.l  #0x00400000,%d0         | ~20 ms for the panel to act on it (cycle count INFERRED)
7:      subq.l  #1,%d0
        bne.s   7b
9:
        .global osw_softreset
osw_softreset:
        lea     (OSW_MBOX).l,%a1
        move.l  #RS_RCR,%d0
        move.l  %d0,(MB_RESET,%a1)
        move.b  #0x80,%d0
        move.b  %d0,(RCR).l
8:      bra.s   8b

| osw_park: send both DSP cores host command $12 (dsp_park.asm) with the
| ColdFire's interrupts masked; d0 = a bit per core that took it. First a
| pause for a frame's host transfers to finish (the frame ISR's eDMA runs
| on without the CPU; ~5 ms at 266 MHz, cycle count INFERRED): a word still
| on its way would be read as the loader's count -- and the OS's upload
| INITs the host interface before its first word in any case (0x40001e5a).
        .global osw_park
osw_park:
        lea     (-8,%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  #0x00100000,%d0
1:      subq.l  #1,%d0
        bne.s   1b
        moveq   #0,%d3
        moveq   #0,%d1
        bsr.s   parkcore
        beq.s   2f
        moveq   #1,%d3
2:      moveq   #1,%d1
        bsr.s   parkcore
        beq.s   3f
        addq.l  #2,%d3
3:      moveq   #0,%d0
        move.b  %d0,(DSP_SELECT).l      | core 0, as the upload starts
        move.l  %d3,%d0
        movem.l (%sp),%d2-%d3
        lea     (8,%sp),%sp
        rts

| the core in d1: select it, raise the host command, wait for HC to clear
| (the frame handler's own poll, 0x4000ab1a: bit 7 of the low byte).
| Z clear (ne) if the core took it within ~2 M polls.
parkcore:
        move.b  %d1,(DSP_SELECT).l
        nop
        move.l  #PARK_HC,%d0
        move.w  %d0,(HI08_CVR).l
        move.l  #2000000,%d2
1:      move.w  (HI08_CVR).l,%d0
        tst.b   %d0
        bpl.s   2f
        subq.l  #1,%d2
        bne.s   1b
        moveq   #0,%d0                  | Z set: not taken
        rts
2:      moveq   #1,%d0                  | Z clear: taken
        rts

        .if     TRACE
| one byte on MIDI OUT (UART0), polled, ~200k polls at most (BOOT TRACE)
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

| one byte to the panel, polled as the bootstrap's putc does (0x20)
        .global putpanel
putpanel:
        bsr.w   txempty
        move.b  %d1,(UART1_UTB).l
        rts
        .global txempty
txempty:
        move.b  (UART1_USR).l,%d0
        btst    #3,%d0
        beq.s   txempty
        rts

notos_close:
        move.l  %d5,-(%sp)
        move.l  (FS_CLOSE).l,%a0
        jsr     (%a0)
        addq.l  #4,%sp
notos:
        pea     (STR_NOTOS).l
        bra.s   msg
bootver:
        pea     str_bootver
        bra.s   msg
ioerr:
        pea     (STR_IOERR).l
msg:    move.l  (%sp)+,%a0
        pea     (0x60).w
        move.l  %a0,-(%sp)
        jsr     (MESSAGE).l
        addq.l  #8,%sp
        movem.l (%sp),%d2-%d5/%a2-%a3
        lea     (24,%sp),%sp
        rts

| ---- strings -----------------------------------------------------------------
| strcat(dst, src): append, bounded to 30 bytes in all (the dialog's line)
strcat:
        move.l  (4,%sp),%a0
        move.l  (8,%sp),%a1
        moveq   #29,%d0
1:      tst.b   (%a0)
        beq.s   2f
        addq.l  #1,%a0
        subq.l  #1,%d0
        bgt.s   1b
        bra.s   4f
2:      move.b  (%a1)+,(%a0)
        beq.s   3f
        addq.l  #1,%a0
        subq.l  #1,%d0
        bgt.s   2b
4:      clr.b   (%a0)
3:      rts

| strcpy24(dst, src): NLEN-1 characters at most
strcpy24:
        move.l  (4,%sp),%a0
        move.l  (8,%sp),%a1
        moveq   #NLEN-1,%d0
1:      move.b  (%a1)+,(%a0)+
        beq.s   2f
        subq.l  #1,%d0
        bne.s   1b
        clr.b   (%a0)
2:      rts

| ---- state (the runtime is RAM: it lives beside the code) --------------------
        .align  4
rec_load:
        .byte   21, 0
        .long   osw_load
        .align  4
rec_offer:
        .byte   21, 0
        .long   osw_reoffer
        .align  4
count:  .long   0
idx:    .long   0
lines:  .long   line1, line2, line3
line1:  .space  32
line2:  .space  32
line3:  .space  32
path:   .space  32
names:  .space  NMAX*NLEN
