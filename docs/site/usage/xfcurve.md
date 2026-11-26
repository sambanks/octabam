XFCURVE changes the response curve of the crossfader, controlling how quickly
scene locks move as you push the fader (stock is LINEAR). Choose the curve
under **PROJ > BRAIN > SETTINGS > CURVE**; one curve setting applies to every
project on the card.

## Operation

The curve applies to everything the crossfader moves on audio tracks: page-1
scene locks, XVOL, STRT/LEN/RATE morphing, SCENES P2 page-2 locks, and MORPH
tracks. A new CURVE takes effect the next time you move the crossfader.

| CURVE | What the fader does |
|---|---|
| LINEAR | stock |
| S SOFT, S-CURVE, S FIRM, S HARD | holds near both scenes and moves in the middle; firmer down the list |
| INV SOFT, INV-CURVE, INV FIRM, INV HARD | the reverse: leaves each scene quickly and gives fine control around the middle |
| CUT | a scene switch in the middle of the fader, with a short blend |
| CUT A, CUT B | one scene everywhere except the last few steps at the A (or B) end: a momentary, scratch-style cut |
| SLOW A, SLOW B | fine control near scene A (or B) |

**Example: a scratch cut.** Lock a track's XVOL off in scene A and on in scene
B, select CUT A, and flick the crossfader into and out of the A end. The track
cuts out only at the extreme end, while tracks without scene locks continue
playing underneath.

- MIDI tracks keep the stock linear crossfade because MIDI SCENES mixes them
  separately.
- The strongest inverse curves (INV FIRM and INV HARD) jump a long way on the
  first step off either end.
- Select parameters still switch at the midpoint of the blend, matching stock
  behavior.
