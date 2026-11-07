/* WAVE (ColdFire machine): a 4-voice wavetable engine, no filter.
 *
 * Derived from CHOMPI WAVE's voice (CHOMPI-Club/CHOMPI a73d732: wavetable.h
 * PopSample's two-sample interpolation, Adsr attack / release), MIT, Copyright
 * (c) 2026 CHOMPI Club (LICENSE-CHOMPI). The filter, the LFOs and the 33-frame
 * table are not carried over: the table is 8 generated frames (tables.py), the
 * frame position is a knob, and the Octatrack's own filter and LFOs follow.
 * Not affiliated with or endorsed by CHOMPI Club.
 *
 * Formats: sample and envelope Q27, gain / coefficients Q31, frame position Q16
 * (frame index . fraction). mul() is the EMAC's fractional multiply,
 * (a * b) >> 31, which needs MACSR = 0x20 and ACC0 = 0 on entry. */
#pragma once
#include <stdint.h>

#define NV 4                    /* voices */
#define FLEN 1024               /* samples a frame */
#define NFR 8                   /* frames: sine, triangle, saw, square, pulses 1/4 1/8 1/16 1/32 */
#define POS_MAX ((NFR - 1) << 16)

typedef struct {
    uint32_t phase, inc;        /* 32-bit phase, increment a sample */
    int32_t gain;               /* velocity gain, Q31 */
    int32_t env;                /* Q27 */
    int32_t mode, gate, gate_prev;
} Voice;

typedef struct {
    Voice v[NV];
    const int16_t *table;       /* (NFR + 1) x FLEN: frame NFR repeats frame NFR - 1, so frame + 1 needs no test */
    int32_t pos, pos_tgt;       /* frame position, Q16, slewed to its target each sample */
    int32_t atk_d0, rel_d0;     /* one-pole steps of the attack and release, Q31 */
} Engine;

void eng_init(Engine *e, const int16_t *table, int32_t atk_d0, int32_t rel_d0);
void eng_pos(Engine *e, int32_t pos_q16);                       /* the target; clamped to 0..POS_MAX */
void eng_on(Engine *e, int v, uint32_t inc, int32_t gain);      /* gate on, phase kept */
void eng_off(Engine *e, int v);                                 /* gate off */
void eng_render(Engine *e, int32_t *out, int n);                /* n Q27 samples, the four voices summed */
