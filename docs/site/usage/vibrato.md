VIBRATO modulates the track's pitch up and down, defaulting to 100% wet (MIX
127). The SHP parameter on the setup page chooses the waveform: SINE, TRI, SQR
(a two-note trill), or RND (a new random pitch every half cycle).

## Access

Select a track, press FX1, and choose VIBRATO. It can also run on FX2 when the
remix is built with its SLOTS setting set to FX1+FX2 (only available in remixes
without the delay and reverb bus); in a default build, VIBRATO on FX2 passes
audio through untouched.

![FX1 SETUP with VIBRATO: SHP.](../../img/vibrato/setup.png)

*FX1 SETUP with VIBRATO: SHP.*

## Operation

- DEP sets the modulation depth in cents (about 14 at the default 48, 25 at 64,
  and 100 at 127) and remains constant as SPD changes, so a fast shallow
  shimmer and a slow wide wobble use the same depth scale. The total swing
  between extremes is twice DEP: at 127, SQR trills a whole tone.
- At very slow rates and full depth, the delay buffer reaches its limit and the
  depth scales down while keeping the waveform shape.
- SLEW rounds the waveform edges, turning SQR from a trill into a glide between
  the two notes while slightly softening the peak depth.
- WID shifts the right channel ahead by up to half a cycle; in RND mode, it
  gives the right channel independent random pitches instead.
- Lowering MIX below 127 blends the dry signal back in. Because the vibrato
  delay is very short, a 50/50 blend produces sweeping comb notches, sounding
  closer to a flanger than a chorus.
- Changing SHP fades the wet signal out, switches shapes, and fades back in to
  avoid clicks. Fast knob moves and parameter locks glide into the new setting:
  SPD and DEP follow changes over about 20 ms, which softens LFO modulation
  faster than a few Hz.
- Holding FUNCTION while turning a knob jumps between useful settings, one
  per click, instead of sweeping to the ends: SPD steps through octaves
  (0.25, 0.5, 1, 2, 4, and 8 Hz); DEP through 1, 5, 10, 25, 50, 75, and 100
  cents (on SQR, 25 to 100 step a quarter tone at a time); WID in 30-degree
  steps; and SLEW and MIX in quarters. Each list also includes both ends of
  the knob.

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
