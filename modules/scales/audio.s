| SCALES -- the audio tracks' scale: the PTCH knob, a step's PTCH lock and the
| CHROMATIC keys snap to the scale of the Part the UI edits (sc_audio, scales.s:
| one scale and one tonic per bank and Part). GNU as, a DRAM unit linked beside
| scales.s (cross-unit symbols resolve in the one link).
|
| The semantics, and the structure of the three routines below, are Tim
| Hastie's SCALE QUANTIZER (timhastie/octatrick-modules, MIT: qz_knob,
| qz_plock, qz_quant and qz_chrom in quantizer/quantizer.s, v2.9, which also
| holds the full account of the two keyboard positions and what the numbers
| mean). What differs: the mask and the tonic come from the Part's audio scale
| (sa_scale) and not from the project's SCALE and ROOT bytes; there is no synth
| branch, so a track whose PTCH is in semitones (FM SYNTH, CX OSC, SY DRUM) is
| not supported -- SCALES conflicts with the modules that make such tracks.
| OFF is stock, byte for byte: every routine replays what its detour displaced.
|
| A sample track's PTCH raw value is 64 + 5 * semitones, 4..124 (the page
| descriptor's minimum and count: 0x6a(%a3) and 0x9a(%a3)); the stock knob moves
| it one raw unit a detent, and with a scale on it moves to the next semitone
| that is in the scale. A CHROMATIC key's index 0..24 (12 = C, [TRIG 13]) makes
| raw = 5 * index + 4 (stock); with a scale on the index is transposed by the
| tonic (key 1 sounds the tonic) and snapped to the nearest degree, ties to the
| lower one.

        .text
        .globl  sa_knob, sa_plock, sa_chrom, sa_scale
        .balign 2

        .set    OCT_WORD, 0x460d16fc      | stock's CHROMATIC octave word: 0 or 1 (FUNC + LEFT/RIGHT eor it)

| sa_scale: -> d0 = the scale's pitch classes on its tonic (bit k = pitch class
| k from C), 0 for OFF; d1 = the tonic 0..11. The Part the UI edits. Clobbers
| d0, d1, a0, a1 (the service's calls); every other register kept.
sa_scale:
        jsr     store_part_ui_context
        move.l  %d0,%d1                 | the context, -1 none
        jbmi    sa_none
        move.l  %d1,-(%sp)
        jsr     sc_audio_mask           | d1 = the context -> d0 = the mask
        move.l  %d0,-(%sp)
        move.l  4(%sp),%d1
        jsr     sc_audio                | d0 = ID << 4 | tonic, -1 for OFF
        move.l  %d0,%d1
        andi.l  #15,%d1                 | the tonic
        move.l  (%sp)+,%d0              | the mask
        lea     4(%sp),%sp
        tst.l   %d0
        rts
sa_none:
        moveq   #0,%d0
        moveq   #0,%d1
        rts

| sa_on: d0 = the UI Part's mask, 0 for OFF, flags set; every other register
| kept (the detours' own registers are live: a0, a1 included).
sa_on:
        lea     -12(%sp),%sp
        movem.l %d1/%a0-%a1,(%sp)
        jbsr    sa_scale
        movem.l (%sp),%d1/%a0-%a1
        lea     12(%sp),%sp
        tst.l   %d0
        rts

| ---- the PTCH knob: jsr planted at 0x40055170 (the knob handler's store) -------
| Registers there (read off 0x40055008): d2 = the clamped new value, d6 = the
| value the knob was turned from (byte), a4 = the encoder delta, d5 = slot,
| a3 = the page descriptor (min at +0x6a, count at +0x9a, slot names at
| +0x16), a2 / a5 = the Part byte and its SRAM mirror. The three displaced
| instructions store d2 and load d1, so d1 is free here.
sa_knob:
        tst.l   %d5                     | slot A only
        jbne    sa_k_store
        moveq   #1,%d1
        move.l  %d1,sa_turned           | a turn while pushed is no press (scales.s sa_tick)
        tst.l   0x460d1684              | page kind 0 = PLAYBACK
        jbne    sa_k_store
        move.l  0x16(%a3),%d1           | the slot's name: "PTCH" (not THRU / NEIGHBOR)
        cmpi.l  #0x50544348,%d1
        jbne    sa_k_store
        move.l  %a4,%d1                 | delta: detents, signed
        jbeq    sa_k_store
        jbsr    sa_on                   | the Part's scale OFF: stock
        jbeq    sa_k_store
        mvz.b   %d6,%d2                 | start from the value the knob was turned from
        jbsr    sa_quant
sa_k_store:
        move.b  %d2,(%a2)               | displaced: the Part byte
        move.b  %d2,(%a5)               | displaced: its mirror
        move.w  %fp,%d1                 | displaced
        rts

| ---- the PTCH knob with a [TRIG] key held: jsr planted at 0x40050e60 --------------
| The p-lock editor (loops over the held steps; d6 = step, d7 = the rest) takes
| the step's lock byte -- or the Part's value when there is none (0xff) --
| through the slot's own handler and the descriptor clamp into d4, then
| stores it at (0x59,%a0,%a1.l) = track record + 0x59 + flat slot (a0 = the
| record, a1 = flat slot) and into the SRAM mirror after the hook. Same
| registers as above: d5 = slot, a3 = descriptor, fp = delta. The lock byte
| is still the old one when the hook runs, so the start value is read there.
sa_plock:
        move.l  %a2,-(%sp)
        tst.l   %d5                     | slot A only
        jbne    sa_p_done
        tst.l   0x460d1684              | PLAYBACK page only
        jbne    sa_p_done
        move.l  0x16(%a3),%d1
        cmpi.l  #0x50544348,%d1         | "PTCH"
        jbne    sa_p_done
        move.l  %fp,%d1                 | delta
        jbeq    sa_p_done
        jbsr    sa_on                   | the Part's scale OFF: stock
        jbeq    sa_p_done
        move.l  %d2,-(%sp)
        mvz.b   (0x59,%a0,%a1.l),%d2    | the step's lock before the store
        cmpi.l  #0xff,%d2
        jbne    sa_p_go                   | a lock: step from it
        move.l  %d3,-(%sp)              | none: from the Part's PTCH
        move.l  %d4,-(%sp)
        movea.l 0x46c82456,%a2
        mvz.b   0x100b14cf,%d2
        move.l  #6322,%d3
        muls.l  %d3,%d2
        adda.l  %d2,%a2                 | the Part
        adda.l  #0x8eda2,%a2            | its machine bytes
        mvz.b   0x100b14cc,%d4          | track
        mvz.b   (%a2,%d4.l),%d2         | machine
        move.l  %d2,%d3
        lsl.l   #3,%d3
        sub.l   %d2,%d3
        sub.l   %d2,%d3                 | machine * 6
        addq.l  #8,%a2                  | +0x8edaa: the PLAYBACK slots
        adda.l  %d3,%a2
        move.l  %d4,%d3
        lsl.l   #5,%d3
        sub.l   %d4,%d3
        sub.l   %d4,%d3                 | track * 30
        mvz.b   (%a2,%d3.l),%d2         | the Part's PTCH
        move.l  (%sp)+,%d4
        move.l  (%sp)+,%d3
sa_p_go:
        jbsr    sa_quant
        move.l  %d2,%d4                 | the value the store and the mirror take
        move.l  (%sp)+,%d2
sa_p_done:
        move.l  (%sp)+,%a2
        move.b  %d4,(0x59,%a0,%a1.l)    | displaced: the lock byte
        mvz.b   0x100b14cc,%d1          | displaced
        rts

| ---- sa_quant: d2 := d2 stepped |d1| degrees in the direction of d1 -------------
| a3 = the descriptor (min at +0x6a, count at +0x9a for slot A). Each step goes
| to the next raw value on a semitone of the scale (raw = 64 + 5 * n; sa_pcraw
| maps raw - min to a pitch class); a value between degrees snaps to the
| nearest one in the turn direction; at the ends the value stays, which is the
| stock clamp. The Part's scale OFF: d2 kept. Preserves everything but d2.
sa_quant:
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %d3,-(%sp)
        move.l  %d4,-(%sp)
        move.l  %d5,-(%sp)
        move.l  %d6,-(%sp)
        move.l  %d7,-(%sp)
        move.l  %a0,-(%sp)
        move.l  %a1,-(%sp)
        move.l  %d1,%d7                 | the delta, kept across sa_scale
        jbsr    sa_scale                | d0 = the mask, 0 OFF
        move.l  %d0,%d3
        jbeq    sa_q_out
        move.l  %d7,%d1
        move.l  0x6a(%a3),%d4           | d4 = the parameter's minimum (4)
        move.l  0x9a(%a3),%d5
        add.l   %d4,%d5
        subq.l  #1,%d5                  | d5 = its maximum (124)
        lea     sa_pcraw(%pc),%a0
        move.l  %d1,%d0                 | d0 = |delta| degrees to step
        jbpl    sa_q_loop
        neg.l   %d0
sa_q_loop:
        tst.l   %d1
        jbmi    sa_q_down
        jbsr    sa_q_up
        jbra    sa_q_next
sa_q_down:
        jbsr    sa_q_dn
sa_q_next:
        subq.l  #1,%d0
        jbne    sa_q_loop
sa_q_out:
        move.l  (%sp)+,%a1
        move.l  (%sp)+,%a0
        move.l  (%sp)+,%d7
        move.l  (%sp)+,%d6
        move.l  (%sp)+,%d5
        move.l  (%sp)+,%d4
        move.l  (%sp)+,%d3
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        rts

| d2 := the first raw above (sa_q_up) / below (sa_q_dn) d2 that sits on a semitone
| of the scale, within [d4, d5]; unchanged when there is none. d6/d7 scratch,
| a0 = sa_pcraw.
sa_q_up:
        move.l  %d2,%d6
sa_q_up1:
        addq.l  #1,%d6
        cmp.l   %d5,%d6
        jbgt    sa_q_ret
        jbsr    sa_q_pc                   | pitch class, 0xff between semitones
        cmpi.l  #12,%d7
        jbcc    sa_q_up1
        btst    %d7,%d3
        jbeq    sa_q_up1
        move.l  %d6,%d2
sa_q_ret:
        rts
sa_q_dn:
        move.l  %d2,%d6
sa_q_dn1:
        subq.l  #1,%d6
        cmp.l   %d4,%d6
        jblt    sa_q_ret
        jbsr    sa_q_pc
        cmpi.l  #12,%d7
        jbcc    sa_q_dn1
        btst    %d7,%d3
        jbeq    sa_q_dn1
        move.l  %d6,%d2
        rts

| sa_q_pc: d7 := the pitch class of raw d6 (a0 = sa_pcraw, d4 = the minimum),
| 0xff between semitones. Preserves everything but d7.
sa_q_pc:
        move.l  %d6,%d7
        sub.l   %d4,%d7
        mvz.b   (%a0,%d7.l),%d7
        rts

| ---- CHROMATIC trig mode: jsr planted at 0x4004fc58 (10 bytes) ----------------
| In 0x4004fb94 (track d2, key index a2 = 0..24 with 12 = C, TRIG 13), the press
| path is about to turn the index into the raw pitch (5 * idx + 4) that becomes
| the lock byte the voice is trigged with, the PTCH lock of a held or
| live-recorded trig and the box on the screen. With a scale on, transpose the
| index by the tonic (clamped at 24 = +12 st, the stock ceiling: a sample
| track's PTCH runs -12..+12) and snap it; the MIDI note the key sends out stays
| the key's own (d3, matched on release). Scratch d0, d1, a0, a1.
sa_chrom:
        jbsr    sa_scale                | d0 = the mask, d1 = the tonic
        jbeq    sa_c_replay               | OFF: stock
        move.l  %d2,-(%sp)
        move.l  %d3,-(%sp)
        move.l  %d4,-(%sp)
        move.l  %d0,%d3
        lea     sa_pc25(%pc),%a0
        move.l  %a2,%d2                 | the key index (key + 12 * stock's octave word: 0..15, or 12..24) ...
        add.l   %d1,%d2                 | ... transposed by the tonic: key 1 sounds it
        moveq   #6,%d4
        cmp.l   %d4,%d1                 | tonic G..B (> 6) in the OTHER position (the word 1, 13 keys): the
        jble    sa_c_top                  | keyboard drops two octaves, r .. r+12 -> r-24 .. r-12 st, the octave
        tst.l   OCT_WORD                | below the default position's r-12 .. r; the bottom 12 - r keys clamp
        jbeq    sa_c_top                  | at -12 st instead of the top r keys at +12
        subi.l  #24,%d2
        jbpl    sa_c_top
        moveq   #0,%d2                  | below -12 st: the stock floor (index 0)
sa_c_top:
        moveq   #24,%d1
        cmp.l   %d1,%d2
        jble    sa_c_inrange
        move.l  %d1,%d2                 | past +12 st: the stock ceiling (index 24)
sa_c_inrange:
        moveq   #0,%d4                  | distance: 0, 1, 2 ... -- lower candidate first
sa_c_loop:
        move.l  %d2,%d1
        sub.l   %d4,%d1
        jbmi    sa_c_hi
        mvz.b   (%a0,%d1.l),%d0
        btst    %d0,%d3
        jbne    sa_c_found
sa_c_hi:
        move.l  %d2,%d1
        add.l   %d4,%d1
        cmpi.l  #24,%d1
        jbhi    sa_c_more
        mvz.b   (%a0,%d1.l),%d0
        btst    %d0,%d3
        jbne    sa_c_found
sa_c_more:
        addq.l  #1,%d4
        cmpi.l  #24,%d4
        jbls    sa_c_loop
        move.l  %d2,%d1                 | no degree at all: cannot happen (every mask has its tonic)
sa_c_found:
        move.l  %d1,%a2
        move.l  (%sp)+,%d4
        move.l  (%sp)+,%d3
        move.l  (%sp)+,%d2
sa_c_replay:
        lea     (4,%a2,%a2.l*4),%a2     | displaced: raw = 5 * idx + 4
        mvz.b   0x100b14cf,%d0          | displaced: the part
        rts

        .balign 2
sa_pc25:                                | chromatic key index 0..24 -> pitch class (12 = C, TRIG 13 at tonic C)
        .byte   0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0
        .balign 2
sa_pcraw:                               | PTCH raw - 4 (0..120) -> pitch class when on a semitone (raw = 64 + 5*n), else 0xff
        .byte   0, 0xff, 0xff, 0xff, 0xff, 1, 0xff, 0xff, 0xff, 0xff
        .byte   2, 0xff, 0xff, 0xff, 0xff, 3, 0xff, 0xff, 0xff, 0xff
        .byte   4, 0xff, 0xff, 0xff, 0xff, 5, 0xff, 0xff, 0xff, 0xff
        .byte   6, 0xff, 0xff, 0xff, 0xff, 7, 0xff, 0xff, 0xff, 0xff
        .byte   8, 0xff, 0xff, 0xff, 0xff, 9, 0xff, 0xff, 0xff, 0xff
        .byte   10, 0xff, 0xff, 0xff, 0xff, 11, 0xff, 0xff, 0xff, 0xff
        .byte   0, 0xff, 0xff, 0xff, 0xff, 1, 0xff, 0xff, 0xff, 0xff
        .byte   2, 0xff, 0xff, 0xff, 0xff, 3, 0xff, 0xff, 0xff, 0xff
        .byte   4, 0xff, 0xff, 0xff, 0xff, 5, 0xff, 0xff, 0xff, 0xff
        .byte   6, 0xff, 0xff, 0xff, 0xff, 7, 0xff, 0xff, 0xff, 0xff
        .byte   8, 0xff, 0xff, 0xff, 0xff, 9, 0xff, 0xff, 0xff, 0xff
        .byte   10, 0xff, 0xff, 0xff, 0xff, 11, 0xff, 0xff, 0xff, 0xff
        .byte   0
        .balign 4
