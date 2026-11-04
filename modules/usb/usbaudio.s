| usbaudio.s -- USB AUDIO OUT: up to 20 channels over USB (UAC2), the
| TRACKS / MAIN / CUE / MASTER / IN / MIDI run-time settings.
|
| Based on markandrus/octemu custom/coldfire/usb-audio.s at 6a9ff68 (MIT).
| The shims, the EP3 bring-up and the UAC2 class-request replies are his.
| Here it is a DRAM unit: the loader places it and zeroes its data, every
| hook is a detour in manifest.py, and the ISR shim chains to USB MIDI's by
| symbol (the units link together; schema.Override). README.md has what
| was measured.
| SPDX-License-Identifier: MIT
|
| The stream is the checked boxes in slot order, at run time (six value
| bytes, remix.inc's resolved values unless the CS1 block is valid -- cfgsel):
|
|   usb_trk       TRACKS:  0 OFF, 1 PRE, 2 POST -- the 16 track channels
|                           (post-FX pre-fader: the read-back arena the eDMA
|                           fills every block; POST: each track's block
|                           times that track's own MAIN gain as core 0
|                           applies it -- LEVEL, mute, solo, XLV, the
|                           16-sample ramp -- MAIN_LEVEL left out; the POST
|                           section below has the design)
|   usb_main      MAIN:    2 channels, the DAC feed's MAIN pair
|   usb_cue       CUE:     2 channels, the CUE pair
|   usb_master    MASTER:  2 channels, track 8's post-FX pre-fader L/R
|   usb_in        IN:      0 OFF, 1 AB, 2 CD, 3 ABCD -- the host -> device
|                           stream's channels (usbaudio_in.s); needs an
|                           output stream beside it (EP3 IN is its
|                           implicit-feedback source)
|   usb_midi      MIDI:    1 on, 0 off (the interface numbers the audio
|                           shims compare against move with it: usb_ac_iface
|                           / usb_as_iface / usb_in_iface, latched by cfgsel)
|
| The defaults (TRACKS PRE, MAIN, CUE, MIDI) are the released image's
| TRACKS MAIN CUE stream. Every combination lives in every image: one
| composable producer writes each frame in the stream's own layout into the
| ring (the checked fields only, in wire order: tracks 16 x (L,R), then
| MAIN, CUE, MASTER -- 4 B each, 24 bits little-endian), through the
| uncached alias, and each high-speed packet's dTD points into the ring:
| nothing is copied (since 27 Oct 2026; until then the ring held 88-byte
| slots and the packet builder copied the checked fields into packet
| buffers, 5.9 us a frame at OUT MAIN CUE on Bryan T's MKII, a frame
| profiler). The full-speed stream is the 8-byte stereo sum
| (aud_sum) in every combination -- sum priority tracks > MAIN > CUE >
| MASTER -- 44/45 frames a packet; the high-speed packet is 11/12 frames x
| the combination's frame bytes at bInterval 2 (250 us). TRACKS with
| MASTER is refused (MASTER is track 8's L/R, already in TRACKS; cfgsel),
| so no combination exceeds 20 channels. The
| geometry (usb_nch, usb_frame_bytes, usb_hs_cap, usb_hs_step) is latched
| by cfgsel with the four config-table pointers; the four config responders
| serve the matching set (descriptors.py, cfg.s).
    .include "remix.inc"
.set TRK_OFF,   0
.set TRK_PRE,   1
.set TRK_POST,  2
.set EARLY_MAGIC,    0xea           | the CS1 early block's magic (brain.c)
.set SUM_SHIFT,      8              | 32-bit read-back -> 24-bit units for the sum
.set UAC2_CLOCK_ID,  0x10

| ---- firmware sites (1.40C) ----
.set SETUP_ALT,      0x46c8ce0a     | SETUP wValue low = alt setting
.set SETUP_IFACE,    0x46c8ce0c     | SETUP wIndex low = interface number
.set EP0_STATUS_IN,  0x4001d524     | zero-length EP0 IN status (ACK)
.set SETIFACE_DONE,  0x4001de74     | control-request-done
.set SETIFACE_STOCK, 0x4001dd0a     | rejoin after the displaced movel
.set GETIFACE_REJOIN,0x4001d81e     | GET_INTERFACE send tail (expects pea'd ptr)
.set GETIFACE_STOCKP,0x400e20a1     | the stock 1-byte "00" the send reads
.set SETUP_BMREQ,    0x46c8ce08     | SETUP bmRequestType
.set SETUP_BREQ,     0x46c8ce09     | SETUP bRequest
.set SETUP_WVALL,    0x46c8ce0a     | SETUP wValue low
.set SETUP_WVALH,    0x46c8ce0b     | SETUP wValue high = control selector
.set SETUP_WIDXL,    0x46c8ce0c     | SETUP wIndex low
.set SETUP_WIDXH,    0x46c8ce0d     | SETUP wIndex high = entity id
.set EP0_SEND_TAIL,  0x4001de5c     | jsr usb_ep0_send(len, buf); addq; done
.set CTRL_STOCK,     0x4001de6a     | the stock STALL, after the displaced movel

| ---- USB controller registers ----
.set EPLISTADDR, 0xfc0b0158         | the controller's OWN dQH list base
.set ENDPTSTAT,  0xfc0b01b8
.set EPPRIME,    0xfc0b01b0
.set EPFLUSH,    0xfc0b01b4
.set EPCOMPLETE, 0xfc0b01bc
.set SETUPSTAT,  0xfc0b01ac         | ENDPTSETUPSTAT
.set EP0CTRL,    0xfc0b01c0         | ENDPTCTRL0: bit 16 = EP0 IN (TX) stall
.set EP0OUT_DTD, 0x4ec95000         | the stock EP0 OUT dTD (usb_ep0_send's status OUT)
.set EP0_BUF,    0x4ec96000         | ... and its 64-byte buffer
.set QH0_OUT_PTR,0x46c8ce18         | -> EP0 OUT dQH
.set ENDPTCTRL3, 0xfc0b01cc
.set USBCMD,     0xfc0b0140
.set ATDTW,      0x00004000         | USBCMD bit 14: the add-dTD tripwire
.set QH_EP3IN,   0x4ec949c0         | EP3 IN dQH, the fallback when ENDPTLISTADDR
                                    | reads outside SDRAM (audio_qh_resolve)
.set QH_EP3IN_OFF, 7*64             | EP3 IN is list entry (3*2)+1
.set EP3IN_BIT,  0x00080000         | ENDPTPRIME/STAT/COMPLETE bit for EP3 IN

| ---- the track source: the read-back arena ----
| The eDMA deposits every track's post-FX, pre-fader block into SRAM each
| frame; the RECEIVE machine sums the same memory. Layout: RB_BASE +
| bank*1024 + track*128 + frame*8, two 32-bit words (L,R) per frame, 16
| frames per block, 8 tracks, ping-pong banks. The producer reads the
| PREVIOUS bank (the pipeline is one block deep). Track level, the
| crossfader, MAIN volume and the master effects are downstream of this tap.
.set RB_BASE,      0x80003190
.set RB_PREV,      0x800000e4      | pingpong_prev: reads use prev
.set RB_TRACKS,    8
| MAIN and CUE: the DAC feed itself. Core 0's mixdown packs ESAI TX slots
| 2/3 and 0/1 (P:0x2df, P:0x2e2) into the host read-back after the track
| blocks; the frame ISR's chain ch1 -> ch6 -> ch7 lands them here, ch6
| writing 0x80005e60..0x80005f60 each frame: 16 x (L,R) at +0x00, then
| 16 x (L,R) at +0x80, 32-bit words in the read-back's format (24 bits,
| left-justified). The stock recorder reads the same buffer for SRC3 =
| MAIN (+0x00) / CUE (+0x80) from inside frame_isr (0x4000d2a0), before
| this hook; the next frame's ch6 cannot overwrite it until the next
| frame_isr. Single buffer, no ping-pong. MAIN = +0x00, CUE = +0x80
| (hardware: Bryan T's MKII, image 90, 25 Sep 2026).
.set MAIN_CUE_BASE,      0x80005e60
.set MAIN_CUE_MAIN_OFF,  0x00
.set MAIN_CUE_CUE_OFF,   0x80
| In the twenty-channel stream MAIN/CUE of a pull are the mix of the tracks
| one block EARLIER than the track words read beside them (the tracks come
| from the previous bank, the mixdown buffer from the current pull):
| measured under the port at 16 samples on every tone that reaches MAIN
| (tools/harness/usb_align.py, 28 Sep 2026; heard as MAIN lagging on Bryan
| T's unit, 25 Sep). With TRACKS in the stream the producer writes the pair
| this many blocks behind the tracks' slot; the consumer runs AUD_TARGET
| (64) frames behind, more than one 16-frame block, so that slot is unread
| when it is written.
.set MAIN_CUE_LAG_BLOCKS, 1
| With MASTER TRACK on, CUE leads MAIN. The mixdown (payload A, P:0x257:
| brset #$a on x:(X:$207+$7e)) takes the master path at P:0x292: the cue bus
| (ring words 0/1, P:0x29f-0x2b2) sums slots 0-6 of this frame's blocks
| directly, while MAIN (words 2/3, P:0x2cb-0x2d0) is slot 7 alone, track 8's
| output of a mix it was sent (x:(X:$209+$1f8), P:0x2b7-0x2ca) two frames
| earlier. The ColdFire sets that bit from the MASTER TRACK byte: the frame
| record builder ORs 0x600 into 0x8000030c + ping*0x200 (halfword $7e of the
| 0x80000210 record) when 0x80000034 is nonzero (0x4000498c-0x400049aa).
| Measured on Bryan T's MKII (29 Sep 2026, a transient on a track sent to
| both, recorded over USB in Logic): master off, 0 samples; master on, CUE
| 43976 vs MAIN 44008, 32 samples = 2 blocks. The producer writes CUE this
| many blocks AHEAD of MAIN's slot while the byte is set. Ahead is safe: the
| consumer is behind the producer, and no later block's write touches a
| slot's CUE field except the block that owns it.
.set MASTER_TRACK_ON,        0x80000034
.set CUE_MASTER_LAG_BLOCKS,  2

| ---- frame geometry --------------------------------------------------------
| The producer fills TWO rings per frame: the stream's frame, usb_frame_bytes
| of the checked fields in wire order (tracks 1-8 L/R first, then MAIN L/R,
| CUE L/R, MASTER L/R -- 4-byte little-endian subslots carrying 24 bits),
| for the HIGH SPEED stream, and an 8-byte stereo sum for FULL SPEED. Both
| are indexed by the same frame count, so the wrap arithmetic has one form.
|
| A sample is the read-back word with its low byte cleared: the arena's
| full scale is 2^31, so the subslot's 24 valid bits are its top 24.
|
| Why the poll is 250 us: 20 ch x 4 B at 44.1 kHz is 3,528 B per
| millisecond, and one high-speed isochronous transaction carries at most
| 1,024 B. At bInterval 2 a packet is 11.025 frames x the combination's
| frame bytes, at most 12 frames with the servo: 960 B at 20 channels.
| Full speed carries the stereo sum only: 44.1 frames x 8 B = 353 B per 1 ms
| frame, under the 1,023 B cap. UAC1 cannot poll faster than 1 ms even at
| high speed (Apple TN3190: bInterval must be 4); this is why the
| descriptors are UAC2.
.set SLOT_BYTES,   80           | the largest frame (20 ch): the ring's size per frame
.set AUD_SPILL,    12           | frames past the ring's end a wrapping packet runs into (the HS cap)
.set SUM_BYTES,    8            | sum slot: (L,R) x 4 B
.set PKT_MAX_FS,   45*SUM_BYTES | 360: the largest 1 ms packet
.set PKT_BUF,      960          | packet buffer stride (>= the HS cap, 12*80)
.set STEP_HS,      11025        | 11.025 frames per 250 us packet, x1000 (<= 20 ch)
.set STEP_FS,      44100        | 44.1 frames per 1 ms packet, x1000
.set SERVO_SHIFT,  1            | proportional gain G = 2^SERVO_SHIFT: x1000
                                | frames per packet per frame of fill error
.set SERVO_MAX,    200          | correction clamp: +-0.2 frame per packet, x1000

| Four queue slots, so the host always finds a packet waiting: four packets
| cover 1 ms of polls. The frame ISR (every 363 us) is the only context that
| queues, so the queue must outlast one block plus that interrupt's latency.
.set SRAM_ODTDS,   0x800079c0   | EP3 IN's NSLOT dTDs in on-chip SRAM (128 B, 32-aligned; Claims.sram)
| The producer's per-frame state, in on-chip SRAM (Claims.sram): a frame's
| reads and writes of it never miss the cache or wait for the SDRAM. The
| MAIN, CUE and MASTER write pointers (through the alias), advanced a frame
| at a time; frame bytes less the tracks' 64 when checked; this frame's
| MAIN/CUE pairs (MAIN_CUE_BASE + f * 8); the block's end.
.set PROD_SRAM,    0x80007a40   | 32 B (Claims.sram)
.set prod_pm,      PROD_SRAM
.set prod_pc,      PROD_SRAM+4
.set prod_px,      PROD_SRAM+8
.set prod_skip,    PROD_SRAM+12
.set prod_src,     PROD_SRAM+16
.set prod_end,     PROD_SRAM+20
| the producer's d6: the block's checked boxes
.set PF_PRE,       0
.set PF_POST,      1
.set PF_MAIN,      2
.set PF_CUE,       3
.set PF_MASTER,    4
.set NSLOT,        4            | power of two: slot arithmetic is a mask
.set UNCACHED,     0x08000000   | + an SDRAM address = the same memory,
                                | cache-inhibited (PLACEMENT.md)

| The rings live in the unit's data and are zeroed by the loader. 1024
| frames = 23 ms of buffer. The sum ring is the CPU's alone, through its
| cached address; the high-speed ring is read by the controller and touched
| by the CPU only through the uncached alias, so neither needs cache
| maintenance.
.set AUD_FRAMES,   1024
.set AUD_TARGET,   64           | ring fill the stream starts at and the servo
                                    | holds: ~1.5 ms (512 before the proportional
                                    | servo; the unit held +-13 around 256 and
                                    | 128 under a busy project, 28 Sep 2026)

.set PORTSC1,    0xfc0b0184         | bits 27:26 = port speed, 2 = high

    .text
| ---- SET_INTERFACE shim (installed at 0x4001dd04) ---------------------------
| Displaced: movel 0xfc0b01c4,%d0. The AudioStreaming interface (usb_as_iface,
| 4 with MIDI, 2 without) records the requested alt setting and completes the
| status stage; any other interface falls through to the stock handler
| unchanged.
|
| The shim RECORDS the request. Everything that builds EP3 state — the
| queue head, the dTDs, ENDPTCTRL3, the ring cursors — is done by the frame
| ISR (audio_ep3_up / audio_ep3_down), the one context that also queues
| packets. This runs from the USB interrupt; if it re-initialized the
| endpoint itself, a SET_INTERFACE landing in the middle of a kick would
| rewrite a queue the kick was still building, and the kick would then prime
| the remains. One owner, one byte of shared state.
|
| The one exception is alt 0's FLUSH, done here as well: the host may send
| its next IN within microseconds of the status stage, before the frame ISR
| has had its block, and a packet already queued would answer it — audio
| after teardown. A flush only cancels what is in flight, is idempotent, and
| builds nothing, so it is safe from this context; the kick checks the
| request byte before it queues, so nothing new follows it; and the frame
| ISR flushes again on its way down. (verify_usb asserts silence after
| alt 0.)
|
| Interrupt levels, from the firmware's own INTC writes: the USB interrupt
| is INTC1 source 47 at level 4 (moveq #4 / moveb ->0xfc04c06f at
| 0x4001e024); the frame IRQ is EPORT IRQ1 at level 5 (0x4001fc30). So the
| frame ISR can preempt this shim — harmless, it only ever sees the request
| byte — and this shim can never interrupt a kick.
    .global audio_setiface_shim
audio_setiface_shim:
    mvzb    SETUP_IFACE,%d0
    mvzb    usb_as_iface,%d1
    cmpl    %d0,%d1
    bne     5f                      | not the AudioStreaming interface -> stock
    mvzb    SETUP_ALT,%d0
    tstl    %d0
    beqs    2f
    moveq   #1,%d0                  | any non-zero alt is the streaming one
    moveb   %d0,usbaudio_alt        | the request; the frame ISR brings EP3 up
    bras    3f
2:  clrb    usbaudio_alt            | the request FIRST: no kick queues past it
    bsr     audio_ep3_flush         | then cancel what is already queued
3:  jsr     EP0_STATUS_IN
    jmp     SETIFACE_DONE
5:  movel   0xfc0b01c4,%d0          | displaced
    jmp     SETIFACE_STOCK

| ---- GET_INTERFACE shim (installed at 0x4001d824) ---------------------------
| Displaced: pea 0x400e20a1 (the stock 1-byte "00"). The AudioStreaming
| interface reports the alt setting the host asked for (whether or not the
| frame ISR has acted on it yet, which it does within one block); the IN
| interface (usb_in_iface, which exists only while IN is not OFF) reports
| its own unit's alt byte; every other interface keeps the stock answer.
    .global audio_getiface_shim
audio_getiface_shim:
    mvzb    SETUP_IFACE,%d0
    mvzb    usb_as_iface,%d1
    cmpl    %d0,%d1
    bnes    1f
    pea     usbaudio_alt
    jmp     GETIFACE_REJOIN
1:  mvzb    usb_in_iface,%d1        | IN OFF: 0, no such interface
    tstb    %d1
    beqs    2f
    cmpl    %d0,%d1
    bnes    2f
    pea     in_alt
    jmp     GETIFACE_REJOIN
2:  pea     GETIFACE_STOCKP
    jmp     GETIFACE_REJOIN

| ---- bus reset and session end (installed at 0x4001e91c and 0x4001e952) -------
| The stock USBSTS.URI handler (jsr 0x4001d6b8: flush, dTD tokens cleared,
| ENDPTCTRL1 cleared) and the OTGSC.BSVIS session-end path (USBCMD.RS and
| USBINTR cleared) write neither this unit's alt bytes nor ENDPTCTRL3. USB
| 2.0 9.1.1.5 puts every interface back to alternate setting 0 on a reset;
| without these two shims a cable pull or a host crash with the stream open
| left usbaudio_alt (and USB AUDIO IN's in_alt) at 1: the producer kept
| running, the kick re-primed EP3 IN before the device was configured, the
| next SET_INTERFACE took .Lep3_same, and GET_INTERFACE answered 1.
| Both shims record the alt 0 request, the way audio_setiface_shim does for
| alt 0, and the frame ISR tears EP3 down. Both sites are USB MIDI's as
| well (usbmidi_rx_reset_shim, usbmidi_rx_sessend_shim: EP2 down); this
| module overrides those detours and calls usbmidi_rx_bus_end itself. The
| ISR prologue has saved d0-d2/a0-a4 (the epilogue at 0x4001e98e restores
| them); a2 is live in the session-end path (0x4001e93a, used at
| 0x4001e974) and is not touched.
|
| Reset: displaced jsr %pc@(0x4001d6b8); moveq #64,%d0 (6 bytes); the next
| instruction is 0x4001e922.
    .global audio_reset_shim
audio_reset_shim:
    jsr     0x4001d6b8              | displaced
    bsr     audio_alt0_request
    jsr     usbmidi_rx_bus_end      | USB MIDI's detour at this site, which this one overrides
    moveq   #64,%d0                 | displaced: USBSTS.URI, written back at 0x4001e922
    jmp     0x4001e922

| Session end: displaced movel 0xfc0b0140,%d0 (USBCMD, 6 bytes); the next
| instruction is 0x4001e958. The request is recorded before the stock code
| clears USBCMD.RS.
    .global audio_sessend_shim
audio_sessend_shim:
    bsr     audio_alt0_request
    jsr     usbmidi_rx_bus_end      | USB MIDI's detour at this site, which this one overrides
    movel   0xfc0b0140,%d0          | displaced
    jmp     0x4001e958

| Alt 0 requested on every interface this unit and USB AUDIO IN own. The
| request bytes only: the frame ISR flushes, disables EP3 and clears the
| dTDs. Clobbers nothing.
audio_alt0_request:
    clrb    usbaudio_alt
    clrb    in_alt
    rts

| ---- EP0 buffer-page fix (installed at 0x4001d4b2 inside usb_ep0_send) -------
| usb_ep0_send sets only the dTD's buffer PAGE 0 (0x4ec95028), never PAGE 1.
| A descriptor whose buffer crosses a 4 KB page then transmits only the bytes
| before the boundary and zeros after (seen in his build as the full-speed
| config truncated to the stock 32-byte MSC part). This shim also fills
| PAGE 1 = (buffer & ~0xfff) + 0x1000, so an EP0 send that spans a page
| boundary completes wherever the descriptors are linked.
|
| Displaced: movel %a0@,0x4ec95028 (a0 = &buffer-arg, set by the preceding
| lea %sp@(12),%a0); rejoin at the following lea (0x4001d4b8). %d0 is dead
| across the rejoin (reloaded at 0x4001d4da), so clobbering it is safe.
    .global audio_ep0page_shim
audio_ep0page_shim:
    movel   %a0@,%d0               | the descriptor buffer pointer (arg)
    movel   %d0,0x4ec95028         | dTD buffer page 0 (displaced instruction)
    andil   #0xfffff000,%d0
    addil   #0x1000,%d0
    movel   %d0,0x4ec9502c         | dTD buffer page 1 — the fix
    jmp     0x4001d4b8

| ---- usb_isr shim (installed at 0x4001e606, USB MIDI's site) ---------------
| Retires EP3 IN completions, then chains to USB MIDI's receive shim
| (usbmidi.s), which takes the EP2 OUT completion and hands on to
| usbmidi.s's, which handles EP2 IN and runs the original displaced instruction.
    .global audio_isr_shim
audio_isr_shim:
    lea     %sp@(-16),%sp
    moveml  %d0-%d1/%a0-%a1,%sp@    | all this shim touches
    | A clock SET_CUR whose data stage outlived audio_ctrl_shim's wait: a new
    | SETUP means the host gave it up; otherwise its OUT completion is ours,
    | taken before the stock completion loop can see it.
    tstb    uac2_set_pending
    beqs    4f
    movel   SETUPSTAT,%d0
    btst    #0,%d0
    beqs    3f
    clrb    uac2_set_pending        | superseded by a new SETUP
    bras    4f
3:  movel   EPCOMPLETE,%d0
    btst    #0,%d0                  | EP0 OUT
    beqs    4f
    bsr     uac2_set_done
4:
    | Exactly ONE place queues packets on EP3: the per-block producer in
    | frame_isr. This shim only retires the completion bit so it cannot go
    | stale; the queue's own state is the ACTIVE bit of each dTD, which the
    | controller clears itself, so there is no bookkeeping to race on. The
    | dTDs are queued WITHOUT IOC — 2000 completion interrupts a second buy
    | nothing when nobody needs to be told.
    movel   EPCOMPLETE,%d0
    movel   #EP3IN_BIT,%d1
    andl    %d1,%d0
    beqs    2f
    movel   #EP3IN_BIT,%d1
    movel   %d1,EPCOMPLETE          | W1C EP3 IN
2:  moveml  %sp@,%d0-%d1/%a0-%a1
    lea     %sp@(16),%sp
    jmp     usbmidi_rx_isr_shim      | USB MIDI's shim, whose detour this one stands in for

| ---- the iso packet builder -------------------------------------------------
| Each packet holds the next n frames from the ring: n = 11/12 at high speed
| (11025/1000 per packet) or 44/45 at
| full speed (44100/1000), so the emitted stream is an exact, gap-free
| substring of what the producer wrote. Underrun queues nothing (the host's
| IN gets an empty packet); a producer that laps the ring (host stopped
| draining) resyncs and counts an overrun.
| Runs from the frame shim only; may clobber every register but %sp.
|
| An isochronous IN cannot NAK: an IN token that arrives with nothing primed
| is answered with a zero-length packet, and a hole in the stream is a
| click. The frame ISR keeps up to NSLOT packets queued and the controller
| chains from one to the next on its own.
|
| The slots are used in turn: aud_tail is the next to fill, so fill order is
| tail-3, tail-2, tail-1 (oldest to newest) and the controller retires them
| in that order. A slot whose dTD is still ACTIVE is in flight or queued and
| is left alone.
usbaudio_kick:
    tstb    usbaudio_alt            | alt 0 requested since this block began:
    beq     9f                      | queue nothing more (teardown follows)
    | THE FIRST POLL SETS THE CUSHION. The host polls EP3 IN some time after
    | its SET_INTERFACE (macOS: about 460 frames later, Bryan T's unit, 27
    | Sep 2026), and the producer keeps filling meanwhile, so a cursor set
    | at bring-up starts the stream that much further behind than
    | AUD_TARGET and the servo holds it there. So: bring-up queues NSLOT
    | packets and sets aud_await to 1; this block marks them queued (2);
    | from then on nothing more is built until one of them has RETIRED, the
    | controller's own record of a poll (the ACTIVE bit it clears), and at
    | that block the cursor is re-set to AUD_TARGET behind the producer.
    | The frames between are skipped once, before the host has audio;
    | usbaudio_anchor holds the count.
    mvzb    aud_await,%d0
    cmpil   #2,%d0
    bnes    .Lk_build
    moveq   #0,%d2                  | any slot no longer ACTIVE = a poll happened
.Lk_await:
    movel   %d2,%d0
    bsr     audio_dtd_of
    movel   %a0@(4),%d1
    btst    #7,%d1
    beqs    .Lk_anchor
    addql   #1,%d2
    cmpil   #NSLOT,%d2
    bcss    .Lk_await
    rts                             | all still queued: the host has not polled
.Lk_anchor:
    movel   aud_produced,%d0
    movel   %d0,%d1
    subl    usbaudio_consumed,%d1   | fill now
    subil   #AUD_TARGET,%d1         | beyond the cushion: skipped
    bles    .Lk_anchored            | at or under it already (a prompt host)
    movel   %d1,usbaudio_anchor
    subil   #AUD_TARGET,%d0
    movel   %d0,usbaudio_consumed
.Lk_anchored:
    clrb    aud_await
.Lk_build:
    moveq   #NSLOT,%d0
    movel   %d0,%sp@-               | builds left this block
1:  bsr     audio_pkt_build         | fill the tail slot, if free
    tstl    %d0
    beqs    2f
    subql   #1,%sp@
    bnes    1b
2:  addql   #4,%sp
    mvzb    aud_await,%d0
    cmpil   #1,%d0
    bnes    3f
    moveq   #2,%d0                  | the bring-up's packets are queued
    moveb   %d0,aud_await
3:
    | Self-heal. The add-dTD tripwire (audio_pkt_build) is the documented
    | way to append to a running queue, and its hazard window is reported by
    | the hardware clearing ATDTW. Should anything ever leave an ACTIVE dTD
    | behind with the endpoint idle — a missed hazard, a flush that raced a
    | prime — the stream would otherwise stall until the next alt 0/1. So
    | every block ends with: idle endpoint + queued dTD = prime the oldest,
    | and count it, so a silent recovery is still measurable.
    movel   ENDPTSTAT,%d0
    movel   EPPRIME,%d1
    orl     %d1,%d0
    andil   #EP3IN_BIT,%d0
    bnes    9f                      | primed or priming: running
    mvzb    aud_tail,%d2            | oldest first: fill order from the tail
    bsr     audio_oldest
    tstl    %d0
    beqs    9f                      | nothing queued: idle is correct
    bsr     audio_prime             | %a4 = head dTD
    addql   #1,usbaudio_reprimes
9:  rts

| %d0 = slot index (taken mod NSLOT) -> %a0 = its dTD, in on-chip SRAM.
| Clobbers d0.
audio_dtd_of:
    andil   #NSLOT-1,%d0
    lsll    #5,%d0
    moveal  #SRAM_ODTDS,%a0
    addal   %d0,%a0
    rts

| The oldest queued dTD: the first ACTIVE one from slot %d2 onward, in fill
| order. Returns d0 = 1 and %a4 = it, or d0 = 0 when none is ACTIVE.
| Clobbers d0-d3/a0.
audio_oldest:
    moveq   #NSLOT-1,%d3
1:  movel   %d2,%d0
    bsr     audio_dtd_of
    movel   %a0@(4),%d1
    btst    #7,%d1
    bnes    2f
    addql   #1,%d2
    subql   #1,%d3
    bpls    1b
    moveq   #0,%d0
    rts
2:  moveal  %a0,%a4
    moveq   #1,%d0
    rts

| Point the queue head at %a4 and prime EP3 IN — the "list empty" case of the
| Chipidea add-dTD procedure. Clobbers d0/a1.
audio_prime:
    moveal  qh_ep3,%a1
    movel   %a4,%a1@(8)             | dQH next dTD
    clrl    %a1@(12)                | dQH token: ACTIVE/HALT clear before a prime
    movel   #EP3IN_BIT,%d0
    movel   %d0,EPPRIME
    rts

| Build one packet into the tail slot and queue it. Returns d0 = 1 if a packet
| was queued, 0 if the slot was busy or the ring could not fill one.
audio_pkt_build:
    mvzb    aud_tail,%d0
    moveal  %d0,%a6                 | a6 = slot index, kept across the copy
    bsr     audio_dtd_of            | a0 = this slot's dTD
    movel   %a0@(4),%d1
    btst    #7,%d1                  | ACTIVE: in flight or queued
    bne     .Lpb_none
    tstb    usbaudio_alt            | (re-checked per packet: alt 0 can land
    beq     .Lpb_none               |  between two builds in one block)
    movel   aud_produced,%d0
    movel   usbaudio_consumed,%d1
    movel   %d0,%d2
    subl    %d1,%d2                 | d2 = frames available
    cmpil   #AUD_FRAMES,%d2
    blss    3f                      | within the ring: fine
    addql   #1,usbaudio_overruns
    movel   %d0,%d1
    subil   #AUD_FRAMES,%d1
    movel   %d1,usbaudio_consumed   | resync to the ring's trailing edge
    movel   #AUD_FRAMES,%d2
3:  tstb    aud_await               | low and high water since the first poll
    bnes    5f
    cmpl    usbaudio_minfill,%d2
    bccs    4f
    movel   %d2,usbaudio_minfill
4:  cmpl    usbaudio_maxfill,%d2
    blss    5f
    movel   %d2,usbaudio_maxfill
5:  movel   usbaudio_acc,%d3
    | RATE SERVO. The endpoint is ASYNCHRONOUS: the device sends at its own
    | clock and the host adapts. The host's polls run on ITS clock, so a fixed
    | number of frames per poll would drain the ring faster or slower than the
    | producer fills it, by the two clocks' drift, and the ring would under-
    | or overrun within minutes. The servo is proportional: each packet drains
    | nominal + G x (fill - AUD_TARGET) / 1000 frames, clamped to +-SERVO_MAX,
    | which is "send what is produced" at the device's clock. The fill decays
    | to the target with a time constant of 1000/G packets (G = 2: 500, about
    | 125 ms at high speed) and drift eps leaves eps x STEP / G frames of
    | error (0.06 at the 11 ppm Bryan T's Mac showed). Held there, the fill no
    | longer wanders, so USB AUDIO IN's ring, whose fill with this one's sums to
    | a constant under implicit feedback, holds too.
    movel   aud_step,%d5            | nominal frames per packet, x1000
    tstb    aud_await               | until the host's first poll anchors the
    bnes    .Lsrv_done              | ring, send nominal: the bring-up burst's
                                    | fill falls 11 per packet, not a clock error
    movel   %d2,%d0
    subil   #AUD_TARGET,%d0         | fill error, signed
    asll    #SERVO_SHIFT,%d0        | x G
    cmpil   #SERVO_MAX,%d0
    bles    .Lsrv_hi
    movel   #SERVO_MAX,%d0
.Lsrv_hi:
    cmpil   #-SERVO_MAX,%d0
    bges    .Lsrv_lo
    movel   #-SERVO_MAX,%d0
.Lsrv_lo:
    addl    %d0,%d5                 | step + correction (> 0: STEP_HS - SERVO_MAX)
.Lsrv_done:
    addl    %d5,%d3
    movel   #1000,%d7
    movel   %d3,%d4
    divu.l  %d7,%d4                 | d4 = n = (acc+step)/1000
    movel   %d4,%d5
    mulu.l  %d7,%d5
    movel   %d3,%d6
    subl    %d5,%d6                 | d6 = new acc
    cmpl    %d4,%d2
    bccs    .Lhave_frames
    addql   #1,usbaudio_underruns
    bra     .Lpb_none               | available < n: underrun, send nothing
.Lhave_frames:
    movel   %d6,usbaudio_acc
    movel   %d4,usbaudio_lastn
    movel   %d2,usbaudio_lastfill
    | ---- the packet's bytes ------------------------------------------------
    | High speed: the packet IS the ring. The producer writes each frame in
    | the stream's own layout (usb_frame_bytes a frame, the checked fields in
    | wire order) through the uncached alias, so the dTD points at the n
    | frames from the cursor and nothing is copied. A packet that runs past
    | the ring's last frame continues into the spill (AUD_SPILL frames past
    | it): the frames from the ring's start are copied there first, about
    | one packet in 93. Full speed copies the 8-byte sum ring into this
    | slot's buffer (aud_bufs + slot * PKT_BUF), in at most two straight runs.
    | a3 = the packet's first byte, through the uncached alias.
    movel   %d4,%d3                 | d3 = n
    movel   usbaudio_consumed,%d1
    andil   #AUD_FRAMES-1,%d1       | ring index of the first frame
    movel   #AUD_FRAMES,%d0
    subl    %d1,%d0                 | d0 = frames before the ring wraps (>= 1)
    tstb    aud_hs
    beqs    .Lcopy_fs
    movel   usb_frame_bytes,%d2
    mulu.l  %d2,%d1
    moveal  #(aud_ring+UNCACHED),%a3
    addal   %d1,%a3                 | a3 = the first frame, in the ring
    cmpl    %d0,%d3
    bls     .Lcopied                | within the ring: nothing to move
    subl    %d0,%d3                 | frames past the end
    mulu.l  %d2,%d3
    lsrl    #2,%d3                  | their longs (a frame is a multiple of 8 B)
    moveal  #(aud_ring+UNCACHED),%a2
    movel   %d2,%d1
    lsll    #8,%d1
    lsll    #2,%d1                  | AUD_FRAMES * frame bytes: the spill
    lea     %a2@(0,%d1:l),%a1
1:  movel   %a2@+,%a1@+
    subql   #1,%d3
    bnes    1b
    bras    .Lcopied
.Lcopy_fs:
    movel   %a6,%d2
    lsll    #8,%d2
    lsll    #2,%d2                  | slot * 1024
    movel   %a6,%d5
    lsll    #6,%d5                  | slot * 64
    subl    %d5,%d2                 | slot * 960 = slot * PKT_BUF
    moveal  #(aud_bufs+UNCACHED),%a3
    addal   %d2,%a3
    moveal  %a3,%a1
    lea     aud_sum,%a2
    lsll    #3,%d1
    addal   %d1,%a2
    cmpl    %d0,%d3
    bhis    .Lfs_wrap
    movel   %d3,%d0
    bsr     audio_copy_sum
    bras    .Lcopied
.Lfs_wrap:
    subl    %d0,%d3
    moveal  %d3,%a5
    bsr     audio_copy_sum
    lea     aud_sum,%a2
    movel   %a5,%d0
    bsr     audio_copy_sum
.Lcopied:
    movel   usbaudio_lastn,%d4      | n again (the copy clobbered it)
    addl    %d4,usbaudio_consumed
    movel   %d4,%d6
    tstb    aud_hs
    beqs    5f
    movel   usb_frame_bytes,%d1     | nbytes = n * the stream's frame bytes
    mulu.l  %d1,%d6
    bras    6f
5:  lsll    #3,%d6                  | nbytes = n * 8
6:  | ---- the dTD: buffer pointers first, the ACTIVE token LAST -------------
    | The packet's bytes were written through the uncached alias (precise
    | stores, each complete before the next instruction) and the dTD is in
    | on-chip SRAM, written in program order: the controller cannot see an
    | ACTIVE token over a half-built descriptor or a half-written packet.
    moveq   #1,%d1
    movel   %d1,%a0@                | next = terminate
    movel   %a3,%a0@(8)             | buffer page 0
    movel   %a3,%d1
    andil   #0xfffff000,%d1
    addil   #0x1000,%d1
    movel   %d1,%a0@(12)            | page 1: a 960-byte buffer can straddle a 4 KB page
    movel   %d6,%d1
    swap    %d1                     | nbytes << 16
    oril    #0x80,%d1               | ACTIVE (no IOC: completions buy nothing)
    movel   %d1,%a0@(4)
    | ---- queue it: the Chipidea "add dTD" procedure -------------------------
    | Case 1, list empty (the previous slot in fill order is not ACTIVE, so
    | nothing older is either): point the queue head at this dTD and prime.
    | Case 2, list running: link this dTD after the previous one, then the
    | tripwire — set ATDTW, sample ENDPTSTAT, trust the sample only if ATDTW
    | is still set (hardware clears it when the sample fell in its hazard
    | window). Still primed: the controller follows the link by itself. Not
    | primed: it retired the previous dTD before it saw the link, so the HEAD
    | to prime is the oldest dTD still ACTIVE (never skip a queued packet),
    | which is this one if every other has retired.
    moveal  %a0,%a4                 | a4 = the head to prime, if it comes to that
    moveal  %a0,%a5                 | a5 = this dTD (audio_dtd_of returns in a0)
    movel   %a6,%d0
    subql   #1,%d0
    bsr     audio_dtd_of
    moveal  %a0,%a2                 | a2 = the previous slot's dTD
    moveal  %a5,%a0
    movel   %a2@(4),%d0
    btst    #7,%d0
    beqs    .Lenq_prime             | case 1
    movel   %a0,%a2@                | case 2: previous.next = this
    movel   EPPRIME,%d0
    andil   #EP3IN_BIT,%d0
    bnes    .Lenq_done              | a prime is pending: it will read the list
    moveq   #16,%d2                 | tripwire attempts (bounded: this is an ISR)
.Lenq_trip:
    movel   USBCMD,%d0
    oril    #ATDTW,%d0
    movel   %d0,USBCMD
    movel   ENDPTSTAT,%d1
    andil   #EP3IN_BIT,%d1          | the sample
    movel   USBCMD,%d0
    andil   #ATDTW,%d0
    bnes    .Lenq_sampled
    subql   #1,%d2
    bnes    .Lenq_trip              | hazard: the sample is void, take another
    bras    .Lenq_done              | never settled: assume running; the
.Lenq_sampled:                      | self-heal re-primes next block if not
    movel   USBCMD,%d0
    andil   #0xffffbfff,%d0         | ~ATDTW
    movel   %d0,USBCMD
    tstl    %d1
    bnes    .Lenq_done              | still running: it will follow the link
    movel   %a6,%d2
    addql   #1,%d2                  | oldest first: tail+1 .. tail in fill order
    bsr     audio_oldest            | a4 = the oldest ACTIVE (this one at worst)
.Lenq_prime:
    bsr     audio_prime
.Lenq_done:
    movel   %a6,%d0
    addql   #1,%d0
    andil   #NSLOT-1,%d0
    moveb   %d0,aud_tail            | the next slot fills next
    moveq   #1,%d0
    rts
.Lpb_none:
    moveq   #0,%d0
    rts

| Copy d0 (>= 1) 8-byte stereo-sum frames from %a2 to %a1, both advanced.
| Clobbers nothing.
audio_copy_sum:
1:  movel   %a2@+,%a1@+
    movel   %a2@+,%a1@+
    subql   #1,%d0
    bnes    1b
    rts

| Mark the queue idle: zero every dTD (ACTIVE clear, next = terminate) and
| start filling at slot 0. Written through the uncached alias, so no cpushl.
| Clobbers d0/d1/a1.
audio_dtds_clear:
    moveal  #SRAM_ODTDS,%a1
    moveq   #NSLOT*8-1,%d1
1:  clrl    %a1@+
    subql   #1,%d1
    bpls    1b
    moveal  #SRAM_ODTDS,%a1
    moveq   #1,%d0
    moveq   #NSLOT-1,%d1
2:  movel   %d0,%a1@                | next = terminate
    lea     %a1@(32),%a1
    subql   #1,%d1
    bpls    2b
    clrb    aud_tail
    rts

| Resolve EP3's queue head from ENDPTLISTADDR. Returns it in %a0 and caches it
| in qh_ep3. The firmware programs 0x4EC94800 here; a value outside SDRAM is
| not an endpoint list, and the known constant is used instead.
audio_qh_resolve:
    movel   EPLISTADDR,%d0
    andil   #0xfffff800,%d0
    cmpil   #0x40000000,%d0
    blts    .Lqh_fallback
    cmpil   #0x50000000,%d0
    bges    .Lqh_fallback
    bras    .Lqh_have
.Lqh_fallback:
    movel   #(QH_EP3IN - QH_EP3IN_OFF),%d0
.Lqh_have:
    addil   #QH_EP3IN_OFF,%d0
    movel   %d0,qh_ep3
    moveal  %d0,%a0
    rts

| ---- EP3 bring-up / teardown: frame-ISR context ONLY ------------------------
| The SET_INTERFACE shim records the host's request in usbaudio_alt; the frame
| shim compares it with aud_running once per block and calls one of these.
| Everything EP3 — queue head, dTDs, ENDPTCTRL3, ring cursors — is owned by
| that one context, so nothing here can interleave with a kick.
audio_ep3_up:
    | FLUSH FIRST. A dTD left primed by an earlier session must not be in
    | flight while the queue head is rewritten underneath it.
    bsr     audio_ep3_flush
    | ZERO THE WHOLE 64-BYTE dQH. EP3's queue head sits past anything the
    | stock firmware ever initializes, so on hardware its TOKEN (+0x0C) and
    | buffer pointers (+0x10..+0x1C) hold power-on garbage. The device
    | controller is a real bus master on silicon: it acts on that token's
    | ACTIVE bit and those pointers, then writes transfer status back through
    | them — an arbitrary memory write, which lands wherever the garbage
    | points (image code included). The firmware's own EP0 setup at
    | 0x4001d656 clears the token for exactly this reason; clearing the whole
    | structure is the safe superset.
    bsr     audio_qh_resolve        | %a0 = EP3 dQH, from the controller
    moveq   #15,%d1
1:  clrl    %a0@+
    subql   #1,%d1
    bpls    1b
    moveal  qh_ep3,%a0              | resolved just above
    | The SPEED decides the stream: the combination's channels in <= the HS
    | cap every 250 us at high speed, the stereo sum
    | in <= 360 B packets every 1 ms at full speed. PORTSC1 bits 27:26 are
    | the negotiated speed (2 = high); the responder picks the config
    | descriptor by the same bits, so the format the host was told and the
    | packets it gets cannot disagree.
    movel   PORTSC1,%d0
    lsrl    #8,%d0
    lsrl    #8,%d0
    lsrl    #8,%d0
    lsrl    #2,%d0
    andil   #3,%d0
    cmpil   #2,%d0
    bnes    .Lspeed_fs
    moveq   #1,%d0
    moveb   %d0,aud_hs
    movel   usb_hs_step,%d0
    movel   %d0,aud_step
    | the dQH cap: the combination's largest packet (latched by cfgsel)
    movel   usb_hs_cap,%d0
    swap    %d0
    addil   #0x60000000,%d0         | Mult 1, ZLT off, maxpkt = the combination's cap
    bras    .Lspeed_set
.Lspeed_fs:
    clrb    aud_hs
    movel   #STEP_FS,%d0
    movel   %d0,aud_step
    movel   #(0x60000000+(PKT_MAX_FS<<16)),%d0  | Mult 1, ZLT off, maxpkt 360
.Lspeed_set:
    movel   %d0,%a0@
    clrl    %a0@(4)                 | current dTD
    moveq   #1,%d0
    movel   %d0,%a0@(8)             | no dTD primed yet (terminate)
    clrl    %a0@(12)                | TOKEN — the field the firmware clears
    bsr     audio_dtds_clear        | every queue slot idle
    movel   ENDPTCTRL3,%d0          | ENDPTCTRL3: TXE + isochronous (the bench
    andil   #0x0000ffff,%d0         | reads the type to serve one dTD per poll);
    oril    #0x00840000,%d0         | the TX half only -- the RX half is EP3 OUT
    movel   %d0,ENDPTCTRL3          | (USB AUDIO IN), which must survive this
    movel   aud_produced,%d0
    subil   #AUD_TARGET,%d0         | start a full cushion BEHIND the producer:
    bccs    .Lcons_ok               | the ring is already full, so there is no
    moveq   #0,%d0                  | priming gap and no startup underruns
.Lcons_ok:
    movel   %d0,usbaudio_consumed
    clrl    usbaudio_acc
    moveq   #1,%d0
    moveb   %d0,aud_running
    moveb   %d0,aud_await           | 1: queue, then wait for the host's first poll
    movel   #0x7fffffff,%d0
    movel   %d0,usbaudio_minfill
    clrl    usbaudio_maxfill
    clrl    usbaudio_anchor
    rts

audio_ep3_down:
    | FLUSH the endpoint. Clearing ENDPTCTRL3 disables it but does NOT cancel
    | a dTD that is already primed, so a packet queued microseconds before
    | alt 0 would still go out and the host would see audio after teardown.
    bsr     audio_ep3_flush
    movel   ENDPTCTRL3,%d0          | TX half off; the RX half (EP3 OUT, USB
    andil   #0x0000ffff,%d0         | AUDIO IN) stays as it was. d0 is free
    movel   %d0,ENDPTCTRL3          | here: the flush above clobbered it
    bsr     audio_dtds_clear        | a flushed dTD still reads ACTIVE
    clrb    aud_running
    rts

| Flush EP3 IN and wait for it. The documented Chipidea sequence, not a
| single write: a prime that lands while a flush is in progress survives it,
| so after ENDPTFLUSH clears, ENDPTSTAT is checked and the flush repeated
| while the endpoint still shows primed. Bounded, because this runs in the
| frame ISR and a controller that never answers must not wedge the machine.
| Clobbers d0/d1.
audio_ep3_flush:
    movel   %d2,%sp@-
    moveq   #16,%d1                 | attempts
1:  movel   #EP3IN_BIT,%d0
    movel   %d0,EPFLUSH
    movel   #0x10000,%d2            | bound: a flush with USBCMD.RS clear (session end) may never complete
2:  movel   EPFLUSH,%d0
    andil   #EP3IN_BIT,%d0
    beqs    4f
    subql   #1,%d2
    bnes    2b
4:
    movel   ENDPTSTAT,%d0
    andil   #EP3IN_BIT,%d0
    beqs    3f                      | idle: done
    subql   #1,%d1
    bnes    1b
3:  movel   %sp@+,%d2
    rts

| ---- the per-block producer (installed at 0x4000d9a0, inside frame_isr) ----
| frame_isr runs once per 16-frame block: the block clock, the audio and the
| trigger to send are all firmware events.
|
| The hook site is the LAST instruction before frame_isr's
| `moveml %sp@,%d0-%fp` epilogue, so every register is about to be reloaded
| from the stack — this shim may clobber d0-a6 freely. It must not touch %sp.
|
| Displaced: clrl 0x46104d4e (6 bytes), rejoin 0x4000d9a6.

| d -> saturated to 24 bits (-2^23 .. 2^23-1). Inline, used for the tracks'
| stereo sum (two per frame). The bounds live in %a5 (0x7fffff) and %a6
| (-0x800000), loaded once per block.
.macro SAT24 d
    cmpl    %a5,\d
    jble    .Lsat_lo\@              | jbcc: gas picks the shortest branch
    movel   %a5,\d
    jbra    .Lsat_ok\@
.Lsat_lo\@:
    cmpl    %a6,\d
    jbge    .Lsat_ok\@
    movel   %a6,\d
.Lsat_ok\@:
.endm

| The same with immediate bounds: the TRACKS POST frame carries the gain
| cursor in %a5, so the sum cannot use the register form.
.macro SAT24I d
    cmpil   #0x7fffff,\d
    jble    .Lsati_lo\@
    movel   #0x7fffff,\d
    jbra    .Lsati_ok\@
.Lsati_lo\@:
    cmpil   #-0x800000,\d
    jbge    .Lsati_ok\@
    movel   #-0x800000,\d
.Lsati_ok\@:
.endm

| d2 = the stem of the read-back word at %a0@(off) by the gain at `gain`:
| the word's low byte cleared (the DSP's hi/lo join drops it), one
| fractional macl by g << 10, so ACC = floor(g x / 2^13), whose top 24 bits
| are floor(8 g x / 2^24). Clobbers d0.
.macro POST_WORD gain, off
    movel   %a0@(\off),%d2
    clrb    %d2
    movel   \gain,%d0
    macl    %d0,%d2,%acc0
    movclrl %acc0,%d2
.endm
| d2 -> the ring: top 24 bits, little-endian.
.macro POST_STORE
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
.endm

    .global audio_frame_shim
audio_frame_shim:
    | The producer runs only while the host asks for the stream (usbaudio_alt,
    | the SET_INTERFACE request, so from the block after it). His build idled
    | until alt 1 and had 127 underruns at startup on hardware, which is why
    | it ran every block here until 5 Oct 2026; the first-poll anchor
    | (usbaudio_kick) now re-sets the cursor AUD_TARGET behind the producer
    | at the host's first poll, 460 frames after alt 1 on macOS, so the ring
    | needs nothing from before the request. What it does need: the
    | AUD_TARGET slots bring-up starts the cursor in must not hold the
    | previous session's tail, so they are zeroed once at the first produced
    | block (audio_cushion_zero), and the stream starts with silence until
    | the anchor (or, for a host that polls within AUD_TARGET frames, up to
    | that many zero frames). Measured on Bryan T's MKII (4 Oct 2026): the
    | always-on producer cost 13-25 us of frame interrupt per frame with no
    | host attached (OUT TRACKS MAIN CUE against OUT MAIN CUE). Not on a
    | unit since.
    tstb    usbaudio_alt
    bnes    .Lproduce
    tstb    aud_force               | the harness's switch (usb_align): produce
    bnes    .Lproduce               | with no host and EP3 left alone
    moveq   #1,%d0
    moveb   %d0,aud_closed
    movel   RB_PREV,%d0             | keep the bank record current: bankdup
    movel   %d0,usbaudio_lastbank   | counts producing blocks only
    | The gain history and the ramp state follow core 0 every block, stream
    | or not (TRACKS POST), so the first block a host gets is already paired
    | and ramped as the mix was (post_frame).
    mvzb    usb_trk,%d0
    cmpib   #TRK_POST,%d0
    bnes    .Lep3
    moveq   #0,%d0                  | state only, no per-sample table
    bsr     post_frame
    bsr     post_emac_leave
    bra     .Lep3
.Lproduce:
    tstb    aud_closed
    beqs    .Lproduce_go
    clrb    aud_closed
    bsr     audio_cushion_zero
.Lproduce_go:
    bsr     producer_usb            | the composable producer (the six bytes
                                    | decide what each frame holds)
    | ---- EP3, owned by this context alone ---------------------------------
    | usbaudio_alt is what the host asked for (SET_INTERFACE); aud_running is
    | what EP3 currently is. Bring it up or down when they differ, and when
    | it is up the block clock IS the send clock: top the queue up now.
.Lep3:
    mvzb    usbaudio_alt,%d0
    mvzb    aud_running,%d1
    cmpl    %d0,%d1
    beqs    .Lep3_same
    tstl    %d0
    beqs    .Lep3_down
    bsr     audio_ep3_up
    bras    .Lep3_kick
.Lep3_down:
    bsr     audio_ep3_down
    bras    9f
.Lep3_same:
    tstl    %d1
    beqs    9f                      | nobody listening: nothing to send
.Lep3_kick:
    bsr     usbaudio_kick
9:  clrl    0x46104d4e              | displaced
    jmp     0x4000d9a6

| The AUD_TARGET ring frames behind the producer, zeroed: the stream's first
| packets are built from them before the anchor. Both rings, the high-speed
| one through the uncached alias at the stream's frame bytes. May clobber
| d0-d7/a0-a6.
audio_cushion_zero:
    movel   aud_produced,%d0
    cmpil   #AUD_TARGET,%d0
    bccs    0f
    addil   #AUD_FRAMES,%d0         | fewer frames ever produced than the cushion
    movel   %d0,aud_produced        | (boot): count one lap ahead, same slots, so
0:  subil   #AUD_TARGET,%d0         | bring-up's cursor is not clamped at 0
    movel   usb_frame_bytes,%d5
    lsrl    #2,%d5                  | longs a frame (0: no high-speed frame)
    moveq   #AUD_TARGET-1,%d1
1:  movel   %d0,%d2
    andil   #AUD_FRAMES-1,%d2
    movel   %d5,%d4
    beqs    3f
    movel   %d2,%d3
    mulu.l  %d5,%d3
    lsll    #2,%d3                  | index * frame bytes
    moveal  #(aud_ring+UNCACHED),%a0
    addal   %d3,%a0
2:  clrl    %a0@+
    subql   #1,%d4
    bnes    2b
3:  lsll    #3,%d2
    lea     aud_sum,%a0
    addal   %d2,%a0
    clrl    %a0@+
    clrl    %a0@
    addql   #1,%d0
    subql   #1,%d1
    bpls    1b
    rts

| ---- the producer: the checked fields of each frame's 88-byte slot ---------
| One producer, every combination: per block it writes 16 frames at the
| cursor aud_produced names. Per frame, in slot order: the 16 track channels
| (PRE: the read-back words with their low byte cleared, byte-reversed;
| POST: the stems, post_frame's gains; the stem/word sums d5/d3 feed the
| full-speed sum), then the checked MAIN / CUE / MASTER pairs. The
| full-speed stereo sum takes the first checked source by the priority
| tracks > MAIN > CUE > MASTER, and is only SENT at full speed; at high
| speed (PORTSC1 bits 27:26 = 2) its store is skipped. Decided per block
| from the PORT, not from aud_hs, so a re-enumeration at full speed refills
| the sum ring long before the host can select alt 1 (enumeration alone
| takes >100 ms; the ring holds 23 ms).
|
| Lags: with TRACKS in the stream, MAIN of a pull is the mix of the tracks
| one block earlier than the track words read beside them, so its pair goes
| MAIN_CUE_LAG_BLOCKS blocks behind the tracks' slot (see the constant); the
| consumer is more than one block behind the producer, so that slot is
| unread when it is written. CUE goes into MAIN's slot, or
| CUE_MASTER_LAG_BLOCKS blocks ahead of it with MASTER TRACK on. MASTER
| (track 8's L/R) is never lagged: the slot's own MASTER field.
|
| The bank record (usbaudio_lastbank, usbaudio_bankdup) counts producing
| blocks that read the arena: TRACKS or MASTER checked. May clobber every
| register.
producer_usb:
    | TRACKS POST: post_frame leaves this block's per-sample gains in
    | post_gtab ([frame][track], g << 10) and the EMAC in fractional mode
    | with the interrupted context's state saved. It clobbers everything, so
    | it runs first, before any producer state exists.
    mvzb    usb_trk,%d0
    cmpib   #TRK_POST,%d0
    bnes    1f
    moveq   #1,%d0
    bsr     post_frame
1:  moveq   #0,%d1
    movel   PORTSC1,%d0
    andil   #0x0c000000,%d0
    cmpil   #0x08000000,%d0
    seq     %d1                     | d1 = 0xff at high speed
    moveal  %d1,%a1                 | a1 != 0: skip the sum this block
    | bankdup counts blocks where the ping-pong bank did not alternate (the
    | producer would then read one bank twice or skip one).
    tstb    usb_trk
    bne     2f
    tstb    usb_master
    beqs    .Lpb_nobank
2:  movel   RB_PREV,%d0
    movel   %d0,%d2
    cmpl    usbaudio_lastbank,%d2
    bnes    3f
    addql   #1,usbaudio_bankdup
3:  movel   %d2,usbaudio_lastbank
    lsll    #8,%d0
    lsll    #2,%d0                  | prev * 1024 (imm shift is 1-8)
    addil   #RB_BASE,%d0
    moveal  %d0,%a2                 | a2 = this bank's track 0, frame 0
    bras    4f
.Lpb_nobank:
    subal   %a2,%a2                 | no arena reads this block
4:  | ---- this block's write pointers, all through the uncached alias ------
    | The ring frame is the stream's frame (usb_frame_bytes): the checked
    | fields in wire order, TRACKS' 64 B first, then MAIN, CUE, MASTER, 8 B
    | each. a3 walks the block's frames; MAIN, CUE and MASTER each have their
    | own pointer (prod_pm, prod_pc, prod_px: the lags below), advanced a
    | frame at a time. A block never wraps (16 divides the ring size).
    movel   usb_frame_bytes,%d7     | d7 = frame bytes
    movel   aud_produced,%d4
    movel   %d4,%d5
    andil   #AUD_FRAMES-1,%d5
    movel   %d5,%d0
    mulu.l  %d7,%d0
    moveal  #(aud_ring+UNCACHED),%a3
    addal   %d0,%a3                 | a3 = this frame's slot
    lsll    #3,%d5
    lea     aud_sum,%a4
    addal   %d5,%a4                 | a4 = stereo-sum cursor
    moveq   #0,%d3                  | d3 = the next field's offset in the frame
    moveq   #0,%d2                  | d2 = MAIN/CUE's lag behind this frame, in frames
    tstb    usb_trk
    beqs    1f
    moveq   #64,%d3
    moveq   #16*MAIN_CUE_LAG_BLOCKS,%d2
1:  movel   %d7,%d0
    subl    %d3,%d0
    movel   %d0,prod_skip           | past the tracks' words: to the next frame
    tstb    usb_main
    beqs    2f
    movel   %d4,%d0
    subl    %d2,%d0
    andil   #AUD_FRAMES-1,%d0
    mulu.l  %d7,%d0
    addl    %d3,%d0
    addil   #(aud_ring+UNCACHED),%d0
    movel   %d0,prod_pm             | MAIN: MAIN_CUE_LAG_BLOCKS behind with TRACKS
    addql   #8,%d3
2:  tstb    usb_cue
    beqs    3f
    movel   %d4,%d0
    subl    %d2,%d0
    tstb    MASTER_TRACK_ON
    beqs    5f
    addil   #16*CUE_MASTER_LAG_BLOCKS,%d0
5:  andil   #AUD_FRAMES-1,%d0
    mulu.l  %d7,%d0
    addl    %d3,%d0
    addil   #(aud_ring+UNCACHED),%d0
    movel   %d0,prod_pc             | CUE: MAIN's frame, or CUE_MASTER_LAG_BLOCKS ahead of it
    addql   #8,%d3
3:  movel   %a3,%d0
    addl    %d3,%d0
    movel   %d0,prod_px             | MASTER: the current frame, never lagged
    lea     MAIN_CUE_BASE,%a0
    movel   %a0,prod_src            | this block's MAIN/CUE pairs, 8 B a frame
    movel   %d7,%d0
    lsll    #4,%d0
    addl    %a3,%d0
    movel   %d0,prod_end            | 16 frames on
    moveq   #SUM_SHIFT,%d1          | asr.l immediate is 1-8 only: shift via d1
    movel   %d7,%d4                 | d4 = frame bytes for the frame loop
    mvzb    usb_trk,%d0
    tstb    %d0
    beq.w   7f                      | OFF: no bounds/gain pointers
    cmpib   #TRK_POST,%d0
    beqs    6f
    moveal  #0x7fffff,%a5           | PRE: SAT24 bounds
    moveal  #-0x800000,%a6
    bras    7f
6:  lea     post_gtab,%a5           | POST: the gain cursor (the sum uses
                                    | the immediate form)
7:  | d6 = this block's checked boxes, read once: the loop tests the
    | register, not the setting bytes. In some project conditions the whole
    | OUT path ran 3-5x slower than in others (Bryan T's MKII, 27 Oct 2026, a
    | frame profiler: the old copy 33 us a frame against 6); the cause is not
    | established, so the loop keeps its own accesses to SDRAM to the ring
    | stores. With this producer the slow conditions fell by about two thirds.
    moveq   #0,%d6
    mvzb    usb_trk,%d0
    cmpib   #TRK_PRE,%d0
    bnes    8f
    bset    #PF_PRE,%d6
8:  cmpib   #TRK_POST,%d0
    bnes    8f
    bset    #PF_POST,%d6
8:  tstb    usb_main
    beqs    8f
    bset    #PF_MAIN,%d6
8:  tstb    usb_cue
    beqs    8f
    bset    #PF_CUE,%d6
8:  tstb    usb_master
    beqs    1f
    bset    #PF_MASTER,%d6
1:
    | ---- the 16 track channels --------------------------------------------
    | PRE: track t's L,R (32-bit, post-FX, pre-fader) with the low byte
    | cleared -- 24 bits, left-justified in the subslot, no saturation needed
    | -- then BYTEREV (ISA_C) to little-endian, one longword store each, at
    | slot + t*8. The same words >> 8 accumulate into the stereo sum in
    | 24-bit units (d5 = L, d3 = R; eight tracks fit in 27 bits).
    btst    #PF_POST,%d6
    bne.w   .Lf_post
    btst    #PF_PRE,%d6
    beq.w   .Lf_notrk
    moveal  %a2,%a0                 | track 0, this frame
    moveq   #0,%d5                  | L sum
    moveq   #0,%d3                  | R sum
    moveq   #RB_TRACKS-1,%d7
2:  movel   %a0@,%d2                | track L
    movel   %d2,%d0
    asrl    %d1,%d0
    addl    %d0,%d5
    clrb    %d2                     | the top 24 bits
    byterev %d2
    movel   %d2,%a3@+
    movel   %a0@(4),%d2             | track R
    movel   %d2,%d0
    asrl    %d1,%d0
    addl    %d0,%d3
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
    lea     %a0@(128),%a0           | next track, same frame
    subql   #1,%d7
    bpl     2b
    | ---- the stereo sum: saturate, left-justify, store little-endian --------
    movel   %a1,%d0
    bne     .Lf_sum_skip            | high speed: the sum ring is not sent
    movel   %d5,%d2
    SAT24   %d2
    | srcjump counts steps in the summed L sample larger than 800 << 8 (his
    | threshold, 800 in 16-bit units) at production, before USB.
    movel   usbaudio_lastsamp,%d0
    subl    %d2,%d0
    bpls    .Lf_sj_abs
    negl    %d0
.Lf_sj_abs:
    cmpil   #(800<<8),%d0
    bcss    .Lf_sj_done
    addql   #1,usbaudio_srcjump
.Lf_sj_done:
    movel   %d2,usbaudio_lastsamp
    movel   %d2,%d0
    lsll    #8,%d0
    byterev %d0
    movel   %d0,%a4@+               | sum L
    movel   %d3,%d0
    SAT24   %d0
    lsll    #8,%d0
    byterev %d0
    movel   %d0,%a4@+               | sum R
.Lf_sum_skip:
    bra     .Lf_fields
    | ---- POST: the stems, each track's block times its own MAIN gain --------
    | post_frame's per-sample gains, read in step with the words. The stereo
    | sum (full speed) is the sum of the stems; lastsample is kept but no
    | srcjump is counted (the stems are already the smoothed mix).
.Lf_post:
    moveal  %a2,%a0                 | track 0, this frame
    moveq   #0,%d5                  | L sum
    moveq   #0,%d3                  | R sum
    moveq   #RB_TRACKS-1,%d7
    movel   %a1,%d0
    bne     .Lf_post_hs
2:  POST_WORD %a5@, 0
    movel   %d2,%d0
    asrl    #8,%d0
    addl    %d0,%d5
    POST_STORE
    POST_WORD %a5@+, 4
    movel   %d2,%d0
    asrl    #8,%d0
    addl    %d0,%d3
    POST_STORE
    lea     %a0@(128),%a0           | next track, same frame
    subql   #1,%d7
    bpl     2b
    movel   %d5,%d2
    SAT24I  %d2
    movel   %d2,usbaudio_lastsamp
    lsll    #8,%d2
    byterev %d2
    movel   %d2,%a4@+               | sum L
    movel   %d3,%d2
    SAT24I  %d2
    lsll    #8,%d2
    byterev %d2
    movel   %d2,%a4@+               | sum R
    bra     .Lf_fields
.Lf_post_hs:
2:  POST_WORD %a5@, 0
    POST_STORE
    POST_WORD %a5@+, 4
    POST_STORE
    lea     %a0@(128),%a0
    subql   #1,%d7
    bpl     2b
.Lf_notrk:
.Lf_fields:
    | ---- MAIN and CUE, the DAC feed, and MASTER, track 8's pair ------------
    | Frame f's MAIN/CUE pairs sit at prod_src = MAIN_CUE_BASE + f*8
    | (+MAIN_CUE_CUE_OFF for CUE). MAIN goes to prod_pm: the frame
    | MAIN_CUE_LAG_BLOCKS blocks behind this one with TRACKS in the stream
    | (see the constant), this one without; CUE to prod_pc, MAIN's frame or
    | CUE_MASTER_LAG_BLOCKS blocks ahead of it with MASTER TRACK on. MASTER
    | reads the arena (a2's bank) and goes to prod_px, this frame, never
    | lagged. Until 27 Oct 2026 MASTER was stored at a3 + 80 with a3 already
    | past the tracks' 64 B, so with TRACKS and MASTER both checked its pair
    | landed in the next slot's track 8 field and the stream's MASTER
    | channels carried whatever the slot held (read from the source, not
    | measured on a unit).
    | MAIN (checked): d2/d3 = the pair, byte-reversed
    btst    #PF_MAIN,%d6
    beqs    .Lf_nomain
    moveal  prod_src,%a0
    movel   %a0@(MAIN_CUE_MAIN_OFF),%d2
    clrb    %d2
    byterev %d2
    movel   %a0@(MAIN_CUE_MAIN_OFF+4),%d3
    clrb    %d3
    byterev %d3
    moveal  prod_pm,%a0
    movel   %d2,%a0@                | MAIN L
    movel   %d3,%a0@(4)             | MAIN R
    addl    %d4,prod_pm
    | MAIN is the sum's priority when it stands alone with no tracks
    movel   %a1,%d0
    bne     .Lf_nomain
    tstb    usb_trk
    bne     .Lf_nomain
    movel   %d2,%a4@+               | MAIN L, full speed
    movel   %d3,%a4@+               | MAIN R, full speed
.Lf_nomain:
    | CUE (checked)
    btst    #PF_CUE,%d6
    beqs    .Lf_nocue
    moveal  prod_src,%a0
    movel   %a0@(MAIN_CUE_CUE_OFF),%d2
    clrb    %d2
    byterev %d2
    movel   %a0@(MAIN_CUE_CUE_OFF+4),%d3
    clrb    %d3
    byterev %d3
    moveal  prod_pc,%a0
    movel   %d2,%a0@                | CUE L
    movel   %d3,%a0@(4)             | CUE R
    addl    %d4,prod_pc
    | CUE is the sum's priority when it stands alone with no tracks or MAIN
    movel   %a1,%d0
    bne     .Lf_nocue
    tstb    usb_trk
    bne     .Lf_nocue
    tstb    usb_main
    bne     .Lf_nocue
    movel   %d2,%a4@+               | CUE L, full speed
    movel   %d3,%a4@+               | CUE R, full speed
.Lf_nocue:
    | MASTER (checked): the arena's track 8, the current frame's field
    btst    #PF_MASTER,%d6
    beqs    .Lf_nomaster
    movel   %a2@((RB_TRACKS-1)*128),%d2
    clrb    %d2
    byterev %d2
    movel   %a2@((RB_TRACKS-1)*128+4),%d3
    clrb    %d3
    byterev %d3
    moveal  prod_px,%a0
    movel   %d2,%a0@                | T8 L
    movel   %d3,%a0@(4)             | T8 R
    addl    %d4,prod_px
    | MASTER is the sum's priority when every other box is off
    movel   %a1,%d0
    bne     .Lf_nomaster
    tstb    usb_trk
    bne     .Lf_nomaster
    tstb    usb_main
    bne     .Lf_nomaster
    tstb    usb_cue
    bne     .Lf_nomaster
    movel   %d2,%a4@+               | T8 L, full speed
    movel   %d3,%a4@+               | T8 R, full speed
.Lf_nomaster:
    movel   prod_skip,%d0
    addal   %d0,%a3                 | the next frame (the tracks' words advanced a3 already)
    lea     %a2@(8),%a2             | next frame
    addql   #8,prod_src
    cmpal   prod_end,%a3
    bcs     1b                      | 16 frames (not bcss: the loop body is long)
    | TRACKS POST: the interrupted context's EMAC back
    mvzb    usb_trk,%d0
    cmpib   #TRK_POST,%d0
    bnes    2f
    bsr     post_emac_leave
2:  movel   aud_produced,%d4
    addil   #16,%d4                 | 16 frames produced
    movel   %d4,aud_produced
    rts

| ---- the runtime settings: cfgsel and the four config responders ----------
| The four GET_DESCRIPTOR(CONFIG / OTHER_SPEED) responders (installed at
| 0x4001d880/88/be/c6) push the pointer cfgsel chose and jump to the stock
| send tail at 0x4001d88e. cfgsel reads the CS1 early block (brain.c
| write_early_block, BRAIN.md 6.4) at usb_cs1_base: magic, version, the
| 16-bit sum over every entry's value bytes (the entries come from
| cs1_early_ents in remix.inc), then the six bytes at their CS1 addresses.
| An invalid block (no card, or not written yet) keeps the image's resolved
| values and leaves usb_cfg_ready 0, so the responders re-read after the
| brain writes the block at load; with no brain (usb_cs1_base = 0) the
| resolved values stand and nothing re-reads. Values are clamped, and the
| one illegal pair (IN with every output off, refused at build time and in
| SETTINGS) cannot survive a hand-edited card. Besides the bytes, cfgsel
| latches the combination's geometry (usb_nch, usb_frame_bytes, the
| high-speed cap and step) and the audio interface numbers the shims compare
| against (with MIDI: AC 3 / AS 4 / IN 5; without: 1 / 2 / 3; no audio
| function: all 0). Clobbers d0-d7/a0-a2.
    .global cfgsel
| One setting from the CS1 block: its entry offset, or -1 when the value is
| fixed in the image (pinned: no entry in the block), then the built-in value.
.macro CFG_READ off, def
    .if \off == -1
    moveq   #\def,%d0
    .else
    movel   #\off,%d0
    bsr     .Lcfg_byte
    .endif
.endm

cfgsel:
    clrb    usb_cfg_ready
    moveq   #0,%d5                  | 0: no valid block read this pass
    moveal  usb_cs1_base,%a0
    tstl    %a0
    beq.w   .Lcfg_baked             | no brain: the resolved values stand
    moveb   %a0@,%d1
    cmpib   #EARLY_MAGIC,%d1
    bne.w   .Lcfg_baked
    moveb   %a0@(1),%d1
    cmpib   #1,%d1
    bne.w   .Lcfg_baked
    lea     cs1_early_ents,%a1
    moveq   #0,%d3                  | the sum over the value bytes
.Lcfg_ent:
    movel   %a1@+,%d0
    beqs    .Lcfg_sum
    movel   %a1@+,%d1               | the entry's size: 1 or 2
    tstl    %d0
    beqs    .Lcfg_ent               | offset 0: no entry, nothing to sum
    movel   %a0,%a2
    addal   %d0,%a2
    mvzb    %a2@,%d2
    addl    %d2,%d3
    cmpil   #2,%d1
    bnes    .Lcfg_ent
    lsll    #8,%d2
    addl    %d2,%d3
    bra     .Lcfg_ent
.Lcfg_sum:
    mvzw    %a0@(2),%d0             | the block's stored sum
    andil   #0xffff,%d3
    cmpl    %d0,%d3
    bne.w   .Lcfg_baked             | mismatch: re-read after the next load
    | the six settings, each at its own CS1 address, clamped and stored as
    | it is read (d1..d4 kept for the IN guard)
    CFG_READ CS1_USB_TRK, usb_trk_def
    cmpil   #TRK_POST,%d0
    bles    1f
    moveq   #TRK_POST,%d0
1:  moveb   %d0,usb_trk
    movel   %d0,%d1
    CFG_READ CS1_USB_MAIN, usb_main_def
    tstl    %d0
    beqs    1f
    moveq   #1,%d0
1:  moveb   %d0,usb_main
    movel   %d0,%d2
    CFG_READ CS1_USB_CUE, usb_cue_def
    tstl    %d0
    beqs    1f
    moveq   #1,%d0
1:  moveb   %d0,usb_cue
    movel   %d0,%d3
    CFG_READ CS1_USB_MASTER, usb_master_def
    tstl    %d0
    beqs    1f
    moveq   #1,%d0
    tstl    %d1                     | TRACKS on: MASTER is refused (track 8's
    beqs    1f                      | L/R is already in the stream; brain.c
    moveq   #0,%d0                  | usb_master_ok)
1:  moveb   %d0,usb_master
    movel   %d0,%d4
    CFG_READ CS1_USB_IN, usb_in_def
    cmpil   #3,%d0
    bles    1f
    moveq   #3,%d0
1:  | the pair guard: IN without an output stream is refused everywhere --
    | the same rule on the bytes as SETTINGS (brain.c usb_pair_ok)
    tstl    %d0
    beqs    2f
    tstl    %d1
    bnes    2f
    tstl    %d2
    bnes    2f
    tstl    %d3
    bnes    2f
    tstl    %d4
    bnes    2f
    moveq   #0,%d0                  | forced OFF
2:  moveb   %d0,usb_inputs
    CFG_READ CS1_USB_MIDI, usb_midi_def
    tstl    %d0
    beqs    1f
    moveq   #1,%d0
1:  moveb   %d0,usb_midi
    moveq   #1,%d5                  | a valid block was read
.Lcfg_baked:
    tstl    %d5
    bnes    .Lcfg_have
    moveq   #usb_trk_def,%d1
    moveq   #usb_main_def,%d2
    moveq   #usb_cue_def,%d3
    moveq   #usb_master_def,%d4
    moveq   #usb_in_def,%d0
    moveb   %d0,usb_inputs
    moveq   #usb_midi_def,%d0
    moveb   %d0,usb_midi
    moveb   %d1,usb_trk
    moveb   %d2,usb_main
    moveb   %d3,usb_cue
    moveb   %d4,usb_master
.Lcfg_have:
    | set index = trk | main<<2 | cue<<3 | master<<4 | in<<5 | midi<<7
    mvzb    usb_trk,%d0
    mvzb    usb_main,%d1
    lsll    #2,%d1
    orl     %d1,%d0
    mvzb    usb_cue,%d1
    lsll    #3,%d1
    orl     %d1,%d0
    mvzb    usb_master,%d1
    lsll    #4,%d1
    orl     %d1,%d0
    mvzb    usb_inputs,%d1
    lsll    #5,%d1
    orl     %d1,%d0
    mvzb    usb_midi,%d1
    lsll    #7,%d1
    orl     %d1,%d0
    | the row: four longs, the fs/hs/os_fs/os_hs table pointers
    lsll    #4,%d0                  | row = set * 16
    lea     set_ptrs,%a0
    addal   %d0,%a0                 | a0 = the row
    movel   %a0@,%d1
    movel   %d1,usb_cfg_sel_fs
    movel   %a0@(4),%d1
    movel   %d1,usb_cfg_sel_hs
    movel   %a0@(8),%d1
    movel   %d1,usb_cfg_sel_os_fs
    movel   %a0@(12),%d1
    movel   %d1,usb_cfg_sel_os_hs
    | nch = 16 x [TRACKS on] + 2 x (MAIN + CUE + MASTER)
    mvzb    usb_trk,%d0
    tstb    %d0
    beqs    1f
    moveq   #16,%d0
    bras    2f
1:  moveq   #0,%d0
2:  mvzb    usb_main,%d1
    addl    %d1,%d0
    addl    %d1,%d0
    mvzb    usb_cue,%d1
    addl    %d1,%d0
    addl    %d1,%d0
    mvzb    usb_master,%d1
    addl    %d1,%d0
    addl    %d1,%d0                 | nch = 16 x TRACKS + 2 x (MAIN + CUE + MASTER)
    moveb   %d0,usb_nch
    | the frame bytes (nch x 4) and the high-speed cap and step: every
    | combination (at most 20 channels) polls at 250 us, 11.025 frames,
    | at most 12 x fb
    lsll    #2,%d0                  | fb
    movel   %d0,usb_frame_bytes
    movel   %d0,%d1
    lsll    #2,%d1                  | fb x 4
    movel   %d0,%d2
    lsll    #3,%d2                  | fb x 8
    addl    %d2,%d1                 | fb x 12
    movel   %d1,usb_hs_cap
    movel   #STEP_HS,%d1
    movel   %d1,usb_hs_step
    | the interface numbers: 0 with no audio function (no alt 1 is ever
    | offered, so the shims' compares cannot match a real interface)
    clrb    usb_ac_iface
    clrb    usb_as_iface
    clrb    usb_in_iface
    tstb    usb_nch
    beqs    5f
    mvzb    usb_midi,%d0
    tstb    %d0
    beqs    6f
    moveq   #3,%d0                  | with MIDI: AC 3, AS 4, IN 5
    bras    7f
6:  moveq   #1,%d0                  | without: AC 1, AS 2, IN 3
7:  moveb   %d0,usb_ac_iface
    addql   #1,%d0
    moveb   %d0,usb_as_iface
    tstb    usb_inputs
    beqs    5f
    addql   #1,%d0
    moveb   %d0,usb_in_iface
5:
    | ready: a valid block, or no brain (nothing later can change the
    | resolved values)
    tstl    %d5
    bnes    8f
    moveal  usb_cs1_base,%a0
    tstl    %a0
    bnes    9f                      | brain but an invalid block: re-read
8:  moveq   #1,%d0
    moveb   %d0,usb_cfg_ready
9:  rts

| %d0 = entry offset -> %d0 = its value (these settings are 1 byte).
| Clobbers d0/a0.
.Lcfg_byte:
    moveal  usb_cs1_base,%a0
    addal   %d0,%a0
    moveq   #0,%d0
    moveb   %a0@,%d0
    rts

| Each responder site is a jsr here (manifest.py SELECTOR_DETOURS, kind =
| "jsr"): the stock pea of the baked table and the bra to the shared tail at
| 0x4001d88e (movel d1,sp@- / jsr a0@, a0 = usb_ep0_send) are gone. The stub
| writes the pointer cfgsel chose over its own return-address slot and
| jumps to the tail: usb_ep0_send's rts returns to 0x4001d894, the site's
| own continuation, with the stock stack (table + d1 for the addq there).
| When usb_cfg_ready is 0 (brain, block not valid yet), cfgsel is re-run
| first; the registers the stock path keeps live are saved across it.
| The moveml pair is the module's lea-framed idiom (see usbmidi.s):
| `%sp@` is mode 2 (store at sp, sp unchanged), so the lea reserves the
| frame below sp -- without it the save writes over the caller's live
| frame ([sp+12] is the handler's return address, clobbered by d3's slot).
    .global stub_fs_config
stub_fs_config:
    tstb    usb_cfg_ready
    bnes    2f
    lea     %sp@(-44),%sp
    moveml  %d0-%d7/%a0-%a2,%sp@
    jsr     cfgsel
    moveml  %sp@,%d0-%d7/%a0-%a2
    lea     %sp@(44),%sp
2:  movel   usb_cfg_sel_fs,%sp@
    jmp     0x4001d88e
    .global stub_hs_config
stub_hs_config:
    tstb    usb_cfg_ready
    bnes    2f
    lea     %sp@(-44),%sp
    moveml  %d0-%d7/%a0-%a2,%sp@
    jsr     cfgsel
    moveml  %sp@,%d0-%d7/%a0-%a2
    lea     %sp@(44),%sp
2:  movel   usb_cfg_sel_hs,%sp@
    jmp     0x4001d88e
    .global stub_os_hs
stub_os_hs:
    tstb    usb_cfg_ready
    bnes    2f
    lea     %sp@(-44),%sp
    moveml  %d0-%d7/%a0-%a2,%sp@
    jsr     cfgsel
    moveml  %sp@,%d0-%d7/%a0-%a2
    lea     %sp@(44),%sp
2:  movel   usb_cfg_sel_os_hs,%sp@
    jmp     0x4001d88e
    .global stub_os_fs
stub_os_fs:
    tstb    usb_cfg_ready
    bnes    2f
    lea     %sp@(-44),%sp
    moveml  %d0-%d7/%a0-%a2,%sp@
    jsr     cfgsel
    moveml  %sp@,%d0-%d7/%a0-%a2
    lea     %sp@(44),%sp
2:  movel   usb_cfg_sel_os_fs,%sp@
    jmp     0x4001d88e

| ==== TRACKS POST: each track's MAIN gain, as core 0 computes it ============
| Measured under the port, 5 Oct 2026 (modules/usb-audio-out-tracks-post/
| README.md, "How it works"):
|
| - The gains. The ColdFire builds a four-entry snapshot ring at 0x80005460
|   (0x80 bytes an entry) in frame_isr (0x40004db8, from 0x4000d0de); per
|   track, eight bytes: cue, MAIN, XLV, split. MAIN is LEVEL << 8 after the
|   ColdFire's 1/16-per-frame smoothing (0x80000c60), set to 0 by mute and
|   by another track's solo; XLV is the crossfader's scene level (0x80000c80,
|   0x7f00 unlocked); split is a sample offset in the block (& 15).
| - The pairing. Core 0 mixes the read-back block this producer reads (the
|   previous bank, pulled one frame ago) with the snapshot BUILT FOUR FRAMES
|   AGO: the transfer machine sends entry (write index + 1) & 3, built three
|   frames before the frame whose block it travels with. By the time this
|   hook runs, frame_isr has rebuilt that entry, so the words are kept here:
|   post_hist, four slots, the slot for this frame read before it is
|   overwritten with this frame's snapshot (0x80003c10).
| - The arithmetic, payload A P:0xfa-0x165 and P:0x203-0x237, with
|   MAIN_LEVEL fixed at 64 (the factor (M/64)^2 core 0 applies is left
|   out, and at 64 it is exactly 1 once the mixdown's asl #2 is counted):
|     sq = floor((w << 8)^2 * 2 / 2^24) = floor(w^2 / 2^7), limited to 2^23-1
|     T  = X:0x6c00[w_xlv >> 7], the 1,024-point sine (post_xlv, extracted
|          from the user's own payload A at build time)
|     G  = floor(sq * floor(T / 4) / 2^23)
|   then per sample the ramp: the last block's increment continues for
|   min(split, last split) samples, holds for the rest of the split, and a
|   new increment floor((G - cur) / 16) runs the remaining 16 - split.
| The state advances every block (the closed-stream path of
| audio_frame_shim calls it, without the table), so it is core 0's whether
| or not a host listens.
.set SNAP_PTR,  0x80003c10            | this frame's snapshot (frame_isr 0x4000ac26)

| d0 = 0: advance the state only; 1: also write this block's sixteen gains
| per track into post_gtab ([frame][track], g << 10). Leaves the EMAC in
| fractional mode with the interrupted context's state in post_emac: the
| caller ends with post_emac_leave. Clobbers d0-d7/a0-a6.
post_frame:
    moveal  %d0,%a6
    | The interrupted context's EMAC, saved as frame_isr saves it
    | (0x4000ac96): MACSR, then integer mode, the extension word, the
    | accumulator. frame_isr restored it at 0x4000d968, before this hook.
    movel   %macsr,%d1
    movel   %d1,post_emac
    moveq   #0,%d1
    movel   %d1,%macsr
    movel   %accext01,%d1
    movel   %d1,post_emac+8
    movclrl %acc0,%d1
    movel   %d1,post_emac+4
    moveq   #0x20,%d1               | fractional, truncating, no saturation
    movel   %d1,%macsr
    movel   post_hidx,%d0
    movel   %d0,%d1
    addql   #1,%d1
    moveq   #3,%d2
    andl    %d2,%d1
    movel   %d1,post_hidx
    lsll    #6,%d0                  | slot * 64: 8 tracks x 8 bytes
    lea     post_hist,%a0
    addal   %d0,%a0                 | a0 = the snapshot of four frames ago
    moveal  SNAP_PTR,%a1            | a1 = this frame's
    lea     post_state,%a2          | per track: cur, increment, last split
    lea     post_gtab,%a3           | column of track 0
    lea     post_xlv,%a4
    moveq   #RB_TRACKS-1,%d7
4:  mvsw    %a0@,%d2                | MAIN word (signed, as core 0 reads w << 8)
    mvzw    %a0@(2),%d3             | XLV word
    mvzw    %a0@(4),%d4             | split word
    movew   %a1@(2),%a0@            | this frame's, kept four frames
    movew   %a1@(4),%a0@(2)
    movew   %a1@(6),%a0@(4)
    mulsl   %d2,%d2
    asrl    #7,%d2                  | sq
    cmpil   #0x7fffff,%d2
    bles    5f
    movel   #0x7fffff,%d2           | w = -0x8000 squares to 2^23: the store limits it
5:  lsrl    #7,%d3                  | the curve index (a word above 0x7fff, which
    andil   #0xff,%d3               | nothing writes, is wrapped, not core 0's)
    movel   %a4@(0,%d3:l:4),%d3     | T
    asrl    #2,%d3                  | floor(T / 4): mpy by (64/128)^2
    lsll    #8,%d2
    lsll    #8,%d3
    macl    %d2,%d3,%acc0           | floor(sq * T/4 / 2^15)
    movclrl %acc0,%d2
    asrl    #8,%d2                  | d2 = G
    moveq   #15,%d0
    andl    %d0,%d4                 | d4 = s, the split
    movel   %a2@,%d5                | d5 = cur
    movel   %a2@(4),%d6             | d6 = the running increment
    movel   %a2@(8),%d0             | the last block's split
    cmpl    %d4,%d0
    bles    6f
    movel   %d4,%d0                 | d0 = m = min(s, last split)
6:  movel   %d4,%a2@(8)
    movel   %a6,%d1
    tstl    %d1
    bnes    .Lpf_table
    | state only: the three segments in closed form
    movel   %d6,%d3
    mulsl   %d0,%d3
    addl    %d3,%d5                 | cur += m * increment
    movel   %d2,%d3
    subl    %d5,%d3
    asrl    #4,%d3                  | d3 = the new increment
    moveq   #16,%d1
    subl    %d4,%d1
    mulsl   %d3,%d1
    addl    %d1,%d5                 | cur += (16 - s) * increment
    bra     .Lpf_next
.Lpf_table:
    moveq   #16,%d1
    subl    %d4,%d1                 | d1 = 16 - s, the new ramp's samples (>= 1)
    subl    %d0,%d4                 | d4 = s - m, the hold
    moveal  %a3,%a5
    tstl    %d0
    beqs    8f
7:  movel   %d5,%d3                 | the last ramp, continued
    lsll    #8,%d3
    lsll    #2,%d3                  | g << 10
    movel   %d3,%a5@
    lea     %a5@(32),%a5
    addl    %d6,%d5
    subql   #1,%d0
    bnes    7b
8:  tstl    %d4
    beqs    10f
    movel   %d5,%d3
    lsll    #8,%d3
    lsll    #2,%d3                  | g << 10
9:  movel   %d3,%a5@                | held
    lea     %a5@(32),%a5
    subql   #1,%d4
    bnes    9b
10: movel   %d2,%d6
    subl    %d5,%d6
    asrl    #4,%d6                  | the new increment
11: movel   %d5,%d3
    lsll    #8,%d3
    lsll    #2,%d3                  | g << 10
    movel   %d3,%a5@
    lea     %a5@(32),%a5
    addl    %d6,%d5
    subql   #1,%d1
    bnes    11b
    movel   %d6,%d3
.Lpf_next:
    movel   %d5,%a2@
    movel   %d3,%a2@(4)
    lea     %a2@(12),%a2
    addql   #8,%a0
    addql   #8,%a1
    addql   #4,%a3
    subql   #1,%d7
    bpl     4b
    rts

| The interrupted context's EMAC back, as frame_isr restores it (0x4000d968).
post_emac_leave:
    moveq   #0,%d0
    movel   %d0,%macsr
    movel   post_emac+4,%d0
    movel   %d0,%acc0
    movel   post_emac+8,%d0
    movel   %d0,%accext01
    movel   post_emac,%d0
    movel   %d0,%macsr
    rts

| ---- UAC2 class-request shim (installed at 0x4001de64) ----------------------
| Displaced: movel 0xfc0b01c0,%d0 — the first instruction of the stock
| "unknown request: STALL EP0" tail, which every request the dispatcher does
| not recognise falls into. A UAC2 host asks the CLOCK SOURCE for its sample
| rate before it will publish a device (RANGE + CUR of CS_SAM_FREQ_CONTROL,
| CUR of CS_CLOCK_VALID_CONTROL, all class GET to the AudioControl interface
| with the entity id in wIndex's high byte), and a STALL there means no
| audio device. A SET CUR of that rate is taken too (.Lctrl_set). Everything
| else falls through to the stock STALL, which is the legal answer for a
| control we do not implement.
|
| Reply the way the stock string-descriptor path does: push the buffer and
| min(wLength, len) and jump to the shared usb_ep0_send tail. d2 still holds
| wLength here (nothing between the dispatcher and the stall touches it). The
| reply buffers are constants in this unit's data: the EP0 send DMAs them
| straight out of memory.
    .global audio_ctrl_shim
audio_ctrl_shim:
    mvzb    SETUP_BMREQ,%d0
    | A vendor GET (bmRequestType 0xc0, bRequest 0x55) reads the
    | fifteen counters below back over EP0 as 60 big-endian bytes, so a
    | host -- the port's bench, or tools/hw/usb_counters.py on a unit --
    | can watch underruns, overruns and the bank-duplicate count during a
    | stream. Any driver a host attached to the interfaces is bypassed: a
    | device-recipient control request needs no interface claim.
    cmpil   #0xc0,%d0
    bne     .Lctrl_class
    mvzb    SETUP_BREQ,%d0
    cmpil   #0x55,%d0
    bne     .Lctrl_lm
    pea     usbaudio_consumed
    moveq   #60,%d0
    bra     .Lctrl_send
    | 0xc0/0x57 reads LOAD METER's published figures (modules/load-meter), the
    | block wValue low names: 0 lm_stats (5 longs), 1 lm_dsp (12), 2 lm_ot
    | (16 slots of {last, sum, count, max}), 3 DLPUMP's counters (16 longs, modules/dlpump), from byte wIndex low on. Each
    | LM_* is 0 without that module, and a request for a block it does not
    | have STALLs as stock does.
    |
    | Two things measured on a unit (24 Oct 2026) shape it. The controller's
    | DMA does not see the CPU's cached stores (the note at the data), and
    | lm_stats is stored once in 0.5 s, so its line stayed in the cache: the
    | request returned the same window for minutes, then jumped 100 windows.
    | The reply is therefore copied, byte by byte from the CPU's view, into
    | lm_reply through the uncached alias. And a control reply whose length is
    | a multiple of 64 makes the NEXT control request return 0 bytes once
    | (wLength 64, 128, 192 and 256 did; 63, 100, 252, 255 did not), so a
    | reply that would be one is sent a byte short and the host asks again
    | from the new offset.
.Lctrl_lm:
    cmpil   #0x57,%d0
    bne     .Lctrl_stock
    lea     %sp@(-12),%sp
    movem.l %d3/%a2-%a3,%sp@
    mvzb    SETUP_WVALL,%d0
    moveq   #20,%d1
    movel   #LM_STATS,%d3
    tstl    %d0
    beqs    3f
    moveq   #48,%d1
    movel   #LM_DSP,%d3
    cmpil   #1,%d0
    beqs    3f
    movel   #256,%d1
    movel   #LM_OT,%d3
    cmpil   #2,%d0
    beqs    3f
    moveq   #64,%d1                 | block 3: DLPUMP's counters (16 longs)
    movel   #DL_DIAG,%d3
    cmpil   #3,%d0
    bne     9f
3:  tstl    %d3
    beq     9f                      | the remix has no LOAD METER (or, for block 3, no DLPUMP)
    mvzb    SETUP_WIDXL,%d0         | byte offset into the block
    cmpl    %d1,%d0
    bcc     9f                      | at or past its end
    subl    %d0,%d1                 | bytes left
    addl    %d0,%d3                 | source
    cmpl    %d2,%d1                 | min(wLength, bytes left)
    bls     4f
    movel   %d2,%d1
4:  tstl    %d1
    beqs    5f
    movel   %d1,%d0
    andil   #63,%d0
    bnes    5f
    subql   #1,%d1                  | never a multiple of 64
5:  moveal  %d3,%a2
    moveal  #(lm_reply+UNCACHED),%a3
    movel   %d1,%d0
    beqs    7f
6:  moveb   %a2@+,%a3@+
    subql   #1,%d0
    bnes    6b
7:  movem.l %sp@,%d3/%a2-%a3
    lea     %sp@(12),%sp
    pea     lm_reply
    movel   %d1,%d0
    bra     .Lctrl_send
9:  movem.l %sp@,%d3/%a2-%a3
    lea     %sp@(12),%sp
    bra     .Lctrl_stock
.Lctrl_class:
    cmpil   #0x21,%d0               | class SET, interface recipient
    beq     .Lctrl_set
    cmpil   #0xa1,%d0               | class GET, interface recipient
    bne     .Lctrl_stock
    mvzb    SETUP_IFACE,%d0
    mvzb    usb_ac_iface,%d1        | the audio function's AudioControl
    cmpl    %d0,%d1
    bne     .Lctrl_stock
    mvzb    SETUP_WIDXH,%d0
    cmpil   #UAC2_CLOCK_ID,%d0      | the clock source entity
    bne     .Lctrl_stock
    mvzb    SETUP_WVALH,%d0         | control selector
    mvzb    SETUP_BREQ,%d1          | 1 = CUR, 2 = RANGE
    cmpil   #1,%d0                  | CS_SAM_FREQ_CONTROL
    beqs    .Lctrl_freq
    cmpil   #2,%d0                  | CS_CLOCK_VALID_CONTROL
    bne     .Lctrl_stock
    cmpil   #1,%d1
    bne     .Lctrl_stock            | only CUR exists for validity
    pea     uac2_clock_valid
    moveq   #1,%d0
    bras    .Lctrl_send
.Lctrl_freq:
    cmpil   #1,%d1
    bnes    .Lctrl_freq_range
    pea     uac2_freq_cur
    moveq   #4,%d0
    bras    .Lctrl_send
.Lctrl_freq_range:
    cmpil   #2,%d1
    bne     .Lctrl_stock
    pea     uac2_freq_range
    moveq   #14,%d0
.Lctrl_send:
    cmpl    %d2,%d0                 | min(wLength, len)
    blss    1f
    movel   %d2,%d0
1:  movel   %d0,%sp@-
    jmp     EP0_SEND_TAIL
| ---- SET CUR of the clock's sample frequency ---------------------------------
| The clock is fixed and its frequency control is declared read-only, but a
| UAC2 host may still SET it to the rate it has just read back (CUR, 4
| bytes), and some hosts give the audio function up when that STALLs. So a
| SET CUR of CS_SAM_FREQ_CONTROL on this clock is taken: 44100, the one rate
| RANGE offers, is acknowledged and changes nothing; any other rate STALLs
| the status stage. Every other class SET still STALLs at once (stock).
| The stock EP0 stack has no control OUT data stage, so this primes EP0's OUT
| dTD for it exactly as usb_ep0_send primes its status OUT, and waits here
| for the data: returning first races the stock completion loop that runs
| right after this request in the same interrupt, which would take a data
| stage that lands by then for the previous transfer's status OUT. A host
| sends it in the next microframe; 100,000 polls (~10 ms) is the bound, and
| audio_isr_shim finishes it for a host slower than that.
.Lctrl_set:
    mvzb    SETUP_IFACE,%d0
    mvzb    usb_ac_iface,%d1        | the audio function's AudioControl
    cmpl    %d0,%d1
    bne     .Lctrl_stock
    mvzb    SETUP_WIDXH,%d0
    cmpil   #UAC2_CLOCK_ID,%d0      | the clock source entity
    bne     .Lctrl_stock
    mvzb    SETUP_WVALH,%d0
    cmpil   #1,%d0                  | CS_SAM_FREQ_CONTROL
    bne     .Lctrl_stock
    mvzb    SETUP_BREQ,%d0
    cmpil   #1,%d0                  | CUR
    bne     .Lctrl_stock
    moveq   #4,%d0
    cmpl    %d0,%d2                 | wLength
    bne     .Lctrl_stock
    movel   #0x00408080,%d0         | 64 bytes, IOC, ACTIVE (usb_ep0_send's status OUT)
    movel   %d0,EP0OUT_DTD+4
    movel   #EP0_BUF,%d0
    movel   %d0,EP0OUT_DTD+8
    movel   #0xdead0001,%d0         | next: terminate
    movel   %d0,EP0OUT_DTD
    moveal  QH0_OUT_PTR,%a0
    movel   #EP0OUT_DTD,%d0
    movel   %d0,%a0@(8)             | dQH next dTD
    movel   EPPRIME,%d0
    moveq   #1,%d1                  | EP0 OUT
    orl     %d1,%d0
    movel   %d0,EPPRIME
    movel   #100000,%d1
5:  movel   EP0OUT_DTD+4,%d0
    btst    #7,%d0                  | ACTIVE
    beqs    6f
    subql   #1,%d1
    bnes    5b
    moveq   #1,%d0
    moveb   %d0,uac2_set_pending
    jmp     SETIFACE_DONE
6:  bsr     uac2_set_done
    jmp     SETIFACE_DONE
.Lctrl_stock:
    movel   0xfc0b01c0,%d0          | displaced
    jmp     CTRL_STOCK

| The data stage of a clock SET CUR has landed in EP0_BUF: take the OUT
| completion (before the stock loop sees it), then ACK 44100 (status IN) or
| STALL the status stage. Clobbers d0-d1/a0-a1.
uac2_set_done:
    moveq   #1,%d0
    movel   %d0,EPCOMPLETE          | W1C EP0 OUT
    clrb    uac2_set_pending
    movel   EP0_BUF,%d0             | wire order: 44 ac 00 00 = 44100
    cmpil   #0x44ac0000,%d0
    bnes    1f
    jsr     EP0_STATUS_IN
    rts
1:  movel   EP0CTRL,%d0
    bset    #16,%d0                 | STALL EP0 IN: the status stage
    movel   %d0,EP0CTRL
    rts

    .data
| UAC2 clock-source replies, little-endian on the wire (his; constant, the
| EP0 send DMAs them straight out of this unit).
    .balign 4
uac2_freq_cur:   .byte 0x44,0xac,0x00,0x00          | 44100
uac2_freq_range: .byte 0x01,0x00                    | wNumSubRanges = 1
                 .byte 0x44,0xac,0x00,0x00          | dMIN 44100
                 .byte 0x44,0xac,0x00,0x00          | dMAX 44100
                 .byte 0x00,0x00,0x00,0x00          | dRES 0
uac2_clock_valid: .byte 0x01

| ---- state -------------------------------------------------------------------
    .balign 4
    .global usbaudio_consumed, usbaudio_acc, usbaudio_overruns
    .global usbaudio_underruns, usbaudio_lastn, usbaudio_lastfill
    .global usbaudio_lastbank, usbaudio_bankdup, usbaudio_srcjump
    .global usbaudio_reprimes, usbaudio_minfill, usbaudio_maxfill, usbaudio_anchor
| The fifteen longs from usbaudio_consumed to aud_produced are what the
| vendor request 0xc0/0x55 returns, in this order.
usbaudio_consumed: .long 0          | frames pulled from the ring
usbaudio_acc:      .long 0          | frames-per-packet accumulator (x1000)
usbaudio_overruns: .long 0
usbaudio_underruns: .long 0    | packets we could not fill
usbaudio_lastn:    .long 0    | frames in the most recent packet
usbaudio_lastfill: .long 0    | ring fill at the most recent packet
usbaudio_lastbank: .long -1   | previous ping-pong bank
usbaudio_bankdup:  .long 0    | blocks where the bank did NOT alternate
usbaudio_lastsamp: .long 0    | previous summed L sample
usbaudio_srcjump:  .long 0    | discontinuities present at production
usbaudio_reprimes: .long 0    | idle endpoint found holding a queued dTD
usbaudio_minfill:  .long 0    | lowest fill at a packet build since the first poll
usbaudio_maxfill:  .long 0    | highest
usbaudio_anchor:   .long 0    | frames skipped at the host's first poll (this open)
aud_produced:      .long 0          | producer frame count
qh_ep3:            .long 0          | EP3 IN dQH, read from ENDPTLISTADDR
aud_step:          .long STEP_HS    | frames per packet x1000, set by the speed

| ---- the full-speed ring (the high-speed one is with the DMA's, below) ----
    .global aud_ring, aud_sum
aud_sum:           .space AUD_FRAMES*SUM_BYTES   | 1024 x stereo sum (the priority pair)
    .balign 4
lm_reply:          .space 256       | 0xc0/0x57's reply, written only through the uncached alias
usbaudio_alt:      .byte 0          | alt setting the host asked for
uac2_set_pending:  .byte 0          | a clock SET CUR's data stage is primed
aud_running:       .byte 0          | EP3 is up (frame-ISR owned)
aud_await:         .byte 0          | 1 = queue for the first poll, 2 = queued, 0 = anchored
aud_hs:            .byte 0          | 1 = high speed (the combination's channels), 0 = full (sum)
aud_tail:          .byte 0          | next dTD slot to fill (0..NSLOT-1)
aud_closed:        .byte 0          | 1 = blocks have passed with no stream asked for: zero the cushion before producing again
aud_force:         .byte 0          | harness only (tools/harness/usb_align.py pokes it): produce with no host; nothing on a unit sets it

| ---- the runtime settings' state: cfgsel's -----------------------------------
    .global usb_trk, usb_main, usb_cue, usb_master, usb_inputs, usb_midi
    .global usb_cfg_ready, usb_nch, usb_ac_iface, usb_as_iface, usb_in_iface
usb_trk:           .byte 0          | TRACKS: 0 OFF, 1 PRE, 2 POST
usb_main:          .byte 0          | MAIN: 0/1
usb_cue:           .byte 0          | CUE: 0/1
usb_master:        .byte 0          | MASTER: 0/1
usb_inputs:        .byte 0          | IN: 0 OFF, 1 AB, 2 CD, 3 ABCD (usbaudio_in.s reads it)
usb_midi:          .byte 0          | MIDI: 0/1
usb_cfg_ready:     .byte 0          | 1 once the config set matches the block
usb_nch:           .byte 0          | the stream's channels: 16 x TRACKS + 2 each of MAIN/CUE/MASTER
usb_ac_iface:      .byte 0          | the audio function's interface numbers
usb_as_iface:      .byte 0          | (3/4/5 with MIDI, 1/2/3 without, 0 with no audio)
usb_in_iface:      .byte 0
    .balign 4
    .global usb_cfg_sel_fs, usb_cfg_sel_hs, usb_cfg_sel_os_fs, usb_cfg_sel_os_hs
    .global usb_frame_bytes, usb_hs_cap, usb_hs_step
usb_cfg_sel_fs:    .long 0          | the four tables of the set in force
usb_cfg_sel_hs:    .long 0
usb_cfg_sel_os_fs: .long 0
usb_cfg_sel_os_hs: .long 0
| the combination's geometry, latched with the set (cfgsel): the HS frame's
| bytes, the HS packet cap, the HS frames-per-packet step
usb_frame_bytes:   .long 0
usb_hs_cap:        .long 0
usb_hs_step:       .long 0

| ---- TRACKS POST's state: in every image (the producer is runtime-chosen) --
    .balign 4
    .global post_hidx, post_emac, post_hist, post_state, post_gtab, post_xlv
post_hidx:         .long 0          | the history slot for this block (0..3)
post_emac:         .long 0, 0, 0    | the interrupted context's MACSR, ACC0, ACCEXT01
post_hist:         .space 4*8*8     | four blocks x 8 tracks x (MAIN, XLV, split, pad) words
post_state:        .space 8*12      | per track: cur, increment, last split (core 0's X:0x3dd ramp state, MAIN half)
post_gtab:         .space 16*8*4    | this block's gains, [frame][track], g << 10
| The XLV curve: X:0x6c00[0..255] of payload A, the first quarter of its
| 1,024-point sine. Extracted from the user's own image at build time by
| modules/usb/manifest.py into remix.inc; no stock bytes are in the repo.
post_xlv:          POST_XLV_TABLE

| Everything the USB controller reads by DMA is read and written by the
| CPU ONLY through the uncached alias (address + UNCACHED). The unit runs
| from SDRAM that ACR0 maps cacheable copyback, and the controller is a bus
| master that does not snoop the CPU's data cache -- so a dTD written through
| its cached address can still be dirty in cache when the controller fetches
| it, and the controller then reads whatever RAM held before. That presented
| on hardware as ENDPTPRIME clearing (the prime was consumed) while ENDPTSTAT
| never armed (the descriptor it found was not ACTIVE); per-line cpushl did
| NOT fix it, in either form; uncached structures did (his build's window at
| 0x4ec94a00 is itself an alias address). The loader writes this
| unit through the same alias and no code names these two arrays by their
| cached addresses, so nothing allocates a cache line for them (inferred
| from the access paths, not measured). dTDs are
| 32-byte aligned (the dQH and dTD next pointers keep bits 31:5 only).
| The dTDs are in on-chip SRAM (SRAM_ODTDS) since 27 Oct 2026, as USB IN's
| are: the controller reaches SRAM through the backdoor and it is not cached,
| and a CPU access there does not wait for the SDRAM.
| The high-speed ring is the packets themselves (since 27 Oct 2026): 1024
| frames of usb_frame_bytes each, then AUD_SPILL frames a packet that runs
| past the end continues into. Written by the producer through the alias
| only; the controller reads it. 16-byte aligned and a multiple of 16 long,
| so no cached datum shares a line with it (a write-back of a line the CPU
| dirtied through its cached address would land on the ring).
    .balign 32
aud_ring:          .space (AUD_FRAMES+AUD_SPILL)*SLOT_BYTES  | at most 80 B a frame (20 ch)
aud_bufs:          .space NSLOT*PKT_BUF          | full speed's packets (<= 360 B, one stride per slot)

    .balign 4
