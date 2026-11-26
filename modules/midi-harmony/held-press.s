/* EVENTS passes the panel key in d0. Harmony's existing held-edit predicate
 * takes the zero-based encoder. Its push handler takes the original stack. */
    .text
    .global mh_ed_press_claim, mh_ed_press_handle
mh_ed_press_claim:
    subi.l #0x38,%d0
    jmp mh_ed_claim
mh_ed_press_handle:
    jmp mhc_step_push
