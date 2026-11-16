| SRC3 KEY -- [MIDI] in the audio editor is the SRC3 record key (8thmyth,
| 14 Nov 2026). The MKI has no [REC3]: from the editor a resample is one key
| away. One press starts the current track's recorder with SRC3 only (its
| RECORDING SETUP source; posted, so QREC applies); the next press stops it
| at once (the immediate mailbox, whatever RLEN). Outside the editor, or with
| the setting off, [MIDI] is stock's (the MIDI tracks).
|
| MKI only: the MKII has [REC3], so its key table stays stock and the model
| flag (0x46c8d18c, 1 on an MKII) sends every [MIDI] there to stock's.
| sk_press / sk_release are [MIDI]'s press and release longs in the MKI key
| table (stock 0x40055678 for both: its second argument tells them apart).
| The release is dropped in the editor so the MIDI page never opens there.
| LAZY CHOP holds [MIDI] in its own layer while open and calls whatever the
| table's press long holds (this, when SRC3 KEY is in the remix).

        .include "remix.inc"            | get_on (the setting)

        .equ    STOCK_MIDI, 0x40055678
        .equ    MKII_FLAG,  0x46c8d18c     | 1 on an MKII (PANEL.md section 4c)
        .equ    AED_WIN,    0x460e5e4c     | the editor's window, 0 when shut
        .equ    CUR_TRACK,  0x100b14cc
        .equ    VOICES,     0x800049d8     | + 0xa8 t: byte 1 = the recorder records
        .equ    VSTRIDE,    0xa8
        .equ    BANK_BLOB,  0x46c82456
        .equ    CUR_PARTB,  0x100b14cf
        .equ    PART_RSET,  0x602          | RECORDING SETUP, 12 bytes a track; +4 SRC3 (0 = "-")
        .equ    F_RECPOST,  0x40005178     | (track, word, 1)
        .equ    F_TOAST,    0x4005a2b8     | (text, duration)
        .equ    REC_SRC3,   0xc010         | (SRC3 0x4000 + 0x8000) | 0x10
        .equ    REC_HALT,   0x80
        .equ    REC_NOW,    0x46c7e9fa     | + 4t: the immediate mailbox

        .text
        .global sk_press, sk_release
sk_press:
        tst.l   (MKII_FLAG).l
        bne     8f
        tst.l   (AED_WIN).l
        beq     8f
        get_on  %d0
        tst.l   %d0
        bne     sk_toggle
8:      jmp     (STOCK_MIDI).l
sk_release:
        tst.l   (MKII_FLAG).l
        bne     8f
        tst.l   (AED_WIN).l
        beq     8f
        get_on  %d0
        tst.l   %d0
        beq     8f
        rts
8:      jmp     (STOCK_MIDI).l

sk_toggle:
        move.l  %d2,-(%sp)
        moveq   #0,%d2
        move.b  (CUR_TRACK).l,%d2
        and.l   #7,%d2                  | d2 = the track
        move.l  %d2,%d0
        move.l  #VSTRIDE,%d1
        mulu.l  %d1,%d0
        add.l   #VOICES+1,%d0
        move.l  %d0,%a0
        tst.b   (%a0)
        bne     3f                      | recording: stop
        moveq   #0,%d0                  | the track's RECORDING SETUP SRC3
        move.b  (CUR_PARTB).l,%d0
        move.l  #0x18b2,%d1
        mulu.l  %d1,%d0
        add.l   #0x8ed80+PART_RSET+4,%d0
        add.l   (BANK_BLOB).l,%d0
        move.l  %d2,%d1
        lsl.l   #2,%d1                  | 4t
        add.l   %d1,%d0
        add.l   %d1,%d0
        add.l   %d1,%d0                 | + 12t (no mulu.l #imm on ColdFire)
        move.l  %d0,%a0
        tst.b   (%a0)
        beq     2f
        pea     1.w
        move.l  #REC_SRC3,-(%sp)
        move.l  %d2,-(%sp)
        jsr     (F_RECPOST).l
        lea     12(%sp),%sp
        lea     msg_rec,%a0
        bra     9f
2:      lea     msg_off,%a0
        bra     9f
3:      move.l  %d2,%d1
        lsl.l   #2,%d1
        add.l   #REC_NOW,%d1
        move.l  %d1,%a0
        move.l  #REC_HALT,(%a0)
        pea     1.w
        pea     REC_HALT.w
        move.l  %d2,-(%sp)
        jsr     (F_RECPOST).l
        lea     12(%sp),%sp
        lea     msg_stop,%a0
9:      move.l  (%sp)+,%d2
        pea     0x30.w
        move.l  %a0,-(%sp)
        jsr     (F_TOAST).l
        addq.l  #8,%sp
        rts

        .data
        .balign 4
        .global sk_on
sk_on:      .long   1                   | the setting without BRAIN: on
msg_rec:    .asciz  "SRC3 RECORDING"
msg_stop:   .asciz  "RECORDING STOPPED"
msg_off:    .asciz  "SRC3 IS OFF (REC SETUP)"
