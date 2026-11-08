The crossfader's curve: how far each scene's locks move as you push the fader. Stock is LINEAR.
Choose the curve in **PROJ > BRAIN > SETTINGS > CURVE**; one curve for every project on the card.

## Operation

The curve applies to everything the crossfader moves on the audio tracks: page-1 scene locks, XVOL,
the STRT/LEN/RATE morph, SCENES P2's page-2 locks and MORPH's tracks. A new CURVE takes effect at the
next crossfader move.

| CURVE | What the fader does |
|---|---|
| LINEAR | stock |
| S SOFT, S-CURVE, S FIRM, S HARD | holds near both scenes and moves in the middle; firmer down the list |
| INV SOFT, INV-CURVE, INV FIRM, INV HARD | the reverse: leaves each scene quickly and gives fine control around the middle |
| CUT | a scene switch in the middle of the fader, with a short blend |
| CUT A, CUT B | one scene everywhere except the last few steps at the A (or B) end: a momentary, scratch-style cut |
| SLOW A, SLOW B | fine control near scene A (or B) |

**A scratch cut.** Lock a track's XVOL off in scene A and on in scene B, choose CUT A, and flick the
fader into and out of the A end: the track cuts out only at the end. Tracks with no scene locks keep
playing underneath.

- MIDI tracks keep the stock linear crossfade (MIDI SCENES mixes them itself).
- The strongest inverse curves (INV FIRM, INV HARD) move a long way on the first step off each end.
- Select parameters still switch where the blend crosses the middle, as stock.
