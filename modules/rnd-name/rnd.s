| RND NAME -- FUNC+CUE fills a random name in the name editor.
|
| Stock name-editor FUNC-held keys (0x400d0916) have REC/PLAY/STOP/NO for
| PASTE/CLEAR/COPY NAME. CUE is absent, so FUNC+CUE fell through to Part
| Reload. This unit replaces that key table (SymbolRef at 0x400d08f2) with
| stock plus CUE -> rnd_chord.
|
| Date + two pool words: CREATE NEW PROJECT, SAVE PROJECT AS, CHOOSE NEW
| PROJECT NAME, and COPY PROJECT (cp_named, when that module is in the
| remix). Words-only (no date): SAVE SAMPLE AS, NAME THE NEW DIR,
| NAME THE NEW SET, and KITS SAVE KIT (other DRAM callbacks). Rename /
| remarks / card: inert.
|
| Date is gated only on CB_SLOT (0x460e761a) — the editor's done-callback
| — never on the window title.
|
| Fill length follows the editor's ED_MAX (kits = 7). Short editors get
| one pool word; longer ones join two (64 x 64).

        .include "remix.inc"            | HAVE_COPY_PROJECT: 1 when COPY PROJECT is in the remix

        .text
        .globl  rnd_chord
        .balign 2

        .equ    CREATE_CB,  0x400644f0
        .equ    SAMPLE_CB1, 0x40024288
        .equ    SAMPLE_CB2, 0x400764dc
        .equ    SAVEAS_CB,  0x40063d30
        .equ    CHOOSE_CB,  0x40063b00
        .equ    NEWDIR_CB,  0x4006c264
        .equ    NEWSET_CB,  0x40080ee8
        .equ    CB_SLOT,    0x460e761a
        .equ    BUF_PTR,    0x460e761e
        .equ    ED_MAX,     0x400d0730
        .equ    CURSOR,     0x460e7438
        .equ    CUR_OFF,    0x460e748e
        .equ    FMT,        0x4007dd20
        .equ    STRLEN,     0x40013db0
        .equ    REFRESH,    0x4007dc84
        .equ    REDRAW,     0x4007dedc
        .equ    TEMPO24,    0x80001814
        .equ    CLOCKEST,   0x80001818
        .equ    RTC_RD,     0x4001c4d8
        .equ    BCD2BIN,    0x4001c31c
        .equ    SPRINTF,    0x40013a08
        .equ    POOL_MASK,  63
        .equ    DRAM_LO,    0x40a00000
        .equ    DRAM_HI,    0x4f000000

        .if     HAVE_COPY_PROJECT
        .extern cp_named                | COPY PROJECT's NAMEED done-cb (DRAM)
        .endif

| FUNC+CUE while the name editor's FUNC layer is up.
| d3 = 1 -> prepend date; d3 = 0 -> words only.
rnd_chord:
        movel   CB_SLOT,%d0
        moveq   #1,%d3
        cmpil   #CREATE_CB,%d0
        beqs    0f
        cmpil   #SAVEAS_CB,%d0         | SAVE PROJECT AS…
        beqs    0f
        cmpil   #CHOOSE_CB,%d0         | CHOOSE NEW PROJECT NAME
        beqs    0f
        .if     HAVE_COPY_PROJECT
        movel   #cp_named,%d1          | COPY PROJECT (same date template)
        cmpl    %d1,%d0
        beqs    0f
        .endif
        moveq   #0,%d3
        cmpil   #SAMPLE_CB1,%d0
        beqs    0f
        cmpil   #SAMPLE_CB2,%d0
        beqs    0f
        cmpil   #NEWDIR_CB,%d0
        beqs    0f
        cmpil   #NEWSET_CB,%d0
        beqs    0f
        | KITS SAVE KIT done-cb lives in the DRAM runtime
        cmpl    #DRAM_LO,%d0
        bcs     9f
        cmpl    #DRAM_HI,%d0
        bcc     9f
0:
        lea     %sp@(-28),%sp
        moveml  %d0-%d3/%a0-%a2,%sp@
        bsr     rnd_fill
        movel   BUF_PTR,%d0
        movel   %d0,%sp@-
        jsr     FMT
        addql   #4,%sp
        movel   BUF_PTR,%d0
        movel   %d0,%sp@-
        jsr     STRLEN
        addql   #4,%sp
        movel   %d0,%d1
        notl    %d1
        addl    %d1,%d1
        subxl   %d1,%d1
        moveal  ED_MAX,%a0
        andl    %d1,%d0
        cmpal   %d0,%a0
        bges    1f
        movel   %a0,%d0
1:
        movel   %d0,CURSOR
        clrl    CUR_OFF
        jsr     REFRESH
        moveml  %sp@,%d0-%d3/%a0-%a2
        lea     %sp@(28),%sp
        jmp     REDRAW
9:
        rts

| Fill BUF_PTR: optional date (d3), then one or two pool words.
| End sentinel = BUF_PTR + ED_MAX (fallback 26 if ED_MAX is 0).
rnd_fill:
        lea     %sp@(-8),%sp
        moveml  %d4/%a3,%sp@
        moveal  BUF_PTR,%a0
        tstl    %d3
        beqs    0f
        bsr     rnd_date
0:
        moveal  BUF_PTR,%a3
        movel   ED_MAX,%d4
        bne     1f
        moveq   #26,%d4
1:
        addal   %d4,%a3
        | room left; kits (max 7) get one word so it is not chopped mid-token
        movel   %a3,%d0
        subl    %a0,%d0
        cmpil   #8,%d0
        bcs     rnd_one

        bsr     rnd_rng
        and.l   #POOL_MASK,%d0
        lea     rnd_a,%a1
        bsr     rnd_nth
        move.l  %a1,%a2

        bsr     rnd_rng
        and.l   #POOL_MASK,%d0
        lea     rnd_b,%a1
        bsr     rnd_nth

2:
        move.b  %a2@+,%d0
        beq     3f
        cmpal   %a3,%a0
        bge     8f
        move.b  %d0,%a0@+
        bra     2b
3:
4:
        move.b  %a1@+,%d0
        beq     8f
        cmpal   %a3,%a0
        bge     8f
        move.b  %d0,%a0@+
        bra     4b

rnd_one:
        bsr     rnd_rng
        move.l  %d0,%d1
        and.l   #POOL_MASK,%d0
        lea     rnd_a,%a1
        btst    #6,%d1
        beqs    5f
        lea     rnd_b,%a1
5:
        bsr     rnd_nth
6:
        move.b  %a1@+,%d0
        beq     8f
        cmpal   %a3,%a0
        bge     8f
        move.b  %d0,%a0@+
        bra     6b
8:
        clr.b   %a0@
        moveml  %sp@,%d4/%a3
        lea     %sp@(8),%sp
        rts

| Write YYMMDD + space from the DS1390 into a0 (year, month, day).
| Returns with a0 advanced by 7. Caller pops (cdecl).
rnd_date:
        lea     %sp@(-20),%sp
        moveml  %d2-%d4/%a2-%a3,%sp@
        moveal  %a0,%a3
        lea     RTC_RD,%a2
        pea     7
        jsr     %a2@
        addql   #4,%sp
        movel   %d0,%sp@-
        jsr     BCD2BIN
        addql   #4,%sp
        movel   %d0,%d2
        pea     6
        jsr     %a2@
        addql   #4,%sp
        movel   %d0,%sp@-
        jsr     BCD2BIN
        addql   #4,%sp
        movel   %d0,%d3
        pea     5
        jsr     %a2@
        addql   #4,%sp
        movel   %d0,%sp@-
        jsr     BCD2BIN
        addql   #4,%sp
        movel   %d0,%d4
        movel   %d4,%sp@-
        movel   %d3,%sp@-
        movel   %d2,%sp@-
        pea     rnd_ymd
        movel   %a3,%sp@-
        jsr     SPRINTF
        lea     %sp@(20),%sp
        moveal  %a3,%a0
        lea     %a0@(7),%a0
        moveml  %sp@,%d2-%d4/%a2-%a3
        lea     %sp@(20),%sp
        rts

| a1 = table, d0 = index -> a1 = C string
rnd_nth:
        lsl.l   #2,%d0
        add.l   %d0,%a1
        move.l  %a1@,%a1
        rts

rnd_rng:
        move.l  rnd_state,%d0
        bne     1f
        move.l  TEMPO24,%d0
        move.l  CLOCKEST,%d1
        eor.l   %d1,%d0
        move.l  #0xA5A5A5A5,%d1
        eor.l   %d1,%d0
        bne     1f
        moveq   #1,%d0
1:
        move.l  #1664525,%d1
        mulu.l  %d1,%d0
        add.l   #1013904223,%d0
        move.l  %d0,rnd_state
        rts

        .data
        .balign 4
rnd_ymd:
        .asciz  "%02d%02d%02d "
        .balign 4
rnd_state:
        .long   0

        .balign 4
rnd_a:
        .long   wa0,wa1,wa2,wa3,wa4,wa5,wa6,wa7
        .long   wa8,wa9,wa10,wa11,wa12,wa13,wa14,wa15
        .long   wa16,wa17,wa18,wa19,wa20,wa21,wa22,wa23
        .long   wa24,wa25,wa26,wa27,wa28,wa29,wa30,wa31
        .long   wa32,wa33,wa34,wa35,wa36,wa37,wa38,wa39
        .long   wa40,wa41,wa42,wa43,wa44,wa45,wa46,wa47
        .long   wa48,wa49,wa50,wa51,wa52,wa53,wa54,wa55
        .long   wa56,wa57,wa58,wa59,wa60,wa61,wa62,wa63
rnd_b:
        .long   wb0,wb1,wb2,wb3,wb4,wb5,wb6,wb7
        .long   wb8,wb9,wb10,wb11,wb12,wb13,wb14,wb15
        .long   wb16,wb17,wb18,wb19,wb20,wb21,wb22,wb23
        .long   wb24,wb25,wb26,wb27,wb28,wb29,wb30,wb31
        .long   wb32,wb33,wb34,wb35,wb36,wb37,wb38,wb39
        .long   wb40,wb41,wb42,wb43,wb44,wb45,wb46,wb47
        .long   wb48,wb49,wb50,wb51,wb52,wb53,wb54,wb55
        .long   wb56,wb57,wb58,wb59,wb60,wb61,wb62,wb63

wa0: .asciz "FOG"
wa1: .asciz "DUB"
wa2: .asciz "DARK"
wa3: .asciz "COLD"
wa4: .asciz "DRONE"
wa5: .asciz "SLEEP"
wa6: .asciz "WARE"
wa7: .asciz "ECHO"
wa8: .asciz "VOID"
wa9: .asciz "SUB"
wa10: .asciz "LATE"
wa11: .asciz "GRID"
wa12: .asciz "SOFT"
wa13: .asciz "DEEP"
wa14: .asciz "SLOW"
wa15: .asciz "MIST"
wa16: .asciz "RAW"
wa17: .asciz "WET"
wa18: .asciz "DRY"
wa19: .asciz "LOW"
wa20: .asciz "HI"
wa21: .asciz "DIM"
wa22: .asciz "WARM"
wa23: .asciz "THIN"
wa24: .asciz "THICK"
wa25: .asciz "SHARP"
wa26: .asciz "BLUNT"
wa27: .asciz "FAST"
wa28: .asciz "IDLE"
wa29: .asciz "LOUD"
wa30: .asciz "MUTE"
wa31: .asciz "NOISE"
wa32: .asciz "GLASS"
wa33: .asciz "IRON"
wa34: .asciz "RUST"
wa35: .asciz "DUST"
wa36: .asciz "ASH"
wa37: .asciz "SMOKE"
wa38: .asciz "STEAM"
wa39: .asciz "ICE"
wa40: .asciz "STONE"
wa41: .asciz "CLAY"
wa42: .asciz "BONE"
wa43: .asciz "WIRE"
wa44: .asciz "TAPE"
wa45: .asciz "FILM"
wa46: .asciz "VHS"
wa47: .asciz "CRT"
wa48: .asciz "NEON"
wa49: .asciz "ACID"
wa50: .asciz "BASE"
wa51: .asciz "PHASE"
wa52: .asciz "PULSE"
wa53: .asciz "SWEEP"
wa54: .asciz "GLIDE"
wa55: .asciz "SNAP"
wa56: .asciz "CLICK"
wa57: .asciz "THUMP"
wa58: .asciz "RUMBLE"
wa59: .asciz "CRACK"
wa60: .asciz "BLEED"
wa61: .asciz "GHOST"
wa62: .asciz "SHADOW"
wa63: .asciz "TRACE"

wb0: .asciz "BED"
wb1: .asciz "LOOP"
wb2: .asciz "WASH"
wb3: .asciz "TAPE"
wb4: .asciz "CHAIN"
wb5: .asciz "VERB"
wb6: .asciz "SCENE"
wb7: .asciz "LOCK"
wb8: .asciz "HUM"
wb9: .asciz "PAD"
wb10: .asciz "GATE"
wb11: .asciz "YARD"
wb12: .asciz "HAZE"
wb13: .asciz "DRIFT"
wb14: .asciz "POOL"
wb15: .asciz "STEM"
wb16: .asciz "HIT"
wb17: .asciz "KICK"
wb18: .asciz "SNAR"
wb19: .asciz "CLAP"
wb20: .asciz "HAT"
wb21: .asciz "TOM"
wb22: .asciz "RIM"
wb23: .asciz "CLICK"
wb24: .asciz "BASS"
wb25: .asciz "LEAD"
wb26: .asciz "ARP"
wb27: .asciz "SEQ"
wb28: .asciz "FX"
wb29: .asciz "BUS"
wb30: .asciz "SEND"
wb31: .asciz "RET"
wb32: .asciz "ROOM"
wb33: .asciz "HALL"
wb34: .asciz "PLATE"
wb35: .asciz "SPRING"
wb36: .asciz "CAB"
wb37: .asciz "AMP"
wb38: .asciz "PEDAL"
wb39: .asciz "RACK"
wb40: .asciz "TAKE"
wb41: .asciz "CLIP"
wb42: .asciz "SHOT"
wb43: .asciz "PASS"
wb44: .asciz "RUN"
wb45: .asciz "CUE"
wb46: .asciz "DROP"
wb47: .asciz "RISE"
wb48: .asciz "SLOT"
wb49: .asciz "BANK"
wb50: .asciz "PART"
wb51: .asciz "PATT"
wb52: .asciz "KIT"
wb53: .asciz "SET"
wb54: .asciz "DIR"
wb55: .asciz "FILE"
wb56: .asciz "WAVE"
wb57: .asciz "BUF"
wb58: .asciz "RING"
wb59: .asciz "CORE"
wb60: .asciz "NODE"
wb61: .asciz "PORT"
wb62: .asciz "LANE"
wb63: .asciz "TRACK"

| Name-editor FUNC-held key table: stock 0x400d0916 plus CUE -> rnd_chord.
| Record is 0x1a bytes: code, press, release, +0xa, +0xe, +0x12, +0x16.
        .balign 2
        .globl  rnd_func_keys
rnd_func_keys:
        | REC 0x29 PASTE NAME
        .word   0x2900
        .long   0x4007e36c, 0, 0, 0, 0, 0
        | PLAY 0x28 CLEAR NAME
        .word   0x2800
        .long   0x4007e324, 0, 0, 0, 0, 0
        | STOP 0x27 COPY NAME
        .word   0x2700
        .long   0x4007e2a4, 0, 0, 0, 0, 0
        | NO 0x32
        .word   0x3200
        .long   0x4007e21c, 0, 0x4007e21c, 0, 0, 0x000f0004
        | CUE 0x2a -> random name (gated in rnd_chord)
        .word   0x2a00
        .long   rnd_chord, 0, 0, 0, 0, 0
        | end
        .word   0xff00
        .long   0, 0, 0, 0, 0, 0

        .balign 2
