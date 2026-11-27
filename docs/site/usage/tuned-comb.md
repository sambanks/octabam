TUNED COMB is a stereo comb filter with stock COMB FILTER's page, whose note
stays in tune at any LP and FB. On the stock comb, closing LP pulls the note
flat, by up to a semitone; TUNED COMB plays the note PTCH and FINE name
whatever LP and FB do, so an LFO or a p-lock on LP never needs a matching
tuning lock.

FB sets a decay time rather than a raw feedback amount, so a note rings for
the same time high or low on the keyboard.

## Access

Select a track, press FX1, and choose TUNED COMB. It can also run on FX2 when
the remix is built with its SLOTS setting set to FX1+FX2 (only available in
remixes without the delay and reverb bus); in a default build, TUNED COMB on
FX2 passes audio through untouched. It is not included in the official
remixes; build the `tuned-comb` test remix to use it.

## Operation

- PTCH names the note, A#0 to A8. FINE detunes it by up to a semitone either
  way; 64 is in tune.
- LP closes the lowpass inside the loop, darkening the ring and shortening
  it, as on the stock comb, without changing the note.
- FB above 64 rings at the note. Below 64 the polarity flips and the note
  sounds an octave down, as on the stock comb. The further from 64, the
  longer the ring: about 0.05 s next to 64, up to 30 s at either end. 64 is
  no feedback. Very long decays are shorter on high notes (about 26 s at C3,
  6.6 s at C5, 1.6 s at C7).
- MIX blends the comb with the dry signal; 0 passes the input untouched and
  127 is the comb alone.
- LFOs on FINE, LP and FB sweep smoothly. When a knob moves, the comb settles
  on the new tuning within about a millisecond.
- Holding FUNCTION while turning a knob steps through stops one click at a
  time instead of jumping to the ends:
  - PTCH steps an octave, keeping the note's name.
  - FINE steps a quarter tone: -100, -50, 0, +50 and +98 cents.
  - LP steps through 81 Hz, 125, 250 and 500 Hz, 1, 2, 4 and 8 kHz, and open.
  - FB steps through decay times of 0.5, 1, 2, 5, 10 and 30 s on each side
    of 64, and 64 itself (no feedback).
  - MIX steps in quarters.
- TUNED COMB uses about 4.5 % of a core held and about 6 % with its knobs
  moving, against 2.7 % for the stock comb, so eight instances fit on one
  core with room to spare.

## Parameters

| Page | Knob | Range | What it does |
|---|---|---|---|
| 1 | PTCH | A#0..A8 | The note, in tune at any LP and FB (default C3) |
| 1 | FINE | 0..127 | Fine tune, ±1 semitone; 64 is in tune |
| 1 | LP | 0..127 | The lowpass in the loop: 81 Hz at 0, one octave every 16 steps, open at 127 |
| 1 | FB | 0..127 | The decay time, 0.05 s next to 64 to 30 s at the ends; below 64 the note drops an octave; 64 is no feedback (default 96) |
| 1 | MIX | 0..127 | Dry/wet; 127 is the comb alone, 0 an exact passthrough |
