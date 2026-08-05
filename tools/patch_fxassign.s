    .cpu 5407
    .text
| =====================================================================
|  FX2 ROLE ASSIGNMENT (BUS.md stage-2 selector)
|
|  Only one DELAY SERVER and one REVERB SERVER may run per bank of four
|  tracks -- both hardcode a fixed Y base, so a second instance would share
|  the first's buffers. The DSP already fails safe (BUS.md hardware test 3's
|  role lock makes a duplicate an exact dry passthrough), but that is a
|  fail-safe, not UX: the entry still looks selectable and silently does
|  nothing. This makes the chooser name the holder instead -- "BDLY TRK3"
|  rather than a row that lies.
|
|  Mechanism. All three code sites that read the FX2 chooser list are
|  `lea <list>,aN` (draw 0x400375f2, select 0x40052494, menu-open 0x40059a40)
|  and tools/build_menu.py already rewrites that 4-byte operand, so moving the
|  list to RAM costs nothing. This hook rebuilds it on menu-open: copy the
|  flash template, then for each role another track in the bank holds, make a
|  RAM copy of the BUSY descriptor with the owner's digit written into its
|  name and point that list entry at the copy.
|
|  Why the BUSY descriptor clones NONE: it inherits NONE's id (0) and empty
|  parameter-enable bitmap, so confirming the row is a real no-op needing no
|  special case anywhere -- only the 13-byte name at P+9 differs.
|
|  Why replace in place rather than drop the entry: positions are load-bearing.
|  FUN_4005996c seeds the cursor from ID2POS (0x400d6150), a STATIC flash
|  id->position table, so shortening the list would desync every id above the
|  gap. Four fixed positions leave ID2POS correct by construction.
|
|  The ids are eight adjacent bytes (FX1 0x8ed80+track, FX2 0x8ed88+track,
|  scene A at 0x8ed90 right after -- the agreement between ARCHITECTURE.md:124,
|  NOTES.md:551 and PARAM_PAGES.md's 0x8ed80/0x8ed88 split is what pins the
|  layout), so a sibling's role is one indexed byte read, not a struct walk.
|
|  Owners are stashed in RAM rather than held in registers: the scan, the
|  402-byte copy and the digit patch each want a scratch pair, and spilling to
|  two words costs less than the register juggling did -- an earlier draft got
|  that wrong by reading saved registers off the stack at hand-computed
|  offsets.
|
|  Every address arrives via --defsym from tools/build_bus.py, so the cave,
|  the RAM block and the descriptor layout stay owned by the build script.
|
|  KNOWN LIMIT, not closed: FUN_4005996c only reaches this path on its
|  one-time init branch (DAT_400bc48c == 0). A re-entry skipping that branch
|  reuses whatever the buffer last held. The stock cursor seed sits in the
|  same branch and has the same shape, so this is stock behaviour rather than
|  a regression -- but it is unproven, and it is the first thing to suspect if
|  a stale row shows up on hardware.
| =====================================================================

| ---- menu-open hook: displaces `lea <list>,%a0` at 0x40059a40 ----
| Entry: d2.b = pattern, d3.b = track, both loaded 2 instructions earlier.
| d0/a0 are dead across this point (d0 is reloaded by the moveq at the return
| address, a0 is the register being replaced); everything else is saved.
| ColdFire movem.l has no -(An) form, hence the lea/movem pair the other
| patches here already use.
    .globl  fxassign_cave
fxassign_cave:
    lea     -0x18(%sp), %sp
    movem.l %d1-%d4/%a1-%a2, (%sp)

    | ---- copy the flash template into the RAM list ----
    | 8 longs: NONE + 3 roles + 3 NONE padding rows + terminator. The padding
    | exists because the row renderer draws a fixed 7-row viewport regardless
    | of the real count (BUS.md hardware test 1) -- copied verbatim so that
    | fix keeps working.
    lea     FLASH_LIST, %a1
    lea     LIST_RAM, %a2
    moveq   #7, %d0
fa_lcopy:
    move.l  %a1@+, %a2@+
    subq.l  #1, %d0
    bpl.b   fa_lcopy

    | ---- a1 -> this bank's four FX2 id bytes; d4 = track; d3 = own index ----
    | base is the POINTER at 0x46c82456, not that address (NOTES.md:586)
    moveq   #0, %d0
    move.b  %d2, %d0                | pattern
    move.l  #0x18b2, %d1            | ColdFire mulu.l takes no immediate -- the
    mulu.l  %d1, %d0                | stock code loads it the same way, and it
    add.l   0x46c82456, %d0         | is the same stride, at 0x40059a68
    add.l   #0x8ed88, %d0
    moveq   #0, %d4
    move.b  %d3, %d4                | track 0..7
    move.l  %d4, %d1
    and.l   #4, %d1                 | bank base: 0-3 and 4-7 are different DSPs
    add.l   %d1, %d0
    move.l  %d0, %a1
    move.l  %d4, %d3
    and.l   #3, %d3                 | our own index, skipped by the scans: the
                                    | role THIS track holds must stay shown

    moveq   #ID_DELAY, %d0
    bsr.w   fa_owner
    move.l  %d1, OWNER_DELAY
    moveq   #ID_REVERB, %d0
    bsr.w   fa_owner
    move.l  %d1, OWNER_REVERB

    move.l  OWNER_DELAY, %d1
    bmi.b   fa_reverb
    lea     BUSY_DELAY, %a1
    lea     DESC_DELAY, %a2
    bsr.w   fa_busy
    lea     LIST_RAM, %a2
    move.l  #DESC_DELAY, %d0        | ColdFire has no move.l #imm to displaced
    move.l  %d0, %a2@(POS_DELAY*4)  | memory; d0 is dead after fa_busy anyway
fa_reverb:
    move.l  OWNER_REVERB, %d1
    bmi.b   fa_done
    lea     BUSY_REVERB, %a1
    lea     DESC_REVERB, %a2
    bsr.w   fa_busy
    lea     LIST_RAM, %a2
    move.l  #DESC_REVERB, %d0
    move.l  %d0, %a2@(POS_REVERB*4)

fa_done:
    movem.l (%sp), %d1-%d4/%a1-%a2
    lea     0x18(%sp), %sp
    lea     LIST_RAM, %a0           | the displaced instruction, repointed
    jmp     0x40059a46

| ---- fa_owner: which OTHER track in this bank holds id d0? ----
| in:  d0 = effect id, a1 -> the bank's 4 id bytes, d3 = our index in the bank
| out: d1 = holder's index 0..3, or -1
| clobbers d1, d2
fa_owner:
    moveq   #0, %d2                 | index within the bank
fa_o_loop:
    cmp.l   %d3, %d2
    beq.b   fa_o_next               | that is us
    moveq   #0, %d1
    move.b  (%a1,%d2.l), %d1
    cmp.l   %d0, %d1
    beq.b   fa_o_hit
fa_o_next:
    addq.l  #1, %d2
    cmpi.l  #4, %d2
    bne.b   fa_o_loop
    moveq   #-1, %d1
    rts
fa_o_hit:
    move.l  %d2, %d1
    rts

| ---- fa_busy: RAM copy of a BUSY descriptor, named for its owner ----
| in:  a1 -> flash template (P), a2 -> RAM copy (P), d1 = holder's bank index,
|      d4 = track
| The name at P+9 is "xxxx TRK?" and the '?' is the only byte that varies, so
| the digit is written straight over it. Panel track numbers are 1-8 where
| these are 0-7, and the bank base has to come back in, hence
| (track & 4) + index + 1.
| clobbers d0, d1, d2, a1, a2
fa_busy:
    move.l  %d1, %d2                | the copy loop needs d1 free
    move.l  %a2, %d1                | remember where the copy lands
    move.w  #DESC_LEN-1, %d0
    andi.l  #0xffff, %d0
fa_b_copy:
    move.b  %a1@+, %a2@+
    subq.l  #1, %d0
    bpl.b   fa_b_copy

    move.l  %d1, %a2                | -> the RAM copy again
    move.l  %d4, %d0
    and.l   #4, %d0                 | bank base
    add.l   %d2, %d0                | + index within the bank
    addq.l  #1, %d0                 | panel numbering starts at 1
    addi.l  #0x30, %d0              | -> ASCII
    move.b  %d0, %a2@(NAME_OFF+DIGIT_OFF)
    rts
