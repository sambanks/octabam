/* DRUMMER -- the drummer engine. drummer.h says what it answers and the
 * rules it keeps; this file is the musical part: the style tables, the
 * collision law, the humanisation and the breaks.
 *
 * The style tables are original, written for this module. One character per
 * 16th: '.' never, '1'..'9' a probability of 10..90 %, 'X' always.
 *   core  the groove at DENS 64, CPLX 0
 *   cplx  what CPLX adds (syncopations, off-beat kicks, ghost notes)
 *   fill  the bar's end when a fill plays (VAR at a phrase's end, BRK 32..63) */
#include "drummer.h"

typedef DrStyle Style;

#include "styles.inc"
_Static_assert(DR_N_STYLES == DR_STYLES, "drummer.h's DR_STYLES is styles.py's count");

static const uint8_t BASE_VEL[DR_ZONES] = { 100, 100, 40, 80, 85, 80, 112, 95, 75 };
static const uint8_t MIX_OF[DR_ZONES] = { DR_MIX_KICK, DR_MIX_SNARE, DR_MIX_SNARE, DR_MIX_HATS, DR_MIX_HATS,
                                          DR_MIX_CYMB, DR_MIX_CYMB, DR_MIX_TOMS, DR_MIX_PERC };
/* The default priority (image 58): TOM and PERC above HAT C and RIDE (a
 * style's perc and toms take their steps from the closed hats; under them,
 * every written perc on a 16th-hat level was never heard), under HAT O. */
/* A zone the kit has not: the first of these it has (image 58). */
static const uint8_t SUBST[DR_ZONES][3] = {
    { DR_TOM, DR_PERC, DR_OUT },              /* KICK */
    { DR_GHOST, DR_PERC, DR_TOM },            /* SNARE */
    { DR_SNARE, DR_PERC, DR_OUT },            /* GHOST (a soft SNARE before this) */
    { DR_HATO, DR_RIDE, DR_PERC },            /* HAT C */
    { DR_HATC, DR_RIDE, DR_CRASH },           /* HAT O */
    { DR_HATC, DR_HATO, DR_PERC },            /* RIDE */
    { DR_HATO, DR_RIDE, DR_HATC },            /* CRASH */
    { DR_PERC, DR_SNARE, DR_OUT },            /* TOM */
    { DR_TOM, DR_HATC, DR_RIDE },             /* PERC */
};
static const uint8_t PRIO[DR_ZONES] = { DR_KICK, DR_SNARE, DR_CRASH, DR_HATO, DR_TOM, DR_PERC, DR_HATC, DR_RIDE, DR_GHOST };
#define LIGHT ((1u << DR_GHOST) | (1u << DR_HATC) | (1u << DR_HATO) | (1u << DR_PERC))

/* ---- small helpers ---------------------------------------------------- */

static uint32_t mix(uint32_t h)
{
    h ^= h >> 15; h *= 0x2c1b3c6du;
    h ^= h >> 12; h *= 0x297a2d39u;
    h ^= h >> 15;
    return h;
}

/* A number from (seed, a, b, c), the same on every pass that asks the same. */
static uint32_t rnd(unsigned seed, uint32_t a, uint32_t b, uint32_t c)
{
    return mix(seed * 0x9e3779b1u ^ a * 0x85ebca77u ^ b * 0xc2b2ae3du ^ c * 0x27d4eb2fu ^ 0x6a09e667u);
}

static unsigned cell(const char *row, unsigned step)
{
    char c;
    if (!row)
        return 0;
    c = row[step];
    if (c == 'X')
        return 100;
    if (c >= '1' && c <= '9')
        return (unsigned)(c - '0') * 10;
    return 0;
}


/* An aspect under HUMN: HUMN 64 gives the aspect as set, 127 twice that (0..252). */
static unsigned amt(unsigned human, unsigned aspect)
{
    return (human * aspect + 32) / 64;
}

static int clampi(int v, int lo, int hi)
{
    return v < lo ? lo : v > hi ? hi : v;
}

static unsigned popcount(unsigned m)
{
    unsigned n = 0;
    while (m) {
        m &= m - 1;
        n++;
    }
    return n;
}

/* Slices of zone z in role r, in slice order: the n-th one, or the count. */
static unsigned slices_of(const DrKit *k, unsigned z, unsigned r, unsigned nth, unsigned *found)
{
    unsigned i, n = 0;
    for (i = 0; i < k->count && i < DR_SLICES; i++) {
        if (k->zone[i] == z && k->role[i] == r) {
            if (n == nth && found)
                *found = i;
            n++;
        }
    }
    return n;
}

static unsigned zone_has(const DrKit *k, unsigned z)
{
    unsigned i;
    for (i = 0; i < k->count && i < DR_SLICES; i++)
        if (k->zone[i] == z)
            return 1;
    return 0;
}

static const Style *style_of(const DrParams *p)
{
    return &STYLES[p->style < DR_STYLES ? p->style : 0];
}

unsigned dr_style_len(unsigned style)
{
    return STYLES[style < DR_STYLES ? style : 0].len;
}

const char *dr_style_name(unsigned style)
{
    return STYLE_NAMES[style < DR_STYLES ? style : 0];
}

/* CPLX through the written levels: 0 BASIC, 64 STANDARD, 127 COMPLEX; in
 * between, the next level's cells come in (or the dropped ones go) one at a
 * time, in an order fixed per style, zone and step: the groove does not move
 * from bar to bar. */
static unsigned level_cell(const DrParams *p, const Style *st, unsigned z, unsigned step)
{
    unsigned pos = p->cplx * 256u / 127u, a = pos >> 7, f = pos & 127u, va, vb, th;
    if (a >= 2)
        return cell(st->lv[2][z], step);
    va = cell(st->lv[a][z], step);
    vb = cell(st->lv[a + 1][z], step);
    if (va == vb)
        return va;
    th = mix(p->style * 977u + z * 131u + step * 7919u + a * 104729u) & 127u;
    return f > th ? vb : va;
}

static unsigned any_level(const Style *st, unsigned z, unsigned step)
{
    return cell(st->lv[0][z], step) || cell(st->lv[1][z], step) || cell(st->lv[2][z], step);
}

/* ---- the groove --------------------------------------------------------- */

static unsigned backbone(unsigned z, unsigned step)
{
    return (z == DR_KICK && step == 0) || (z == DR_SNARE && (step == 4 || step == 12));
}

/* SEED in bands (image 62): 0 the style's table; 1-127 eight bands of
 * sixteen (the last fifteen), the band how far from the table (12 % of the
 * cells touched in band 1, 60 % in band 8), the place in the band the variant
 * (1-16). A variant is the same one in every band, harder in each: a cell
 * touched in a band is touched the same way in every band above. Every other
 * draw of the engine (ghosts, humanisation, fills, BRK) is keyed on the
 * variant alone, so a band change keeps the feel and moves the groove. */
static unsigned seed_band(unsigned v) { return v ? (v - 1u) / 16u : 0; }       /* 0..7 */
unsigned dr_seed_variant(unsigned v) { return v ? (v - 1u) % 16u + 1u : 0; }  /* 0 the table, 1..16 */

/* A touched cell is emptied, filled or takes its neighbour's (a 16th or an 8th
 * away: the syncopations move), a third each; the kick on 1 and the snares on
 * 2 and 4 stay. */
static unsigned core_of(const DrParams *p, const Style *st, unsigned z, unsigned step)
{
    unsigned core = level_cell(p, st, z, step), var = dr_seed_variant(p->seed), touched, act;
    if (!var || (backbone(z, step) && core == 100))
        return core;
    touched = 12u + seed_band(p->seed) * 48u / 7u;
    if (rnd(var, 300 + z, step, 7) % 100 >= touched)
        return core;
    act = rnd(var, 310 + z, step, 7) % 6;
    if (act < 2)
        return 0;
    if (act < 4)
        return core > 80 ? core : (z == DR_KICK || z == DR_SNARE || z == DR_HATC || z == DR_GHOST ||
                                   z == DR_PERC || z == DR_TOM) ? 85 : core;
    return level_cell(p, st, z, (step ^ (act & 1 ? 1u : 2u)) % st->len);
}

static unsigned groove_prob(const DrParams *p, const Style *st, unsigned z, unsigned step)
{
    unsigned core = core_of(p, st, z, step), cx = cell(st->lv[2][z], step), d = p->dens, pr;
    if (core == 100 && d >= 16 && backbone(z, step))
        return 100;              /* the backbone stays down to DENS 16 */
    pr = d < 64 ? core * (d + 16) / 80 : core;
    if (d > 64 && (core || cx))
        pr += (100 - (pr > 100 ? 100 : pr)) * (d - 64) / 128;
    return pr > 100 ? 100 : pr;
}

static unsigned groove_hits(const DrParams *p, const Style *st, unsigned step)
{
    unsigned z, mask = 0;
    step %= st->len;
    for (z = 0; z < DR_ZONES; z++)
        if (rnd(dr_seed_variant(p->seed), 1 + z, step, 0) % 100 < groove_prob(p, st, z, step))
            mask |= 1u << z;
    return mask;
}

unsigned dr_groove_hits(const DrKit *k, const DrParams *p, unsigned step)
{
    (void)k;
    return groove_hits(p, style_of(p), step);
}

/* ---- REDRUM (image 77) ----------------------------------------------------
 * The loop: each slice on the step its hit falls on (its start plus its
 * ALIGN), the trim being the bars TRIM_BARS says (else the tempo's; else one;
 * whole bars, 1 2 4 or 8, since image 78), its place off the step kept (1/24 step). Two slices on one step: the first
 * kept. */
/* The span the loop is laid on (the trim; the slices' own extent, first start to last end, when no
 * whole slice is in it: a trim the slot left unset, 0..64 frames under the port) and its steps: TRIM_BARS's bars (else the tempo's,
 * else one) to the nearest of 1, 2, 4, 8 whole bars (image 78: a loop of 6.4 bars, the project's
 * tempo on a slot that never had its own, played 102 steps off the bar), 0 none. */
static unsigned loop_span(const uint32_t *bounds, unsigned n, uint32_t *ts, uint32_t *te,
                          unsigned bars100, unsigned tempo24)
{
    uint32_t lo = 0xffffffffu, hi = 0, len, steps;
    unsigned i, in = 0, p;
    for (i = 0; i < n && i < DR_SLICES; i++) {
        uint32_t a = bounds[3 * i], e = bounds[3 * i + 1];
        in += a >= *ts && e <= *te && e > a;
        if (a < lo)
            lo = a;
        if (e > hi)
            hi = e;
    }
    if (!n)
        return 0;
    if (!in) {
        if (hi <= lo)
            return 0;
        *ts = lo;
        *te = hi;
    }
    len = *te - *ts;
    steps = bars100 * 16u / 100u;
    if (!steps && tempo24)                       /* frames x BPM / (44100 x 60 / 4): 16ths */
        steps = (len / 100u * tempo24 / 24u + 3307u) / 6615u;
    if (!steps)
        steps = 16;
    if (steps > 1024)
        steps = 1024;
    for (p = 16; p < DR_LOOP_STEPS && steps * steps > 2u * p * p; p *= 2)
        ;                                        /* up while past p x sqrt 2 */
    return p;
}

unsigned dr_loop_steps(const uint32_t *bounds, unsigned n, uint32_t trim_start, uint32_t trim_end,
                       unsigned bars100, unsigned tempo24)
{
    return loop_span(bounds, n, &trim_start, &trim_end, bars100, tempo24);
}

void dr_loop_build(DrLoop *l, const uint32_t *bounds, unsigned n, uint32_t trim_start, uint32_t trim_end,
                   unsigned bars100, unsigned tempo24, const uint8_t *align_ms)
{
    uint32_t len, steps, sh = 0;
    unsigned i;
    l->len = 0;
    for (i = 0; i < DR_LOOP_STEPS; i++) {
        l->slice[i] = 0;
        l->mt[i] = 0;
    }
    l->pad = 0;
    steps = loop_span(bounds, n, &trim_start, &trim_end, bars100, tempo24);
    len = trim_end > trim_start ? trim_end - trim_start : 0;
    if (!steps || !len)
        return;
    while ((len >> sh) > (1u << 20))
        sh++;
    for (i = 0; i < n && i < DR_SLICES; i++) {
        uint32_t at = bounds[3 * i] + (align_ms ? align_ms[i] * 441u / 10u : 0u), pos, s0;
        if (at < trim_start || at >= trim_end)
            continue;
        pos = ((at - trim_start) >> sh) * (steps * 24u) / (len >> sh);   /* 1/24 step */
        s0 = (pos + 12u) / 24u;
        if (l->slice[s0 % steps])
            continue;
        l->slice[s0 % steps] = (uint8_t)(i + 1u);
        l->mt[s0 % steps] = (int8_t)((int)pos - (int)(s0 * 24u));
    }
    l->len = (uint8_t)steps;
}

/* The bar of the loop as a style: BASIC the loop's hits but its soft slices
 * and ghosts, STANDARD the loop, COMPLEX the loop and the style's COMPLEX
 * cells on the steps the loop leaves free (CPLX brings them in one at a time
 * past 64: the loop's own hits never lose to them); the style's fills and
 * their colour, no lay-back nor swing of its own (the loop has its feel). A
 * slice OUT of the kit (a SIMILAR copy) is in no row: dr_step plays it raw. */
static const Style *loop_style(const DrKit *k, const DrParams *p, uint32_t bar)
{
    const Style *own = style_of(p), *rock = &STYLES[10];
    const DrLoop *l = p->loop;
    DrLoopBar *b = p->bar;
    Style *st = &b->style;
    unsigned z, s, v, i;
    for (v = 0; v < 3; v++)
        for (z = 0; z < DR_ZONES; z++) {
            for (s = 0; s < DR_STEPS; s++) {
                unsigned o = l->slice[(bar * DR_STEPS + s) % l->len];
                b->row[v][z][s] = (char)(v == 2 && !(o && o <= k->count) && own->len == DR_STEPS && own->lv[2][z]
                                         ? own->lv[2][z][s] : '.');
            }
            b->row[v][z][DR_STEPS] = 0;
        }
    for (s = 0; s < DR_STEPS; s++) {
        unsigned o = l->slice[(bar * DR_STEPS + s) % l->len], zn, m;
        if (!o || o > k->count)
            continue;
        i = o - 1u;
        zn = k->zone[i];
        m = zn < DR_ZONES ? 1u << zn : zn == DR_COMBO ? k->combo[i] : 0u;
        for (z = 0; z < DR_ZONES; z++)
            if (m & (1u << z)) {
                b->row[1][z][s] = b->row[2][z][s] = 'X';
                if (zn == DR_COMBO || (k->role[i] != DR_SOFT && z != DR_GHOST))
                    b->row[0][z][s] = 'X';
            }
    }
    for (v = 0; v < 3; v++)
        for (z = 0; z < DR_ZONES; z++)
            st->lv[v][z] = b->row[v][z];
    for (z = 0; z < DR_ZONES; z++)
        st->fill[z] = own->len == DR_STEPS ? own->fill[z] : rock->fill[z];
    st->late = st->swing = 0;
    st->len = DR_STEPS;
    for (i = 0; i < 4; i++)
        st->fam[i] = own->fam[i];
    return st;
}

static unsigned fill_mask(const Style *st, unsigned step)
{
    unsigned z, mask = 0;
    for (z = 0; z < DR_ZONES; z++)
        if (cell(st->fill[z], step))
            mask |= 1u << z;
    return mask;
}

/* ---- the fill library (image 72; FILLS, image 74) ----------------------
 * ORN sends a share of the fills (none at 0, 32 % at 16, 90 % from 45) to a
 * library; the style's weights (styles.py FILL_COLOUR) draw the family:
 *   written   the style's own fill row
 *   rudiment  a sticking played round the kit: single, double, paradiddle,
 *             inverted paradiddle (RLLR LRRL), paradiddle-diddle, six-stroke,
 *             double paradiddle, linear fills with the kick, flam tap, drag,
 *             ratamacue, five-stroke roll
 *   triplet   the 6/8 feel: 8th triplets (three hits a beat, at 0, +1/3 and
 *             -1/3 of a step), sextuplets (six a beat: the pairs one hit and
 *             its retrig 2/3 of a step later, on the same drum), or 8th
 *             triplets breaking into sextuplets on the last beat; in 12/8 the
 *             grid's own triplets, doubled
 *   3 over 4  groups of three 16ths across the beat (of two 8ths in 12/8)
 * A sticking letter is a hand: R L upper case accented, r l not, k K a kick,
 * F G an accent with its flam (a retrig 3/24 later), D E a doubled stroke (a
 * retrig 6/24 later: drags, the five-stroke roll). The orchestration, drawn
 * per fill: the right hand round the toms (their slices in slice order,
 * across the fill: from the first tom to the last) and the left on the snare;
 * everything on the snare (the accents out, the rest soft); or the hands
 * swapped. A non-written fill starts on a beat. Every draw is keyed on the
 * style too: two styles on one SEED fill differently. FILLS (p->fill, the
 * window after KIT BALANCE) sets any of these by hand, AUTO each: the
 * family, how often, how long, the sticking, the orchestration, the
 * triplets. */
enum { FF_WRITTEN, FF_RUDIMENT, FF_TRIPLET, FF_HEMIOLA };
enum { FO_AROUND, FO_SNARE, FO_SWAP };
static const char *const RUDIMENTS[] = { "Rlrl", "RrLl", "RlrrLrll", "RllrLrrl", "Rlrrll", "RllrrL",
                                         "RlrlrrLrlrll", "Rlk", "Rllk", "FrGl", "ERDL", "ErlRDlrL", "DERl" };
static const char *const RUDIMENT_NAMES[] = { "SNGL", "DBLE", "PARA", "INVP", "PDDL", "SIXS",
                                              "DPAR", "LIN3", "LIN4", "FTAP", "DRAG", "RTMQ", "FIVE" };
static const char *const TRIPLETS[] = { "RlrLrl", "Rll", "RllrrL", "Rlrrll", "Rlk", "Frl", "FlrGrl" };
static const char *const TRIPLET_NAMES[] = { "TRPL", "RLL", "SIXS", "PDDL", "LIN", "SWIS", "FACC" };
static const char *const HEMIOLAS[] = { "Rll", "Rlk", "Kll", "Fll" };
static const char *const HEMIOLA_NAMES[] = { "TSS", "LIN", "KSS", "FSS" };
#define NELEM(a) (sizeof(a) / sizeof((a)[0]))
_Static_assert(NELEM(RUDIMENTS) == NELEM(RUDIMENT_NAMES) && NELEM(TRIPLETS) == NELEM(TRIPLET_NAMES)
               && NELEM(HEMIOLAS) == NELEM(HEMIOLA_NAMES), "a name a sticking");

unsigned dr_fill_sticks(unsigned fam)
{
    return fam == FF_RUDIMENT ? NELEM(RUDIMENTS) : fam == FF_TRIPLET ? NELEM(TRIPLETS)
         : fam == FF_HEMIOLA ? NELEM(HEMIOLAS) : 0;
}

const char *dr_fill_stick_name(unsigned fam, unsigned n)
{
    unsigned c = dr_fill_sticks(fam);
    if (!c)
        return "--";
    n %= c;
    return fam == FF_RUDIMENT ? RUDIMENT_NAMES[n] : fam == FF_TRIPLET ? TRIPLET_NAMES[n] : HEMIOLA_NAMES[n];
}

static const char *stick_of(unsigned fam, unsigned n)
{
    unsigned c = dr_fill_sticks(fam);
    n %= c;
    return fam == FF_RUDIMENT ? RUDIMENTS[n] : fam == FF_TRIPLET ? TRIPLETS[n] : HEMIOLAS[n];
}

typedef struct {
    uint8_t fam, orch, stick, kind;  /* kind: 0 8th triplets, 1 sextuplets, 2 8ths then sextuplets */
    uint8_t from;                /* the fill's first step */
    int8_t mt;                   /* this step's stroke: its place, 1/24 step */
    uint8_t rtrg, rtim, acc;     /* its retrig (a sextuplet's pair, a flam, a double), accented */
    uint8_t slice;               /* a tom slice + 1, 0 the zone's own pick */
} Fill;

static unsigned fill_family(const DrParams *p, const Style *st, unsigned seed, uint32_t bar)
{
    unsigned share = p->orn * 2u, w, r, f, tot = 0;
    if (p->fill[DR_F_FILL])                      /* FILLS: the family set */
        return p->fill[DR_F_FILL] <= DR_FILL_MAX ? p->fill[DR_F_FILL] - 1u : FF_WRITTEN;
    if (p->fill[DR_F_TRIP] && p->fill[DR_F_TRIP] <= DR_TRIP_MAX)
        return FF_TRIPLET;                       /* TRIP set, FILL AUTO: TRIP asks for triplets (image 78) */
    if (share > 90)
        share = 90;
    if (rnd(seed, bar, 110, p->style) % 100 >= share)
        return FF_WRITTEN;
    for (f = 0; f < 4; f++)
        tot += st->fam[f];
    if (!tot)
        return FF_WRITTEN;
    r = rnd(seed, bar, 111, p->style) % tot;
    for (f = 0; f < 4; f++) {
        w = st->fam[f];
        if (r < w)
            return f;
        r -= w;
    }
    return FF_WRITTEN;
}

/* The n-th TOM slice in slice order (n < the count) in *slice; the count. */
static unsigned tom_slices(const DrKit *k, unsigned nth, unsigned *slice)
{
    unsigned i, n = 0;
    for (i = 0; i < k->count && i < DR_SLICES; i++)
        if (k->zone[i] == DR_TOM) {
            if (n == nth && slice)
                *slice = i;
            n++;
        }
    return n;
}

/* The zone this step of a library fill plays (DR_OUT a rest), its stroke in f. */
static unsigned fill_stroke(const DrKit *k, const Style *st, Fill *f, unsigned step)
{
    unsigned L = st->len, beat = L == 12 ? 3u : 4u, rel = step - f->from, n = L - f->from, j = rel, b, r;
    unsigned zone, ntom, tom = 0, right;
    const char *stick = stick_of(f->fam, f->stick);
    char c;
    f->mt = 0; f->rtrg = 0; f->rtim = 0; f->slice = 0;
    if (f->fam == FF_HEMIOLA) {
        j = rel % (L == 12 ? 2u : 3u);           /* groups of three 16ths (two 8ths in 12/8) */
    } else if (f->fam == FF_TRIPLET) {
        unsigned last = rel >= n - beat, sext = f->kind == 1 || (f->kind == 2 && last);
        b = rel / beat;
        r = rel % beat;
        if (L == 12) {                           /* the grid is the triplet: sextuplets double it */
            if (sext) {
                f->rtrg = 1; f->rtim = 12;
                j = 2 * rel;
            }
        } else if (!sext) {                      /* three a beat: 0, 1 + 1/3, 3 - 1/3 */
            static const int8_t MT[4] = { 0, 8, 0, -8 };
            static const uint8_t PULSE[4] = { 0, 1, 0xff, 2 };
            if (PULSE[r] == 0xff)
                return DR_OUT;
            j = 3 * b + PULSE[r];
            f->mt = MT[r];
        } else {                                 /* six a beat: 0, 2/3 (+ 4/3), 2, 2 + 2/3 (+ 3 + 1/3) */
            static const uint8_t PULSE[4] = { 0, 1, 3, 4 };
            j = 6 * b + PULSE[r];
            if (r & 1) {
                f->mt = -8;
                f->rtrg = 1;
                f->rtim = 16;
            }
        }
    }
    {
        unsigned len = 0;
        while (stick[len])
            len++;
        c = stick[j % len];
    }
    f->acc = (c >= 'A' && c <= 'Z') && c != 'D' && c != 'E';
    if (!f->rtrg && (c == 'F' || c == 'G')) {
        f->rtrg = 1; f->rtim = 3;                /* a flam */
    } else if (!f->rtrg && (c == 'D' || c == 'E')) {
        f->rtrg = 1; f->rtim = 6;                /* a double: drags, five-stroke */
    }
    if (c == 'k' || c == 'K')
        return DR_KICK;
    right = c == 'R' || c == 'r' || c == 'F' || c == 'D';
    zone = f->orch == FO_SNARE ? DR_SNARE : (right ^ (f->orch == FO_SWAP)) ? DR_TOM : DR_SNARE;
    if (zone == DR_TOM && (ntom = tom_slices(k, 0, 0)) != 0) {
        tom_slices(k, rel * ntom / (n ? n : 1), &tom);   /* round the toms, across the fill */
        f->slice = (uint8_t)(tom + 1);
    }
    return zone;
}

/* ---- dr_step ------------------------------------------------------------ */

void dr_kit_init(DrKit *k, unsigned count)
{
    unsigned i;
    for (i = 0; i < DR_SLICES; i++) {
        k->zone[i] = DR_OUT;
        k->role[i] = DR_NORMAL;
        k->combo[i] = 0;
    }
    k->count = (uint8_t)(count > DR_SLICES ? DR_SLICES : count);
    for (i = 0; i < DR_ZONES; i++)
        k->prio[i] = PRIO[i];
    k->reserved[0] = k->reserved[1] = 0;
}

/* The slice for zone z at level vel: its role's list (or the nearest role's),
 * the first one, or under ROUND another one than last time. */
static unsigned pick_slice(const DrKit *k, DrState *s, unsigned z, unsigned vel, unsigned round_amt,
                           uint32_t h, unsigned *ok)
{
    static const uint8_t ORDER[DR_ROLES][DR_ROLES] = {
        { DR_ACCENT, DR_NORMAL, DR_SOFT }, { DR_NORMAL, DR_ACCENT, DR_SOFT }, { DR_SOFT, DR_NORMAL, DR_ACCENT } };
    unsigned want = vel >= 105 ? DR_ACCENT : vel >= 60 ? DR_NORMAL : DR_SOFT, i, r, n = 0, idx, slice = 0;
    if (round_amt > 96 && (h >> 16) % 156 < round_amt - 96)
        want = (h >> 20) % DR_ROLES;                 /* ALT past half: any role of the zone */
    for (i = 0; i < DR_ROLES; i++) {
        r = ORDER[want][i];
        n = slices_of(k, z, r, 0, 0);
        if (n)
            break;
    }
    if (!n) {
        *ok = 0;
        return 0;
    }
    idx = s->last[z][r] < n ? s->last[z][r] : 0;
    if (!round_amt)
        idx = 0;
    else if (n > 1 && (h % 127) < (round_amt > 127 ? 127u : round_amt))
        idx = (idx + 1 + (h >> 8) % (n - 1)) % n;     /* any other one */
    s->last[z][r] = (uint8_t)idx;
    slices_of(k, z, r, idx, &slice);
    *ok = 1;
    return slice;
}

/* BRK past 96, beat b of the bar: 0 plays, 1 repeats the last hit, 2 a hole. A beat
 * acts on a chance growing with BRK (10 % at 96, every one at 127); an acting beat
 * repeats, one in six a hole, never the 1 nor two beats running (image 78: the holes
 * outweighed the repeats, a repeat playing only the steps that had a hit). */
static unsigned brk_cut(unsigned seed, uint32_t bar, unsigned b, unsigned brk)
{
    unsigned i, cut = 0, prev;
    for (i = 1; i <= b; i++) {
        prev = cut;
        cut = 0;
        if (rnd(seed, bar, 51, i) % 100 < (brk - 96u) * 3u + 10u)
            cut = rnd(seed, bar, 50, i) % 6u == 0 && prev != 2 ? 2u : 1u;
    }
    return cut;
}

void dr_step(const DrKit *k, const DrParams *p, DrState *s, uint32_t bar, unsigned step,
             unsigned forced, DrHit *out)
{
    const Style *st = style_of(p);
    const DrLoop *lp = p->loop && p->loop->len && p->bar ? p->loop : 0;
    unsigned own = 0, use_own = 0;                   /* REDRUM: the loop's slice + 1 on this step */
    int own_mt = 0;
    unsigned seed = dr_seed_variant(p->seed), phrase = p->phrase ? p->phrase : 4, brk = p->brk;
    unsigned h_var = amt(p->human, p->var), h_ghost = p->ghost;   /* GHST alone (image 65; x HUMN / 64 before: HUMN 64's level kept) */
    unsigned h_vel = amt(p->human, p->vel), h_round = amt(p->human, p->round);
    unsigned h_time = amt(p->human, p->time), h_orn = p->orn * 2u;   /* ORN alone (image 64; ORN x HUMN / 64 before): 127 reaches every ornament */
    unsigned mask, z, zone = DR_OUT, slice = 0, ok = 0, flags = 0, vel, fill_from = DR_STEPS, i, lib = 0, land;
    Fill fl;
    int mt = 0;

    unsigned L, beat;
    if (lp) {
        st = loop_style(k, p, bar);
        step %= DR_STEPS;
        own = lp->slice[(bar * DR_STEPS + step) % lp->len];
        own_mt = lp->mt[(bar * DR_STEPS + step) % lp->len];
        if (own > k->count)
            own = 0;
    }
    L = st->len; beat = L == 12 ? 3u : 4u;
    step %= L;
    fl.fam = FF_WRITTEN; fl.orch = 0; fl.stick = 0; fl.kind = 0; fl.from = 0;
    fl.mt = 0; fl.rtrg = 0; fl.rtim = 0; fl.acc = 0; fl.slice = 0;
    out->play = 0; out->slice = 0; out->vel = 0; out->mtime = 0;
    out->rtrg = 0; out->rtim = 0; out->zone = DR_OUT; out->flags = 0;

    /* 1. the groove, BRK's variation layer, the fills */
    mask = groove_hits(p, st, step);
    if (brk && brk < 32)
        for (z = 0; z < DR_ZONES; z++)
            if (rnd(seed, bar, 20 + z, step) % 100 < cell(st->lv[2][z], step) * brk / 32)
                mask |= 1u << z;
    /* VAR: past half, the groove changes from bar to bar (cells added where
     * the style has something, others dropped; never the backbone), up to a
     * third of them; fills at the phrase's end, and at every bar's end near
     * the top */
    if (h_var > 64) {
        unsigned rate = (h_var - 64) / 4;                /* % of the cells, 0..47 */
        for (z = 0; z < DR_ZONES; z++) {
            if (backbone(z, step) || rnd(seed, bar, 400 + z, step) % 100 >= rate)
                continue;
            if (mask & (1u << z))
                mask &= ~(1u << z);
            else if (any_level(st, z, step) || z == DR_HATC || z == DR_GHOST)
                mask |= 1u << z;
        }
    }
    {   /* the fills: BRK 32..63 asks for one at every bar's end (FILLS' FREQ 2BAR every 2nd, PHRS the
         * phrase's end), as long as BRK's place says (32 half a beat, 40 a beat, 48 two, 56 a bar) unless
         * FILLS' LONG says; FREQ AUTO also lets VAR place its own (the phrase's end; near the top most bars'
         * end; past half two beats, now and then a bar), FREQ BRK, 2BAR and PHRS do not (image 75) */
        unsigned freq = p->fill[DR_F_FREQ] <= DR_FREQ_MAX ? p->fill[DR_F_FREQ] : 0, lng = p->fill[DR_F_LONG];
        if (brk >= 32 && brk < 64
            && (freq <= 1 || (freq == 2 && bar % 2u == 1u) || (freq == 3 && bar % phrase == phrase - 1))) {
            unsigned z = (brk - 32u) / 8u;
            fill_from = z == 0 ? L - 2 : z == 1 ? L - beat : z == 2 ? L - 2 * beat : 0;
        } else if (freq == 0) {
            if (h_var && bar % phrase == phrase - 1 && rnd(seed, bar, 99, 0) % 127 < h_var)
                fill_from = L - 4;
            if (h_var > 160 && fill_from > L - 3 && rnd(seed, bar, 97, 0) % 92 < h_var - 160)
                fill_from = L - 3;               /* near the top: a short fill at most bars' end */
            if (fill_from == L - 4 && !lng && h_var > 64) {   /* VAR past half: two beats, now and then a bar */
                unsigned r = rnd(seed, bar, 96, 0) % 128;
                if (h_var > 110 && r < (h_var - 110) / 2)
                    fill_from = 0;
                else if (r < h_var - 64)
                    fill_from = L - 2 * beat;
            }
        }
        if (fill_from < L && lng)
            fill_from = lng == 1 ? L - beat : lng == 2 ? L - 2 * beat : 0;
    }
    if (fill_from < L) {
        fl.fam = (uint8_t)fill_family(p, st, seed, bar);
        if (fl.fam != FF_WRITTEN) {
            fl.from = (uint8_t)(fill_from - fill_from % beat);
            {
                unsigned m = rnd(seed, bar, 113, p->style) % 24u, fs = p->fill[DR_F_STIK], c = dr_fill_sticks(fl.fam);
                unsigned o = p->fill[DR_F_ORCH], tk = p->fill[DR_F_TRIP];
                fl.orch = (uint8_t)(o && o <= DR_ORCH_MAX ? o - 1u : rnd(seed, bar, 112, p->style) % 3u);
                fl.stick = (uint8_t)(fs && p->fill[DR_F_FILL] && c ? (fs - 1u) % c : c ? m % c : 0);
                fl.kind = (uint8_t)(tk && tk <= DR_TRIP_MAX ? tk - 1u : m / 8u % 3u);
            }
            fill_from = fl.from;
        }
    }
    /* a fill of a beat or more lands on a crash, the next bar's 1 (image 76): the last step's
     * fill is kept in the state, so BRK let go as the fill ends still lands; a whole-bar fill
     * going on (BRK 56 held) lands when it stops */
    land = step == 0 && s->fill_len >= beat && !forced && fill_from > 0;
    s->fill_len = (uint8_t)(step >= fill_from ? L - fill_from : 0);
    if (step >= fill_from) {
        flags |= DRF_FILL;
        if (fl.fam == FF_WRITTEN) {
            mask = fill_mask(st, step);
        } else {
            z = fill_stroke(k, st, &fl, step);
            mask = z < DR_ZONES ? 1u << z : 0;
            lib = 1;
        }
    }
    if (h_var && step == 0 && bar && bar % phrase == 0 && rnd(seed, bar, 98, 0) % 127 < h_var)
        mask |= 1u << DR_CRASH;                      /* a phrase starts on a crash */
    if (land)
        mask |= (1u << DR_CRASH) | (1u << DR_KICK);
    if (brk >= 80 && brk < 96) {                     /* half-time: one snare, on 3 */
        mask &= ~(1u << DR_SNARE);
        if (step == L / 2)
            mask |= 1u << DR_SNARE;
    }

    /* KIT BALANCE, the zones' mix: below 64 a zone's hits drop out (all of them at
     * 0), above it the zone plays more: the cells any level of the style has
     * there, then (past 100) any step for the light zones, the 8ths for the
     * others. GHOST's soft snares follow SNARE's mix (step 4). */
    for (z = 0; z < DR_ZONES; z++) {
        unsigned m = p->mix[MIX_OF[z]];
        if (m < 64) {
            if ((mask & (1u << z)) && rnd(seed, bar, 600 + z, step) % 64 >= m)
                mask &= ~(1u << z);
        } else if (m > 64 && !(mask & (1u << z))) {
            unsigned cand = any_level(st, z, step) ? (m - 64) * 100u / 63u
                          : m <= 100 ? 0u
                          : (LIGHT >> z & 1u) || step % 2u == 0 ? (m - 100) * 3u : 0u;   /* light zones any
                                                                  * step, the others the 8ths */
            if (rnd(seed, bar, 620 + z, step) % 100 < cand)
                mask |= 1u << z;
        }
    }

    if (land && !(mask & (1u << DR_CRASH)))
        land = 0;                                    /* KIT BALANCE's CYMB took the crash */

    /* a kit with a RIDE on a style that writes none: every other phrase the
     * closed hats move to the ride (HUMAN and VAR past 32; HUMAN 0 untouched) */
    if (h_var > 32 && zone_has(k, DR_RIDE) && !any_level(st, DR_RIDE, step) && (bar / phrase) % 2u == 1u
        && (mask & (1u << DR_HATC)) && !(flags & DRF_FILL))
        mask = (mask & ~(1u << DR_HATC)) | (1u << DR_RIDE);

    /* 2. a zone carried from the step before (SHIFT) takes a free step */
    if (s->carry && !mask) {
        mask = 1u << (s->carry - 1);
        flags |= DRF_SHIFT;
    }
    s->carry = 0;

    /* zones the kit cannot play are not candidates; a GHOST without ghost
     * slices is a soft SNARE */
    if ((mask & (1u << DR_GHOST)) && !zone_has(k, DR_GHOST)) {
        mask &= ~(1u << DR_GHOST);
        if (!(mask & (1u << DR_SNARE)) && zone_has(k, DR_SNARE)) {
            mask |= 1u << DR_SNARE;
            flags |= DRF_GHOST;
        }
    }
    /* a fill's toms on a kit with no TOM: the snare plays them */
    if ((flags & DRF_FILL) && (mask & (1u << DR_TOM)) && !zone_has(k, DR_TOM) && zone_has(k, DR_SNARE))
        mask = (mask & ~(1u << DR_TOM)) | (1u << DR_SNARE);
    /* a zone the kit does not have: the nearest one it has (SUBST), so a kit
     * of three zones plays every style; none of them, the zone is silent */
    for (z = 0; z < DR_ZONES; z++)
        if ((mask & (1u << z)) && !zone_has(k, z)) {
            mask &= ~(1u << z);
            for (i = 0; i < 3; i++) {
                unsigned y = SUBST[z][i];
                if (y < DR_ZONES && zone_has(k, y)) {
                    mask |= 1u << y;
                    break;
                }
            }
        }

    /* the landing: a combo slice with the crash (and the kick when it plays), else the
     * crash alone, over the kick's priority; a kit with no crash at all lands as it would */
    if (land) {
        unsigned want = (1u << DR_CRASH) | (mask & (1u << DR_KICK));
        for (i = 0; i < k->count && i < DR_SLICES; i++)
            if (k->zone[i] == DR_COMBO && (k->combo[i] & want) == want) {
                zone = DR_COMBO; slice = i; ok = 1; flags |= DRF_COMBO;
                break;
            }
        if (!ok && zone_has(k, DR_CRASH))
            zone = DR_CRASH;
    }
    /* REDRUM: the loop's slice OUT of the kit (a SIMILAR copy) plays raw on its step, as DENS
     * and VAR's drops let it (no zone: KIT BALANCE and SEED do not reach it) */
    if (zone == DR_OUT && !mask && own && k->zone[own - 1u] == DR_OUT && !(flags & DRF_FILL)) {
        unsigned pr = p->dens < 64 ? (p->dens + 16u) * 100u / 80u : 100u;
        if (rnd(seed, bar, 500, step) % 100 < pr
            && !(h_var > 64 && rnd(seed, bar, 501, step) % 100 < (h_var - 64) / 4)) {
            zone = DR_COMBO; slice = own - 1u; ok = 1; use_own = 1;
        }
    }
    /* 3. collisions: the combo slice holding exactly these zones, else the priority */
    if (zone != DR_OUT) {
        /* the landing chose */
    } else if (popcount(mask) >= 2) {
        for (i = 0; i < k->count && i < DR_SLICES; i++)
            if (k->zone[i] == DR_COMBO && k->combo[i] == mask) {
                zone = DR_COMBO; slice = i; ok = 1; flags |= DRF_COMBO;
                break;
            }
        if (!ok) {
            for (i = 0; i < DR_ZONES; i++)
                if (mask & (1u << k->prio[i])) {
                    zone = k->prio[i];
                    break;
                }
            if (p->shift) {
                unsigned lose = mask & ~(1u << zone) & LIGHT;
                for (i = 0; i < DR_ZONES && lose; i++)
                    if (lose & (1u << k->prio[i])) {
                        s->carry = (uint8_t)(k->prio[i] + 1);
                        break;
                    }
            }
        }
    } else if (mask) {
        for (z = 0; z < DR_ZONES; z++)
            if (mask & (1u << z))
                zone = z;
    }

    /* a hat right after a crash would cut it: let the crash ring */
    if (!forced && (zone == DR_HATC || zone == DR_HATO) && s->since_crash >= 2 && s->since_crash <= 3 &&
        popcount(mask) == 1)
        zone = DR_OUT;

    /* 4. GHOST: soft snares on free steps, near the backbeat, not every bar */
    if (zone == DR_OUT && !forced && h_ghost && !lib) {
        unsigned w = L == 16 && (step == 3 || step == 5 || step == 11 || step == 13) ? 3 : step % beat ? 2 : 1;
        unsigned g = zone_has(k, DR_GHOST) ? DR_GHOST : zone_has(k, DR_SNARE) ? DR_SNARE : DR_OUT;
        if (g != DR_OUT && rnd(seed, bar, 30, step) % 400 * 64u < h_ghost * w / 2 * p->mix[DR_MIX_SNARE]) {
            zone = g;
            flags |= DRF_GHOST;
        }
    }

    /* 5. the track's trig plays, whatever the engine chose */
    if (forced) {
        flags |= DRF_FORCED;
        if (zone == DR_OUT) {
            zone = step % (2 * beat) == 0 ? DR_KICK : DR_SNARE;
            if (!zone_has(k, zone))
                for (i = 0, zone = DR_OUT; i < DR_ZONES; i++)
                    if (zone_has(k, k->prio[i])) {
                        zone = k->prio[i];
                        break;
                    }
            if (zone == DR_OUT && k->count) {
                zone = DR_COMBO;                     /* a kit with no zone: slice 0 */
                slice = 0; ok = 1;
            }
        }
    }
    /* BRK past 96: a repeated beat stutters on all its steps, the empty ones too (image 78) */
    if (zone == DR_OUT && brk >= 96 && s->prev_slice && brk_cut(seed, bar, step / beat, brk) == 1)
        zone = s->prev_zone ? s->prev_zone - 1u : DR_SNARE;
    if (zone == DR_OUT)
        goto done;
    /* REDRUM: the step plays the loop's own slice where it plays that slice's zone (or its combo) */
    if (own && !use_own && !(flags & (DRF_FILL | DRF_GHOST))) {
        unsigned oz = k->zone[own - 1u];
        use_own = (zone < DR_ZONES && zone == oz)
                  || (zone == DR_COMBO && oz == DR_COMBO && (flags & DRF_COMBO) && k->combo[slice] == k->combo[own - 1u]);
    }

    /* 6. the level: the zone's, shaped by the metre and a little chance (the loop's own slice
     * at its own level) */
    vel = (flags & DRF_GHOST) ? 40 : use_own ? 100 : zone == DR_COMBO ? 105 : BASE_VEL[zone];
    /* VEL: the metre (beats loud, off-16ths soft, hats the most) and chance;
     * twice as wide at HUMN 127; past that, random full accents */
    if (h_vel) {
        int off = L == 16 ? (step & 1) : step % beat != 0;
        int metric = step % beat == 0 ? 25 : !off ? 0 :
                     (zone == DR_HATC || zone == DR_HATO || zone == DR_RIDE) ? -42 : -24;
        int jitter = (int)(rnd(seed, bar, 40, step) % 49) - 24;
        vel = (unsigned)clampi((int)vel + (metric + jitter) * (int)h_vel / 127, 1, 127);
        if (h_vel > 96 && rnd(seed, bar, 41, step) % 100 < (h_vel - 96) / 4)
            vel = rnd(seed, bar, 42, step) & 1 ? 127 : 8;   /* past half: a full accent, or nearly nothing */
    }
    if (lib && zone != DR_COMBO && !forced)      /* a library fill: its accents, the rest under them */
        vel = zone == DR_KICK ? (fl.acc ? 112u : 88u) : fl.acc ? 120u : fl.orch == FO_SNARE ? 46u : 70u;
    if (flags & DRF_FILL)
        vel = (unsigned)clampi((int)vel + clampi(((int)step - (int)(L - 4)) * 6, -12, 18), 1, 127);
    if (forced && vel < 118)
        vel = 118;
    if (land && (zone == DR_CRASH || (flags & DRF_COMBO)) && vel < 116)
        vel = 116;                                   /* the landing, accented */

    /* 7. the slice: COMBO chosen above; BRK's shuffle and repeat; else the zone's */
    if (brk >= 96 && s->prev_slice) {
        unsigned cut = brk_cut(seed, bar, step / beat, brk);
        if (cut == 1 || (cut == 2 && forced)) {
            slice = s->prev_slice - 1; ok = 1; flags |= DRF_BREAK;
            zone = s->prev_zone ? s->prev_zone - 1u : zone;
            out->rtrg = (uint8_t)(1 + rnd(seed, bar, 52, step) % 3);
            out->rtim = (uint8_t)(brk >= 112 ? 6 : 12);
        } else if (cut == 2) {
            goto done;                                     /* a hole in the break */
        }
    }
    if (!ok && brk >= 64 && brk < 96 && rnd(seed, bar, 60, step) % 100 < (brk - 64) * 3) {
        unsigned n = 0, pick, j;
        for (j = 0; j < k->count && j < DR_SLICES; j++)
            n += k->zone[j] != DR_OUT;
        if (n) {
            pick = rnd(seed, bar, 61, step) % n;
            for (j = 0; j < k->count && j < DR_SLICES; j++)
                if (k->zone[j] != DR_OUT && !pick--) {
                    slice = j; ok = 1; flags |= DRF_BREAK;
                    break;
                }
        }
    }
    /* REDRUM: the loop's slice and its place off the step; ALT (x HUMN) swaps it now and then for
     * another of its zone -- the redrum -- a raw one (OUT of the kit) always plays itself */
    if (use_own && !(flags & DRF_BREAK)
        && (k->zone[own - 1u] == DR_OUT || !(h_round && rnd(seed, bar, 72, step) % 254 < h_round))) {
        slice = own - 1u; ok = 1; mt = own_mt;
    }
    if (!ok && h_round > 150 && zone < DR_ZONES && rnd(seed, bar, 71, step) % 100 < (h_round - 150) * 3 / 5) {
        /* ALT near the top: a neighbour's sound now and then */
        static const uint8_t NEXT[DR_ZONES] = { DR_TOM, DR_GHOST, DR_SNARE, DR_HATO, DR_RIDE, DR_HATC,
                                                 DR_RIDE, DR_KICK, DR_TOM };
        if (zone_has(k, NEXT[zone]))
            zone = NEXT[zone];
    }
    if (!ok && lib && zone == DR_TOM && fl.slice) {
        slice = fl.slice - 1u; ok = 1;           /* round the toms */
    }
    if (!ok)
        slice = pick_slice(k, s, zone, (flags & DRF_GHOST) ? 1 : vel, h_round, rnd(seed, bar, 70, step), &ok);
    if (!ok)
        goto done;

    /* 8. the timing: a laid-back snare, swung hats, a little looseness */
    /* SWNG: a laid-back snare, swung off-16ths (hats first); past HUMN x SWNG
     * 127 every off-16th shuffles, up to a third of a step (a triplet feel),
     * and the looseness grows */
    if (h_time) {
        unsigned odd = L == 16 ? (step & 1) : step % beat == 2;
        int loose = 2 + (int)h_time / 64;
        if (zone == DR_SNARE || zone == DR_GHOST)
            mt += (int)((st->late * 2 * h_time + 63) / 127);
        if (odd && (zone == DR_HATC || zone == DR_HATO || zone == DR_RIDE || (flags & DRF_GHOST)))
            mt += (int)(((st->swing + 2) * h_time + 63) / 127);
        if (odd && h_time > 127)
            mt += (int)((h_time - 127) * 8 / 125);
        mt += ((int)(rnd(seed, bar, 80, step) % (unsigned)(2 * loose + 1)) - loose) * (int)h_time / 127;
    }
    if (lib)
        mt += fl.mt;                             /* a triplet's place: the fill's, not the humanisation's */
    mt = clampi(mt, -23, 12);
    if (lib && fl.rtrg && !out->rtrg) {
        out->rtrg = fl.rtrg; out->rtim = fl.rtim;   /* a sextuplet's pair */
    }

    /* 9. ornaments: a rare flam on a loud snare, a roll closing a fill */
    /* ORN: flams on loud snares, a roll closing a fill; past half, ruffs
     * leading into the backbeat and doubled hats. Each ornament's spacing is
     * drawn from three, tight to open (image 68, the user's: not always the
     * tightest), on a draw of its own: the hits ornamented stay the same. */
    if (h_orn && !out->rtrg && !(lib && (fl.fam == FF_TRIPLET || step < L - 1))) {   /* a library fill's
                                                 * sticking is its ornament: ORN closes a rudiment with its roll alone */
        static const uint8_t FLAM[3] = { 2, 3, 4 }, ROLL[3] = { 4, 6, 8 }, RUFF[3] = { 3, 4, 6 },
                             DBL[3] = { 6, 8, 12 }, TRPL[3] = { 4, 6, 8 };
        unsigned w = rnd(seed, bar, 95, step) % 3u;
        if (zone == DR_SNARE && vel >= 100 && !lib && rnd(seed, bar, 90, step) % 200 < h_orn) {
            out->rtrg = 1; out->rtim = FLAM[w];      /* a flam */
        } else if ((flags & DRF_FILL) && step >= L - 2 && rnd(seed, bar, 91, step) % 150 < h_orn) {
            out->rtrg = (uint8_t)(2 + (h_orn > 127)); out->rtim = ROLL[w];   /* a roll closing the fill */
        } else if (lib) {
            ;                                    /* no ruff, no doubled hit in a library fill */
        } else if (h_orn > 96 && (step + 1) % (2 * beat) == beat && rnd(seed, bar, 92, step) % 250 < h_orn - 96) {
            out->rtrg = 2; out->rtim = RUFF[w];      /* a ruff into the backbeat */
        } else if (h_orn > 150 && (zone == DR_HATC || zone == DR_HATO || zone == DR_RIDE || zone == DR_PERC)
                   && rnd(seed, bar, 93, step) % 150 < h_orn - 150) {
            out->rtrg = (uint8_t)(1 + (h_orn > 220));   /* doubled, tripled hats and bells */
            out->rtim = h_orn > 220 ? TRPL[w] : DBL[w];
        }
    }

    out->play = 1;
    out->slice = (uint8_t)slice;
    out->vel = (uint8_t)vel;
    out->mtime = (int8_t)mt;
    out->zone = (uint8_t)zone;
    out->flags = (uint8_t)flags;
    s->prev_zone = (uint8_t)(zone + 1);
    s->prev_slice = (uint8_t)(slice + 1);
    if (zone == DR_CRASH || (zone == DR_COMBO && (k->combo[slice] & (1u << DR_CRASH))))
        s->since_crash = 1;
done:
    if (s->since_crash && s->since_crash < 255)
        s->since_crash++;
}
