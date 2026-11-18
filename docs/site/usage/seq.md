Use **SEQ** to fill a track with a Euclidean rhythm, add parameter locks
on their own rhythms, and generate melodies or MIDI chords. Hold
**`[TRACK]`** and press **`[PAGE]`** to open it for that track.

## Mental model

Start with when the track plays. Then give each parameter its own rhythm:
a filter can change on different steps from the notes, while volume
follows another rhythm.

Prepare a fill with the knobs, then press **`[YES]`** to write it into the
pattern. The grid previews your SEQ settings. Opening SEQ recalls those
settings rather than copying the pattern's existing trigs.

## Open and leave

Hold **`[TRACK]`** and press **`[PAGE]`** to open SEQ. Press another
**`[TRACK]`** to switch to that track, or **`[NO]`** to close.

**`[PAGE]`** still selects pattern pages. **`[FUNC]`** + **`[TRACK]`** still
mutes, and **`[CUE]`** + **`[TRACK]`** still cues a track.

## Lanes

Each track has one **TRIG** rhythm and a **PLCK** rhythm for each parameter.
Choose the parameter with **D** and the lane with **C**, **LANE**.

| Lane | What a fill changes |
|---|---|
| **TRIG** | Replaces the track's sample trigs or MIDI note trigs and the selected parameter's locks together. Other parameters keep their locks. |
| **PLCK** | Replaces only the selected parameter's locks. The track's trigs and other parameters keep their data. |

A TRIG fill also gives the selected parameter the TRIG rhythm. Switch to
PLCK to change that parameter's rhythm independently. Selecting another
parameter recalls its own PLCK rhythm and depth.

A PLCK fill clears the selected parameter's locks on steps outside its
rhythm, including steps with a sample or note trig. A hit without a sample
or note trig becomes a **trigless trig**, which triggers LFOs and FX
envelopes. When a TRIG fill removes a sample or note trig, locks for other
parameters remain on a trigless trig.

## Controls

| Keys | Action |
|---|---|
| **`[RIGHT]`** | Switch from Rhythm to Harmony. Select **SRC** / **PTCH** on audio or **NOTE** on MIDI with **D** first. |
| **`[LEFT]`** | Return from Harmony to Rhythm. |

### Rhythm

![SEQ Rhythm on an audio track.](../../img/seq/panel.png)

| Control | Effect |
|---|---|
| **A**, **PULS** | Choose how many hits to spread across the pattern length. |
| **B**, **ROT** | Shift those hits around the pattern. |
| **C**, **LANE** | Choose the TRIG rhythm or the selected parameter's PLCK rhythm. |
| **D**, page and parameter | Choose which parameter to write, such as **AMP** / **VOL**, **SRC** / **PTCH**, or MIDI **NOTE**. |
| **E**, **DPTH** | Set how far the locks vary from the Part value. At 0, a fill clears the selected parameter's locks. |

For **AMP** / **VOL**, the Part volume is the ceiling, so the variation
makes quieter steps. Other parameters vary above and below their Part
values. Pitch uses the Harmony settings.

MIDI destinations include **NOTE**, **VEL**, **LEN**, LFO and ARP
parameters, pitch bend, channel pressure, and **CC1** through **CC10**.

### Harmony

![SEQ Harmony on a MIDI track.](../../img/seq/midi-tonal.png)

Set the Part's pitch first, select **PTCH** or **NOTE** on Rhythm, raise
**DPTH** above 0, then press **`[RIGHT]`**.

| Control | Effect |
|---|---|
| **A**, **SCAL** | Choose MAJ, MIN, PENT, DOR, PHR, MIX, WHOL or CHRO. |
| **B**, **ROOT** | Choose the scale's root note. |
| **C**, **VOIC** | On MIDI tracks, choose one to four notes per hit. |
| **D**, **RANG** | Set the pitch span above and below the Part pitch, in semitones. At 0, use the Part pitch. |
| **E**, **PHRS** | UP rises, DOWN falls, ALT and TRI move back and forth, and WAVE picks pitches randomly. |
| **F**, **CHRD** | On MIDI tracks, choose the chord shape and inversion. |

On audio tracks, **DPTH** narrows pitch variation within **RANG**. On MIDI
tracks, **RANG** sets the melody's pitch span. SEQ's **SCAL** and **ROOT**
are independent of the PROJECT SCALE QUANTIZER.

## Writing the pattern

Press **`[YES]`** to fill the selected lane. Each fill writes locks using
the current Part values. Changing the Part later leaves those locks at
their written values. Fill again to use the new Part values.

If the track already has trigs, changing TRIG **PULS**, **ROT** or tapping
**`[CUE]`** opens **"ARE YOU SURE?"**. Press **`[YES]`** to continue editing,
or **`[NO]`** to cancel. When the preview is ready, press **`[YES]`** again
to write. Confirming the dialog alone leaves the pattern untouched.

Tap **`[CUE]`** to scatter the current number of hits randomly on the
selected lane. Each tap chooses another arrangement. Press **`[YES]`** to
write it. Turning **PULS** returns to a Euclidean rhythm.

## Save your settings

Save the project to keep SEQ's rhythms, depths and Harmony settings with
the bank. Audio and MIDI tracks keep separate SEQ settings. Written trigs
and locks belong to the pattern.

## Clear data

![SEQ clear menu.](../../img/seq/clear.png)

Press **`[FUNC]`** + **`[BANK]`** while SEQ is open. Choose a row and press
**`[YES]`** to clear immediately and return to SEQ. **`[NO]`** cancels.

| Action | Result |
|---|---|
| **CLEAR DEST** | Clear the selected parameter's locks and reset its PLCK rhythm and depth. |
| **CLEAR ALL DEST** | Clear every parameter's locks and reset their PLCK rhythms and depths. Keep the track's trigs. |
| **CLEAR ALL+TRIGS** | Also clear the track's trigs. Reset TRIG **PULS** to 5 and **ROT** to 0. |

Clearing affects the selected track within the pattern length. Other
tracks and patterns keep their data.

To clear one destination's locks directly, select **PLCK** and the
parameter with **D**, set **PULS** to 0, then press **`[YES]`**. Sample
trigs and other parameters stay. Empty trigless trigs are removed.

![PLCK PULS 0 clears PTCH while preserving sample trigs and other parameters.](../../img/seq/clear-dest.png)

## Examples

The diagrams use audio tracks. Black marks a parameter lock on a sample
trig; hatching marks a trigless trig. Use the same procedures on MIDI
tracks for note trigs and MIDI parameters.

### Place sample trigs

On an empty 16-step pattern, choose **LANE** = **TRIG**. Select **SRC** /
**PTCH** with **D**, leave **DPTH** at 0, set **PULS** to 5, then press
**`[YES]`**. You get five evenly spread sample trigs. Change **ROT** to
shift them against the other tracks. At **DPTH** 0, the fill also clears
existing PTCH locks.

![TRIG with DPTH 0 places sample trigs and clears PTCH.](../../img/seq/notes-only.png)

### Add volume changes on another rhythm

Set **LANE** to **PLCK**, choose **AMP** / **VOL** with **D**, then set
**PULS**, **ROT** and **DPTH**. Press **`[YES]`**. The sample trigs keep
their rhythm while volume follows its own.

![PLCK writes VOL while preserving sample trigs and PTCH.](../../img/seq/stack-vol.png)

### Change the trig rhythm and keep other locks

Select **TRIG** and **SRC** / **PTCH**, change **PULS** or **ROT**, then
press **`[YES]`**. The sample trigs and PTCH locks follow the new rhythm.
Volume locks remain on their previous steps.

![TRIG reshapes PTCH while preserving VOL.](../../img/seq/trig-reshape.png)

### Rewrite one parameter's locks

Select **PLCK** and **SRC** / **PTCH**, change **ROT**, then press
**`[YES]`**. PTCH locks move to the PLCK hits and clear on its misses,
including steps that still have sample trigs.

![PLCK rewrites PTCH while preserving sample trigs and other parameters.](../../img/seq/plck-overwrite.png)

### Write MIDI chords

Set the MIDI track's output channel in **NOTE SETUP**, opened with
**`[FUNC]`** + **`[SRC]`** or a double-tap of **`[SRC]`**. Then:

1. Set the MIDI Part's **NOTE** to C3.
2. Open SEQ, choose **LANE** = **TRIG** and **NOTE** with **D**, then set
   **PULS** and a nonzero **DPTH**.
3. Press **`[RIGHT]`**. Set **SCAL** to MAJ, **ROOT** to C, **RANG** to 0,
   **VOIC** to 3 and **CHRD** to MAJ0.
4. Press **`[YES]`** to write C3, E3 and G3 on each hit.

Set **VOIC** to 1 and fill again to replace the chords with single notes.
Reducing **VOIC** clears unused additional note locks on the fill's hits.
Enable the track's MIDI arpeggiator to arpeggiate the generated chords.
