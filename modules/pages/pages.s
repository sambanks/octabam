| PAGES -- a page key pressed again steps through the registered pages
| (manifest.py). remix.inc carries the cycle per page and the ticks.
        .text
        .include "remix.inc"
        .globl  pg_opener, pg_tick_stub

| pg_opener is the detour at 0x400322f0, the page key's setup opener (code,
| mode), called only from 0x40055720 (0x4005576c). Mode 1 is a single press
| on the page already shown: stock opens nothing when no setup window is open
| (0x400bcd14 +8) and 0x46c7dd26 (FUNC) is clear. That press on a key with
| registered pages steps to the next; mode 3 (the double press, the stock
| setup) and every other case run stock. The displaced `movel %sp@(4),%d0;
| moveq #3,%d1` is replayed before 0x400322f6.
pg_opener:
        moveq   #1,%d1
        cmp.l   8(%sp),%d1
        bne.s   1f
        movea.l 0x400bcd14,%a0
        tst.l   8(%a0)                  | a setup window open
        bne.s   1f
        tst.l   0x46c7dd26              | FUNC held
        bne.s   1f
        .if     pg_midi_src
        moveq   #pg_midi_src_code,%d1
        cmp.l   4(%sp),%d1
        bne.s   2f
        tst.l   0x80000012              | MIDI mode
        beq.s   2f
        pg_cycle_midi_src               | returns to 0x40055720
2:
        .endif
        .if     pg_audio_src
        moveq   #pg_audio_src_code,%d1
        cmp.l   4(%sp),%d1
        bne.s   3f
        tst.l   0x80000012              | audio mode
        bne.s   3f
        pg_cycle_audio_src              | returns to 0x40055720
3:
        .endif
1:      move.l  4(%sp),%d0
        moveq   #3,%d1
        jmp     0x400322f6

| pg_tick_stub is the detour at 0x40052208, the display loop (UI task) as it
| loads the double-press tick count: each page's tick (it follows the track,
| closes when the screen leaves its page).
pg_tick_stub:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        pg_ticks
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        move.l  0x460d5de0,%d0
        jmp     0x4005220e
