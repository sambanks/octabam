WAVELOAD is a CPU benchmark probe rather than a playable machine. It renders K
instances of a fixed-point port of CHOMPI WAVE's 4-voice engine inside the
ColdFire frame interrupt and discards the output, letting CF Meter measure the
CPU cost of a 4-voice wavetable track and how many instances fit.

## Access

WAVELOAD has no menu or screen of its own. CF Meter's BURN knob (T8 FX2 page 1,
first knob) sets K from 0 to 12 (values above 12 render 12 instances). It is
included in the `waveload` and `waveload-port` remixes rather than in the
official remixes.

## Operation

- Read the CPU load on CF Meter's readout (see CF Meter): set K, then check the
  frame interrupt's mean and maximum timing.
- Testing showed that one 4-voice track is the ColdFire's practical limit,
  which is why WAVE runs on the DSP instead.
- The fixed-point engine closely matches CHOMPI WAVE's original floating-point
  classes until the pitch LFO engages, after which they diverge.
- The `waveload` image currently fails to assemble (`meter.s:91`, short branch
  displacement 130), so captures are unavailable until that error is fixed.
