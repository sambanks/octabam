| screenshot.s -- the Elektron screenshot SysEx RPC, answered on MIDI OUT.
|
| Request (13 bytes):   F0 00 20 3C <id0> 00 <leader> m1 m2 r1 r2 cmd F7
|   id0 = 05 (the OT's own) or 10 (the id Digitakt / Analog Four MKII /
|   Rytm MKII answer; screendump's default probe). The 7-bit body decodes to
|   msgId:u16 replyTo:u16 cmd:u8 with cmd = 04.
| Reply:  the request's two id bytes, then the 7-bit encoding of
|   msgId:u16 replyTo:u16 cmd=84 ver=1 w=0080 h=0040 len=00000400 pixels[1024]
|   F7 (1,194 bytes). The pixels are the frame the panel was last sent: the
|   flush 0x40013abc clears the back buffer [0x400b9710], ORs every visible
|   layer of the list at [0x460babf0] into it (the page plane 0x46c7e0ea
|   and the windows: MIXER, SETUP, popups, menus), sends the diff against
|   [0x400b970c] to the panel and swaps the two pointers, so [0x400b970c]
|   holds the composited frame now on the LCD. Same layout as the plane:
|   128 rows of 8 bytes, byte x*8+p = panel page p of column x; bit y of
|   the big-endian row x = pixel (x, y), which is screendump's column-major,
|   row 0 at the least significant bit.
| 7-bit encoding: groups of 7 data bytes, each behind a leader byte whose bit
|   (6-i) is the MSB of data byte i; a trailing group of n bytes has n bytes.
|
| Stock's SysEx entry 0x40001918 takes `F0 00 20 3C 05 00 <b6>` only for
| b6 in 0x50..0x73 and drops every other message. The detour sits on the
| entry (it replays the displaced `movel %d2,%sp@-` and `moveal %sp@(8),%a0`)
| and passes every message that is not this request back to stock.
|
| The reply goes back on the transport the request came on. usbmidi_rx.s
| (modules/usb) sets usbmidi_rx_sysex when it enqueues an F0; the hook reads
| and clears it at every SysEx, so it is 1 only for a message that began on
| USB. USB: the 1,194 bytes go through the firmware's USB-MIDI encoder
| (0x4001d204, stateful across SysEx, 4 bytes per 3) in one call, one EP2 IN
| transfer of 1,592 bytes from the 4 KB buffer at 0x4ecc8000, after claiming
| usbmidi_tx_busy as usbmidi_tx_kick does. The USB symbols are weak: an image
| without the USB module answers on DIN only.
|
| DIN: bytes leave through the MIDI OUT ring the way 0x40010bc8 writes them
| (ring 0x400b966c, write index 0x400b9678 counting down, fill 0x400b967c,
| UART0 TX enable 0xfc060014 := 3), so the wire sees them in order with
| whatever stock has queued. 0x460ba978 != 0 is stock's MIDI OUT hold: no
| reply then. After the reply the running-status byte 0x460ba988 is cleared,
| so the next channel message carries its status.

        .text
        .global ss_hook
        .weak   usbmidi_rx_sysex, usbmidi_up, usbmidi_tx_busy

        .equ    FRONT,      0x400b970c      | -> the frame the last flush sent (PANEL.md section 9)
        .equ    RING_PTR,   0x400b966c
        .equ    RING_IDX,   0x400b9678
        .equ    RING_CNT,   0x400b967c
        .equ    UART0_UIMR, 0xfc060014
        .equ    MIDI_HOLD,  0x460ba978
        .equ    RUN_STATUS, 0x460ba988
        .equ    TX_ACT,     0x46c8345e
        .equ    STOCK_NEXT, 0x4000191e      | site + 6
        .equ    RAW_LEN,    1038            | 14 header + 1024 pixels
        .equ    ENCODER,    0x4001d204      | usb_midi_encoder(len, buf): one EP2 IN transfer

ss_hook:
        movel   %d2,%sp@-                   | displaced
        moveal  %sp@(8),%a0                 | displaced: the message, at its F0
        clrl    %d1                         | d1 = 1 when the message came over USB
        lea     usbmidi_rx_sysex:l,%a1
        movel   %a1,%d0
        beqs    ss_nousb                    | no USB in the image
        mvzb    %a1@,%d1
        clrb    %a1@
ss_nousb:
        tstb    %a0@(1)
        bnew    ss_pass
        mvzb    %a0@(2),%d0
        cmpil   #0x20,%d0
        bnew    ss_pass
        mvzb    %a0@(3),%d0
        cmpil   #0x3c,%d0
        bnew    ss_pass
        tstb    %a0@(5)
        bnew    ss_pass
        mvzb    %a0@(12),%d0                | exactly 13 bytes
        cmpil   #0xf7,%d0
        bnew    ss_pass
        mvzb    %a0@(11),%d0                | cmd = 04 ...
        cmpil   #4,%d0
        bnew    ss_pass
        mvzb    %a0@(6),%d0                 | ... with its MSB (leader bit 2) clear
        btst    #2,%d0
        bnew    ss_pass
        cmpil   #0x50,%d0                   | b6 >= 0x50 is stock's
        bccw    ss_pass
        mvzb    %a0@(4),%d0
        cmpil   #5,%d0
        beqs    ss_go
        cmpil   #0x10,%d0
        bnew    ss_pass

ss_go:
        lea     %sp@(-32),%sp
        moveml  %d3-%d7/%a2-%a4,%sp@
        movel   %d1,%d7                     | the transport the request came on

        | raw frame header
        lea     ss_raw:l,%a2
        mvzw    ss_seq:l,%d0
        addql   #1,%d0
        movew   %d0,ss_seq:l
        movew   %d0,%a2@                    | msgId
        mvzb    %a0@(6),%d3                 | leader
        mvzb    %a0@(7),%d0                 | replyTo = the request's msgId
        btst    #6,%d3
        beqs    1f
        oril    #0x80,%d0
1:      moveb   %d0,%a2@(2)
        mvzb    %a0@(8),%d0
        btst    #5,%d3
        beqs    2f
        oril    #0x80,%d0
2:      moveb   %d0,%a2@(3)
        moveb   #0x84,%a2@(4)
        moveb   #1,%a2@(5)                  | ver
        movew   #128,%a2@(6)                | w
        movew   #64,%a2@(8)                 | h
        clrw    %a2@(10)                    | len = 0x00000400
        movew   #1024,%a2@(12)

        | the frame last sent to the panel, behind the header; masked, so
        | no flush swaps the pointers or reuses the buffer mid-copy
        lea     %a2@(14),%a1
        movew   %sr,%d1
        movew   #0x2700,%sr
        moveal  (FRONT).l,%a3
        movel   #255,%d0
3:      movel   %a3@+,%a1@+
        subql   #1,%d0
        bpls    3b
        movew   %d1,%sr

        | encoded message: F0 00 20 3C <id0> <id1> body F7
        lea     ss_enc:l,%a4
        moveb   #0xf0,%a4@+
        clrb    %a4@+
        moveb   #0x20,%a4@+
        moveb   #0x3c,%a4@+
        moveb   %a0@(4),%a4@+
        moveb   %a0@(5),%a4@+
        movel   %a2,%a3                     | src = raw
        movel   #RAW_LEN,%d3
4:      moveal  %a4,%a2                     | leader slot
        addql   #1,%a4
        clrl    %d4
        moveq   #6,%d5
5:      mvzb    %a3@+,%d0
        btst    #7,%d0
        beqs    6f
        bset    %d5,%d4
6:      andil   #0x7f,%d0
        moveb   %d0,%a4@+
        subql   #1,%d3
        beqs    7f
        subql   #1,%d5
        bpls    5b
7:      moveb   %d4,%a2@
        tstl    %d3
        bnes    4b
        moveb   #0xf7,%a4@+

        | out: USB when the request came over USB, else the MIDI OUT ring
        lea     ss_enc:l,%a3
        movel   %a4,%d3
        subl    %a3,%d3
        tstl    %d7
        beqs    ss_din
        lea     usbmidi_up:l,%a1
        movel   %a1,%d0
        beqs    ss_din
        tstb    %a1@
        beqs    ss_din
        lea     usbmidi_tx_busy:l,%a2
        movel   #0x400000,%d6               | give the host's last transfer time to finish
9:      tstb    %a2@
        beqs    10f
        subql   #1,%d6
        bnes    9b
        bras    ss_fin                      | the host is not reading EP2: no reply
10:     movew   %sr,%d1
        movew   #0x2700,%sr
        tstb    %a2@
        beqs    11f
        movew   %d1,%sr                     | the isr or a stock send took it first
        bras    9b
11:     moveq   #1,%d0
        moveb   %d0,%a2@                    | claim EP2 IN (the isr clears it)
        movew   %d1,%sr
        movel   %a3,%sp@-
        movel   %d3,%sp@-
        jsr     (ENCODER).l
        addql   #8,%sp
        bras    ss_fin

ss_din:
        tstl    (MIDI_HOLD).l
        bnes    ss_fin
8:      mvzb    %a3@+,%d0
        bsrs    ss_put
        subql   #1,%d3
        bnes    8b
        clrl    (RUN_STATUS).l
        moveq   #10,%d1
        movel   %d1,(TX_ACT).l

ss_fin:
        moveml  %sp@,%d3-%d7/%a2-%a4
        lea     %sp@(32),%sp
ss_done:
        movel   %sp@+,%d2
        rts

ss_pass:
        jmp     (STOCK_NEXT).l

| d0.b -> the MIDI OUT ring (d1, d6, a1 clobbered)
ss_put:
1:      movel   (RING_CNT).l,%d1
        cmpil   #4094,%d1
        bgts    1b
        movew   %sr,%d1
        movew   #0x2700,%sr
        movel   (RING_CNT).l,%d6
        addql   #1,%d6
        movel   %d6,(RING_CNT).l
        movel   (RING_IDX).l,%d6
        moveal  (RING_PTR).l,%a1
        moveb   %d0,%a1@(0,%d6:l)
        subql   #1,%d6
        andil   #4095,%d6
        movel   %d6,(RING_IDX).l
        moveq   #3,%d6
        moveb   %d6,(UART0_UIMR).l
        movew   %d1,%sr
        rts

        .section .bss
        .align  2
ss_raw: .skip   1040
ss_enc: .skip   1200
ss_seq: .skip   2
