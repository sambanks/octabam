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
Follow alone; MIDI SCALES adds seven modes and SCALES offers all 52 scales. The follower's saved KEY returns
when RFOL is switched OFF.

## Share a progression with Harmony

In the **midi** remix, a Harmony source can drive a NOTE bass, CHORD stabs
and an arp, each with its own rhythm and register. Followers use the source's
resolved root and KEY, then choose their own Harmony chord quality and
voicing. They do not copy the source's generated chord voices. **TRIG** waits
for each follower's next trig; **LIVE** also moves held notes with the source.
**RFOL OFF** keeps a track independent, and Harmony works without Follow.
See the [four-track musical example](midi-harmony.md#arrange-a-song-with-the-midi-remix).

## Storage and compatibility

RFOL, register choices and UPDT are saved in each Part. Fresh Parts default
to RFOL OFF, FIXED octave 3 and TRIG. MIDI Follow requires **STORE** and **EVENTS**.

Stock 1.40C preserves the source-track number but resets Follow's register and
update settings when saving the bank. Returning to Follow after that save
uses FIXED octave 0 and TRIG, with SOURCE offset reset to −2 octaves. Keep a
separate project copy before saving in stock firmware.

## Testing status

MKII USB MIDI tests on 30 October 2026 passed ten minutes each with seven
four-note GRAV LIVE followers at 200 BPM / 1×, both sharing one source and
forming a chain. A five-minute run added eight looping FLEX tracks with
FILTER and PLATE REV; audio stayed continuous and the panel remained responsive.
STOP released all held follower notes. Earlier Part save/reload and power-cycle
checks also passed.

**Known limit:** eight MIDI tracks playing four-note chords on every sixteenth
at 300 BPM / 2× froze the unit with RFOL OFF on every track and Follow still
loaded. Avoid that load while the freeze remains unresolved. The
passing runs do not establish a safe maximum for all MIDI traffic or remix
combinations. MKI and DIN output/timing remain unverified.
