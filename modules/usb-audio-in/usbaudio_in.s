| usbaudio_in.s -- USB AUDIO IN: the host's channels standing in for inputs.
|
| Three modules assemble this source: USB AUDIO IN AB (host channels 1/2 ->
| inputs A/B), IN CD (1/2 -> C/D) and IN ABCD (1-4 -> A-D); remix.inc sets
| IN_CHANNELS (2 or 4). Which inputs the pair lands on is the DSP inject's
| business (rx_inject_*.asm, manifest.py): this unit ships the host's
| channels in host order.
|
| The host streams AudioStreaming interface 5 alt 1 on EP3 OUT: isochronous,
| asynchronous with IMPLICIT feedback (EP3 IN, the input stream, is the
| feedback source, so the host sizes each OUT packet from EP3 IN's),
| IN_CHANNELS x 24-bit in 4-byte little-endian subslots, 11/12 frames per
| 250 us packet (<= 96 B for a pair, <= 192 B for four).
|
|   USB side (this unit, all in the frame transfer machine's state 7):
|     EP3 OUT up/down follows the host's SET_INTERFACE(5); four dTDs stay
|     queued; each retired dTD's frames go into a 1,024-frame ring and the
|     dTD is queued again at the tail (the Chipidea add-dTD procedure, as
|     usbaudio.s does for EP3 IN).
|   DSP side: once per 16-sample frame, 16 ring frames become TX_WORDS
|     host-port halfwords for core 0 at $6320, the idle bank + $320 after the
|     DSP's mask: word 0 = 1 while the stream is open, then 16 x (ch1 hi,
|     ch1 lo, ch2 hi, ch2 lo[, ch3.., ch4..]), hi = sample[23:8], lo =
|     sample[7:0], then zero pad. The DSP inject copies them over the
|     module's slots of the RX block the next frame while word 0 is set, and
|     leaves the block alone otherwise.
|
| Hooks (manifest.py):
|   0x4001dd0a  SET_INTERFACE: usbaudio's shim sends every interface but 4
|               here; interface 5 alt 0/1 records the alt and ACKs, any other
|               alt STALLs, the rest goes on to the stock (mass-storage)
|               handler. GET_INTERFACE(5) is answered by usbaudio.s (USB_IN).
|   0x40004bc0  frame transfer state 7 (8 bytes): first visit does the work
|               and starts one more transfer; its completion is the second
|               visit, which runs stock state 7 (the frame IRQ unmask).
|   0x4001de6e  the EP0 stall store: vendor GET 0x56 answers the counters.
|
| Memory: the dTDs and packet buffers are in on-chip SRAM (SRAM_*, declared
| in each manifest's Claims.sram; the four-channel buffers reach the reply): the controller reaches SRAM through the
| backdoor, it is not cached, so what the CPU writes is what the DMA reads.
| The host-port buffer is in SDRAM and touched only through the uncached
| alias (+0x08000000); the ring and the state are CPU-only. Packet buffers
| in SDRAM through the alias have not been measured with USB CROSSBAR on.
|
| Latency: the ring runs at IN_TARGET frames of cushion. With implicit
| feedback the host's OUT rate follows EP3 IN's packet sizes, and those
| follow usbaudio's rate servo. That servo is proportional and holds EP3 IN's
| fill at AUD_TARGET, so this ring, which mirrors EP3 IN's, holds too.
| (Before it, a +-128-frame deadband let both rings wander by its width.)
| IN_TARGET then only has to cover a block, a packet and the jitter the unit
| shows (376-395 around 384 on Bryan T's MKII, 28 Sep 2026). The two rings'
| fills sum to a constant set at stream start (README, Latency).
| SPDX-License-Identifier: MIT

    .include "remix.inc"            | IN_CHANNELS: 2 (AB, CD) or 4 (ABCD)
.set UNCACHED,       0x08000000
.set SRAM_DTDS,      0x80007c00     | NSLOTI dTDs, 32-byte aligned (128 B)
.set SRAM_BUFS,      0x80007c80     | NSLOTI packet buffers (384 B, or 768 for four channels)
.set SRAM_REPLY,     0x80007f80     | EP0 reply for 0x56 (64 B)

| ---- firmware sites (1.40C) ----
.set SETUP_BMREQ,    0x46c8ce08     | the SETUP packet, byte by byte
.set SETUP_BREQ,     0x46c8ce09
.set SETUP_WVALL,    0x46c8ce0a     | wValue low = alt setting
.set SETUP_WVALH,    0x46c8ce0b
.set SETUP_WIDXL,    0x46c8ce0c     | wIndex low = interface number
.set SETUP_WLENL,    0x46c8ce0e
.set SETUP_WLENH,    0x46c8ce0f
.set EP0_SEND_TAIL,  0x4001de5c     | jsr usb_ep0_send(len, buf); addq; done
.set EP0CTRL,        0xfc0b01c0     | ENDPTCTRL0
.set EP0_TXS,        16             | ENDPTCTRL0 bit 16: TX stall
.set EP0_STATUS_IN,  0x4001d524     | zero-length EP0 IN status (ACK)
.set SETIFACE_DONE,  0x4001de74     | control-request-done
.set SETIFACE_REJOIN,0x4001dd10     | stock SET_INTERFACE after the displaced oril
.set STATE7_DONE,    0x40004bc8     | the transfer IRQ's movem restore + rte
.set FRAME_UNMASK,   0xfc04801d     | stock state 7's write (INTC0 CIMR <- 1)
.set VENDOR_REQ,     0x56           | usbaudio answers 0x55 with its own

| ---- USB controller ----
.set EPLISTADDR, 0xfc0b0158
.set ENDPTSTAT,  0xfc0b01b8
.set EPPRIME,    0xfc0b01b0
.set EPFLUSH,    0xfc0b01b4
.set EPCOMPLETE, 0xfc0b01bc
.set ENDPTCTRL3, 0xfc0b01cc
.set USBCMD,     0xfc0b0140
.set ATDTW,      0x00004000         | USBCMD add-dTD tripwire
.set PORTSC1,    0xfc0b0184
.set PORTSC_PSPD, 0x0c000000        | bits 27:26 = port speed
.set PORTSC_HS,  0x08000000         | 2 = high speed
.set QH_LIST,    0x4ec94800         | the firmware's dQH list (fallback)
.set QH_EP3OUT_OFF, 6*64            | EP3 OUT is list entry 3*2
.set EP3OUT_BIT, 0x00000008         | ENDPTPRIME/STAT/COMPLETE/FLUSH bit
.set CTRL3_RX,   0x00000084         | ENDPTCTRL3 RX half: RXE + isochronous
.set DTD_ACTIVE, 7                  | dTD token bit 7
.set DTD_ERRS,   0x68               | token: halted, data buffer error, transaction error

| ---- the eDMA / host port (as states 4/5 program them) ----
.set EDMA_SADDR, 0xfc045000
.set EDMA_NBYTES,0xfc045008
.set EDMA_CITER, 0xfc045014
.set EDMA_BITER, 0xfc04501c
.set EDMA_START, 0xfc04401e
.set CORE_SEL,   0xfc0a400c
.set HOST_ICR,   0x20000000
.set HOST_CVR,   0x20000004
.set HOST_DATA,  0x2000001c
.set DSP_DEST,   0x6320             | idle bank + $320 after the DSP's mask

| ---- geometry ----
.set IN_IFACE,   5
.set NSLOTI,     4                  | dTDs kept queued (1 ms of packets)
.set FRAME_B,    4*IN_CHANNELS      | bytes per frame: 8 for a pair, 16 for four
.set OPKT,       12*FRAME_B         | 12 frames: the largest packet, 96 or 192 B
.set IN_FRAMES,  1024               | ring, frames (power of two)
.set IN_TARGET,  96                 | cushion before consuming, 2.2 ms (see Latency)
.set BLOCK,      16                 | DSP frame
.if IN_CHANNELS == 4
.set TX_BYTES,   320                | word 0 + 128 halfwords + pad: 5 eDMA minor loops of 64
.else
.set TX_BYTES,   192                | word 0 + 64 halfwords + pad: 3 eDMA minor loops of 64
.endif
.set TX_WORDS,   TX_BYTES/2
.set NCOUNT,     15                 | longs in in_counters

| wValue / wIndex / wLength from the SETUP packet, 16 bits into \r.
.macro SETUP16 hi, lo, r
    mvzb    \hi,\r
    lsll    #8,\r
    orl     \lo,\r
.endm

    .text
| ---- SET_INTERFACE (0x4001dd0a) ---------------------------------------------
| Displaced: oril #0x00400040,%d0 (d0 = ENDPTCTRL1, loaded by the stock
| movel or by usbaudio's shim). d1 is free until 0x4001dd2e reloads it.
    .global in_setiface_shim
in_setiface_shim:
    mvzb    SETUP_WIDXL,%d1
    cmpil   #IN_IFACE,%d1
    beqs    1f
    oril    #0x00400040,%d0         | displaced
    jmp     SETIFACE_REJOIN
1:  mvzb    SETUP_WVALL,%d1
    moveq   #1,%d0
    cmpl    %d0,%d1
    bhis    2f                      | interface 5 has alt 0 and alt 1 only
    moveb   %d1,in_alt              | the request; state 7 brings EP3 OUT up/down
    jsr     EP0_STATUS_IN
    jmp     SETIFACE_DONE
2:  movel   EP0CTRL,%d0             | STALL, as the stock unknown-request tail does
    bset    #EP0_TXS,%d0
    movel   %d0,EP0CTRL
    jmp     SETIFACE_DONE

| ---- vendor GET 0x56 (installed at 0x4001de6e) ------------------------------
| Displaced: movel %d0,0xfc0b01c0 -- the stall's store (ENDPTCTRL0 with the
| stall bits already set in d0). Two paths reach it: the unknown-request tail
| (0x4001de6a's bset, which usbaudio's class shim also falls back into) and a
| standard-request stall (braw 0x4001de6e at 0x4001dd00).
| bmRequestType 0xc0 / bRequest 0x56 answers in_counters (NCOUNT big-endian
| longs) instead of stalling; everything else stalls as stock. wLength comes
| from the SETUP packet: d2 is wLength on usbaudio's path but not provably on
| the 0x4001dd00 one. d1-d3 are free: the epilogue at 0x4001de74 pops d2/d3.
| The reply is copied into SRAM first: the EP0 DMA reads memory, and the
| counters live in the data cache.
    .global in_ctrl_shim
in_ctrl_shim:
    movel   %d0,%d2                 | the stall value, for the reject path
    mvzb    SETUP_BMREQ,%d1
    cmpil   #0xc0,%d1
    bnes    .Lc_stall
    mvzb    SETUP_BREQ,%d1
    cmpil   #VENDOR_REQ,%d1
    bnes    .Lc_stall
    lea     in_counters,%a0
    moveal  #SRAM_REPLY,%a1
    moveq   #NCOUNT-1,%d0
1:  movel   %a0@+,%a1@+
    subql   #1,%d0
    bpls    1b
    pea     SRAM_REPLY
    moveq   #NCOUNT*4,%d3
    SETUP16 SETUP_WLENH, SETUP_WLENL, %d0
    cmpl    %d0,%d3
    bhis    1f                      | len > wLength: send wLength
    movel   %d3,%d0
1:  movel   %d0,%sp@-
    jmp     EP0_SEND_TAIL
.Lc_stall:
    movel   %d2,%d0
    movel   %d0,EP0CTRL             | displaced: the stall
    jmp     SETIFACE_DONE

| ---- state 7 (0x40004bc0) -----------------------------------------------------
| The transfer IRQ saved d0-d1/a0-a1; everything else is saved here. The
| first visit per frame is the stock machine's; our transfer's completion
| is the second, which runs the displaced stock state 7.
| While the stream is closed the DSP needs word 0 = 0 in both of its banks
| (the transfer lands in the working bank's +$320 and the banks alternate per
| frame), not a fresh block every frame: the block is transferred until
| ZERO_BLOCKS of them have completed since the close (in_zero_sent), then
| skipped, and the first visit runs the stock state 7 itself. in_seconds
| therefore counts transfers, not frames, while closed. (Bryan T, 4 Oct
| 2026: one eDMA transfer and one interrupt pass per frame for nothing with
| no host; not measured since.)
.set ZERO_BLOCKS, 4                 | two banks; two more for margin
    .global in_state7_shim
in_state7_shim:
    tstb    in_busy
    bnes    .Ls7_second
    lea     %sp@(-40),%sp
    moveml  %d2-%d7/%a2-%a5,%sp@
    bsr     in_frame
    moveml  %sp@,%d2-%d7/%a2-%a5
    lea     %sp@(40),%sp
    tstb    in_running
    bnes    .Ls7_send
    mvzb    in_zero_sent,%d0
    cmpil   #ZERO_BLOCKS,%d0
    bccs    .Ls7_stock              | both DSP banks hold word 0 = 0
.Ls7_send:
    moveq   #1,%d0
    moveb   %d0,in_busy
    bsr     in_dma_start
    jmp     STATE7_DONE
.Ls7_second:
    addql   #1,in_seconds
    clrb    in_busy
    tstb    in_running
    bnes    .Ls7_stock
    mvzb    in_zero_sent,%d0        | one more closed block (word 0 = 0) landed
    addql   #1,%d0
    moveb   %d0,in_zero_sent
.Ls7_stock:
    moveq   #1,%d1                  | stock state 7, displaced
    moveb   %d1,FRAME_UNMASK
    jmp     STATE7_DONE

| One more host-port transfer: TX_WORDS halfwords from in_tx to core 0 at
| DSP_DEST, eDMA ch 0 exactly as states 4/5 set it up (64-byte minor loops).
in_dma_start:
    clrb    %d0
    moveb   %d0,CORE_SEL            | core 0
    moveq   #64,%d1
    movel   %d1,EDMA_NBYTES
    movel   #(in_tx+UNCACHED),%d1
    movel   %d1,EDMA_SADDR
    movew   #0x81,%d0
    movew   %d0,HOST_ICR
    movew   #DSP_DEST,%d1
    movew   %d1,HOST_DATA
    movew   #TX_WORDS-1,%d0
    movew   %d0,HOST_DATA
    movew   #0x88,%d1
    movew   %d1,HOST_CVR
    movew   #(0x8000+TX_BYTES/64),%d0   | E_LINK, TX_BYTES/64 minor loops
    movew   %d0,EDMA_CITER
    movew   %d0,EDMA_BITER
    clrb    %d1
    moveb   %d1,EDMA_START
    rts

| ---- the per-frame work ----------------------------------------------------
| May clobber d0-d7/a0-a5.
in_frame:
    addql   #1,in_frames            | state-7 visits = DSP frames
    mvzb    in_alt,%d0
    mvzb    in_running,%d1
    cmpl    %d0,%d1
    beqs    1f
    tstl    %d0
    beqs    2f
    bsr     in_up
    bras    1f
2:  bsr     in_down
1:  tstb    in_running
    beqs    .Lf_idle
    movel   #EP3OUT_BIT,%d0
    movel   %d0,EPCOMPLETE          | W1C: no IOC, so this bit never interrupts
    bsr     in_retire
    bsr     in_selfheal
    bra     in_build
.Lf_idle:
    moveal  #(in_tx+UNCACHED),%a1
    clrw    %a1@                    | word 0 clear: the jacks
    rts

| Bring EP3 OUT up. High speed only: the descriptors declare interface 5 at
| high speed alone, so a full-speed host never asks. Retried every frame
| while the host asks for alt 1.
in_up:
    movel   PORTSC1,%d0
    andil   #PORTSC_PSPD,%d0
    cmpil   #PORTSC_HS,%d0
    bne     9f
    bsr     in_flush
    bsr     in_qh_resolve           | a0 = EP3 OUT dQH
    moveq   #15,%d1
1:  clrl    %a0@+                   | the whole dQH: its token and pointers
    subql   #1,%d1                  | are power-on garbage (usbaudio.s)
    bpls    1b
    moveal  qh_in,%a0
    movel   #(0x60000000+(OPKT<<16)),%d0   | Mult 1, ZLT off, maxpkt OPKT
    | Mult must be non-zero: with Mult 0 (Linux's chipidea udc has it for
    | ISO RX) 800 of 821 packets completed with a transaction error and 0
    | bytes, then the stream stopped (Bryan T, 26 Sep 2026).
    movel   %d0,%a0@
    moveq   #1,%d0
    movel   %d0,%a0@(8)             | next dTD: terminate
    movel   ENDPTCTRL3,%d0          | the RX half only: EP3 IN owns TX
    andil   #0xffff0000,%d0
    oril    #CTRL3_RX,%d0
    movel   %d0,ENDPTCTRL3
    clrl    in_produced
    clrl    in_consumed
    moveq   #-1,%d0
    movel   %d0,in_minfill
    clrl    in_maxfill
    moveq   #1,%d0
    moveb   %d0,in_prefill
    clrb    in_ri
    bsr     in_arm_all
    moveq   #1,%d0
    moveb   %d0,in_running
    clrb    in_zero_sent
9:  rts

in_down:
    bsr     in_flush
    movel   ENDPTCTRL3,%d0
    andil   #0xffff0000,%d0         | RX half off, TX half as it was
    movel   %d0,ENDPTCTRL3
    moveal  #SRAM_DTDS,%a1
    moveq   #NSLOTI*8-1,%d1
1:  clrl    %a1@+
    subql   #1,%d1
    bpls    1b
    clrb    in_running
    clrb    in_zero_sent            | a zero block goes out before the transfers stop
    rts

| Flush EP3 OUT, bounded, repeating while it still shows primed.
in_flush:
    movel   %d2,%sp@-
    moveq   #16,%d1
1:  movel   #EP3OUT_BIT,%d0
    movel   %d0,EPFLUSH
    movel   #0x10000,%d2            | bound: a flush with USBCMD.RS clear (session end) may never complete
2:  movel   EPFLUSH,%d0
    andil   #EP3OUT_BIT,%d0
    beqs    4f
    subql   #1,%d2
    bnes    2b
4:
    movel   ENDPTSTAT,%d0
    andil   #EP3OUT_BIT,%d0
    beqs    3f
    subql   #1,%d1
    bnes    1b
3:  movel   %sp@+,%d2
    rts

| EP3 OUT's queue head from ENDPTLISTADDR (a value outside SDRAM is not a
| list: the firmware's constant then). -> a0, cached in qh_in.
in_qh_resolve:
    movel   EPLISTADDR,%d0
    andil   #0xfffff800,%d0
    cmpil   #0x40000000,%d0
    blts    1f
    cmpil   #0x50000000,%d0
    blts    2f
1:  movel   #QH_LIST,%d0
2:  addil   #QH_EP3OUT_OFF,%d0
    movel   %d0,qh_in
    moveal  %d0,%a0
    rts

| d0 = slot (mod NSLOTI) -> a0 = its dTD, a3 = its buffer (both in SRAM).
| Clobbers d0/d1.
in_slot:
    andil   #NSLOTI-1,%d0
    movel   %d0,%d1
    lsll    #5,%d0                  | slot * 32
    moveal  #SRAM_DTDS,%a0
    addal   %d0,%a0
    moveal  #SRAM_BUFS,%a3
.if IN_CHANNELS == 4
    lsll    #6,%d1                  | slot * 64
.else
    lsll    #5,%d1                  | slot * 32
.endif
    addal   %d1,%a3
    addal   %d1,%a3
    addal   %d1,%a3                 | + slot * OPKT (3 x 32 or 3 x 64)
    rts

| Write slot d2's dTD for one packet: buffer pages, next = terminate, then
| the ACTIVE token LAST (uncached stores reach memory in program order).
| -> a0 = the dTD. Clobbers d0/d1/a3.
in_dtd_fill:
    movel   %d2,%d0
    bsr     in_slot
    moveq   #1,%d0
    movel   %d0,%a0@                | next = terminate
    movel   %a3,%a0@(8)             | page 0
    movel   %a3,%d0
    andil   #0xfffff000,%d0
    addil   #0x1000,%d0
    movel   %d0,%a0@(12)            | page 1: a buffer may straddle 4 KB
    movel   #((OPKT<<16)+(1<<DTD_ACTIVE)),%d0   | total bytes, ACTIVE, no IOC
    movel   %d0,%a0@(4)
    rts

| Queue all NSLOTI dTDs as one chain and prime.
in_arm_all:
    moveq   #NSLOTI-1,%d2
1:  bsr     in_dtd_fill             | back to front: each links the next
    movel   %d2,%d0
    addql   #1,%d0
    cmpil   #NSLOTI,%d0
    beqs    2f
    moveal  %a0,%a4
    bsr     in_slot                 | a0 = the next dTD
    movel   %a0,%a4@                | this.next = next
    moveal  %a4,%a0
2:  subql   #1,%d2
    bpls    1b
    moveal  qh_in,%a1               | a0 = slot 0, the head
    movel   %a0,%a1@(8)
    clrl    %a1@(12)
    movel   #EP3OUT_BIT,%d0
    movel   %d0,EPPRIME
    rts

| Retire completed dTDs in queue order into the ring, and queue each again.
in_retire:
    moveq   #NSLOTI,%d7             | at most one lap
.Lr_next:
    mvzb    in_ri,%d2
    movel   %d2,%d0
    bsr     in_slot
    movel   %a0@(4),%d3             | token
    btst    #DTD_ACTIVE,%d3
    bne     .Lr_done                | still ACTIVE: nothing more has landed
    movel   %d3,%d0
    andil   #DTD_ERRS,%d0
    beqs    1f
    addql   #1,in_bad
    addql   #1,in_err
1:  movel   %d3,%d0
    swap    %d0
    andil   #0x7fff,%d0             | bytes left
    movel   #OPKT,%d4
    subl    %d0,%d4                 | d4 = bytes received
    bcs     .Lr_requeue             | nonsense: drop it
    movel   %d4,%d0
    andil   #FRAME_B-1,%d0
    beqs    2f
    addql   #1,in_bad               | not whole frames
    addql   #1,in_partial
2:
.if IN_CHANNELS == 4
    lsrl    #4,%d4                  | frames
.else
    lsrl    #3,%d4                  | frames
.endif
    movel   %d4,in_lastn
    addql   #1,in_pkts
    tstl    %d4
    beqs    .Lr_requeue
    | copy d4 frames from a3 into the ring at in_produced
    lea     in_ring,%a2
    movel   in_produced,%d5
3:  movel   %d5,%d0
    andil   #IN_FRAMES-1,%d0
.if IN_CHANNELS == 4
    lsll    #4,%d0
    lea     %a2@(0,%d0:l),%a1
    movel   %a3@+,%a1@+
    movel   %a3@+,%a1@+
.else
    lsll    #3,%d0
    lea     %a2@(0,%d0:l),%a1
.endif
    movel   %a3@+,%a1@+
    movel   %a3@+,%a1@+
    addql   #1,%d5
    subql   #1,%d4
    bnes    3b
    movel   %d5,in_produced
    subl    in_consumed,%d5         | fill
    cmpil   #IN_FRAMES,%d5
    blss    .Lr_requeue
    addql   #1,in_overruns          | host ahead by a whole ring: resync
    movel   in_produced,%d0
    subil   #IN_TARGET,%d0
    movel   %d0,in_consumed
.Lr_requeue:
    bsr     in_dtd_fill             | slot d2 again, ACTIVE
    bsr     in_enqueue
    movel   %d2,%d0
    addql   #1,%d0
    andil   #NSLOTI-1,%d0
    moveb   %d0,in_ri
    subql   #1,%d7
    bne     .Lr_next
.Lr_done:
    rts

| Append the just-filled dTD (a0, slot d2) after slot d2-1, the Chipidea
| add-dTD procedure (usbaudio.s audio_pkt_build has the commentary).
| Clobbers d0/d1/d3/a1/a3/a4/a5.
in_enqueue:
    moveal  %a0,%a5                 | this
    movel   %d2,%d0
    subql   #1,%d0
    bsr     in_slot                 | a0 = previous
    moveal  %a0,%a1
    moveal  %a5,%a0
    movel   %a1@(4),%d0
    btst    #DTD_ACTIVE,%d0
    beqs    .Le_prime               | previous retired: list empty
    movel   %a0,%a1@                | previous.next = this
    movel   EPPRIME,%d0
    andil   #EP3OUT_BIT,%d0
    bnes    .Le_done                | a prime is pending: it reads the list
    moveq   #16,%d3
.Le_trip:
    movel   USBCMD,%d0
    oril    #ATDTW,%d0
    movel   %d0,USBCMD
    movel   ENDPTSTAT,%d1
    andil   #EP3OUT_BIT,%d1
    movel   USBCMD,%d0
    andil   #ATDTW,%d0
    bnes    .Le_sampled
    subql   #1,%d3
    bnes    .Le_trip
    bras    .Le_done                | never settled: the self-heal catches it
.Le_sampled:
    movel   USBCMD,%d0
    andil   #~ATDTW,%d0
    movel   %d0,USBCMD
    tstl    %d1
    bnes    .Le_done                | still running: it follows the link
    bsr     in_oldest               | a0 = the oldest ACTIVE (this at worst)
.Le_prime:
    moveal  qh_in,%a1
    movel   %a0,%a1@(8)
    clrl    %a1@(12)
    movel   #EP3OUT_BIT,%d0
    movel   %d0,EPPRIME
.Le_done:
    rts

| The oldest ACTIVE dTD in queue order from in_ri -> a0 (d0 = 1), or d0 = 0.
| Clobbers d0/d1/d3/d4/a3.
in_oldest:
    mvzb    in_ri,%d4
    moveq   #NSLOTI-1,%d3
1:  movel   %d4,%d0
    bsr     in_slot
    movel   %a0@(4),%d1
    btst    #DTD_ACTIVE,%d1
    bnes    2f
    addql   #1,%d4
    subql   #1,%d3
    bpls    1b
    moveq   #0,%d0
    rts
2:  moveq   #1,%d0
    rts

| Idle endpoint + queued dTD = prime the oldest, and count it.
in_selfheal:
    movel   ENDPTSTAT,%d0
    movel   EPPRIME,%d1
    orl     %d1,%d0
    andil   #EP3OUT_BIT,%d0
    bnes    9f
    bsr     in_oldest
    tstl    %d0
    beqs    9f
    moveal  qh_in,%a1
    movel   %a0,%a1@(8)
    clrl    %a1@(12)
    movel   #EP3OUT_BIT,%d0
    movel   %d0,EPPRIME
    addql   #1,in_reprimes
9:  rts

| 16 ring frames -> in_tx for the DSP: word 0 = 1, then each host channel as
| a hi/lo halfword pair, host order. Before the cushion is full, and on an
| underrun (which refills the cushion), silence with word 0 set: an open
| stream owns its inputs even while it is starting.
in_build:
    moveal  #(in_tx+UNCACHED),%a1
    movel   in_produced,%d0
    subl    in_consumed,%d0         | fill
    movel   %d0,in_lastfill
    tstb    in_prefill
    beqs    1f
    cmpil   #IN_TARGET,%d0
    bcs     .Lb_silence             | still filling
    clrb    in_prefill
    bras    2f
1:  cmpil   #BLOCK,%d0
    bcc     2f
    addql   #1,in_underruns
    moveq   #1,%d1
    moveb   %d1,in_prefill
    bras    .Lb_silence
2:  cmpl    in_minfill,%d0          | fill before this block's 16 go out
    bccs    4f
    movel   %d0,in_minfill
4:  cmpl    in_maxfill,%d0
    blss    5f
    movel   %d0,in_maxfill
5:  moveq   #1,%d0
    movew   %d0,%a1@+               | word 0: the stream is open
    lea     in_ring,%a2
    movel   in_consumed,%d5
    moveq   #BLOCK,%d7
.Lb_frame:
    movel   %d5,%d0
    andil   #IN_FRAMES-1,%d0
.if IN_CHANNELS == 4
    lsll    #4,%d0
.else
    lsll    #3,%d0
.endif
    lea     %a2@(0,%d0:l),%a0       | a0 = this frame: IN_CHANNELS x 4 B, LE
    moveq   #IN_CHANNELS,%d6
.Lb_ch:
    mvzb    %a0@(3),%d1             | sample[23:16]
    lsll    #8,%d1
    mvzb    %a0@(2),%d2             | sample[15:8]
    orl     %d2,%d1
    movew   %d1,%a1@+               | hi = sample[23:8]
    mvzb    %a0@(1),%d1             | lo = sample[7:0]
    movew   %d1,%a1@+
    addql   #4,%a0
    subql   #1,%d6
    bnes    .Lb_ch
    addql   #1,%d5
    subql   #1,%d7
    bnes    .Lb_frame
    movel   %d5,in_consumed
    rts
.Lb_silence:
    moveq   #TX_BYTES/4-1,%d1
3:  clrl    %a1@+
    subql   #1,%d1
    bpls    3b
    moveal  #(in_tx+UNCACHED),%a1
    moveq   #1,%d0
    movew   %d0,%a1@                | word 0: open, silent
    rts

    .data
    .balign 4
    .global in_counters
in_counters:                        | vendor request 0x56's order (tools/hw/usb_counters.py)
in_produced:  .long 0               | frames into the ring
in_consumed:  .long 0               | frames sent to the DSP
in_pkts:      .long 0               | OUT packets retired
in_lastn:     .long 0               | frames in the last packet
in_lastfill:  .long 0               | ring fill at the last frame
in_underruns: .long 0               | blocks the ring could not supply
in_overruns:  .long 0               | ring laps (host ahead)
in_reprimes:  .long 0               | self-heal primes
in_bad:       .long 0               | err + partial
in_frames:    .long 0               | first state-7 visits (DSP frames)
in_seconds:   .long 0               | second state-7 visits (our transfer's completion)
in_minfill:   .long 0               | lowest fill while consuming, since up
in_maxfill:   .long 0               | highest fill while consuming, since up
in_err:       .long 0               | completions with a dTD error bit
in_partial:   .long 0               | completions that were not whole frames

qh_in:        .long 0
in_ring:      .space IN_FRAMES*FRAME_B
    .global in_alt                  | usbaudio.s answers GET_INTERFACE(5) from it
in_alt:       .byte 0               | the host's request (USB interrupt)
in_running:   .byte 0               | EP3 OUT is up (state-7 owned)
in_prefill:   .byte 0               | filling the cushion
in_ri:        .byte 0               | next dTD slot to retire
in_busy:      .byte 0               | state 7: our transfer is in flight
in_zero_sent: .byte 0               | closed: blocks with word 0 = 0 completed since the close; transfers skipped from ZERO_BLOCKS

    .balign 32
in_tx:        .space TX_BYTES
