/* ColdFire descriptor helpers; all audio synthesis runs on the DSP. */
#include "engine.h"
#include "tables.inc"
const uint8_t ab_mc_defaults[AB_PARAMS] = {64, 80, 80, 64, 64, 0, 0, 64, 127, 64, 64, 0};
unsigned ab_lpf_frequency(unsigned value) { return (unsigned)ab_lpf_freq[value&127]; }
