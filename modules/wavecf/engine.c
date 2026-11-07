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
    p->inc = inc;
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
            v->phase = ph + v->inc;
            sum += mul(mul(s, v->gain), env) << 4;
        }
        *out++ = sum;
    }
}
