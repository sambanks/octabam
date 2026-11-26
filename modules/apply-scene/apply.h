/* APPLY SCENE: the engine. No firmware calls: verify.py builds it for the
 * host and checks it against a model of stock's scene morph. */
#ifndef APPLY_H
#define APPLY_H

#include <stdint.h>

/* A track's page-1 parameters, as scene locks number them ("flat"): 0-5 SRC,
 * 6-11 LFO, 12-17 AMP (17 = XVOL, the scene-only level), 18-23 FX1, 24-29
 * FX2. A scene keeps 32 bytes per track; 30 and 31 are SCENES P2's. */
enum { AP_FLATS = 30, AP_XVOL = 17, AP_SCENE_BYTES = 32 };

/* Which scenes a gesture takes. */
enum { AP_A = 1, AP_B = 2, AP_AB = 3 };

/* A byte above 127 is unlocked (stock writes 0xff). */
static inline int ap_locked(uint8_t b) { return b < 0x80; }

/* Q15 weights from a track's weight long (0x80003c60 + 4t): the high half is
 * minus scene A's share, the low half minus scene B's, as the frame builder
 * multiplies them (msac). XF CURVE and MORPH write the same long. */
static inline int32_t ap_weight_a(uint32_t w) { return -(int32_t)(int16_t)(w >> 16); }
static inline int32_t ap_weight_b(uint32_t w) { return -(int32_t)(int16_t)(w & 0xffff); }

/* The values a gesture gives one track.
 *   which  AP_A, AP_B or AP_AB
 *   a, b   the two scenes' 32 bytes for the track; NULL = no scene there
 *          (none assigned, or muted with FUNC + SCENE for a blend)
 *   knob   the Part's own 30 values: the blend's side for an unlocked flat
 *   wa, wb the Q15 weights (ap_weight_a/_b)
 *   skip   flats never written (bit k = flat k)
 *   out    30 values
 * Returns the mask of flats the gesture writes: a scene's locked flats, or
 * for a blend every flat locked in either scene. */
uint32_t ap_values(unsigned which, const uint8_t *a, const uint8_t *b, const uint8_t *knob,
                   int32_t wa, int32_t wb, uint32_t skip, uint8_t *out);

/* The blend of two values with the frame builder's weights, rounded to the
 * nearest step and kept in 0..127. */
uint8_t ap_mix(uint8_t va, uint8_t vb, int32_t wa, int32_t wb);

/* A scene's 32 bytes for one track from the blend: every flat locked in A or
 * B (and not in `skip`) locked at the blend, the rest unlocked (0xff). XVOL
 * is locked only when both scenes lock it (an unlocked XVOL has no value to
 * blend with). Bytes 30-31 are copied from `keep` (the slot's own SCENES P2
 * cells). Returns the number of flats locked. */
unsigned ap_scene(const uint8_t *a, const uint8_t *b, const uint8_t *knob, int32_t wa, int32_t wb,
                  uint32_t skip, const uint8_t *keep, uint8_t *scene);

/* The commit: unlock (0xff) every flat in `mask` that the scene's 32 bytes for
 * a track lock. XVOL and bytes 30-31 are never touched. Returns how many it
 * unlocked. */
unsigned ap_clear(uint8_t *scene, uint32_t mask);

/* SCENES P2: page 2 of FX1 and FX2. A scene's page-2 locks are eight
 * cells shared by its tracks, in bytes 30 and 31 of its 32-byte rows: cell i
 * = row i's key (track<<4 | fx1<<3 | slot, bit 7 set = empty) and value.
 * Here `cells` is those 16 bytes in order (key, value per cell), and a
 * track's page 2 is twelve values, j 0-5 FX1's slots and 6-11 FX2's (the
 * Part's order from +0x8f07e). */
enum { AP_P2 = 12, AP_CELLS = 8 };

/* Track t's page-2 locks in `cells`: vals[j] the value or 0xff. Returns the
 * mask of locked j. */
uint32_t ap_p2_locks(const uint8_t *cells, unsigned t, uint8_t *vals);

/* ap_values for page 2, as SCENES P2's frame pass morphs it: a blend lerps
 * with wa and 0x8000 - wa, an unlocked side the knob, and a select (bit j of
 * `selects`) snaps, to A from wa 0x4000 up. a, b: the scenes' cells or NULL. */
uint32_t ap_p2_values(unsigned which, const uint8_t *a, const uint8_t *b, unsigned t, const uint8_t *knob,
                      int32_t wa, uint32_t selects, uint8_t *out);

/* The commit on page 2: track t's cells in `mask` emptied. Returns how many. */
unsigned ap_p2_clear(uint8_t *cells, unsigned t, uint32_t mask);

/* Track t's j in `mask` locked at vals[j]: its own cell, else a free one; a
 * lock with no cell left is dropped. Returns how many were written. */
unsigned ap_p2_set(uint8_t *cells, unsigned t, uint32_t mask, const uint8_t *vals);

#endif
