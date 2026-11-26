VARISPEED adds tempo-locked varispeed playback to STATIC and FLEX tracks. The
sample plays dry like tape, with speed and pitch moving together locked to the
project tempo. No tape effect is modeled, and the DSP code remains stock.

## Access

SRC SETUP > TSTR gains a fifth position, VARI: `OFF AUTO NORM BEAT VARI`.

![SRC SETUP on a FLEX track: TSTR set to VARI.](../../img/varispeed/setup.png)

## Playback

A VARI track plays at `(project BPM × p) / (sample BPM × q)` in exact integers,
where `p/q` is the QUAN ratio below. Playback speeds above 2× fold down an
octave, and RATE still applies.

On AUTO, any sample whose TIMESTRETCH attribute (audio editor > ATTR) is set to
VARI plays the same way.

If the sample or project tempo is outside 30–300 BPM, the track plays as if
TSTR were OFF.

## QUAN

On a VARI track, the PTCH knob becomes QUAN, setting the ratio `p/q`: 1/2, 2/3,
3/4, 4/5, 1/1 (the default), 5/4, 4/3, 3/2, or 2/1. One detent moves one ratio
step. The knob is drawn as a nine-position switch with 1/2 pointing left, 1/1
pointing up, and 2/1 pointing right.

![The SRC page of a VARI track: PTCH is QUAN, here 3/2.](../../img/varispeed/quan.png)

Switching away from VARI restores PTCH to its previous value.

## Notes

- Applies to STATIC and FLEX tracks only; PICKUP keeps its own TSTR behavior.
- TSNS remains TSNS on a VARI track.
