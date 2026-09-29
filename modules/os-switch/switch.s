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
        .set    SCAN_STATE, 0x460e76ac  | its name pool (64 KB) and its cache, to 0x460f77ff
        .set    SCAN_STATE_LEN, 0x10154
        .set    SCAN_MAX,  1024         | its table's capacity (0x4007f35e), 12-byte records {name*, is_dir, -}
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
        .set    HI08_ISR,  0x20000008   | the host-side status: bit 0 RXDF (the upload's own poll)
        .set    HI08_RXL,  0x2000001c   | RXM:RXL; reading it takes the word (0x40001ce0)
        .set    DSP_SELECT, 0xfc0a400c  | which core's host port the window shows (0, 1): the upload's own
        .set    PARK_HC,   0x008f       | HC | $0f: vector P:$1e, dsp_park.asm's osw_dsp
                                        | (was $12/P:$24 until the park moved
                                        | into the dead vector run, 29 Sep 2026)
        .set    NMAX, 32                | .OBI files listed
        .set    NLEN, 24                | bytes kept of each name

        .text

| ---- MAIN MENU > OS: a fifth root category ----------------------------------
| The root list holds five rows from boot (its window is five tall, the
| init at 0x40064c70 is given 5, and stock fills four; docs/firmware/
| MAINMENU.md section 1). Stock's four rows come from the user's own image,
| then ours: the label, the category icon, and the child list below.
        .global osw_root
        .align  4
osw_root:
        ROOT_ROWS                       | remix.inc: .incbin of 0x400cc698, 4 x 0x18
        .long   str_os, osw_icon, 0, 0, osw_list, 0

| the category icon: a window descriptor {19, 9, 1, ink, mask} as stock's
| (0x400cbc34..0x400cbc70), each plane 19 words, one column per word, the
| column's pixels in the high byte, bit 0 the top row
        .align  4
osw_icon:
        .long   0x13, 0x09, 0x01, osw_ink, osw_mask
osw_ink:
        ICON_INK
osw_mask:
        ICON_MASK

| the child list: shipped initialised (stock inits only its own descriptors,
| docs/firmware/MAINMENU.md section 1): count, scroll, cursor, selection,
| visible rows, count again, the rows. osw_scan rewrites both counts.
        .align  4
        .global osw_list
osw_list:
        .long   1, 0, 0, 0, 7, 1, osw_rows

str_os:
        .asciz  "OS"
str_self:
        OSW_SELF                        | remix.inc: this image's own name (make's VERSION)
str_flash:
        .asciz  "HOME "
str_unknown:
        .asciz  "?"
str_title:
        .asciz  "OS SWITCH"
str_obi:
        .asciz  "OBI"
str_none:
        .asciz  "NO .OBI FILES ON CARD"
str_boot:
        .asciz  "BOOT "
str_q:
        .asciz  "?"
str_stops:
        .asciz  "PLAYBACK WILL STOP"
str_home:
        .asciz  "POWER-CYCLE: BACK HOME"
str_now:
        .asciz  "NOW "
str_flashed:
        .asciz  "FLASHED"
str_hash:
        .asciz  "LAST SWITCH: HASH ERROR"
str_bver:
        .asciz  "LAST SWITCH: BOOTSTRAP"
str_size:
        .asciz  "LAST SWITCH: TOO BIG"
str_bootver:
        .asciz  "OTHER BOOTSTRAP VERSION"
        .align  2

| ---- the list, rebuilt each time MAIN MENU opens -----------------------------
| Detour at 0x40064c32: the opener's "no menu window yet" path, before the
| window is created and the list drawn. The scan is the stock one OS
| UPGRADE uses for `/*.BIN` (0x4007f598), from the UI task as a row
| action's is; stock's own file browsers read the card during playback.
| Replays `move.l (0x400cbf6c).l,-(%sp)`.
        .global osw_menu
osw_menu:
        lea     (-60,%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        | the scan calls through the file system's vector table
        | (0x46c8240e, FS_OPEN): with it not yet set up -- a warm harness
        | that opens the menu with no card behind it (emu_bringup,
        | verify_hidden) -- keep the last list rather than jump through 0
        tst.l   (0x46c8240e).l
        beq.s   1f
        tst.l   (FS_OPEN).l
        beq.s   1f
        bsr.w   osw_scan
1:      movem.l (%sp),%d0-%d7/%a0-%a6
        lea     (60,%sp),%sp
        move.l  (0x400cbf6c).l,-(%sp)
        jmp     (0x40064c38).l

| osw_scan: names[] = the card root's .OBI files, sorted; rows[] = the
| heading(s), then one row per file (label = the name without .OBI)
        .global osw_scan
osw_scan:
        lea     (-12,%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        | BORROW THE SCAN'S STATE AND GIVE IT BACK. The stock dir scan keeps
        | every listing's names in ONE global 64 KB pool (0x460e76ac) and its
        | last directory, extension and count in a cache after it (0x460f76ac..
        | 0x460f77ff); the project, set and sample browsers list through the
        | same scan (0x4006a4c0, 0x4006aee8, 0x4006465a) and keep pointing into
        | that pool. OS UPGRADE, the only other root scan, reboots after it;
        | this runs at every MAIN MENU opening, so it saves the pool and the
        | cache first, lists into its own table, and puts both back byte for
        | byte. Build 15 on the unit listed through the browsers' table and
        | pool and threw VEC:04 (PC 0x2007e788) on a later file load
        | (29 Sep 2026; the port did not reproduce it).
        lea     (SCAN_STATE).l,%a0
        lea     osw_save,%a1
        move.l  #SCAN_STATE_LEN/4,%d0
1:      move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.s   1b
        clr.l   -(%sp)
        clr.l   -(%sp)
        pea     str_obi
        pea     osw_tab
        pea     (STR_SLASH).l
        jsr     (DIRSCAN).l
        lea     (20,%sp),%sp
        | keep the files, drop the directories
        lea     osw_tab,%a2
        moveq   #0,%d2                  | files kept
        move.l  %d0,%d3
        ble.s   2f
1:      tst.l   (4,%a2)
        bne.s   3f
        cmpi.l  #NMAX,%d2
        bcc.s   3f
        move.l  %d2,%d0
        mulu.w  #NLEN,%d0
        lea     names,%a0
        add.l   %d0,%a0
        move.l  (%a2),-(%sp)
        move.l  %a0,-(%sp)
        bsr.w   strcpy24
        addq.l  #8,%sp
        addq.l  #1,%d2
3:      lea     (12,%a2),%a2
        subq.l  #1,%d3
        bne.s   1b
2:      move.l  %d2,count
        | the names are ours now: the scan's state back as it was
        lea     osw_save,%a0
        lea     (SCAN_STATE).l,%a1
        move.l  #SCAN_STATE_LEN/4,%d0
3:      move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.s   3b
        bsr.w   sortnames
        bsr.w   buildrows
        movem.l (%sp),%d2-%d3/%a2
        lea     (12,%sp),%sp
        rts

| sortnames: names[0..count) in ascending byte order (count <= 32: a
| bubble sort, NLEN-byte swaps through `tmp`)
sortnames:
        lea     (-20,%sp),%sp
        movem.l %d2-%d4/%a2-%a3,(%sp)
        move.l  count,%d4
1:      subq.l  #1,%d4
        ble.s   9f
        moveq   #0,%d2                  | i
        lea     names,%a2
2:      cmp.l   %d4,%d2
        bcc.s   1b
        lea     (NLEN,%a2),%a3
        | compare names[i] (a2) with names[i+1] (a3)
        move.l  %a2,%a0
        move.l  %a3,%a1
3:      move.b  (%a0)+,%d0
        move.b  (%a1)+,%d1
        cmp.b   %d1,%d0
        bhi.s   4f                      | out of order: swap
        bcs.s   5f
        tst.b   %d0
        bne.s   3b
        bra.s   5f
4:      moveq   #NLEN-1,%d3
        move.l  %a2,%a0
        move.l  %a3,%a1
6:      move.b  (%a0),%d0
        move.b  (%a1),%d1
        move.b  %d1,(%a0)+
        move.b  %d0,(%a1)+
        subq.l  #1,%d3
        bpl.s   6b
5:      move.l  %a3,%a2
        addq.l  #1,%d2
        bra.s   2b
9:      movem.l (%sp),%d2-%d4/%a2-%a3
        lea     (20,%sp),%sp
        rts

| buildrows: the rows and the counts. Row 0 is a heading in stock's
| separator form (two 0x17 glyphs, the text, 0x17 to 22 wide; the cursor
| skips a row whose action is 0): NOW <running>. A failed last switch adds
| a plain heading. Then a row per file, or one inert NO .OBI FILES row.
buildrows:
        lea     (-16,%sp),%sp
        movem.l %d2-%d3/%a2-%a3,(%sp)
        lea     osw_rows,%a2
        | heading 0: "\x17NOW <this image>\x17..."
        lea     head0,%a3
        lea     str_now,%a0
        bsr.w   heading
        lea     str_self,%a0
        bsr.w   headtail
        | heading 1: "\x17HOME <the flashed image>\x17...": this one
        | after a power-on; after a switch, the name the switch carried
        lea     head1,%a3
        lea     str_flash,%a0
        bsr.w   heading
        bsr.w   flashname
        bsr.w   headtail
        moveq   #2,%d3                  | headings
        | a failed last switch: its reason, inert
        lea     (OSW_MBOX).l,%a1
        move.l  (MB_STATUS,%a1),%d0
        lea     str_hash,%a0
        cmpi.l  #ST_HASH,%d0
        beq.s   1f
        lea     str_bver,%a0
        cmpi.l  #ST_BVER,%d0
        beq.s   1f
        lea     str_size,%a0
        cmpi.l  #ST_SIZE,%d0
        bne.s   2f
1:      bsr.w   inert
        addq.l  #1,%d3
2:      move.l  %d3,nhead
        | the files
        move.l  count,%d2
        bne.s   3f
        lea     str_none,%a0
        bsr.w   inert
        moveq   #1,%d2                  | rows after the headings
        bra.s   6f
3:      moveq   #0,%d1
        lea     names,%a0
        lea     labels,%a1
4:      move.l  %a1,(%a2)+              | label
        clr.l   (%a2)+                  | no window
        move.l  #osw_pick,%d0
        move.l  %d0,(%a2)+              | action
        clr.l   (%a2)+
        clr.l   (%a2)+
        clr.l   (%a2)+
        | label = the name, without .OBI
        move.l  %a0,-(%sp)
        move.l  %a1,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %a0,-(%sp)
        move.l  %a1,-(%sp)
        bsr.w   strcpy24
        addq.l  #8,%sp
        move.l  (4,%sp),%a0
        bsr.w   stripobi
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%a1
        move.l  (%sp)+,%a0
        lea     (NLEN,%a0),%a0
        lea     (NLEN,%a1),%a1
        addq.l  #1,%d1
        cmp.l   %d2,%d1
        bcs.s   4b
6:      add.l   %d3,%d2                 | every row
        lea     osw_list,%a0
        move.l  %d2,(%a0)
        move.l  %d2,(0x14,%a0)
        | the cursor back on the first file, the window at the top
        clr.l   (4,%a0)
        move.l  %d3,(8,%a0)
        move.l  %d3,(0xc,%a0)
        movem.l (%sp),%d2-%d3/%a2-%a3
        lea     (16,%sp),%sp
        rts

| inert: a row at (a2)+ with label a0 and no action
inert:
        move.l  %a0,(%a2)+
        clr.l   (%a2)+
        clr.l   (%a2)+
        clr.l   (%a2)+
        clr.l   (%a2)+
        clr.l   (%a2)+
        rts

| heading: start the heading at a3 -- one 0x17 glyph (the pane is 15
| characters wide: HOME + a 9-character name fills it), then the text at a0
heading:
        moveq   #0x17,%d0
        move.b  %d0,(%a3)
        clr.b   (1,%a3)
        move.l  %a0,-(%sp)
        move.l  %a3,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        rts

| headtail: append the name at a0, pad with 0x17 to 22, and emit the row
headtail:
        move.l  %a0,-(%sp)
        move.l  %a3,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        move.l  %a3,%a0
        bsr.w   stripobi
        move.l  %a3,%a0
        moveq   #22,%d0
        bsr.w   padsep
        move.l  %a3,%a0
        bra.w   inert

| a0 = the flashed image's name: this image's, unless this boot came from a
| switch (status RUN), then the one the switch carried in the mailbox
flashname:
        lea     str_self,%a0
        lea     (OSW_MBOX).l,%a1
        move.l  (MB_STATUS,%a1),%d0
        cmpi.l  #ST_RUN,%d0
        bne.s   1f
        lea     (OSW_MBOX+MB_FLASH).l,%a0
        tst.b   (%a0)
        bne.s   1f
        lea     str_unknown,%a0
1:      rts

| stripobi: cut a trailing ".OBI" (any case) off the string at a0
stripobi:
        move.l  %a0,%a1
1:      tst.b   (%a1)+
        bne.s   1b
        subq.l  #1,%a1                  | the NUL
        move.l  %a1,%d0
        sub.l   %a0,%d0
        moveq   #4,%d1
        cmp.l   %d1,%d0
        bcs.s   9f
        lea     (-4,%a1),%a1
        move.b  (%a1),%d1
        cmpi.b  #'.',%d1
        bne.s   9f
        clr.b   (%a1)
9:      rts

| padsep: 0x17 after the string at a0 up to d0 characters
padsep:
1:      tst.b   (%a0)
        beq.s   2f
        addq.l  #1,%a0
        subq.l  #1,%d0
        bgt.s   1b
        rts
2:      tst.l   %d0
        ble.s   3f
        moveq   #0x17,%d1
        move.b  %d1,(%a0)+
        subq.l  #1,%d0
        bra.s   2b
3:      clr.b   (%a0)
        rts

| ---- a file picked: the confirm dialog -----------------------------------
| The row action is called with 0 (docs/firmware/MAINMENU.md section 3); the
| file is the list's selection (scroll + cursor) past the headings.
        .global osw_pick
osw_pick:
        lea     (-8,%sp),%sp
        movem.l %d2/%a2,(%sp)
        lea     osw_list,%a0
        move.l  (4,%a0),%d0
        add.l   (8,%a0),%d0
        sub.l   nhead,%d0
        bmi.s   9f
        cmp.l   count,%d0
        bcc.s   9f
        move.l  %d0,idx
        | line 1: "BOOT <label>?"
        lea     line1,%a2
        clr.b   (%a2)
        pea     str_boot
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        move.l  idx,%d0
        mulu.w  #NLEN,%d0
        lea     labels,%a0
        add.l   %d0,%a0
        move.l  %a0,-(%sp)
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        pea     str_q
        move.l  %a2,-(%sp)
        bsr.w   strcat
        addq.l  #8,%sp
        pea     osw_answer
        pea     (3).w
        pea     lines
        pea     (3).w
        pea     str_title
        jsr     (DIALOG).l
        lea     (20,%sp),%sp
9:      movem.l (%sp),%d2/%a2
        lea     (8,%sp),%sp
        rts

| a0 = names[idx], the file name
curname:
        move.l  idx,%d0
        mulu.w  #NLEN,%d0
        lea     names,%a0
        lea     (%a0,%d0.l),%a0
        rts

| ---- the dialog's answer ----------------------------------------------------
        .global osw_answer
osw_answer:
        tst.l   (4,%sp)
        bne.s   1f
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
1:      rts


| ---- the chainloader's body -------------------------------------------------
| Copied to OSW_BODY by osw_load, its length and the sum of its longs in the
| mailbox; the ROM gate (chain.s) runs it after spending the mailbox, with
| a1 = the mailbox and a2 = the gate's resume. Position-independent: it
| runs from the stage page, not from here. It checks the stage and hands
| over, or writes why not and goes back to the gate.
        .align  4
        .global osw_body
osw_body:
        move.l  (MB_LEN,%a1),%d2
        move.l  (MB_HASH,%a1),%d3
        move.l  #OSW_MAGIC,%d0
        eor.l   %d2,%d0
        eor.l   %d3,%d0
        cmp.l   (MB_CHECK,%a1),%d0
        bne.w   b_none
        tst.l   %d2
        beq.w   b_size
        cmpi.l  #OSW_MAXLEN,%d2
        bhi.w   b_size
        cmpi.l  #OS_VEROFF+2,%d2
        bcs.w   b_size
        | The entry of the staged image would compare its bootstrap version
        | with NOR's and, if newer, REPROGRAM THE BOOTSTRAP (0x4000f9b4) --
        | the recovery path. Only a staged image whose version is NOR's own
        | may run.
        lea     (OSW_IMG+OS_VEROFF).l,%a0
        mvz.w   (%a0),%d0
        mvz.w   (NOR_BOOTVER).w,%d1
        cmp.l   %d1,%d0
        bne.w   b_ver
        lea     (OSW_IMG).l,%a0
        move.l  %d2,%d0
        moveq   #0,%d1
b_hash1:
        move.l  %d1,%d4
        lsl.l   #5,%d1
        add.l   %d4,%d1
        moveq   #0,%d4
        move.b  (%a0)+,%d4
        add.l   %d4,%d1
        subq.l  #1,%d0
        bne.s   b_hash1
        cmp.l   %d3,%d1
        bne.w   b_hash
        move.l  #ST_BOOT,%d0
        move.l  %d0,(MB_STATUS,%a1)
        | the stub, out of the way of the copy
        lea     b_stub(%pc),%a0
        lea     (OSW_STUB).l,%a2
        moveq   #(b_stub_end-b_stub)/2,%d0
b_copy:
        move.w  (%a0)+,(%a2)+
        subq.l  #1,%d0
        bne.s   b_copy
        move.l  (OS_ARGCELL).l,%d1      | the bootstrap's argument, read before it is overwritten
        lea     (OSW_IMG).l,%a0
        lea     (OS_ENTRY).l,%a2
        move.l  %d2,%d0
        jmp     (OSW_STUB).l
b_none:
        move.l  #ST_NONE,%d0
        bra.s   1f
b_size:
        move.l  #ST_SIZE,%d0
        bra.s   1f
b_ver:
        move.l  #ST_BVER,%d0
        bra.s   1f
b_hash:
        move.l  #ST_HASH,%d0
1:      move.l  %d0,(MB_STATUS,%a1)
        jmp     (%a2)

| The stub: a0 = stage, a2 = OS_ENTRY, d0 = length, d1 = the argument.
| Caches off and invalidated for the copy, then the bootstrap's own exit
| state, then the entry as the bootstrap calls it (bootstrap 0x2d3c:
| `move.l 0x8000050a,-(%sp) ; jsr 0x40000400`). Position-independent.
        .align  2
b_stub:
        move.l  #CACR_OFF,%d4
        movec   %d4,%cacr
        nop
b_stub1:
        move.l  (%a0)+,(%a2)+
        subq.l  #4,%d0
        bgt.s   b_stub1
        move.l  #CACR_BOOT,%d4
        movec   %d4,%cacr
        nop
        move.l  %d1,-(%sp)
        jsr     (OS_ENTRY).l
b_halt:
        bra.s   b_halt
b_stub_end:
        .align  4
        .global osw_body_end
osw_body_end:

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
        | the chainloader's body into the stage page, and its sum
        lea     osw_body,%a0
        lea     (OSW_BODY).l,%a2
        move.l  #(osw_body_end-osw_body)/4,%d0
        lea     (OSW_MBOX).l,%a1
        move.l  %d0,(MB_BODYLEN,%a1)
        moveq   #0,%d1
7:      move.l  (%a0)+,%d2
        move.l  %d2,(%a2)+
        add.l   %d2,%d1
        subq.l  #1,%d0
        bne.s   7b
        move.l  %d1,(MB_BODYSUM,%a1)
        | the flashed image's name, for the next image's HOME line: ours
        | after a power-on, carried on when this boot is itself a switch
        move.l  (MB_STATUS,%a1),%d0
        cmpi.l  #ST_RUN,%d0
        beq.s   8f
        lea     str_self,%a0
        lea     (OSW_MBOX+MB_FLASH).l,%a2
        moveq   #15,%d0
6:      move.b  (%a0)+,(%a2)+
        subq.l  #1,%d0
        bne.s   6b
        clr.b   (%a2)
8:      lea     (OSW_MBOX).l,%a1
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
        | (bits 1..0) and the words drained from each (bits 3..2 core 0, 5..4 core 1)
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
| ColdFire's interrupts masked, and drain each one's host-side receive
| register (below); d0 = a bit per core that took it (bits 0, 1), then the
| words drained from core 0 (bits 3..2) and core 1 (bits 5..4). First a
| pause for a frame's host transfers to finish (the frame ISR's eDMA runs
| on without the CPU; ~5 ms at 266 MHz, cycle count INFERRED): a word still
| on its way would be read as the loader's count -- and the OS's upload
| INITs the host interface before its first word in any case (0x40001e5a).
        .global osw_park
osw_park:
        lea     (-12,%sp),%sp
        movem.l %d2-%d4,(%sp)
        move.l  #0x00100000,%d0
1:      subq.l  #1,%d0
        bne.s   1b
        moveq   #0,%d3
        moveq   #0,%d1
        bsr.s   parkcore
        beq.s   2f
        moveq   #1,%d3
2:      bsr.s   drain
        lsl.l   #2,%d0
        or.l    %d0,%d3
        moveq   #1,%d1
        bsr.s   parkcore
        beq.s   3f
        addq.l  #2,%d3
3:      bsr.s   drain
        lsl.l   #4,%d0
        or.l    %d0,%d3
        moveq   #0,%d0
        move.b  %d0,(DSP_SELECT).l      | core 0, as the upload starts
        move.l  %d3,%d0
        movem.l (%sp),%d2-%d4
        lea     (12,%sp),%sp
        rts

| drain: the selected core's host-side receive register. A chip reset
| clears it; the soft reset does not (the HI08 is the DSP's), so a word the
| payload sent before the park would still be there, RXDF set, and the next
| OS's record sender (0x40001b18) reads it as its first record's echo -- and
| abandons the upload, silently (its caller ignores the result), on
| anything above 3. INFERRED from build 11 on the unit (the upload returned
| in ~1 ms, no audio frame followed); BOOT TRACE's notes 17/19 measure it.
| Reads the word out while RXDF is set, a pause before each look for the
| DSP side to move a queued word over; d0 = the words read, 0..3 (3 = 3 or
| more, at most 15).
drain:
        moveq   #0,%d4
1:      move.l  #20000,%d2
2:      subq.l  #1,%d2
        bne.s   2b
        move.w  (HI08_ISR).l,%d0
        btst    #0,%d0
        beq.s   3f
        move.w  (HI08_RXL).l,%d0        | the low lanes: the read that takes the word
        addq.l  #1,%d4
        moveq   #15,%d0
        cmp.l   %d4,%d0
        bne.s   1b
3:      move.l  %d4,%d0
        moveq   #3,%d2
        cmp.l   %d0,%d2
        bge.s   4f
        move.l  %d2,%d0
4:      rts

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
count:  .long   0
idx:    .long   0
nhead:  .long   1
lines:  .long   line1, str_stops, str_home
line1:  .space  32
path:   .space  32
head0:  .space  32
head1:  .space  32
names:  .space  NMAX*NLEN
labels: .space  NMAX*NLEN
        .align  4
osw_tab:
        .space  SCAN_MAX*12
osw_save:
        .space  SCAN_STATE_LEN
        .align  4
osw_rows:
        .long   str_none, 0, 0, 0, 0, 0
        .space  (NMAX+1)*0x18
