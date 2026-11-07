/* WAVE's note layer: pitch, chords and the knob laws, over engine.h. */
#pragma once
#include "engine.h"

uint32_t wcf_inc(int32_t p_q8);                            /* phase increment of p (Q8 semitones above C3, clamped to +-48) */
void wcf_note(Engine *e, int32_t p_q8, int chrd, int voic);  /* a START: CHORD: the first voic voices on the chord's notes, the rest off; POLY: the next of the voic voices, one note */
void wcf_scale(Engine *e, uint32_t mask);                      /* the scale to snap notes onto, 0 = none (read at a START) */
void wcf_init(Engine *e, const int16_t *table);             /* the engine, with its fixed internal attack (1.5 ms) and release (13 ms) */
void wcf_knobs(Engine *e, int fram, int sprd, int glid);     /* raw 0..127 each: frame position, voicing spread, pitch glide */
void wcf_setup(Engine *e, int vibr, int vrat, int oct, int fine, int comp, int mode);   /* SETUP: raw 0..127 each, oct 0..2 (-1, 0, +1), mode 0 CHORD / 1 POLY */
void wcf_clock(Engine *e, int step);                         /* once a frame: the sequencer's step word; times frames a step */
void wcf_amp(Engine *e, int atk, int hold, int rel, int start);   /* once a frame, before the render: the AMP page's ATK, HOLD, REL (raw 0..127)
                                                                   * as the DSP's own laws; start: a START this frame. The DSP is left at ATK 0 / HOLD INF / REL INF */
