| FREE LOOP -- the hand-written part of the unit: the detour stubs, the
| STORE glue, the key tables and the state the C keeps in loader-owned
| DRAM. generate.py appends this to the compiled freeloop.c + adapter.c.
|
| fl_cc is hooked at 0x4000e79c, the stock CC handler's entry (the CC
| vector's target, and CC MAP's tail-call for every CC it does not take),
| before its linkw. sp@(4) = the message: +0 status (0xB0 | channel), +1 CC,
| +2 value. Any other CC: the displaced linkw/moveml replayed, then stock
| at 0x4000e7a4.
|   CC 90 / 91 / 93, any channel that reaches an audio track: the track's
|          REC / PLAY/STOP / END pedal (fl_pedal, value 0 = the release).
|   CC 83-89 on the PROG CH channel (LIVE PEDAL's, flashed on OCTABAM2/4/7):
|          83 PLAY / STOP, 84 clear R1-R8 (stopped), 85 / 86 next /
|          previous pattern, 88 / 89 next / previous bank; value 0 ignored;
|          admitted as stock admits a Program Change, except that the AUTO
|          channel stays admitted in MIDI mode.
        .text
        .globl  fl_cc, fl_gate_stub, fl_ui_stub, fl_rec_stub, fl_trig_stub
        .globl  fl_cfg, fl_st, fl_saved, fl_now, fl_playing_was, fl_clear_all, fl_bank_seen
        .globl  fl_nowrite, fl_backup, fl_win_row, fl_win_t, fl_clear, fl_trim, fl_toast_act
        .globl  fl_toast_up, fl_win_pushed, fl_win, fl_text, fl_path, fl_path2, fl_layer, fl_takes
        .globl  fl_keep, fl_keep_n
        .globl  fl_keys, fl_st_answer, fl_settle, fl_stock_cc, fl_msg, fl_trim_t24, fl_trim_bars
        .globl  fl_qany, fl_qrefresh, fl_qinj, fl_src, fl_injd3, fl_glyph, fl_draw
        .globl  fl_pop, fl_pop_key, fl_pop_t, fl_pop_idle, fl_pop_last, fl_pop_closed
        .globl  fl_armed, fl_odub, fl_qplay, fl_stopm, fl_pop_msg, fl_pop_mt, fl_pop_mticks, fl_pat_t, fl_fade, fl_fade_lv, fl_bpat
        .globl  fl_file_path, fl_file_open, fl_file_read, fl_file_write, fl_file_close
        .globl  fl_file_crc, fl_file_refuse

        .equ    FL_PEDAL, 90
        .equ    FL_PLAY, 91
        .equ    FL_UNDO, 92
        .equ    FL_END, 93
        .equ    LP_PLAY, 83
        .equ    LP_CLEAR, 84
        .equ    PS_NEXT, 85
        .equ    PS_PREV, 86
        .equ    PS_BNEXT, 88
        .equ    PS_BPREV, 89
        .equ    FL_CLIENT, 5            | STORE's CLIENT_IDS

fl_cc:
        movea.l 4(%sp),%a0
        mvz.b   1(%a0),%d0              | CC number
        moveq   #FL_PEDAL,%d1
        cmp.l   %d1,%d0
        beq     pedal
        moveq   #FL_PLAY,%d1
        cmp.l   %d1,%d0
        beq     pedal
        moveq   #FL_UNDO,%d1
        cmp.l   %d1,%d0
        beq     pedal
        moveq   #FL_END,%d1
        cmp.l   %d1,%d0
        beq     pedal
        moveq   #LP_PLAY,%d1
        cmp.l   %d1,%d0
        beq     mine
        moveq   #LP_CLEAR,%d1
        cmp.l   %d1,%d0
        beq     mine
        moveq   #PS_NEXT,%d1
        cmp.l   %d1,%d0
        beq     mine
        moveq   #PS_PREV,%d1
        cmp.l   %d1,%d0
        beq     mine
        moveq   #PS_BNEXT,%d1
        cmp.l   %d1,%d0
        beq     mine
        moveq   #PS_BPREV,%d1
        cmp.l   %d1,%d0
        beq     mine
stock:
fl_stock_cc:                            | (message): the stock handler, as the CC vector calls it
        link.w  %fp,#-44                | displaced
        movem.l %d2-%d7/%a2-%a5,(%sp)   | displaced
        jmp     0x4000e7a4

| CC 90 / 91: fl_pedal(channel, cc, value) after stock's channel -> track map.
pedal:
        move.l  %a2,-(%sp)
        movea.l %a0,%a2
        jsr     0x40001854              | channel -> track map, as stock does first
        mvz.b   2(%a2),%d0
        move.l  %d0,-(%sp)              | value
        mvz.b   1(%a2),%d0
        move.l  %d0,-(%sp)              | cc
        mvz.b   (%a2),%d0
        moveq   #15,%d1
        and.l   %d1,%d0
        move.l  %d0,-(%sp)              | channel
        jsr     fl_pedal
        lea     12(%sp),%sp
        movea.l (%sp)+,%a2
        rts

mine:
        tst.b   2(%a0)                  | value 0: the pedal's release
        bne     go
        rts
go:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        movea.l 16(%sp),%a2             | the message
        jsr     0x40001854              | channel -> track map, as stock does first
        mvs.b   (%a2),%d3
        moveq   #15,%d0
        and.l   %d0,%d3                 | d3 = channel
        lea     0x46c7febe,%a0
        move.l  (%a0,%d3.l*4),%d2       | d2 = that channel's map word
        mvz.b   0x8000002b,%d0
        btst    #0,%d0                  | PROG CH RECEIVE
        beq     out
        mvs.b   0x8000002d,%d0          | PROG CH channel, -1 = AUTO
        moveq   #-1,%d1
        cmp.l   %d1,%d0
        bne     fixed
        move.l  %d2,%d0
        andi.l  #0x1ff,%d0
        beq     out                     | the channel reaches no track
        bra     admit                   | the AUTO channel in MIDI mode too: these
                                        | are the transport's and the banks', not a
                                        | track's (stock's PC guard, 0x40033970,
                                        | refuses AUTO when MIDI mode is on)
fixed:
        cmp.l   %d3,%d0
        bne     out
admit:
        mvz.b   1(%a2),%d0
        moveq   #LP_PLAY,%d1
        cmp.l   %d1,%d0
        bne     notp
        moveq   #1,%d0
        cmp.l   0x800065b8,%d0          | running?
        bne     start
        movea.l #0x4000a1e0,%a0         | stock MIDI Stop
        bra     transport
start:
        movea.l #0x4000a274,%a0         | stock MIDI Start
transport:
        mvz.b   0x80000029,%d3          | TRANSPORT RECEIVE, put back below
        moveq   #1,%d0
        move.b  %d0,0x80000029
        clr.l   -(%sp)                  | the handler's argument slot
        jsr     (%a0)
        addq.l  #4,%sp
        move.b  %d3,0x80000029
        bra     out
notp:
        moveq   #LP_CLEAR,%d1
        cmp.l   %d1,%d0
        bne     step
        moveq   #1,%d0
        cmp.l   0x800065b8,%d0
        beq     out                     | only with the sequencer stopped
        move.b  %d0,fl_clear_all        | the UI task clears on its next tick
        bra     out
step:
        tst.l   0x800065b8              | transport running?
        beq     ui
        mvz.b   0x800065c0,%d0          | cued pattern
        cmpi.b  #-1,%d0
        beq     ui
        mvz.b   0x800065bf,%d1          | cued bank
        bra     have
ui:
        mvz.b   0x80000004,%d0          | current pattern
        mvz.b   0x80000002,%d1          | current bank
have:
        lsl.l   #4,%d1
        add.l   %d0,%d1                 | d1 = bank*16 + pattern
        mvz.b   1(%a2),%d0
        moveq   #PS_NEXT,%d2
        cmp.l   %d2,%d0
        beq     next
        moveq   #PS_PREV,%d2
        cmp.l   %d2,%d0
        beq     prev
        andi.l  #0xf0,%d1               | a bank step: pattern 1 of the base's bank
        moveq   #PS_BNEXT,%d2
        cmp.l   %d2,%d0
        bne     bprev
        addi.l  #16,%d1
        cmpi.l  #255,%d1
        bgt     out                     | already bank P
        bra     cue
bprev:
        subi.l  #16,%d1
        bmi     out                     | already bank A
        bra     cue
next:
        addq.l  #1,%d1
        cmpi.l  #255,%d1
        bgt     out                     | already P16
        bra     cue
prev:
        subq.l  #1,%d1
        bmi     out                     | already A1
cue:
        move.l  %d1,%d2
        jsr     0x4009a404              | as the PC handler does before cueing
        moveq   #15,%d0
        and.l   %d2,%d0
        move.l  %d0,-(%sp)              | pattern
        lsr.l   #4,%d2
        move.l  %d2,-(%sp)              | bank
        jsr     0x400a1030
        addq.l  #8,%sp
out:
        movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        rts

| 0x4009d9a4, the step handler's recorder-trig test (`tst.l %d3 ; beq.s
| 0x4009da16 ; move.l #0x91a,%d2` displaced; d3 = the REC bits of track
| d7). On an audio track with a recorder trig, or while a trig waits to be
| injected (an UNDO buffer's pass), d3 = fl_gate_track(d7, d3).
| d0/d1/a0/a1 only: d2-d7 are the step handler's (the C keeps them).
| While an END toggle is pending, fl_step_track(d7) first: a track on its
| loop's first step takes it.
fl_gate_stub:
        moveq   #8,%d0
        cmp.l   %d0,%d7
        bcc     pass                    | MIDI tracks: stock
        tst.b   fl_qany
        bne     0f
        tst.b   fl_qplay                | a PLAY entry somewhere: each track's first step
        beq     1f
0:      move.l  %d7,-(%sp)
        jsr     fl_step_track
        addq.l  #4,%sp
1:
        tst.l   %d3
        bne     2f
        tst.b   fl_qinj
        beq     pass                    | no recorder trig on this step
2:
        move.l  %d3,-(%sp)
        move.l  %d7,-(%sp)
        jsr     fl_gate_track
        addq.l  #8,%sp
        move.l  %d0,%d3                 | 0: this step has no recorder trig
pass:
        .ifdef  HK_REC_GATE             | beside REC_TRIG_MUTE (modules/hooks rec_gate): its gate
        jmp     rtm_gate                | replays the displaced move, may mute d3, and decides
        .else
        move.l  #0x91a,%d2              | displaced
        tst.l   %d3
        bne     fire
        jmp     0x4009da16              | no recorder trig on this step
fire:
        jmp     0x4009d9ae              | muls.l %d7,%d2 and on
        .endif

| ---- the track's mark at the screen edge, beside its status icon: a dot
| over it while it overdubs, a ring blinking at 2 Hz while armed. The form of
| REC_TRIG_MUTE's rtm_glyph and rtm_draw (Zac-Kyoti/octatrack-kyoti-fw, MIT),
| with FREE LOOP's states.
|
| The edge renderer 0x4004bee2: `jsr fl_glyph` replaces `lea 0x400c0cb8,%a0`.
| d3 = track, a4 = state (bit 0 playing, bit 1 the recorder live); folded in:
| 12 | playing overdubbing (the pass may be another recorder's), 10 | playing
| armed (blink on) and not recording, so the stock cache
| redraws on each change.
fl_glyph:                               | d0 / d1 only, as rtm_glyph: the rest is the renderer's
        mvz.b   fl_odub,%d0
        btst    %d3,%d0
        beq.s   1f
        moveq   #12,%d1
        bra.s   7f
1:      move.l  %a4,%d0
        btst    #1,%d0                  | recorder live: the true "+" wins until it ends
        bne.s   8f
        mvz.b   fl_armed,%d0
        btst    %d3,%d0
        beq.s   8f
        moveq   #10,%d1
7:      move.l  %a4,%d0
        andi.l  #1,%d0                  | playing
        or.l    %d1,%d0
        move.l  %d0,%a4
8:      lea     0x400c0cb8,%a0          | displaced: the renderer's per-track state cache
        rts

| The edge renderer 0x4004c00c: `jmp fl_draw` replaces `moveq #3,%d0 ;
| cmpl %a4,%d0 ; bnes 0x4004c02a`. a3 = box x, a2 = row offset, the blit
| 0x400128a8(desc, plane, x, y) in a5.
fl_draw:
        move.l  %a4,%d0
        moveq   #3,%d1
        cmp.l   %d0,%d1
        bne.s   1f
        jmp     0x4004c012              | 3: stock's "+>"
1:      lea     fl_ring_stop,%a0        | 10: armed, idle
        subq.l  #8,%d0
        subq.l  #2,%d0
        beq.s   2f
        lea     fl_ring_play,%a0        | 11: armed, playing
        subq.l  #1,%d0
        beq.s   2f
        lea     fl_dot_stop,%a0         | 12: overdubbing, idle
        subq.l  #1,%d0
        beq.s   2f
        lea     fl_dot_play,%a0         | 13: overdubbing, playing
        subq.l  #1,%d0
        beq.s   2f
        .ifdef  HK_ICON_DRAW            | beside REC_TRIG_MUTE (modules/hooks icon_draw):
        jmp     rtm_draw                | its mute dots (8 / 9), else nothing to draw
        .else
        jmp     0x4004c02a              | nothing to draw
        .endif
2:      pea     49(%a2)
        move.l  %a3,-(%sp)              | 7 wide, at x like stock's "+>"
        pea     0x400bf10a              | the plane
        move.l  %a0,-(%sp)
        jmp     0x4004c024              | the renderer's jsr (a5) + lea 16(sp)

        .balign 4
fl_ring_stop:   .long   7, 5, 1, fl_r_stop, 0x400c514e   | 0x400c514e: stock "+>"'s 7-column mask
fl_ring_play:   .long   7, 5, 1, fl_r_play, 0x400c514e
fl_dot_stop:    .long   7, 5, 1, fl_d_stop, 0x400c514e
fl_dot_play:    .long   7, 5, 1, fl_d_play, 0x400c514e
fl_r_stop:      .long   0x70000000,0x50000000,0x70000000,0,0x70000000,0x70000000,0x70000000   | o []
fl_r_play:      .long   0x70000000,0x50000000,0x70000000,0,0xf8000000,0x70000000,0x20000000   | o >
fl_d_stop:      .long   0x70000000,0x70000000,0x70000000,0,0x70000000,0x70000000,0x70000000   | * []
fl_d_play:      .long   0x70000000,0x70000000,0x70000000,0,0xf8000000,0x70000000,0x20000000   | * >

| The record builder's machine-trig test 0x4009d39e (`move.l %a5,%d3 ; and.l
| %d3,%d0 ; beq.w 0x4009d91a`, 8 bytes; d0 / d3 read on neither exit), track
| d7: no trig this step, or track d7 STOPped by a PLAY entry (fl_stopm) ->
| the builder's own "no trig" exit, a stock empty step (no trig, trigless,
| one-shot or lock-only, none of their locks); the trig conditions above it
| still run, the recorder trigs below it too.
fl_trig_stub:
        move.l  %a5,%d3                 | displaced
        and.l   %d3,%d0                 | displaced
        beq     1f
        tst.b   fl_qplay
        beq     2f
        move.l  116(%sp),%d0            | the pattern the builder builds (0x4009d91a's)
        lea     -12(%sp),%sp
        movem.l %d1/%a0-%a1,(%sp)       | the builder's, kept
        move.l  %d0,-(%sp)
        move.l  %d7,-(%sp)
        jsr     fl_trig_entry           | its first trig of a pattern: a PLAY STOP entry, before it sounds
        addq.l  #8,%sp
        movem.l (%sp),%d1/%a0-%a1
        lea     12(%sp),%sp
2:      mvz.b   fl_stopm,%d3
        btst    %d7,%d3
        bne     1f
        jmp     0x4009d3a6              | a trig: on
1:      jmp     0x4009d91a              | no trig this step

| The toast countdown 0x40056c28, UI task, 1/60 s: `move.l 0x460d1e6c,%d0`
| displaced. Called through a register from the task loop: d2-d7/a2-a6 are
| the caller's (the C keeps them). A tick that showed a toast returns
| (stock's countdown starts with the next one), as LIVE PEDAL's did.
fl_ui_stub:
        jsr     fl_ui_tick
        tst.l   %d0
        beq     tick
        rts
tick:
        move.l  0x460d1e6c,%d0          | displaced
        jmp     0x40056c2e

| The recorder routine's setup pointer, 0x40006d1a: `adda.l #0x80000cf4,%a4`
| displaced (a4 = the track's published RECORDING SETUP, 12 bytes: INAB
| INCD RLEN TRIG SRC3 ...). 136(%sp) is the track (the routine's own read at
| 0x40006d08); d0, d1 and a0 are rewritten at 0x40006d20.. before any use
| (LIVE PEDAL's site). While a track's free take runs, the routine reads a
| copy of its setup with RLEN MAX (64): the take lasts until the pedal ends
| it, whatever the track's RLEN (the template's PLEN).
fl_rec_stub:
        adda.l  #0x80000cf4,%a4         | displaced
        move.l  136(%sp),%d0            | the track
        moveq   #8,%d1
        cmp.l   %d1,%d0
        bcc     rec
        lea     fl_src,%a0              | an UNDO buffer's pass: the looping
        mvz.b   (%a0,%d0.l),%d1         | track's setup (fl_src[r] = track + 1)
        beq     own
        subq.l  #1,%d1
        sub.l   %d0,%d1                 | a4 += 12 (src - track)
        move.l  %d1,%d0
        add.l   %d0,%d0
        add.l   %d1,%d0
        lsl.l   #2,%d0
        adda.l  %d0,%a4
        bra     rec
own:
        lea     fl_st,%a0
        moveq   #1,%d1                  | FL_TAKE
        cmp.b   (%a0,%d0.l),%d1
        bne     rec
        lea     fl_take_setup,%a0
        move.l  (%a4),(%a0)
        move.l  4(%a4),4(%a0)
        move.l  8(%a4),8(%a0)
        moveq   #64,%d1
        move.b  %d1,2(%a0)              | RLEN MAX
        movea.l %a0,%a4
rec:
        jmp     0x40006d20

| ---- STORE's file calls in the C convention (modules/store/store.s: a0, a1,
| d0 in, d0 out, a2 = the context; each clobbers d0, d1, a0, a1).
fl_file_path:                           | (format, out)
        movea.l 4(%sp),%a0
        movea.l 8(%sp),%a1
        moveq   #0,%d0
        jmp     store_path
fl_file_open:                           | (path, mode) -> d0 < 0 failed
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        movea.l 12(%sp),%a1
        lea     fl_ctx,%a2
        jsr     store_fopen
        movea.l (%sp)+,%a2
        rts
fl_file_read:                           | (buffer, length) -> 1 done
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        move.l  12(%sp),%d0
        lea     fl_ctx,%a2
        jsr     store_fread
        movea.l (%sp)+,%a2
        rts
fl_file_write:
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        move.l  12(%sp),%d0
        lea     fl_ctx,%a2
        jsr     store_fwrite
        movea.l (%sp)+,%a2
        rts
fl_file_close:
        move.l  %a2,-(%sp)
        lea     fl_ctx,%a2
        jsr     store_fclose
        movea.l (%sp)+,%a2
        rts
fl_file_crc:                            | (data, length) -> the CRC-32
        movea.l 4(%sp),%a0
        move.l  8(%sp),%d0
        moveq   #0,%d1
        jmp     store_crc32
fl_file_refuse:
        moveq   #FL_CLIENT,%d0
        moveq   #0,%d1
        jmp     store_refuse
fl_st_answer:                           | d0 = IGNORE / OVERWRITE / BACKUP
        move.l  %d0,-(%sp)
        jsr     fl_answer
        addq.l  #4,%sp
        rts

| ---- the [TRACK]-held key table: stock's 0x400d1594 record for record
| (code, 0, press, release, 16 zero bytes), UP added before the terminator
| (MORPH's form; the manifest points the layer's keys field 0x400d164e here).
        .macro  KEYREC code, press, release
        .byte   \code, 0
        .long   \press, \release
        .space  16
        .endm
        .balign 4
fl_keys:
        KEYREC  0x27, 0x40083a7c, 0                 | STOP (stock)
        KEYREC  0x28, 0x40083a30, 0                 | PLAY (stock)
        KEYREC  0x2f, 0x40083ce0, 0                 | BANK (stock)
        KEYREC  0x31, 0x400834d8, 0x400834d8        | YES  (stock: ARM REC TRK)
        KEYREC  0x32, 0x40083488, 0x40083488        | NO   (stock: DISARM REC TRK)
        KEYREC  0x18, 0x400839dc, 0                 | 0x18 (stock)
        KEYREC  0x33, fl_key_up, 0                  | UP: the FREE LOOP window
        .byte   0xff, 0                             | terminator, as stock 0x400d1630
        .space  24

| ---- the window's input layer, as the stock ones: {0, keys, encoders, 0,
| 0, -1, -1}. Key records, 26 B: {code, 0, press, release, repeat, aux, 0,
| delay, rate}; encoder records, 22 B: {index, 0, handler, 16 B}.
        .balign 4
fl_layer:
        .long   0, FL_KEYS, FL_ENCS, 0, 0, -1, -1
FL_KEYS:
        .irp    k, 0x33, 0x20, 0x34, 0x21
        .byte   \k, 0
        .long   fl_key_win, 0, fl_key_win, 0, 0
        .word   15, 5
        .endr
        .irp    k, 0x31, 0x32
        .byte   \k, 0
        .long   fl_key_win, 0, 0, 0, 0
        .word   0, 0
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
FL_ENCS:
        .irp    k, 0, 1, 2, 3, 4, 5, 6
        .byte   \k, 0
        .long   fl_enc_win, 0, 0, 0, 0
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0

| ---- state (DRAM, writable, zeroed by the loader but for fl_bank_seen) ----
        .balign 4
fl_cfg:         .space  1098
        .balign 4
fl_saved:       .space  1098
        .balign 4
fl_st:          .space  176             | FlState (adapter.c asserts it)
fl_now:         .long   0
fl_take_setup:  .space  12
fl_trim:        .space  32
fl_trim_t24:    .space  32
fl_trim_bars:   .space  32
fl_keep:        .space  192
fl_takes:       .space  32
fl_win:         .long   0
fl_toast_act:   .space  16
fl_text:        .space  24
fl_path:        .space  260
fl_path2:       .space  260
fl_clear:       .space  8
fl_msg:         .space  4
fl_qany:        .byte   0
fl_qrefresh:    .byte   0
fl_qinj:        .byte   0
fl_pop_t:       .byte   0
fl_pop_idle:    .byte   0
fl_pop_last:    .byte   0
fl_armed:       .byte   0
fl_odub:        .byte   0
fl_qplay:       .byte   0
fl_stopm:       .byte   0
fl_pop_msg:     .byte   0
fl_pop_mt:      .byte   0
fl_pop_mticks:  .byte   0
fl_pat_t:       .byte   0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff
fl_bpat:        .byte   0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff
fl_fade:        .space  8
fl_fade_lv:     .space  8
        .balign 4
fl_pop:         .long   0
fl_pop_key:     .long   0
fl_src:         .space  8
        .balign 4
fl_injd3:       .space  32
        .balign 2
fl_settle:      .space  8
fl_keep_n:      .space  8
fl_playing_was: .byte   0
fl_clear_all:   .byte   0
fl_bank_seen:   .byte   0xff
fl_nowrite:     .byte   0
fl_backup:      .byte   0
fl_win_row:     .byte   0
fl_win_t:       .byte   0
fl_toast_up:    .byte   0
fl_win_pushed:  .byte   0
        .balign 4
fl_ctx:         .space  4120            | STORE's context: the file object and its 4 KB buffer
