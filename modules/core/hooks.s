
| ---- hooks.s: the two load-path detours and the per-remix table --------------
|
| Both sites are on the engine task's load path, before the banks are read:
|   0x40085342  LOAD PROJECT, before the empty-project init 0x400909d8:
|               `moveq #27,%d1 / movel %d1,%fp@(-570)`
|   0x40084d4a  the bank load every bank but the current (the power-up's
|               path too): `mvzb 0x80000002,%d1`
| Each stub keeps every register, calls core_load and replays what the
| detour displaced.

        .include "remix.inc"           | core_fx, core_fx_n (manifest.py fx_inc)

| MODE DEFAULTS' view table, or 0 when that module is not in the remix
| (Linked.defsyms resolves MODEDEF_TABLE).
        .section .rodata
        .balign 4
        .globl  core_modedef
core_modedef: .long MODEDEF_TABLE

        .text
        .globl  core_on_load, core_on_bankload
core_on_load:
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        jsr     core_load
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        moveq   #27,%d1
        move.l  %d1,%fp@(-570)
        rts
core_on_bankload:
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        jsr     core_load
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        mvz.b   0x80000002,%d1
        rts

| ---- SAVE PROJECT: card.work -> card.strd --------------------------------------
| The project store 0x4008ee74 is called from 0x40085642, 0x400856dc and
| 0x40085780; KITS hooks its entry. Each call site jumps here: copy, then
| tail-call the store with the caller's arguments (PLOCKS P2's form).
        .globl  core_on_store
core_on_store:
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        jsr     core_card_store
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        jmp     0x4008ee74

| ---- the engine task's job switch --------------------------------------------
|   0x4008485e  `mvzb %a2@,%d0 / moveq #45,%d1 / cmpl %d0,%d1`, then bcss
|               0x4008484e (a type above 45 goes back to the receive) and the
|               jump table. Type 0x41 runs core_job and goes back to the
|               receive; every other type takes the stock path.
        .globl  core_on_job
core_on_job:
        mvz.b   %a2@,%d0
        cmp.l   #0x41,%d0
        bne.s   1f
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        jsr     core_job
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        jmp     0x4008484e
1:      moveq   #45,%d1
        cmp.l   %d0,%d1
        jmp     0x40084864
