# MIDI Scales

Adds Dorian, Phrygian, Lydian, Mixolydian and Locrian to the native MIDI
scale selector, alongside Major and natural Minor, in all 12 keys.

## Use

- Open MIDI **ARP SETUP** with **FUNC + AMP**.
- Press **F: KEY** to enable or bypass scale correction; turn F to choose a key
  and mode. Choices are grouped by key.
- KEY corrects sequencer/arp pitches. Added modes choose the nearest scale note,
  with ties going downward. It does not generate chords or affect audio tracks.

For example, C Dorian uses C, D, E-flat, F, G, A and B-flat.
KEY OFF bypasses correction. Original Major/Minor choices keep their native behavior.

## Storage and stock firmware

KEY is saved per MIDI track in the native Part, including Part copy and reload.
No separate settings file is needed.

Stock 1.40C loads extended KEY values as **B Minor**. Saving that bank on stock
replaces its extended mode with B Minor; simply loading does not rewrite all
other bank files. Keep a separate project copy, or choose OFF, Major or Minor
and save before returning to stock.

[Implementation, provenance and verification](DEVELOPMENT.md).
