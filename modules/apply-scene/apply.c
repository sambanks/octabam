/* APPLY SCENE: the engine (apply.h). */
#include "apply.h"

uint8_t ap_mix(uint8_t va, uint8_t vb, int32_t wa, int32_t wb) {
    int32_t v = ((int32_t)va * wa + (int32_t)vb * wb + 0x4000) >> 15;
    if (v < 0) v = 0;
    if (v > 127) v = 127;
    return (uint8_t)v;
}

uint32_t ap_values(unsigned which, const uint8_t *a, const uint8_t *b, const uint8_t *knob,
                   int32_t wa, int32_t wb, uint32_t skip, uint8_t *out) {
    uint32_t mask = 0;
    if (!(which & AP_A)) a = 0;
    if (!(which & AP_B)) b = 0;
    for (unsigned k = 0; k < AP_FLATS; k++) {
        out[k] = knob[k];
        if (skip & (1u << k)) continue;
        int la = a && ap_locked(a[k]), lb = b && ap_locked(b[k]);
        if (!la && !lb) continue;
        if (which == AP_AB)
            out[k] = ap_mix(la ? a[k] : knob[k], lb ? b[k] : knob[k], wa, wb);
        else
            out[k] = la ? a[k] : b[k];
        mask |= 1u << k;
    }
    return mask;
}

unsigned ap_scene(const uint8_t *a, const uint8_t *b, const uint8_t *knob, int32_t wa, int32_t wb,
                  uint32_t skip, const uint8_t *keep, uint8_t *scene) {
    uint8_t mixed[AP_FLATS];
    uint32_t mask = ap_values(AP_AB, a, b, knob, wa, wb, skip | (1u << AP_XVOL), mixed);
    unsigned n = 0;
    for (unsigned k = 0; k < AP_FLATS; k++) {
        scene[k] = 0xff;
        if (mask & (1u << k)) {
            scene[k] = mixed[k];
            n++;
        }
    }
    if (!(skip & (1u << AP_XVOL)) && a && b && ap_locked(a[AP_XVOL]) && ap_locked(b[AP_XVOL])) {
        scene[AP_XVOL] = ap_mix(a[AP_XVOL], b[AP_XVOL], wa, wb);
        n++;
    }
    scene[30] = keep[30];
    scene[31] = keep[31];
    return n;
}

unsigned ap_clear(uint8_t *scene, uint32_t mask) {
    unsigned n = 0;
    mask &= ~(1u << AP_XVOL);
    for (unsigned k = 0; k < AP_FLATS; k++)
        if ((mask & (1u << k)) && ap_locked(scene[k])) {
            scene[k] = 0xff;
            n++;
        }
    return n;
}

/* A cell's key for track t's page-2 value j, and back. */
static unsigned p2_key(unsigned t, unsigned j) { return t << 4 | (j < 6 ? 8u : 0u) | (j % 6); }

static int p2_index(unsigned key, unsigned t) {
    if (key & 0x80 || (key >> 4) != t || (key & 7) > 5) return -1;
    return (int)((key & 7) + (key & 8 ? 0 : 6));
}

uint32_t ap_p2_locks(const uint8_t *cells, unsigned t, uint8_t *vals) {
    uint32_t mask = 0;
    for (unsigned j = 0; j < AP_P2; j++) vals[j] = 0xff;
    if (!cells) return 0;
    for (unsigned i = 0; i < AP_CELLS; i++) {
        int j = p2_index(cells[2 * i], t);
        if (j < 0) continue;
        vals[j] = cells[2 * i + 1];
        mask |= 1u << j;
    }
    return mask;
}

uint32_t ap_p2_values(unsigned which, const uint8_t *a, const uint8_t *b, unsigned t, const uint8_t *knob,
                      int32_t wa, uint32_t selects, uint8_t *out) {
    uint8_t va[AP_P2], vb[AP_P2];
    uint32_t ma = (which & AP_A) ? ap_p2_locks(a, t, va) : 0, mb = (which & AP_B) ? ap_p2_locks(b, t, vb) : 0;
    uint32_t mask = ma | mb;
    for (unsigned j = 0; j < AP_P2; j++) {
        out[j] = knob[j];
        if (!(mask & (1u << j))) continue;
        uint8_t x = (ma >> j) & 1 ? va[j] : knob[j], y = (mb >> j) & 1 ? vb[j] : knob[j];
        if (which != AP_AB) out[j] = (ma >> j) & 1 ? x : y;
        else if ((selects >> j) & 1) out[j] = wa >= 0x4000 ? x : y;
        else out[j] = ap_mix(x, y, wa, 0x8000 - wa);
    }
    return mask;
}

unsigned ap_p2_clear(uint8_t *cells, unsigned t, uint32_t mask) {
    unsigned n = 0;
    for (unsigned i = 0; i < AP_CELLS; i++) {
        int j = p2_index(cells[2 * i], t);
        if (j < 0 || !((mask >> j) & 1)) continue;
        cells[2 * i] = 0xff;
        n++;
    }
    return n;
}

unsigned ap_p2_set(uint8_t *cells, unsigned t, uint32_t mask, const uint8_t *vals) {
    unsigned n = 0;
    for (unsigned j = 0; j < AP_P2; j++) {
        if (!((mask >> j) & 1)) continue;
        unsigned key = p2_key(t, j), at = AP_CELLS;
        for (unsigned i = 0; i < AP_CELLS && at == AP_CELLS; i++)
            if (cells[2 * i] == key) at = i;
        for (unsigned i = 0; i < AP_CELLS && at == AP_CELLS; i++)
            if (cells[2 * i] & 0x80) at = i;
        if (at == AP_CELLS) continue;
        cells[2 * at] = (uint8_t)key;
        cells[2 * at + 1] = vals[j];
        n++;
    }
    return n;
}
