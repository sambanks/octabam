# MIDI Follow

Makes one MIDI track follow another track's notes while keeping its own
rhythm, velocity and note length. It follows the source's native N1–4 notes
and preserves their intervals in the follower's selected register.

## Use

1. On the follower, open **NOTE SETUP** with **FUNC + SRC**.
2. Turn **D: RFOL** from OFF to the source track, for example T1.
3. Program the source's notes and the follower's rhythm. Give them separate
   output channels; start with the follower's arp off.
4. Press D to open **FOLLOW**. A/B/C are **RFOL**, **REG**, **OCT/OFFS**;
   D is **UPDT**. E/F are unused.

| Control | Behavior |
| --- | --- |
| REG: FIXED | Uses the source pitch class in OCT 0–10; default octave 3. |
| REG: GRAV | Ignores source octave; balances small movements with a preference for OCT 0–10. Default octave 3. |
| REG: SOURCE | Uses the source's full root pitch, shifted by OFFS −2 to +2. Default 0. |
| UPDT: TRIG | Takes the latest logical source notes at the follower's next programmed note. |
| UPDT: LIVE | Also shifts held follower notes when the source root changes. |

Each mode remembers its own value in the same C control. FIXED is the default;
RFOL starts OFF and UPDT starts TRIG. Octave names use C0 = MIDI 0.
Use the follower's native **TRAN**, including parameter locks, for a semitone
offset after register selection. TRAN +7 is always seven semitones, not a scale degree.
Out-of-range roots are silent.

GRAV prefers the twelve notes C–B in the selected octave without a hard
register boundary. At OCT2, B2 → C can become B2 → C3 instead of jumping to
C2; a following F returns to F2. It can still make larger return jumps.
It follows the previous played root, before transposition. Additional chord
voices and repeated arp notes do not change that reference. The first root starts in the preferred octave (or
the closest valid octave for the partial OCT10). Transport start/resume,
Part replacement/change and source/register/home edits reset the reference;
ordinary pattern changes alone retain it.

## Musical behavior

- RFOL OFF uses native notes. Before a source root is available, playback is unchanged.
- The source supplies its NOTE and NOT2–4 pitches. The follower plays that set in its selected register, with its own
  TRAN. Its stored NOT2–4 do not add notes.
- LIVE shifts currently held notes when the source root moves. A change to
  native NOT2–4 with the same root takes effect at the follower's next trig.
- Several tracks can follow one source. Chains use the ultimate source and
  the final follower's settings; intermediate transpositions do not accumulate.
  The selector prevents self-following and cycles.
- Source rests retain the last root. Muting the source silences its output but
  lets its root progression continue driving followers.
- Same-tick source trigs are captured before followers play. An earlier
  microtimed follower trig uses the preceding root.

## Storage and stock firmware

RFOL, REG, all three remembered values and UPDT are native Part settings per track.
Runtime roots and held notes are not saved. Requires **MIDI Part State**;
Scales and KITS are optional. MIDI Follow cannot currently be combined
with **EUCLID**.

Stock 1.40C preserves the source-track number but resets the mode, response
and octave fields. After saving that bank on stock, Follow returns as **FIXED,
octave 0, TRIG**, with a remembered SOURCE offset of **-2 octaves**. Keep a
separate project copy to preserve these settings.

## Testing status

MIDI Follow has been tested in the emulator. **Hardware testing is still to
be done**, including physical MIDI output, timing and note releases on an
Octatrack MKI/MKII.

[Implementation and verification](DEVELOPMENT.md).
