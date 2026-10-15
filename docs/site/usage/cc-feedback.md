## What it does

The OT transmits a CC for every live knob byte that changes, whatever
changed it, so a controller's encoders (a BCR2000's LED rings) follow
the unit. Stock sends a page-1 knob's CC on a panel turn only; after a
pattern or Part change, a project load, MODE DEFAULTS, an incoming CC or
a page-2 knob turn the controller shows stale values.

## How to check

Connect the controller: OT MIDI OUT to its MIDI IN, and its output back
to the OT's MIDI IN for the rings to follow. With AUDIO CC OUT on, change
a bank or pattern: the new values arrive paced at one message per UI
tick, so a bank change reaches the controller over about three seconds
instead of one burst.

## The CC numbers

| knob | CC |
|---|---|
| PLAYBACK page 1 | 16–21 |
| AMP page 1 | 22–27 |
| LFO page 1 | 28–33 |
| FX1 page 1 | 34–39 |
| FX2 page 1 | 40–45 |
| FX1 page 2 | 68–73 |
| FX2 page 2 | 62–67 |

Not sent: LEVEL (CC 46), AMP VOL outside the AMP page, MUTE and SOLO
(49/50), the crossfader (48), and PLAYBACK and AMP page 2 (no CC numbers
exist for them).
