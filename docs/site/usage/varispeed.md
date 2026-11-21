Tempo-locked varispeed for STATIC and FLEX tracks. The sample plays dry,
tape-style: speed and pitch move together, locked to the project tempo.
Nothing is emulated and the DSP is stock.

## Access

SRC SETUP > TSTR gets a fifth position, VARI: `OFF AUTO NORM BEAT VARI`.

![SRC SETUP on a FLEX track: TSTR set to VARI.](../../img/varispeed/setup.png)

## Playback

A VARI track plays at (project BPM × p) / (sample BPM × q), exact in
integers, where p/q is the QUAN ratio below. Above 2× it folds down an
octave. RATE still applies.

On AUTO, a sample whose TIMESTRETCH (audio editor > ATTR) is VARI plays
the same way.

A sample or project tempo outside 30–300 BPM plays as TSTR OFF.

A VARI note held over a Part switch keeps its speed until the track's
next trig.

## QUAN

On a VARI track the PTCH knob becomes QUAN, the ratio p/q: 1/2, 2/3, 3/4,
4/5, 1/1 (the default), 5/4, 4/3, 3/2 or 2/1. One detent moves one ratio.
The knob is drawn as a nine-position switch: 1/2 points left, 1/1 up and
2/1 right.

![The SRC page of a VARI track: PTCH is QUAN, here 3/2.](../../img/varispeed/quan.png)

Entering VARI, QUAN starts at 1/1, unless the track had another QUAN
when it last left VARI: then it comes back. Each Part keeps its own, and
a saved project keeps it. Leaving VARI gives PTCH back its value.

## Notes

- STATIC and FLEX only; PICKUP keeps its own TSTR.
- TSNS stays TSNS on a VARI track.
