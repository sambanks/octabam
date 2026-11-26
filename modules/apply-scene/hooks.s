| APPLY SCENE -- the hand-written part of the unit: the TRACKS setting's
| read, and SCENES P2's presence, FX2 descriptors and cache. generate.py appends this to the compiled apply.c +
| adapter.c. The scene keys' tables (aps_keys_a, aps_keys_b) come in through
| remix.inc, written per remix from the user's stock image (manifest.py
| keys_inc).
        .text
        .include "remix.inc"            | get_tracks, APS_P2, APS_DESC2, aps_keys_a, aps_keys_b
        .globl  aps_tracks_all

| int32_t aps_tracks_all(void): the TRACKS setting, 0 ACTIVE, 1 ALL.
aps_tracks_all:
        get_tracks %d0
        rts

| int32_t aps_p2(void): 1 when SCENES P2 is in the image (APS_P2, remix.inc).
        .globl  aps_p2, aps_desc2, aps_p2_changed
aps_p2:
        moveq   #APS_P2,%d0
        rts

| uint32_t aps_desc2(void): the remix's FX2 descriptor table (its FX2 ids).
aps_desc2:
        move.l  #APS_DESC2,%d0
        rts

| void aps_p2_changed(void): SCENES P2's frame pass reads the cells again
| (p2s_changed drops its cache; clobbers d0, d1, a0 only).
aps_p2_changed:
        .if     APS_P2
        jmp     p2s_changed
        .else
        rts
        .endif
