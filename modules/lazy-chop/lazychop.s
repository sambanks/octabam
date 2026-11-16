| LAZY CHOP -- one DRAM unit. GNU as, ColdFire (m68k-elf-as -mcpu=54455).
|
| A mode on the audio editor's stock SLICE page. LAZY CHOP (the slice
| menu's first row) registers a key layer of its own on top of the page's
| (0x40031494, the firmware's keymap list; the last registered wins). The
| layer holds only the trig keys, YES and NO, and only while chopping; the
| page's encoders and drawing stay stock.
|
|   While chopping, the sequencer's own trigs on the chopped track are
|   held off (lc_cmdgate), so the take plays straight on; the other tracks
|   play as usual.
|
|   CHOP   TRIG 1 plays the editor's track from the trim start (slice 1
|          starts there). TRIG n+1 ends slice n and starts slice n+1 at the
|          playhead; after TRIG 16 the page turns (a popup says SLICES 17-32)
|          and the next TRIG 1 starts slice 17, and so on
|          to 64. Only the expected key places a marker. YES (or slice 64)
|          writes the slices; NO puts back the ones there before.
|   While LAZY CHOP is open the trig LEDs show this page: red for the
|   slices made, green for the next key to tap (a new page starts with
|   TRIG 1 green); at the end they are stock's again. Stock's trig-LED pass
|   (0x40043fdc, called through the slot 0x400c0936) runs first and LAZY
|   CHOP skips that pass while it is open (lc_ledpass): stock's running
|   light blinks the playhead's pair and dims one of them, which LAZY CHOP
|   would otherwise undo and stock redo at every step (on 8thmyth's MKI,
|   F5: a trig flashing and the keys starved after two chops). The LED
|   task's tick checks ids 0-31 at 20 Hz (lc_tick) and sets again only the
|   ids that differ, so a stray flash is undone with a message or two.
|   Either way the mode ends and the keys are stock's again: the slices are
|   edited as any others (LEVEL moves between them, A/B/C edit).
|
| While chopping, entry 0 of the slice table is the whole take and the
| slices made are entries 1..n (the open last one runs to the trim end),
| count n+1: the editor draws every marker, and the voice, which follows
| entry 0's window live when SLIC is on, plays the whole take (with the
| slices in place it stopped at slice 1's end: 8thmyth's MKI, F5). YES
| moves them down to 0..n-1, count n. The voice playing the take keeps the
| window it started with. A tap behind the last marker (the take looped,
| or a trig restarted the track) places nothing and says LOOPED.
| The page's leave routine (0x40071bac) calls lc_leave (a detour on its
| map removal), so the layer never outlives the SLICE page.
|
| Firmware facts this relies on (1.40C, read statically and measured under the port):
|   record (0x4006da78)  +300 trim start, +304 trim end, +312 64 x {start, end, loop},
|                        +1080 the editor's marker, +1092 slice count
|   voice t              0x800049d8 + 0xa8*t: +0 active, +8 settings (the record), +68 position
|   track command        0x46c80354 + 4*t: 0x1d plays track t next frame, 0x40 releases
|   current track        byte 0x100b14cc
|   slice under marker   0x400ceb3c

        .include "remix.inc"            | get_snap/put_snap, get_live/put_live (the settings)
        .equ    REC_TRIM_S, 300
        .equ    MIN_START,  384        | slice 1 and the take not before frame 384 while stretching (see lc_s0)
        .equ    REC_TRIM_E, 304
        .equ    REC_SLICES, 312
        .equ    REC_MARK,   1080
        .equ    REC_COUNT,  1092
        .equ    BACKUP_LONGS, 196          | +312 .. +1095: the slices, the marker, the count
        .equ    MAX_SLICES, 64
        .equ    MIN_GAP,    64             | samples, at least, between two markers

        .equ    VOICES,     0x800049d8
        .equ    CMD,        0x46c80354
        .equ    CMD_PLAY,   0x1d
        .equ    CMD_STOP,   0x40
        .equ    CUR_TRACK,  0x100b14cc
        .equ    SEL,        0x400ceb3c

        .equ    F_BUSY,     0x4006e2cc     | () -> 0 when the editor can act
        .equ    F_HAS,      0x4006dae4     | (-1) -> non-zero when the slot has audio
        .equ    F_REC,      0x4006da78     | () -> the edited slot's record, 0 if none
        .equ    F_REG,      0x40031494     | (map) register a key layer
        .equ    F_UNREG,    0x4003146c     | (map) remove it
        .equ    F_SORT,     0x40070c28     | (slices, count)
        .equ    F_UPD1,     0x40070cbc     | ADD SLICE HERE's refresh, in order
        .equ    F_UPD2,     0x400718f8
        .equ    F_REDRAW,   0x4006dbdc
        .equ    F_EDITED,   0x40044920
        .equ    F_LEDON,    0x40013784     | set_led(id, ticks): on for ticks of a 120 Hz countdown; 0 = off
        .equ    F_UNBLINK,  0x400131c8     | (id) clears the id's blink bit
        .equ    F_LEVEL,    0x400135b0     | (id, 0..15) the LED's brightness (cached: sent only on a change)
        .equ    TICK_DIV,   6              | lc_tick checks every 6th 120 Hz tick: 20 Hz
        .equ    F_TRIGLEDS, 0x40043fdc     | stock's trig-LED pass (arg: as given)
        .equ    F_LEDTICK,  0x4001387c     | the 120 Hz LED countdown tick (no args)
        .equ    LED_STATE,  0x460ba9ae     | on bits, id i = byte i>>3 bit i&7
        .equ    LED_BLINK,  0x460ba98c     | blink phase, XORed on the wire
        .equ    LED_LONG,   0x00ffffff     | ~39 hours: on until LAZY CHOP clears it
        .equ    F_TOAST,    0x4005a2b8     | (text, duration)
        .equ    F_SPRINTF,  0x40013a08
        .equ    F_FRAMEADDR, 0x4009499c    | (arena id, frame, 1) -> d0 = the frame's address (FLEX 0-127, recorders 128-135)
        .equ    F_OBJREC,   0x400946d8     | (1, arena id) -> its control record, 0 if none
        .equ    F_RECPOST,  0x40005178     | (track, word, 1): stock's recorder command (TRACK+REC's own call, 0x40083908)
        .equ    REC_POS,    0x46c802c8     | + 4t: frames recorded in recorder t's take (the record head)
        .equ    BANK_BLOB,  0x46c82456     | the bank in RAM; its Parts at +0x8ed80 + part * 0x18b2
        .equ    CUR_PARTB,  0x100b14cf     | the current Part (byte)
        .equ    PART_RSET,  0x602          | a Part's RECORDING SETUP, 12 bytes a track:
                                           | +0 INAB, +1 INCD (0 = "-"), +3 TRIG, +4 SRC3 (0 = "-")
        .equ    MUTE_BYTE,  0x8000000a     | the tracks' mute bits (bit t), the byte of 0x80000008's 8-15
        .equ    REC_HALT,   0x80           | stop, as 0x40083806 posts it
        .equ    REC_NOW,    0x46c7e9fa     | + 4t: the immediate mailbox (REC THRESHOLD's), acted on in the frame interrupt
        .equ    VSTRIDE,    0xa8
        .equ    FLEX_BASE,  0x100b14f0     | arena record 0; 1096 bytes each, 136 of them
        .equ    ARENA_N,    136
        .equ    HOLD_TICKS, 60             | undo: a hold of 0.5 s (the LED task's 120 Hz tick)
        .equ    SNAP_W1,    352            | frames searched either side of a tap first (8 ms)
        .equ    SNAP_W,     1024           | then, with no crossing there, 23 ms: anything above ~22 Hz
                                           | (8 ms alone fell back to the quietest frame on bass-heavy cuts, 8thmyth, H5)
        .equ    STATIC_BASE, 0x100d5b30    | STATIC slot records, 1096 bytes each, 128 of them
        .equ    STATIC_STAT, 0x46c90a78    | STATIC slot status records, 44 bytes each: +0 the format
        .equ    FMT_TABLE,  0x80003c20     | 16 bytes a format: +8 bytes per frame
        .equ    STR_DESC,   0x46aa9e80     | STATIC stream buffer: compartment descriptors, 8 bytes
        .equ    STR_DATA,   0x46949e80     | its audio, 4,096 bytes a compartment

        .equ    ST_OFF,     0
        .equ    ST_ARMED,   1
        .equ    ST_CHOP,    2

        .text
        .global lc_ledflt
        .global lc_open, lc_leave, lc_trig, lc_yes, lc_no, lc_ledpass, lc_tick, lc_cmdgate, lc_trigup, lc_snapfix, lc_snapdone

| ---- helpers (clobber d0-d1/a0-a1 only) ----------------------------------

| a0 <- voice of lc_track
lc_voice:
        move.l  lc_track,%d1
        move.l  %d1,%d0
        lsl.l   #7,%d0                  | 128t
        lsl.l   #3,%d1                  | 8t
        add.l   %d1,%d0
        lsl.l   #2,%d1                  | 32t
        add.l   %d1,%d0                 | 168t
        add.l   #VOICES,%d0
        move.l  %d0,%a0
        rts

| a1 <- &slice[d0] of lc_rec (d0 kept)
lc_slice:
        move.l  %d0,%d1
        lsl.l   #2,%d1                  | 4n
        move.l  %d1,%a1
        add.l   %d1,%d1                 | 8n
        add.l   %d1,%a1                 | 12n
        add.l   lc_rec,%a1
        lea     REC_SLICES(%a1),%a1
        rts

| track command d0 -> lc_track (a play is marked LAZY CHOP's own, so
| lc_cmdgate lets it through)
lc_cmd:
        cmp.l   #CMD_PLAY,%d0
        bne     1f
        moveq   #1,%d1
        move.l  %d1,lc_own
        move.l  %d0,-(%sp)
        bsr     lc_lockplay             | the edited slot as the trig's sample lock
        move.l  (%sp)+,%d0
1:      move.l  lc_track,%d1
        lsl.l   #2,%d1
        add.l   #CMD,%d1
        move.l  %d1,%a0
        move.l  %d0,(%a0)
        rts

| ---- ZERO SNAP: the audio around a tap ----------------------------------
|
| Where the frames come from:
|   FLEX slots and recorders (arena 0-135): the firmware's frame-address
|     routine 0x4009499c(id, frame, 1), once per contiguous run (it returns
|     the frames left in the 6,144-byte block in d1).
|   STATIC slots: the stream buffer the streaming task (0x40091d18) fills
|     from the card: 4,096-byte chunks of the sample's data; chunk c of
|     track t sits in compartment 32t + 2(c & 15) or the one after, whose
|     8-byte descriptor at 0x46aa9e80 + 8*index holds c >> 4 (+0), the slot
|     (+4) and a loaded flag (+5); its audio is at 0x46949e80 + 4096*index.
|     A frame that is not buffered is left out of the search.
| Format (both): the record's first long, then bytes per frame from the
| table 0x80003c20 + 16*format + 8: 3/6 (24-bit mono/stereo), 2/4 (16-bit).
| Frames are big-endian, left first; the top 16 bits of each channel are
| read byte by byte (no alignment assumed) and summed (mono: left twice).

| a0 <- the address of frame d0 in the snap source, d1 <- the frames left in
| that run; a0 = 0 when it is not readable. Clobbers d0-d1/a0-a1.
lc_ptr:
        move.l  lc_src,%d1
        cmp.l   #2,%d1
        beq     5f
        pea     1.w                     | FLEX / recorder
        move.l  %d0,-(%sp)
        move.l  lc_id,-(%sp)
        jsr     (F_FRAMEADDR).l
        lea     12(%sp),%sp
        move.l  %d0,%a0
        tst.l   %d1
        bgt     9f
        sub.l   %a0,%a0
9:      rts
5:      lea     -12(%sp),%sp            | STATIC: the stream buffer
        movem.l %d2-%d4,(%sp)
        move.l  lc_bpf,%d1
        mulu.l  %d1,%d0                 | byte offset in the sample's data
        move.l  %d0,%d2
        and.l   #4095,%d2               | w: inside the chunk
        moveq   #12,%d1
        lsr.l   %d1,%d0                 | c: the chunk
        move.l  %d0,%d4
        lsr.l   #4,%d4                  | c >> 4: what its descriptor holds
        and.l   #15,%d0
        add.l   %d0,%d0
        move.l  lc_tbase,%d3
        add.l   %d0,%d3                 | index 32t + 2(c & 15)
        moveq   #0,%d0                  | try 0, then index + 1
1:      move.l  %d3,%d1
        lsl.l   #3,%d1
        add.l   #STR_DESC,%d1
        move.l  %d1,%a0
        tst.b   5(%a0)                  | loaded?
        beq     2f
        moveq   #0,%d1
        move.b  4(%a0),%d1              | this slot's?
        cmp.l   lc_id,%d1
        bne     2f
        cmp.l   (%a0),%d4               | this chunk?
        bne     2f
        move.l  %d3,%d0                 | found
        moveq   #12,%d1
        lsl.l   %d1,%d0
        add.l   #STR_DATA,%d0
        add.l   %d2,%d0
        move.l  %d0,%a0
        move.l  #4096,%d1
        sub.l   %d2,%d1
        move.l  lc_bpf,%d0
        divu.l  %d0,%d1                 | whole frames left in the chunk
        tst.l   %d1
        bgt     8f
        bra     4f
2:      tst.l   %d0
        bne     4f                      | both tried
        moveq   #1,%d0
        addq.l  #1,%d3
        bra     1b
4:      sub.l   %a0,%a0                 | not buffered
        moveq   #0,%d1
8:      movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| d0 <- the top 16 bits of the channel at a0 (signed), read byte by byte
lc_s16:
        move.b  (%a0),%d0
        extb.l  %d0
        lsl.l   #8,%d0
        move.l  %d1,-(%sp)
        moveq   #0,%d1
        move.b  1(%a0),%d1
        or.l    %d1,%d0
        move.l  (%sp)+,%d1
        rts

| ZERO SNAP: d2 (a tap's frame) moves to the nearest zero crossing of the
| mono sum within SNAP_W frames; with none, to the quietest frame there;
| with nothing readable, it stays. Kept inside (trim start, trim end).
lc_snapfix:
        tst.l   lc_snap
        beq     99f
        move.l  lc_rec,%d0
        sub.l   #FLEX_BASE,%d0
        blt     99f
        move.l  #1096,%d1
        divu.l  %d1,%d0                 | arena id, or past it: STATIC?
        cmp.l   #ARENA_N,%d0
        blt     10f
        move.l  lc_rec,%d0              | STATIC slot 0-127?
        sub.l   #STATIC_BASE,%d0
        blt     99f
        move.l  #1096,%d1
        divu.l  %d1,%d0
        cmp.l   #128,%d0
        bge     99f
        move.l  %d0,lc_id
        moveq   #2,%d1
        move.l  %d1,lc_src
        moveq   #44,%d1                 | its status record: the format
        mulu.l  %d1,%d0
        add.l   #STATIC_STAT,%d0
        move.l  %d0,%a0
        move.l  lc_track,%d0
        lsl.l   #5,%d0
        move.l  %d0,lc_tbase            | 32t
        bra     20f
10:     move.l  %d0,lc_id               | FLEX / recorder
        moveq   #1,%d1
        move.l  %d1,lc_src
        move.l  %d0,-(%sp)              | its control record (none: no snap)
        pea     1.w
        jsr     (F_OBJREC).l
        addq.l  #8,%sp
        tst.l   %d0
        beq     99f
        move.l  %d0,%a0
20:     move.l  (%a0),%d0               | format 0-3
        cmp.l   #3,%d0
        bhi     99f
        lsl.l   #4,%d0
        add.l   #FMT_TABLE+8,%d0
        move.l  %d0,%a0
        move.l  (%a0),%d0               | bytes per frame
        move.l  %d0,lc_bpf
        lsr.l   #1,%d0                  | the right channel's offset: bpf/2 (stereo)
        move.l  lc_bpf,%d1
        cmp.l   #4,%d1
        bge     21f
        moveq   #0,%d0                  | mono: left twice
21:     move.l  %d0,lc_roff
        lea     -36(%sp),%sp
        movem.l %d3-%d7/%a2-%a5,(%sp)
        move.l  #SNAP_W1,%d0
        move.l  %d0,lc_w
15:     move.l  lc_rec,%a0
        bsr     lc_s0
        move.l  %d0,%d3
        addq.l  #1,%d3                  | lowest frame
        move.l  %d2,%d0
        sub.l   lc_w,%d0
        cmp.l   %d3,%d0
        blt     22f
        move.l  %d0,%d3                 | d3 = i, from max(tap - W, trim start + 1)
22:     move.l  REC_TRIM_E(%a0),%d4
        subq.l  #1,%d4
        move.l  %d2,%d0
        add.l   lc_w,%d0
        cmp.l   %d4,%d0
        bgt     23f
        move.l  %d0,%d4                 | d4 = to min(tap + W, trim end - 1)
23:     tst.l   lc_behind               | a LIVE take: nothing is recorded past the head
        beq     24f
        cmp.l   %d2,%d4
        ble     24f
        move.l  %d2,%d4
24:     moveq   #-1,%d6                 | nearest crossing so far
        move.l  #0x7fffffff,%d7         | its distance
        move.l  #0x7fffffff,%d0
        move.l  %d0,lc_qv               | the quietest |sum| so far
        moveq   #-1,%d0
        move.l  %d0,lc_qf               | and its frame
        clr.l   lc_hp                   | no previous frame yet
        sub.l   %a3,%a3                 | frames left in the current run
        move.l  lc_bpf,%a4
        move.l  lc_roff,%a5
30:     cmp.l   %d4,%d3
        bgt     40f
        cmp.l   #0,%a3
        bne     31f
        move.l  %d3,%d0                 | a new run
        bsr     lc_ptr
        move.l  %a0,%a2
        move.l  %d1,%a3
        cmp.l   #0,%a2
        bne     31f
        clr.l   lc_hp                   | not readable: a gap
        sub.l   %a3,%a3
        addq.l  #1,%d3
        bra     30b
31:     move.l  %a2,%a0
        bsr     lc_s16
        move.l  %d0,%d5                 | left
        move.l  %a2,%a0
        add.l   %a5,%a0
        bsr     lc_s16
        add.l   %d0,%d5                 | + right: the sum
        add.l   %a4,%a2
        subq.l  #1,%a3
        tst.l   lc_hp
        beq     33f
        move.l  lc_prev,%d0
        eor.l   %d5,%d0
        bpl     33f                     | same sign
        move.l  %d3,%d0                 | a crossing at i: |i - tap|
        sub.l   %d2,%d0
        bpl     32f
        neg.l   %d0
32:     cmp.l   %d7,%d0
        bge     37f
        move.l  %d0,%d7                 | the nearest so far
        move.l  %d3,%d6
        cmp.l   %d2,%d3
        bge     40f                     | at or past the tap: no later crossing is nearer
        bra     33f
37:     cmp.l   %d2,%d3                 | past the tap and no nearer than one before it:
        bgt     40f                     | the nearest is certain
33:     move.l  %d5,%d0                 | |sum|: the quietest?
        bpl     34f
        neg.l   %d0
34:     cmp.l   lc_qv,%d0
        bge     35f
        move.l  %d0,lc_qv
        move.l  %d3,lc_qf
35:     move.l  %d5,lc_prev
        moveq   #1,%d0
        move.l  %d0,lc_hp
        addq.l  #1,%d3
        bra     30b
40:     tst.l   %d6
        bpl     43f
        move.l  lc_w,%d0                | none in 8 ms: once more in 23 ms
        cmp.l   #SNAP_W,%d0
        beq     41f
        move.l  #SNAP_W,%d0
        move.l  %d0,lc_w
        bra     15b
43:     tst.l   %d6
        bmi     41f
        move.l  %d6,%d2                 | the nearest crossing
        bra     42f
41:     move.l  lc_qf,%d0
        bmi     42f
        move.l  %d0,%d2                 | else the quietest frame
42:     movem.l (%sp),%d3-%d7/%a2-%a5
        lea     36(%sp),%sp
99:
lc_snapdone:                            | (the gate's cost check times lc_snapfix to here)
        rts

| SCALE (MKI) / PAGE (MKII), code 0x1b: ZERO SNAP on/off. Not FUNC + YES:
| a FUNC record with a sub-map of LAZY CHOP's left the trig keys unreachable
| on 8thmyth's MKI after one FUNC + YES (F7), and the port did not show it.
| [MIDI] (code 0x35) while LAZY CHOP is open: LAZY CHOP's layer holds the
| key, so stock's (the MIDI tracks) cannot close the editor and cancel the
| chop. If SRC3 KEY (modules/src3-key) has taken [MIDI]'s press in the MKI
| key table, its handler runs (SRC3 record start / stop; in LIVE CHOP, TRIG
| 1 then joins that take at the head and YES stops it); else nothing.
lc_midi:
        tst.l   (MKII_FLAG).l           | MKII: [REC3] is its own key; [MIDI] nothing here
        bne     9f
        move.l  (MIDI_PRESS).l,%a0
        cmp.l   #STOCK_MIDI,%a0
        beq     9f
        jmp     (%a0)
9:      rts
        .equ    MIDI_PRESS, 0x400c015a      | [MIDI]'s press long, the MKI key table
        .equ    MKII_FLAG,  0x46c8d18c      | 1 on an MKII
        .equ    STOCK_MIDI, 0x40055678

| d0 <- where slice 1 and the take LAZY CHOP plays start: the trim start, but
| not before frame MIN_START (unless the trim ends by then) while the track
| time-stretches. The DSP's timestretch (TSTR AUTO, NORM, BEAT) stalls when a voice keeps restarting within about 300 frames of
| the sample's frame 0: on 8thmyth's MKI (H2, 14 Nov 2026) slice 1 at 0
| went silent after repeated SLICES-mode presses, and LAZY CHOP's TRIG 1 then
| played nothing (no cut could land); at 308, 379 and 564 it never failed.
| Stock CREATE SLICE GRID slices do the same. OFF and VARI do not stretch, so
| there slice 1 stays at the trim start (8thmyth, H4). MIN_START 384 ~ 8.7 ms.
| a0 = the record. Clobbers d0 only.
lc_s0:
        move.l  REC_TRIM_S(%a0),%d0
        cmp.l   #MIN_START,%d0
        bge     9f
        bsr     lc_stretch
        tst.l   %d0
        beq     8f
        move.l  #MIN_START,%d0
        cmp.l   REC_TRIM_E(%a0),%d0
        blt     9f
8:      move.l  REC_TRIM_S(%a0),%d0     | no stretch, or a take shorter than that
9:      rts

| d0 <- 1 if lc_track's SETUP TSTR (the live lane 0x80000510 + 48t, byte 28)
| is AUTO, NORM or BEAT, else 0 (OFF; VARISPEED's VARI). AUTO counts even when
| the sample's own TSMODE (record +0x110, stock 0x40007d7c) would not stretch:
| harmless there, and 8thmyth's AUTO takes stalled. Clobbers d0 only.
lc_stretch:
        lea     -8(%sp),%sp
        movem.l %d1/%a1,(%sp)
        move.l  lc_track,%d1
        move.l  %d1,%d0
        lsl.l   #5,%d0
        lsl.l   #4,%d1
        add.l   %d0,%d1                 | 48t
        add.l   #LANE_TSTR,%d1
        move.l  %d1,%a1
        moveq   #0,%d0
        move.b  (%a1),%d0
        subq.l  #1,%d0                  | 1 AUTO, 2 NORM, 3 BEAT stretch (AUTO counted
        cmp.l   #2,%d0                  | whatever the sample's TSMODE: 8thmyth, H4)
        bhi     2f
        moveq   #1,%d0
        bra     3f
2:      moveq   #0,%d0
3:      movem.l (%sp),%d1/%a1
        lea     8(%sp),%sp
        rts
        .equ    LANE_TSTR,  0x80000510+28

| d0 <- the recorder (0-7) whose buffer lc_rec is, or -1 (arena ids 128-135)
lc_rectrk:
        move.l  lc_rec,%d0
        sub.l   #FLEX_BASE,%d0
        blt     8f
        move.l  #1096,%d1
        divu.l  %d1,%d0
        sub.l   #128,%d0
        blt     8f
        cmp.l   #8,%d0
        bge     8f
        rts
8:      moveq   #-1,%d0
        rts

| d0 <- the REC key bits recorder d0's RECORDING SETUP asks for: INAB set
| 0x1000, INCD set 0x2000, SRC3 set 0x4000; 0 = every input off. Clobbers d1/a0.
lc_inbits:
        move.l  %d2,-(%sp)
        move.l  %d0,%d2
        moveq   #0,%d0
        move.b  (CUR_PARTB).l,%d0
        move.l  #0x18b2,%d1
        mulu.l  %d1,%d0
        add.l   #0x8ed80+PART_RSET,%d0
        add.l   (BANK_BLOB).l,%d0
        move.l  %d2,%d1
        lsl.l   #2,%d1                  | 4t
        add.l   %d2,%d2
        add.l   %d1,%d2
        add.l   %d2,%d2                 | 12t (d2 = 2(4t + 2t) = 12t)
        add.l   %d2,%d0
        move.l  %d0,%a0
        moveq   #0,%d0
        tst.b   (%a0)
        beq     1f
        or.l    #0x1000,%d0
1:      tst.b   1(%a0)
        beq     2f
        or.l    #0x2000,%d0
2:      tst.b   4(%a0)
        beq     3f
        or.l    #0x4000,%d0
3:      move.l  (%sp)+,%d2
        rts

| silent chop: lc_track's mute bit on while LAZY CHOP plays it (the voice
| runs, so the playhead and the cuts are as in STUDIO); lc_unmute puts it
| back only if LAZY CHOP set it. Clobber d0-d1/a0.
lc_mute:
        moveq   #1,%d1
        move.l  lc_track,%d0
        lsl.l   %d0,%d1
        lea     (MUTE_BYTE).l,%a0
        moveq   #0,%d0
        move.b  (%a0),%d0
        and.l   %d1,%d0
        bne     9f                      | muted already: leave it as it is
        move.b  (%a0),%d0
        or.l    %d1,%d0
        move.b  %d0,(%a0)
        move.l  %d1,lc_mset
9:      rts
lc_unmute:
        move.l  lc_mset,%d1
        beq     9f
        clr.l   lc_mset
        lea     (MUTE_BYTE).l,%a0
        moveq   #0,%d0
        move.b  (%a0),%d0
        not.l   %d1
        and.l   %d1,%d0
        move.b  %d0,(%a0)
9:      rts

| d0 <- non-zero (Z clear) while recorder d0 records (its voice byte 1). Clobbers d1/a0.
lc_recing:
        move.l  %d0,%d1
        move.l  %d2,-(%sp)
        move.l  #VSTRIDE,%d2
        mulu.l  %d2,%d1                 | (no mulu.l #imm on ColdFire)
        move.l  (%sp)+,%d2
        add.l   #VOICES+1,%d1
        move.l  %d1,%a0
        moveq   #0,%d0
        move.b  (%a0),%d0
        rts

| d0 <- non-zero (Z clear) while the LIVE take LAZY CHOP started or joined
| records, or is still to start (its start waits for QREC): d0 = 2 then.
| Clobbers d1/a0.
lc_lrun:
        move.l  lc_ltk,%d0
        beq     9f
        subq.l  #1,%d0
        bsr     lc_recing
        beq     1f
        clr.l   lc_lpend                | it records: the start has landed
        moveq   #1,%d0
        bra     9f
1:      move.l  lc_lpend,%d0            | not yet recording: pending (2) or over (0)
        beq     9f
        moveq   #2,%d0
9:      tst.l   %d0
        rts

| stop the LIVE take (recording or still to start). Clobbers d0-d1/a0-a1.
lc_lstop:
        move.l  lc_ltk,%d0
        beq     9f
        subq.l  #1,%d0
        clr.l   lc_lpend
        move.l  %d0,%d1                 | at once, whatever QREC: the immediate mailbox
        lsl.l   #2,%d1                  | (0x46c7e9fa + 4t, which the frame interrupt's
        add.l   #REC_NOW,%d1            | dispatcher acts on), not the quantized post
        move.l  %d1,%a0
        move.l  #REC_HALT,(%a0)
        pea     1.w                     | and the stop posted too: a start still waiting for
        pea     REC_HALT.w              | QREC is replaced by it
        move.l  %d0,-(%sp)
        jsr     (F_RECPOST).l
        lea     12(%sp),%sp
9:      rts

| [CUE] (code 0x2a): LIVE CHOP / STUDIO CHOP, kept (the setting). The take
| in progress keeps the mode it began with; the next TRIG 1 takes the new one.
| lc_live is read again after put_live: brain_post_settings clobbers d0 (H5/H6
| indexed the popup table with it and toasted a stray pointer: 8thmyth's
| unit glitched on [CUE], 14 Nov 2026; the three-way cycle was dropped).
lc_livetog:
        move.l  lc_live,%d0
        eor.l   #1,%d0
        move.l  %d0,lc_live
        put_live %d0
        lea     msg_studio,%a0
        tst.l   lc_live
        beq     1f
        lea     msg_live,%a0
1:      bra     lc_toast

lc_snaptog:
        move.l  lc_snap,%d0
        eor.l   #1,%d0
        move.l  %d0,lc_snap
        put_snap %d0                    | kept: BRAIN writes it to the card
        move.l  lc_snap,%d0
        lea     msg_snapoff,%a0
        beq     1f
        lea     msg_snapon,%a0
1:      bra     lc_toast

| play frames d0..d1 of the take at its own speed: entry 0 is set to them
| and, for the moment, the track's live SLIC is ON and STRT 0, so the voice
| plays entry 0 as a slice. The trim is not touched (with SLIC off, a trim
| set to a slice made timestretch stretch it to the sample's length: G1 on
| 8thmyth's MKI). The live lane (0x80000810 + 72t: STRT +1, SLIC +0x21)
| is what the engine reads at the trigger (the Part and its copies are not
| written); lc_unaud puts both bytes and entry 0 back. Clobbers d0-d1/a0-a1.
        .equ    LIVE_LANE,  0x80000810
        .equ    LIVE_STRT,  1
        .equ    LIVE_SLIC,  0x21
lc_range:
        move.l  %d2,-(%sp)
        move.l  lc_rec,%a0
        move.w  %sr,%d2
        move.w  #0x2700,%sr
        move.l  %d0,REC_SLICES(%a0)
        move.l  %d1,REC_SLICES+4(%a0)
        move.l  lc_track,%d0            | the live lane of the track
        moveq   #72,%d1
        mulu.l  %d1,%d0
        add.l   #LIVE_LANE,%d0
        move.l  %d0,%a1
        tst.l   lc_tmod
        bne     1f
        moveq   #0,%d0
        move.b  LIVE_SLIC(%a1),%d0
        move.l  %d0,lc_slsave
        move.b  LIVE_STRT(%a1),%d0
        move.l  %d0,lc_stsave
        moveq   #1,%d0
        move.l  %d0,lc_tmod
1:      move.b  #1,LIVE_SLIC(%a1)
        clr.b   LIVE_STRT(%a1)
        move.w  %d2,%sr
        move.l  (%sp)+,%d2
        moveq   #CMD_PLAY,%d0
        bra     lc_cmd                  | tail call

| entry 0 back to the whole take and the live SLIC and STRT back (after
| lc_range). Clobbers d0/a0.
lc_unaud:
        tst.l   lc_tmod
        beq     9f
        move.l  %d1,-(%sp)
        move.l  lc_rec,%a0
        move.w  %sr,%d0
        move.w  #0x2700,%sr
        move.l  %d0,-(%sp)              | (lc_s0 clobbers d0: the SR word kept meanwhile)
        bsr     lc_s0
        move.l  %d0,%d1
        move.l  (%sp)+,%d0
        move.l  %d1,REC_SLICES(%a0)
        move.l  REC_TRIM_E(%a0),%d1
        move.l  %d1,REC_SLICES+4(%a0)
        move.l  %d0,-(%sp)
        move.l  lc_track,%d0
        moveq   #72,%d1
        mulu.l  %d1,%d0
        add.l   #LIVE_LANE,%d0
        move.l  %d0,%a0
        move.l  lc_slsave,%d1
        move.b  %d1,LIVE_SLIC(%a0)
        move.l  lc_stsave,%d1
        move.b  %d1,LIVE_STRT(%a0)
        move.l  (%sp)+,%d0
        clr.l   lc_tmod
        move.w  %d0,%sr
        move.l  (%sp)+,%d1
9:      rts

| a trig key's release after a hold of HOLD_TICKS or more:
|   the last slice's key: that slice goes;
|   the green TRIG 1 at the start of pages 2-4: back a page, the previous
|   page's last slice goes (and the cut or resume the press made, if any).
| Slice 1 stays.
lc_trigup:
        move.l  4(%sp),%d0
        and.l   #0xff,%d0
        move.l  lc_hkey,%d1
        clr.l   lc_hkey
        subq.l  #1,%d1
        cmp.l   %d0,%d1
        bne     9f
        move.l  lc_state,%d0
        cmp.l   #ST_CHOP,%d0
        bne     9f
        move.l  lc_ticks,%d0
        sub.l   lc_ptime,%d0
        cmp.l   #HOLD_TICKS,%d0
        blt     9f
        move.l  %d2,-(%sp)
        move.l  %d3,-(%sp)
        move.l  lc_hgreen,%d3           | slices before the green press, or 0
        bne     1f
        move.l  lc_next,%d3             | the last slice's key: slice n
1:      move.l  %d3,%d2                 | d2: the slice reported; keep d3 - 1 slices
        subq.l  #1,%d3
        bsr     lc_unaud
2:      move.l  lc_next,%d0
        cmp.l   %d3,%d0
        ble     3f
        cmp.l   #2,%d0
        blt     3f
        bsr     lc_undo1
        bra     2b
3:      bsr     lc_sync
        bsr     lc_refresh
        move.l  %d2,-(%sp)
        pea     fmt_undo
        pea     lc_buf
        jsr     (F_SPRINTF).l
        lea     12(%sp),%sp
        lea     lc_buf,%a0
        bsr     lc_toast
        move.l  (%sp)+,%d3
        move.l  (%sp)+,%d2
9:      rts

| the last slice goes: slice n-1 runs on to the end again (interrupts
| masked for the three longs). Clobbers d0-d1/a0-a1.
lc_undo1:
        move.l  lc_next,%d0
        subq.l  #1,%d0
        bsr     lc_slice                | a1 = &entry[n-1]
        move.l  lc_rec,%a0
        move.w  %sr,%d1
        move.w  #0x2700,%sr
        move.l  REC_TRIM_E(%a0),4(%a1)
        move.l  lc_next,%d0
        move.l  %d0,REC_COUNT(%a0)      | entry 0 + slices 1..n-1
        subq.l  #1,%d0
        move.l  %d0,lc_next
        move.w  %d1,%sr
        rts

| the slot LAZY CHOP edits goes into the track's pending lock block as its
| sample lock (byte 31 of 0x46c7dfda + 32t, which the frame path copies at
| the trigger and refills with -1, as MIDI chromatic play does with PTCH):
| the trigger plays that slot even when the track's own sample is another
| (the editor opened from a trig's sample lock). FLEX 0-135 (recorders
| 128-135), STATIC 0-127, as the step records hold them. Clobbers d0-d1/a0.
        .equ    PEND_LOCKS, 0x46c7dfda
lc_lockplay:
        move.l  lc_rec,%d0
        sub.l   #FLEX_BASE,%d0
        blt     9f
        move.l  #1096,%d1
        divu.l  %d1,%d0
        cmp.l   #ARENA_N,%d0
        blt     1f
        move.l  lc_rec,%d0
        sub.l   #STATIC_BASE,%d0
        blt     9f
        divu.l  %d1,%d0
        cmp.l   #128,%d0
        bge     9f
1:      move.l  lc_track,%d1
        lsl.l   #5,%d1
        add.l   #PEND_LOCKS+31,%d1
        move.l  %d1,%a0
        move.b  %d0,(%a0)
9:      rts

| toast a0 (a NUL-terminated string)
lc_toast:
        pea     0x30.w
        move.l  %a0,-(%sp)
        jsr     (F_TOAST).l
        addq.l  #8,%sp
        rts

lc_refresh:
        jsr     (F_UPD1).l
        jsr     (F_UPD2).l
        jsr     (F_REDRAW).l
        rts

| (re)register the layer with key table a0
lc_layer:
        move.l  %a0,-(%sp)
        bsr     lc_unlayer
        move.l  (%sp)+,%a0
        move.l  %a0,lc_map+4
        pea     lc_map
        jsr     (F_REG).l
        addq.l  #4,%sp
        moveq   #1,%d0
        move.l  %d0,lc_registered
        rts

lc_unlayer:
        tst.l   lc_registered
        beq     1f
        pea     lc_map
        jsr     (F_UNREG).l
        addq.l  #4,%sp
        clr.l   lc_registered
1:      rts

| put back the slices saved by lc_open (interrupts masked)
lc_restore:
        move.l  %d2,-(%sp)
        move.l  lc_rec,%a1
        lea     REC_SLICES(%a1),%a1
        lea     lc_backup,%a0
        move.l  #BACKUP_LONGS,%d0
        move.w  %sr,%d2
        move.w  #0x2700,%sr
1:      move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne     1b
        move.w  %d2,%sr
        move.l  (%sp)+,%d2
        rts

| d0 <- the wanted on-bits for ids 0-31 as a long, byte 0 = ids 0-7 in
| the high byte (the state array's order): on this page keys 0..k-1 red
| (id 2i, the slices made), key k green (id 2k+1, the next to tap), the
| rest off; k = lc_next % 16
lc_want:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        move.l  lc_next,%d3
        and.l   #15,%d3                 | k
        moveq   #0,%d0                  | the bits
        moveq   #0,%d1                  | key
1:      cmp.l   %d3,%d1
        bgt     3f                      | after the next key: off
        move.l  %d1,%d2
        add.l   %d2,%d2                 | id = 2*key: red
        cmp.l   %d3,%d1
        blt     2f
        addq.l  #1,%d2                  | the next key: green
2:      move.l  %d2,%d4
        and.l   #7,%d4                  | bit = 24 - 8*(id>>3) + (id&7)
        lsr.l   #3,%d2
        lsl.l   #3,%d2
        neg.l   %d2
        add.l   #24,%d2
        add.l   %d4,%d2
        moveq   #1,%d4
        lsl.l   %d2,%d4
        or.l    %d4,%d0
3:      addq.l  #1,%d1
        cmp.l   #16,%d1
        blt     1b
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| d0 <- what ids 0-31 show now (state XOR blink phase), same layout
lc_shown:                               | LED_STATE is only word-aligned: two word reads
        moveq   #0,%d0
        move.w  (LED_STATE).l,%d0
        swap    %d0
        move.w  (LED_STATE+2).l,%d0
        move.l  (LED_BLINK).l,%d1
        eor.l   %d1,%d0
        rts

| one id to its wanted state: blink bit off, full brightness, on for good
| or off. d0 = id, d1 = on (non-zero) or off. Clobbers d0-d1/a0-a1.
lc_led1:
        move.l  %d2,-(%sp)
        move.l  %d3,-(%sp)
        move.l  %d0,%d2
        move.l  %d1,%d3
        move.l  %d2,-(%sp)
        jsr     (F_UNBLINK).l
        addq.l  #4,%sp
        pea     15.w
        move.l  %d2,-(%sp)
        jsr     (F_LEVEL).l
        addq.l  #8,%sp
        tst.l   %d3
        beq     1f
        pea     LED_LONG
        bra     2f
1:      clr.l   -(%sp)                  | set_led(id, 0): the countdown and the bit cleared
2:      move.l  %d2,-(%sp)
        jsr     (F_LEDON).l
        addq.l  #8,%sp
        move.l  (%sp)+,%d3
        move.l  (%sp)+,%d2
        rts

| d0 <- id's bit number in the long (24 - 8*(id>>3) + (id&7)); d0 = id in
lc_bit:
        move.l  %d0,%d1
        and.l   #7,%d1
        lsr.l   #3,%d0
        lsl.l   #3,%d0
        neg.l   %d0
        add.l   #24,%d0
        add.l   %d1,%d0
        rts

| every id 0-31 set to lc_want (when LAZY CHOP opens)
lc_leds:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        bsr     lc_want
        move.l  %d0,%d4
        moveq   #0,%d2
1:      move.l  %d2,%d0
        bsr     lc_bit
        move.l  %d4,%d1
        lsr.l   %d0,%d1
        and.l   #1,%d1
        move.l  %d2,%d0
        bsr     lc_led1
        addq.l  #1,%d2
        cmp.l   #32,%d2
        blt     1b
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

| only the ids that differ from lc_want (state XOR blink) are set again:
| a tap changes two, a stray flash one; nothing is sent when all match
lc_sync:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        bsr     lc_want
        move.l  %d0,%d4                 | wanted
        bsr     lc_shown
        move.l  %d0,%d3
        eor.l   %d4,%d3                 | the ids that differ
        beq     9f
        moveq   #0,%d2
1:      move.l  %d2,%d0
        bsr     lc_bit
        move.l  %d3,%d1
        lsr.l   %d0,%d1
        and.l   #1,%d1
        beq     2f
        move.l  %d4,%d1
        lsr.l   %d0,%d1
        and.l   #1,%d1
        move.l  %d2,%d0
        bsr     lc_led1
2:      addq.l  #1,%d2
        cmp.l   #32,%d2
        blt     1b
9:      movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        rts

lc_ledsoff:
        move.l  %d2,-(%sp)
        moveq   #0,%d2
1:      clr.l   -(%sp)                  | set_led(id, 0): the countdown and the bit cleared
        move.l  %d2,-(%sp)
        jsr     (F_LEDON).l
        addq.l  #8,%sp
        addq.l  #1,%d2
        cmp.l   #32,%d2
        blt     1b
        move.l  (%sp)+,%d2
        rts

| stock's trig-LED pass, through its slot (0x400c0936): stock's own when
| LAZY CHOP is closed; else stock's, then ids 0-31 put back to LAZY CHOP's
| (only when they differ, so the panel link sees no extra traffic)
| the LED task's tick (0x40055956 loads it into a2): stock's countdowns,
| then, while LAZY CHOP is open, ids 0-31 checked against lc_want and set
| again if a stock flash (a short countdown) or a pass changed them
lc_tick:
        jsr     (F_LEDTICK).l
        tst.l   lc_state
        beq     9f
        addq.l  #1,lc_ticks             | LAZY CHOP's clock for the undo hold
        move.l  lc_div,%d0
        subq.l  #1,%d0
        bgt     1f
        moveq   #TICK_DIV,%d0
        move.l  %d0,lc_div
        bra     lc_sync                 | tail call
1:      move.l  %d0,lc_div
9:      rts

| the frame path's read of a track's pending command (0x4000b54a: d3 =
| track, a0 = 0x46c80354; next a beq on bit 0). While chopping, a play
| the sequencer posts for the chopped track is dropped, so the take plays
| on from TRIG 1: a step trig would restart it, or with SLIC on play only
| slice 1, and no tap past the first slice could land (8thmyth's MKI, F5).
| LAZY CHOP's own play (lc_own) goes through. Clobbers d0 only; returns
| the flags of btst #0.
lc_cmdgate:
        move.l  (%a0,%d3.l*4),%d0
        btst    #0,%d0
        beq     9f
        move.l  %d1,-(%sp)
        move.l  lc_state,%d1
        cmp.l   #ST_CHOP,%d1
        bne     8f
        cmp.l   lc_track,%d3
        bne     8f
        tst.l   lc_own
        beq     5f
        clr.l   lc_own                  | LAZY CHOP's own play
        bra     8f
5:      clr.l   (%a0,%d3.l*4)           | the sequencer's: dropped
        moveq   #0,%d0
8:      move.l  (%sp)+,%d1
9:      btst    #0,%d0
        rts

lc_ledpass:
        tst.l   lc_state
        bne     1f
        jmp     (F_TRIGLEDS).l
1:      bsr     lc_sync                 | LAZY CHOP open: stock's pass is skipped (it
        moveq   #0,%d0                  | draws only the trig LEDs: no running light,
        rts                             | no blink or level changes to fight)

| set_led(id, ticks) for stock's step-LED painter (0x400341xx: its five
| lea 0x40013784 operands point here). While LAZY CHOP is open the trig
| LEDs (ids 0-31) are LAZY CHOP's: a p-locked step's 3-tick flashes from
| that painter were turned off again by lc_tick a tick later, and the
| steps flickered (8thmyth, H5). Dropped then; every other id, and every call
| with LAZY CHOP closed, goes to stock's.
lc_ledflt:
        tst.l   lc_state
        beq     1f
        move.l  4(%sp),%d0
        cmp.l   #32,%d0
        bcc     1f
        rts
1:      jmp     (F_LEDON).l


| leave the mode (no data change)
lc_end:
        bsr     lc_unaud
        bsr     lc_unmute
        clr.l   lc_ltk
        clr.l   lc_lpend
        clr.l   lc_aud
        clr.l   lc_hkey
        bsr     lc_unlayer
        bsr     lc_ledsoff
        clr.l   lc_state
        rts

| ---- the slice menu row ------------------------------------------------

lc_open:
        tst.l   lc_state
        bne     9f
        get_live %d0                    | LIVE CHOP as set (BRAIN SETTINGS or the last [CUE])
        move.l  %d0,lc_live
        clr.l   lc_ltk
        cmp.l   #1,%d0                  | LIVE only (STUDIO needs a take to chop)
        bne     2f
        jsr     (F_REC).l               | LIVE on a recorder buffer: it arms empty or while
        tst.l   %d0                     | recording too (it records; nothing plays ahead
        beq     2f                      | of the head), where stock's slice editing refuses
        move.l  %d0,lc_rec
        bsr     lc_rectrk
        tst.l   %d0
        bpl     3f
2:      jsr     (F_BUSY).l
        tst.l   %d0
        bne     9f
        pea     -1.w
        jsr     (F_HAS).l
        addq.l  #4,%sp
        tst.l   %d0
        beq     9f
3:      jsr     (F_REC).l
        tst.l   %d0
        beq     9f
        move.l  %d0,lc_rec
        move.l  %d0,%a0
        lea     REC_SLICES(%a0),%a0
        lea     lc_backup,%a1
        move.l  #BACKUP_LONGS,%d0
1:      move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne     1b
        moveq   #0,%d0
        move.b  CUR_TRACK,%d0
        move.l  %d0,lc_track
        clr.l   lc_next
        moveq   #ST_ARMED,%d0
        move.l  %d0,lc_state
        lea     lc_keys_chop,%a0
        bsr     lc_layer
        bsr     lc_leds
        get_snap %d0                    | ZERO SNAP as set (BRAIN SETTINGS or the last [SCALE])
        move.l  %d0,lc_snap
        move.l  lc_live,%d1             | the popup: mode (x 8) and ZERO SNAP (+ 4)
        lsl.l   #3,%d1
        tst.l   %d0
        beq     2f
        addq.l  #4,%d1
2:      lea     msg_arms,%a0
        move.l  (%a0,%d1.l),%a0
        bsr     lc_toast
9:      rts

| ---- keys --------------------------------------------------------------

| lc_trig(code, edge)
lc_trig:
        move.l  %d2,-(%sp)
        move.l  8(%sp),%d0
        and.l   #0xff,%d0
        move.l  lc_state,%d1
        cmp.l   #ST_ARMED,%d1
        beq     .Larmed
        cmp.l   #ST_CHOP,%d1
        beq     .Lchop
.Lret:  move.l  (%sp)+,%d2
        rts

.Larmed:                                | TRIG 1 starts the take
        tst.l   %d0
        bne     .Lret
        tst.l   lc_live
        beq     .Lstudio
        bsr     lc_rectrk
        tst.l   %d0
        bpl     .Llive
.Lsilent:                               | LIVE with nothing to record (a sample slot, or every
        bsr     lc_mute                 | input off): the take plays muted, the cuts as in STUDIO
        lea     msg_silent,%a0
        bsr     lc_toast
.Lstudio:
        move.l  lc_rec,%a0
        moveq   #0,%d0
        bsr     lc_slice                | a1 = &slice[0]
        move.w  %sr,%d2
        move.w  #0x2700,%sr
        moveq   #2,%d0                  | entry 0 the whole take (what plays), entry 1 slice 1
        move.l  %d0,REC_COUNT(%a0)
        bsr     lc_s0                   | both from max(trim start, MIN_START)
        move.l  %d0,(%a1)
        move.l  REC_TRIM_E(%a0),4(%a1)
        move.l  %d0,12(%a1)
        moveq   #-1,%d0
        move.l  %d0,8(%a1)
        move.l  REC_TRIM_E(%a0),16(%a1)
        move.l  %d0,20(%a1)
        move.w  %d2,%sr
        moveq   #1,%d0
        move.l  %d0,lc_next
        moveq   #CMD_PLAY,%d0
        bsr     lc_cmd
        moveq   #ST_CHOP,%d0
        move.l  %d0,lc_state
        bsr     lc_sync
        bsr     lc_refresh
        bra     .Lret

.Llive:                                 | LIVE: the recorder starts (or a take running is joined);
        move.l  %d0,%d2                 | slice 1 starts at the record head; nothing plays
        addq.l  #1,%d0
        move.l  %d0,lc_ltk
        move.l  %d2,%d0
        bsr     lc_recing
        bne     1f
        move.l  %d2,%d0                 | idle: start it with its RECORDING SETUP's inputs
        bsr     lc_inbits
        tst.l   %d0
        bne     3f
        clr.l   lc_ltk                  | every input off: nothing to record, silent chop
        moveq   #0,%d0
        bra     .Lsilent
3:      add.l   #0x8000,%d0
        or.l    #0x10,%d0               | (keys + 0x8000) | 0x10, as stock's REC keys build it
        pea     1.w                     | (the recorder honours QREC: the start may wait for
        move.l  %d0,-(%sp)              | the next step or loop; the take's frame 0 is then)
        move.l  %d2,-(%sp)
        jsr     (F_RECPOST).l
        lea     12(%sp),%sp
        moveq   #1,%d0
        move.l  %d0,lc_lpend
        moveq   #0,%d2                  | the take starts at frame 0 (slice 1 at MIN_START, below)
        bra     2f
1:      move.l  %d2,%d0                 | recording: the head now
        lsl.l   #2,%d0
        add.l   #REC_POS,%d0
        move.l  %d0,%a0
        move.l  (%a0),%d2
2:      move.l  lc_rec,%a0
        cmp.l   #MIN_START,%d2          | slice 1 not before MIN_START while stretching (lc_s0)
        bge     4f
        bsr     lc_stretch
        tst.l   %d0
        beq     4f
        move.l  #MIN_START,%d2
4:      move.l  lc_rec,%a0
        moveq   #0,%d0
        bsr     lc_slice                | a1 = &slice[0]
        bsr     lc_s0
        move.l  %d0,-(%sp)
        move.w  %sr,%d1
        move.w  #0x2700,%sr
        moveq   #2,%d0
        move.l  %d0,REC_COUNT(%a0)
        move.l  (%sp)+,(%a1)
        move.l  REC_TRIM_E(%a0),4(%a1)
        moveq   #-1,%d0
        move.l  %d0,8(%a1)
        move.l  %d2,12(%a1)
        move.l  REC_TRIM_E(%a0),16(%a1)
        move.l  %d0,20(%a1)
        move.w  %d1,%sr
        move.l  %d2,lc_last
        moveq   #1,%d0
        move.l  %d0,lc_next
        moveq   #ST_CHOP,%d0
        move.l  %d0,lc_state
        bsr     lc_sync
        bsr     lc_refresh
        bra     .Lret

.Lchop:                                 | the green key cuts (or resumes); a red one auditions
        move.l  lc_next,%d1
        and.l   #15,%d1
        cmp.l   %d1,%d0
        beq     .Lgreen
        move.l  lc_next,%d1             | the last slice's key (TRIG 16 just after a page turn)
        subq.l  #1,%d1
        and.l   #15,%d1
        cmp.l   %d1,%d0
        bne     1f
        addq.l  #1,%d0                  | held: undo on release after HOLD_TICKS
        move.l  %d0,lc_hkey
        clr.l   lc_hgreen
        move.l  lc_ticks,%d0
        move.l  %d0,lc_ptime
        move.l  lc_next,%d1             | it auditions the last slice
        bra     .Laud
1:      move.l  lc_next,%d1
        and.l   #15,%d1
        cmp.l   %d1,%d0
        bge     .Lret                   | an unlit key: nothing
        move.l  lc_next,%d1             | a red key: slice base + key + 1
        move.l  %d1,%d2
        and.l   #15,%d2
        sub.l   %d2,%d1
        add.l   %d0,%d1
        addq.l  #1,%d1
.Laud:  move.l  %d1,-(%sp)
        bsr     lc_lrun                 | a LIVE take: no audition (nothing plays out)
        beq     1f
        addq.l  #4,%sp
        bra     .Lret
1:      bsr     lc_unaud
        move.l  (%sp)+,%d0
        bsr     lc_slice                | a1 = &entry[slice]
        move.l  (%a1),%d0
        move.l  4(%a1),%d1
        bsr     lc_range                | play just that slice
        moveq   #1,%d0
        move.l  %d0,lc_aud              | the take is stopped: the green key resumes
        bra     .Lret

.Lgreen:
        clr.l   lc_hgreen
        tst.l   %d0                     | TRIG 1 at the start of pages 2-4: a hold undoes
        bne     1f                      | back across the page (lc_trigup)
        move.l  lc_next,%d1
        beq     1f
        move.l  %d1,%d2
        and.l   #15,%d2
        bne     1f
        move.l  %d1,lc_hgreen
        moveq   #1,%d1
        move.l  %d1,lc_hkey
        move.l  lc_ticks,%d1
        move.l  %d1,lc_ptime
1:      bsr     lc_lrun                 | a LIVE take: the cut at the record head
        beq     2f
        cmp.l   #2,%d0
        beq     .Lret                   | its start still waits for QREC: nothing recorded yet
        move.l  lc_ltk,%d0
        subq.l  #1,%d0
        lsl.l   #2,%d0
        add.l   #REC_POS,%d0
        move.l  %d0,%a0
        move.l  (%a0),%d2
        moveq   #1,%d0
        move.l  %d0,lc_behind
        bsr     lc_snapfix              | ZERO SNAP, behind the head only
        clr.l   lc_behind
        bra     .Lcut
2:      tst.l   lc_aud
        bne     .Lresume
        bsr     lc_unaud                | after a resume: entry 0 the whole take again before
                                        | the refresh sorts the table (the voice plays on: the
                                        | range ended at the trim end too)
        bsr     lc_voice
        tst.b   (%a0)
        beq     .Lresume                | the take has played out
        move.l  8(%a0),%d1
        cmp.l   lc_rec,%d1
        bne     .Lwrong
        move.l  68(%a0),%d2             | the playhead
        bsr     lc_snapfix              | ZERO SNAP, if on
.Lcut:  move.l  lc_next,%d0
        bsr     lc_slice                | a1 = &entry[next]: slice next, the open one
        move.l  (%a1),%d1
        cmp.l   %d1,%d2
        blt     .Lback                  | behind the last marker: the take looped or restarted
        add.l   #MIN_GAP,%d1
        cmp.l   %d1,%d2
        blt     .Lret                   | too close to the previous marker
        move.l  lc_rec,%a0
        move.l  REC_TRIM_E(%a0),%d1
        sub.l   #MIN_GAP,%d1
        cmp.l   %d1,%d2
        bge     .Lret                   | too close to the end
        move.w  %sr,%d1
        move.w  #0x2700,%sr
        move.l  %d2,4(%a1)              | the open slice ends here
        move.l  %d2,lc_last             | the next one starts here
        move.l  lc_next,%d0
        cmp.l   #MAX_SLICES-1,%d0
        bge     1f                      | slice 64: no entry 64; lc_finish adds it
        move.l  %d2,12(%a1)
        move.l  REC_TRIM_E(%a0),16(%a1)
        moveq   #-1,%d0
        move.l  %d0,20(%a1)
1:      move.l  lc_next,%d0
        addq.l  #1,%d0
        move.l  %d0,lc_next
        cmp.l   #MAX_SLICES,%d0
        bge     2f
        addq.l  #1,%d0
        move.l  %d0,REC_COUNT(%a0)      | entry 0 + the slices: the markers show
2:      move.w  %d1,%sr
        move.l  lc_next,%d0
        cmp.l   #MAX_SLICES,%d0
        bge     .Lfull
        bsr     lc_sync
        bsr     lc_refresh
        move.l  lc_next,%d0
        move.l  %d0,%d1
        and.l   #15,%d1
        bne     .Lret
        move.l  %d0,%d1                 | after TRIG 16: the page turns; say which
        add.l   #16,%d1                 | slices TRIG 1-16 now place (17-32, ...)
        move.l  %d1,-(%sp)
        addq.l  #1,%d0
        move.l  %d0,-(%sp)
        pea     fmt_page
        pea     lc_buf
        jsr     (F_SPRINTF).l
        lea     16(%sp),%sp
        lea     lc_buf,%a0
        bsr     lc_toast
        bra     .Lret
.Lfull: move.l  (%sp)+,%d2
        bra     lc_finish

.Lresume:                               | play on from the last marker; the next press cuts
        bsr     lc_unaud
        clr.l   lc_aud
        move.l  lc_next,%d0
        bsr     lc_slice                | the open slice
        move.l  (%a1),%d0
        move.l  lc_rec,%a0
        move.l  REC_TRIM_E(%a0),%d1
        bsr     lc_range
        bra     .Lret

.Lback:                                 | say so: YES keeps what is placed
        move.l  lc_next,-(%sp)
        pea     fmt_back
        pea     lc_buf
        jsr     (F_SPRINTF).l
        lea     12(%sp),%sp
        lea     lc_buf,%a0
        bsr     lc_toast
        bra     .Lret

.Lwrong:                                | the track plays another sample
        bsr     lc_unaud
        moveq   #CMD_STOP,%d0
        bsr     lc_cmd
        bsr     lc_restore
        bsr     lc_end
        bsr     lc_refresh
        lea     msg_wrong,%a0
        bsr     lc_toast
        bra     .Lret

| YES while chopping: write the slices
lc_yes:
        bsr     lc_lrun                 | LIVE: YES stops the take too, then writes the slices
        beq     1f
        bsr     lc_lstop
1:      bsr     lc_unaud
        move.l  lc_state,%d0
        cmp.l   #ST_CHOP,%d0
        beq     lc_finish
        bra     lc_end                  | armed, nothing played: just leave

lc_finish:
        bsr     lc_unaud
        move.l  %d2,-(%sp)
        moveq   #CMD_STOP,%d0
        bsr     lc_cmd
        move.l  lc_rec,%a0
        move.w  %sr,%d2
        move.w  #0x2700,%sr
        lea     REC_SLICES(%a0),%a1     | entries 1..min(n,63) down to 0..
        move.l  lc_next,%d0
        cmp.l   #MAX_SLICES-1,%d0
        ble     3f
        moveq   #MAX_SLICES-1,%d0
3:      move.l  %d0,%d1                 | longs: 3 per entry
        add.l   %d0,%d0
        add.l   %d1,%d0
4:      move.l  12(%a1),(%a1)+
        subq.l  #1,%d0
        bne     4b
        move.l  lc_next,%d0
        cmp.l   #MAX_SLICES,%d0
        blt     5f
        move.l  lc_last,(%a1)+          | slice 64: from the last tap to the trim end
        move.l  REC_TRIM_E(%a0),(%a1)+
        moveq   #-1,%d0
        move.l  %d0,(%a1)
5:      move.l  lc_next,%d0
        move.l  %d0,REC_COUNT(%a0)
        move.l  lc_next,-(%sp)
        pea     REC_SLICES(%a0)
        jsr     (F_SORT).l
        addq.l  #8,%sp
        move.w  %d2,%sr
        clr.l   SEL
        move.l  lc_next,-(%sp)
        pea     fmt_done
        pea     lc_buf
        jsr     (F_SPRINTF).l
        lea     12(%sp),%sp
        lea     lc_buf,%a0
        bsr     lc_toast
        bsr     lc_end
        bsr     lc_refresh
        jsr     (F_EDITED).l
        move.l  (%sp)+,%d2
        rts

| NO: put the old slices back and leave the mode
lc_no:
        bsr     lc_unaud
        move.l  lc_state,%d0
        cmp.l   #ST_CHOP,%d0
        bne     1f
        moveq   #CMD_STOP,%d0
        bsr     lc_cmd
1:      bsr     lc_restore
        bsr     lc_end
        bsr     lc_refresh
        lea     msg_cancel,%a0
        bra     lc_toast

| ---- the SLICE page's leave: a jsr detour on its 0x4003146c(0x400ceb60) --
| Called with the stock argument on the stack; ends by jumping to stock's
| remove, which returns to the page's leave routine.
lc_leave:
        move.l  lc_state,%d0
        beq     2f
        bsr     lc_unaud                | (clobbers d0: the state is read again below; G3 compared
        move.l  lc_state,%d0            | lc_unaud's SR word and skipped the restore: stress seed 22)
        cmp.l   #ST_CHOP,%d0
        bne     1f
        moveq   #CMD_STOP,%d0           | left mid-chop: the old slices come back
        bsr     lc_cmd
        bsr     lc_restore
1:      bsr     lc_end
2:      jmp     (F_UNREG).l

| ---- data -----------------------------------------------------------------

        .macro  KREC code, press, release=0
        .byte   \code, 0
        .long   \press, \release, 0, 0, 0, 0
        .endm
        .macro  TRIGS
        KREC    0x00, lc_trig, lc_trigup
        KREC    0x01, lc_trig, lc_trigup
        KREC    0x02, lc_trig, lc_trigup
        KREC    0x03, lc_trig, lc_trigup
        KREC    0x04, lc_trig, lc_trigup
        KREC    0x05, lc_trig, lc_trigup
        KREC    0x06, lc_trig, lc_trigup
        KREC    0x07, lc_trig, lc_trigup
        KREC    0x08, lc_trig, lc_trigup
        KREC    0x09, lc_trig, lc_trigup
        KREC    0x0a, lc_trig, lc_trigup
        KREC    0x0b, lc_trig, lc_trigup
        KREC    0x0c, lc_trig, lc_trigup
        KREC    0x0d, lc_trig, lc_trigup
        KREC    0x0e, lc_trig, lc_trigup
        KREC    0x0f, lc_trig, lc_trigup
        .endm

        .data
        .global lc_label, lc_state, lc_next, lc_rec
        .balign 4
lc_map:         .long   0, lc_keys_chop, 0, 0, 0        | {next, keys, encoders (none: stock's), 0, marker}
lc_state:       .long   0
lc_registered:  .long   0
lc_rec:         .long   0
lc_track:       .long   0
lc_next:        .long   0
lc_div:         .long   0
lc_own:         .long   0
lc_last:        .long   0
lc_id:          .long   0
lc_src:         .long   0               | ZERO SNAP's source: 1 FLEX/recorder, 2 STATIC
lc_bpf:         .long   0
lc_roff:        .long   0
lc_tbase:       .long   0
lc_qv:          .long   0
lc_qf:          .long   0
lc_prev:        .long   0
lc_hp:          .long   0
lc_ticks:       .long   0
lc_ptime:       .long   0
lc_hkey:        .long   0               | key + 1 of a held last-slice key, 0 if none
lc_hgreen:      .long   0               | the slices before a page-start TRIG 1 press, or 0
        .global lc_aud
lc_aud:         .long   0               | an audition stopped the take
lc_tmod:        .long   0               | lc_range's entry 0 and live SLIC/STRT are in place
lc_slsave:      .long   0               | the live SLIC and STRT they replaced
lc_stsave:      .long   0
        .global lc_snap
lc_snap:        .long   0               | ZERO SNAP now (from the setting at each open)
        .global lc_live, lc_ltk
lc_live:        .long   0               | LIVE CHOP (1) or STUDIO CHOP (0), from the setting at each open
lc_ltk:         .long   0               | recorder + 1 of the LIVE take started or joined, 0 if none
lc_lpend:       .long   0               | its start is posted, not yet recording (QREC)
lc_mset:        .long   0               | the mute bit LAZY CHOP set for silent chop, 0 if none
lc_w:           .long   0               | lc_snapfix: the window now (SNAP_W1, then SNAP_W)
lc_behind:      .long   0               | lc_snapfix: search behind the tap only

lc_keys_chop:
        TRIGS
        KREC    0x31, lc_yes
        KREC    0x32, lc_no
        KREC    0x1b, lc_snaptog        | SCALE (MKI) / PAGE (MKII): ZERO SNAP on/off
        KREC    0x35, lc_midi           | MIDI: SRC3 KEY's if present (held: stock's cannot close the editor)
        KREC    0x2a, lc_livetog        | CUE: LIVE CHOP / STUDIO CHOP
        .byte   0xff, 0

lc_label:   .asciz  "LAZY CHOP"
msg_ast:    .asciz  "LAZY CHOP: STUDIO"
msg_asts:   .asciz  "LAZY CHOP: STUDIO SNAP"
msg_alv:    .asciz  "LAZY CHOP: LIVE"
msg_alvs:   .asciz  "LAZY CHOP: LIVE SNAP"
msg_live:   .asciz  "LIVE CHOP"
msg_studio: .asciz  "STUDIO CHOP"
msg_silent: .asciz  "SILENT CHOP"
        .balign 4
        .balign 4
msg_arms:   .long   msg_ast, msg_asts, msg_alv, msg_alvs
msg_wrong:  .asciz  "TRACK PLAYS ANOTHER SAMPLE"
msg_cancel: .asciz  "LAZY CHOP CANCELLED"
fmt_done:   .asciz  "%d SLICES"
fmt_page:   .asciz  "SLICES %d-%d"
fmt_back:   .asciz  "LOOPED: YES KEEPS %d"
msg_snapon: .asciz  "ZERO SNAP ON"
fmt_undo:   .asciz  "SLICE %d REMOVED"
msg_snapoff: .asciz "ZERO SNAP OFF"
        .balign 4
lc_buf:     .space  32

        .bss
        .balign 4
lc_backup:  .space  BACKUP_LONGS*4
