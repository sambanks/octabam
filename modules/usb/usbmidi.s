| usbmidi.s -- the glue that completes the firmware's dormant USB-MIDI half.
| From markandrus/octemu custom/coldfire/usb-midi.s at 6a9ff68 (MIT), carried
| as a DRAM unit of octabam's platform instead of the in-image free zone his
| patch links it into. His text verbatim, and pinned to his blob's sha256,
| until 4 Nov 2026; since then octabam's: the TX queue is a 4 KB ring of whole
| messages (issue #1016, "TX queue" below), and the rest is his. The grown configuration descriptors are cfg.s (descriptors.py, per
| remix) and the responder's length clamps clamp.s.
|
| Five shims and a USB-MIDI RX decoder. The TX encoder, EP2 bring-up and
| EP2 primitives are the firmware's own dormant code (usb_midi_* in his
| re/coldfire.syms) -- this file only wires them in.
|
| Hooks (a 6-byte jmp planted by the build, displaced bytes replayed):
|   0x4001d9ca  SET_CONFIGURATION body   -> setcfg_shim (EP2 up + flag)
|   0x4001daec  CLEAR_FEATURE(halt)      -> clrfeat_shim (answer for EP2)
|   0x4001e606  usb_isr UI path          -> isr_shim (EP2 completions)
|   0x40010bc8  midi_send entry          -> send_shim (mirror to encoder)
|   0x400108b0  priority byte sender     -> prio_shim (realtime to encoder)
|
| ColdFire ISA notes: moveml has no -(sp)/(sp)+ forms (manual lea adjust,
| the firmware's own idiom), no ORI to SR (save SR, movew #0x2700, restore),
| and no immediate/mem-to-mem stores to absolute (route through a register).

| ---- firmware entry points (re/coldfire.syms) ----
.set EP2_INIT,      0x4001d0e4      | usb_midi_ep2_init
.set EP2_RX_PRIME,  0x4001d184      | usb_midi_rx_prime(buf)
.set ENCODER,       0x4001d204      | usb_midi_encoder(len, buf)
.set RX_ENQUEUE,    0x40092bbc      | midi_rx_enqueue(byte on stack)
.set RX_BUF,        0x4ecc9000      | usb_midi_rx_buf
.set EP2_RX_TD,     0x4ec953e4      | EP2 OUT dTD token (remaining<<16)
.set EPCOMPLETE,    0xfc0b01bc
.set QH_EP2OUT_W0,  0x4ec94900      | dQH word 0 (mult/zlt/maxpkt)
.set QH_EP2IN_W0,   0x4ec94940
.set PORTSC1,       0xfc0b0184      | port status/control (speed in bits 27:26)

    .text
    .global usbmidi_setcfg_shim, usbmidi_isr_shim
    .global usbmidi_send_shim, usbmidi_prio_shim

| ---- SET_CONFIGURATION body hook -----------------------------------------
| Hook at 0x4001d9ca, on the REAL SET_CONFIGURATION path (0x4001d8ce
| branches here at bnew when the request byte is nonzero). By this point
| EP0 IN status is primed and EP1 is up; bring EP2 up too.
| Displaced: pea 0x400b9868 (first arg of the MSC-task wakeup message).
usbmidi_setcfg_shim:
    lea     %sp@(-16),%sp
    moveml  %d0-%d1/%a0-%a1,%sp@
    jsr     EP2_INIT               | writes dQH word0 = 0x20400000 (mult1,64)
    | Match the EP2 dQH max packet to the NEGOTIATED port speed: the
    | dormant init leaves 64 (correct for full speed), only high speed
    | needs the 512-byte override, and it must agree with the FS/HS config
    | descriptor the responder serves by the same PORTSC1 speed bits.
    movel   PORTSC1,%d0
    moveq   #26,%d1
    lsrl    %d1,%d0
    andil   #3,%d0                 | bits 27:26: 0=FS 1=LS 2=HS
    moveq   #2,%d1
    cmpl    %d0,%d1
    bnes    1f                     | not high speed -> keep the init's 64
    movel   #0x22000000,%d0        | mult 1, max packet 512
    movel   %d0,QH_EP2OUT_W0
    movel   %d0,QH_EP2IN_W0
1:  moveq   #1,%d0
    moveb   %d0,usbmidi_up
    clrb    usbmidi_tx_busy
    moveml  %sp@,%d0-%d1/%a0-%a1
    lea     %sp@(16),%sp
    pea     0x400b9868             | displaced
    jmp     0x4001d9d0

| ---- CLEAR_FEATURE(ENDPOINT_HALT) hook -----------------------------------
| The stock handler at 0x4001daec accepts only endpoint 1 and STALLs any
| other, so a host clearing a halt on EP2 gets a stall. EP2 never halts, so
| this is a compliance edge, not a runtime path — but a shippable composite
| answers it. For EP2 (wIndex 0x02 / 0x82) clear the stall bits in
| ENDPTCTRL2 and ACK via the dormant EP0 zero-length status primitive; any
| other endpoint falls through to the stock handler unchanged.
| Displaced: movew 0x46c8ce0c,%d0 (raw wIndex, byte-reversed in memory).
.set QH_SETUP_WIDX, 0x46c8ce0c
.set ENDPTCTRL2,    0xfc0b01c8
.set EP0_STATUS_IN, 0x4001d524
usbmidi_clrfeat_shim:
    movew   QH_SETUP_WIDX,%d0      | displaced; d0 = raw wIndex (preserved)
    movel   %d0,%d2
    byterev %d2
    swap    %d2
    mvzw    %d2,%d2                | wIndex in host order
    moveq   #127,%d1
    andl    %d2,%d1                | endpoint number
    moveq   #2,%d2
    cmpl    %d1,%d2
    bnes    9f                     | not EP2 -> stock handler (d0 intact)
    movel   ENDPTCTRL2,%d1
    bclr    #0,%d1                 | RXS (EP2 OUT stall)
    bclr    #16,%d1                | TXS (EP2 IN stall)
    movel   %d1,ENDPTCTRL2
    jsr     EP0_STATUS_IN          | zero-length EP0 IN status = ACK
    jmp     0x4001de74             | control request done
9:  jmp     0x4001daf2             | stock CLEAR_FEATURE continuation

| ---- usb_isr UI hook ------------------------------------------------------
| Displaced (replayed at the end): movel 0xfc0b01ac,%d0. d0 is reloaded by
| the displaced instruction; everything else is saved.
usbmidi_isr_shim:
    lea     %sp@(-16),%sp
    moveml  %d1-%d2/%a0-%a1,%sp@
    movel   EPCOMPLETE,%d0
    andil   #0x00040004,%d0
    beqs    9f
    movel   %d0,EPCOMPLETE          | w1c the EP2 bits
    btst    #18,%d0                 | EP2 IN done -> transfer free, flush more
    beqs    1f
    clrb    usbmidi_tx_busy
    movel   %d0,%sp@-               | kick (via encoder) trashes d0/a-regs
    bsr     usbmidi_tx_kick         | drain whatever queued while busy
    movel   %sp@+,%d0
1:  btst    #2,%d0                  | EP2 OUT done -> decode + re-prime
    beqs    9f
    movel   EP2_RX_TD,%d1           | token: remaining<<16
    swap    %d1
    andil   #0x7fff,%d1
    moveq   #64,%d0
    subl    %d1,%d0                 | bytes actually received
    bles    2f
    bsrs    usbmidi_rx_decode
2:  pea     RX_BUF
    jsr     EP2_RX_PRIME
    addql   #4,%sp
9:  moveml  %sp@,%d1-%d2/%a0-%a1
    lea     %sp@(16),%sp
    movel   0xfc0b01ac,%d0
    jmp     0x4001e60c

| ---- USB-MIDI event packets -> raw DIN bytes ------------------------------
| d0 = byte count (multiple of 4) at RX_BUF. Feeds midi_rx_enqueue exactly
| as the UART0 ISR does (byte pushed as a long), interrupts masked so the
| FIFO indices cannot race the DIN path.
usbmidi_rx_decode:
    lea     %sp@(-20),%sp
    moveml  %d3-%d5/%a2-%a3,%sp@
    movew   %sr,%d5
    movew   #0x2700,%sr
    lea     RX_BUF,%a2
    lea     usbmidi_cin_len,%a3
    movel   %d0,%d3
    asrl    #2,%d3                  | event count
    bles    8f
3:  mvzb    %a2@,%d0
    moveq   #15,%d1
    andl    %d1,%d0
    mvzb    %a3@(0,%d0:l),%d4       | MIDI bytes in this event
    beqs    5f
    moveq   #0,%d2
4:  mvzb    %a2@(1,%d2:l),%d0
    movel   %d0,%sp@-
    jsr     RX_ENQUEUE
    addql   #4,%sp
    addql   #1,%d2
    cmpl    %d4,%d2
    blts    4b
5:  addql   #4,%a2
    subql   #1,%d3
    bgts    3b
8:  movew   %d5,%sr
    moveml  %sp@,%d3-%d5/%a2-%a3
    lea     %sp@(20),%sp
    rts

| ---- TX queue ---------------------------------------------------------------
| D1's single-dTD hole is closed by a software queue, not a dTD chain: both
| senders APPEND complete MIDI messages to a ring; a kick moves whole messages,
| up to TX_SND bytes, into the send buffer and encodes it through the dormant
| encoder as one transfer whenever EP2 IN is free, and the EP2-IN completion
| ISR kicks again until the ring is empty. The encoder never reads a buffer an
| append is writing. A message that does not fit in the ring, or is longer
| than TX_SND, increments usbmidi_tx_drops: loss is counted, never silent.
|
| Until 4 Nov 2026 (issue #1016) the queue was one 256-byte accumulator
| (markandrus's TX_CAP), so any burst longer than what fitted before the next
| completion lost its tail: CC 61's 283-CC dump (849 bytes in about 5 ms)
| reached the host with 102 to 172 messages on an MKI (xynta). The ring holds
| TX_RING bytes of [length hi, length lo, message] records.
| TX_SND bounds one transfer: the encoder (0x4001d204) writes up to 4 bytes per
| MIDI byte to 0x4ecc8000 with no bound, and usb_midi_rx_buf starts 4 KB later
| (0x4ecc9000), so a transfer must stay under 1,024 MIDI bytes; 512 keeps the
| interrupt-masked copy short. A message is never split (the encoder reads
| ahead inside a message: a SysEx cut in two would be framed wrongly).
.set TX_RING, 4096                  | a power of two
.set TX_MASK, TX_RING - 1
.set TX_SND,  512

| usbmidi_tx_append(len=%d0, buf=%a0): queue one complete message, then
| kick. Masks interrupts around the ring. Trashes %d0-%d3/%a0-%a1.
usbmidi_tx_append:
    tstl    %d0
    blew    9f                      | nothing to queue
    cmpil   #TX_SND,%d0
    bgtw    8f                      | can never go out whole: drop, count
    movew   %sr,%d2
    movew   #0x2700,%sr
    mvzw    usbmidi_tx_used,%d3
    addl    %d0,%d3
    addql   #2,%d3                  | used + the record (header + message)
    cmpil   #TX_RING,%d3
    bgtw    6f                      | the ring is full -> drop, count
    movew   %d3,usbmidi_tx_used
    mvzw    usbmidi_tx_acc_len,%d3
    addl    %d0,%d3
    movew   %d3,usbmidi_tx_acc_len  | MIDI bytes queued (headers not counted)
    lea     usbmidi_tx_acc,%a1
    mvzw    usbmidi_tx_head,%d1
    movel   %d0,%d3
    lsrl    #8,%d3
    moveb   %d3,%a1@(0,%d1:l)       | length, high byte
    addql   #1,%d1
    andil   #TX_MASK,%d1
    moveb   %d0,%a1@(0,%d1:l)       | length, low byte
    addql   #1,%d1
    andil   #TX_MASK,%d1
5:  moveb   %a0@+,%d3
    moveb   %d3,%a1@(0,%d1:l)
    addql   #1,%d1
    andil   #TX_MASK,%d1
    subql   #1,%d0
    bnes    5b
    movew   %d1,usbmidi_tx_head
    movew   %d2,%sr
    bra     usbmidi_tx_kick
6:  movew   %d2,%sr
8:  addql   #1,usbmidi_tx_drops
9:  rts

| usbmidi_tx_kick: if EP2 IN is free and the ring is non-empty, move whole
| messages (up to TX_SND bytes) into snd and encode it as one transfer. Masks
| only the move; the encode runs unmasked on the stable snd buffer (tx_busy
| serialises kicks). Trashes %d0-%d2/%a0-%a1 (usbmidi_isr_shim saves those);
| saves what else it uses.
usbmidi_tx_kick:
    lea     %sp@(-16),%sp
    moveml  %d3-%d5/%a2,%sp@
    movew   %sr,%d1
    movew   #0x2700,%sr
    tstb    usbmidi_tx_busy
    bnew    9f
    tstw    usbmidi_tx_acc_len
    beqw    9f                      | nothing queued
    moveq   #1,%d2
    moveb   %d2,usbmidi_tx_busy     | claim the transfer (reg -> abs)
    lea     usbmidi_tx_acc,%a0
    lea     usbmidi_tx_snd,%a1
    moveal  %a1,%a2                 | where the next message goes in snd
    mvzw    usbmidi_tx_tail,%d2     | the oldest record
    moveq   #0,%d3                  | bytes in snd
1:  mvzb    %a0@(0,%d2:l),%d4
    lsll    #8,%d4
    movel   %d2,%d5
    addql   #1,%d5
    andil   #TX_MASK,%d5
    mvzb    %a0@(0,%d5:l),%d0
    orl     %d0,%d4                 | d4 = this message's length
    movel   %d3,%d0
    addl    %d4,%d0
    cmpil   #TX_SND,%d0
    bgts    4f                      | it waits for the next transfer (never the first)
    movel   %d0,%d3
    mvzw    usbmidi_tx_used,%d0
    subl    %d4,%d0
    subql   #2,%d0
    movew   %d0,usbmidi_tx_used
    mvzw    usbmidi_tx_acc_len,%d0
    subl    %d4,%d0
    movew   %d0,usbmidi_tx_acc_len
2:  addql   #1,%d5
    andil   #TX_MASK,%d5
    moveb   %a0@(0,%d5:l),%d0
    moveb   %d0,%a2@+
    subql   #1,%d4
    bnes    2b
    addql   #1,%d5
    andil   #TX_MASK,%d5
    movel   %d5,%d2                 | the next record
    tstw    usbmidi_tx_acc_len
    bnes    1b
4:  movew   %d2,usbmidi_tx_tail
    movew   %d3,usbmidi_tx_snd_len
    movew   %d1,%sr                 | encode with interrupts restored
    movel   %a1,%sp@-               | buf
    movel   %d3,%sp@-               | len
    jsr     ENCODER
    addql   #8,%sp
    bras    8f
9:  movew   %d1,%sr
8:  moveml  %sp@,%d3-%d5/%a2
    lea     %sp@(16),%sp
    rts

| ---- midi_send entry hook -------------------------------------------------
| Stack on entry: sp@(4)=len, sp@(8)=buf. Queue the whole message, then run
| the displaced prologue and continue into midi_send unchanged.
usbmidi_send_shim:
    tstb    usbmidi_up
    beqs    0f
    lea     %sp@(-24),%sp          | ColdFire moveml has no -(sp) form
    moveml  %d0-%d3/%a0-%a1,%sp@
    movel   %sp@(28),%d0           | len (orig sp@(4) + 24 saved)
    moveal  %sp@(32),%a0           | buf (orig sp@(8) + 24 saved)
    bsr     usbmidi_tx_append
    moveml  %sp@,%d0-%d3/%a0-%a1
    lea     %sp@(24),%sp
0:  lea     %sp@(-20),%sp           | displaced midi_send prologue
    moveml  %d2-%d5/%a2,%sp@
    jmp     0x40010bd0

| ---- priority (realtime) byte sender hook ---------------------------------
| Stack on entry: sp@(4)=byte as long (LSB at sp@(7)).
usbmidi_prio_shim:
    tstb    usbmidi_up
    beqs    0f
    lea     %sp@(-24),%sp
    moveml  %d0-%d3/%a0-%a1,%sp@
    moveb   %sp@(31),%d0           | the byte (orig sp@(7) + 24 saved)
    moveb   %d0,usbmidi_tmpbyte
    lea     usbmidi_tmpbyte,%a0
    moveq   #1,%d0
    bsr     usbmidi_tx_append
    moveml  %sp@,%d0-%d3/%a0-%a1
    lea     %sp@(24),%sp
0:  movel   %d2,%sp@-               | displaced priority-sender entry
    moveb   %sp@(11),%d1
    jmp     0x400108b6

| ---- data -----------------------------------------------------------------
    .balign 2
usbmidi_cin_len:
    .byte   0,0,2,3,3,1,2,3,3,3,3,3,2,2,3,1
    .global usbmidi_up, usbmidi_tx_busy, usbmidi_tx_drops
    .global usbmidi_tx_acc, usbmidi_tx_acc_len, usbmidi_tx_head, usbmidi_tx_tail, usbmidi_tx_used
usbmidi_up:      .byte 0
usbmidi_tx_busy: .byte 0
usbmidi_tmpbyte: .byte 0
    .balign 2
usbmidi_tx_acc_len: .word 0         | MIDI bytes queued in the ring
usbmidi_tx_snd_len: .word 0
usbmidi_tx_head:    .word 0         | ring index of the next record
usbmidi_tx_tail:    .word 0         | ring index of the oldest record
usbmidi_tx_used:    .word 0         | ring bytes in use, headers included
    .balign 4
usbmidi_tx_drops:   .long 0
usbmidi_tx_acc:  .space TX_RING     | the ring
usbmidi_tx_snd:  .space TX_SND
    .balign 2
