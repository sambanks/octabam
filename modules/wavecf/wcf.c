/* WAVE's note layer; see wcf.h.  Tables: wcf_data.c (tables.py). */
#include "wcf.h"
#include "fx.h"

extern const uint32_t wcf_base_inc;
extern const int32_t wcf_exp2[385];
extern const int32_t wcf_tc[128];
extern const int8_t wcf_chord[32][4];
extern const int32_t wcf_lfo[128];
extern const int32_t wcf_comp_drive[128];
extern const int32_t wcf_comp_makeup[128];
extern const int32_t wcf_glide[128];

/* 0.8 / n, Q31: four voices at the table amplitude sum to 0.36 at most */
static const int32_t gain_n[5] = {0, 1717986918, 858993459, 572662306, 429496730};

/* p (Q8 semitones above C3) moved to the nearest degree of the scale by whole semitones: the pitch class from C,
 * the lower candidate first at each distance (ties go down), as the quantizer does (modules/cxosc po_snap) */
static int32_t snap(int32_t p, uint32_t mask)
{
    if (!mask) return p;
    int32_t n = ((p + 128 + 120 * 256) >> 8) + 1080;      /* the nearest semitone number from C, biased positive */
    int32_t pc = n % 12;
    for (int d = 0; d <= 6; ++d) {
        int lo = pc - d;
        if (lo < 0) lo += 12;
        if (mask & (1u << lo)) return p - 256 * d;
        int hi = pc + d;
        if (hi >= 12) hi -= 12;
        if (mask & (1u << hi)) return p + 256 * d;
    }
    return p;
}

void wcf_scale(Engine *e, uint32_t mask)
{
    e->scale = mask & 0xfff;
}

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
    if (e->poly) {                                  /* POLY: one note on the next voice of the pool; the others keep sounding */
        int v = e->next;
        if (v >= voic) v = 0;
        eng_on(e, v, wcf_inc(snap(p + e->tune_off, e->scale)), gain_n[voic]);
        e->next = v + 1;
        for (v = voic; v < NV; ++v) eng_off(e, v);
        return;
    }
    const int8_t *c = wcf_chord[chrd & 31];
    int lift = e->spread >> 5;                      /* SPRD 0..127: 0..3 of the upper notes (the 2nd, then the 3rd, the 4th) go up an octave */
    for (int v = 0; v < NV; ++v) {
        int iv = c[v] + (v >= 1 && v <= lift ? 12 : 0);
        if (v < voic) eng_on(e, v, wcf_inc(snap(p + e->tune_off + 256 * iv, e->scale)), gain_n[voic]);
        else eng_off(e, v);
    }
    e->next = 0;
}

void wcf_init(Engine *e, const int16_t *table)
{
    eng_init(e, table, wcf_tc[20], wcf_tc[60]);
}

void wcf_knobs(Engine *e, int fram, int sprd, int glid)
{
    if (fram > 127) fram = 127;
    if (sprd > 127) sprd = 127;
    if (glid > 127) glid = 127;
    eng_pos(e, (fram * POS_MAX) / 127);
    e->spread = sprd;
    e->glide = wcf_glide[glid];
}


void wcf_setup(Engine *e, int vibr, int vrat, int oct, int fine, int comp, int mode)
{
    if (vibr > 127) vibr = 127;
    if (vrat > 127) vrat = 127;
    if (comp > 127) comp = 127;
    if (oct > 2) oct = 2;
    int f = fine > 127 ? 127 : fine;
    eng_setup(e, vibr * 16909320,                              /* depth: vibr / 127, Q31 */
              (uint32_t)wcf_lfo[vrat], wcf_comp_drive[comp], wcf_comp_makeup[comp], mode ? 1 : 0,
              (oct - 1) * 12 * 256 + (f - 64) * 2);             /* OCT: -1 / 0 / +1 octave; FINE: +-1/2 semitone */
}
