| CHORDS FACTORY -- the hand-written part of the unit: SCALES' scale and
| STORE's channel lookups, STORE's file calls, the atelier's input layer and
| the file buffers. generate.py appends this to the compiled chords.c +
| adapter.c. The page itself is opened, closed and ticked by PAGES
| (ch_page_shown / _open / _close / _tick, adapter.c).
        .text
        .include "remix.inc"            | HAVE_SCALES, CH_CLIENT (STORE's client id)
        .globl  ch_scale, ch_channel, ch_layer, ch_keyboard
        .globl  ch_file_path, ch_file_open, ch_file_read, ch_file_write, ch_file_close
        .globl  ch_file_crc, ch_file_refuse, ch_st_answer, ch_path, ch_path2, ch_fbuf, ch_fsaved

| CHORDS stores absolute pitches. A track whose native NOTE lane belongs
| to Harmony cannot record those as degrees. This is a musical constraint
| of these two clients; TRIG MODES does not interpret note formats.
        .globl ch_accepts_absolute
ch_accepts_absolute:
        .if HAVE_HARMONY
        move.l 4(%sp),%d0
        jsr mh_get
        tst.l %d0
        beq.s 1f
        moveq #0,%d0
        rts
1:
        .endif
        moveq #1,%d0
        rts

| int32_t ch_scale(unsigned t): SCALES' scale of MIDI track t as
| mask << 4 | tonic, or -1 (KEY OFF, or no SCALES in the remix). TURING's tm_scale.
ch_scale:
        .if     HAVE_SCALES
        move.l  4(%sp),%d0
        jsr     sc_track                | d0 = ID << 4 | tonic, -1 for KEY OFF
        tst.l   %d0
        bmi.s   9f
        move.l  %d0,-(%sp)
        lsr.l   #4,%d0
        jsr     sc_mask                 | d0 = the ID's mask, 0 for no such ID
        move.l  (%sp)+,%d1
        tst.l   %d0
        beq.s   8f
        lsl.l   #4,%d0
        andi.l  #15,%d1
        or.l    %d1,%d0
9:      rts
8:      moveq   #-1,%d0
        rts
        .else
        .if HAVE_MIDI_SCALES
        move.l 4(%sp),%d0
        jmp ms_track
        .else
        moveq   #-1,%d0
        rts
        .endif
        .endif

| int32_t ch_keyboard(unsigned t, unsigned first, unsigned green): SCALES'
| sc_keyboard, the trig keys as a keyboard in the scale's colours with the
| green-masked keys green; 0 when nothing was drawn (KEY OFF, or no SCALES
| in the remix: adapter.c draws its own).
ch_keyboard:
        .if     HAVE_SCALES
        jmp     sc_keyboard
        .else
        moveq   #0,%d0
        rts
        .endif

| int32_t ch_channel(unsigned t): byte 0 of MIDI track t's SETUP (CHAN: 0
| off, else channel + 1) in the Part the pages edit, through STORE's Part
| service (it preserves every register but d0); -1 when STORE has none.
ch_channel:
        move.l  %d2,-(%sp)
        jsr     store_part_ui_context   | d0 = bank * 4 + Part, or -1
        tst.l   %d0
        bmi.s   1f
        move.l  %d0,%d1
        move.l  8(%sp),%d0              | the track
        moveq   #0,%d2                  | SETUP byte 0, CHAN
        jsr     store_part_midi_read
1:      move.l  (%sp)+,%d2
        rts

| ---- STORE's file calls in the C convention (modules/store/store.s: a0, a1,
| d0 in, d0 out, a2 = the context; each clobbers d0, d1, a0, a1), as TURING's.
ch_file_path:                           | (format, out)
        movea.l 4(%sp),%a0
        movea.l 8(%sp),%a1
        moveq   #0,%d0
        jmp     store_path
ch_file_open:                           | (path, mode) -> d0 < 0 failed
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        movea.l 12(%sp),%a1
        lea     ch_ctx,%a2
        jsr     store_fopen
        movea.l (%sp)+,%a2
        rts
ch_file_read:                           | (buffer, length) -> 1 done
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        move.l  12(%sp),%d0
        lea     ch_ctx,%a2
        jsr     store_fread
        movea.l (%sp)+,%a2
        rts
ch_file_write:
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        move.l  12(%sp),%d0
        lea     ch_ctx,%a2
        jsr     store_fwrite
        movea.l (%sp)+,%a2
        rts
ch_file_close:
        move.l  %a2,-(%sp)
        lea     ch_ctx,%a2
        jsr     store_fclose
        movea.l (%sp)+,%a2
        rts
ch_file_crc:                            | (data, length) -> the CRC-32
        movea.l 4(%sp),%a0
        move.l  8(%sp),%d0
        moveq   #0,%d1
        jmp     store_crc32
ch_file_refuse:
        moveq   #CH_CLIENT,%d0
        moveq   #0,%d1
        jmp     store_refuse
ch_st_answer:                           | d0 = IGNORE / OVERWRITE / BACKUP
        move.l  %d0,-(%sp)
        jsr     ch_answer
        addq.l  #4,%sp
        rts

| CHORDS' mode-2 guide uses the native SLOTS layout. TRIG MODES owns
| menu registration, key/LED dispatch and held-note cleanup.
        .globl ch_box_head, ch_box_pic, ch_box_bar
ch_box_head:
        tst.l   0x80000012
        beq.s   1f
        jsr     ch_box_header
        jmp     0x4003601a
1:      move.l  0x460d16f8,%d0
        jmp     0x40035f98

| 0x40044b74, the box's picture for mode 2 (SLOTS' cells): in MIDI mode
| CHORDS' (ch_box_picture), then the picture's common end.
ch_box_pic:
        tst.l   0x80000012
        beq.s   1f
        jsr     ch_box_picture
        jmp     0x400453e2
1:      pea     0xa
        pea     0x3d
        jmp     0x40044b7c

| 0x40045502, the box's sample bar for modes 2 / 3 (SLOTS, SLICES: the play
| position of the audio track's sample, x 61..117, y 8..9): in MIDI mode
| CHORDS has no sample, so none (on to the refresh's common end).
ch_box_bar:
        tst.l   0x80000012
        beq.s   1f
        jmp     0x400455f2
1:      pea     0x1
        pea     0x9
        jmp     0x4004550a

| TRIG + UP (adapter.c, ch_trig_up): ch_up_layer, pushed while trig keys are
| held on a MIDI track, takes UP's press; the chooser's window then pushes
| ch_pk_layer: UP / DOWN (with stock's repeat, as SCALES'), YES, NO. Key
| records as SCALES' (code, 0, press, 0, repeat, 0, 0, delay, rate).
        .globl  ch_up_layer, ch_pk_layer, ch_pk_icon
        .balign 4
ch_up_layer:
        .long   0, ch_up_keys, ch_no_encs, 0, 0, -1, -1
ch_up_keys:
        .byte   0x33, 0
        .long   ch_trig_up, 0, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
ch_pk_layer:
        .long   0, ch_pk_keys, ch_no_encs, 0, 0, -1, -1
ch_pk_keys:
        .byte   0x33, 0                 | UP
        .long   ch_pk_ud, 0, ch_pk_ud, 0, 0
        .word   15, 5
        .byte   0x20, 0                 | DOWN
        .long   ch_pk_ud, 0, ch_pk_ud, 0, 0
        .word   15, 5
        .byte   0x31, 0                 | YES
        .long   ch_pk_yes, 0, 0, 0, 0
        .word   0, 0
        .byte   0x32, 0                 | NO
        .long   ch_pk_close, 0, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
ch_no_encs:
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .balign 4
| The title's icon: SCALES' keyboard (a stock icon record: 19 x 9, a long a
| column, the column in its top bits; the second plane all set, as stock's)
| with three of its white keys marked, a chord.
ch_pk_icon:
        .long   0x13, 0x09, 0x01, ch_pk_icon_p0, ch_pk_icon_p1
ch_pk_icon_p0:
        .long   0xff800000, 0x86800000, 0xfc800000, 0xff800000, 0xfc800000
        .long   0xfc800000, 0xff800000, 0xfc800000, 0x80800000, 0xff800000
        .long   0x86800000, 0xfc800000, 0xff800000, 0xfc800000, 0xfc800000
        .long   0xff800000, 0xfc800000, 0x86800000, 0xff800000
ch_pk_icon_p1:
        .rept   19
        .long   0xff800000
        .endr

| The trig keys: one stub per key for its press and its release, each passing
| its own code, so nothing hangs on the arguments stock's dispatcher passes.
        .irp    k, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
ch_kd_\k:
        pea     \k
        jsr     ch_key_down
        addq.l  #4,%sp
        rts
ch_ku_\k:
        pea     \k
        jsr     ch_key_up
        addq.l  #4,%sp
        rts
        .endr

| The atelier's input layer, as the stock ones: {0, keys, encoders, 0, 0, -1,
| -1}. Key records, 26 B: {code, 0, press, release, repeat, aux, 0, delay,
| rate}; encoder records, 22 B: {index, 0, handler, 16 B}. The sixteen trig
| keys choose a slot (FUNC: the keyboard), so the sequencer's trigs are not
| edited under the page; the six pushes are swallowed; LEVEL passes.
        .balign 4
ch_layer:
        .long   0, CH_KEYS, CH_ENCS, 0, 0, -1, -1
CH_KEYS:
        .irp    k, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
        .byte   \k, 0
        .long   ch_kd_\k, ch_ku_\k, 0, 0, 0
        .word   0, 0
        .endr
        .irp    k, 0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d
        .byte   \k, 0
        .long   ch_page_push, 0, 0, 0, 0
        .word   0, 0
        .endr
        .byte   0xff, 0
        .space  24
CH_ENCS:
        .irp    k, 0, 1, 2, 3, 4, 5
        .byte   \k, 0
        .long   ch_page_enc, 0, 0, 0, 0
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0

| The file's buffers, in the image (zero at boot, unlike .bss: TRAPS
| trap-dram-bss). STORE_CTX: the stock file object and its 4 KB buffer.
        .balign 4
ch_ctx:         .space  4120
ch_path:        .space  260
ch_path2:       .space  260
ch_fbuf:        .space  3584            | CH_FILE_B (chords.h's ch_pack)
ch_fsaved:      .space  3584
