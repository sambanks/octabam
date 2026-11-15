| DRUMMER -- the hand-written part of the unit: the detour stubs and the
| state the C keeps in loader-owned DRAM (explicitly zeroed here, never
| .bss: TRAPS trap-dram-bss). generate.py appends this to the compiled
| drummer.c + adapter.c. Sites: INVESTIGATION.md, phases 1-2 and 4.
        .text
        .balign 4
        .global dr_step_stub, dr_frame_stub, dr_start_stub, dr_rebuild_stub

| 0x400a2d82, the sequencer tick right after `jsr 0x4009d1e8` (the step
| builder), d5 = the track. Displaced: mvzb 0x8000668d,%d0 (6), re-run last
| so d0 is what stock loaded.
dr_step_stub:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        move.l  28(%sp),-(%sp)          | the builder's (track, bank, pattern, step, n) at 16(%sp): step
        move.l  28(%sp),-(%sp)          | pattern
        move.l  28(%sp),-(%sp)          | bank
        move.l  44(%sp),-(%sp)          | n
        move.l  %d5,-(%sp)
        jsr     dr_on_step              | (track, n, bank, pattern, step)
        lea     20(%sp),%sp
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        mvz.b   0x8000668d,%d0
        jmp     0x400a2d88

| 0x4009dca2, the rebuild (0x4009da20's path) right after `jsr 0x4009d1e8`
| (track d6, step d2, n -1). Displaced: lea 20(%sp),%sp ; moveal 106(%sp),%a0
| (8). d0/d1/a1 are free here (reloaded below the site).
dr_rebuild_stub:
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a1,(%sp)
        move.l  24(%sp),-(%sp)          | the builder's (track, bank, pattern, step, n) at 12(%sp): step
        move.l  24(%sp),-(%sp)          | pattern
        move.l  24(%sp),-(%sp)          | bank
        move.l  %d2,-(%sp)
        move.l  %d6,-(%sp)
        jsr     dr_on_rebuild           | (track, step, bank, pattern, step)
        lea     20(%sp),%sp
        movem.l (%sp),%d0-%d1/%a1
        lea     12(%sp),%sp
        lea     20(%sp),%sp
        move.l  106(%sp),%a0
        jmp     0x4009dcaa

| PAGES' locks (pages/locks.c) when the remix has them (PAGES, EVENTS:
| HAVE_PAGELOCKS from manifest.py), else KIT BALANCE as it is: no lock.
        .include "remix.inc"
        .globl  dr_pl_step, dr_pl_value, dr_pl_shown, dr_pl_where
dr_pl_step:                             | (page, track, bank, pattern, step, trig)
        .if     HAVE_PAGELOCKS
        jmp     pg_lk_step
        .else
        rts
        .endif
dr_pl_value:                            | (page, track, slot, base) -> the value played
        .if     HAVE_PAGELOCKS
        jmp     pg_lk_value
        .else
        move.l  16(%sp),%d0
        rts
        .endif
dr_pl_shown:                            | (page, track, slot) -> 0xffff nothing held
        .if     HAVE_PAGELOCKS
        jmp     pg_lk_shown
        .else
        move.l  #0xffff,%d0
        rts
        .endif
dr_pl_where:                            | () -> the held step / scene, 0 none
        .if     HAVE_PAGELOCKS
        jmp     pg_lk_where
        .else
        moveq   #0,%d0
        rts
        .endif

| 0x4000d3ae, the packer, after `movel %d1,0x800062a8` (the frame's page
| records). Displaced: movel #32,%macsr (6), re-run last.
dr_frame_stub:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     dr_frame
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        move.l  #32,%macsr
        jmp     0x4000d3b4

| The FLEX entry of the voice-start table (0x400d6458, a SymbolRef):
| called as stock 0x4000f450(track, slot, flags) (the packer, 0x4000d490..9c). A DRUMMER track gets its hit's
| slice before the stock start and its VOL after; any other track, stock.
dr_start_stub:
        move.l  4(%sp),%d0              | track
        cmp.l   #8,%d0
        bcc.s   .Lstock
        lea     dr_on,%a0
        tst.b   (%a0,%d0.l)
        beq.s   .Lstock
        lea     -16(%sp),%sp
        movem.l %d1-%d2/%a0-%a1,(%sp)
        move.l  %d0,%d2                 | the track, kept across the calls
        move.l  28(%sp),-(%sp)          | flags (bit 5: a live start -- trig key, AED, KIT -- not the sequencer's)
        move.l  %d2,-(%sp)
        jsr     dr_before_start
        addq.l  #8,%sp
        move.l  28(%sp),-(%sp)          | flags, the packer's third argument (16 saved + 4 ret + 8)
        move.l  28(%sp),-(%sp)          | slot (+ 4 pushed)
        move.l  %d2,-(%sp)              | track: stock 0x4000f450 reads all three (sp@(72): the flags)
        jsr     0x4000f450
        addq.l  #8,%sp                  | drop track and slot, keep a word for:
        move.l  %d0,(%sp)               | stock's result, if any
        move.l  %d2,-(%sp)
        jsr     dr_after_start
        addq.l  #4,%sp
        move.l  (%sp)+,%d0
        movem.l (%sp),%d1-%d2/%a0-%a1
        lea     16(%sp),%sp
        rts
.Lstock:
        jmp     0x4000f450

| ---- the KIT window's input (kit.c) -------------------------------------
| dr_up_layer, pushed while a trig key is held on a DRUMMER track, takes UP's
| press; the window pushes dr_kw_layer: UP / DOWN (stock's repeat), YES, NO,
| the trig keys, the encoders. Records as CHORDS' / SCALES': keys {code, 0,
| press, release, repeat, aux, 0, delay, rate} 26 B, encoders {index, 0,
| handler, 16 B} 22 B, layers {0, keys, encoders, 0, 0, -1, -1}.
        .globl  dr_up_layer, dr_kw_layer
        .irp    k, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
dr_kt_\k:
        pea     \k
        jsr     dr_kw_trig
        addq.l  #4,%sp
        rts
        .endr
        .balign 4
dr_up_layer:
        .long   0, dr_up_keys, dr_no_encs, 0, 0, -1, -1
dr_up_keys:
        .byte   0x2f, 0                 | BANK with a trig held: the KIT (image 57; UP before)
        .long   dr_kit_up, 0, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
dr_kw_layer:
        .long   0, dr_kw_keys, dr_kw_encs, 0, 0, -1, -1
dr_kw_keys:
        .byte   0x33, 0                 | UP
        .long   dr_kw_ud, 0, dr_kw_ud, 0, 0
        .word   15, 5
        .byte   0x20, 0                 | DOWN
        .long   dr_kw_ud, 0, dr_kw_ud, 0, 0
        .word   15, 5
        .byte   0x31, 0                 | YES: close
        .long   dr_kw_close, 0, 0, 0, 0
        .word   0, 0
        .byte   0x32, 0                 | NO: close
        .long   dr_kw_close, 0, 0, 0, 0
        .word   0, 0
        .byte   0x34, 0                 | LEFT: page 1
        .long   dr_kw_left, 0, 0, 0, 0
        .word   0, 0
        .byte   0x21, 0                 | RIGHT: page 2 (FUNC + RIGHT, AUTO again: kit.c)
        .long   dr_kw_right, 0, 0, 0, 0
        .word   0, 0
        .irp    k, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
        .byte   \k, 0
        .long   dr_kt_\k, 0, 0, 0, 0
        .word   0, 0
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
dr_kw_encs:
        .irp    k, 0, 1, 2, 3, 4, 5
        .byte   \k, 0
        .long   dr_kw_enc, 0, 0, 0, 0
        .endr
dr_no_encs:
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
| KIT BALANCE (kit.c): pushed while PAGES shows DRUMMER's page after LIVE (SRC again),
| A-F turn the zones' mix; no key of its own.
        .globl  dr_l2_layer
        .balign 4
dr_l2_layer:
        .long   0, dr_l2_keys, dr_l2_encs, 0, 0, -1, -1
dr_l2_keys:
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
dr_l2_encs:
        .irp    k, 0, 1, 2, 3, 4, 5
        .byte   \k, 0
        .long   dr_l2_enc, 0, 0, 0, 0
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0

| ---- STORE's file calls in the C convention (modules/store/store.s: a0, a1,
| d0 in, d0 out, a2 = the context; each clobbers d0, d1, a0, a1). FREE LOOP's.
        .globl  dr_file_path, dr_file_open, dr_file_read, dr_file_write, dr_file_close
        .globl  dr_file_crc, dr_file_refuse, dr_st_answer
        .equ    DR_CLIENT, 8
dr_file_path:                           | (format, out)
        movea.l 4(%sp),%a0
        movea.l 8(%sp),%a1
        moveq   #0,%d0
        jmp     store_path
dr_file_open:                           | (path, mode) -> d0 < 0 failed
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        movea.l 12(%sp),%a1
        lea     dr_ctx,%a2
        jsr     store_fopen
        movea.l (%sp)+,%a2
        rts
dr_file_read:                           | (buffer, length) -> 1 done
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        move.l  12(%sp),%d0
        lea     dr_ctx,%a2
        jsr     store_fread
        movea.l (%sp)+,%a2
        rts
dr_file_write:
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        move.l  12(%sp),%d0
        lea     dr_ctx,%a2
        jsr     store_fwrite
        movea.l (%sp)+,%a2
        rts
dr_file_close:
        move.l  %a2,-(%sp)
        lea     dr_ctx,%a2
        jsr     store_fclose
        movea.l (%sp)+,%a2
        rts
dr_file_crc:                            | (data, length) -> the CRC-32
        movea.l 4(%sp),%a0
        move.l  8(%sp),%d0
        moveq   #0,%d1
        jmp     store_crc32
dr_file_refuse:
        moveq   #DR_CLIENT,%d0
        moveq   #0,%d1
        jmp     store_refuse
dr_st_answer:                           | d0 = IGNORE / OVERWRITE / BACKUP
        move.l  %d0,-(%sp)
        jsr     dr_answer
        addq.l  #4,%sp
        rts

| ---- the engine task's receive (image 68) ----------------------------------
|   0x40084854  `jsr 0x40000d00 / moveal %d0,%a2 / addql #4,%sp`: the next
|               message. A DRUMMER job (type 0x42, store.c dr_drk_post) runs
|               dr_job and goes back to the receive (0x4008484e); every other
|               message goes on to the type switch at 0x4008485e (BRAIN's
|               detour when BRAIN is in: it takes 0x41).
        .globl  dr_on_job
dr_on_job:
        jsr     0x40000d00
        movea.l %d0,%a2
        addq.l  #4,%sp
        mvz.b   (%a2),%d0
        cmpi.l  #0x42,%d0
        bne.s   1f
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     dr_job
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        jmp     0x4008484e
1:      jmp     0x4008485e

| dr_sample_at(slot, frame, &run) -> d0: stock's pool walk 0x4009499c(slot,
| position, 1) (SAMPLE_SAVE.md: the WAV writer's), its run (d1) stored.
        .globl  dr_sample_at
dr_sample_at:
        pea     1
        move.l  12(%sp),-(%sp)          | frame (8 + 4)
        move.l  12(%sp),-(%sp)          | slot (4 + 8)
        jsr     0x4009499c
        lea     12(%sp),%sp
        movea.l 12(%sp),%a0
        move.l  %d1,(%a0)
        rts

| ---- state: loader-owned DRAM, explicitly initialised -------------------
        .balign 4
        .global dr_loop, dr_loop_bar
        .global dr_on, dr_kit, dr_state, dr_knob, dr_knob_ok, dr_pos, dr_pass, dr_scale
        .global dr_last_idx, dr_len, dr_strt, dr_kit_ready, dr_ring, dr_head, dr_count
        .global dr_vel_now, dr_vol_base, dr_vol_mine, dr_stats, dr_last_hit, dr_restarted, dr_desc, dr_desc_ok
dr_stats:     .zero   32
        .globl  dr_payload, dr_saved, dr_path, dr_path2
dr_payload:   .zero   4728              | DrSave (store.c), the file's payload (version 5)
dr_saved:     .zero   4728              | what the file holds
dr_ctx:       .zero   4120              | STORE's context: the file object and its 4 KB buffer
dr_path:      .zero   260
dr_path2:     .zero   260
        .balign 4
dr_desc_ok:   .zero   4
dr_desc:      .zero   0x1ca             | DRUMMER's page descriptor (dr_page)
        .balign 4
dr_pos:       .zero   32
dr_pass:      .zero   32
dr_scale:     .zero   32
dr_ring:      .zero   8*4*8             | 8 tracks x 4 hits x {slice, vel, used, pad, pos}
dr_last_hit:  .zero   8*8               | DrHit: the step's decision, for the tick's second call
dr_kit:       .zero   8*268             | DrKit (static assert in adapter.c)
dr_state:     .zero   8*32              | DrState
dr_loop:      .zero   8*258             | DrLoop (REDRUM, image 77)
        .balign 4
dr_loop_bar:  .zero   612               | DrLoopBar (REDRUM's scratch)
        .balign 2
dr_on:        .zero   8                 | the signed tracks, refreshed every frame (dr_frame)
dr_knob:      .zero   8*12
dr_knob_ok:   .zero   8
dr_last_idx:  .zero   8
dr_len:       .zero   8
dr_strt:      .zero   8
dr_kit_ready: .zero   8
dr_head:      .zero   8
dr_count:     .zero   8
dr_vel_now:   .zero   8
dr_vol_base:  .zero   8
dr_vol_mine:  .zero   8                 | the VOL the last hit wrote (0 none)
dr_restarted: .zero   8
        .balign 2
