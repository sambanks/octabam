| OCTAKIT MIRROR -- stock's SRAM working-part mirror brought level with the
| working part before a page CLEAR or PASTE, on an image carrying Octakit.
|
| Stock keeps two copies of the current part: the working part in the bank
| (*0x46c82456 + 0x8ed80 + part * 0x18b2) and a battery-backed mirror of it
| (0x100a4ece + part * 0x18b2); every stock edit writes both, and stock
| 1.40C leaves them equal after a project load (measured under the port, 30
| Sep 2026). Octakit's load path stages her Kit into the working part
| (gk_stage_canonical, gk_workspace_prepare) and leaves the mirror as the
| file had it; her page-clipboard check (gk_page_clipboard_validate_result
| -> compare_payloads) then requires the two byte-equal after the clear and
| halts on `illegal` when they are not: VEC:04 at gk_page_clipboard_fatal
| on every page-key + CLEAR (docs/contributing/FAILURE_MODES.md).
|
| Detour at the input layer's key dispatch (0x4003191c: `move.l d4,-(sp) /
| move.l d2,-(sp) / jsr (a0)`, the call her wrappers are reached through,
| return 0x40031922). When the handler about to run is the one the page-key
| layer's CLEAR or PASTE record holds (read from the record at run time:
| Octakit's recipe owns those two words, 0x400bab08 and 0x400baaee), the
| current part's working bytes are copied into its mirror first -- what a
| stock edit would have left. Her bytes are untouched; her checks run whole.
| Every register is preserved.

        .set    REC_CLEAR, 0x400bab08   | page-key layer: CLEAR's press handler (Octakit's wrapper)
        .set    REC_PASTE, 0x400baaee   | ... PASTE's
        .set    BANKPTR,   0x46c82456   | the current bank's blob
        .set    WORKOFF,   0x0008ed80   | its working parts (her GK_STOCK_BANK_WORKING_OFFSET)
        .set    PARTIDX,   0x100b14cf   | the current part (her GK_STOCK_CURRENT_PART_PRIMARY)
        .set    MIRROR,    0x100a4ece   | the SRAM mirror (her GK_STOCK_WORKING_PART_MIRROR_BASE)
        .set    PARTSZ,    0x18b2       | one part, 6322 bytes (her GK_PART_PAYLOAD_SIZE)
        .set    RESUME,    0x40031922   | the dispatch's `addq.l #8,%sp`

        .text
        .global osm_dispatch
osm_dispatch:
        cmpa.l  (REC_CLEAR).l,%a0
        beq.s   1f
        cmpa.l  (REC_PASTE).l,%a0
        bne.s   2f
1:      bsr.s   osm_sync
2:      move.l  %d4,-(%sp)
        move.l  %d2,-(%sp)
        jsr     (%a0)
        jmp     (RESUME).l

| the current part's working bytes into its mirror, a word at a time (the
| mirror's parts are two-byte aligned)
osm_sync:
        lea     (-16,%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        moveq   #0,%d0
        move.b  (PARTIDX).l,%d0
        moveq   #3,%d1
        cmp.l   %d1,%d0
        bhi.s   9f                      | not a part: leave both alone
        mulu.w  #PARTSZ,%d0
        move.l  (BANKPTR).l,%d1
        beq.s   9f                      | no bank yet
        movea.l %d1,%a0
        adda.l  #WORKOFF,%a0
        adda.l  %d0,%a0
        lea     (MIRROR).l,%a1
        adda.l  %d0,%a1
        move.l  #PARTSZ/2,%d1
1:      move.w  (%a0)+,(%a1)+
        subq.l  #1,%d1
        bne.s   1b
9:      movem.l (%sp),%d0-%d1/%a0-%a1
        lea     (16,%sp),%sp
        rts
