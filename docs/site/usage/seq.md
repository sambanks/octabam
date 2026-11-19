![SEQ Rhythm on an audio track.](../../img/seq/panel.png)

Use **SEQ** to fill an audio or MIDI track's pattern with a Euclidean
rhythm, add parameter locks on their own rhythms, and generate melodies or
MIDI chords. On **TRIG**, a fill writes sample or note trigs and the
selected destination's locks together. On **PLCK**, it rewrites only that
destination and leaves the track trigs alone.

**PULS** sets the hit count, **ROT** shifts the hits, and **DPTH** controls
how far locks vary from the Part value. Press **`[YES]`** to write the
preview. Each destination keeps its own PLCK rhythm, so its locks can land
independently of the track trigs. SEQ settings save with the **project** and
bank; audio and MIDI tracks keep separate settings. Hold **`[TRACK]`** and
press **`[PAGE]`** to open SEQ for that track.

## Mental model

Each track has one TRIG rhythm and a separate PLCK rhythm for each
destination.

Audio sample trigs play the machine. MIDI note trigs send notes. Each
destination's PLCK rhythm controls which steps write its locks. These
rhythms can line up or land on different steps.

Choose **TRIG** to fill the sample or note rhythm. Choose **PLCK** to fill
one destination's rhythm. A **TRIG** fill also writes locks for the selected
destination; a **PLCK** fill rewrites only that destination. Other
destinations keep their locks.

The grid previews SEQ's current settings; it does not show the pattern's
existing trigs. Opening SEQ or switching tracks loads saved settings but
does not read live trigs. Press **`[YES]`** to write the preview to the
pattern.

## Open and leave

| Gesture | Result |
|---|---|
| **`[TRACK]`** + **`[PAGE]`** | Open SEQ on that track |
| **`[NO]`** | Close the window |
| Bare **`[PAGE]`** | Stock pattern pages / step banks; SEQ stays open |
| Another **`[TRACK]`** while open | Switch SEQ to that track |
| Double-tap **`[TRACK]`** | Stock **QUICK ASSIGN** on audio tracks; stock behavior on MIDI tracks |
| **`[FUNC]`** + **`[TRACK]`** | Stock mute |
| **`[TRACK]`** + **`[PLAY]`** / **`[STOP]`** / **`[BANK]`** | Stock preview / stop / audio editor |
| **`[CUE]`** + **`[TRACK]`** | Stock cue that track |
| Bare **`[CUE]`** (tap) | Random **PULS** hits on the focused lane |
| **`[FUNC]`** + **`[BANK]`** | Open the clear menu |

## Lanes

On each track SEQ keeps:

1. **One TRIG lane.** Where audio **sample trigs** or MIDI **note trigs** land.
2. **One PLCK lane per destination.** Knob **D** picks the destination
   (**AMP** / **VOL**, **SRC** / **PTCH**, or a MIDI parameter). That destination keeps its
   own **PULS**, **ROT**, **DPTH**, and random step selection on the track.

**LANE** (**C**) chooses which lane **A** / **B** and the step grid edit.
Scroll **D** on **PLCK** to load that destination's **PULS** / **ROT** into
**A** / **B**.

| **LANE** | What you edit | What **`[YES]`** does |
|---|---|---|
| **TRIG** | Sample-trig or note-trig rhythm | Rewrites the track trigs. Places or clears locks for **only the current destination** on those steps. Copies that destination's PLCK **PULS** / **ROT** to match. |
| **PLCK** | That destination's lock rhythm | Leaves track trigs alone. Rewrites **only this destination**. Misses clear it even on steps with a sample or note trig. Hits without a track trig become **trigless trigs**. |

On audio tracks, a trigless trig can trigger LFOs and FX envelopes without
playing a sample.

**D** / **E** stay live on **`[YES]`** even when **LANE** is **TRIG**.

## Controls

SEQ has two control pages. **`[RIGHT]`** opens Harmony when **D** is set to
audio **SRC** / **PTCH** or MIDI **NOTE**. **`[LEFT]`** returns to Rhythm.
The step grid and **LEN** stay visible on both pages.

### Rhythm

| Knob | Label | Role |
|---|---|---|
| **A** | **PULS** | Hit count of the focused lane |
| **B** | **ROT** | Rotation of the focused lane |
| **C** | **LANE** | **TRIG** or **PLCK** |
| **D** | Page and parameter | Choose the lock destination. Audio choices include **AMP** / **VOL**, **SRC** / **PTCH**, and CX OSC controls. MIDI choices include **NOTE**, **VEL**, **LEN**, LFO and ARP parameters, pitch bend, channel pressure, and **CC1** through **CC10**. |
| **E** | **DPTH** | Set lock variation. At 0, the fill clears this destination's locks. **AMP** / **VOL** varies only below the Part value; audio **PTCH** and MIDI **NOTE** follow Harmony. Other destinations vary above and below their Part values. |
| **F** | | Empty |

**LEN** shows the active **pattern** length.

Tap **`[CUE]`** and release without **`[TRACK]`** to keep the **PULS** hit
count and choose its steps randomly on the focused lane. Changing **PULS**
returns to the Euclidean pattern.

### Harmony

#### Audio tracks

![SEQ Harmony on an audio track.](../../img/seq/tonal.png)

On audio tracks, Harmony controls the **SRC** / **PTCH** destination.
**SCAL** and **ROOT** set the scale for generated pitch locks. **RANG**
sets their pitch span around the Part's **PLAYBACK PTCH**. At **RANG** 0,
fills use the Part pitch.

On audio tracks, **C** and **F** are blank. **PHRS** does not affect audio
PTCH fills.

#### MIDI tracks

![SEQ Harmony on a MIDI track.](../../img/seq/midi-tonal.png)

On MIDI tracks, **A** **SCAL** chooses MAJ, MIN, PENT, DOR, PHR, MIX,
WHOL or CHRO. **B** **ROOT** chooses C through B. **C** **VOIC** chooses
one to four notes. **D** **RANG** sets the pitch span around the Part's
**NOTE**. **E** **PHRS** chooses UP, DOWN, ALT, TRI or WAVE. **F** **CHRD**
chooses a chord shape and inversion.

SEQ's **SCAL** and **ROOT** are independent of the PROJECT SCALE
QUANTIZER on both audio and MIDI tracks.

## Writing the pattern

Opening SEQ or switching tracks loads that track's saved settings. The grid
previews those settings; it does not show existing pattern trigs. Press
**`[YES]`** to write the preview to the pattern.

Each fill writes lock values from the current Part. Changing the Part later
leaves written locks unchanged; fill again to use the new Part values.

**`[YES]`** overwrites from **PULS** / **ROT**, or from the random step
selection made with **`[CUE]`**.

**TRIG lane, sample trigs already present.** Changing **PULS** / **ROT** /
**`[CUE]`** opens **"ARE YOU SURE?"** with
**`"EXISTING TRIGS IN THE PATTERN"`** /
**`"WILL BE CLEARED ON NEXT FILL"`**. Dialog **`[YES]`** only unlocks the
knobs. Press **`[YES]`** again to write the pattern.

**TRIG lane, note trigs already present.** Changing **PULS** / **ROT** /
**`[CUE]`** opens the same dialog. The first **`[YES]`** applies the pending
change to the preview and unlocks editing. Press **`[YES]`** again to write.
**`[NO]`** cancels the pending change.

**`[CUE]`** tap (release with no **`[TRACK]`**). Keeps **PULS** as the hit
count and picks *which* steps are on at random on the focused lane.
**`[CUE]`** + **`[TRACK]`** is stock cue. Editing **PULS** after a random
tap returns to Euclidean.

**TRIG fill.** Audio sample trigs or MIDI note trigs follow the TRIG lane.
Locks for the selected destination land on those steps. At **DPTH** 0, the
fill clears that destination's locks. Other destination locks stay. If a
step loses its track trig but keeps another destination's lock, it becomes
a **trigless trig**.

**PLCK fill.** Track trigs stay. The selected destination clears on every
miss, including on steps with a sample or note trig, then writes on PLCK
hits. **PULS 0** clears this destination across the pattern. Empty
trigless trigs drop when nothing else remains on them.

## Clear data

![SEQ clear menu.](../../img/seq/clear.png)

To clear one destination's locks, set **LANE** to **PLCK**, set **PULS**
to 0, then press **`[YES]`**. Track trigs and other destinations stay.
Empty **trigless trigs** drop when nothing else remains on the step.

![PLCK PULS 0 clears PTCH; sample trigs and other destinations stay.](../../img/seq/clear-dest.png)

Use the menu to clear existing locks or trigs without writing a new fill.

While SEQ is open, press **`[FUNC]`** + **`[BANK]`** to open the clear
menu. Choose a row and press **`[YES]`** once. That row clears and resets
immediately; no second SEQ **`[YES]`** is needed. SEQ returns afterward.

| Row | What clears |
|---|---|
| **CLEAR DEST** | Clear the selected destination's locks. Reset its **DPTH**, PLCK **PULS** / **ROT**, and random step selection; keep track trigs. |
| **CLEAR ALL DEST** | Clear every SEQ destination's locks on this track. Reset each destination's **DPTH**, PLCK **PULS** / **ROT**, and random step selection; keep track trigs. |
| **CLEAR ALL+TRIGS** | Clear all destinations and their settings, plus audio sample trigs or MIDI note trigs. Reset TRIG **PULS** to 5 and **ROT** to 0. |

These clears affect only the selected track within the current pattern
length. Other tracks and patterns keep their data.

The first two rows keep track trigs. Steps with no track trig or remaining
locks become empty. Press **`[NO]`** to cancel and return to SEQ. Press
**`[FUNC]`** + **`[BANK]`** again to close the menu.

## Examples

In the figures, black marks a lock on a sample trig, hatching marks a
**trigless trig**, and white marks no lock.

### Place sample trigs

On an empty track, set **LANE** to **TRIG**, choose **SRC** / **PTCH** with
**D**, leave **DPTH** at 0, set **PULS**, then press **`[YES]`**. Sample
trigs land and PTCH locks clear.

![TRIG DPTH 0 writes sample trigs and clears PTCH.](../../img/seq/notes-only.png)

### Lock pitch on those trigs

Set **LANE** to **TRIG**, choose **SRC** / **PTCH**, set **PULS** / **ROT**
and a non-zero **DPTH**, then press **`[YES]`**. PTCH locks land on the new
sample trigs. The PTCH PLCK **PULS** / **ROT** match the TRIG rhythm.

### Add volume locks on another rhythm

Set **LANE** to **PLCK**, choose **AMP** / **VOL**, set a different
**PULS** / **ROT**, then press **`[YES]`**. VOL follows its own PLCK rhythm.
Sample trigs and PTCH locks stay where they are.

![PLCK writes only VOL; sample trigs and PTCH stay.](../../img/seq/stack-vol.png)

### Change the sample-trig rhythm

With PTCH and VOL locks on the pattern, set **LANE** to **TRIG**, choose
**SRC** / **PTCH**, change **PULS**, then press **`[YES]`**. PTCH follows
the new sample trigs. VOL locks stay; steps that lose a sample trig become
**trigless trigs** if another lock remains.

![TRIG reshapes PTCH while VOL survives as trigless trigs.](../../img/seq/trig-reshape.png)

### Rewrite one destination's locks

Set **LANE** to **PLCK**, choose **SRC** / **PTCH**, change **ROT**, then
press **`[YES]`**. PTCH clears on every PLCK miss, including on sample
trigs. Other destinations stay.

![PLCK rewrites PTCH while preserving sample trigs and other destinations.](../../img/seq/plck-overwrite.png)

### Place random trigs

Focus **TRIG** or **PLCK**, set **PULS** to the hit count, tap **`[CUE]`**
to choose those steps at random, then press **`[YES]`** to write.

### Write MIDI chords

Set the MIDI track's output channel in **NOTE SETUP**, opened with
**`[FUNC]`** + **`[SRC]`** or a double-tap of **`[SRC]`**. Set the Part's
**NOTE** to C3. In SEQ, select **TRIG**, choose **NOTE** with **D**, and set
**PULS** and a non-zero **DPTH**. Press **`[RIGHT]`**, choose MAJ for
**SCAL**, C for **ROOT**, set **RANG** to 0, **VOIC** to 3 and **CHRD** to
MAJ0. Press **`[YES]`** to write C3, E3 and G3 on each hit.

Set **VOIC** to 1 and fill again to write single notes and clear unused
extra-voice locks. USB MIDI output is available when the remix includes
USB MIDI and the Octatrack is outside USB DISK MODE.
