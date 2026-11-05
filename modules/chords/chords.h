/* CHORDS FACTORY engine: chord types, voicings and voice leading. Pure C,
 * no firmware: adapter.c drives it from the atelier page. A chord is played
 * by one MIDI trig, so it has at most CH_VOICES notes (stock's NOTE, NOT2,
 * NOT3, NOT4). */
#ifndef CHORDS_H
#define CHORDS_H

#include <stdint.h>

enum { CH_VOICES = 4, CH_SLOTS = 16, CH_BANKS = 16, CH_NAME = 8 };
enum { CH_NONE = 0xff };        /* an empty voice in a ChVoicing */

/* The notes of one chord, lowest first; n of them (0 = an empty slot). */
typedef struct {
    uint8_t n;
    uint8_t note[CH_VOICES];
} ChVoicing;

/* The chord types: a name (after the root's: "m7" -> "Dm7") and the pitch
 * classes above the root, at most CH_VOICES (a ninth leaves its fifth out). */
typedef struct {
    char    name[6];
    uint8_t n;
    uint8_t pc[CH_VOICES];
} ChType;

extern const ChType ch_types[];
extern const unsigned ch_ntypes;

/* SPREAD: how a built chord is laid out from its inversion's close voicing.
 * Wider after OPEN: BASS (OPEN, its bass an octave down), TENTH (the bass,
 * the others an octave up), WIDE (voice k k octaves up). Added at the end:
 * chords.work's spread bytes keep their meaning. */
enum { CH_CLOSE, CH_DROP2, CH_DROP3, CH_OPEN, CH_BASS, CH_TENTH, CH_WIDE, CH_SPREADS };
extern const char *const ch_spread_names[CH_SPREADS];

/* Root (0 C .. 11 B), type, inversion (0 root position .. n-1, clamped),
 * spread, octave (octave n's C is 12 n: 60, stock's C4, is octave 5, shown OCT 4): one voicing. */
void ch_build(unsigned root, unsigned type, unsigned inversion, unsigned spread, unsigned octave, ChVoicing *out);

/* Voice leading: the voicings of root/type nearest `prev`, best first, at
 * most `max` (<= CH_LEAD_MAX). Each keeps the chord's every pitch class
 * (a triad after a four-note chord doubles its root or fifth), no unison,
 * no voice crossing (voice i is the i-th lowest), notes within an octave
 * below prev's lowest .. above its highest. The cost: the total semitones
 * the voices move (prev's voices matched in order; a voice added or
 * dropped counts its distance to the nearest); a doubled third costs 2,
 * a span over two octaves 1 a semitone more. CH_BASS_ROOT: the lowest note
 * is the root. Returns how many; 0 when prev is empty (ch_build then). */
enum { CH_LEAD_MAX = 8, CH_BASS_ROOT = 1 };
unsigned ch_lead(const ChVoicing *prev, unsigned root, unsigned type, unsigned flags,
                 ChVoicing out[], unsigned max);
unsigned ch_cost(const ChVoicing *prev, const ChVoicing *next);

/* A voicing's root and type when its pitch classes are a known chord
 * (the bass preferred as root); returns 0 when they are not. */
unsigned ch_identify(const ChVoicing *v, unsigned *root, unsigned *type);

/* "Dm7", "F#maj7", or "?" for an unknown chord, "-" for an empty one. */
void ch_name(const ChVoicing *v, char out[CH_NAME]);

/* The scale's chord on `degree` (0 = the tonic's): its notes a third
 * apart in the scale, three or (sevenths) four. `scale` is SCALES' form,
 * mask << 4 | tonic (mask bit d = d semitones above the tonic). Returns 0
 * when the stack is no known type (the root and type left unset). */
unsigned ch_diatonic(int32_t scale, unsigned degree, unsigned sevenths, unsigned *root, unsigned *type);

/* The keyboard: note toggled in or out of v (kept sorted). Returns 0 when
 * v is full and the note is not in it. */
unsigned ch_toggle(ChVoicing *v, unsigned note);

/* Move voice i by delta semitones, kept between its neighbours (no
 * crossing, no unison) and in 0..127. Returns nonzero when it moved. */
unsigned ch_move_voice(ChVoicing *v, unsigned i, int delta);

/* One slot of the atelier: the chord as played (v) and how it was made.
 * BUILT: ch_build(root, type, inv, spread, oct); LEAD: the `lead`-th
 * answer of ch_lead from the slot before (flags: CH_BASS_ROOT); EDIT: the
 * notes as moved or typed, kept. degree: the scale degree FUNC + F last
 * chose (0..6), or CH_NONE. An empty slot has v.n == 0. */
enum { CH_MODE_BUILT, CH_MODE_LEAD, CH_MODE_EDIT, CH_MODES };
typedef struct {
    ChVoicing v;
    uint8_t root, type, inv, spread, oct, lead, mode, degree, flags;
} ChSlot;
enum { CH_OCT_MAX = 9 };

void ch_slot_clear(ChSlot *s);      /* empty; C major, CLOSE, octave 4 (48, stock's C3), BUILT */
/* The slot's notes again from its parameters (BUILT, LEAD; EDIT keeps
 * them). LEAD with no chord before builds instead. Returns the number of
 * LEAD answers (the lead index is clamped to them), 0 otherwise. */
unsigned ch_slot_apply(ChSlot *s, const ChVoicing *prev);

/* chords.work's payload: per bank, per slot, n, the four notes, then the
 * nine parameters in ChSlot's order. */
enum { CH_SLOT_B = 1 + CH_VOICES + 9, CH_FILE_B = CH_BANKS * CH_SLOTS * CH_SLOT_B };
void ch_pack(const ChSlot bank[CH_BANKS][CH_SLOTS], uint8_t out[CH_FILE_B]);
/* Back, each slot checked: n 0..4, notes 0..127, ascending, distinct, every
 * parameter in its range; a slot that is not is cleared. */
void ch_unpack(const uint8_t in[CH_FILE_B], ChSlot bank[CH_BANKS][CH_SLOTS]);

#endif
