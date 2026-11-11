| PAGES LOCKS -- the hand-written part of the locks unit: EVENTS' entries
| and the clients' callbacks by page id (remix.inc, manifest.py locks_inc).
| generate.py appends it to the compiled locks.c.
        .text
        .include "remix.inc"
        .globl  pg_claim, pg_scene_claim, pg_handle, pg_scene_handle, pg_copy_pre, pg_steps
        .globl  pg_lk_cb_any, pg_lk_cb_ctx, pg_lk_cb_turn, pg_lk_cb_part, pg_lk_cb_redraw, pg_lk_hold

| EVENTS' claims take d0 = encoder, d1 = delta and must be read-only; the
| handlers (pg_handle, pg_scene_handle: locks.c) take stock's native frame.
pg_claim:
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        jsr     pg_lk_claim
        addq.l  #8,%sp
        rts
pg_scene_claim:
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        jsr     pg_lk_scene_claim
        addq.l  #8,%sp
        rts

| EVENTS' notifications in registers: edit.copy_pre d0 dst, d1 src, d2 length;
| edit.steps d0 op, d1-d5 its arguments (locks.c pg_lk_copy, pg_lk_steps).
pg_copy_pre:
        move.l  %d2,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        jsr     pg_lk_copy
        lea     12(%sp),%sp
        rts
pg_steps:
        lea     -24(%sp),%sp
        movem.l %d0-%d5,(%sp)
        jsr     pg_lk_steps
        lea     24(%sp),%sp
        rts

| The clients' page in front (0 none): the first nonzero.
pg_lk_cb_ctx:
        pg_lk_ctx_calls
        moveq   #0,%d0
        rts

| Any PAGES page in front (locks or not): 1, else 0.
pg_lk_cb_any:
        pg_lk_shown_calls
        moveq   #0,%d0
        rts

| (page, ...): the page's client, the same frame.
pg_lk_cb_turn:
        pg_lk_by_page turn
        moveq   #-1,%d0
        rts
pg_lk_cb_part:
        pg_lk_by_page part
        moveq   #0,%d0
        rts
pg_lk_cb_redraw:
        pg_lk_by_page redraw
        rts

| ---- STORE's file calls in the C convention (modules/store/store.s: a0, a1,
| d0 in, d0 out, a2 = the context; each clobbers d0, d1, a0, a1). DRUMMER's.
        .globl  pg_file_path, pg_file_open, pg_file_read, pg_file_write, pg_file_close
        .globl  pg_file_crc, pg_file_refuse, pg_st_answer, pg_lk_path, pg_lk_path2
pg_file_path:                           | (format, out)
        movea.l 4(%sp),%a0
        movea.l 8(%sp),%a1
        moveq   #0,%d0
        jmp     store_path
pg_file_open:                           | (path, mode) -> d0 < 0 failed
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        movea.l 12(%sp),%a1
        lea     pg_lk_ctx,%a2
        jsr     store_fopen
        movea.l (%sp)+,%a2
        rts
pg_file_read:                           | (buffer, length) -> 1 done
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        move.l  12(%sp),%d0
        lea     pg_lk_ctx,%a2
        jsr     store_fread
        movea.l (%sp)+,%a2
        rts
pg_file_write:
        move.l  %a2,-(%sp)
        movea.l 8(%sp),%a0
        move.l  12(%sp),%d0
        lea     pg_lk_ctx,%a2
        jsr     store_fwrite
        movea.l (%sp)+,%a2
        rts
pg_file_close:
        move.l  %a2,-(%sp)
        lea     pg_lk_ctx,%a2
        jsr     store_fclose
        movea.l (%sp)+,%a2
        rts
pg_file_crc:                            | (data, length) -> the CRC-32
        movea.l 4(%sp),%a0
        move.l  8(%sp),%d0
        moveq   #0,%d1
        jmp     store_crc32
pg_file_refuse:
        moveq   #PG_CLIENT,%d0
        moveq   #0,%d1
        jmp     store_refuse
pg_st_answer:                           | d0 = IGNORE / OVERWRITE / BACKUP
        move.l  %d0,-(%sp)
        jsr     pg_lk_answer
        addq.l  #4,%sp
        rts

        .data
pg_lk_hold:
        pg_lk_holds
        .balign 4
pg_lk_ctx:    .zero   4120              | STORE's context: the file object and its 4 KB buffer
pg_lk_path:   .zero   260
pg_lk_path2:  .zero   260
        .text
