**SEQ** is a track window for Euclidean **sample trigs**, MIDI **note
trigs** and **parameter locks**. Hold **`[TRACK]`** and press **`[PAGE]`**
to open it. The name comes from the SEQ submenu on Digitakt II and
Digitone II.

The window shows the title **SEQ**, the rings icon, a stock 3x2 DATA ENTRY
grid, a step grid (hollow = off, solid = on; up to 4 rows of 16 for length
64), and **LEN** with the **pattern** step count at the bottom right. The
top-right corner of the SEQ logo panel shows the active knob page, **1/2** or
**2/2**. Press **`[LEFT]`** or
**`[RIGHT]`** to change the knob page. The step grid remains visible.

It writes **pattern** sequencer data. SEQ settings save with the
**project** and bank. Audio tracks default to **AMP** / **VOL**. MIDI tracks
use note trigs and MIDI destinations with the same controls.

## Mental model

Think of the track as a trig rhythm with a separate rhythm for each
parameter. Audio-track TRIGs play samples. MIDI-track TRIGs send notes.
A destination's PLCK rhythm controls when its parameter lock applies.

Set the TRIG lane for the sample or note pattern. Set a PLCK lane to place
that destination's motion. The rhythms can line up or play different steps.
Other destinations stay as they are until you edit them.

Nothing hits the **pattern** until **`[YES]`**. Dial the shape, watch the
grid, then write.

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

## Lanes

On each track SEQ keeps:

1. **One TRIG lane.** Where audio **sample trigs** or MIDI **note trigs** land.
2. **One PLCK lane per destination.** Knob **D** picks the destination,
   such as **AMP** / **VOL** on audio tracks or **SRC** / **PTCH** on MIDI
   tracks. Each destination keeps its own **PULS**, **ROT**, **DPTH**, and
   random mask on the track.

**LANE** (**C**) chooses which lane **A** / **B** and the step grid edit.
Scroll **D** on **PLCK** to load that destination's **PULS** / **ROT** into
**A** / **B**.

| **LANE** | What you edit | What **`[YES]`** does |
|---|---|---|
| **TRIG** | Audio sample-trig or MIDI note-trig rhythm | Rewrites that track's trigs. Places or clears locks for **only the current destination** on those steps. Copies that destination's PLCK **PULS** / **ROT** to match. |
| **PLCK** | That destination's lock rhythm | Leaves track trigs alone. Rewrites **only this destination**. Misses clear it even on trig steps. Hits without a track trig become **trigless trigs**. |

**D** / **E** stay live on **`[YES]`** even when **LANE** is **TRIG**.

## Knob pages

Page **1/2** keeps the rhythm controls. Page **2/2** changes only the knob
assignments; the rhythm grid remains visible and unchanged.

### Page 1/2

Same 3x2 cells as stock SETUP pages:

| Knob | Label | Role |
|---|---|---|
| **A** | **PULS** | Hit count of the focused lane |
| **B** | **ROT** | Rotation of the focused lane |
| **C** | **LANE** | **TRIG** or **PLCK** |
| **D** | page + param | Lock destination. Two lines, LFO SETUP **PMTR** style (**AMP** / **VOL**, **SRC** / **PTCH**, …). **AMP** / **XVOL** is skipped. On **CX OSC** also **SRC** / **CAR** **MOD** **SYMM** **FDBK** **PWM** |
| **E** | **DPTH** | How far locks swing from the Part value. **0** clears that destination. **SRC** / **PTCH** stays in scale around the Part's **PLAYBACK** **PTCH**. **AMP** / **VOL** sits at or below the Part's **AMP** **VOL**. Anything else swings ± **DPTH** |
| **F** | | Empty |

### Page 2/2

The second page controls melody and harmony for both audio and MIDI tracks.
SEQ keeps these scale settings separate from the PROJECT SCALE QUANTIZER.

**LEN** shows the active **pattern** length.

| Knob | Label | Role |
|---|---|---|
| **A** | **SCAL** | MAJ, MIN, PENT, DOR, PHR, MIX, WHOL or CHRO |
| **B** | **ROOT** | Root note C through B |
| **C** | **MODE** | MIDI: MELO, CHRD or ARP. Audio: MELO or ARP |
| **D** | **RANG** | Pitch radius around the Part pitch, from unison to four octaves |
| **E** | **PHRS** | UP, DOWN, ALT, TRI or WAVE; shapes MIDI melody/ARP and audio melody |
| **F** | **HARM** / **INTV** | MIDI HARM enables the seventh chord tone. Audio INTV transposes its PTCH line by a scale degree, unison through seventh. |

Audio INTV applies when RANG is above zero. At RANG 0, PTCH follows the Part
value. Set different intervals on separate audio tracks to play a harmony.
The tonal page has not yet been confirmed on hardware.

In MIDI ARP mode, notes walk the selected scale from the Part NOTE; PHRS
sets the direction or pattern. Audio ARP mode walks upward through the
available scale pitches. RANG sets the pitch radius for melody generation
and audio PTCH variation; MIDI ARP uses scale degrees from the Part NOTE.

## Writing the pattern

Open and track-switch load the track's saved SEQ settings into the knobs
and grid. The grid previews those settings. It does not read existing trigs
back from the **pattern**. Nothing hits the **pattern** until **`[YES]`**.

**`[YES]`** overwrites from **PULS** / **ROT**, or from a free **`[CUE]`**
mask.

**Audio TRIG lane, sample trigs already present.** Changing **PULS** /
**ROT** / **`[CUE]`** first opens stock **`"ARE YOU SURE?"`** with
**`"EXISTING TRIGS IN THE PATTERN"`** /
**`"WILL BE CLEARED ON NEXT FILL"`**. Dialog **`[YES]`** unlocks the
knobs. A second **`[YES]`** writes the fill.

**MIDI TRIG lane, note trigs already present.** Changing **PULS** / **ROT** /
**`[CUE]`** opens the same confirmation. The first **`[YES]`** applies the
pending change to the preview and unlocks editing. Press **`[YES]`** again
to write the fill. **`[NO]`** cancels the pending edit.

**`[CUE]`** tap (release with no **`[TRACK]`**). Keeps **PULS** as the hit
count and picks *which* steps are on at random on the focused lane.
**`[CUE]`** + **`[TRACK]`** is stock cue. Editing **PULS** after a random
tap returns to Euclidean.

**TRIG write.** On audio tracks, sample trigs follow the TRIG lane. On
MIDI tracks, note trigs follow it. The selected destination is written on
those steps (**DPTH** 0 clears its locks). Other destinations stay. If a
step loses its track trig but still holds another destination, it becomes a
**trigless trig**.

**PLCK write.** Track trigs stay. The selected destination clears on every
miss, including on trig steps, then writes on PLCK hits. **PULS 0** clears
that destination across the pattern. Empty trigless trigs drop when nothing
else remains on them.

## Clear SEQ data

With SEQ open, press **`[FUNC]`** + **`[BANK]`** to open the clear menu.
Choose a row and press **`[YES]`** to clear it. **`[NO]`** cancels and
returns to SEQ.

| Row | Result on the focused track |
|---|---|
| **CLEAR DEST** | Clears the selected destination's locks and resets its **DPTH**, **PULS** and **ROT**. Other destinations and track trigs stay. |
| **CLEAR ALL DEST** | Clears all destinations and their settings. Track trigs stay. |
| **CLEAR ALL+TRIGS** | Clears all destinations and track trigs. TRIG **PULS** returns to 5 and **ROT** to 0. |

The clear applies within **LEN** on the focused track. On audio tracks it
clears sample trigs. On MIDI tracks it clears note trigs. Other tracks and
patterns keep their data.

## MIDI tracks

On MIDI tracks, **D** selects **NOTE**, **VEL**, **LEN**, **NOT2**, **NOT3**,
**NOT4**, LFO and ARP parameters, pitch bend, channel pressure, and **CC1**
through **CC10**. Each destination has its own **DPTH** and PLCK rhythm.
MIDI SEQ settings save separately from audio SEQ settings.

**NOTE** is the main pitch. **NOT2**, **NOT3** and **NOT4** add voices at
semitone offsets from NOTE. **DPTH** varies each destination around its value
in the playing Part when you write. The resulting locks store those values.
Changing the Part later does not change existing locks. Set the Part value
first, then write each destination that should use it.

To send the MIDI track to a device, set its channel in **NOTE SETUP**, opened
by double-tapping **`[SRC]`** or pressing **`[FUNC]`** + **`[SRC]`**. USB
output is available when the remix includes USB MIDI and the Octatrack is
outside USB DISK MODE.

## Examples

These procedures apply to audio and MIDI tracks. Substitute note trigs for
sample trigs on a MIDI track, and choose a MIDI destination from **D**.
Figures show audio-track labels. Black means a lock on a track trig; hatch
means a **trigless trig**; white means no lock.

### Write trigs and a destination together

On an empty track, choose **LANE** = **TRIG**, select a destination with
**D**, set **PULS** and **DPTH**, then press **`[YES]`**. The track trigs
follow the TRIG rhythm. Locks for the selected destination land on those
steps. The destination's PLCK **PULS** / **ROT** match the TRIG rhythm.
At **DPTH** 0, the fill clears that destination's locks.

![TRIG with DPTH 0 places sample trigs and clears PTCH on an audio track.](../../img/seq/notes-only.png)

### Add a destination on another rhythm

Choose **LANE** = **PLCK**, select a destination, then set a different
**PULS** / **ROT** and press **`[YES]`**. That destination follows its own
rhythm. The track's sample or note trigs and all other destinations stay.
Steps with a lock and no track trig become **trigless trigs**.

![PLCK writes only VOL; sample trigs and PTCH stay on this audio track.](../../img/seq/stack-vol.png)

### Change the track-trig rhythm

With locks on several destinations, change **PULS** / **ROT** in the TRIG
lane and press **`[YES]`**. The track's trigs follow the new rhythm. The
selected destination is rewritten on those steps. Other destination locks
stay, and become **trigless trigs** where the track trig is removed.

![TRIG reshapes PTCH while VOL stays on the audio track.](../../img/seq/trig-reshape.png)

### Rewrite one destination's locks

Choose **LANE** = **PLCK**, select the destination, change **ROT**, then
press **`[YES]`**. That destination clears on every PLCK miss, including
steps with a sample or note trig. It writes on PLCK hits, creating
**trigless trigs** where no track trig exists. Other destinations stay.

![PLCK clears PTCH on sample-trig misses; other destinations stay on this audio track.](../../img/seq/plck-overwrite.png)

### Clear one destination's locks

Set **LANE** = **PLCK**, select the destination, set **PULS** to 0, then
press **`[YES]`**. This clears that destination over the pattern length.
Track trigs and other destinations stay. Empty trigless trigs are removed.

![PLCK PULS 0 clears PTCH; sample trigs and other destinations stay on this audio track.](../../img/seq/clear-dest.png)

### Place random trigs

Focus **TRIG** or **PLCK**, set **PULS** to the hit count, then tap
**`[CUE]`** to choose that many random steps. Press **`[YES]`** to write.
On TRIG this randomizes sample trigs or note trigs. On PLCK it randomizes
the selected destination's locks.

### Write a MIDI chord

For voices centered on C3, E3 and G3, set the MIDI Part's **NOTE** to C3,
**NOT2** to +4 and **NOT3** to +7. In SEQ, choose **LANE** = **TRIG**,
**D** = **NOTE**, set **PULS** and a nonzero **DPTH**, then press **`[YES]`**.
This writes note trigs and NOTE locks. Select **NOT2**, set its **DPTH**
above 0, and press **`[YES]`** to write its locks on the same steps. Repeat
for **NOT3**. Each destination needs its own fill and nonzero **DPTH**.

Changing **D** alone does not write locks. If note trigs already exist,
changing TRIG **PULS**, **ROT** or tapping **`[CUE]`** opens the confirmation
described above. Confirm the preview, then press **`[YES]`** again to write.
