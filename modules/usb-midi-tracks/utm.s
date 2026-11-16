| utm.s -- USB MIDI TRACKS: every audio-track START becomes USB MIDI, USB only.
|
| One ColdFire unit, no detour: the kind table's FLEX and STATIC renderer
| entries (0x400d6438 / 0x400d6434, stock value 0x40004008) are repointed here,
| as SYNTH MACHINE does, so the two cannot share an image (the ledger refuses
| the pair by overlap). The packer calls a track's renderer twice a frame,
| [0,n) for the old voice and [n,16) for the new one, and runs the start
| handler between the two calls: on the SECOND call of a start frame the
| voice struct already holds the new sample's record (synth README, "the voice
| struct"). A start frame is bit 4 of the nibble byte 0x46104d0c[t], set during
| both calls. This wrapper does its work and tail-jumps to the stock renderer
| with the stack untouched.
|
| For each START on track t (0..7) it queues, as ONE batch on usbmidi.s's
| queue (usbmidi_tx_queue: USB only, the DIN port is never touched), on the
| track's TRIG CHANNEL (0x8000003f + t; -1 = OFF sends nothing, as stock):
|     Bn  16..21    PTCH STRT LEN RATE RTRG RTIM, as the voice gets them
|                   (SEND = NOTES+CC only)
|     9n  slot      VEL      note = the playing sample's slot, 0..127
| and GATE_FRAMES second calls (frames) later
|     8n  slot      0        note-off, on the channel the note-on went out on;
|                            a new START first closes a pending one.
| The BRAIN setting SEND (OFF, NOTES, NOTES+CC) gates the note-ons and the CCs;
| a note-off owed is always sent, so turning SEND off never strands a note.
|
| Nothing here runs the encoder. The frame interrupt only queues
| (usbmidi_tx_queue) and posts utm_kick to the engine task through stock's
| deferred-call queue (0x40000c3c, record type 21: what stock's frame
| interrupt, REMOTE and REMIX SWITCH post), at most one post outstanding.
| utm_kick runs usbmidi_tx_kick in task context; while a transfer is in
| flight the EP2 IN completion's own kick drains the rest. TRAPS
| trap-late-frame: the encoder runs unmasked and took ~150 us of window.
|
| Stuck notes: a track whose machine leaves FLEX/STATIC (a part, kit or
| machine change, a project load) stops reaching utm_render, so its own gate
| would never count down. utm_seen holds one bit per track rendered in the
| current frame; a second call that finds its own bit already set opens a new
| frame and first closes the pending note of every track not seen in the
| frame before. With no FLEX/STATIC track left at all nothing runs here, and
| the note is closed at the next render call of any track.
|
| What is read, and how sure it is:
|   knobs      the parameter record, pointer 0x800062a8: halfwords 0..5, high byte
|              (MIDI.md 1, LFO.md): the frame builder's output, so trig locks, the
|              crossfader's morph and any LFO on the knob are in it. The lane
|              0x80000810 has no morph. Measured with locks and a scene sweep.
| The numbers are stock's own for these knobs (what the unit and CC FEEDBACK send)
| and the values its raw bytes. PTCH: 64 = unpitched, 5 = a semitone. STRT with SLIC
| ON: raw/2 + 1 = the slice. RTRG: raw + 1 on the panel. SLIC itself is the page-2
| ON/OFF switch and has no CC.
|   channel    0x8000003f + t, MIDI_TRIG_CH1..8, -1 = OFF (MIDI.md, the CC
|              handler's map and Appendix D; cc-feedback reads the same byte).
|   slot       voice 0x800049d8 + 0xa8*t, +8 = the sample's settings record:
|              FLEX 0x100b14f0 + 0x448*slot (136 records), STATIC 0x100d5b30 + ...
|              (synth README, the voice struct; written by the start handler
|              0x4000f450 before the second call). Measured under the port.
| RETRIGS (stock renderer 0x40004008 read and run, 3 Nov 2026). Per-track render
| state at 0x80004898 + 40*t (the pointer 0x800062a4 walks it): +4 count, latched
| from the parameter record's RTRG word on the START, +8 repeats done, +0xc
| position, +0x18 interval. Each second call recomputes the interval from the
| record's live RTIM, and each time it runs out the live RTRG is compared with
| the repeats done (127 = endless); then the renderer restarts the voice with
| jsr 0x4000f450(track, state+0x10, state+0x14), at 0x4000421c. That call's
| operand (0x4000421e) is repointed here, so one repeat is one call whatever a
| scene or the crossfader does to RTRG/RTIM meanwhile: nothing is latched here.
| The packer's own START reaches 0x4000f450 through its table (0x400d6454), not
| through this call, so every hit is a repeat. On a START frame the first call
| also restarts the OLD voice here; that hit is skipped (the START's own note
| follows in the second call), so the host never sees on(old), off(old), on(new)
| in one frame. A count latched as 0 means no repeats for that voice, in the
| audio too. RTRG is shown raw + 1: the panel's minimum 1 is raw 0 (one play,
| the default) and raw 127 is INF.
| utm_retrig closes the note if its gate has not run out yet and sends the note
| again, with its CCs, from the voice's record as it stands. The stop routine
| 0x40006820 clears the count, so a voice that died repeats nothing.

        .include "remix.inc"            | get_send (BRAIN: 0 OFF, 1 NOTES, 2 NOTES+CC)

        .text
        .global utm_render, utm_retrig, utm_kick, utm_dbg

        .set    CC_FIRST,    16             | PLAYBACK page 1, slots 0..5
        .set    VEL,         100
        .set    GATE_FRAMES, 160            | ~58 ms at 16 samples/frame, 44.1 kHz
        .set    SEND_CC,     2              | SEND = NOTES+CC
        .set    FP_PTR,      0x800062a8     | the packer's per-track parameter record
        .set    TRIGCH,      0x8000003f     | +t: the track's TRIG CHANNEL, 0..15, -1 = OFF
        .set    VOICE,       0x800049d8
        .set    NIBBLE,      0x46104d0c
        .set    FLEX0,       0x100b14f0
        .set    SLOTSZ,      0x448
        .set    SLOTSPAN,    0x24640        | 136 records; STATIC's table (0x100d5b30) follows FLEX's
        .set    STOCK_RENDER, 0x40004008
        .set    START_HANDLER, 0x4000f450
        .set    DEFER,       0x40000c3c     | (queue, record {byte 21, 0, long fn}): fn runs in the task
        .set    ENGQ,        0x460d17ce     | the engine task's queue (KERNEL.md)

| utm_render(track, ping, start, end): the stock renderer's arguments, at
| 4(%sp).. on entry. Registers saved here; the stock routine is jumped to with
| the stack as it came.
utm_render:
        lea     -36(%sp),%sp
        movem.l %d0-%d4/%a0-%a3,(%sp)    | args now at 40 track, 44 ping, 48 start, 52 end
        moveq   #16,%d0
        cmp.l   52(%sp),%d0
        bne     utm_out                  | the frame's first call
        move.l  40(%sp),%d4              | d4 = track
        cmpi.l  #8,%d4
        bcc     utm_out
        lea     utm_dbg(%pc),%a2
        addq.l  #1,(%a2)                 | second calls seen for an audio track
        lea     -48(%sp),%sp             | batch: 7 swept offs + own off + 6 CCs + on = 45
        movea.l %sp,%a1                  | a1 = start of the batch
        movea.l %sp,%a0                  | a0 = write pointer
        bsr     utm_sweep                | a new frame: close the notes of tracks not rendered
        lea     utm_state(%pc),%a3
        move.l  %d4,%d2
        lsl.l   #2,%d2
        adda.l  %d2,%a3                  | a3 = this track's state: +0 note+1 (0 = none), +1 channel, +2 frames left
        tst.b   (%a3)
        beq     utm_chk                  | nothing pending
        mvz.w   2(%a3),%d3
        subq.l  #1,%d3
        move.w  %d3,2(%a3)
        tst.l   %d3
        bne     utm_chk
        bsr     utm_off                  | the gate ran out
utm_chk:
        lea     NIBBLE,%a2
        adda.l  %d4,%a2
        btst    #4,(%a2)                 | a voice starts this frame
        beq     utm_flush
        lea     utm_dbg(%pc),%a2
        addq.l  #1,4(%a2)                | STARTs seen
        tst.b   (%a3)
        beq     utm_nooff
        bsr     utm_off                  | a new START closes the note still sounding
utm_nooff:
        bsr     utm_on
utm_flush:
        bsr     utm_send
        lea     48(%sp),%sp
utm_out:
        movem.l (%sp),%d0-%d4/%a0-%a3
        lea     36(%sp),%sp
        jmp     STOCK_RENDER

| utm_retrig(track, a, b): the renderer's call of the start handler for one
| repeat. Everything is saved: the caller keeps its registers live across it.
utm_retrig:
        lea     -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)    | return address at 60, track at 64
        move.l  64(%sp),%d4              | track
        cmpi.l  #8,%d4
        bcc     utm_rt_out
        lea     NIBBLE,%a2
        adda.l  %d4,%a2
        btst    #4,(%a2)                 | a START frame: this is the old voice, replaced
        bne     utm_rt_out               | in this frame's second call; send nothing for it
        lea     utm_dbg(%pc),%a2
        addq.l  #1,16(%a2)               | repeats seen
        lea     -24(%sp),%sp             | batch: off + 6 CCs + on
        movea.l %sp,%a1
        movea.l %sp,%a0
        lea     utm_state(%pc),%a3
        move.l  %d4,%d2
        lsl.l   #2,%d2
        adda.l  %d2,%a3
        tst.b   (%a3)
        beq     utm_rt_on                | the gate already ran out
        bsr     utm_off
utm_rt_on:
        bsr     utm_on
        bsr     utm_send
        lea     24(%sp),%sp
utm_rt_out:
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea     60(%sp),%sp
        jmp     START_HANDLER

| utm_sweep: on the first second call of a new frame (this track's bit already
| set in utm_seen), append a note-off for every pending note of a track not
| rendered in the frame before, then start the new frame's set with this track.
| In: a0 = write pointer, d4 = track.  Trashes d0-d3, a2, a3.
utm_sweep:
        lea     utm_seen(%pc),%a2
        mvz.b   (%a2),%d0
        btst    %d4,%d0
        beq     utm_sw_mark              | first time this frame for this track
        moveq   #0,%d1                   | d1 = track u
        lea     utm_state(%pc),%a3
utm_sw_next:
        tst.b   (%a3)
        beq     utm_sw_skip              | u has nothing pending
        btst    %d1,%d0
        bne     utm_sw_skip              | u was rendered: its own gate counts
        lea     utm_dbg(%pc),%a2
        addq.l  #1,20(%a2)               | notes closed for a track no longer rendered
        bsr     utm_off
utm_sw_skip:
        addq.l  #4,%a3
        addq.l  #1,%d1
        cmpi.l  #8,%d1
        bne     utm_sw_next
        moveq   #0,%d0                   | a new frame
        lea     utm_seen(%pc),%a2
utm_sw_mark:
        bset    %d4,%d0
        move.b  %d0,(%a2)
        rts

| utm_on: append the six CCs (SEND = NOTES+CC) and the note-on of this track's
| voice on its TRIG CHANNEL, arm the gate. Nothing if SEND is OFF, the channel
| is OFF, or the voice's record is not a sample slot.
| In: a0 = write pointer, a3 = state, d4 = track.  Trashes d0-d3, a2.
utm_on:
        get_send %d1
        tst.l   %d1
        beq     utm_on_x                 | SEND = OFF
        lea     TRIGCH,%a2
        adda.l  %d4,%a2
        mvz.b   (%a2),%d3                | the track's channel; -1 (OFF) reads 255
        cmpi.l  #16,%d3
        bcc     utm_on_x                 | TRIG CHANNEL OFF: stock sends nothing either
        | ---- the note: the sample slot of this track's voice
        move.l  %d4,%d2
        move.l  %d4,%d0
        lsl.l   #3,%d2                   | t*8
        lsl.l   #5,%d0                   | t*32
        add.l   %d0,%d2                  | t*40
        lsl.l   #2,%d0                   | t*128
        add.l   %d0,%d2                  | t*168 = 0xa8*t
        lea     VOICE,%a2
        adda.l  %d2,%a2
        move.l  8(%a2),%d0               | the sample's settings record
        lea     utm_dbg(%pc),%a2
        move.l  %d0,8(%a2)               | debug: the last record read
        subi.l  #FLEX0,%d0
        cmpi.l  #SLOTSPAN,%d0
        bcs     utm_slot                 | inside the FLEX table
        subi.l  #SLOTSPAN,%d0            | STATIC's table follows it
        cmpi.l  #SLOTSPAN,%d0
        bcc     utm_on_x                 | no record: no note
utm_slot:
        move.l  #SLOTSZ,%d2
        divu.l  %d2,%d0                  | d0 = slot
        cmpi.l  #128,%d0
        bcc     utm_on_x                 | a recorder buffer: no note
        cmpi.l  #SEND_CC,%d1
        bcs     utm_note                 | SEND = NOTES: no CCs
        | ---- the knobs as this frame's record has them
        movea.l FP_PTR,%a2
        moveq   #CC_FIRST,%d1
utm_cc:
        move.l  %d3,%d2
        ori.l   #0xB0,%d2                | control change on the trig channel
        move.b  %d2,(%a0)+
        move.b  %d1,(%a0)+
        mvz.b   (%a2),%d2                | the halfword's high byte
        addq.l  #2,%a2
        andi.l  #0x7f,%d2
        move.b  %d2,(%a0)+
        addq.l  #1,%d1
        cmpi.l  #CC_FIRST+6,%d1
        bne     utm_cc
utm_note:
        move.l  %d3,%d2
        ori.l   #0x90,%d2                | note-on on the trig channel
        move.b  %d2,(%a0)+
        move.b  %d0,(%a0)+
        move.b  #VEL,(%a0)+
        move.b  %d3,1(%a3)               | the note-off goes out on this channel
        move.l  %d0,%d2
        addq.l  #1,%d2
        move.b  %d2,(%a3)                | pending: note + 1
        move.w  #GATE_FRAMES,2(%a3)
        lea     utm_dbg(%pc),%a2
        addq.l  #1,12(%a2)               | notes queued
utm_on_x:
        rts

| utm_off: append the note-off for the pending note at a3, on the channel its
| note-on used, and clear it.
| In: a0 = write pointer, a3 = state.  Trashes d2, d3.
utm_off:
        mvz.b   (%a3),%d2
        subq.l  #1,%d2                   | the note
        mvz.b   1(%a3),%d3
        ori.l   #0x80,%d3
        move.b  %d3,(%a0)+
        move.b  %d2,(%a0)+
        clr.b   (%a0)+                   | velocity 0
        clr.b   (%a3)
        rts

| utm_send: hand the batch to the USB MIDI module's queue, USB only, and have
| the engine task kick it (utm_kick): the encoder never runs in this interrupt.
| In: a1 = start, a0 = end.  Trashes d0-d3, a0, a1 (and DEFER's d0-d1/a0-a1).
utm_send:
        move.l  %a0,%d0
        sub.l   %a1,%d0                  | bytes in the batch
        beq     utm_send_x
        tst.b   usbmidi_up
        beq     utm_send_x               | no host session: nothing goes out
        movea.l %a1,%a0
        jsr     usbmidi_tx_queue         | d0 = len, a0 = buf; no kick
        tst.b   utm_kick_pending
        bne     utm_send_x               | a kick is already posted
        moveq   #1,%d0
        move.b  %d0,utm_kick_pending
        pea     utm_kick_rec
        pea     ENGQ
        jsr     DEFER
        addq.l  #8,%sp
        lea     utm_dbg(%pc),%a0
        addq.l  #1,24(%a0)               | kicks posted
utm_send_x:
        rts

| utm_kick: in the engine task. Clear the flag first, so a batch queued after
| it posts again, then run usbmidi's kick (a no-op while EP2 IN is busy: the
| completion ISR kicks then).
utm_kick:
        clr.b   utm_kick_pending
        move.l  %d2,%sp@-
        jsr     usbmidi_tx_kick          | trashes d0-d2, a0, a1
        move.l  %sp@+,%d2
        rts

        .balign 4
utm_kick_rec:                            | DEFER's record
        .byte   21, 0
        .long   utm_kick
utm_kick_pending:
        .byte   0
utm_seen:                                | bit t: track t rendered in the current frame
        .byte   0
        .balign 4
utm_dbg:                                 | second calls, STARTs, last record, notes queued, repeats,
        .space  28                       | notes swept, kicks posted
utm_state:
        .space  32                       | 8 tracks * 4: note+1, channel, frames-left word
