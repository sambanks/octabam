TAPE ECHO is a mono single-head tape echo with stereo dry output that replaces
FX2 SPRING REV. It runs on the ColdFire CPU rather than the DSP using the stock
delay's four-second per-track ring buffer, leaving the DSP side as an empty
passthrough. Repeats darken and wobble as you raise AGE and WOW, and feedback
past the midpoint builds tape noise into self-oscillation.

## Access

Select a track, press FX2, and choose TAPE ECHO from the chooser where SPRING
REV used to be. All parameters are on page 1; page 2 is disabled. This module
is not included in the official remixes; build the `tapeecho` remix to use it.
It is not yet hardware-qualified: earlier builds froze the unit during editing
with three to six active instances, and the current build has not been flashed
to hardware.

![FX2 SETUP with Tape Echo selected.](../../img/tapeecho/chooser.png)

*FX2 SETUP with Tape Echo selected.*

## Operation

- In SYNC FREE mode, TIME is continuous from 46 to 231 ms.
- In SYNC BEAT mode, TIME selects one of twelve named note divisions
  (T = triplet, dot = dotted): 1/64, 1/32 triplet, 1/32, 1/16 triplet, 1/16,
  1/8 triplet, dotted 1/16, 1/8, 1/4 triplet, dotted 1/8, 1/4, and dotted 1/4.
  The delay follows the project tempo, and all twelve divisions fit from 30 to
  300 BPM.
- Changing the delay time in BEAT mode crossfades the read pointer over about
  11.6 ms and settles within about 23 ms of the last edit.
- MIX at 0 outputs the exact dry signal.
- DRIVE is fixed at 0.
- AGE occupies the parameter slot formerly used by HEADS, so saved projects
  with HEADS parameter locks need those locks reset.

## Parameters

| Page | Knob | Range | What it does |
|---|---|---|---|
| 1 | TIME | 0-127 | 46-231 ms in FREE; a division in BEAT |
| 1 | FDBK | 0-127 | Regeneration; the top of the range self-oscillates |
| 1 | WOW | 0-127 | 0.8 Hz wow plus random flutter; 0 is static |
| 1 | AGE | 0-127 | Repeat bandwidth, flutter, and hiss; fresh at 0, worn at 127 |
| 1 | SYNC | FREE, BEAT | Continuous or tempo-quantised time |
| 1 | MIX | 0-127 | Dry/wet mix; 0 is exact dry |
