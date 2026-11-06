A pitch vibrato: the track's audio bends up and down in pitch, wet only by
default (MIX 127). Pick the shape on the setup page (SHP): SINE, TRI, SQR (a
two-note trill) or RND (a new random pitch every half cycle).

## Access

Select the track, press FX1, and pick VIBRATO. It runs on FX2 too when the
remix is built with its SLOTS setting at FX1+FX2 (only in a remix without the
delay and reverb bus); in a default build VIBRATO on FX2 passes the audio
through untouched.

![FX1 SETUP with VIBRATO: SHP.](../../img/vibrato/setup.png)

*FX1 SETUP with VIBRATO: SHP.*

## Operation

- DEP is the depth in cents (about 14 at the default 48, 25 at 64, 100 at
  127) and stays put as SPD changes, so a fast shallow shimmer and a slow
  wide wobble use the same DEP. The two extremes of the swing are exactly
  twice DEP apart: at 127, SQR trills a whole tone.
- At very slow rates and full depth the delay runs out of line and the depth
  is scaled down; the shape is kept.
- SLEW rounds the shape: on SQR it turns the trill into a glide between the
  two notes. It also softens the peak depth a little.
- WID pushes the right channel ahead by up to half a cycle; on RND it gives
  the right channel its own random pitches instead.
- MIX below 127 blends the dry back in. Because the vibrato's delay is very
  short, a 50/50 blend sweeps comb notches, closer to a flanger than a chorus.
- A SHP change fades the wet out, switches, and fades it back, so it never
  clicks. Fast knob moves and p-locks glide into the new setting: SPD and
  DEP follow the knob over about 20 ms, so an LFO on them faster than a few
  Hz is softened.

## Parameters

![VIBRATO main page: SPD, DEP, SLEW, WID, MIX.](../../img/vibrato/main.png)

*VIBRATO main page: SPD, DEP, SLEW, WID, MIX.*

| Knob | Range | Default | What it does |
|---|---|---|---|
| SPD | 0–127 | 80 (3.4 Hz) | Rate, 0.25 Hz to 15.5 Hz; every 21 steps is an octave |
| DEP | 0–127 | 48 (±14 cents) | Peak pitch deviation, up to ±100 cents |
| SLEW | 0–127 | 0 | Rounds the shape, up to a quarter-cycle smoothing |
| WID | 0–127 | 0 | Right channel's lead, up to half a cycle; on RND, how independent the right channel's random pitches are |
| MIX | 0–127 | 127 | Dry/wet; 127 is the vibrato alone, 0 passes the dry through exactly |
| SHP (setup) | SINE / TRI / SQR / RND | SINE | The pitch shape |
