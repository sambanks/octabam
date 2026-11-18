| TRACK TRIG MODES -- each track remembers its trig mode (8thmyth, 14 Nov
| 2026). Stock keeps one trig mode (0x460d16f0) and, across [MIDI], one
| stash for the other side (0x400c0aec). Here sixteen bytes, T1-T8 then
| M1-M8, hold the mode last chosen on each track; selecting a track (or
| crossing [MIDI]) brings its mode back before stock redraws the screen
| and the trig LEDs. Every mode is per track, QUICK MUTE and DELAY CTRL
| included (owner, 14 Nov 2026).
|
| Three kinds of site:
|  ttm_set   the trig mode list's two setters (FUNC + UP / DOWN), at their
|            `jsr 0x400359ac` right after `move.l (a0),0x460d16f0`: store
|            the new mode for the current track, then stock's box redraw.
|            Scrolling stores each row passed; the row the list is left on
|            is the last store, so it is the one kept.
|  ttm_sel   the track select 0x40083bf8, at its two track stores: replay
|            them, load the track's mode, on to stock's restage / redraw.
|  ttm_midi  the [MIDI] key 0x40055548, after stock's mode stash and side /
|            track swap (`clr.l 0x46c7d2c0`): load the new track's mode,
|            on to stock's page switch and redraw.
| Only d0/d1/a0 are used; every site has them free. A slot holds only a
| mode chosen from its own side's list, so it is always valid there.

        .equ    TRIG_MODE,  0x460d16f0      | long: 0 TRACKS 1 CHROMATIC 2 SLOTS 3 SLICES 4 QUICK MUTE 5 DELAY CTRL
        .equ    CUR_TRACK,  0x80000000      | byte: the current track 0..7 on the side shown
        .equ    UI_TRACK,   0x100b14cc      | byte: its UI mirror
        .equ    MIDI_MODE,  0x80000012      | long: nonzero = the MIDI tracks

        .text
        .global ttm_set, ttm_sel, ttm_midi, ttm_mem

| a0 = &ttm_mem[track + 8 * MIDI]; d1 clobbered.
ttm_slot:
        moveq   #0,%d1
        move.b  (CUR_TRACK).l,%d1
        andi.l  #7,%d1
        tst.l   (MIDI_MODE).l
        beq.s   1f
        addq.l  #8,%d1
1:      lea     ttm_mem:l,%a0
        adda.l  %d1,%a0
        rts

| The current track's stored mode into TRIG_MODE.
ttm_load:
        bsr.s   ttm_slot
        moveq   #0,%d0
        move.b  (%a0),%d0
        move.l  %d0,(TRIG_MODE).l
        rts

| jsr site 0x40051f1e / 0x40051f8e (`jsr 0x400359ac`).
ttm_set:
        bsr.s   ttm_slot
        move.l  (TRIG_MODE).l,%d0
        move.b  %d0,(%a0)
        jmp     (0x400359ac).l          | stock's box redraw, returns to the setter

| jmp site 0x40083c2e: d2 = the clamped track.
ttm_sel:
        move.b  %d2,(CUR_TRACK).l
        move.b  %d2,(UI_TRACK).l
        bsr.s   ttm_load
        jmp     (0x40083c3a).l

| jmp site 0x400555de.
ttm_midi:
        clr.l   (0x46c7d2c0).l
        bsr.s   ttm_load
        jmp     (0x400555e4).l

| Loader-owned DRAM, zeroed at boot: every track starts in TRACKS.
        .balign 4
ttm_mem:
        .zero   16
