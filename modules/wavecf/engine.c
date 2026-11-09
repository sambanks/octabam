/* WAVE engine; see engine.h for the formats and the licence. */
#include "engine.h"

#include "fx.h"

enum { IDLE, ATTACK, SUSTAIN, RELEASE };

#define ONE27 (1 << 27)
#define ATK_TGT_Q27 135559905
#define REL_TARGET (-1342177)          /* -0.01, Q27 */
#define POS_SLEW 8                     /* the position closes 1/256 of the gap a sample */

void eng_init(Engine *e, const int16_t *table, int32_t atk_d0, int32_t rel_d0)
{
    int32_t *p = (int32_t *)e;
    for (unsigned i = 0; i < sizeof(Engine) / 4; ++i) p[i] = 0;
    e->table = table;
    e->atk_d0 = atk_d0;
    e->rel_d0 = rel_d0;
    e->glide = 1 << 28;                    /* 1/8 a call: about 3 ms */
    e->fps = 345;                          /* 120 BPM at 1x until a step has been timed */
    e->last_step = -1;
}

void eng_adsr(Engine *e, int32_t atk_d0, int32_t rel_d0)
{
    e->atk_d0 = atk_d0;
    e->rel_d0 = rel_d0;
}

void eng_setup(Engine *e, int32_t lfo_amp, uint32_t lfo_inc, int32_t drive, int32_t makeup, int32_t poly, int32_t tune_off)
{
    e->lfo_amp = lfo_amp;
    e->lfo_inc = lfo_inc;
    e->drive = drive;
    e->makeup = makeup;
    e->poly = poly;
    e->tune_off = tune_off;
}

/* a triangle, Q30, -1 .. 1 */
static inline int32_t tri30(uint32_t ph)
{
    int32_t s = (int32_t)(ph ^ 0x80000000u);
    return (s ^ (s >> 31)) - (1 << 30);
}

/* 2^x for |x| <= 1/6 (x Q30), cubic, result Q30 */
static inline int32_t exp2_30(int32_t x)
{
    int32_t y = mul(x, 1488522236);                /* x ln2, Q30 */
    int32_t y2 = mul(y, y);                        /* y^2 / 2, Q30 */
    int32_t y3 = mul(y2, y);                       /* y^3, Q28 */
    return (1 << 30) + y + y2 + mul(y3, 1431655765);   /* + y^3 / 6, Q30 */
}

void eng_pos(Engine *e, int32_t pos)
{
    if (pos < 0) pos = 0;
    if (pos > POS_MAX) pos = POS_MAX;
    e->pos_tgt = pos;
}

void eng_on(Engine *e, int v, uint32_t inc, int32_t gain)
{
    Voice *p = &e->v[v];
    p->inc_tgt = inc;
    if (p->mode == IDLE) p->inc = inc;      /* a silent voice starts at its pitch; a sounding one glides to it */
    p->gain = gain;
    p->gate = 1;
    p->gate_prev = 0;           /* a rising edge for the next render, also on a sounding voice */
}

void eng_off(Engine *e, int v)
{
    e->v[v].gate = 0;
}

void eng_render(Engine *e, int32_t *out, int n)
{
    /* the pitch LFO, once a call: +-2 semitones at full depth (CHOMPI's pitchLfo, 2^(lfo * 2 / 12)) */
    int32_t pmul = 1 << 30;
    if (e->lfo_amp) {
        int32_t pl = mul(tri30(e->lfo_ph), e->lfo_amp);
        pmul = exp2_30(mul(pl, 357913941));        /* x 1/6 */
        e->lfo_ph += e->lfo_inc * (uint32_t)n;
    }
    for (int k = 0; k < NV; ++k) {
        Voice *v = &e->v[k];
        v->inc += (uint32_t)mul((int32_t)v->inc_tgt - (int32_t)v->inc, e->glide);   /* the glide to the new pitch, a step a call */
        v->incm = pmul == (1 << 30) ? v->inc : (uint32_t)(mul((int32_t)v->inc, pmul) << 1);
    }

    int32_t g = e->amp_cur, tgt = e->amp_tgt, dg = 0;
    if (g == 0 && tgt == 0) {                       /* the AMP is closed: silence, and none of the voices' work */
        for (int i = 0; i < n; ++i) out[i] = 0;
        return;
    }
    if (tgt != g) dg = (tgt - g) / n;               /* a linear ramp across this call */

    for (; n > 0; --n) {
        e->pos += (e->pos_tgt - e->pos) >> POS_SLEW;
        int idx = e->pos >> 16;
        int32_t fa = (e->pos & 0xffff) << 15;                  /* Q31 */
        const int16_t *cur = e->table + idx * FLEN;
        const int16_t *nxt = cur + FLEN;

        int32_t sum = 0;
        Voice *v = e->v;
        for (int k = 0; k < NV; ++k, ++v) {
            /* Adsr::Process */
            int32_t g = v->gate;
            if (g && !v->gate_prev) v->mode = ATTACK;
            else if (!g && v->gate_prev) v->mode = RELEASE;
            v->gate_prev = g;
            int32_t env = v->env;
            if (v->mode == ATTACK) {
                env += mul(e->atk_d0, ATK_TGT_Q27 - env);
                if (env > ONE27) { env = ONE27; v->mode = SUSTAIN; }
            } else if (v->mode == RELEASE) {
                env += mul(e->rel_d0, REL_TARGET - env);
                if (env < 0) { env = 0; v->mode = IDLE; }
            }
            v->env = env;
            if (v->mode == IDLE) continue;

            /* wavetable::PopSample, two frames: each a linear interpolation, then the position's mix */
            uint32_t ph = v->phase;
            int i = ph >> 22;
            int32_t fr = (ph >> 8) & 0x3fff;
            int j = (i + 1) & (FLEN - 1);
            int32_t a1 = cur[i], a2 = cur[j], b1 = nxt[i], b2 = nxt[j];
            int32_t a = (a1 << 12) + ((fr * (a2 - a1)) >> 2);
            int32_t b = (b1 << 12) + ((fr * (b2 - b1)) >> 2);
            int32_t s = a + mul(b - a, fa);
            v->phase = ph + v->incm;
            sum += mul(mul(s, v->gain), env) << 4;
        }
        if (e->drive) {                                        /* COMP: drive into the cubic soft clip y = x - x^3 / 3 */
            int32_t t = mul(sum, e->drive);                    /* Q22 */
            if (t > (1 << 22)) t = 1 << 22;
            if (t < -(1 << 22)) t = -(1 << 22);
            t <<= 8;                                           /* Q30 */
            int32_t t3 = mul(mul(t, t), t);                    /* Q28 */
            int32_t y = t - (mul(t3, 715827883) << 2);         /* Q30 */
            sum = mul(y, e->makeup);                           /* Q27 */
        }
        g += dg;
        *out++ = mul(sum, g) << 1;                 /* the AMP level, Q30 */
    }
    e->amp_cur = tgt;
}
