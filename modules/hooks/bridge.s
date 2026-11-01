| HOOKS -- the bridged stock sites (modules/hooks/manifest.py says why each).
| remix.inc sets hk_<bridge> to 1 for each bridge this remix needs and fills
| its macro; a bridge that is off emits nothing.
        .text
        .include "remix.inc"

        .if     hk_status_icon
| renderer 0x4004bee2: `jsr hk_status_icon` replaces `lea 0x400c0cb8,%a0`.
| Each participant is called as its own detour would be: d3 the track, a4
| the state; each may rewrite a4 and ends with the lea redone, so a0 is the
| cache on return. d0, d1 and a1 are reloaded by the renderer before use.
        .global hk_status_icon
hk_status_icon:
        hk_status_icon_chain
        rts
        .endif

        .if     hk_track_key
| the [TRACK]-held layer's records: code, 0, press, release, 16 zero bytes
| (stock's layout, 0x1a bytes; repeat 0), then stock's 0xff terminator.
        .macro  HKREC code, press, release
        .byte   \code, 0
        .long   \press, \release
        .space  16
        .endm
        .balign 2
        .global hk_track_keys
hk_track_keys:
        hk_track_key_records
        .byte   0xff, 0
        .space  24
        .endif

        .if     hk_frame_tail
| frame interrupt epilogue 0x4000d9a6, jmp'd to on every exit path: each
| participant (built with HK_FRAME_TAIL: it returns), then the epilogue.
| d0-a6 are saved at (sp) by the prologue, so every register is free.
        .global hk_frame_tail
hk_frame_tail:
        hk_frame_tail_chain
        movem.l (%sp),%d0-%d7/%a0-%a6   | the stock epilogue, once
        lea     252(%sp),%sp
        .global hk_frame_tail_rte       | (a label only: verify_hooks stops here)
hk_frame_tail_rte:
        rte
        .endif

        .if     hk_frame_entry
| frame interrupt entry 0x4000aad0: the stock prologue once, then each
| participant (built with HK_FRAME_ENTRY: entered after its replay, it
| returns), then the interrupt's body.
        .global hk_frame_entry
hk_frame_entry:
        lea     -252(%sp),%sp           | the stock prologue, once
        movem.l %d0-%d7/%a0-%a6,(%sp)
        hk_frame_entry_chain
        jmp     (0x4000aad8).l
        .endif

        .if     hk_boot
| 0x40000512: `jsr hk_boot` replaces `jsr 0x4000f938`. Each participant but
| the last is called (built with HK_BOOT: it returns); the last tail-jumps
| to 0x4000f938, which returns to the boot.
        .global hk_boot
hk_boot:
        hk_boot_chain
        .endif

        .if     hk_chromatic
| CHROMATIC, BLACKPYRAMIDS_303 beside SCALE QUANTIZER. Each stub is entered
| as the participants' own detours were: same registers, same stack (the
| octave keys' handler reads the key at 8(%sp)).
| .hk_is_bp: Z clear when the UI track (0x100b14cc) is a BLACKPYRAMIDS track
| (its ot_track_is, C ABI). Keeps every register; movem, lea and rts keep CCR.
.hk_is_bp:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        moveq   #0,%d0
        move.b  0x100b14cc,%d0
        move.l  %d0,-(%sp)
        jsr     ot_track_is
        addq.l  #4,%sp
        tst.l   %d0
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        rts
| .hk_sanitize: ot_chrom_sanitize (an octave above 1 on another track -> 0;
| nothing on a BLACKPYRAMIDS track). Keeps every register.
.hk_sanitize:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     ot_chrom_sanitize
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        rts

        .global hk_octkey, hk_keyidx, hk_octdraw
| 0x40045918, FUNC + LEFT/RIGHT: both handlers go on at 0x40045920.
hk_octkey:
        bsr.w   .hk_is_bp
        beq.s   1f
        jmp     ot_oct_hook
1:      bsr.w   .hk_sanitize
        jmp     qz_octkey
| 0x40050254, the key's index: both go on at 0x4005025c (8 bytes replayed).
hk_keyidx:
        bsr.w   .hk_sanitize
        jmp     qz_keyidx
| 0x40044968, the keyboard picture: a BLACKPYRAMIDS track the full image
| (its own branch, d1 = 1); another track SCALE QUANTIZER's, which goes on
| at stock's bne 0x40044970.
hk_octdraw:
        bsr.w   .hk_is_bp
        beq.s   1f
        moveq   #1,%d1
        jmp     (0x40044988).l
1:      jmp     qz_octdraw
        .endif

        .if     hk_machine_rows
| the track's machine list, 5 + N rows (each machine module's, 5 .. 4 + N,
| machine_rows) in six on screen. The list at 0x460e7386: +0 the top row, +8 the cursor, +16 the
| count. The drawer's loop (0x4007864c..0x400787b2) keeps d2 the screen row,
| a2 its y, d3 the name formatter, d4 the surface, d7 the text drawer; stock
| draws and boxes row d2, which is right only while the list never scrolls.
| Its cursor bar already draws at cursor - top. d0, d1, a0, a1 are scratch
| at both sites (reloaded by the code each returns to).
        .set    MC_LIST, 0x460e7386
        .global hk_mc_name, hk_mc_box
| 0x40078678, the loop's head (`moveq #4,%d0 ; cmp.l %d2,%d0 ; blt.s`):
| row top + d2's name, as stock's call does, then on at 0x400786a2.
hk_mc_name:
        move.l  (MC_LIST).l,%d0
        add.l   %d2,%d0
        cmp.l   (MC_LIST+16).l,%d0
        bge.s   1f
        move.l  %d0,-(%sp)
        movea.l %d3,%a0
        jsr     (%a0)
        move.l  %d0,-(%sp)
        moveq   #-1,%d1
        move.l  %d1,-(%sp)
        pea     1(%a2)
        pea     0x5.w
        move.l  %d4,-(%sp)
        pea     (0x400ba876).l
        movea.l %d7,%a1
        jsr     (%a1)
        lea     28(%sp),%sp
1:      jmp     (0x400786a2).l
| 0x400786c8, a0 the UI track's machine byte: the box on screen row d2 when
| that track's row (the head machine's type routine, which asks the others
| down the chain: 5 .. 4 + N for a signed track) is top + d2.
hk_mc_box:
        mvs.b   (%a0),%d0
        hk_mc_type
        move.l  (MC_LIST).l,%d1
        add.l   %d2,%d1
        cmp.l   %d1,%d0
        bne.s   1f
        cmp.l   (MC_LIST+16).l,%d1
        bge.s   1f
        jmp     (0x400786d4).l
1:      jmp     (0x400786fc).l
        .endif
