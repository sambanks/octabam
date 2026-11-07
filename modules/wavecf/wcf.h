/* WAVE's note layer: pitch, chords and the knob laws, over engine.h. */
#pragma once
#include "engine.h"

uint32_t wcf_inc(int32_t p_q8);                            /* phase increment of p (Q8 semitones above C3, clamped to +-48) */
void wcf_note(Engine *e, int32_t p_q8, int chrd, int voic);  /* a START: the first voic voices on the chord's notes, the rest off */
void wcf_knobs(Engine *e, int fram, int atk, int rel);       /* raw 0..127 each: frame position, attack, release */
