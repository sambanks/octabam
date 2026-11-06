/* CHORDS FACTORY engine (chords.h). */
#include "chords.h"

const ChType ch_types[] = {
    {"",      3, {0, 4, 7}},
    {"m",     3, {0, 3, 7}},
    {"7",     4, {0, 4, 7, 10}},
    {"maj7",  4, {0, 4, 7, 11}},
    {"m7",    4, {0, 3, 7, 10}},
    {"m7b5",  4, {0, 3, 6, 10}},
    {"dim",   3, {0, 3, 6}},
    {"dim7",  4, {0, 3, 6, 9}},
    {"aug",   3, {0, 4, 8}},
    {"sus2",  3, {0, 2, 7}},
    {"sus4",  3, {0, 5, 7}},
    {"7sus4", 4, {0, 5, 7, 10}},
    {"6",     4, {0, 4, 7, 9}},
    {"m6",    4, {0, 3, 7, 9}},
    {"add9",  4, {0, 2, 4, 7}},
    {"madd9", 4, {0, 2, 3, 7}},
    {"mmaj7", 4, {0, 3, 7, 11}},
    {"9",     4, {0, 2, 4, 10}},
    {"m9",    4, {0, 2, 3, 10}},
    {"maj9",  4, {0, 2, 4, 11}},
    {"5",     2, {0, 7}},
};
const unsigned ch_ntypes = sizeof ch_types / sizeof ch_types[0];

const char *const ch_spread_names[CH_SPREADS] = {"CLOSE", "DROP2", "DROP3", "OPEN", "BASS", "TENTH", "WIDE"};

static const char *const roots[12] = {"C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"};

static void sort(uint8_t *a, unsigned n) {
    for (unsigned i = 1; i < n; i++)
        for (unsigned j = i; j && a[j - 1] > a[j]; j--) {
            uint8_t t = a[j];
            a[j] = a[j - 1];
            a[j - 1] = t;
        }
}

static unsigned type_mask(unsigned root, unsigned type) {
    unsigned m = 0;
    for (unsigned k = 0; k < ch_types[type].n; k++) m |= 1u << ((root + ch_types[type].pc[k]) % 12);
    return m;
}

void ch_build(unsigned root, unsigned type, unsigned inversion, unsigned spread, unsigned octave, ChVoicing *out) {
    const ChType *t = &ch_types[type < ch_ntypes ? type : 0];
    unsigned n = t->n, inv = inversion < n ? inversion : n - 1;
    root %= 12;
    int v[CH_VOICES];
    v[0] = (int)(octave * 12 + (root + t->pc[inv]) % 12);
    for (unsigned k = 1; k < n; k++) {
        int pc = (int)((root + t->pc[(inv + k) % n]) % 12);
        int x = v[k - 1] - v[k - 1] % 12 + pc;
        while (x <= v[k - 1]) x += 12;
        v[k] = x;
    }
    if (spread == CH_DROP2 && n >= 3) v[n - 2] -= 12;
    if (spread == CH_DROP3 && n >= 4) v[n - 3] -= 12;
    if ((spread == CH_OPEN || spread == CH_BASS || (spread == CH_DROP3 && n < 4)) && n >= 3) {
        if (n == 4) { v[2] -= 12; v[0] -= 12; }  /* drop 2 and 4 */
        else v[1] += 12;                            /* the open triad: its middle note up */
    }
    if (spread == CH_BASS) {                        /* OPEN, its lowest note an octave down */
        unsigned b = 0;
        for (unsigned k = 1; k < n; k++)
            if (v[k] < v[b]) b = k;
        v[b] -= 12;
    }
    if (spread == CH_TENTH)                         /* the bass, the rest an octave up: root and 10th */
        for (unsigned k = 1; k < n; k++) v[k] += 12;
    if (spread == CH_WIDE)                          /* voice k, k octaves up */
        for (unsigned k = 1; k < n; k++) v[k] += 12 * (int)k;
    int lo = v[0], hi = v[0];
    for (unsigned k = 1; k < n; k++) {
        if (v[k] < lo) lo = v[k];
        if (v[k] > hi) hi = v[k];
    }
    int shift = 0;
    while (lo + shift < 0) shift += 12;
    while (hi + shift > 127) shift -= 12;
    out->n = (uint8_t)n;
    for (unsigned k = 0; k < CH_VOICES; k++) out->note[k] = k < n ? (uint8_t)(v[k] + shift) : CH_NONE;
    sort(out->note, n);
}

static int absd(int a) { return a < 0 ? -a : a; }

/* The voices' total move: prev and next matched in order, every voice of
 * each matched at least once (a dynamic time warp over the sorted lists). */
unsigned ch_cost(const ChVoicing *prev, const ChVoicing *next) {
    unsigned m = prev->n, n = next->n;
    if (!m || !n) return 0;
    unsigned d[CH_VOICES][CH_VOICES];
    for (unsigned i = 0; i < m; i++)
        for (unsigned j = 0; j < n; j++) {
            unsigned c = (unsigned)absd((int)prev->note[i] - (int)next->note[j]), best;
            if (!i && !j) best = 0;
            else if (!i) best = d[i][j - 1];
            else if (!j) best = d[i - 1][j];
            else {
                best = d[i - 1][j - 1];
                if (d[i - 1][j] < best) best = d[i - 1][j];
                if (d[i][j - 1] < best) best = d[i][j - 1];
            }
            d[i][j] = best + c;
        }
    return d[m - 1][n - 1];
}

static unsigned common(const ChVoicing *a, const ChVoicing *b) {
    unsigned c = 0;
    for (unsigned i = 0; i < a->n; i++)
        for (unsigned j = 0; j < b->n; j++) c += a->note[i] == b->note[j];
    return c;
}

/* The search: candidate notes in the window, every ascending choice of
 * `voices` of them that covers the chord's pitch classes, ranked. */
typedef struct {
    const ChVoicing *prev;
    unsigned root, type, flags, voices, need, max, count;
    uint8_t cand[64];
    unsigned ncand;
    ChVoicing *out;
    unsigned cost[CH_LEAD_MAX], keep[CH_LEAD_MAX];
} Search;

static unsigned penalty(const Search *s, const ChVoicing *v) {
    unsigned p = 0, seen = 0;
    for (unsigned k = 0; k < v->n; k++) {
        unsigned iv = (v->note[k] + 12 - s->root) % 12, bit = 1u << iv;
        if (seen & bit && iv != 0 && iv != 7) p += 2;      /* a doubled third (or seventh) */
        seen |= bit;
    }
    int span = (int)v->note[v->n - 1] - (int)v->note[0];
    if (span > 24) p += (unsigned)(span - 24);
    return p;
}

static void consider(Search *s, const ChVoicing *v) {
    if (s->flags & CH_BASS_ROOT && v->note[0] % 12 != s->root) return;
    unsigned cost = ch_cost(s->prev, v) + penalty(s, v), keep = common(s->prev, v);
    unsigned at = s->count;
    while (at && (s->cost[at - 1] > cost || (s->cost[at - 1] == cost && s->keep[at - 1] < keep))) at--;
    if (at >= s->max) return;
    unsigned last = s->count < s->max ? s->count : s->max - 1;
    for (unsigned k = last; k > at; k--) {
        s->out[k] = s->out[k - 1];
        s->cost[k] = s->cost[k - 1];
        s->keep[k] = s->keep[k - 1];
    }
    s->out[at] = *v;
    s->cost[at] = cost;
    s->keep[at] = keep;
    if (s->count < s->max) s->count++;
}

static void choose(Search *s, ChVoicing *v, unsigned from, unsigned have) {
    if (v->n == s->voices) {
        if (have == s->need) consider(s, v);
        return;
    }
    for (unsigned c = from; c + (s->voices - v->n) <= s->ncand; c++) {
        v->note[v->n++] = s->cand[c];
        choose(s, v, c + 1, have | 1u << (s->cand[c] % 12));
        v->n--;
    }
}

unsigned ch_lead(const ChVoicing *prev, unsigned root, unsigned type, unsigned flags,
                 ChVoicing out[], unsigned max) {
    if (!prev->n || type >= ch_ntypes || !max) return 0;
    Search s;
    s.prev = prev;
    s.root = root % 12;
    s.type = type;
    s.flags = flags;
    s.need = type_mask(s.root, type);
    s.max = max < CH_LEAD_MAX ? max : CH_LEAD_MAX;
    s.count = 0;
    s.out = out;
    unsigned tn = ch_types[type].n;
    s.voices = prev->n > tn ? prev->n : tn;
    if (s.voices > CH_VOICES) s.voices = CH_VOICES;
    int lo = (int)prev->note[0] - 12, hi = (int)prev->note[prev->n - 1] + 12;
    if (lo < 0) lo = 0;
    if (hi > 127) hi = 127;
    s.ncand = 0;
    for (int x = lo; x <= hi && s.ncand < sizeof s.cand; x++)
        if (s.need >> (x % 12) & 1) s.cand[s.ncand++] = (uint8_t)x;
    ChVoicing v;
    v.n = 0;
    for (unsigned k = 0; k < CH_VOICES; k++) v.note[k] = CH_NONE;
    choose(&s, &v, 0, 0);
    for (unsigned k = 0; k < s.count; k++)
        for (unsigned j = out[k].n; j < CH_VOICES; j++) out[k].note[j] = CH_NONE;
    return s.count;
}

unsigned ch_identify(const ChVoicing *v, unsigned *root, unsigned *type) {
    if (!v->n) return 0;
    unsigned mask = 0;
    for (unsigned k = 0; k < v->n; k++) mask |= 1u << (v->note[k] % 12);
    unsigned bass = v->note[0] % 12;
    for (unsigned pass = 0; pass < 2; pass++)       /* the bass as root first, then any */
        for (unsigned t = 0; t < ch_ntypes; t++)
            for (unsigned r = 0; r < 12; r++) {
                if ((pass == 0) != (r == bass) || !(mask >> r & 1)) continue;
                if (type_mask(r, t) == mask) {
                    *root = r;
                    *type = t;
                    return 1;
                }
            }
    return 0;
}

void ch_name(const ChVoicing *v, char out[CH_NAME]) {
    unsigned root, type, k = 0;
    if (!v->n) { out[0] = '-'; out[1] = 0; return; }
    if (!ch_identify(v, &root, &type)) { out[0] = '?'; out[1] = 0; return; }
    for (const char *p = roots[root]; *p; p++) out[k++] = *p;
    for (const char *p = ch_types[type].name; *p && k < CH_NAME - 1; p++) out[k++] = *p;
    out[k] = 0;
}

unsigned ch_diatonic(int32_t scale, unsigned degree, unsigned sevenths, unsigned *root, unsigned *type) {
    if (scale < 0) return 0;
    unsigned tonic = (unsigned)scale & 15, mask = (unsigned)scale >> 4, steps[12], n = 0;
    for (unsigned d = 0; d < 12; d++)
        if (mask >> d & 1) steps[n++] = (tonic + d) % 12;
    if (n < 5) return 0;
    unsigned r = steps[degree % n], want = 0;
    for (unsigned j = 0; j < (sevenths ? 4u : 3u); j++) want |= 1u << steps[(degree + 2 * j) % n];
    for (unsigned t = 0; t < ch_ntypes; t++)
        if (type_mask(r, t) == want) {
            *root = r;
            *type = t;
            return 1;
        }
    return 0;
}

unsigned ch_toggle(ChVoicing *v, unsigned note) {
    for (unsigned k = 0; k < v->n; k++)
        if (v->note[k] == note) {
            for (unsigned j = k + 1; j < v->n; j++) v->note[j - 1] = v->note[j];
            v->note[--v->n] = CH_NONE;
            return 1;
        }
    if (v->n >= CH_VOICES || note > 127) return 0;
    v->note[v->n++] = (uint8_t)note;
    sort(v->note, v->n);
    return 1;
}

unsigned ch_move_voice(ChVoicing *v, unsigned i, int delta) {
    if (i >= v->n) return 0;
    int lo = i ? v->note[i - 1] + 1 : 0, hi = i + 1 < v->n ? v->note[i + 1] - 1 : 127;
    int x = (int)v->note[i] + delta;
    if (x < lo) x = lo;
    if (x > hi) x = hi;
    if (x == v->note[i]) return 0;
    v->note[i] = (uint8_t)x;
    return 1;
}

void ch_slot_clear(ChSlot *s) {
    s->v.n = 0;
    for (unsigned k = 0; k < CH_VOICES; k++) s->v.note[k] = CH_NONE;
    s->root = 0;
    s->type = 0;
    s->inv = 0;
    s->spread = CH_CLOSE;
    s->oct = 4;
    s->lead = 0;
    s->mode = CH_MODE_BUILT;
    s->degree = CH_NONE;
    s->flags = 0;
}

unsigned ch_slot_apply(ChSlot *s, const ChVoicing *prev) {
    if (s->mode == CH_MODE_EDIT) return 0;
    if (s->mode == CH_MODE_LEAD && prev && prev->n) {
        ChVoicing out[CH_LEAD_MAX];
        unsigned n = ch_lead(prev, s->root, s->type, s->flags & CH_BASS_ROOT, out, CH_LEAD_MAX);
        if (n) {
            if (s->lead >= n) s->lead = (uint8_t)(n - 1);
            s->v = out[s->lead];
            return n;
        }
    }
    s->mode = CH_MODE_BUILT;
    ch_build(s->root, s->type, s->inv, s->spread, s->oct, &s->v);
    return 0;
}

void ch_pack(const ChSlot bank[CH_BANKS][CH_SLOTS], uint8_t out[CH_FILE_B]) {
    for (unsigned b = 0; b < CH_BANKS; b++)
        for (unsigned i = 0; i < CH_SLOTS; i++) {
            const ChSlot *s = &bank[b][i];
            uint8_t *o = out + (b * CH_SLOTS + i) * CH_SLOT_B;
            o[0] = s->v.n;
            for (unsigned k = 0; k < CH_VOICES; k++) o[1 + k] = s->v.note[k];
            o += 1 + CH_VOICES;
            o[0] = s->root; o[1] = s->type; o[2] = s->inv; o[3] = s->spread; o[4] = s->oct;
            o[5] = s->lead; o[6] = s->mode; o[7] = s->degree; o[8] = s->flags;
        }
}

void ch_unpack(const uint8_t in[CH_FILE_B], ChSlot bank[CH_BANKS][CH_SLOTS]) {
    for (unsigned b = 0; b < CH_BANKS; b++)
        for (unsigned i = 0; i < CH_SLOTS; i++) {
            const uint8_t *r = in + (b * CH_SLOTS + i) * CH_SLOT_B, *p = r + 1 + CH_VOICES;
            ChSlot *s = &bank[b][i];
            unsigned ok = r[0] <= CH_VOICES && p[0] < 12 && p[1] < ch_ntypes && p[2] < CH_VOICES
                       && p[3] < CH_SPREADS && p[4] <= CH_OCT_MAX && p[5] < CH_LEAD_MAX && p[6] < CH_MODES
                       && (p[7] < 7 || p[7] == CH_NONE) && p[8] <= CH_BASS_ROOT;
            for (unsigned k = 0; ok && k < r[0]; k++)
                ok = r[1 + k] <= 127 && (!k || r[1 + k] > r[k]);
            ch_slot_clear(s);
            if (!ok) continue;
            s->v.n = r[0];
            for (unsigned k = 0; k < s->v.n; k++) s->v.note[k] = r[1 + k];
            s->root = p[0]; s->type = p[1]; s->inv = p[2]; s->spread = p[3]; s->oct = p[4];
            s->lead = p[5]; s->mode = p[6]; s->degree = p[7]; s->flags = p[8];
        }
}
