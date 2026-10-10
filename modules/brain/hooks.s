
| ---- hooks.s: the two load-path detours and the per-remix table --------------
|
| Both sites are on the engine task's load path, before the banks are read:
|   0x40085342  LOAD PROJECT, before the empty-project init 0x400909d8:
|               `moveq #27,%d1 / movel %d1,%fp@(-570)`
|   0x40084d4a  the bank load every bank but the current (the power-up's
|               path too): `mvzb 0x80000002,%d1`
| Each stub keeps every register, calls brain_load and replays what the
| detour displaced.

        .include "remix.inc"           | brain_fx, brain_fx_n (manifest.py fx_inc)

| MODE DEFAULTS' view table, or 0 when that module is not in the remix
| (Linked.defsyms resolves MODEDEF_TABLE).
        .section .rodata
        .balign 4
        .globl  brain_modedef
brain_modedef: .long MODEDEF_TABLE

        .text
        .globl  brain_on_load, brain_on_bankload
brain_on_load:
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        jsr     brain_load
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        moveq   #27,%d1
        move.l  %d1,%fp@(-570)
        rts
brain_on_bankload:
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        jsr     brain_load
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        mvz.b   0x80000002,%d1
        rts

| ---- SAVE PROJECT: card.work -> card.strd --------------------------------------
| The project store 0x4008ee74 is called from 0x40085642, 0x400856dc and
| 0x40085780; KITS hooks its entry. Each call site jumps here: copy, then
| tail-call the store with the caller's arguments (PLOCKS P2's form).
        .globl  brain_on_store
brain_on_store:
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        jsr     brain_card_store
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        jmp     0x4008ee74

| ---- the engine task's job switch --------------------------------------------
|   0x4008485e  `mvzb %a2@,%d0 / moveq #45,%d1 / cmpl %d0,%d1`, then bcss
|               0x4008484e (a type above 45 goes back to the receive) and the
|               jump table. Type 0x41 runs brain_job and goes back to the
|               receive; every other type takes the stock path.
        .globl  brain_on_job
brain_on_job:
        mvz.b   %a2@,%d0
        cmp.l   #0x41,%d0
        bne.s   1f
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        jsr     brain_job
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        jmp     0x4008484e
1:      moveq   #45,%d1
        cmp.l   %d0,%d1
        jmp     0x40084864

| ---- the debug log: the MIDI thread's handler call -----------------------------
|   0x40005572  `moveal %a2@(0,%d0:l:4),%a0 / jsr %a0@`: the handler for the
|               message (status>>4 in d0), with the message pointer and 0
|               pushed. The stub keeps its own return in a slot (the MIDI
|               thread is the only caller), calls the handler as stock does,
|               then logs the message and what the handler left.
        .globl  brain_on_midi
brain_on_midi:
        move.l  %sp@+,brain_midi_ret
        lea     brain_midi_msg,%a1      | the message as it came in: a handler
        move.b  %a0@,%a1@               | may overwrite it (program change does)
        move.b  %a0@(1),%a1@(1)
        move.b  %a0@(2),%a1@(2)
        moveal  %a2@(0,%d0:l:4),%a0
        jsr     %a0@
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        pea     brain_midi_msg
        jsr     brain_midi_log
        addq.l  #4,%sp
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        move.l  brain_midi_ret,%sp@-
        rts
        .data
        .balign 4
brain_midi_ret: .long 0
brain_midi_msg: .long 0
        .text

| ---- the boot screen: the OS's boot animation draws BRAIN's ------------------
|   0x40055aa2  `jsr 0x40013abc`: the animation's per-frame flush (560 frames
|               on DTIM3's clock, the LED/key-scan task). d2 is the frame
|               (DTIM3 time, 0..559 by frames of varying step), d6 the surface, whose +12 is the plane
|               (PIRATE FLAG's hook site and reading, sanderlegit, PR #542).
|               Every frame the 128 columns are replaced: the brain's from
|               the left over frames 0..199, the word's over 240..399; then
|               the flush stock called. The art is bootart.py's, generated
|               per build (manifest.py boot_inc: brain_boot_brain/_word, a
|               column a big-endian 64-bit word, row y at bit y).
        .set    BOOT_FLUSH, 0x40013abc
        .globl  brain_boot_frame
brain_boot_frame:
        lea     %sp@(-20),%sp
        movem.l %d2-%d5/%a2,%sp@
        movea.l %d6,%a0
        movea.l %a0@(12),%a1            | the plane
        move.l  %d2,%d4                 | brain columns shown: frame * 16 / 25
        lsl.l   #4,%d4
        moveq   #25,%d0                 | ColdFire's divu.l takes no immediate
        divu.l  %d0,%d4
        move.l  %d2,%d5                 | word columns shown: (frame - 240) * 4 / 5
        subi.l  #240,%d5
        bpl.s   1f
        moveq   #0,%d5
1:      lsl.l   #2,%d5
        moveq   #5,%d0
        divu.l  %d0,%d5
        lea     brain_boot_brain,%a2
        lea     brain_boot_word,%a0
        moveq   #0,%d3                  | x
2:      moveq   #0,%d0
        moveq   #0,%d1
        cmp.l   %d4,%d3
        bge.s   3f
        move.l  %a2@,%d0
        move.l  %a2@(4),%d1
3:      cmp.l   %d5,%d3
        bge.s   4f
        or.l    %a0@,%d0
        or.l    %a0@(4),%d1
4:      move.l  %d0,%a1@+
        move.l  %d1,%a1@+
        addq.l  #8,%a2
        addq.l  #8,%a0
        addq.l  #1,%d3
        cmpi.l  #128,%d3
        blt.s   2b
        | the first frame at or past 280 kept for verify_brain, with its
        | frame number (the plane is redrawn long before a dump can read it;
        | d2 is DTIM3 time, so a frame number can be skipped)
        tst.l   brain_boot_snapf
        bne.s   6f
        cmpi.l  #280,%d2
        blt.s   6f
        move.l  %d2,brain_boot_snapf
        movea.l %d6,%a0
        movea.l %a0@(12),%a0
        lea     brain_boot_snap,%a1
        move.l  #256,%d0
5:      move.l  %a0@+,%a1@+
        subq.l  #1,%d0
        bne.s   5b
6:      movem.l %sp@,%d2-%d5/%a2
        lea     %sp@(20),%sp
        jmp     (BOOT_FLUSH).l          | the flush stock called, returning to it
        .data
        .balign 4
        .globl  brain_boot_snap, brain_boot_snapf
brain_boot_snapf: .long 0
brain_boot_snap: .space 1024
        .text
