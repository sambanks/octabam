| usbmidi.s -- the glue that completes the firmware's dormant USB-MIDI half.
| markandrus/octemu custom/coldfire/usb-midi.s at 6a9ff68 (MIT), his text
| verbatim: the build re-links this unit at his zone address 0x400d24f0 on
| every build and compares it with his blob's sha256 (manifest.py
| Linked.reference), so it is his bytes, carried as a DRAM unit of
| octabam's platform instead of the in-image free zone his patch links it
| into. The grown configuration descriptors are cfg.s (descriptors.py, per
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
1:  bsr     usbmidi_tx_reset        | nothing queued for an old session goes out in this one
    moveq   #1,%d0
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

| ---- TX queue -------------------------------------------------------------
| D1's single-dTD hole is closed by a software queue, not a dTD chain. Senders
| append complete MIDI messages; a kick flushes them through the dormant
| encoder as one transfer whenever EP2 IN is free, and the EP2-IN completion
| ISR kicks again. Two stages:
|   acc  (TX_CAP bytes)  the next transfer's bytes; a message that fits goes
|                        here directly while the ring is empty
|   ring (RING_CAP)      whole messages as [len][bytes], in arrival order,
|                        for a burst longer than acc holds
| snd is the transfer being encoded, so the encoder never reads a buffer an
| append is writing. A kick moves whole ring messages into acc before it swaps.
| A message longer than 255 bytes, or one the ring has no room for, increments
| usbmidi_tx_drops: loss is counted, never silent.
.set TX_CAP,   256
.set RING_CAP, 4096                     | power of two

| usbmidi_tx_append(len=%d0, buf=%a0): queue one complete message, then
| kick. Masks interrupts around the queue. Trashes %d0-%d3/%a0-%a1.
usbmidi_tx_append:
    tstl    %d0
    jle     9f                      | nothing to queue
    movew   %sr,%d2
    movew   #0x2700,%sr
    cmpil   #255,%d0
    jgt     6f                      | longer than a ring record -> drop, count
    mvzw    usbmidi_tx_rhead,%d1
    mvzw    usbmidi_tx_rtail,%d3
    cmpl    %d3,%d1
    bnes    4f                      | older messages wait in the ring: queue behind them
    mvzw    usbmidi_tx_acc_len,%d1  | d1 = acc_len
    movel   %d1,%d3
    addl    %d0,%d3                 | d3 = acc_len + len (proposed)
    cmpil   #TX_CAP,%d3
    bgts    4f                      | does not fit acc -> ring
    lea     usbmidi_tx_acc,%a1
    addal   %d1,%a1                 | dest = &acc[acc_len]
5:  moveb   %a0@+,%a1@+
    subql   #1,%d0
    bnes    5b
    movew   %d3,usbmidi_tx_acc_len  | acc_len = acc_len + len
    movew   %d2,%sr
    bra     usbmidi_tx_kick
4:  mvzw    usbmidi_tx_rhead,%d1    | free = (head - tail - 1) mod RING_CAP
    mvzw    usbmidi_tx_rtail,%d3
    subl    %d3,%d1
    subql   #1,%d1
    andil   #RING_CAP-1,%d1
    movel   %d0,%d3
    addql   #1,%d3                  | record = len byte + message
    cmpl    %d3,%d1
    blts    6f                      | no room -> drop, count
    mvzw    usbmidi_tx_rtail,%d1
    lea     usbmidi_tx_ring,%a1
    moveb   %d0,%a1@(0,%d1:l)       | len byte
    addql   #1,%d1
    andil   #RING_CAP-1,%d1
3:  moveb   %a0@+,%d3
    moveb   %d3,%a1@(0,%d1:l)
    addql   #1,%d1
    andil   #RING_CAP-1,%d1
    subql   #1,%d0
    bnes    3b
    movew   %d1,usbmidi_tx_rtail
    movew   %d2,%sr
    bra     usbmidi_tx_kick
6:  addql   #1,usbmidi_tx_drops
    movew   %d2,%sr
9:  rts

| usbmidi_tx_refill: move whole ring messages into acc while the next one
| fits. Caller has interrupts masked. Preserves %d1/%d3/%d4; trashes
| %d0/%d2/%a0/%a1.
usbmidi_tx_refill:
    movel   %d1,%sp@-
    movel   %d3,%sp@-
    movel   %d4,%sp@-
1:  mvzw    usbmidi_tx_rhead,%d1
    mvzw    usbmidi_tx_rtail,%d0
    cmpl    %d0,%d1
    beqs    8f                      | ring empty
    lea     usbmidi_tx_ring,%a0
    mvzb    %a0@(0,%d1:l),%d2       | d2 = message length
    mvzw    usbmidi_tx_acc_len,%d3
    movel   %d3,%d4
    addl    %d2,%d4
    cmpil   #TX_CAP,%d4
    bgts    8f                      | the next message does not fit acc
    movew   %d4,usbmidi_tx_acc_len
    lea     usbmidi_tx_acc,%a1
    addal   %d3,%a1                 | dest = &acc[old acc_len]
    addql   #1,%d1
    andil   #RING_CAP-1,%d1
2:  mvzb    %a0@(0,%d1:l),%d0
    moveb   %d0,%a1@+
    addql   #1,%d1
    andil   #RING_CAP-1,%d1
    subql   #1,%d2
    bnes    2b
    movew   %d1,usbmidi_tx_rhead
    bra     1b
8:  movel   %sp@+,%d4
    movel   %sp@+,%d3
    movel   %sp@+,%d1
    rts

| usbmidi_tx_reset: drop everything queued (acc and ring). Saves its own SR.
| Trashes %d0.
usbmidi_tx_reset:
    movew   %sr,%d0
    movew   #0x2700,%sr
    clrw    usbmidi_tx_acc_len
    clrw    usbmidi_tx_rhead
    clrw    usbmidi_tx_rtail
    movew   %d0,%sr
    rts

| usbmidi_tx_kick: if EP2 IN is free and something is queued, top acc up from
| the ring, swap acc->snd and encode snd as one transfer. Masks only the
| refill and swap; the encode runs unmasked on the stable snd buffer
| (tx_busy serialises kicks).
usbmidi_tx_kick:
    movew   %sr,%d1
    movew   #0x2700,%sr
    tstb    usbmidi_tx_busy
    bnes    9f
    bsr     usbmidi_tx_refill
    mvzw    usbmidi_tx_acc_len,%d0
    beqs    9f                      | nothing queued
    moveq   #1,%d2
    moveb   %d2,usbmidi_tx_busy     | claim the transfer (reg -> abs)
    movew   %d0,usbmidi_tx_snd_len  | remember length for the encode
    lea     usbmidi_tx_acc,%a0
    lea     usbmidi_tx_snd,%a1
7:  moveb   %a0@+,%a1@+             | swap acc -> snd (d0 > 0 guaranteed)
    subql   #1,%d0
    bnes    7b
    clrw    usbmidi_tx_acc_len
    movew   %d1,%sr                 | encode with interrupts restored
    mvzw    usbmidi_tx_snd_len,%d0
    lea     usbmidi_tx_snd,%a0
    movel   %a0,%sp@-               | buf
    movel   %d0,%sp@-              | len
    jsr     ENCODER
    addql   #8,%sp
    rts
9:  movew   %d1,%sr
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
    .global usbmidi_up, usbmidi_tx_busy, usbmidi_tx_drops, usbmidi_tx_reset
usbmidi_up:      .byte 0
usbmidi_tx_busy: .byte 0
usbmidi_tmpbyte: .byte 0
    .balign 2
usbmidi_tx_acc_len: .word 0
usbmidi_tx_snd_len: .word 0
usbmidi_tx_rhead:   .word 0
usbmidi_tx_rtail:   .word 0
usbmidi_tx_drops:   .long 0
usbmidi_tx_acc:  .space TX_CAP
usbmidi_tx_snd:  .space TX_CAP
usbmidi_tx_ring: .space RING_CAP
    .balign 2
