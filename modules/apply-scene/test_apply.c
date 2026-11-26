/* APPLY SCENE engine tests (verify.py builds and runs them on the host). */
#include <stdio.h>
#include <string.h>
#include "apply.h"

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("  [FAIL] " __VA_ARGS__); printf("\n"); } } while (0)

/* The stock weight table: -258 * xf (MIDI.md appendix C), and the longs the
 * crossfader handlers build from it. */
static uint32_t weight_long(int xf) {
    int16_t t = (int16_t)(-258 * xf);
    uint16_t hi = (uint16_t)t, lo = (uint16_t)((0x8000 - t) & 0xffff);
    return (uint32_t)hi << 16 | lo;
}

static void mix(void) {
    int worst = 0;
    for (int xf = 0; xf < 128; xf++) {
        uint32_t w = weight_long(xf);
        int32_t wa = ap_weight_a(w), wb = ap_weight_b(w);
        CHECK(wa >= 0 && wb >= 0 && wa + wb == 0x8000, "weights at xf %d: %ld + %ld", xf, (long)wa, (long)wb);
        for (int a = 0; a < 128; a++)
            for (int b = 0; b < 128; b++) {
                /* the frame builder's value, in 1/256 steps: (a<<8)*wa + (b<<8)*wb, >> 15 */
                long exact = ((long)(a << 8) * wa + (long)(b << 8) * wb) >> 15;
                int v = ap_mix((uint8_t)a, (uint8_t)b, wa, wb);
                int err = (int)(v * 256 - exact);
                if (err < 0) err = -err;
                if (err > worst) worst = err;
            }
    }
    CHECK(worst <= 128, "the blend is the frame builder's to the nearest step (worst %d/256)", worst);
    uint32_t w0 = weight_long(0), w127 = weight_long(127);
    CHECK(ap_mix(10, 90, ap_weight_a(w0), ap_weight_b(w0)) == 90, "xf 0 is scene B");
    CHECK(ap_mix(10, 90, ap_weight_a(w127), ap_weight_b(w127)) == 10, "xf 127 is scene A");
    printf("  ap_mix: every value pair at every crossfader position within half a step (worst %d/256)\n", worst);
}

static void values(void) {
    uint8_t a[32], b[32], knob[30], out[30];
    memset(a, 0xff, 32);
    memset(b, 0xff, 32);
    for (int k = 0; k < 30; k++) knob[k] = (uint8_t)(k + 40);
    a[3] = 5; a[17] = 99; a[20] = 0;
    b[3] = 105; b[25] = 127;
    uint32_t w = weight_long(64);
    int32_t wa = ap_weight_a(w), wb = ap_weight_b(w);
    uint32_t skip = 1u << AP_XVOL;
    uint32_t m = ap_values(AP_A, a, b, knob, wa, wb, skip, out);
    CHECK(m == ((1u << 3) | (1u << 20)), "A: locked flats, XVOL skipped (mask %lx)", (unsigned long)m);
    CHECK(out[3] == 5 && out[20] == 0 && out[4] == knob[4], "A: the scene's values, the rest the knobs'");
    m = ap_values(AP_B, a, b, knob, wa, wb, skip, out);
    CHECK(m == ((1u << 3) | (1u << 25)) && out[3] == 105 && out[25] == 127, "B: its locks");
    m = ap_values(AP_AB, a, b, knob, wa, wb, skip, out);
    CHECK(m == ((1u << 3) | (1u << 20) | (1u << 25)), "AB: every flat locked in either (mask %lx)", (unsigned long)m);
    CHECK(out[3] == ap_mix(5, 105, wa, wb), "AB: both locked, the blend");
    CHECK(out[20] == ap_mix(0, knob[20], wa, wb), "AB: B unlocked, its side the knob");
    CHECK(out[25] == ap_mix(knob[25], 127, wa, wb), "AB: A unlocked, its side the knob");
    m = ap_values(AP_AB, 0, b, knob, wa, wb, skip, out);
    CHECK(m == ((1u << 3) | (1u << 25)) && out[3] == ap_mix(knob[3], 105, wa, wb), "AB, A absent: the knob's side");
    m = ap_values(AP_A, 0, b, knob, wa, wb, skip, out);
    CHECK(m == 0, "A absent: nothing");
    m = ap_values(AP_A, a, b, knob, wa, wb, skip | 0x3f, out);
    CHECK(m == (1u << 20), "skip: SRC left alone");
    printf("  ap_values: A, B, the blend, absent scenes, skipped flats\n");
}

static void scene(void) {
    uint8_t a[32], b[32], knob[30], keep[32], row[32];
    memset(a, 0xff, 32);
    memset(b, 0xff, 32);
    memset(keep, 0xff, 32);
    for (int k = 0; k < 30; k++) knob[k] = 64;
    keep[30] = 0x12; keep[31] = 0x34;
    a[12] = 10; a[17] = 100; b[14] = 107; b[17] = 20;
    uint32_t w = weight_long(64);
    int32_t wa = ap_weight_a(w), wb = ap_weight_b(w);
    unsigned n = ap_scene(a, b, knob, wa, wb, 0, keep, row);
    CHECK(n == 3, "the locked flats counted (%u)", n);
    CHECK(row[12] == ap_mix(10, 64, wa, wb) && row[14] == ap_mix(64, 107, wa, wb), "the blend, the knob on an unlocked side");
    CHECK(row[17] == ap_mix(100, 20, wa, wb), "XVOL locked in both: blended");
    CHECK(row[0] == 0xff && row[13] == 0xff, "no lock where neither scene locks");
    CHECK(row[30] == 0x12 && row[31] == 0x34, "SCENES P2's bytes kept");
    b[17] = 0xff;
    n = ap_scene(a, b, knob, wa, wb, 0, keep, row);
    CHECK(row[17] == 0xff && n == 2, "XVOL locked in one only: unlocked");
    printf("  ap_scene: the blend's scene, XVOL, SCENES P2's bytes\n");
}

static void commit(void) {
    uint8_t row[32];
    memset(row, 0xff, 32);
    row[12] = 10; row[14] = 107; row[17] = 90; row[30] = 0x12;
    unsigned n = ap_clear(row, (1u << 12) | (1u << 13) | (1u << 17));
    CHECK(n == 1 && row[12] == 0xff, "commit: the applied flat unlocked (%u)", n);
    CHECK(row[14] == 107, "commit: a flat not applied keeps its lock");
    CHECK(row[17] == 90 && row[30] == 0x12, "commit: XVOL and SCENES P2's bytes kept");
    printf("  ap_clear: applied flats unlocked, XVOL and the rest kept\n");
}

/* SCENES P2's frame pass (p2scenes.s morph6) for one slot: wA = xf * 258,
 * an unlocked side the knob, a select snapping at 0x4000. */
static int morph6(int a, int b, int knob, int32_t wa, int sel) {
    if (a == 0xff && b == 0xff) return knob;
    if (a == 0xff) a = knob;
    if (b == 0xff) b = knob;
    if (sel) return wa >= 0x4000 ? a : b;
    return (int)(((uint32_t)a * (uint32_t)wa + (uint32_t)b * (uint32_t)(0x8000 - wa) + 0x4000) >> 15);
}

static void cell(uint8_t *cells, unsigned i, unsigned t, int fx1, unsigned slot, uint8_t v) {
    cells[2 * i] = (uint8_t)(t << 4 | (fx1 ? 8 : 0) | slot);
    cells[2 * i + 1] = v;
}

static void page2(void) {
    uint8_t a[16], b[16], knob[12], out[12], v[12];
    memset(a, 0xff, 16);
    memset(b, 0xff, 16);
    for (int j = 0; j < 12; j++) knob[j] = (uint8_t)(50 + j);
    cell(a, 0, 1, 1, 2, 10);   /* T2 FX1 slot 2 = j 2 */
    cell(a, 3, 1, 0, 4, 90);   /* T2 FX2 slot 4 = j 10 */
    cell(a, 5, 2, 0, 4, 77);   /* T3: not T2's */
    cell(b, 1, 1, 0, 4, 20);
    cell(b, 2, 1, 0, 0, 1);    /* T2 FX2 slot 0 = j 6, a select below */
    uint32_t m = ap_p2_locks(a, 1, v);
    CHECK(m == ((1u << 2) | (1u << 10)) && v[2] == 10 && v[10] == 90 && v[0] == 0xff, "locks: T2's cells (mask %lx)", (unsigned long)m);
    m = ap_p2_values(AP_A, a, b, 1, knob, 0, 0, out);
    CHECK(m == ((1u << 2) | (1u << 10)) && out[2] == 10 && out[10] == 90 && out[0] == knob[0], "A: its locks");
    m = ap_p2_values(AP_B, a, b, 1, knob, 0x8000, 0, out);
    CHECK(m == ((1u << 6) | (1u << 10)) && out[10] == 20 && out[6] == 1, "B: its locks, the fader aside");
    int worst = 0;
    for (int xf = 0; xf < 128; xf++) {
        int32_t wa = ap_weight_a(weight_long(xf));
        m = ap_p2_values(AP_AB, a, b, 1, knob, wa, 1u << 6, out);
        CHECK(m == ((1u << 2) | (1u << 6) | (1u << 10)), "AB: every slot locked in either");
        int want[12];
        want[2] = morph6(10, 0xff, knob[2], wa, 0);
        want[6] = morph6(0xff, 1, knob[6], wa, 1);
        want[10] = morph6(90, 20, knob[10], wa, 0);
        for (int j = 2; j <= 10; j += 4)
            if (out[j] != want[j]) worst++;
    }
    CHECK(worst == 0, "AB: the frame pass's value at every fader position (%d differ)", worst);
    m = ap_p2_values(AP_AB, 0, b, 1, knob, 0x4000, 0, out);
    CHECK(m == ((1u << 6) | (1u << 10)) && out[10] == morph6(0xff, 20, knob[10], 0x4000, 0), "AB, A muted: the knob's side");
    m = ap_p2_values(AP_A, a, b, 5, knob, 0, 0, out);
    CHECK(m == 0, "a track with no cells: nothing");

    uint8_t c[16];
    memcpy(c, a, 16);
    unsigned n = ap_p2_clear(c, 1, 1u << 10);
    CHECK(n == 1 && c[6] == 0xff && c[0] == a[0] && c[10] == a[10], "clear: T2's j 10 only, T3's same slot kept");

    uint8_t e[16];
    memset(e, 0xff, 16);
    v[0] = 5; v[11] = 99;
    n = ap_p2_set(e, 4, (1u << 0) | (1u << 11), v);
    CHECK(n == 2 && e[0] == (4 << 4 | 8 | 0) && e[1] == 5 && e[2] == (4 << 4 | 5) && e[3] == 99, "set: two new cells");
    v[0] = 6;
    n = ap_p2_set(e, 4, 1u << 0, v);
    CHECK(n == 1 && e[1] == 6 && e[4] == 0xff, "set: an existing lock updated in its cell");
    for (unsigned t = 0; t < 3; t++) ap_p2_set(e, t, 0x3, v);
    n = ap_p2_set(e, 7, 1u << 3, v);
    CHECK(n == 0, "set: eight cells taken, the ninth lock dropped");
    printf("  page 2: SCENES P2's cells read, blended as its frame pass, cleared and set\n");
}

int main(void) {
    mix();
    values();
    scene();
    commit();
    page2();
    return fails ? 1 : 0;
}
