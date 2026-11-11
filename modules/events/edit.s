/* edit.held and edit.scene_held select the first owner; edit.copy_pre and edit.steps notify all clients.
 * The generated macros reload arguments independently before every callback.
 * Native stack frames, copy arguments and return values stay native. */
    .text
    .include "modules/events/frame.inc"
    .include "remix.inc"
    .if ev_edit_copy_pre_count
    .global ed_copy
ed_copy:
    EV_SAVE
    ev_edit_copy_pre
    EV_RESTORE
    /* Tail-call native memcpy once, with its original stack and arguments. */
    jmp 0x40020898
    .endif
    .if ev_edit_held_count
    .global ed_held
ed_held:
    EV_SAVE
    ev_edit_held
    EV_RESTORE
    lea -80(%sp),%sp
    movem.l %d2-%d7/%a2-%fp,(%sp)
    jmp 0x400508ec
    .endif
    .if ev_edit_scene_held_count
    /* Stock's scene-lock knob handlers (encoder, ticks), installed over every
     * encoder while a scene key is held (0x46c7dede + 20 * encoder): SCENE A's
     * 0x40053498, SCENE B's 0x40052e98 (its twin, a 32-byte frame; measured
     * under the port, 11 Nov 2026: the table holds one or the other). */
    .global ed_scene_held, ed_scene_held_b
ed_scene_held:
    EV_SAVE
    ev_edit_scene_held
    EV_RESTORE
    lea -36(%sp),%sp
    movem.l %d2-%d7/%a2-%a4,(%sp)
    jmp 0x400534a0
ed_scene_held_b:
    EV_SAVE
    ev_edit_scene_held
    EV_RESTORE
    lea -32(%sp),%sp
    movem.l %d2-%d7/%a2-%a3,(%sp)
    jmp 0x40052ea0
    .endif
    .if ev_edit_steps_count
    /* edit.steps (manifest.py): each site saves the native frame, lays its
     * record (op, five arguments) under it, notifies, replays what it
     * displaced and goes on. EV_SAVE's frame: d0..d7 at 0..28, the native
     * stack at 64. */
    .macro STEPS_CALL
    ev_edit_steps
    lea 24(%sp),%sp
    EV_RESTORE
    .endm
    .global ed_steps_trig, ed_steps_locks, ed_steps_track, ed_steps_copy, ed_steps_paste
ed_steps_trig:                       /* 0x4006036e: d3 = d5 + d6 * 16, the step */
    lsl.l #4,%d6
    move.l %a5,%d3
    add.l %d6,%d3
    EV_SAVE
    lea -24(%sp),%sp
    clr.l (%sp)                      /* TRIG_CLEAR */
    move.l %d3,4(%sp)
    STEPS_CALL
    jmp 0x40060374
ed_steps_locks:                      /* 0x40040e14(pattern, track, page, mask) */
    EV_SAVE
    lea -24(%sp),%sp
    moveq #1,%d0
    move.l %d0,(%sp)
    move.l 92(%sp),4(%sp)
    move.l 96(%sp),8(%sp)
    move.l 100(%sp),12(%sp)
    move.l 104(%sp),16(%sp)
    STEPS_CALL
    lea -44(%sp),%sp
    movem.l %d2-%d7/%a2-%a6,(%sp)
    jmp 0x40040e1c
ed_steps_track:                      /* 0x40039df4(pattern, track, flags) */
    EV_SAVE
    lea -24(%sp),%sp
    moveq #2,%d0
    move.l %d0,(%sp)
    move.l 92(%sp),4(%sp)
    move.l 96(%sp),8(%sp)
    move.l 100(%sp),12(%sp)
    STEPS_CALL
    lea -60(%sp),%sp
    movem.l %d2-%d7/%a2-%a6,(%sp)
    jmp 0x40039dfc
ed_steps_copy:                       /* 0x4002bf38(clip, pattern, track, page, mask) */
    EV_SAVE
    lea -24(%sp),%sp
    moveq #3,%d0
    move.l %d0,(%sp)
    move.l 92(%sp),4(%sp)
    move.l 96(%sp),8(%sp)
    move.l 100(%sp),12(%sp)
    move.l 104(%sp),16(%sp)
    move.l 108(%sp),20(%sp)
    STEPS_CALL
    lea -64(%sp),%sp
    movem.l %d2-%d7/%a2-%a6,(%sp)
    jmp 0x4002bf40
ed_steps_paste:                      /* 0x4002cb52, in 0x4002c89c(clip, pattern, track, ...): */
    EV_SAVE                          /* d4 the source record, d5 the destination step, */
    lea -24(%sp),%sp                 /* the routine's arguments at the native sp + 96 */
    moveq #4,%d0
    move.l %d0,(%sp)
    move.l 184(%sp),4(%sp)
    move.l 188(%sp),8(%sp)
    move.l 192(%sp),12(%sp)
    move.l 40(%sp),16(%sp)           /* d4 (EV_SAVE + 16) */
    move.l 44(%sp),20(%sp)           /* d5 */
    STEPS_CALL
    adda.l #0x1001614f,%a0
    jmp 0x4002cb58
    .endif
