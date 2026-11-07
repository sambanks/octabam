/* WAVE's note layer; see wcf.h.  Tables: wcf_data.c (tables.py). */
#include "wcf.h"
#include "fx.h"

extern const uint32_t wcf_base_inc;
extern const int32_t wcf_exp2[385];
extern const int32_t wcf_tc[128];
extern const int8_t wcf_chord[32][4];

/* 0.8 / n, Q31: four voices at the table amplitude sum to 0.36 at most */
static const int32_t gain_n[5] = {0, 1717986918, 858993459, 572662306, 429496730};

uint32_t wcf_inc(int32_t p)
{
    if (p < -48 * 256) p = -48 * 256;
    if (p > 48 * 256) p = 48 * 256;
    int32_t k = (p >> 3) + 3072;                /* 1/32 semitones, 8 octaves up so it is positive */
    int32_t rem = p & 7;
    int32_t o = k / 384 - 8;
    int32_t kk = k % 384;
    int32_t e0 = wcf_exp2[kk], e1 = wcf_exp2[kk + 1];
    int32_t e = e0 + (((e1 - e0) * rem) >> 3);                 /* 2^(p / 12), Q29 */
    uint32_t inc = (uint32_t)(mul((int32_t)(wcf_base_inc << 6), e) >> 4);
    return o >= 0 ? inc << o : inc >> -o;
}

void wcf_note(Engine *e, int32_t p, int chrd, int voic)
{
    if (voic < 1) voic = 1;
    if (voic > NV) voic = NV;
    const int8_t *c = wcf_chord[chrd & 31];
    for (int v = 0; v < NV; ++v) {
        if (v < voic) eng_on(e, v, wcf_inc(p + 256 * c[v]), gain_n[voic]);
        else eng_off(e, v);
    }
}

void wcf_knobs(Engine *e, int fram, int atk, int rel)
{
    if (fram > 127) fram = 127;
    if (atk > 127) atk = 127;
    if (rel > 127) rel = 127;
    eng_pos(e, (fram * POS_MAX) / 127);
    e->atk_d0 = wcf_tc[atk];
    e->rel_d0 = wcf_tc[rel];
}
