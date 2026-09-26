| SCENES P2 -- scene locks and the crossfader for FX1/FX2 page 2.
|
| Stock's scene block is 32 bytes a track a scene and the frame builder
| morphs bytes 0..29 (page 1 of the five pages) into the DSP frame every
| frame; page 2 has no byte and the loop stops at halfword 17
| (docs/firmware/MIDI.md Appendix C). This unit adds page 2:
|
| * a POOL of page-2 locks inside each Part window at +0x90522 (144 bytes,
|   the run midisc's MIDI-track locks use; the ledger refuses the pair):
|   u16 magic 'P2', u8 count, then 3-byte entries
|       b0 = scene<<3 | track      b1 = fx1<<3 | slot2 (0..5)      b2 = value
|   47 entries at most. Part Save / Reload / Project Save carry the window
|   whole, so the pool travels with the part like the stock scene block.
| * the FRAME PASS (frame_hook, detour at 0x4000cf40, after the stock morph,
|   before the transfer): per track, the current (bank, part, scene A,
|   scene B) key is compared with a cache; on a change the track's locks are
|   unpacked from the pool into P2W (A and B values per slot, 0xff = none).
|   Then every locked slot is lerped with the stock weight table
|   (0x80003c60: hi word = -xf*258, Q15) into the voice record's page-2
|   bytes (FX2 halfwords 24..26 = bytes 48..53, FX1 18..20 = 36..41), an
|   unlocked side taking the knob byte already in the record. A select
|   (descriptor count < 128) snaps: the A side from the fader's midpoint up.
| * the EDITOR HOOKS (the FX2 page-2 editor 0x4003a9dc and FX1's 0x4003abe4,
|   detoured at entry): with a scene held (0x460d169c: 1 = A, else B) a
|   page-2 knob turn edits the held scene's lock instead of the Part --
|   the slot's own encoder hook and clamp (descriptor +0x12a, +0x6a, +0x9a),
|   the pool in the working window and its SRAM twin (0x100a4ece + part*
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
        .set    POOL_OFF,   0x90522
        .set    POOL_MAGIC, 0x5032          | 'P2'
        .set    POOL_MAX,   47
        .set    WEIGHTS,    0x80003c60      | long per track: hi = -xf*258
        .set    SCENE_A_OFF, 0x80000006     | nonzero: scene A disabled
        .set    SCENE_B_OFF, 0x80000007
        .set    DESC1,      0x400d5f58      | FX1 descriptor pointers by id
        .set    DESC2,      0x400d5fdc      | FX2 descriptor pointers by id
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
| row's 24 lock bytes from the pool. Clobbers d0-d6, a0.
unpack: movel   %d0,%a4@
        moveq   #-1,%d1
        movel   %d1,%a4@(4)
        movel   %d1,%a4@(8)
        movel   %d1,%a4@(12)
        movel   %d1,%a4@(16)
        movel   %d1,%a4@(20)
        movel   %d1,%a4@(24)
        movel   %a3,%d1
        addil   #POOL_OFF,%d1
        moveal  %d1,%a0                | a0 = pool
        moveq   #0,%d1
        movew   %a0@,%d1
        cmpil   #POOL_MAGIC,%d1
        bne.s   udone
        moveq   #0,%d3
        moveb   %a0@(2),%d3            | count
        cmpil   #POOL_MAX,%d3
        ble.s   ucnt
        moveq   #POOL_MAX,%d3
ucnt:   addql   #3,%a0
        movel   %d0,%d5
        lsrl    #8,%d5
        andil   #0xff,%d5              | d5 = scene A
        movel   %d0,%d6
        andil   #0xff,%d6              | d6 = scene B
uloop:  subql   #1,%d3
        bmi.s   udone
        moveq   #0,%d1
        moveb   %a0@,%d1               | scene<<3 | track
        movel   %d1,%d2
        andil   #7,%d2
        cmpl    %d7,%d2
        bne.s   unext
        lsrl    #3,%d1                 | d1 = scene
        moveq   #0,%d2
        moveb   %a0@(1),%d2            | fx1<<3 | slot2
        movel   %d2,%d4
        andil   #7,%d4
        cmpil   #6,%d4
        bge.s   unext
        addql   #4,%d4                 | row offset of slot2 on the FX2 A side
        btst    #3,%d2
        beq.s   ufx
        addil   #12,%d4                | FX1 sides
ufx:    moveq   #0,%d2
        moveb   %a0@(2),%d2            | the value
        cmpl    %d1,%d5
        bne.s   unotA
        moveb   %d2,%a4@(0,%d4:l)
unotA:  cmpl    %d1,%d6
        bne.s   unext
        moveb   %d2,%a4@(6,%d4:l)
unext:  addql   #3,%a0
        bra.s   uloop
udone:  rts

| --------------------------------------------------------------- editors ----
| Entry state of the stock editors: sp@ = return, sp@(4) = slot2, sp@(8) = ticks.
| No scene held: on to P2_NEXT2 / P2_NEXT1 with the entry state untouched.
| Without Octakit `remix.inc` sets them to fx2_stock / fx1_stock (the
| displaced prologue, then the stock body); with her, the SCENES P2 KITS
| bridge overrides her writes at the two entries and the build defines
| the symbols as her wrappers, so her editor protocol runs whole.
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
        moveal  %sp@(32),%a2
        jmp     0x4003a9e8
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
        moveal  %sp@(32),%a2
        jmp     0x4003abf0

| edit: d0 = kind (1 FX2, 0 FX1). d2 slot2, d3 ticks, d4 track, d5 part,
| d6 kind, d7 held scene; a2 descriptor, a3 part window, a4 pool, a5 entry.
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
        movel   %a3,%d0
        addil   #POOL_OFF,%d0
        moveal  %d0,%a4                | a4 = pool
        bsr.w   pinit
        movel   %d7,%d0
        lsll    #3,%d0
        orl     %d4,%d0                | d0 = b0 wanted
        movel   %d2,%d1
        tstl    %d6
        bne.s   eb1
        addql   #8,%d1
eb1:    bsr.w   pfind                  | d1 = b1 wanted -> a5 = entry or 0
        moveq   #0,%d0
        moveb   KROWS+(KFUNC>>3),%d0
        btst    #(KFUNC&7),%d0
        beq.s   eturn
        movel   %a5,%d0                | FUNC held: remove the lock
        beq.w   edone
        bsr.w   premove
        bra.w   ecommit
eturn:  movel   %a5,%d0
        beq.s   eknob
        moveq   #0,%d0
        moveb   %a5@(2),%d0            | the lock's value
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
        movel   %d7,%d3                | append an entry: b0, b1; the value
        lsll    #3,%d3                 | parks in d7 (the scene is spent)
        orl     %d4,%d3
        movel   %d2,%d1
        tstl    %d6
        bne.s   eb2
        addql   #8,%d1
eb2:    movel   %d0,%d7
        bsr.w   pappend                | d3 = b0, d1 = b1 -> a5 (0 = full)
        movel   %d7,%d0
        movel   %a5,%d1
        beq.w   edone                  | full: the turn is dropped
estore: moveb   %d0,%a5@(2)
ecommit:
        bsr.w   pcommit                | a4 = pool, d5 = part
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

| ------------------------------------------------------------ the pool ----
| pinit: a4 = pool. Stamps the magic on a pool that has none (count 0).
pinit:  moveq   #0,%d0
        movew   %a4@,%d0
        cmpil   #POOL_MAGIC,%d0
        beq.s   piok
        movew   #POOL_MAGIC,%a4@
        clrb    %a4@(2)
piok:   rts

| pfind: a4 = pool, d0 = b0, d1 = b1 -> a5 = the entry, or 0. Clobbers a0.
pfind:  movel   %d2,%sp@-
        moveq   #0,%d2
        moveb   %a4@(2),%d2
        lea     %a4@(3),%a0
        suba.l  %a5,%a5
pfloop: subql   #1,%d2
        bmi.s   pfdone
        cmpb    %a0@,%d0
        bne.s   pfnext
        cmpb    %a0@(1),%d1
        bne.s   pfnext
        moveal  %a0,%a5
        bra.s   pfdone
pfnext: addql   #3,%a0
        bra.s   pfloop
pfdone: movel   %sp@+,%d2
        rts

| pappend: a4 = pool, d3 = b0, d1 = b1 -> a5 = the new entry (value unset),
| or 0 when the pool holds POOL_MAX. Clobbers d0.
pappend:
        moveq   #0,%d0
        moveb   %a4@(2),%d0
        cmpil   #POOL_MAX,%d0
        bcs.s   paok
        suba.l  %a5,%a5
        rts
paok:   movel   %d0,%sp@-
        addql   #1,%d0
        moveb   %d0,%a4@(2)
        movel   %sp@,%d0
        addl    %d0,%d0
        addl    %sp@+,%d0              | index*3
        lea     %a4@(3),%a5
        addal   %d0,%a5
        moveb   %d3,%a5@
        moveb   %d1,%a5@(1)
        rts

| premove: a4 = pool, a5 = the entry to drop; the tail moves down.
| Clobbers d0, d1, a0, a1.
premove:
        moveq   #0,%d0
        moveb   %a4@(2),%d0
        subql   #1,%d0
        moveb   %d0,%a4@(2)
        movel   %d0,%d1
        addl    %d0,%d0
        addl    %d1,%d0
        lea     %a4@(3),%a0
        addal   %d0,%a0                | a0 = one past the last entry
        moveal  %a5,%a1
prloop: cmpl    %a0,%a1
        bcc.s   prdone
        moveb   %a1@(3),%a1@
        addql   #1,%a1
        bra.s   prloop
prdone: rts

| pcommit: a4 = pool (working window), d5 = part. Mirrors the pool into the
| part's SRAM twin, sets the stock scene editor's dirty marks and drops the
| frame cache so the next frame re-reads the pool. Clobbers d0, d1, a0, a1.
pcommit:
        movel   #PART_STRIDE,%d1
        mulu.l  %d5,%d1
        addil   #SRAM_PART+POOL_OFF-0x8ed80,%d1
        moveal  %d1,%a0
        moveal  %a4,%a1
        moveq   #36,%d1
pccopy: movel   %a1@+,%a0@+
        subql   #1,%d1
        bne.s   pccopy
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
        lea     P2W,%a0
        moveq   #-1,%d0
        moveq   #8,%d1
pcinv:  movel   %d0,%a0@
        lea     %a0@(32),%a0
        subql   #1,%d1
        bne.s   pcinv
        rts

| ----------------------------------------------- scene copy / paste / clear ----
| Stock copies a scene (0x400274cc(part, scene)) into its clipboard
| 0x460c8122 and writes one back (0x40025b40(src, part, scene): paste from
| the clipboard, clear and undo from other buffers). The pool follows: a
| copy snapshots the scene's page-2 locks into CLIP; a scene write drops the
| target scene's locks and, when the source is the stock clipboard, adds
| CLIP's under the new scene number.
        .set    SCENE_CLIP, 0x460c8122
        .globl  scene_copy_hook, scene_write_hook
scene_copy_hook:
        lea     %sp@(-36),%sp
        movem.l %d2-%d5/%a2-%a6,%sp@
        moveq   #0,%d5
        moveb   %sp@(40+3),%d5         | part (a long; its low byte)
        moveq   #0,%d4
        moveb   %sp@(44+3),%d4         | scene
        bsr.w   pool_of                | d5 -> a4 = the part's pool
        lea     CLIP,%a5
        lea     CLIPN,%a6
        bsr.w   snapshot
        movem.l %sp@,%d2-%d5/%a2-%a6
        lea     %sp@(36),%sp
        lea     %sp@(-24),%sp          | the displaced prologue, then on
        movem.l %d2-%d7,%sp@
        movel   %sp@(28),%d2
        jmp     0x400274d8

scene_write_hook:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %sp@(48),%d6           | src
        moveq   #0,%d5
        moveb   %sp@(52+3),%d5         | part
        moveq   #0,%d4
        moveb   %sp@(56+3),%d4         | scene
        bsr.w   pool_of
        bsr.w   pinit
        bsr.w   drop_scene             | the target scene's entries go
swadd:  lea     CLIP,%a2
        moveq   #0,%d2
        moveb   CLIPN,%d2
        cmpil   #SCENE_CLIP,%d6
        beq.s   swaloop
        lea     UCLIP,%a2              | the undo buffer written back
        moveq   #0,%d2
        moveb   UCLIPN,%d2
        cmpil   #SCENE_UNDO,%d6
        bne.s   swcommit
swaloop:
        subql   #1,%d2
        bmi.s   swcommit
        movel   %d4,%d3
        lsll    #3,%d3
        moveq   #0,%d0
        moveb   %a2@,%d0
        orl     %d0,%d3                | b0 = scene<<3 | track
        moveq   #0,%d1
        moveb   %a2@(1),%d1            | b1
        bsr.w   pappend
        movel   %a5,%d0
        beq.s   swcommit               | full
        moveb   %a2@(2),%a5@(2)
        addql   #3,%a2
        bra.s   swaloop
swcommit:
        bsr.w   pcommit
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        lea     %sp@(-48),%sp          | the displaced prologue, then on
        movem.l %d2-%d7/%a2-%fp,%sp@
        moveal  %sp@(52),%a5
        jmp     0x40025b4c

| The undo snapshot (0x400275a0(kind, part, scene), before a paste or a
| clear) copies the scene into 0x460bf218; UNDO writes that buffer back
| through the scene write. The pool's entries for the scene go to UCLIP.
        .set    SCENE_UNDO, 0x460bf218
        .globl  scene_undo_hook, scene_clear_hook
scene_undo_hook:
        lea     %sp@(-36),%sp
        movem.l %d2-%d5/%a2-%a6,%sp@
        moveq   #0,%d5
        moveb   %sp@(44+3),%d5         | part (the second argument)
        moveq   #0,%d4
        moveb   %sp@(48+3),%d4         | scene
        bsr.w   pool_of
        lea     UCLIP,%a5
        lea     UCLIPN,%a6
        bsr.w   snapshot
        movem.l %sp@,%d2-%d5/%a2-%a6
        lea     %sp@(36),%sp
        lea     %sp@(-24),%sp          | the displaced prologue, then on
        movem.l %d2-%d7,%sp@
        movel   %sp@(32),%d2
        jmp     0x400275ac

| The CLEAR row's writer, 0x40038c30(scene), fills the scene's block with
| 0xff in place for the current part (0x80000003); its page-2 locks go too.
scene_clear_hook:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveq   #0,%d5
        moveb   0x80000003,%d5         | part
        moveq   #0,%d4
        moveb   %sp@(48+3),%d4         | scene
        bsr.w   pool_of
        bsr.w   pinit
        bsr.w   drop_scene
        bsr.w   pcommit
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        lea     %sp@(-40),%sp          | the displaced prologue, then on
        movem.l %d2-%d7/%a2-%a5,%sp@
        movel   %sp@(44),%d4
        jmp     0x40038c3c

| snapshot: a4 = pool, d4 = scene, a5 = a clip, a6 = its count byte.
| Clobbers d0-d2, a0, a5.
snapshot:
        clrb    %a6@
        moveq   #0,%d2
        moveb   %a4@(2),%d2
        lea     %a4@(3),%a0
snloop: subql   #1,%d2
        bmi.s   sndone
        moveq   #0,%d0
        moveb   %a0@,%d0
        movel   %d0,%d1
        lsrl    #3,%d1
        cmpl    %d4,%d1
        bne.s   snnext
        andil   #7,%d0
        moveb   %d0,%a5@               | track
        moveb   %a0@(1),%a5@(1)        | kind | slot2
        moveb   %a0@(2),%a5@(2)        | value
        addql   #3,%a5
        moveq   #0,%d0
        moveb   %a6@,%d0
        addql   #1,%d0
        moveb   %d0,%a6@
snnext: addql   #3,%a0
        bra.s   snloop
sndone: rts

| drop_scene: a4 = pool, d4 = scene: every entry of that scene goes.
| Clobbers d0, d1, a0, a1, a5.
drop_scene:
        lea     %a4@(3),%a5
dsloop: moveq   #0,%d0
        moveb   %a4@(2),%d0
        movel   %d0,%d1
        addl    %d0,%d0
        addl    %d1,%d0
        lea     %a4@(3),%a0
        addal   %d0,%a0                | one past the last entry
        cmpl    %a0,%a5
        bcc.s   dsdone
        moveq   #0,%d0
        moveb   %a5@,%d0
        lsrl    #3,%d0
        cmpl    %d4,%d0
        bne.s   dskeep
        bsr.w   premove                | a5 stays: the next entry moved in
        bra.s   dsloop
dskeep: addql   #3,%a5
        bra.s   dsloop
dsdone: rts

| pool_of: d5 = part -> a4 = that part's pool in the working window.
pool_of:
        movel   DBPTR,%d0
        movel   #PART_STRIDE,%d1
        mulu.l  %d5,%d1
        addl    %d1,%d0
        addil   #POOL_OFF,%d0
        moveal  %d0,%a4
        rts

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
| to draw. Keeps everything but d6 and a0.
dial:   moveq   #0,%d0
        moveb   %a0@,%d0
        tstl    SCENE_HELD
        beq.w   dknob
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
        bsr.w   pool_of                | d5 -> a4
        movel   DBPTR,%d0
        movel   #PART_STRIDE,%d2
        mulu.l  %d5,%d2
        addl    %d2,%d0
        addil   #SEL_OFF,%d0
        moveal  %d0,%a1
        movel   SCENE_HELD,%d0
        cmpil   #1,%d0
        beq.s   dselA
        addql   #1,%a1
dselA:  moveq   #0,%d0
        moveb   %a1@,%d0
        lsll    #3,%d0
        orl     %d1,%d0                | b0 = scene<<3 | track
        movel   %d4,%d1
        tstl    %d6
        bne.s   db1
        addql   #8,%d1
db1:    moveq   #0,%d2
        movew   %a4@,%d2
        cmpil   #POOL_MAGIC,%d2
        bne.s   dnone
        bsr.w   pfind
        movel   %a5,%d0
        beq.s   dnone
        moveq   #0,%d3
        moveb   %a5@(2),%d3
dnone:  movel   %d3,%d0
        movem.l %sp@,%d1-%d5/%a1/%a4/%a5
        lea     %sp@(32),%sp
dknob:  movel   %d0,%d6
        rts

| The scene clipboard's page-2 locks: {track, kind|slot2, value} x POOL_MAX.
        .align  2
CLIPN:  .byte   0
        .align  2
CLIP:   .fill   POOL_MAX*3,1,0
UCLIPN: .byte   0
        .align  2
UCLIP:  .fill   POOL_MAX*3,1,0

| The cache: 8 rows of 32 -- key (bank, part, scene A, scene B), then the
| FX2 A locks (6), FX2 B (6), FX1 A (6), FX1 B (6). A key of -1 never
| matches (a bank of 0xff is skipped before the compare). In .text: the
| depacked window is RAM, and a .data section would cost an 8 KB boundary.
        .align  4
P2W:    .fill   256,1,0xff
