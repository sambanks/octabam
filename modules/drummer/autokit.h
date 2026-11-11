/* DRUMMER -- AUTO kit: a zone, a role and an ALIGN for every slice, from its
 * sound. Freestanding (integers, no library call), the same code on the unit
 * (kit.c reads the slot's audio in RAM) and on the host (verify_autokit.py
 * reads the WAV).
 *
 * Per slice: its peak and its main hit (the first 1 ms block at half the
 * peak, in the first 0.5 s); then, over 70 ms from the hit, the energy, the
 * energy under a one-pole low-pass (about 110 Hz), the energy of the first
 * difference / 4 (a high-frequency measure) and how much of it is left in
 * the window's second half; and the decay, how long the hit rings (its last
 * 10 ms block within 40 dB of the peak, 4 s at most). Rules (calibrated on the
 * user's 16-slice loop and, image 69, a 35-sound acoustic kit the user named:
 * autokit_refs.py, score_autokit.py; 10/10 and 30/35):
 *   KICK   lows >= 45 % of the energy
 *   CYMBAL rings 1.2 s or more, lows < 15 %, highs >= 5 %: CRASH if it holds
 *          (>= 60 %), RIDE if not
 *   HAT    highs >= 15 %, lows < 15 %: HAT O if it holds (>= 50 %), HAT C if not
 *   SNARE  highs >= 1 %, lows < 30 %, loud (peak >= 40 % of the loudest slice)
 *   GHOST  the same, soft
 *   TOM    lows 15..45 %
 *   PERC   the rest
 * Roles by level (the mean square after the hit) inside each zone: the top
 * third ACCENT, the bottom third SOFT.
 * ALIGN: the main hit's position when it is 15 ms or later into the slice.
 *
 * SIMILAR slices (image 59): a fingerprint per slice, its level left out --
 * the square root of each of four bands' share of the energy (one-poles at
 * about 110 Hz, 1 kHz and 4 kHz cut the window in four) and the window's
 * envelope in eight segments (log2 under the loudest, 1/16 octave, 12 octaves
 * at most). The distance, in tenths: |bands| + |envelope| x 500 / 192, the
 * scale of the host prototype (the user's loop: its repeats 0.2 .. 5.8 apart,
 * a 32-sound chain's two nearest 7.8). Inside a zone, the loudest slice first:
 * a slice within the tolerance of one kept is its copy -- OUT, or LINKED to
 * it (GAIN turned on one turns the group) -- unless 6 dB softer or more,
 * which is kept as a SOFT of its own. */
#ifndef AUTOKIT_H
#define AUTOKIT_H
#include "drummer.h"

typedef struct {
    uint32_t peak;               /* |sample| >> 6, the peak */
    uint32_t low_pct, high_pct;  /* the low / high energy, % of the total */
    uint32_t onset_ms;           /* the main hit, ms into the slice */
    uint32_t hold_pct;           /* the window's second half, % of its first */
    uint32_t level;              /* the window's mean square: how loud (a clipped peak says less) */
    uint16_t band[4];            /* sqrt(the band's share of the energy) x 1000: lows .. highs */
    uint8_t env[8];              /* the segment's energy under the loudest, 1/16 octave (0 the loudest, 192 at most) */
    uint32_t decay_ms;           /* the hit's ring: its last 10 ms block within 40 dB of the peak (4 s at most) */
} AkFeatures;

enum { AK_TOL_MAX = 15, AK_TOL_DEFAULT = 6, AK_DUP_OUT = 0, AK_DUP_LINK = 1 };

/* One mono sample (left + right) / 2, 16-bit scale, at a frame of the slot. */
typedef int (*AkRead)(void *ctx, uint32_t frame);

void ak_features(AkRead read, void *ctx, uint32_t start, uint32_t end, AkFeatures *f);

/* The distance of two slices' fingerprints, in tenths (the tolerance's unit x 10). */
uint32_t ak_distance(const AkFeatures *a, const AkFeatures *b);

/* The kit from the slices' features: zone, role (and combo 0) for n slices,
 * ALIGN in align[] (ms). tol 0: no similar slices looked for; else (tenths of
 * it x 10) the copies are OUT (mode AK_DUP_OUT) or linked (AK_DUP_LINK):
 * link[i] = the kept slice + 1 for every slice of a group of two or more, the
 * kept one too, 0 alone. Returns the copies found. */
unsigned ak_kit(const AkFeatures *f, unsigned n, DrKit *k, uint8_t *align, unsigned tol, unsigned mode,
                uint8_t *link);

#endif
