/* DRUMMER -- AUTO kit (autokit.h says what and why). */
#include "autokit.h"

#define AK_RATE 44100u
#define AK_WINDOW (AK_RATE * 70u / 1000u)       /* 70 ms */
#define AK_BLOCK (AK_RATE / 1000u)              /* 1 ms */

static uint32_t pct(uint32_t part, uint32_t total)
{
    if (!total)
        return 0;
    if (part >= total)
        return 100;
    return total > 40000000u ? part / (total / 100u) : part * 100u / total;
}

static uint32_t isqrt(uint32_t v)
{
    uint32_t r = 0, b = 1u << 30;
    while (b > v)
        b >>= 2;
    while (b) {
        if (v >= r + b) {
            v -= r + b;
            r = (r >> 1) + b;
        } else {
            r >>= 1;
        }
        b >>= 2;
    }
    return r;
}

/* log2(v) in 1/16 octave (v >= 1). */
static uint32_t log2q4(uint32_t v)
{
    static const uint8_t FRAC[16] = { 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 15 };
    uint32_t b = 0;
    while (v >> (b + 1))
        b++;
    return b * 16u + FRAC[(b >= 4 ? v >> (b - 4) : v << (4 - b)) & 15u];
}

/* Pass 1, the whole slice (at most 0.5 s) in 1 ms blocks: its peak and the
 * main hit, the first block at half the peak. Pass 2, 70 ms from that block:
 * the energies and the hold. */
void ak_features(AkRead read, void *ctx, uint32_t start, uint32_t end, AkFeatures *f)
{
    uint32_t n = end > start ? end - start : 0, i, j, e = 0, lo = 0, hi = 0, first = 0, second = 0;
    uint32_t peak = 0, hit = 0, w, eb[4] = { 0, 0, 0, 0 }, es[8] = { 0 }, tb = 0, top = 0, k;
    int32_t y = 0, q1 = 0, q2 = 0, q3 = 0, prev = 0;
    if (n > AK_RATE / 2u)
        n = AK_RATE / 2u;
    for (i = 0; i < n; i++) {
        int32_t x = read(ctx, start + i) >> 6;
        uint32_t a = (uint32_t)(x < 0 ? -x : x);
        if (a > peak)
            peak = a;
    }
    for (i = 0; i < n && peak; i += AK_BLOCK) {
        uint32_t m = 0;
        for (j = i; j < i + AK_BLOCK && j < n; j++) {
            int32_t x = read(ctx, start + j) >> 6;
            uint32_t a = (uint32_t)(x < 0 ? -x : x);
            if (a > m)
                m = a;
        }
        if (m * 2u >= peak) {
            hit = i;
            break;
        }
    }
    w = n - hit < AK_WINDOW ? n - hit : AK_WINDOW;
    for (i = 0; i < w; i++) {
        int32_t x = read(ctx, start + hit + i) >> 6, d = x - prev, lp, b1, b2;
        uint32_t x2 = (uint32_t)(x * x);
        prev = x;
        /* the low-pass in 1/256 (image 69): in whole units (x - y) / 64 stood still under 64, and a
         * kick at -8 dBFS measured 29 % lows for its 97 % */
        y += (x * 256 - y) / 64;                  /* one pole, ~110 Hz at 44.1 kHz */
        lp = y / 256;
        e += x2;
        lo += (uint32_t)(lp * lp);
        hi += (uint32_t)(d * d) / 4u;             /* (2 sin(pi f / fs))^2 <= 4: /4 keeps it under e */
        /* SIMILAR's fingerprint keeps image 59's whole-unit one-poles: its tolerance was set on them (the
         * user's loop: its repeats 0.2 .. 5.7 apart); the precise ones moved a hat pair 5.7 -> 6.2 */
        q1 += (x - q1) / 64;                      /* ~110 Hz */
        q2 += (x - q2) / 8;                       /* ~0.9 kHz */
        q3 += (x - q3) / 2;                       /* ~3.5 kHz */
        b1 = q2 - q1;
        b2 = q3 - q2;
        eb[0] += (uint32_t)(q1 * q1) >> 4;        /* the four bands; >> 4 keeps 70 ms in 32 bits */
        eb[1] += (uint32_t)(b1 * b1) >> 4;
        eb[2] += (uint32_t)(b2 * b2) >> 4;
        eb[3] += (uint32_t)((x - q3) * (x - q3)) >> 4;
        es[i * 8u / w] += x2;
        if (i < w / 2)
            first += x2;
        else
            second += x2;
    }
    f->peak = peak;
    f->low_pct = pct(lo, e);
    f->high_pct = pct(hi, e);
    f->onset_ms = hit / AK_BLOCK;
    f->hold_pct = pct(second, first);
    f->level = w ? e / w : 0;
    /* the decay (image 69): from the hit, 10 ms blocks (every 4th frame read), the last one still within
     * 40 dB of the slice's peak, up to 4 s or the slice's end. A cymbal rings for seconds; a hat, a snare
     * or a kick is down in a few hundred ms. */
    {
        uint32_t nd = end > start ? end - start : 0, pk = 0, last = hit, b;
        if (nd > AK_RATE * 4u)
            nd = AK_RATE * 4u;
        for (i = hit; i < nd && i < hit + AK_RATE / 10u; i += 4) {
            int32_t x = read(ctx, start + i);
            uint32_t a = (uint32_t)(x < 0 ? -x : x);
            if (a > pk)
                pk = a;
        }
        for (b = hit; b < nd && pk; b += AK_RATE / 100u) {
            uint32_t m = 0;
            for (i = b; i < b + AK_RATE / 100u && i < nd; i += 4) {
                int32_t x = read(ctx, start + i);
                uint32_t a = (uint32_t)(x < 0 ? -x : x);
                if (a > m)
                    m = a;
            }
            if (m * 100u >= pk)
                last = b;
        }
        f->decay_ms = (last - hit) / AK_BLOCK;
    }
    for (k = 0; k < 4; k++)
        tb += eb[k];
    for (k = 0; k < 4; k++) {               /* the share in 1/10000, its root x 1000 */
        uint32_t sh = !tb ? 0 : tb > 400000u ? eb[k] / (tb / 10000u) : eb[k] * 10000u / tb;
        f->band[k] = (uint16_t)isqrt((sh > 10000u ? 10000u : sh) * 100u);
    }
    for (k = 0; k < 8; k++) {
        es[k] = log2q4(es[k] + 1u);
        if (es[k] > top)
            top = es[k];
    }
    for (k = 0; k < 8; k++)
        f->env[k] = (uint8_t)(top - es[k] > 192u ? 192u : top - es[k]);
}

uint32_t ak_distance(const AkFeatures *a, const AkFeatures *b)
{
    uint32_t sb = 0, se = 0, k;
    for (k = 0; k < 4; k++) {
        int32_t d = (int32_t)a->band[k] - (int32_t)b->band[k];
        sb += (uint32_t)(d * d);
    }
    for (k = 0; k < 8; k++) {
        int32_t d = (int32_t)a->env[k] - (int32_t)b->env[k];
        se += (uint32_t)(d * d);
    }
    return isqrt(sb) + isqrt(se) * 500u / 192u;
}

static unsigned zone_of(const AkFeatures *f, uint32_t loudest)
{
    unsigned loud = f->peak * 100u >= loudest * 40u;
    if (!f->peak)
        return DR_OUT;
    if (f->low_pct >= 45)
        return DR_KICK;
    if (f->decay_ms >= 1200 && f->low_pct < 15 && f->high_pct >= 5)   /* rings for seconds: a cymbal */
        return f->hold_pct >= 60 ? DR_CRASH : DR_RIDE;
    if (f->high_pct >= 15 && f->low_pct < 15)
        return f->hold_pct >= 50 ? DR_HATO : DR_HATC;
    if (f->high_pct >= 1 && f->low_pct < 30)
        return loud ? DR_SNARE : DR_GHOST;
    if (f->low_pct >= 15)
        return DR_TOM;
    return DR_PERC;
}

/* Similar slices: inside each zone, loudest first, a slice within tol of one
 * already kept (and less than 6 dB under it) is its copy. Returns the copies. */
static unsigned similar(const AkFeatures *f, unsigned n, DrKit *k, unsigned tol, unsigned mode, uint8_t *link,
                        uint8_t *soft)
{
    unsigned i, j, copies = 0;
    uint8_t done[DR_SLICES], keep[DR_SLICES];
    for (i = 0; i < n; i++) {
        done[i] = keep[i] = 0;
        soft[i] = 0;
    }
    for (;;) {                                   /* the loudest slice not yet seen */
        unsigned best = n, kept = n;
        for (i = 0; i < n; i++)
            if (!done[i] && k->zone[i] < DR_ZONES && (best == n || f[i].level > f[best].level))
                best = i;
        if (best == n)
            break;
        done[best] = 1;
        for (j = 0; j < n; j++)                  /* the nearest kept slice of its zone within tol */
            if (keep[j] && k->zone[j] == k->zone[best] && ak_distance(&f[j], &f[best]) <= tol * 10u
                && (kept == n || ak_distance(&f[j], &f[best]) < ak_distance(&f[kept], &f[best])))
                kept = j;
        if (kept == n) {
            keep[best] = 1;
            continue;
        }
        if (f[best].level * 4u <= f[kept].level) {   /* 6 dB softer or more: a SOFT of its own */
            keep[best] = 1;
            soft[best] = 1;
            continue;
        }
        copies++;
        if (mode == AK_DUP_LINK) {
            link[best] = (uint8_t)(kept + 1);
            link[kept] = (uint8_t)(kept + 1);
        } else {
            k->zone[best] = DR_OUT;
        }
    }
    return copies;
}

unsigned ak_kit(const AkFeatures *f, unsigned n, DrKit *k, uint8_t *align, unsigned tol, unsigned mode,
                uint8_t *link)
{
    unsigned i, j, z, copies = 0;
    uint32_t loudest = 0;
    uint8_t soft[DR_SLICES];
    if (n > DR_SLICES)
        n = DR_SLICES;
    for (i = 0; i < n; i++)
        if (f[i].peak > loudest)
            loudest = f[i].peak;
    for (i = 0; i < n; i++) {
        k->zone[i] = (uint8_t)zone_of(&f[i], loudest);
        k->combo[i] = 0;
        align[i] = (uint8_t)(f[i].onset_ms >= 15 ? (f[i].onset_ms > 250 ? 250 : f[i].onset_ms & ~1u) : 0);
        soft[i] = 0;
    }
    for (i = 0; i < DR_SLICES; i++)
        link[i] = 0;
    if (tol)
        copies = similar(f, n, k, tol, mode, link, soft);
    /* roles: rank by peak inside each zone; the top third ACCENT, the bottom third SOFT */
    for (z = 0; z < DR_ZONES; z++) {
        unsigned count = 0;
        for (i = 0; i < n; i++)
            count += k->zone[i] == z;
        for (i = 0; i < n; i++) {
            unsigned louder = 0;
            if (k->zone[i] != z)
                continue;
            for (j = 0; j < n; j++)
                if (k->zone[j] == z && (f[j].level > f[i].level || (f[j].level == f[i].level && j < i)))
                    louder++;
            if (count < 2)
                k->role[i] = DR_NORMAL;
            else if (louder * 3u < count)
                k->role[i] = DR_ACCENT;
            else if (louder * 3u >= count * 2u)
                k->role[i] = DR_SOFT;
            else
                k->role[i] = DR_NORMAL;
        }
    }
    for (i = 0; i < n; i++)
        if (soft[i])
            k->role[i] = DR_SOFT;
    for (i = n; i < DR_SLICES; i++) {
        k->zone[i] = DR_OUT;
        align[i] = 0;
    }
    return copies;
}
