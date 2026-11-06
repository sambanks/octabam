| SCENES P2 -- scene locks and the crossfader for FX1/FX2 page 2.
|
| Stock's scene block is 32 bytes a track a scene and the frame builder
| morphs bytes 0..29 (page 1 of the five pages) into the DSP frame every
| frame; page 2 has no byte and the loop stops at halfword 17
| (docs/firmware/MIDI.md Appendix C). This unit adds page 2:
|
| * the CELLS: bytes 30 and 31 of each track's 32-byte block in the stock
|   scene block (Part +0x8f3e2 + scene*0x100 + track*0x20), which the frame
|   builder skips (0x4000cef6) and stock fills with 0xff. A scene's eight
|   cells hold up to eight page-2 locks of any of its tracks:
|       byte 30 = track<<4 | fx1<<3 | slot2 (0..5), bit 7 set = empty
|       byte 31 = value
|   Stock moves the whole block: Part Save / Reload / paste, Project Save,
|   the CS1 copy, KITS's Kits, and scene copy, paste, undo and clear
|   (docs/firmware/PARTS.md section 9 says why not the Part's tail).
| * the FRAME PASS (frame_hook, detour at 0x4000cf40, after the stock morph,
|   before the transfer): per track, the current (bank, part, scene A,
|   scene B) key is compared with a cache; on a change the track's locks are
|   unpacked from the A and B scenes' cells into P2W (A and B values per slot, 0xff = none).
|   Then every locked slot is lerped with the stock weight table
|   (0x80003c60: hi word = -xf*258, Q15) into the voice record's page-2
|   bytes (FX2 halfwords 24..26 = bytes 48..53, FX1 18..20 = 36..41), an
|   unlocked side taking the knob byte already in the record. A select
|   (descriptor count < 128) snaps: the A side from the fader's midpoint up.
| * the EDITOR HOOKS (the FX2 page-2 editor 0x4003a9dc and FX1's 0x4003abe4,
|   detoured at entry): with a scene held (0x460d169c: 1 = A, else B) a
|   page-2 knob turn edits the held scene's lock instead of the Part --
|   the slot's own encoder hook and clamp (descriptor +0x12a, +0x6a, +0x9a),
|   the cell in the working window and its SRAM twin (0x100a4ece + part*
|   0x18b2), the stock scene editor's dirty flags, the slot's redraw flag.
|
| Registers at the frame site: d0-d7, a0-a5 are dead until the replayed
| `moveal %sp@(128),%a2` (a3/a4/a5 are reloaded at 0x4000cf4a..0x4000cf5a);
| sp@(136) is the frame's voice-record base (this ping).

        .set    SCENE_HELD, 0x460d169c
        .set    TRK_BANK,   0x8000182a      | per-track bank byte (0xff = none)
        .set    TRK_PART,   0x80001832      | per-track part byte
        .set    BLOB,       0x400e21e0      | the bank blob the frame ISR addresses
        .set    BANK_STRIDE, 0x9b340
        .set    PART_STRIDE, 0x18b2
        .set    SEL_OFF,    0x8ed90         | part: scene A byte, B at +1
        .set    ID1_OFF,    0x8ed80         | part: FX1 id per track
        .set    ID2_OFF,    0x8ed88         | part: FX2 id per track
        .set    P1P2_OFF,   0x8f07e         | part: FX1 page 2, +track*30+slot2
        .set    P2P2_OFF,   0x8f084         | part: FX2 page 2
        .set    CELL0,      0x8f400         | part: scene 0's cell 0 (0x8f3e2 + 30)
        .set    NCELL,      8               | cells a scene, 0x20 apart
        .set    WEIGHTS,    0x80003c60      | long per track: hi = -xf*258
        .set    SCENE_A_OFF, 0x80000006     | nonzero: scene A disabled
        .set    SCENE_B_OFF, 0x80000007
        .set    DESC1,      0x400d5f58      | FX1 descriptor pointers by id
        | DESC2 (FX2 descriptor pointers by id) comes from remix.inc
        .set    DBPTR,      0x46c82456      | long: the Part DB base (UI code)
        .set    PART_DISP,  0x100b14cf      | the part the panel edits
        .set    TRACK_CUR,  0x80000000
        .set    SRAM_PART,  0x100a4ece      | + part*0x18b2: the copy that survives a power cycle
        .set    ENC_DEFAULT, 0x4003240c     | the default encoder hook
        .set    DIRTY,      0x40027e00
        .set    REDRAW,     0x46c7d244
        .set    EDIT_A,     0x460d1694
        .set    EDIT_B,     0x460d1698
        .set    KROWS,      0x46100b18      | bytes: the panel's held keys, code = row*8 + bit
        .set    KFUNC,      0x2d            | FUNCTION: row 5, bit 5

        .text
        .globl  frame_hook, fx2_edit_hook, fx1_edit_hook, fx2_stock, fx1_stock

| ---------------------------------------------------------------- frame ----
frame_hook:
        moveal  %sp@(136),%a5          | a5 = voice records, 64 B a track
        lea     P2W,%a4                | a4 = this track's cache row
        moveq   #0,%d7                 | d7 = track
tloop:  lea     TRK_BANK,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d7:l),%d0      | bank
        cmpil   #0xff,%d0
        beq     tnext
        moveq   #0,%d1
        moveb   %a0@(8,%d7:l),%d1      | part
        movel   #BANK_STRIDE,%d2
        mulu.l  %d0,%d2
        movel   #PART_STRIDE,%d3
        mulu.l  %d1,%d3
        addl    %d3,%d2
        addil   #BLOB,%d2
        moveal  %d2,%a3                | a3 = the track's part window
        lsll    #8,%d0
        orl     %d1,%d0
        lsll    #8,%d0
        addil   #SEL_OFF,%d2
        moveal  %d2,%a0
        moveq   #0,%d1
        moveb   %a0@,%d1               | scene A
        orl     %d1,%d0
        lsll    #8,%d0
        moveq   #0,%d1
        moveb   %a0@(1),%d1            | scene B
        orl     %d1,%d0                | d0 = key
        cmpl    %a4@,%d0
        beq.s   cached
        bsr.w   unpack                 | a3, a4, d0 (key), d7 (track)
cached: movel   %a4@(4),%d0            | any lock at all?
        andl    %a4@(8),%d0
        andl    %a4@(12),%d0
        andl    %a4@(16),%d0
        andl    %a4@(20),%d0
        andl    %a4@(24),%d0
        addql   #1,%d0
        beq     tnext
        moveq   #0,%d5                 | d5 = disabled sides: bit 0 A, bit 1 B
        tstb    SCENE_A_OFF
        beq.s   fa
        moveq   #1,%d5
fa:     tstb    SCENE_B_OFF
        beq.s   fb
        addql   #2,%d5
fb:     cmpil   #3,%d5
        beq     tnext                  | both off: stock skips the morph too
        lea     WEIGHTS,%a0
        movel   %a0@(0,%d7:l:4),%d6
        swap    %d6
        extl    %d6
        negl    %d6                    | d6 = wA = xf*258 (0..0x8000)
        movel   %d7,%d0
        lsll    #6,%d0
        lea     %a5@(0,%d0:l),%a1      | a1 = this track's voice record
        | FX2: id -> descriptor, locks at a4@(4) (A) / a4@(10) (B), bytes 48..53
        movel   %a3,%d0
        addil   #ID2_OFF,%d0
        addl    %d7,%d0
        moveal  %d0,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        lea     DESC2,%a0
        moveal  %a0@(0,%d0:l:4),%a2    | a2 = descriptor (0 = none)
        lea     %a4@(4),%a0
        moveq   #48,%d4
        bsr.w   morph6
        | FX1: locks at a4@(16) / a4@(22), bytes 36..41
        movel   %a3,%d0
        addil   #ID1_OFF,%d0
        addl    %d7,%d0
        moveal  %d0,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        lea     DESC1,%a0
        moveal  %a0@(0,%d0:l:4),%a2
        lea     %a4@(16),%a0
        moveq   #36,%d4
        bsr.w   morph6
tnext:  lea     %a4@(32),%a4
        addql   #1,%d7
        cmpil   #8,%d7
        bne     tloop
        moveal  %sp@(128),%a2          | the displaced pair, then on
        addal   #0x80000660,%a2
        jmp     0x4000cf4a

| morph6: six slots. a0 = A locks (B at a0@(6)), a1 = record, a2 = descriptor
| or 0, d4 = record byte offset of slot 0, d5 = disabled sides, d6 = wA.
| Clobbers d0-d3, keeps d4-d7 and a0-a5.
morph6: movel   %d4,%sp@-
        movel   %a3,%sp@-
        moveq   #0,%d3                 | d3 = k
mloop:  moveq   #0,%d0
        moveb   %a0@(0,%d3:l),%d0      | A
        moveq   #0,%d1
        moveb   %a0@(6,%d3:l),%d1      | B
        btst    #0,%d5
        beq.s   ma
        moveq   #-1,%d0
        andil   #0xff,%d0
ma:     btst    #1,%d5
        beq.s   mb
        moveq   #-1,%d1
        andil   #0xff,%d1
mb:     movel   %d0,%d2
        andl    %d1,%d2
        cmpil   #0xff,%d2
        beq.s   mnext                  | neither side locked
        moveq   #0,%d2
        moveb   %a1@(0,%d4:l),%d2      | the knob, as the copier left it
        cmpil   #0xff,%d0
        bne.s   mA
        movel   %d2,%d0
mA:     cmpil   #0xff,%d1
        bne.s   mB
        movel   %d2,%d1
mB:     movel   %a2,%d2
        beq.s   mlerp                  | no descriptor: a plain lerp
        movel   %d3,%d2
        addql   #6,%d2
        lsll    #2,%d2
        addl    %a2,%d2
        moveal  %d2,%a3
        movel   %a3@(0x9a),%d2         | the slot's value count
        cmpil   #128,%d2
        bge.s   mlerp
        cmpil   #0x4000,%d6            | a select snaps at the midpoint
        blt.s   msel_b
        movel   %d0,%d2
        bra.s   mstore
msel_b: movel   %d1,%d2
        bra.s   mstore
mlerp:  movel   %d6,%d2
        mulu.l  %d2,%d0                | A*wA
        movel   #0x8000,%d2
        subl    %d6,%d2
        mulu.l  %d2,%d1                | B*wB
        addl    %d1,%d0
        addil   #0x4000,%d0
        lsrl    #8,%d0
        lsrl    #7,%d0                 | (A*wA + B*wB + 0.5) >> 15
        movel   %d0,%d2
mstore: moveb   %d2,%a1@(0,%d4:l)
mnext:  addql   #1,%d4
        addql   #1,%d3
        cmpil   #6,%d3
        bne     mloop
        moveal  %sp@+,%a3
        movel   %sp@+,%d4
        rts

| unpack: a3 = part window, a4 = cache row, d0 = key, d7 = track. Fills the
| row's 24 lock bytes from scene A's and scene B's cells. Clobbers d0-d6,
| a0, a1.
unpack: movel   %d0,%a4@
        moveq   #-1,%d1
        movel   %d1,%a4@(4)
        movel   %d1,%a4@(8)
        movel   %d1,%a4@(12)
        movel   %d1,%a4@(16)
        movel   %d1,%a4@(20)
        movel   %d1,%a4@(24)
        movel   %d0,%d5
        lsrl    #8,%d5
        andil   #0xff,%d5              | d5 = scene A
        movel   %d0,%d6
        andil   #0xff,%d6              | d6 = scene B
        moveal  %a4,%a1                | the A sides
        movel   %d5,%d1
        bsr.s   ucells
        lea     %a4@(6),%a1            | the B sides
        movel   %d6,%d1
| ucells: d1 = scene, a1 = the row's side base, a3, d7 as above. A lock of
| FX2 slot k goes to a1@(4 + k), FX1's to a1@(16 + k). Clobbers d1-d4, a0.
ucells: cmpil   #15,%d1
        bhi.s   ucdone
        lsll    #8,%d1
        addl    %a3,%d1
        addil   #CELL0,%d1
        moveal  %d1,%a0                | a0 = the scene's cell 0
        moveq   #NCELL,%d3
ucloop: moveq   #0,%d1
        moveb   %a0@,%d1               | track<<4 | fx1<<3 | slot2
        btst    #7,%d1
        bne.s   ucnext                 | empty
        movel   %d1,%d2
        lsrl    #4,%d2
        cmpl    %d7,%d2
        bne.s   ucnext
        movel   %d1,%d4
        andil   #7,%d4
        cmpil   #6,%d4
        bge.s   ucnext
        addql   #4,%d4                 | row offset of slot2 on the FX2 side
        btst    #3,%d1
        beq.s   ucfx
        addil   #12,%d4                | FX1
ucfx:   moveb   %a0@(1),%d2            | the value
        moveb   %d2,%a1@(0,%d4:l)
ucnext: lea     %a0@(32),%a0
        subql   #1,%d3
        bne.s   ucloop
ucdone: rts

| --------------------------------------------------------------- editors ----
| Entry state of the stock editors: sp@ = return, sp@(4) = slot2, sp@(8) = ticks.
| No scene held: on to P2_NEXT2 / P2_NEXT1 with the entry state untouched;
| `remix.inc` sets them to fx2_stock / fx1_stock (the displaced prologue,
| then the stock body). The detours displace EIGHT bytes (lea + movem):
| fx2_stock / fx1_stock continue at entry+8, where the stock
| `moveal %sp@(32),%a2` must still be (padded to twelve until 28 Sep 2026,
| that instruction was a nop, and under Octakit's trampoline the body
| read a garbage slot: every page-2 turn halted, rig-kits, bottleservice).
        .include "remix.inc"
fx2_edit_hook:
        tstl    SCENE_HELD
        beq.s   fx2_next
        movel   %sp@(4),%d1
        cmpil   #5,%d1
        bhi.s   fx2_next
        moveq   #1,%d0
        bra.s   edit
fx2_next:
        jmp     P2_NEXT2
fx2_stock:
        lea     %sp@(-28),%sp          | the displaced prologue, then on
        movem.l %d2-%d5/%a2-%a4,%sp@
        jmp     0x4003a9e4
fx1_edit_hook:
        tstl    SCENE_HELD
        beq.s   fx1_next
        movel   %sp@(4),%d1
        cmpil   #5,%d1
        bhi.s   fx1_next
        moveq   #0,%d0
        bra.s   edit
fx1_next:
        jmp     P2_NEXT1
fx1_stock:
        lea     %sp@(-28),%sp
        movem.l %d2-%d5/%a2-%a4,%sp@
        jmp     0x4003abec

| edit: d0 = kind (1 FX2, 0 FX1). d2 slot2, d3 ticks, d4 track, d5 part,
| d6 kind, d7 held scene; a2 descriptor, a3 part window, a4 the scene's cell 0,
| a5 the cell, a6 its key byte.
| With FUNC held the turn removes the lock instead of moving it.
edit:   lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %d0,%d6
        movel   %sp@(48),%d2
        movel   %sp@(52),%d3
        moveq   #0,%d4
        moveb   TRACK_CUR,%d4
        moveq   #0,%d5
        moveb   PART_DISP,%d5
        movel   DBPTR,%d0
        movel   #PART_STRIDE,%d1
        mulu.l  %d5,%d1
        addl    %d1,%d0
        moveal  %d0,%a3                | a3 = the edited part's window
        addil   #SEL_OFF,%d0
        moveal  %d0,%a0
        movel   SCENE_HELD,%d1
        cmpil   #1,%d1
        beq.s   eselA
        addql   #1,%a0
eselA:  moveq   #0,%d7
        moveb   %a0@,%d7               | d7 = the held scene
        movel   %d7,%d0
        lsll    #8,%d0
        addl    %a3,%d0
        addil   #CELL0,%d0
        moveal  %d0,%a4                | a4 = the held scene's cell 0
        movel   %d4,%d0
        lsll    #4,%d0
        orl     %d2,%d0
        tstl    %d6
        bne.s   eb1
        addql   #8,%d0                 | d0 = track<<4 | fx1<<3 | slot2
eb1:    moveal  %d0,%a6
        bsr.w   cfind                  | -> a5 = the cell or 0
        moveq   #0,%d0
        moveb   KROWS+(KFUNC>>3),%d0
        btst    #(KFUNC&7),%d0
        beq.s   eturn
        movel   %a5,%d0                | FUNC held: remove the lock
        beq.w   edone
        moveq   #-1,%d0
        moveb   %d0,%a5@
        bra.w   ecommit
eturn:  movel   %a5,%d0
        beq.s   eknob
        moveq   #0,%d0
        moveb   %a5@(1),%d0            | the lock's value
        bra.s   ecur
eknob:  movel   %d4,%d0                | the Part's page-2 byte
        moveq   #30,%d1
        mulu.l  %d1,%d0
        addl    %d2,%d0
        addl    %a3,%d0
        tstl    %d6
        beq.s   ek1
        addil   #P2P2_OFF,%d0
        bra.s   ek2
ek1:    addil   #P1P2_OFF,%d0
ek2:    moveal  %d0,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
ecur:   movel   %a3,%d1                | d0 = current; descriptor from the id
        addl    %d4,%d1
        tstl    %d6
        beq.s   ei1
        addil   #ID2_OFF,%d1
        moveal  %d1,%a0
        moveq   #0,%d1
        moveb   %a0@,%d1
        lea     DESC2,%a0
        bra.s   ei2
ei1:    addil   #ID1_OFF,%d1
        moveal  %d1,%a0
        moveq   #0,%d1
        moveb   %a0@,%d1
        lea     DESC1,%a0
ei2:    moveal  %a0@(0,%d1:l:4),%a2    | a2 = descriptor
        movel   %d2,%d1
        addql   #6,%d1
        lsll    #2,%d1
        moveal  %a2,%a0
        addal   %d1,%a0
        moveal  %a0@(0x12a),%a1        | the slot's encoder hook
        movel   %a1,%d1
        bne.s   ehook
        lea     ENC_DEFAULT,%a1
ehook:  movel   %d0,%sp@-              | hook(slot2, ticks, current) -> d0
        movel   %d3,%sp@-
        movel   %d2,%sp@-
        jsr     %a1@
        lea     %sp@(12),%sp
        mvs.w   %d0,%d0
        movel   %d2,%d1
        addql   #6,%d1
        lsll    #2,%d1
        moveal  %a2,%a0
        addal   %d1,%a0
        movel   %a0@(0x6a),%d1         | clamp to min .. min + count - 1
        cmpl    %d1,%d0
        bge.s   ec1
        movel   %d1,%d0
ec1:    addl    %a0@(0x9a),%d1
        subql   #1,%d1
        cmpl    %d1,%d0
        ble.s   ec2
        movel   %d1,%d0
ec2:    movel   %a5,%d1
        bne.s   estore
        bsr.w   cempty                 | -> a5 = a free cell or 0
        movel   %a5,%d1
        beq.w   edone                  | eight locks in the scene: the turn is dropped
        moveb   %d0,%a5@(1)            | the value, then the cell's key: the
        movel   %a6,%d1                | frame ISR reads the key first
        moveb   %d1,%a5@
        bra.s   ecommit
estore: moveb   %d0,%a5@(1)
ecommit:
        bsr.w   ccommit                | a3 = window, a5 = cell, d5 = part
        movel   %d2,%d1                | the slot's redraw flag, as the editor sets it
        movel   %d1,%d0
        lsll    #2,%d0
        addl    %d0,%d1
        addql   #1,%d1
        lsll    #2,%d1
        lea     REDRAW,%a0
        moveq   #20,%d0
        movel   %d0,%a0@(0,%d1:l)
        moveq   #1,%d0
        movel   %d0,EDIT_A
        movel   %d0,EDIT_B
edone:  moveq   #0,%d0
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| scene_knob_hook: 0x40053498(encoder, ticks), stock's scene-lock knob
| handler. A scene key's press installs it as every encoder's handler
| (0x46c7dede + 20 * encoder, written by 0x40031406), over the SETUP
| window's page-2 editor, so with a scene held a SETUP turn never reaches
| fx2_edit_hook / fx1_edit_hook (measured under the port, 5 Nov 2026: zero
| calls of 0x4003a9dc with SCENE A held, three without). With the FX1 or
| FX2 SETUP window open (0x460d175c, 0x460d1684 = 3 / 4), audio mode and a
| knob 0..5, the turn goes to the matching edit hook; the entry state is
| the editors' own (sp@(4) = slot, sp@(8) = ticks). Anything else replays
| the displaced prologue and continues in stock.
        .set    WINDOW,     0x460d175c
        .set    PAGEKIND,   0x460d1684
        .set    MIDIMODE,   0x80000012
        .globl  scene_knob_hook
scene_knob_hook:
        tstl    WINDOW
        beq.s   sk_stock
        tstl    SCENE_HELD
        beq.s   sk_stock
        tstl    MIDIMODE
        bne.s   sk_stock
        movel   %sp@(4),%d1
        cmpil   #5,%d1
        bhi.s   sk_stock
        movel   PAGEKIND,%d0
        cmpil   #4,%d0
        beq.w   fx2_edit_hook
        cmpil   #3,%d0
        beq.w   fx1_edit_hook
sk_stock:
        lea     %sp@(-36),%sp          | the displaced prologue, then on
        movem.l %d2-%d7/%a2-%a4,%sp@
        jmp     0x400534a0

| ----------------------------------------------------------- the cells ----
| cfind: a4 = a scene's cell 0, d0 = the key byte -> a5 = its cell, or 0.
| Clobbers d1, a0.
cfind:  moveal  %a4,%a0
        moveq   #NCELL,%d1
        suba.l  %a5,%a5
cfloop: cmpb    %a0@,%d0
        beq.s   cfhit
        lea     %a0@(32),%a0
        subql   #1,%d1
        bne.s   cfloop
        rts
cfhit:  moveal  %a0,%a5
        rts

| cempty: a4 = a scene's cell 0 -> a5 = its first empty cell, or 0.
| Clobbers d1, a0.
cempty: moveal  %a4,%a0
        moveq   #NCELL,%d1
        suba.l  %a5,%a5
celoop: tstb    %a0@
        bmi.s   cehit
        lea     %a0@(32),%a0
        subql   #1,%d1
        bne.s   celoop
        rts
cehit:  moveal  %a0,%a5
        rts

| ccommit: a3 = the part's working window, a5 = the cell, d5 = part.
| Mirrors the cell into the part's SRAM twin, sets the stock scene editor's
| dirty marks and drops the frame cache. Clobbers d0, d1, a0, a1.
ccommit:
        movel   #PART_STRIDE,%d1
        mulu.l  %d5,%d1
        addil   #SRAM_PART-0x8ed80,%d1
        addl    %a5,%d1
        subl    %a3,%d1
        moveal  %d1,%a0
        moveb   %a5@(1),%a0@(1)
        moveb   %a5@,%a0@
        movel   DBPTR,%d1
        moveal  %d1,%a0
        moveq   #1,%d1
        lsll    %d5,%d1
        movel   %a0,%d0
        addil   #0x95048,%d0
        moveal  %d0,%a1
        moveq   #0,%d0                 | ColdFire has no byte OR to memory
        moveb   %a1@,%d0
        orl     %d1,%d0
        moveb   %d0,%a1@
        moveq   #0,%d0
        moveb   0x100b145e,%d0
        orl     %d1,%d0
        moveb   %d0,0x100b145e
        movel   %a0,%d0
        addil   #0x9b332,%d0
        moveal  %d0,%a1
        moveq   #1,%d0
        movel   %d0,%a1@
        movel   %d0,0x100f8598
        jsr     DIRTY
| pinval: the next frame re-reads every track's cells. Clobbers d0, d1, a0.
pinval: lea     P2W,%a0
        moveq   #-1,%d0
        moveq   #8,%d1
pcinv:  movel   %d0,%a0@
        lea     %a0@(32),%a0
        subql   #1,%d1
        bne.s   pcinv
        rts

| ----------------------------------------------------- scene paste / clear ----
| Stock's scene copy, paste, undo and clear move all 32 bytes of each
| track's block (0x400274cc, 0x40025b40, 0x400275a0, 0x40038c30), so the
| cells follow without help. The writers change a scene under the frame
| cache's key: the scene write (0x40025b40(src, part, scene): paste, undo)
| and the CLEAR row's writer (0x40038c30(scene)) run as calls, and the cache
| is dropped after they return.
        .globl  scene_write_hook, scene_clear_hook
scene_write_hook:
        movel   %sp@(12),%sp@-         | the three arguments again
        movel   %sp@(12),%sp@-
        movel   %sp@(12),%sp@-
        jsr     write_stock
        lea     %sp@(12),%sp
        movel   %d0,%sp@-
        bsr.w   pinval
        movel   %sp@+,%d0
        rts
write_stock:
        lea     %sp@(-48),%sp          | the displaced prologue, then on
        movem.l %d2-%d7/%a2-%fp,%sp@
        moveal  %sp@(52),%a5
        jmp     0x40025b4c

scene_clear_hook:
        movel   %sp@(4),%sp@-
        jsr     clear_stock
        addql   #4,%sp
        movel   %d0,%sp@-
        bsr.w   pinval
        movel   %sp@+,%d0
        rts
clear_stock:
        lea     %sp@(-40),%sp          | the displaced prologue, then on
        movem.l %d2-%d7/%a2-%a5,%sp@
        movel   %sp@(44),%d4
        jmp     0x40038c3c

| ------------------------------------------------------------- the dial ----
| The page-2 knob draw reads the Part byte at 0x40037840 (FX2) and
| 0x40037bdc (FX1): a0 = DB + track*30 + part*0x18b2 + slot2, then
| `moveb %a0@,%d6`. With a scene held the dial shows that scene's lock
| instead, as the page-1 dials do. fp = track*30 + part*0x18b2, d4 = slot2.
        .globl  dial2_hook, dial1_hook
dial2_hook:
        addal   #P2P2_OFF,%a0
        moveq   #1,%d6
        bsr.w   dial
        jmp     0x40037848
dial1_hook:
        addal   #P1P2_OFF,%a0
        moveq   #0,%d6
        bsr.w   dial
        jmp     0x40037be4

| dial: a0 = the Part byte, d6 = kind, fp / d4 as above -> d6 = the value
| to draw: a held scene's lock, else (with PLOCKS P2 in the remix) a held
| step's page-2 lock, else the Part byte. Keeps everything but d6 and a0.
dial:   moveq   #0,%d0
        moveb   %a0@,%d0
        tstl    SCENE_HELD
        beq.w   dnoscene
        lea     %sp@(-32),%sp
        movem.l %d1-%d5/%a1/%a4/%a5,%sp@
        movel   %d0,%d3                | the knob, the fallback
        movel   %a6,%d0
        movel   #PART_STRIDE,%d1
        divu.l  %d1,%d0                | d0 = part
        movel   %d0,%d5
        mulu.l  %d1,%d0
        movel   %a6,%d1
        subl    %d0,%d1
        moveq   #30,%d0
        divu.l  %d0,%d1                | d1 = track
        movel   DBPTR,%d0
        movel   #PART_STRIDE,%d2
        mulu.l  %d5,%d2
        addl    %d2,%d0
        moveal  %d0,%a4                | a4 = the part's window
        addil   #SEL_OFF,%d0
        moveal  %d0,%a1
        movel   SCENE_HELD,%d0
        cmpil   #1,%d0
        beq.s   dselA
        addql   #1,%a1
dselA:  moveq   #0,%d0
        moveb   %a1@,%d0               | the held scene
        cmpil   #15,%d0
        bhi.s   dnone
        lsll    #8,%d0
        addl    %a4,%d0
        addil   #CELL0,%d0
        moveal  %d0,%a4                | a4 = its cell 0
        movel   %d1,%d0
        lsll    #4,%d0
        orl     %d4,%d0
        tstl    %d6
        bne.s   db1
        addql   #8,%d0                 | d0 = track<<4 | fx1<<3 | slot2
db1:    bsr.w   cfind
        movel   %a5,%d0
        beq.s   dnone
        moveq   #0,%d3
        moveb   %a5@(1),%d3
dnone:  movel   %d3,%d0
        movem.l %sp@,%d1-%d5/%a1/%a4/%a5
        lea     %sp@(32),%sp
dnoscene:
        .if     PLOCKS
        jsr     plk_dial               | PLOCKS P2: a held step's page-2 lock
        .endif
dknob:  movel   %d0,%d6
        rts

| The cache: 8 rows of 32 -- key (bank, part, scene A, scene B), then the
| FX2 A locks (6), FX2 B (6), FX1 A (6), FX1 B (6). A key of -1 never
| matches (a bank of 0xff is skipped before the compare). In .text: the
| depacked window is RAM, and a .data section would cost an 8 KB boundary.
        .align  4
P2W:    .fill   256,1,0xff
