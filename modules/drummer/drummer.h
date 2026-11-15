/* DRUMMER -- the drummer engine: one sliced FLEX track played as a drum kit.
 *
 * Once per sequencer step of a DRUMMER track the adapter asks dr_step() what
 * the step plays: nothing, or ONE hit (the track is mono: a hit cuts the one
 * before) with its slice, level, micro-timing and ornament. The answer comes
 * from the kit (each slice's zone and role), the style tables, the knobs
 * (DENS, CPLX, HUMAN, BRK, SEED and the six humanisation aspects) and the
 * track's own trig on that step, which forces a hit (an accent or a fill).
 *
 * Rules the tests hold (verify.py):
 *   - HUMAN 0 plays the style's groove untouched: no level shaping, no
 *     micro-timing, no ghost, no ornament, the first slice of each role.
 *   - A trig of the track always plays.
 *   - The same SEED replays the same performance from the transport start.
 *   - BRK 0 is the groove again, whatever BRK did before.
 *   - Collisions: the COMBO slice holding exactly the colliding zones, else
 *     the highest priority zone; SHIFT moves a light loser to the next step.
 *
 * Freestanding: integers only, no library call, no allocation. Compiled for
 * the unit by generate.py (m68k-elf-gcc -mcpu=5475), tested on the host by
 * verify.py. Every state field starts at zero. */
#ifndef DRUMMER_H
#define DRUMMER_H
#include <stdint.h>

#define DR_SLICES 64
#define DR_STEPS 16              /* steps of a 4/4 bar (a 12/8 style's bar is 12) */

enum {                           /* zones */
    DR_KICK, DR_SNARE, DR_GHOST, DR_HATC, DR_HATO, DR_RIDE, DR_CRASH, DR_TOM, DR_PERC,
    DR_ZONES,                    /* 9 playing zones */
    DR_COMBO = DR_ZONES,         /* a slice holding several zones (combo mask) */
    DR_OUT = 15                  /* not in the kit */
};
enum { DR_ACCENT, DR_NORMAL, DR_SOFT, DR_ROLES };
#define DR_STYLES 29             /* styles.py: BRKB HHOP FUNK HOUS JUNG DUB AFRO CLAV BOSS BMBE ROCK DISC TECH
                                 * TRAP RNB DEMB SAMB BAIA CUMB GARA DSTP SHUF SIX8 ELEC DEEP MINI AMAP
                                 * FTWK HILF */

enum { DR_MIX_KICK, DR_MIX_SNARE, DR_MIX_HATS, DR_MIX_CYMB, DR_MIX_TOMS, DR_MIX_PERC, DR_MIXES };
#define DR_LK_PAGE 1u            /* KIT BALANCE's page id in PAGES' locks (pages/manifest.py LOCKS) */
                                 /* KIT BALANCE's groups: KICK; SNARE GHOST; HAT C HAT O; RIDE CRASH; TOM; PERC */

#define DR_GAIN_MIN (-24)        /* a slice's GAIN in the KIT window, dB */
#define DR_GAIN_MAX 6

typedef struct {
    uint8_t zone[DR_SLICES];     /* DR_KICK .. DR_COMBO, DR_OUT */
    uint8_t role[DR_SLICES];     /* DR_ACCENT .. DR_SOFT */
    uint16_t combo[DR_SLICES];   /* COMBO slices: bit z = holds zone z */
    uint8_t count;               /* slices in the sample (0..64) */
    uint8_t prio[DR_ZONES];      /* zones, highest priority first */
    uint8_t reserved[2];
} DrKit;

typedef struct {                 /* knob values 0..127 (style 0..DR_STYLES-1) */
    uint8_t style, dens, cplx, human, brk, seed;   /* the PLAYBACK page */
    uint8_t vel, round, time, ghost, orn, var;     /* the SETUP page: the aspects */
    uint8_t shift;               /* 0 off, else a light loser may move a step */
    uint8_t phrase;              /* bars of a phrase: 4 or 8 (0 = 4) */
    uint8_t mix[DR_MIXES];       /* KIT BALANCE, the zones' mix: 0 out, 64 the style's, 127 twice as busy */
    uint8_t fill[6];             /* FILLS (image 74), 0 AUTO each: FILL FREQ LONG STIK ORCH TRIP (DR_F_*) */
    uint8_t reserved[2];
    const struct DrLoop *loop;   /* REDRUM (image 77): the sample's own loop as the groove, 0 off */
    struct DrLoopBar *bar;       /* REDRUM's scratch (one for every track: one step at a time) */
} DrParams;

/* REDRUM (image 77, the KIT window's F): the sample's own loop -- its slices
 * where they start in it, the trim's bars long -- is the groove the knobs play
 * with; the style gives its fills, and its COMPLEX cells past CPLX 64. */
#define DR_LOOP_STEPS 128        /* 8 bars at most */

typedef struct DrStyle {
    const char *lv[3][DR_ZONES]; /* BASIC (CPLX 0), STANDARD (64), COMPLEX (127) */
    const char *fill[DR_ZONES];  /* a bar's end when a fill plays (VAR, BRK) */
    uint8_t late;                /* snare lay-back, 1/24 step at TIME 127 */
    uint8_t swing;               /* odd-16th hat delay, 1/24 step at TIME 127 */
    uint8_t len;                 /* steps in a bar: 16, or 12 (12/8) */
    uint8_t fam[4];              /* the fill library's weights: written, rudiment, triplet, 3 over 4 */
} DrStyle;

typedef struct DrLoop {
    uint8_t len;                 /* the loop's steps (16 a bar), 0 none */
    uint8_t slice[DR_LOOP_STEPS];    /* the slice + 1 starting on the step, 0 none */
    int8_t mt[DR_LOOP_STEPS];    /* its place from the step, 1/24 step (-12..11) */
    uint8_t pad;
} DrLoop;

typedef struct DrLoopBar {       /* dr_step's scratch: the bar as a style */
    char row[3][DR_ZONES][DR_STEPS + 1];   /* BASIC (the loop, no soft slice), the loop, the loop + the style's COMPLEX */
    DrStyle style;
} DrLoopBar;

/* The loop from the slot: n slices' bounds (start, end, loop point: 3 words
 * each), the trim (frames), its bars x 100 (0: from the tempo, BPM x 24),
 * each slice's ALIGN (ms, 0 none: the hit's place is the slice's start plus
 * it). */
void dr_loop_build(DrLoop *l, const uint32_t *bounds, unsigned n, uint32_t trim_start, uint32_t trim_end,
                   unsigned bars100, unsigned tempo24, const uint8_t *align_ms);
/* Its length in steps as dr_loop_build lays it (image 78: 1, 2, 4 or 8 whole bars, the nearest to
 * TRIM_BARS or the tempo's; the slices' own extent when none starts in the trim), 0 none. */
unsigned dr_loop_steps(const uint32_t *bounds, unsigned n, uint32_t trim_start, uint32_t trim_end,
                       unsigned bars100, unsigned tempo24);

enum { DR_F_FILL, DR_F_FREQ, DR_F_LONG, DR_F_STIK, DR_F_ORCH, DR_F_TRIP, DR_FILLS };
/* FILL  AUTO (ORN's share, the style's colour), WRIT, RUDI, TRIP, 3:4: the family of every fill
 * FREQ  AUTO: BRK 32..63's (every bar) and VAR's own; BRK: BRK's alone (every bar), 2BAR, PHRS (the
 *       phrase's end): BRK's alone, those bars (image 75)
 * LONG  AUTO (BRK's place: 32 half a beat, 40 a beat, 48 two, 56 a bar), 1BT, 2BT, BAR
 * STIK  AUTO (drawn), else the family's sticking n (FILL RUDI, TRIP or 3:4)
 * ORCH  AUTO (drawn), TOMS (right hand round the toms), SNR (all on the snare), SWAP
 * TRIP  AUTO (drawn), 8TH (8th triplets), 6LET (sextuplets), 8>6 (8ths into sextuplets) */
enum { DR_FILL_MAX = 4, DR_FREQ_MAX = 3, DR_LONG_MAX = 3, DR_ORCH_MAX = 3, DR_TRIP_MAX = 3 };
/* The stickings of a family (1 rudiment, 2 triplet, 3 3:4): the count, and the n-th's name (4 characters). */
unsigned dr_fill_sticks(unsigned fam);
const char *dr_fill_stick_name(unsigned fam, unsigned n);

typedef struct {
    uint8_t last[DR_ZONES][DR_ROLES];  /* the slice index (in its list) last played */
    uint8_t carry;               /* zone + 1 shifted from the step before, 0 none */
    uint8_t prev_zone;           /* zone + 1 of the last hit, 0 none */
    uint8_t prev_slice;          /* slice + 1 of the last hit, 0 none */
    uint8_t since_crash;         /* 0 no crash yet; 1 + steps since the last crash (saturates) */
    uint8_t fill_len;            /* steps of the fill the last step was in, 0 none: a beat or more lands on a crash (image 76) */
} DrState;

typedef struct {
    uint8_t play;                /* 1: the step plays this hit */
    uint8_t slice;               /* 0..count-1 */
    uint8_t vel;                 /* 1..127, the hit's level before the adapter's VOL law */
    int8_t mtime;                /* micro-timing, 1/24 step, -23..23 */
    uint8_t rtrg;                /* retrigs after the hit (0 none), a flam or a roll */
    uint8_t rtim;                /* retrig interval, 1/24 step (0 when rtrg is 0) */
    uint8_t zone;                /* the zone played (DR_COMBO for a combo slice) */
    uint8_t flags;               /* DRF_* */
} DrHit;

#define DRF_FORCED 1             /* the track's trig */
#define DRF_GHOST  2             /* added by GHOST */
#define DRF_FILL   4             /* a fill (VAR, BRK) */
#define DRF_BREAK  8             /* a BRK cut (shuffle, repeat) */
#define DRF_COMBO  16            /* a collision answered by a combo slice */
#define DRF_SHIFT  32            /* carried from the step before */

/* The default kit: every slice out, priority KICK SNARE CRASH HATO TOM PERC HATC RIDE GHOST. */
void dr_kit_init(DrKit *k, unsigned count);

/* What step `step` (0..15) of bar `bar` (bars since the transport start)
 * plays. `forced`: the track has a trig there. */
void dr_step(const DrKit *k, const DrParams *p, DrState *s, uint32_t bar, unsigned step,
             unsigned forced, DrHit *out);   /* step < dr_style_len(p->style) */

/* Steps in a bar of the style: 16, or 12 for a 12/8 style. */
unsigned dr_style_len(unsigned style);
/* Its name on the knob (4 characters). */
const char *dr_style_name(unsigned style);
/* SEED's variant: 0 the table, 1..16 (image 62: SEED in eight bands of sixteen). */
unsigned dr_seed_variant(unsigned seed);

/* The groove alone (HUMAN 0, BRK 0): does zone z hit at this step? (for the
 * window's preview and the tests) */
unsigned dr_groove_hits(const DrKit *k, const DrParams *p, unsigned step);

#endif
