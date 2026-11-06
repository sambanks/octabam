/* Host tests for the CHORDS FACTORY engine (run by verify.py). No firmware. */
#include <stdio.h>
#include <string.h>
#include "chords.h"

static int failures, checks;
#define CHECK(cond, ...) do { ++checks; if (!(cond)) { ++failures; \
    printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

enum { IONIAN = 0xab5, AEOLIAN = 0x5ad };

static unsigned type_of(const char *name) {
    for (unsigned t = 0; t < ch_ntypes; t++)
        if (!strcmp(ch_types[t].name, name)) return t;
    printf("no type %s\n", name);
    return 0;
}

static ChVoicing V(unsigned n, unsigned a, unsigned b, unsigned c, unsigned d) {
    ChVoicing v = {(uint8_t)n, {(uint8_t)a, (uint8_t)b, (uint8_t)c, (uint8_t)d}};
    for (unsigned k = n; k < CH_VOICES; k++) v.note[k] = CH_NONE;
    return v;
}

static int same(const ChVoicing *a, const ChVoicing *b) {
    return a->n == b->n && !memcmp(a->note, b->note, a->n);
}

static void show(const char *what, const ChVoicing *v) {
    printf("    %s:", what);
    for (unsigned k = 0; k < v->n; k++) printf(" %u", v->note[k]);
    printf("\n");
}

static void test_build(void) {
    ChVoicing v, w;
    ch_build(0, type_of(""), 0, CH_CLOSE, 5, &v);
    w = V(3, 60, 64, 67, 0);
    CHECK(same(&v, &w), "C close: 60 64 67");
    ch_build(0, type_of(""), 1, CH_CLOSE, 5, &v);
    w = V(3, 64, 67, 72, 0);
    CHECK(same(&v, &w), "C first inversion: 64 67 72");
    ch_build(2, type_of("m7"), 0, CH_CLOSE, 5, &v);
    w = V(4, 62, 65, 69, 72);
    CHECK(same(&v, &w), "Dm7 close: 62 65 69 72");
    ch_build(2, type_of("m7"), 0, CH_DROP2, 5, &v);
    w = V(4, 57, 62, 65, 72);
    CHECK(same(&v, &w), "Dm7 drop 2: 57 62 65 72");
    ch_build(2, type_of("m7"), 0, CH_DROP3, 5, &v);
    w = V(4, 53, 62, 69, 72);
    CHECK(same(&v, &w), "Dm7 drop 3: 53 62 69 72");
    ch_build(2, type_of("m7"), 0, CH_OPEN, 5, &v);
    w = V(4, 50, 57, 65, 72);
    CHECK(same(&v, &w), "Dm7 open (drop 2 and 4): 50 57 65 72");
    ch_build(0, type_of(""), 0, CH_OPEN, 5, &v);
    w = V(3, 60, 67, 76, 0);
    CHECK(same(&v, &w), "C open triad: 60 67 76");
    ch_build(11, type_of("maj9"), 3, CH_OPEN, 10, &v);
    CHECK(v.n == 4 && v.note[3] <= 127, "the top of the range stays in 0..127: %u", v.note[3]);
    ch_build(0, type_of("5"), 0, CH_OPEN, 0, &v);
    CHECK(v.n == 2 && v.note[0] == 0 && v.note[1] == 7, "a power chord at the bottom: %u %u", v.note[0], v.note[1]);
    ch_build(0, 0, 9, CH_CLOSE, 5, &v);
    CHECK(v.note[0] == 67, "an inversion past the chord's notes clamps to the last: %u", v.note[0]);
}

/* Every type at every root, every inversion and spread: sorted, distinct,
 * the type's pitch classes, named back (root position: exactly). */
static void test_all_types(void) {
    for (unsigned t = 0; t < ch_ntypes; t++)
        for (unsigned r = 0; r < 12; r++)
            for (unsigned inv = 0; inv < ch_types[t].n; inv++)
                for (unsigned sp = 0; sp < CH_SPREADS; sp++) {
                    ChVoicing v;
                    ch_build(r, t, inv, sp, 5, &v);
                    unsigned mask = 0, want = 0;
                    for (unsigned k = 0; k < v.n; k++) {
                        mask |= 1u << (v.note[k] % 12);
                        CHECK(!k || v.note[k] > v.note[k - 1], "type %u root %u: ascending", t, r);
                    }
                    for (unsigned k = 0; k < ch_types[t].n; k++) want |= 1u << ((r + ch_types[t].pc[k]) % 12);
                    CHECK(mask == want && v.n == ch_types[t].n, "type %s root %u inv %u spread %u: its notes",
                          ch_types[t].name, r, inv, sp);
                    unsigned rr, tt;
                    CHECK(ch_identify(&v, &rr, &tt), "type %s root %u: identified", ch_types[t].name, r);
                    if (inv == 0 && sp == CH_CLOSE)
                        CHECK(rr == r && tt == t, "type %s root %u: named back as %u %s", ch_types[t].name, r, rr,
                              ch_types[tt].name);
                }
}

static void test_names(void) {
    char s[CH_NAME];
    ChVoicing v;
    ch_build(2, type_of("m7"), 0, CH_CLOSE, 5, &v);
    ch_name(&v, s);
    CHECK(!strcmp(s, "Dm7"), "Dm7: %s", s);
    ch_build(6, type_of("madd9"), 2, CH_OPEN, 5, &v);
    ch_name(&v, s);
    CHECK(!strcmp(s, "F#madd9"), "the longest name: %s", s);
    ch_build(10, type_of("m7b5"), 0, CH_DROP2, 4, &v);
    ch_name(&v, s);
    CHECK(!strcmp(s, "Bbm7b5"), "Bbm7b5: %s", s);
    v = V(3, 60, 61, 62, 0);
    ch_name(&v, s);
    CHECK(!strcmp(s, "?"), "a cluster: %s", s);
    v.n = 0;
    ch_name(&v, s);
    CHECK(!strcmp(s, "-"), "empty: %s", s);
    v = V(4, 57, 60, 64, 67);              /* A C E G: Am7 over A, C6 when C is the bass */
    ch_name(&v, s);
    CHECK(!strcmp(s, "Am7"), "the bass names it: %s", s);
    v = V(4, 60, 64, 67, 69);
    ch_name(&v, s);
    CHECK(!strcmp(s, "C6"), "the bass names it: %s", s);
}

static void lead_case(const char *what, ChVoicing prev, unsigned root, const char *type, ChVoicing want) {
    ChVoicing out[CH_LEAD_MAX];
    unsigned n = ch_lead(&prev, root, type_of(type), 0, out, CH_LEAD_MAX);
    CHECK(n > 0 && same(&out[0], &want), "%s: the smoothest", what);
    if (n && !same(&out[0], &want)) { show("got", &out[0]); show("want", &want); }
}

static void test_lead_cases(void) {
    lead_case("C -> F", V(3, 60, 64, 67, 0), 5, "", V(3, 60, 65, 69, 0));
    lead_case("C -> Am", V(3, 60, 64, 67, 0), 9, "m", V(3, 60, 64, 69, 0));
    lead_case("C -> G", V(3, 60, 64, 67, 0), 7, "", V(3, 59, 62, 67, 0));
    lead_case("Dm7 -> G7", V(4, 62, 65, 69, 72), 7, "7", V(4, 62, 65, 67, 71));
    lead_case("G7 -> Cmaj7", V(4, 62, 65, 67, 71), 0, "maj7", V(4, 60, 64, 67, 71));
    lead_case("Cmaj7 -> Am7", V(4, 60, 64, 67, 71), 9, "m7", V(4, 60, 64, 67, 69));
}

/* Properties of every answer, for every pair of types and roots from a
 * spread of starting voicings. */
static void test_lead_properties(void) {
    unsigned total = 0;
    for (unsigned t0 = 0; t0 < ch_ntypes; t0++)
        for (unsigned sp = 0; sp < CH_SPREADS; sp += 3) {
            ChVoicing prev;
            ch_build(0, t0, 0, sp, 5, &prev);
            for (unsigned t = 0; t < ch_ntypes; t++)
                for (unsigned r = 0; r < 12; r++)
                    for (unsigned flags = 0; flags <= CH_BASS_ROOT; flags++) {
                        ChVoicing out[CH_LEAD_MAX];
                        unsigned n = ch_lead(&prev, r, t, flags, out, CH_LEAD_MAX);
                        CHECK(n > 0, "%s -> %u%s: an answer", ch_types[t0].name, r, ch_types[t].name);
                        unsigned want = 0, voices = prev.n > ch_types[t].n ? prev.n : ch_types[t].n;
                        for (unsigned k = 0; k < ch_types[t].n; k++) want |= 1u << ((r + ch_types[t].pc[k]) % 12);
                        unsigned last = 0;
                        for (unsigned i = 0; i < n; i++) {
                            const ChVoicing *v = &out[i];
                            unsigned mask = 0, ok = v->n == voices;
                            for (unsigned k = 0; k < v->n; k++) {
                                mask |= 1u << (v->note[k] % 12);
                                ok &= !k || v->note[k] > v->note[k - 1];
                                ok &= v->note[k] + 12 >= prev.note[0] && v->note[k] <= prev.note[prev.n - 1] + 12;
                            }
                            for (unsigned k = v->n; k < CH_VOICES; k++) ok &= v->note[k] == CH_NONE;
                            CHECK(ok && mask == want, "%s -> %u%s #%u: every pitch class, ascending, in the window",
                                  ch_types[t0].name, r, ch_types[t].name, i);
                            if (flags & CH_BASS_ROOT) CHECK(v->note[0] % 12 == r, "the root in the bass");
                            for (unsigned j = 0; j < i; j++) CHECK(!same(v, &out[j]), "no answer twice");
                            unsigned c = ch_cost(&prev, v);
                            CHECK(!i || c + 30 >= last, "ranked by movement");
                            last = c;
                        }
                        total += n;
                    }
        }
    CHECK(total > 10000, "answers: %u", total);
}

/* The first answer is at least as smooth as any built voicing of the chord
 * in the window (the search sees every one of them). */
static void test_lead_best(void) {
    for (unsigned t = 0; t < ch_ntypes; t++)
        for (unsigned r = 0; r < 12; r++) {
            ChVoicing prev = V(4, 57, 62, 65, 72), out[1];
            if (!ch_lead(&prev, r, t, 0, out, 1)) { CHECK(0, "an answer"); continue; }
            unsigned best = ch_cost(&prev, &out[0]);
            if (out[0].n != ch_types[t].n) continue;    /* a doubled voicing: no built peer */
            for (unsigned inv = 0; inv < ch_types[t].n; inv++)
                for (unsigned sp = 0; sp < CH_SPREADS; sp++)
                    for (unsigned oct = 3; oct <= 6; oct++) {
                        ChVoicing b;
                        ch_build(r, t, inv, sp, oct, &b);
                        if (b.note[0] + 12 < prev.note[0] || b.note[b.n - 1] > prev.note[prev.n - 1] + 12) continue;
                        int span = b.note[b.n - 1] - b.note[0];
                        unsigned c = ch_cost(&prev, &b) + (span > 24 ? (unsigned)(span - 24) : 0);
                        CHECK(best <= c, "%u%s: the answer moves %u, a built voicing %u", r, ch_types[t].name, best, c);
                    }
        }
}

static void test_doubling(void) {
    ChVoicing prev = V(4, 62, 65, 69, 72), out[CH_LEAD_MAX];      /* Dm7 -> C: four voices, the root or fifth doubled */
    unsigned n = ch_lead(&prev, 0, type_of(""), 0, out, CH_LEAD_MAX);
    CHECK(n && out[0].n == 4, "a triad after four voices keeps four: %u", out[0].n);
    unsigned thirds = 0;
    for (unsigned k = 0; k < out[0].n; k++) thirds += out[0].note[k] % 12 == 4;
    CHECK(thirds == 1, "the third not doubled");
    ChVoicing tri = V(3, 60, 64, 67, 0);
    n = ch_lead(&tri, 7, type_of("7"), 0, out, CH_LEAD_MAX);
    CHECK(n && out[0].n == 4, "a seventh after a triad takes four: %u", out[0].n);
    ChVoicing empty = V(0, 0, 0, 0, 0);
    CHECK(!ch_lead(&empty, 0, 0, 0, out, CH_LEAD_MAX), "nothing before: no answer (ch_build)");
}

static void test_diatonic(void) {
    static const struct { int32_t scale; unsigned degree, sevenths; const char *want; } cases[] = {
        {IONIAN << 4 | 0, 0, 0, "C"}, {IONIAN << 4 | 0, 1, 0, "Dm"}, {IONIAN << 4 | 0, 4, 1, "G7"},
        {IONIAN << 4 | 0, 6, 0, "Bdim"}, {IONIAN << 4 | 0, 6, 1, "Bm7b5"}, {IONIAN << 4 | 0, 3, 1, "Fmaj7"},
        {AEOLIAN << 4 | 9, 0, 0, "Am"}, {AEOLIAN << 4 | 9, 2, 1, "Cmaj7"}, {IONIAN << 4 | 2, 4, 1, "A7"},
    };
    for (unsigned i = 0; i < sizeof cases / sizeof cases[0]; i++) {
        unsigned r, t;
        char s[CH_NAME] = "";
        if (ch_diatonic(cases[i].scale, cases[i].degree, cases[i].sevenths, &r, &t)) {
            ChVoicing v;
            ch_build(r, t, 0, CH_CLOSE, 5, &v);
            ch_name(&v, s);
        }
        CHECK(!strcmp(s, cases[i].want), "degree %u: %s, want %s", cases[i].degree, s, cases[i].want);
    }
    unsigned r, t;
    CHECK(!ch_diatonic(-1, 0, 0, &r, &t), "no scale, no diatonic chord");
}

static void test_keyboard(void) {
    ChVoicing v = V(0, 0, 0, 0, 0);
    CHECK(ch_toggle(&v, 67) && ch_toggle(&v, 60) && ch_toggle(&v, 64), "three keys in");
    ChVoicing w = V(3, 60, 64, 67, 0);
    CHECK(same(&v, &w), "kept sorted");
    CHECK(ch_toggle(&v, 64) && v.n == 2 && v.note[1] == 67 && v.note[2] == CH_NONE, "a key again: out");
    CHECK(ch_toggle(&v, 70) && ch_toggle(&v, 72) && !ch_toggle(&v, 74), "four voices at most");
    CHECK(ch_move_voice(&v, 1, -20) && v.note[1] == 61, "a voice stops above the one below: %u", v.note[1]);
    CHECK(ch_move_voice(&v, 1, 20) && v.note[1] == 69, "and below the one above: %u", v.note[1]);
    CHECK(!ch_move_voice(&v, 1, 1), "no unison");
    CHECK(ch_move_voice(&v, 3, 100) && v.note[3] == 127, "the top stops at 127");
    CHECK(!ch_move_voice(&v, 4, 1), "no fifth voice");
}

static void test_slots(void) {
    ChSlot a, b;
    ch_slot_clear(&a);
    CHECK(!a.v.n && a.oct == 4 && a.mode == CH_MODE_BUILT && a.degree == CH_NONE, "a cleared slot is empty");
    a.root = 2;
    a.type = type_of("m7");
    a.spread = CH_DROP2;
    a.oct = 5;
    CHECK(!ch_slot_apply(&a, NULL), "BUILT: no answers");
    ChVoicing w = V(4, 57, 62, 65, 72);
    CHECK(same(&a.v, &w), "BUILT: Dm7 drop 2");
    ch_slot_clear(&b);
    b.root = 7;
    b.type = type_of("7");
    b.mode = CH_MODE_LEAD;
    unsigned n = ch_slot_apply(&b, &a.v);
    ChVoicing best[CH_LEAD_MAX];
    ch_lead(&a.v, 7, b.type, 0, best, CH_LEAD_MAX);
    CHECK(n == CH_LEAD_MAX && same(&b.v, &best[0]), "LEAD: the smoothest after the slot before (%u answers)", n);
    b.lead = 3;
    ch_slot_apply(&b, &a.v);
    CHECK(same(&b.v, &best[3]), "LEAD 4: the fourth");
    b.lead = 200;
    ch_slot_apply(&b, &a.v);
    CHECK(b.lead == n - 1, "the lead index clamps: %u", b.lead);
    b.flags = CH_BASS_ROOT;
    ch_slot_apply(&b, &a.v);
    CHECK(b.v.note[0] % 12 == 7, "BASS: G in the bass");
    ChVoicing none = V(0, 0, 0, 0, 0);
    b.lead = 0;
    CHECK(!ch_slot_apply(&b, &none) && b.mode == CH_MODE_BUILT && b.v.n == 4, "LEAD with nothing before: built");
    b.mode = CH_MODE_EDIT;
    b.v = V(3, 50, 51, 52, 0);
    ch_slot_apply(&b, &a.v);
    CHECK(b.v.n == 3 && b.v.note[0] == 50, "EDIT keeps its notes");
}

static void test_file(void) {
    static ChSlot bank[CH_BANKS][CH_SLOTS], back[CH_BANKS][CH_SLOTS];
    static uint8_t buf[CH_FILE_B];
    CHECK(CH_FILE_B == 3584, "chords.work's payload: %d", (int)CH_FILE_B);
    for (unsigned b = 0; b < CH_BANKS; b++)
        for (unsigned i = 0; i < CH_SLOTS; i++) {
            ChSlot *s = &bank[b][i];
            ch_slot_clear(s);
            if (!((b + i) % 3)) continue;
            s->root = (uint8_t)(i % 12);
            s->type = (uint8_t)((b * 7 + i) % ch_ntypes);
            s->inv = (uint8_t)(i % 3);
            s->spread = (uint8_t)(b % CH_SPREADS);
            s->oct = (uint8_t)(3 + b % 4);
            s->lead = (uint8_t)(i % CH_LEAD_MAX);
            s->mode = (uint8_t)(i % CH_MODES);
            s->degree = (uint8_t)(i % 2 ? i % 7 : CH_NONE);
            s->flags = (uint8_t)(b & 1);
            ch_build(s->root, s->type, s->inv, s->spread, s->oct, &s->v);
        }
    ch_pack(bank, buf);
    memset(back, 0xa5, sizeof back);
    ch_unpack(buf, back);
    unsigned ok = 1;
    for (unsigned b = 0; b < CH_BANKS; b++)
        for (unsigned i = 0; i < CH_SLOTS; i++) ok &= !memcmp(&bank[b][i], &back[b][i], sizeof(ChSlot));
    CHECK(ok, "every slot of every bank back");
    uint8_t *p = buf + 1 + CH_VOICES;
    buf[0] = 9;                                 /* n past 4 */
    buf[CH_SLOT_B] = 2; buf[CH_SLOT_B + 1] = 70; buf[CH_SLOT_B + 2] = 60;    /* descending */
    buf[2 * CH_SLOT_B] = 1; buf[2 * CH_SLOT_B + 1] = 200;                    /* past 127 */
    p[3 * CH_SLOT_B + 1] = (uint8_t)ch_ntypes;                               /* no such type */
    p[4 * CH_SLOT_B + 6] = CH_MODES;                                         /* no such mode */
    ch_unpack(buf, back);
    for (unsigned i = 0; i < 5; i++)
        CHECK(!back[0][i].v.n && back[0][i].v.note[0] == CH_NONE && back[0][i].oct == 4, "bad slot %u is cleared", i);
}

int main(void) {
    test_build();
    test_all_types();
    test_names();
    test_lead_cases();
    test_lead_properties();
    test_lead_best();
    test_doubling();
    test_diatonic();
    test_keyboard();
    test_slots();
    test_file();
    printf("  CHORDS FACTORY engine: %d checks, %d failed\n", checks, failures);
    return failures != 0;
}
