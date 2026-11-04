| usbmidi_rx.s -- the USB-MIDI receive path, in front of usbmidi.s.
| octabam. usbmidi.s stays markandrus's bytes (manifest.py Linked.reference);
| the two detours that reached its SET_CONFIGURATION and usb_isr shims reach
| these, which hand over to them.
|
| What usbmidi.s's decoder does with a packet: SR = 0x2700 for the whole packet,
| one midi_rx_enqueue (0x40092bbc) per MIDI byte. midi_rx_enqueue has no full
| check: it writes ring[head], head++ (wrap at 32), count++, forces INTC source 36.
| The consumer, the MIDI framer 0x40092bf4, pops one byte per interrupt, and
| runs at the same INTC level (4) as the USB interrupt, so it cannot run inside
| the USB ISR whatever SR is. A packet of more than 32 MIDI bytes overwrites
| unread bytes (16 note-ons = 48 bytes: notes 0x35..0x3f reached the parser,
| 0x3b..0x3f twice, 0x30..0x34 never; README.md "Receive path").
|
| Here:
|  * Before an event's bytes are enqueued, count (0x46100b7c) + the event's
|    bytes must fit in 32. If not, the framer is run once from here (a fabricated
|    exception frame, so its rte returns to us): it pops one byte, parses it and
|    posts what it completes, exactly what its interrupt would do.
|  * The enqueues of one event run at SR 0x2700 (a DIN byte cannot land between
|    the bytes of one message); the framer runs at the SR the ISR entered with.
|  * The RX dTD is sized to the endpoint's max packet: 512 at high speed (the
|    dormant init primes 64), so a packet of up to 128 events is one transfer.
|    At full speed (max packet 64) the stock 64-byte dTD already matches.
|  * A dTD that completed with halted / data buffer error / transaction error
|    status is counted in usbmidi_rx_errs and not decoded.
|  * A bus reset and a session end (the cable pulled) take EP2 down: the
|    transmit queue's state is cleared and both directions are flushed, so
|    nothing is primed on EP2 until the host configures the device again,
|    and SET_CONFIGURATION flushes EP2 before the dormant init rewrites its
|    queue heads (see "Bus reset and session end" below).
|  * Each 0xF8 is timestamped before it is enqueued, as the UART0 ISR does
|    (0x4001070a..0x4001071e): DTCN0 into CLK_T, the delta into CLK_DT. The
|    clock handler 0x40005a48 builds the tempo (0x80001818, 0x80001814) from
|    that delta; without it USB clock steps the sequencer and leaves the tempo
|    at the project's, or at the last DIN clock's.
|  * One clock source at a time, DIN first (#944). Both sources reach the
|    one FIFO, framer and clock handler, so DIN and USB clock together are
|    one stream of twice the ticks: the sequencer steps on both and the
|    handler's interval ring reads the gaps between them (120 + 120 BPM
|    read 5267..6424, and the tempo was copied into the project's TEMPOx24).
|    A USB clock or transport event (0xF8, 0xFA, 0xFB, 0xFC, 0xF2) is dropped
|    whole while DIN is clocking: CLK_T was written by someone other than
|    this decoder (it differs from usbmidi_rx_clk_t, the last stamp written
|    here) less than CLK_GAP counts ago. CLK_GAP is the clock handler's
|    resync gap (0x40005a96), so the first USB tick taken after DIN stops
|    carries a delta past it and the handler starts a fresh ring.
|  * A completion between the two ENDPTCOMPLETE reads (#1017). This unit's ISR
|    shim reads ENDPTCOMPLETE, takes an EP2 OUT completion and re-primes the
|    512-byte dTD, then hands over to usbmidi_isr_shim, which reads it again and
|    still takes bit 2 the 64-byte way: a transfer completing in between was
|    w1c'd there as 64 - remaining <= 0 bytes, never decoded, and the stock
|    64-byte prime left usbmidi_rx_state at 2, so the next transfer decoded as
|    448 + n bytes (an older transfer's tail replayed; port: 500 of 1,000 short
|    transfers lost, 55,888 stale events). That branch ends in the stock
|    usb_midi_rx_prime, and is the only path that reaches it at state 2, so a
|    detour there (usbmidi_rx_late_shim) decodes what it did not -- all of it,
|    or for n > 448 the bytes past the n - 448 its own decoder took -- and
|    re-primes the 512-byte dTD. usbmidi.s's bytes are unchanged.

.set EP2_RX_PRIME,  0x4001d184      | usb_midi_rx_prime(buf), the 64-byte form
.set RX_ENQUEUE,    0x40092bbc      | midi_rx_enqueue(byte on stack)
.set FRAMER,        0x40092bf4      | MIDI framer, INTC source 36 handler, ends in rte
.set FIFO_COUNT,    0x46100b7c
.set DTCN0,         0xfc07000c      | DMA timer 0 count (DTIN0 pin)
.set CLK_T,         0x46c8345a      | DTCN0 at the last 0xF8
.set CLK_DT,        0x46c83466      | DTCN0 delta between the last two 0xF8: the MIDI clock handler's tempo input
.set CLK_GAP,       1881600         | DTCN0 counts (167 ms): the clock handler's resync gap (0x40005a96)
.set RX_BUF,        0x4ecc9000      | usb_midi_rx_buf; its 4 KB page holds nothing else
.set EP2_RX_DTD,    0x4ec953e0      | next-dTD word; token at +4, buffer at +8
.set EP2_RX_TD,     0x4ec953e4
.set QH_EP2OUT_TOK, 0x4ec9490c      | dQH overlay token
.set QH_EP2IN_TOK,  0x4ec9494c      | EP2 IN dQH overlay token (QH_EP2IN_W0 0x4ec94940 + 0x0c)
.set QH_PTR_EP2OUT, 0x46c8ce14      | pointer to the EP2 OUT dQH
.set EPCOMPLETE,    0xfc0b01bc
.set ENDPTPRIME,    0xfc0b01b0
.set ENDPTFLUSH,    0xfc0b01b4
.set ENDPTSTAT,     0xfc0b01b8
.set EP2_BITS,      0x00040004      | EP2 IN (bit 18) and EP2 OUT (bit 2), in every ENDPT* register
.set PORTSC1,       0xfc0b0184
.set TD_STOCK64,    0x00408080      | what the dormant init writes: 64 bytes, IOC, ACTIVE
.set TD_512,        0x02008080      | 512 bytes, IOC, ACTIVE
.set TD_ERRORS,     0x68            | status bits: halted, data buffer error, transaction error

    .text
    .global usbmidi_rx_setcfg_shim, usbmidi_rx_isr_shim
    .global usbmidi_rx_reset_shim, usbmidi_rx_sessend_shim, usbmidi_rx_bus_end
    .global usbmidi_rx_state, usbmidi_rx_errs, usbmidi_rx_clk_t, usbmidi_rx_dropped
    .global usbmidi_rx_late_shim, usbmidi_rx_late

| ---- SET_CONFIGURATION hook (replaces usbmidi.s's detour) ------------------
| Live at the hook: d0-d1 (usbmidi_setcfg_shim saves them). Records whether
| the endpoint's dTD has to be re-sized once EP2_INIT has primed it:
| usbmidi_rx_state 1 = high speed, still the dormant init's 64-byte dTD.
| First, EP2 comes down: usbmidi_up cleared (no new message is queued while
| the queue heads are rewritten) and both directions flushed, because
| EP2_INIT rewrites the queue heads and a dTD still primed from an earlier
| session must not be in flight underneath it (usbaudio.s's EP3 rule).
| usbmidi_setcfg_shim then sets usbmidi_up and clears usbmidi_tx_busy.
usbmidi_rx_setcfg_shim:
    bsr     usbmidi_rx_bus_end
    lea     %sp@(-8),%sp
    moveml  %d0-%d1,%sp@
    movel   PORTSC1,%d0
    moveq   #26,%d1
    lsrl    %d1,%d0
    andil   #3,%d0                  | bits 27:26: 2 = HS
    moveq   #0,%d1
    cmpil   #2,%d0
    bnes    1f
    moveq   #1,%d1
1:  moveb   %d1,usbmidi_rx_state
    moveml  %sp@,%d0-%d1
    lea     %sp@(8),%sp
    jmp     usbmidi_setcfg_shim

| ---- usb_isr UI hook (replaces usbmidi.s's detour) --------------------------
| Takes EP2 OUT completions, then hands over to usbmidi_isr_shim, which sees
| only the EP2 IN bit and replays the displaced instruction. d0 is reloaded
| by that replay; the rest is saved here.
usbmidi_rx_isr_shim:
    lea     %sp@(-36),%sp
    moveml  %d1-%d5/%a0-%a3,%sp@
    tstb    usbmidi_up
    beqw    9f
    movel   EPCOMPLETE,%d0
    btst    #2,%d0
    bnes    2f
    | no completion: re-size the dormant init's still-pending 64-byte dTD
    mvzb    usbmidi_rx_state,%d0
    cmpil   #1,%d0
    bnew    9f
    movel   EP2_RX_TD,%d0
    cmpil   #TD_STOCK64,%d0
    bnew    9f
    bsr     usbmidi_rx_flush
    bsr     usbmidi_rx_prime
    braw    9f
2:  moveq   #4,%d1
    movel   %d1,EPCOMPLETE          | w1c EP2 OUT
    movel   EP2_RX_TD,%d1           | token: remaining<<16, status in 7:0
    movel   %d1,%d2
    swap    %d2
    andil   #0x7fff,%d2             | remaining
    moveq   #64,%d0                 | what the dTD was primed with
    mvzb    usbmidi_rx_state,%d3
    cmpil   #2,%d3
    bnes    3f
    movel   #512,%d0
3:  subl    %d2,%d0                 | bytes received
    andil   #TD_ERRORS,%d1
    beqs    4f
    addql   #1,usbmidi_rx_errs
    bras    5f
4:  tstl    %d0
    bles    5f
    bsr     usbmidi_rx_decode
5:  mvzb    usbmidi_rx_state,%d0
    beqs    6f
    bsr     usbmidi_rx_prime        | high speed: 512-byte dTD
    bras    9f
6:  pea     RX_BUF                  | full speed: the firmware's own 64-byte prime
    jsr     EP2_RX_PRIME
    addql   #4,%sp
9:  moveml  %sp@,%d1-%d5/%a0-%a3
    lea     %sp@(36),%sp
    jmp     usbmidi_isr_shim

| ---- usb_midi_rx_prime entry (0x4001d184), issue #1017 -------------------
| Displaced (replayed on the stock path): movel #TD_STOCK64,%d0. At 4(sp): the
| buffer (the stock argument). At usbmidi_rx_state 2 the caller is
| usbmidi_isr_shim's 64-byte branch, for an EP2 OUT completion that landed after
| this unit's ISR shim read ENDPTCOMPLETE (it has already w1c'd the bit). The
| dTD's token still holds that completion: decode it here and prime 512 again,
| instead of the stock 64-byte prime. A token still ACTIVE completed nothing:
| the 512-byte dTD stays primed. Any other state goes on to stock.
usbmidi_rx_late_shim:
    lea     %sp@(-36),%sp
    moveml  %d1-%d5/%a0-%a3,%sp@
    mvzb    usbmidi_rx_state,%d0
    cmpil   #2,%d0
    bnew    8f                      | not the late branch: the stock prime
    movel   EP2_RX_TD,%d1           | token: remaining<<16, status in 7:0
    btst    #7,%d1
    bnew    7f                      | still ACTIVE: nothing completed, keep it
    addql   #1,usbmidi_rx_late
    movel   %d1,%d2
    swap    %d2
    andil   #0x7fff,%d2             | remaining
    movel   #512,%d0
    subl    %d2,%d0                 | n, the bytes received
    andil   #TD_ERRORS,%d1
    beqs    1f
    addql   #1,usbmidi_rx_errs
    bras    6f
1:  movel   #448,%d1                | usbmidi.s decoded 64 - remaining = n - 448
    movel   %d0,%d2                 | bytes from RX_BUF itself when that was > 0
    subl    %d1,%d2
    bgts    2f
    moveq   #0,%d2
2:  subl    %d2,%d0                 | what is left, from RX_BUF + d2
    bles    6f
    lea     RX_BUF,%a2
    addal   %d2,%a2
    bsr     usbmidi_rx_decode_a2
6:  bsr     usbmidi_rx_prime        | the 512-byte dTD again (state stays 2)
7:  moveml  %sp@,%d1-%d5/%a0-%a3
    lea     %sp@(36),%sp
    rts                             | to usbmidi_isr_shim, past the stock prime
8:  moveml  %sp@,%d1-%d5/%a0-%a3
    lea     %sp@(36),%sp
    movel   #TD_STOCK64,%d0         | the displaced instruction
    jmp     0x4001d18a

| usbmidi_rx_flush: take the primed EP2 OUT dTD back (ENDPTFLUSH bit 2, until
| the flush and ENDPTSTAT have both cleared, bounded) and clear the overlay.
usbmidi_rx_flush:
    moveq   #4,%d1
    movel   #0x1000,%d2
1:  movel   %d1,ENDPTFLUSH
2:  movel   ENDPTFLUSH,%d0
    andl    %d1,%d0
    beqs    3f
    subql   #1,%d2
    bgts    2b
    bras    4f
3:  movel   ENDPTSTAT,%d0
    andl    %d1,%d0
    beqs    4f
    subql   #1,%d2
    bgts    1b
4:  moveq   #0,%d0
    movel   %d0,QH_EP2OUT_TOK
    rts

| ---- Bus reset and session end ----------------------------------------------
| usbmidi.s sets usbmidi_up at SET_CONFIGURATION and nothing clears it, and
| usbmidi_tx_busy is cleared only by an EP2 IN completion or SET_CONFIGURATION.
| The unit is mains powered, so both outlive a cable pull. Measured on Ignorato's
| MKII (OCTABAM14, macOS and two Windows 10 hosts, 7-9 Oct 2026): transmit
| works on the first connection after boot and never after an unplug and
| replug; a bus reset with the cable in does not do it. Under the port
| (verify_usb_midi_replug) the session end leaves usbmidi_up = 1, the unit
| goes on queueing clock and primes EP2 IN with USBCMD.RS clear, and the
| bytes queued while unplugged go out after the next SET_CONFIGURATION.
| How silicon then loses EP2 IN for good is inferred, not measured: a prime
| the controller has not taken survives a flush, and EP2_INIT rewrites the
| queue head of a primed endpoint (the ChipIdea hazard usbaudio.s guards
| EP3 against).
|
| Installed at the same two sites as USB AUDIO's audio_reset_shim and
| audio_sessend_shim (0x4001e91c, the USBSTS.URI handler; 0x4001e952,
| OTGSC.BSVIS session end); with a USB AUDIO module in the remix those
| override these detours and call usbmidi_rx_bus_end themselves.
| The ISR prologue has saved d0-d2/a0-a4; usbmidi_rx_bus_end saves what it
| uses anyway, and a2 (live on the session-end path) is not touched.
|
| Reset: displaced jsr %pc@(0x4001d6b8); moveq #64,%d0; rejoin 0x4001e922.
usbmidi_rx_reset_shim:
    jsr     0x4001d6b8              | displaced: the stock reset handling (flush, tokens, ENDPTCTRL1)
    bsr     usbmidi_rx_bus_end
    moveq   #64,%d0                 | displaced: USBSTS.URI, written back at 0x4001e922
    jmp     0x4001e922

| Session end: displaced movel 0xfc0b0140,%d0 (USBCMD); rejoin 0x4001e958,
| before the stock code clears USBCMD.RS, so the flush runs on a running
| controller.
usbmidi_rx_sessend_shim:
    bsr     usbmidi_rx_bus_end
    movel   0xfc0b0140,%d0          | displaced
    jmp     0x4001e958

| usbmidi_rx_bus_end: EP2 down until the next SET_CONFIGURATION. The senders
| stop queueing (usbmidi_up = 0), the transfer slot is free (tx_busy = 0),
| what was queued for the old session is dropped (a stale clock is worth
| nothing to the next host), and both EP2 directions are flushed. The
| accumulator length is usbmidi.s's local usbmidi_tx_acc_len, at
| usbmidi_up + 4 in his verbatim layout (up, tx_busy, tmpbyte, .balign 2):
| Linked.reference pins those bytes and verify_usb_midi_replug checks the
| offset. Interrupts are masked for the three stores, as usbmidi.s masks its
| own accumulator. Saves everything it uses.
| usbmidi_tx_kick sets tx_busy and runs the encoder with interrupts unmasked;
| a reset or session end in that window is followed by the encoder's EP2 IN
| prime. The flush here at SET_CONFIGURATION cancels it before EP2_INIT.
usbmidi_rx_bus_end:
    lea     %sp@(-16),%sp
    moveml  %d0-%d3,%sp@
    movew   %sr,%d3
    movew   #0x2700,%sr
    clrb    usbmidi_up
    clrb    usbmidi_tx_busy
    clrw    usbmidi_up+4            | usbmidi_tx_acc_len
    movew   %d3,%sr
    bsr     usbmidi_rx_ep2_flush
    moveml  %sp@,%d0-%d3
    lea     %sp@(16),%sp
    rts

| usbmidi_rx_ep2_flush: cancel whatever EP2 has primed, both directions. The
| documented ChipIdea sequence, as usbaudio.s's audio_ep3_flush, plus a wait
| for ENDPTPRIME first: a prime the controller has not yet taken is not
| cancelled by a flush. Then ENDPTFLUSH, until it clears; repeated while
| ENDPTSTAT still shows either bit. Every wait is bounded (16 x 65,536
| polls): a controller that never answers must not wedge the USB ISR.
| Then both queue heads' overlay tokens are cleared (a flushed dTD still
| reads ACTIVE) and any EP2 completion is dropped. Clobbers d0-d3.
usbmidi_rx_ep2_flush:
    movel   #EP2_BITS,%d1
    movel   #0x10000,%d3
1:  movel   ENDPTPRIME,%d0
    andl    %d1,%d0
    beqs    2f
    subql   #1,%d3
    bnes    1b
2:  moveq   #16,%d2                 | attempts
3:  movel   %d1,ENDPTFLUSH
    movel   #0x10000,%d3            | polls
4:  movel   ENDPTFLUSH,%d0
    andl    %d1,%d0
    beqs    5f
    subql   #1,%d3
    bnes    4b
5:  movel   ENDPTSTAT,%d0
    andl    %d1,%d0
    beqs    6f                      | neither direction primed: done
    subql   #1,%d2
    bnes    3b
6:  moveq   #0,%d0
    movel   %d0,QH_EP2OUT_TOK
    movel   %d0,QH_EP2IN_TOK
    movel   %d1,EPCOMPLETE          | w1c: no stale EP2 completion
    rts

| usbmidi_rx_prime: usb_midi_rx_prime with a 512-byte token; state = 2.
usbmidi_rx_prime:
    movel   #TD_512,%d0
    movel   %d0,EP2_RX_TD
    movel   #RX_BUF,%d0
    movel   %d0,EP2_RX_TD+4
    lea     EP2_RX_DTD,%a1
    movel   #0xdead0001,%d0         | next-dTD: terminate
    movel   %d0,%a1@
    moveal  QH_PTR_EP2OUT,%a0
    movel   %a1,%a0@(8)
    lea     ENDPTPRIME,%a0
    movel   %a0@,%d0
    moveq   #4,%d1
    orl     %d1,%d0
    movel   %d0,%a0@
    moveq   #2,%d0
    moveb   %d0,usbmidi_rx_state
    rts

| usbmidi_rx_decode: d0 = byte count (a multiple of 4) at RX_BUF. Event
| packets -> midi_rx_enqueue, as usbmidi.s's decoder does, with room made first
| and each 0xF8 timestamped.
| Trashes d0-d5/a0-a3; d5 = the entry SR.
usbmidi_rx_decode:
    lea     RX_BUF,%a2
| usbmidi_rx_decode_a2: the same, from a2 (usbmidi_rx_late_shim's remainder).
usbmidi_rx_decode_a2:
    lea     usbmidi_rx_cin_len,%a3
    movel   %d0,%d3
    asrl    #2,%d3                  | event count
    blew    8f
    movew   %sr,%d5
3:  mvzb    %a2@,%d0
    moveq   #15,%d1
    andl    %d1,%d0
    mvzb    %a3@(0,%d0:l),%d4       | MIDI bytes in this event
    beqs    5f
4:  movew   #0x2700,%sr
    movel   FIFO_COUNT,%d0
    addl    %d4,%d0
    moveq   #32,%d1
    cmpl    %d0,%d1
    bges    6f                      | the event fits
    movew   %d5,%sr
    bsr     usbmidi_rx_run_framer
    bras    4b
6:  bsr     usbmidi_rx_din_owns
    beqs    10f
    addql   #1,usbmidi_rx_dropped   | DIN is clocking: the event is not enqueued
    bras    11f
10: moveq   #0,%d2
7:  mvzb    %a2@(1,%d2:l),%d0
    cmpil   #0xf8,%d0
    bnes    9f
    movel   DTCN0,%d1
    movel   %d1,%d0
    subl    CLK_T,%d0
    movel   %d0,CLK_DT
    movel   %d1,CLK_T
    movel   %d1,usbmidi_rx_clk_t
    mvzb    %a2@(1,%d2:l),%d0       | the 0xF8 again
9:  movel   %d0,%sp@-
    jsr     RX_ENQUEUE
    addql   #4,%sp
    addql   #1,%d2
    cmpl    %d4,%d2
    blts    7b
11: movew   %d5,%sr
5:  addql   #4,%a2
    subql   #1,%d3
    bgts    3b
8:  rts

| usbmidi_rx_din_owns: at SR 0x2700, a2 = the event. Z clear (d0 = 1) when
| the event is a clock or transport message and DIN is clocking: CLK_T is not
| the last stamp this decoder wrote and is under CLK_GAP old. A stale foreign
| CLK_T is adopted as ours, so a DTCN0 wrap (2^32 counts, 380 s) cannot make
| a DIN tick from long ago look recent. Trashes d0-d1.
usbmidi_rx_din_owns:
    mvzb    %a2@(1),%d0
    cmpil   #0xf8,%d0
    beqs    1f
    cmpil   #0xfa,%d0
    bcss    3f                      | below 0xFA (0xF2 is checked below)
    cmpil   #0xfc,%d0
    blss    1f                      | 0xFA, 0xFB, 0xFC
    bras    4f
3:  cmpil   #0xf2,%d0
    bnes    4f
1:  movel   CLK_T,%d0
    cmpl    usbmidi_rx_clk_t,%d0
    beqs    4f                      | the last 0xF8 stamped was ours
    movel   DTCN0,%d1
    subl    %d0,%d1                 | the DIN tick's age
    cmpil   #CLK_GAP,%d1
    blss    5f                      | younger than the gap: DIN owns the clock
    movel   %d0,usbmidi_rx_clk_t    | stale: adopt it
4:  moveq   #0,%d0
    rts
5:  moveq   #1,%d0
    rts

| usbmidi_rx_run_framer: one pass of the framer, entered as its interrupt
| would: the long exception frame (format 4, vector 0x64, the current SR)
| over a return address, so its rte lands on the rts. Pops one FIFO byte.
usbmidi_rx_run_framer:
    movew   %sr,%d0
    mvzw    %d0,%d0
    oril    #0x41900000,%d0
    lea     1f,%a0
    movel   %a0,%sp@-
    movel   %d0,%sp@-
    jmp     FRAMER
1:  rts

    .balign 2
usbmidi_rx_cin_len:
    .byte   0,0,2,3,3,1,2,3,3,3,3,3,2,2,3,1
usbmidi_rx_state: .byte 0
    .balign 4
usbmidi_rx_errs:  .long 0
usbmidi_rx_clk_t: .long 0           | DTCN0 at the last 0xF8 this decoder stamped
usbmidi_rx_dropped: .long 0         | USB clock and transport events dropped while DIN clocked
usbmidi_rx_late:  .long 0           | EP2 OUT completions taken at usb_midi_rx_prime (#1017)
