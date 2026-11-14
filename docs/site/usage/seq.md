**SEQ** places Euclidean **sample trigs** and **parameter locks** on one
audio track. Named after the SEQ submenu on Digitakt II / Digitone II. On
Octatrack it is its own window on the track via **`[TRACK]`** + **`[PAGE]`**.
It is separate from the DSP **EUCLID** effect, and it leaves
`PROJECT > CONTROL > SEQUENCER` alone, so SCALE QUANTIZER stays beside it.

Hold a **`[TRACK]`** key and press **`[PAGE]`**. SEQ opens for that track:
title **SEQ**, the rings icon, a stock 3x2 DATA ENTRY grid, a step grid
(hollow = off, solid = on; up to 4 rows of 16 for length 64), and **LEN**
with the **pattern** step count at the bottom right.

It writes **pattern** sequencer data. Settings live in `euclid.work` and
save with the **project** / bank. Defaults: TRIG **PULS** 5, destination
**AMP** / **VOL**, **ROT** / **DPTH** / PLCK **PULS** 0, **LANE** = **TRIG**.

## Mental model

Think of the track as stacked rhythms, not one step grid.

**Sample trigs** are one rhythm: when the machine plays. Each **parameter
lock** destination is its own rhythm: when pitch moves, when volume ducks,
when a filter opens. Those rhythms live side by side on the same track.
They can line up, or they can disagree.

SEQ is how you paint those layers with Euclidean density and rotation.
Focus the sample-trig layer when you want hits. Focus a destination when
you want that parameter's motion. Other layers stay put until you choose
them.

Nothing hits the **pattern** until **`[YES]`**. Dial the shape, watch the
grid, then write.

## Open and leave

| Gesture | Result |
|---|---|
| **`[TRACK]`** + **`[PAGE]`** | Open SEQ on that track |
| **`[NO]`** | Close the window |
| Bare **`[PAGE]`** | Stock pattern pages / step banks; SEQ stays open |
| Another **`[TRACK]`** while open | Switch SEQ to that track |
| Double-tap **`[TRACK]`** | Stock **QUICK ASSIGN** |
| **`[FUNC]`** + **`[TRACK]`** | Stock mute |
| **`[TRACK]`** + **`[PLAY]`** / **`[STOP]`** / **`[BANK]`** | Stock preview / stop / audio editor |
| **`[CUE]`** + **`[TRACK]`** | Stock cue that track |
| Bare **`[CUE]`** (tap) | Random **PULS** hits on the focused lane |
| **`[FUNC]`** + **`[BANK]`** | Open the clear menu |

## Lanes

On each track SEQ keeps:

1. **One TRIG lane.** Where **sample trigs** land.
2. **One PLCK lane per destination.** Knob **D** picks the destination
   (**AMP** / **VOL**, **SRC** / **PTCH**, …). That destination keeps its
   own **PULS**, **ROT**, **DPTH**, and free mask on the track.

**LANE** (**C**) chooses which lane **A** / **B** and the step grid edit.
Scroll **D** on **PLCK** to load that destination's **PULS** / **ROT** into
**A** / **B**.

| **LANE** | What you edit | What **`[YES]`** does |
|---|---|---|
| **TRIG** | Sample-trig rhythm | Rewrites **sample trigs**. Places or clears locks for **only the current destination** on those steps. Copies that destination's PLCK **PULS** / **ROT** to match. |
| **PLCK** | That destination's lock rhythm | Leaves sample trigs alone. Rewrites **only this destination**. Misses clear it even on sample-trig steps. Hits without a sample trig become **trigless trigs**. |

**D** / **E** stay live on **`[YES]`** even when **LANE** is **TRIG**.

## Knobs

Same 3x2 cells as stock SETUP pages:

| Knob | Label | Role |
|---|---|---|
| **A** | **PULS** | Hit count of the focused lane |
| **B** | **ROT** | Rotation of the focused lane |
| **C** | **LANE** | **TRIG** or **PLCK** |
| **D** | page + param | Lock destination. Two lines, LFO SETUP **PMTR** style (**AMP** / **VOL**, **SRC** / **PTCH**, …). **AMP** / **XVOL** is skipped. On **CX OSC** also **SRC** / **CAR** **MOD** **SYMM** **FDBK** **PWM** |
| **E** | **DPTH** | How far locks swing from the Part value. **0** clears that destination. **SRC** / **PTCH** stays in scale around the Part's **PLAYBACK** **PTCH**. **AMP** / **VOL** sits at or below the Part's **AMP** **VOL**. Anything else swings ± **DPTH** |
| **F** | | Empty |

**LEN** shows the active **pattern** length.

For **SRC** / **PTCH**, **SCALE OFF** places the Part's **PLAYBACK PTCH**
on every hit. With **SCALE** enabled, **DPTH** spreads pitches within
that scale around the Part's pitch. **DPTH** 0 clears the pitch locks.

## Writing the pattern

Open and track-switch load the track's saved SEQ settings into the knobs
and grid. The grid is write-only: it shows those settings, and never reads
live sample trigs back from the **pattern**. Nothing hits the **pattern**
until **`[YES]`**.

**`[YES]`** overwrites from **PULS** / **ROT**, or from a free **`[CUE]`**
mask.

**TRIG lane, sample trigs already present.** Changing **PULS** / **ROT** /
**`[CUE]`** first opens stock **`"ARE YOU SURE?"`** with
**`"EXISTING TRIGS IN THE PATTERN"`** /
**`"WILL BE CLEARED ON NEXT FILL"`**. Dialog **`[YES]`** only unlocks the
knobs. Writing the pattern is a second **`[YES]`**.

**`[CUE]`** tap (release with no **`[TRACK]`**). Keeps **PULS** as the hit
count and picks *which* steps are on at random on the focused lane.
**`[CUE]`** + **`[TRACK]`** is stock cue. Editing **PULS** after a random
tap returns to Euclidean.

**TRIG write.** Sample trigs follow the TRIG lane. Locks for the current
destination land on those steps (**DPTH** 0 clears them). Other destination
locks stay. If a step loses its sample trig but still holds another
destination, it becomes a **trigless trig**.

**PLCK write.** Sample trigs stay. This destination clears on every miss,
including on sample-trig steps, then writes on PLCK hits. **PULS 0** clears
this destination across the pattern. Empty trigless steps drop when nothing
else remains on them.

## Examples

In the figures: black = lock on a sample trig; hatch = **trigless trig**;
white = no lock.

### Place sample trigs

Empty track. **LANE** = **TRIG**, **D** = **SRC** / **PTCH**, **DPTH** = 0,
set **PULS**, **`[YES]`**:

![TRIG DPTH 0 writes sample trigs and clears PTCH.](../../img/seq/notes-only.png)

Sample trigs land. Current destination locks clear because **DPTH** is 0.

### Lock pitch on those trigs

**LANE** = **TRIG**, set **PULS** / **ROT**, **D** = **SRC** / **PTCH**,
**DPTH** non-zero, **`[YES]`**. Sample trigs land; **PTCH** locks sit on
those steps; that destination's PLCK **PULS** / **ROT** match the TRIG
rhythm.

### Add volume locks on another rhythm

You already have sample trigs + **PTCH**. Switch to **LANE** = **PLCK**,
**D** = **AMP** / **VOL**, set a different **PULS** / **ROT**, **`[YES]`**:

![PLCK writes only VOL; sample trigs and PTCH stay.](../../img/seq/stack-vol.png)

**VOL** locks follow that destination's PLCK rhythm (**trigless trigs**
where there is no sample trig). Sample trigs and **PTCH** stay.

### Change the sample-trig rhythm

Sample trigs with **PTCH** + **VOL**. Keep **D** = **SRC** / **PTCH**,
change TRIG **PULS**, **`[YES]`**:

![TRIG YES reshapes only PTCH; VOL survives as trigless where sample trigs drop.](../../img/seq/trig-reshape.png)

- **PTCH** (current destination) clears on silent steps and rewrites on the
  new sample trigs.
- **VOL** (other destination) is kept. Where a sample trig disappears but
  **VOL** remains, the step becomes a **trigless trig**.

### Rewrite one destination's locks

**PTCH** was placed from **TRIG**. Switch to **LANE** = **PLCK**, **D** =
**SRC** / **PTCH**, change **ROT**, **`[YES]`**:

![PLCK YES clears PTCH on sample-trig misses; other destinations stay.](../../img/seq/plck-overwrite.png)

- **PTCH** clears on every miss, including on sample trigs that still fire,
  then writes on the new PLCK hits (**trigless trig** if no sample trig).
- Other destinations (**VOL**, filter, …) stay.

### Clear one destination's locks

**LANE** = **PLCK**, that destination's **PULS** = 0, **`[YES]`**:

![PLCK PULS 0 clears PTCH; sample trigs and other destinations stay.](../../img/seq/clear-dest.png)

Clears this destination over the pattern length. Sample trigs stay. Orphan
trigless bits drop when nothing else remains on the step.

### Clear from the menu

While SEQ is open, press **`[FUNC]`** + **`[BANK]`**. Choose a row and
press **`[YES]`**. The clear happens immediately and SEQ returns.

| Row | What clears |
|---|---|
| **CLEAR DEST** | The current destination's locks and its PLCK settings |
| **CLEAR ALL DEST** | Every SEQ destination's locks and PLCK settings on this track |
| **CLEAR ALL+TRIGS** | All of the above, plus sample trigs on this track. TRIG returns to **PULS** 5 and **ROT** 0 |

The first two rows keep sample trigs. Steps with no sample trig or
remaining locks become empty. Press **`[NO]`** once to cancel and
return to SEQ. Pressing **`[FUNC]`** + **`[BANK]`** again also cancels.

### Place random trigs

Focus the lane (**TRIG** or **PLCK**), set **PULS** to the hit count you
want, tap **`[CUE]`** (exactly that many hits at random on that lane),
then **`[YES]`** to write.
