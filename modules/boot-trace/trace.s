| BOOT TRACE -- one MIDI note on MIDI OUT at each stage of the boot, so a
| hang on the unit names its stage (modules/os-switch, build 3: the unit
| stops on the OCTABAM screen after a soft reset, and neither the port nor
| the image says where).
|
| Note On, channel 1, velocity 127, note = the stage:
|   1  the OS entry ran (OS SWITCH's chainloader, when it is in the image)
|   2  the DSP upload starts          0x40001e50
|   3  the DSP upload returned        0x40000512
|   4  the panel link's init          0x4001f834
|   5  the MKII panel handshake       0x4001f4dc
|   6  the UI's panel report check    0x40061c94
|   7  the first audio frame interrupt entered   0x4000aad0
|   8  ... and returned                          0x4000d9a6
|   9  the entry's clock check reached, velocity = the PLL multiplier byte
|      (0xfc0c4000 >> 24; 22 = 264 MHz)          0x40000432
|  10  the entry's bootstrap-REPROGRAM branch taken, velocity = NOR's
|      bootstrap version low byte (must never appear)   0x40000450
|  11  the bootstrap reprogram itself entered   0x4000f9b4
|  12  (OS SWITCH's chainloader) no switch pending: back to the entry
|  13  (OS SWITCH's switcher) just before the reset, velocity = the DSP
|      cores that took the park command (bit 0 core 0, bit 1 core 1)
|  14  a DSP bootstrap upload starts, velocity = its index (0 = core 0)
|                                                  0x40001d4c
|  15  a DSP payload's records start, velocity = its index (0 = core 0)
|  17  a DSP record's echo as the ColdFire reads it (low 7 bits; the
|      first 6 per core)                      0x40001bb4
|  19  ... when that echo is not a record type (> 3) and the upload is
|      abandoned: bits 13..7, then bits 20..14
|  20..25  the record sender stalled on a transmit wait (see tr_tx1)
|  18  the payload's final record (type 3, the jump): its echo, low 7
|      bits; anything but 3 abandons the upload     0x40001cf4
|  26  (OS SWITCH's boot picker) reached at the boot's first project-load
|      post, velocity 0 = it opened, else why it stepped aside (1 no
|      project, 2 a switch's boot, 3 no file system, 4 a dialog up, 5 the
|      set or project would not mount, 6 no other image, 7 no dialog)
|  27  (OS SWITCH's boot picker) answered: 0 YES, 1 NO, 2 the countdown's
|      NO (untouched), 3 the countdown's YES (after an arrow)
|  16  the records' first echo is late: every 2^20 polls of the host
|      port's ISR, at most six times, velocity = the ISR (bit 0 RXDF,
|      1 TXDE, 2 TRDY, 3 HF2, 4 HF3; OS SWITCH's loader raises HF2 when
|      it runs and HF3 when it jumps)          0x40001b82
|                                                  0x40001b18
|
| UART0 is MIDI (its RX is MIDI IN, tools/emu/README.md); the bootstrap
| sets it up for its own SysEx upgrade and enables its transmitter
| (0x202e), so this writes it polled, from the first instruction of the OS
| on. Each byte waits for TXRDY (USR bit 2) at most ~200k polls, so a dead
| port costs time, never a hang. Every register is preserved.

        .set    UART0_USR, 0xfc060004
        .set    UART0_UTB, 0xfc06000c

        .text

| trace: the note in d0.b, velocity 127; tracev: velocity in d1.b (0..127).
| Everything preserved.
        .global trace
trace:
        move.l  %d1,-(%sp)
        moveq   #0x7f,%d1
        bsr.s   tracev
        move.l  (%sp)+,%d1
        rts
        .global tracev
tracev:
        lea     (-16,%sp),%sp
        movem.l %d0-%d3,(%sp)
        move.l  %d1,%d3
        move.l  #0x90,%d1
        bsr.s   tx
        move.l  (%sp),%d1
        bsr.s   tx
        move.l  %d3,%d1
        andi.l  #0x7f,%d1
        bsr.s   tx
        movem.l (%sp),%d0-%d3
        lea     (16,%sp),%sp
        rts
tx:
        move.l  #200000,%d2
1:      move.b  (UART0_USR).l,%d0
        btst    #2,%d0
        bne.s   2f
        subq.l  #1,%d2
        bne.s   1b
2:      move.b  %d1,(UART0_UTB).l
        rts

        .global tr_dsp
tr_dsp:
        moveq   #2,%d0
        bsr.w   trace
        clr.b   %d0
        move.b  %d0,(0xfc0a400c).l
        jmp     (0x40001e58).l

        .global tr_dsp_done
tr_dsp_done:
        moveq   #3,%d0
        bsr.w   trace
        jsr     (0x4000f938).l
        jmp     (0x40000518).l

        .global tr_panel
tr_panel:
        move.l  %d0,-(%sp)
        moveq   #4,%d0
        bsr.w   trace
        move.l  (%sp)+,%d0
        link.w  %fp,#-16
        movem.l %d2-%d3/%a2,(%sp)
        jmp     (0x4001f83c).l

        .global tr_handshake
tr_handshake:
        move.l  %d0,-(%sp)
        moveq   #5,%d0
        bsr.w   trace
        move.l  (%sp)+,%d0
        lea     (-40,%sp),%sp
        movem.l %d2-%d7/%a2-%a3,(%sp)
        jmp     (0x4001f4e4).l

        .global tr_ui
tr_ui:
        move.l  %d0,-(%sp)
        moveq   #6,%d0
        bsr.w   trace
        move.l  (%sp)+,%d0
        tst.l   (0x46c8d18c).l
        jmp     (0x40061c9a).l

| the audio frame interrupt: note 7 the first time it is entered, note 8 the
| first time it returns (a hang inside it -- the DSP handshake at 0x4000ab1a
| polls with no timeout -- shows as 7 without 8). Once each: a flag byte.
        .global tr_frame
tr_frame:
        lea     (-252,%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        tst.b   seen7
        bne.s   1f
        moveq   #1,%d0
        move.b  %d0,seen7
        moveq   #7,%d0
        bsr.w   trace
1:      jmp     (0x4000aad8).l

        .global tr_frame_end
tr_frame_end:
        tst.b   seen8
        bne.s   1f
        moveq   #1,%d0
        move.b  %d0,seen8
        moveq   #8,%d0
        bsr.w   trace
1:      movem.l (%sp),%d0-%d7/%a0-%a6
        lea     (252,%sp),%sp
        rte

seen7:  .byte   0
seen8:  .byte   0
nboot:  .byte   0
nrec:   .byte   0
nlate:  .byte   0
necho:  .byte   0
nslow:  .byte   0
        .even
npoll:  .long   0
npollt: .long   0
nrecs:  .long   0
        .even

        .global tr_clock
tr_clock:
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        move.l  (0xfc0c4000).l,%d1
        moveq   #24,%d0
        lsr.l   %d0,%d1
        moveq   #9,%d0
        bsr.w   tracev
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        move.w  (0x400dea48).l,%d1
        jmp     (0x40000438).l

        .global tr_reprog_branch
tr_reprog_branch:
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        mvz.w   (0x3ffc).w,%d1
        moveq   #10,%d0
        bsr.w   tracev
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        pea     (0x96).w
        jmp     (0x40000456).l

        .global tr_reprog
tr_reprog:
        move.l  %d0,-(%sp)
        moveq   #11,%d0
        bsr.w   trace
        move.l  (%sp)+,%d0
        lea     (-16,%sp),%sp
        movem.l %d2/%a2-%a4,(%sp)
        jmp     (0x4000f9bc).l

        .global tr_bootup
tr_bootup:
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        moveq   #0,%d1
        move.b  nboot,%d1               | the call's index: 0 = core 0, 1 = core 1 at a boot
        addq.l  #1,%d1
        move.b  %d1,nboot
        subq.l  #1,%d1
        moveq   #14,%d0
        bsr.w   tracev
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        lea     (-16,%sp),%sp
        movem.l %d2-%d4/%a2,(%sp)
        jmp     (0x40001d54).l

        .global tr_records
tr_records:
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        moveq   #0,%d1
        move.b  nrec,%d1               | the call's index: 0 = core 0, 1 = core 1 at a boot
        addq.l  #1,%d1
        move.b  %d1,nrec
        subq.l  #1,%d1
        moveq   #15,%d0
        bsr.w   tracev
        clr.b   necho                  | each core reports its own first echoes
        clr.l   nrecs
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        lea     (-12,%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        jmp     (0x40001b20).l

        .global tr_echo
tr_echo:
        move.l  npoll,%d0
        addq.l  #1,%d0
        move.l  %d0,npoll
        andi.l  #0xfffff,%d0
        bne.s   1f
        moveq   #0,%d0
        move.b  nlate,%d0
        cmpi.l  #6,%d0
        bcc.s   1f
        addq.l  #1,%d0
        move.b  %d0,nlate
        move.l  %d1,-(%sp)
        move.w  (0x20000008).l,%d1
        moveq   #16,%d0
        bsr.w   tracev
        move.l  (%sp)+,%d1
1:      move.w  (0x20000008).l,%d0
        jmp     (0x40001b88).l

| a record's echo, d0; replays `moveq #3,d2 / cmp.l d0,d2 / blt 0x40001d40`
        .global tr_rececho
tr_rececho:
        addq.l  #1,nrecs
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        moveq   #0,%d1
        move.b  necho,%d1
        cmpi.l  #6,%d1
        bcc.s   1f
        addq.l  #1,%d1
        move.b  %d1,necho
        move.l  4(%sp),%d1
        moveq   #17,%d0
        bsr.w   tracev
1:      move.l  4(%sp),%d0
        moveq   #3,%d1
        cmp.l   %d0,%d1
        bge.s   2f
        | not a type: report the rest of the word, then the stock error exit
        move.l  %d0,%d1
        lsr.l   #7,%d1
        moveq   #19,%d0
        bsr.w   tracev
        move.l  4(%sp),%d1
        moveq   #14,%d0
        lsr.l   %d0,%d1
        moveq   #19,%d0
        bsr.w   tracev
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        moveq   #3,%d2
        jmp     (0x40001d40).l
2:      move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        moveq   #3,%d2
        bra.w   tr_tx2

| the final record's echo, d0; replays `moveq #3,d2 / cmp.l d0,d2 / bne 0x40001d40`
        .global tr_lastecho
tr_lastecho:
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %d0,%d1
        moveq   #18,%d0
        bsr.w   tracev
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        moveq   #3,%d2
        cmp.l   %d0,%d2
        beq.s   1f
        jmp     (0x40001d40).l
1:      jmp     (0x40001cfa).l

| The record sender's three transmit waits (TXDE|TRDY, ISR bits 1..2): the
| DSP stopped taking words. Each wait polls as stock does; every 2^20 polls
| (all sites together), at most three times per boot, txslow reports:
|   20  the site: 1 before a record's type (0x40001b46), 2 before its
|       address (0x40001bbc), 3 before a data word (0x40001c4c)
|   21  records echoed so far on this core, bits 6..0; 22 bits 13..7
|   23  the data word's index in its record (d3), bits 6..0; 24 bits 13..7
|   25  the host-side ISR (bit 0 RXDF, 1 TXDE, 2 TRDY, 3 HF2, 4 HF3)
| d2 is live at site 1 (the record's type) and d2/d3 at site 3: kept.
        .global tr_tx1
tr_tx1:
        move.w  (0x20000008).l,%d0
        moveq   #6,%d1
        and.l   %d1,%d0
        bne.s   1f
        moveq   #1,%d1
        bsr.s   txslow
        bra.s   tr_tx1
1:      jmp     (0x40001b52).l

tr_tx2:
        move.w  (0x20000008).l,%d0
        moveq   #6,%d1
        and.l   %d1,%d0
        bne.s   1f
        moveq   #2,%d1
        bsr.s   txslow
        bra.s   tr_tx2
1:      jmp     (0x40001bc8).l

        .global tr_tx3
tr_tx3:
        move.w  (0x20000008).l,%d0
        moveq   #6,%d1
        and.l   %d1,%d0
        bne.s   1f
        moveq   #3,%d1
        bsr.s   txslow
        bra.s   tr_tx3
1:      jmp     (0x40001c58).l

| d1 = the site; everything preserved
txslow:
        lea     (-8,%sp),%sp
        movem.l %d0-%d1,(%sp)
        move.l  npollt,%d0
        addq.l  #1,%d0
        move.l  %d0,npollt
        andi.l  #0xfffff,%d0
        bne.s   9f
        moveq   #0,%d0
        move.b  nslow,%d0
        cmpi.l  #3,%d0
        bcc.s   9f
        addq.l  #1,%d0
        move.b  %d0,nslow
        moveq   #20,%d0
        bsr.w   tracev                  | the site, in d1
        move.l  nrecs,%d1
        moveq   #21,%d0
        bsr.w   tracev
        lsr.l   #7,%d1
        moveq   #22,%d0
        bsr.w   tracev
        move.l  %d3,%d1
        moveq   #23,%d0
        bsr.w   tracev
        lsr.l   #7,%d1
        moveq   #24,%d0
        bsr.w   tracev
        move.w  (0x20000008).l,%d1
        moveq   #25,%d0
        bsr.w   tracev
9:      movem.l (%sp),%d0-%d1
        lea     (8,%sp),%sp
        rts
