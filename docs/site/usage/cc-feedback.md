This module transmits a MIDI CC whenever any live knob value changes, regardless of what triggered the change, so external MIDI controllers (such as a BCR2000's LED rings) stay in sync with the Octatrack. Stock OS only sends page-1 CCs when you turn a front-panel encoder, leaving external controllers out of sync after a pattern or Part change, project load, MODE DEFAULTS reset, incoming CC, or page-2 adjustment.

## Operation

Connect the Octatrack's MIDI OUT to your controller's MIDI IN, and connect the controller's MIDI OUT back to the Octatrack's MIDI IN. With AUDIO CC OUT enabled, switching banks or patterns transmits the updated values paced at one message per UI tick, so a full bank change updates the controller over roughly three seconds instead of a single burst.

## Other synths on the MIDI out

CC FEEDBACK sends messages on every audio track's MIDI channel, and loading a project transmits the loaded Part's knob values. Any synthesizer listening on one of those channels will interpret those CCs as parameter changes. Assign external synths to MIDI channels not used by audio tracks, or set AUDIO CC OUT to INT when no controller needs feedback.

## The CC numbers

| Knob | CC |
|---|---|
| PLAYBACK page 1 | 16–21 |
| AMP page 1 | 22–27 |
| LFO page 1 | 28–33 |
| FX1 page 1 | 34–39 |
| FX2 page 1 | 40–45 |
| FX1 page 2 | 108–111, 14, 15 |
| FX2 page 2 | 102–107 |

Page 2 parameters use the CC numbers defined by CC MAP.

The following parameters are not transmitted: LEVEL (CC 46), AMP VOL outside the AMP page, MUTE and SOLO (CC 49 and 50), the crossfader (CC 48), and PLAYBACK and AMP page 2 (which have no assigned CC numbers).
