MIDI Follow lets a MIDI track play another track's notes at its own rhythm,
velocity and note length. It uses the source's native N1–4 pitches and keeps
their intervals when placing them in the follower's register. Several tracks
can follow one source; chains resolve to their final source.

## How to Use It

1. Program notes on a source MIDI track and trigs on a follower track.
2. On the follower, open **NOTE SETUP** with **FUNC + SRC**.
3. Turn **D: RFOL** to the source track, then press D to open **FOLLOW**.
4. Set **REG** to FIXED (pitch class in **OCT**), GRAV (nearby notes around
   **OCT**), or SOURCE (source octave plus **OFFS** of −2 to +2).
5. Set **UPDT** to TRIG for changes at the follower's next trig, or LIVE to
   shift held notes when the source root changes.

The follower's **TRAN** adds a chromatic semitone offset after register
placement. Its stored N2–4 do not add notes: when the source has N2–4, those
source voices are followed even if the follower's own slots are empty. A
source rest retains the last notes. Source mute silences its output while
allowing its notes to drive followers. Give source and follower separate MIDI
channels while checking the result.

The source's scale and transpose are applied before Follow captures its notes.
Followers therefore share the source's pitch choices without copying its scale
setting. The follower's own TRAN is then applied as a chromatic offset.

## Storage and compatibility

RFOL, register choices and UPDT are saved in each Part. Fresh Parts default
to RFOL OFF, FIXED octave 3 and TRIG. MIDI Follow requires **MIDI Part State** and **EVENTS**.

Stock 1.40C preserves the source-track number but resets Follow's register and
update settings when saving the bank. Returning to Follow after that save
uses FIXED octave 0 and TRIG, with SOURCE offset reset to −2 octaves. Keep a
separate project copy before saving in stock firmware.

## Testing status

MIDI Follow has been tested in the emulator. **Hardware testing is still to
be done**, including physical MIDI output, timing and note releases.
