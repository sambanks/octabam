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
|
| UART0 is MIDI (its RX is MIDI IN, docs/remixer/EMU.md); the bootstrap
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
