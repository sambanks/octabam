MIDI Follow lets a MIDI track play another track's notes at its own rhythm,
velocity and note length. It places the source's native N1–4 pitches in the
follower's register, then applies TRAN and the inherited source KEY. Several tracks
can follow one source; chains resolve to their final source.

## How to Use It

1. Program notes on a source MIDI track and trigs on a follower track.
2. On the follower, open **NOTE SETUP** with **FUNC + SRC**.
3. Turn **D: RFOL** to the source track, then press D to open **FOLLOW**.
4. Set **REG** to FIXED (pitch class in **OCT**), GRAV (nearby notes around
   **OCT**), or SOURCE (source octave plus **OFFS** of −2 to +2).
5. Set **UPDT** to TRIG for changes at the follower's next trig, or LIVE to
   shift held notes when the source root changes.

The follower's **TRAN** adds a semitone offset after register placement;
the inherited KEY then corrects each note to the scale, as in stock. Its stored N2–4 do not add notes: when the source has N2–4, those
source voices are followed even if the follower's own slots are empty. A
source rest retains the last notes. Source mute silences its output while
allowing its notes to drive followers. Give source and follower separate MIDI
channels while checking the result.

The source's scale and transpose are applied before Follow captures its notes.
The follower also inherits the source's KEY for correction after its own TRAN.
Its KEY display shows the source setting and cannot be edited while following.
KEY OFF leaves transposition chromatic. For example, C with TRAN +1 gives C♯
with KEY OFF, but C with KEY C major. Stock major/minor scales work with
Follow alone; MIDI Scales adds more choices. The follower's saved KEY returns
when RFOL is switched OFF.

## Storage and compatibility

RFOL, register choices and UPDT are saved in each Part. Fresh Parts default
to RFOL OFF, FIXED octave 3 and TRIG. MIDI Follow requires **STORE** and **EVENTS**.

Stock 1.40C preserves the source-track number but resets Follow's register and
update settings when saving the bank. Returning to Follow after that save
uses FIXED octave 0 and TRIG, with SOURCE offset reset to −2 octaves. Keep a
separate project copy before saving in stock firmware.

## Testing status

The current revision has emulator coverage. Limited Octatrack MKII tests used
MFOL29U / BUILD FA (29 October 2026); the current revision has not been tested
on hardware. USB MIDI captures confirmed four-note
following and clean releases, including STOP during held chords. Part save/reload
and saved OCT 4 surviving a power-cycle also passed. MKI, DIN timing and sustained
maximum-load testing remain unverified.
