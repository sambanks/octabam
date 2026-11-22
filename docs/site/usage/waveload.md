A probe, not a playable machine. It renders K instances of a fixed-point
port of CHOMPI WAVE's voice engine (4 voices each) inside the ColdFire's
frame interrupt and discards the output, so CF Meter reads what a 4-voice
wavetable track costs on the unit and how many fit.

## Access

No menu and no screen of its own. CF Meter's BURN knob (T8 FX2 page 1,
first knob) becomes K, 0 to 12; above 12 it renders 12. The test remixes
`waveload` and `waveload-port` carry it. Not in an official remix.

## Operation

- Read the cost on CF Meter's readout (see CF Meter): set K, then read the
  frame interrupt's mean and maximum.
- The result was one 4-voice track as the ColdFire's limit, which is why
  WAVE runs on the DSP instead.
- The engine matches CHOMPI WAVE's own float classes closely until the
  pitch LFO starts, then parts.
- The `waveload` image does not assemble at present (`meter.s:91`, short
  branch displacement 130), so no capture of it is possible until that is
  fixed.
