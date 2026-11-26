## What it does

DRUMMER turns a FLEX track holding a **sliced drum sample** into a generative
drummer. You load a loop or a kit of one-shots cut into slices; DRUMMER sorts
the slices into drum roles and plays them live in the style you choose. Nothing
is written into the pattern. At each step, DRUMMER chooses which slice to play,
how loud to play it, and how early or late it lands based on a set of knobs.
Turning the knobs while it plays changes the performance in real time, making
it simpler or busier, straighter or looser, with fills, ghost notes, and breaks
on the crossfader.

DRUMMER has two playback modes:

- **Style mode** (REDRUM OFF): DRUMMER plays one of 29 built-in grooves
  (breakbeat, funk, house, jungle, dub, afrobeat, bossa, techno, trap, and
  more) using the sounds of your kit.
- **REDRUM mode** (ON): DRUMMER plays **your loop's own groove**, slice by
  slice, while the same knobs reshape it. You can play the break as recorded,
  thin it out, swap hits, and add ghost notes, fills, and breaks.

The track remains a FLEX track, so its sample, slices, AMP, LFOs, and effects
all work as usual. If you open the project on a stock Octatrack, it appears as
a standard FLEX track.

## Where to find it

DRUMMER is included in the `drummer` test remix. It requires STORE (so kits are
saved with the project) and PAGES (for the KIT BALANCE and NEXT pages). Any of
the eight tracks can be a DRUMMER track, each with its own kit.

## Quick start

1. Load a drum loop onto a FLEX track and **slice it** in the audio editor
   using a grid, transients, or manual placement (DRUMMER reads your slices and
   never moves them). One hit per slice works best.
2. Press **FUNC + SRC** to open the machine list and scroll down to **DRUMMER**
   on the last row. Press **YES** to make the track a DRUMMER track and display
   its CONFIG knobs (or press RIGHT on the row to pick a different sample
   first).

   ![The machine list, DRUMMER the last row](../../img/drummer/machines.png)

3. Press **NO** to close the machine list. DRUMMER prompts you to build a kit.
   Press **YES** to analyse and sort every slice into drum roles (kick, snare,
   hats, and so on); a toast reports how many slices were sorted. Pressing
   **NO** leaves the kit empty so that only the track's own trigs play.

   ![The kit question](../../img/drummer/ask.png)

   ![AUTO done](../../img/drummer/auto.png)

4. Press **PLAY**. The track starts playing the style selected on CONFIG
   (`BRKB`, a breakbeat, by default), and you can shape it with the knobs.

You do not need any trigs placed on the track. Any trig you do place still
plays as an accent (a kick on the beat if the step is otherwise empty, or a
snare otherwise).

## The pages

A DRUMMER track has five dedicated screens. Press **SRC** to cycle through the
first three (LIVE, KIT BALANCE, NEXT), press **FUNC + SRC** to open CONFIG, and
**hold a trig key and press BANK** to open the KIT window.

| screen | open with | what is on it |
|---|---|---|
| LIVE | SRC | The six performance knobs: SEED, DENS, CPLX, ORN, BRK, GHST |
| KIT BALANCE | SRC again | How heavily each drum group plays |
| NEXT | SRC a third time | Beat-synced commands: stop, resume, fill, style change, or break |
| CONFIG | FUNC + SRC | Style and feel settings: STYL, VEL, ALT, SWNG, HUMN, VAR |
| KIT window | hold a trig, press BANK | Per-slice drum assignment, level, and timing; track settings and REDRUM; fill settings |

### LIVE: the knobs you play

![The LIVE page](../../img/drummer/live.png)

| knob | 0 | 64 | 127 |
|---|---|---|---|
| **SEED** | The style as written | A moderate variation | The furthest variation |
| **DENS** | Very sparse (backbone only) | The style as written | Busier, adding extra hits from the complex version |
| **CPLX** | The BASIC version of the style | STANDARD | COMPLEX |
| **ORN** | No ornaments | Flams on loud snares and rolls closing fills | Adds ruffs plus doubled and tripled hats |
| **BRK** | Normal groove | (see below) | Stutters and repeats |
| **GHST** | No ghost notes | Moderate ghost notes | Frequent soft snares around the backbeat |

**SEED** selects a deterministic variation of the current style. `TBL` at 0
plays the style as written; above 0 there are eight bands of sixteen
variations, displayed as `band:variant` (`1:01` through `8:15`). The band
controls how strongly the pattern diverges (band 1 changes roughly one cell in
eight, while band 8 changes more than half), and a variant keeps its character
across bands while becoming stronger. The kick on beat 1 and the snares on
beats 2 and 4 never move. The same SEED always replays the same performance
from PLAY.

**CPLX** moves across the style's three written complexity levels (BASIC,
STANDARD, and COMPLEX), adding the next level's hits gradually. The screen
shows your position as `BAS`, `STD`, or `CPX`, and intermediate values such as
`B>50` (halfway from BASIC to STANDARD) or `S>25` (a quarter of the way to
COMPLEX).

**BRK** is the break knob, intended for crossfader control (lock it to a scene;
see *Breaks on the crossfader* below). Its range is divided into zones:

| BRK | what happens |
|---|---|
| 0 | Normal groove |
| 1-31 | Gradually brings in more of the style's busier layer |
| 32-63 | Adds a fill at the end of every bar: half a beat at 32, one beat from 40, two beats from 48, and a full bar from 56. Fills of one beat or longer land on a crash on the next beat 1 |
| 64-79 | Draws slices from across the whole kit, scrambling the groove |
| 80-95 | Same scramble at half-time (one snare on beat 3) |
| 96-127 | Per-beat cuts: repeats the last hit as a 16th-note stutter (tighter past 112), occasionally dropping a beat (never beat 1, and never two in a row) |

When you return BRK to 0, the groove resumes right where it would have been.

**GHST** adds soft snare hits on open steps near the backbeat, using the kit's
GHOST slices or a soft SNARE slice if no GHOST slices exist. The SNARE row on
KIT BALANCE scales their frequency.

### CONFIG: the style and the feel

![The CONFIG page](../../img/drummer/config.png)

| knob | 0 | towards 127 |
|---|---|---|
| **STYL** | | Selects the style by name (see the list below) |
| **VEL** | Every hit at equal volume | Accents beats and softens off-beats (especially hats) with slight randomness; past halfway, adds occasional full accents |
| **ALT** | Always uses the first slice of each drum type | Alternates among slices of the same type; past halfway uses any role of that drum; near the top occasionally borrows a neighbour (kick/tom, snare/ghost, hats/ride) |
| **SWNG** | Straight timing | Lays back the snare and swings hats; past halfway shuffles every off-16th up to a triplet feel |
| **HUMN** | Leaves the groove untouched | Scales the overall amount of VEL, ALT, SWNG, and VAR: 64 applies them as set, 127 doubles their depth |
| **VAR** | Plays the same bar every bar | Adds fills at the end of each phrase; past halfway varies the groove from bar to bar with longer fills (two beats, sometimes a full bar); near the top adds a fill at the end of every bar |

HUMN acts as the master humanisation depth. At 0, VEL, ALT, SWNG, and VAR have
no effect and the groove plays strictly as written. ORN and GHST are not scaled
by HUMN.

**The styles** (STYL): `BRKB` breakbeat, `HHOP` hip-hop, `FUNK`, `HOUS` house,
`JUNG` jungle, `DUB` one drop, `AFRO` afrobeat, `CLAV` son clave 3-2, `BOSS`
bossa, `BMBE` bembe 12/8, `ROCK`, `DISC` disco, `TECH` techno, `TRAP`, `RNB`
r&b / neo-soul, `DEMB` reggaeton dembow, `SAMB` samba, `BAIA` baiao, `CUMB`
cumbia, `GARA` uk garage, `DSTP` dubstep, `SHUF` blues shuffle 12/8, `SIX8` 6/8
afro, `ELEC` electro, `DEEP` deep house, `MINI` minimal techno, `AMAP`
amapiano, `FTWK` footwork, and `HILF` highlife. Every style uses the full kit,
mapping bells, claves, rims, and shakers to PERC slices and congas and log
drums to TOM slices. Styles in 12/8 play 12-step bars.

### KIT BALANCE: the mix of the drums

![KIT BALANCE](../../img/drummer/balance.png)

KIT BALANCE provides six rows, one per knob: **A KICK**, **B SNARE** (including
ghost notes), **C HATS** (closed and open), **D CYMB** (ride and crash), **E
TOMS**, and **F PERC**. The centre tick (`=`) plays the style as written.
Turning left reduces how often that drum plays (`-20` drops a fifth of its
hits; `OUT` removes all of them). Turning right adds more hits: first pulling
from the style's busier complexity layers, and then (past the small tick, where
the bar becomes dotted) filling open steps for lighter drums (hats, perc,
ghosts) and 8th-note steps for the rest. Each detent changes the value by 5%,
and turning pauses briefly at the centre tick.

KIT BALANCE is stored per Part, so switching Parts loads that Part's balance.
The track's own sequencer trigs always play regardless of KIT BALANCE.

**Locks on steps and scenes.** KIT BALANCE supports parameter locks just like
stock pages (via PAGES locks; the remix also needs EVENTS):

- **On a step:** With GRID RECORDING enabled, place a trig (TRIG, or FUNC +
  TRIG for a trigless trig), hold it, and turn encoders A–F to lock those drum
  zones on that step. The title changes to `STEP n`; locked zones show their
  value while unlocked ones show `--`. Hold FUNC while turning an encoder to
  clear its lock. As in stock OS, the lock stays active until the track's next
  trig.
- **On a scene:** Hold SCENE A or B and turn encoders A–F to lock zones to that
  scene (title `SCENE n`), allowing the crossfader to morph between the two
  scenes' drum mixes. Hold FUNC while turning to remove a lock.

![KIT BALANCE: step 3's locks, trig 3 held](../../img/drummer/balance-step.png)

![KIT BALANCE: scene A's lock, SCENE A held](../../img/drummer/balance-scene.png)

Locks behave like stock parameter locks: removing a trig removes its locks,
pressing trig + PLAY clears them, and copying a trig, track, or pattern copies
them along with it. They are saved with the project in `pglocks.work`. Part and
bank operations (such as RELOAD PART, or copying a Part or bank) do not move
them yet.

### NEXT: orders on the beat

![NEXT, an order armed](../../img/drummer/next-armed.png)

NEXT lets you queue a beat-synced command for the drummer, such as playing a
triplet fill and stopping at the end of the next phrase. The command waits for
the beat, bar, or phrase boundary you choose and triggers on time regardless of
how early or late you turned the knob. The six cells match the physical knob
layout: A, B, and C on top, D, E, and F below.

| knob | what it does | values |
|---|---|---|
| **A WHEN** | Arms the order for a timing boundary | `--` (nothing armed), BEAT, BAR, PHRASE, 2 PHR |
| **B RUN** | Stop or resume playback | `--`, STOP (track's own trigs keep playing), SILENT (track's own trigs are silenced too); displays RESUME while the drummer is stopped |
| **C HOW** | Transition into the stop or resume | DRY, CRASH (crash on beat 1), FILL (fill ending on beat 1), FILL+CR, PICKUP (half-beat lead-in; followed by a crash on resume) |
| **D FILL** | Fill type for the order (plays even if B is `--`) | `--`, TRIP, 6LET, RUDI, 3:4, LONG (a full bar) |
| **E STYL** | Switch to another style starting on beat 1 | `--` or any style (remains active until you turn CONFIG's STYL knob) |
| **F BRK** | Trigger a break starting on beat 1 | `--`, 1 BEAT, 2 BEATS, BAR (BRK cuts), STUTTER (a full bar of stutter) |

**Encoder A requires four detents per value and arms after a half-second pause**,
so bumping the knob does nothing and turning past BEAT on the way to PHRASE
arms PHRASE instead of BEAT. **Only A resets back to `--` after the order
runs.** You can configure B through F once and trigger the same command
repeatedly with A (for example, alternating STOP and RESUME). An asterisk (`*`)
marks cells that are configured and waiting for A. To cancel an armed order
before it triggers, turn A back to `--`.

![NEXT: the order set, waiting for WHEN](../../img/drummer/next-ready.png)

The top row displays the drummer's current state (PLAYING or STOPPED), a summary
of the armed order, and the current bar within the phrase on the right. Below
it, a full-width phrase bar divides into one cell per bar and fills along with
the playhead, with a marker underneath where the order will execute and the
remaining beats shown beside it. While armed, the order's values appear inverted
and blink during the final four beats. When the order executes, the line flashes
and A resets to `--`.

![NEXT: the last beat before the order](../../img/drummer/next-close.png)

![NEXT: the order played, the drummer stopped](../../img/drummer/next-stopped.png)

While stopped, the drummer keeps counting silently so RESUME brings it back in
time on beat 1. Orders with a fill (C set to FILL, FILL+CR, or PICKUP, or D
set) require the order to land on beat 1 of a bar; if A is set to BEAT mid-bar,
the order executes without the fill. Fill length follows the FILLS page's LONG
setting (KIT window page 4), defaulting to one beat on AUTO, or a full bar when
D is set to LONG.

If you arm an order while the sequencer is stopped, it triggers on the first
step when playback starts. For example, arming STOP before pressing PLAY starts
the pattern without the drummer so you can bring it in later with RESUME.
Settings B through F are saved in the Part; A is not saved, so a project always
loads with nothing armed.

### The KIT window

Hold any **trig key** and press **BANK** to open the KIT window (pressing BANK
alone still selects a bank). The window displays one slice per row across four
pages. Use **LEFT / RIGHT** to change pages, **UP / DOWN** to step through
slices and audition them, any **trig key** to jump directly to and audition
that slice, and **YES** or **NO** to close. Pressing **FUNC + RIGHT** re-runs
automatic kit analysis (AUTO) after asking for confirmation.

**Page 1: what each slice is.**

![KIT window, page 1](../../img/drummer/kit-zones.png)

- **A ZONE**: Assigns the drum role for the slice: KICK, SNARE, GHOST, HAT C,
  HAT O, RIDE, CRASH, TOM, PERC, a two-drum combo (such as kick + crash), or
  OUT (excluded from playback).
- **B ROLE**: Sets the dynamic role to ACC (loud accents), NRM (normal), or SFT
  (soft hits). DRUMMER matches each hit's velocity to the role, playing an ACC
  snare on loud hits and an SFT snare on soft ones.
- **LNK**: Displays `=n` on slices that AUTO detected as duplicates of slice
  `n` (see SIMILAR on page 3).

**Page 2: timing, level, scene.**

![KIT window, page 2](../../img/drummer/kit-align.png)

- **A ALGN** (0–250 ms): Starts the slice early by this amount so a hit that
  sits late inside its slice lands on the beat. AUTO sets this automatically
  when it detects a delayed transient.
- **B GAIN** (-24 to +6 dB): Adjusts the slice's individual level on top of hit
  velocity. Adjusting a linked slice updates its entire linked group together.
- **E SCN** (`--` or 1–16): Applies a Part scene's locks (for this track's LFO,
  AMP, FX1, and FX2 parameters) only when this slice plays. For example, you
  can reserve scenes 9–16 for per-slice effects (like a delay send on one snare
  or a filter on the open hat) while keeping scenes 1–8 for the crossfader.
- **F DOSE** (5–100%): Controls how strongly the slice moves toward the
  assigned scene's parameter values.

**Page 3: the track.**

![KIT window, page 3](../../img/drummer/kit-track.png)

- **A SHIFT**: When ON, if a light hit (ghost, hat, or perc) collides with a
  louder drum on the same step, it shifts to the next free step instead of
  being dropped.
- **B PHRASE**: Sets the phrase length to 4 or 8 bars for VAR fills and
  crashes.
- **C SIMILAR**: Sets how closely two slices must match for AUTO to treat one
  as a copy of the other (OFF or 1–15; default is 6).
- **D COPIES**: Chooses how AUTO handles duplicate slices: OUT removes them
  from the kit, while LINK keeps them and links their GAIN controls together.
- **E KIT FILE**: Turn E to save the kit to a file alongside the sample. Next
  time you load that sample on a DRUMMER track, its kit loads automatically
  without prompting.
- **F REDRUM**: Selects OFF, AUTO, or 1, 2, 4, or 8 BARS (see *REDRUM* below).
  The row displays what REDRUM detected for the loop, such as `AUTO 1BAR 16SL`.

Changes to SIMILAR and COPIES take effect the next time you run AUTO. The kit
assignments, GAIN, ALIGN, SCENE, DOSE, and page 3 settings are all saved per
track with the project.

**Page 4: FILLS, the fills' vocabulary.**

![KIT window, page 4](../../img/drummer/kit-fills-set.png)

Page 4 has six fill parameters, all defaulting to AUTO so the style, VAR, and
ORN knobs decide automatically. A filled box indicates a manual override:

| knob | choices |
|---|---|
| **A FILL** | Fill type: WRIT (the style's written fill), RUDI (drum rudiments), TRIP (triplets), or 3:4 (groups of three over four) |
| **B FREQ** | When fills trigger: AUTO (both BRK and VAR fills), BRK (only when BRK requests one), 2BAR (BRK fills every second bar), or PHRS (BRK fills at the end of a phrase) |
| **C LONG** | Fill length: AUTO (follows BRK's zone), 1BT, 2BT, or BAR |
| **D STIK** | Selects a specific sticking for the fill type chosen in A (shows `--` while A is AUTO or WRIT) |
| **E ORCH** | Orchestration across drums: TOMS (right hand around the toms, left on the snare), SNR (all on the snare), or SWAP |
| **F TRIP** | Triplet subdivision: 8TH (8th-note triplets), 6LET (sextuplets), or 8>6 (8ths accelerating to sextuplets on the last beat). Setting this while A is AUTO forces triplet fills |

Available stickings on **D**:
- Rudiments: `SNGL` single stroke, `DBLE` double stroke, `PARA` paradiddle,
  `INVP` inverted paradiddle, `PDDL` paradiddle-diddle, `SIXS` six-stroke roll,
  `DPAR` double paradiddle, `LIN3` / `LIN4` linear with kick, `FTAP` flam tap,
  `DRAG` single drag tap, `RTMQ` ratamacue, `FIVE` five-stroke roll.
- Triplets: `TRPL` single stroke, `RLL`, `SIXS` six-stroke, `PDDL`
  paradiddle-diddle, `LIN` linear, `SWIS` Swiss army triplet, `FACC` flam
  accent.
- 3:4: `TSS` (tom snare snare), `LIN`, `KSS` (kick snare snare), `FSS` (flam
  snare snare).

FILLS settings are saved per Part, just like KIT BALANCE. Changes made during
playback apply on the next fill. To trigger a one-off fill that differs from
these settings, use NEXT's D FILL knob.

## How a kit is made

**AUTO** analyses each slice's low-frequency energy, high-frequency energy, and
decay length. Heavy low end is classified as a kick; bright highs with little
low end become a hat (open if it sustains); a ring lasting a second or more
becomes a cymbal; midrange/high energy over moderate low end becomes a snare
(or a ghost if soft); a lower resonant decay becomes a tom; everything else is
assigned to perc. Within each drum zone, the loudest slices are marked ACC and
the softest SFT. AUTO is a starting point: if a slice is misclassified, change
its zone on KIT window page 1 and the change takes effect immediately.

**SIMILAR.** Drum loops often repeat the same sound several times (for example,
a two-bar loop whose second bar repeats the first). AUTO detects these copies
and keeps one of each. With COPIES set to OUT, duplicate slices are removed
from the kit (the toast reports e.g. `5 SIMILAR OUT`); with LINK, they stay in
the kit and share a linked gain group. A duplicate that is 6 dB softer or more
is kept separately as an SFT hit.

**Collisions.** Because a FLEX track plays one slice at a time, DRUMMER must
resolve steps where the groove calls for two drums simultaneously. If the kit
contains a combo slice matching those exact two drums, that slice plays;
otherwise the higher-priority drum wins (kick first, then snare, then the other
zones).

## REDRUM: your loop as the groove

With REDRUM enabled, DRUMMER places each slice at its original position in your
loop (preserving its micro-timing off the 16th-note grid so the loop's feel
stays intact) and uses that loop as the groove. Setting **HUMN 0, SEED 0, CPLX
64** replays the loop exactly as recorded, using each step's original slice.
From there, the knobs reshape it:

| knob | under REDRUM |
|---|---|
| ALT (with HUMN) | Occasionally swaps a slice for another slice of the same drum (the re-drum effect) |
| SEED | Moves, removes, and adds hits just as in style mode |
| DENS | Below 64, thins out the loop while keeping the backbone |
| CPLX | 0 plays the loop without soft hits or ghosts; 64 plays the loop as-is; 127 layers the selected style's COMPLEX hits onto steps the loop leaves empty (never overwriting the loop's own hits) |
| GHST, VAR, ORN, BRK, VEL | Same as in style mode: ghost notes, bar-to-bar variations, ornaments, fills, breaks, and dynamics |
| STYL | Supplies fill patterns and character only, without replacing the loop's own groove, swing, or lay-back |
| KIT BALANCE | Same as in style mode, per drum group |

Slices that SIMILAR set to OUT still play on their original steps as recorded,
though KIT BALANCE and SEED do not affect them. With COPIES set to LINK, they
stay assigned to their drum group so every knob affects them.

**How long is the loop?** REDRUM needs to know the loop's length in bars to map
slices onto steps. In **AUTO** mode, it reads the sample slot's attributes (bar
length if present, otherwise tempo) and rounds to the nearest of 1, 2, 4, or 8
bars. A slot without its own tempo inherits the project tempo, which can cause
a 150 BPM loop to read as 6.4 bars at 120 BPM and round to 8 bars. If the row
shows the wrong bar count, **set it manually** to 1, 2, 4, or 8 BARS with
encoder F. A manual bar length ignores the slot's tempo, so the loop tracks the
project at any tempo.

If a loop is longer than the pattern, it continues across pattern cycles: a
4-bar loop on a 16-step pattern plays all four bars over four passes of the
pattern.

## Configurations

**A steady groove for a song.** On CONFIG, pick your style and set HUMN to 0.
On LIVE, set SEED to 0, DENS to 64, CPLX to 64, and BRK to 0. Every bar plays
identically, straight from the written style.

**A human drummer.** Set HUMN to 64, VEL to 64, SWNG to 40–70, and ALT to 40.
Add VAR around 40 for phrase-end fills, ORN around 32 for flams and rolls, and
GHST around 40 for ghost notes.

**More and less.** DENS and CPLX both control busyness in different ways: CPLX
steps through the written pattern layers (adding parts and syncopation), while
DENS thins or adds hits randomly around them. Try DENS 20 for a breakdown, or
CPLX 127 and DENS 90 for a peak.

**Breaks on the crossfader.** Lock BRK to a scene: hold SCENE B and turn BRK to
56 (for a one-bar fill) or 110 (for stutters), while keeping BRK at 0 on SCENE
A. Moving the crossfader moves smoothly from the groove into the break and back,
with fills of a beat or more landing on a crash.

**Fills only where you want them.** On KIT window page 4 (FILLS), set FREQ to
BRK (so fills only occur when BRK requests them) and LONG to 1BT. Locking BRK
to 40 on a scene gives you a one-beat fill on demand with the crossfader. You
can also set FREQ to 2BAR or PHRS to restrict fills to every second bar or the
end of each phrase.

**Triplet fills.** On KIT window page 4 (FILLS), set TRIP to 6LET (sextuplets)
and leave FILL on AUTO or set it to TRIP.

**An ending.** On NEXT, set B to STOP, C to FILL+CR, and D to LONG. Near the
end of the song, turn A to PHRASE to play a full-bar fill, hit a crash on the
next phrase's beat 1, and stop. To bring the drummer back in, set C to PICKUP
and turn A to PHRASE again (B now reads RESUME) for a lead-in and crash.

**Drop the drums for a bar.** On NEXT, set B to STOP and C to DRY. Turn A to
BAR to stop on the next bar, then turn A to BAR again to come back in on the
following bar. Set B to SILENT instead if you also want to mute the track's own
trigs.

**Change style on the phrase.** On NEXT, set E to the new style and leave B on
`--`, then turn A to PHRASE. The new style starts on beat 1 of the next phrase
and stays active until you turn CONFIG's STYL knob again.

**One slice, one effect.** On KIT window page 2, assign SCN 9 to the open hat
slice, then lock the track's filter on scene 9. Only the open hat plays through
that filter setting, leaving the rest of the kit untouched. You can use the
same trick for a delay send on the snare alone or a pitch shift on the toms.

**Two drummers.** Put two DRUMMER tracks on the same sliced loop with different
SEEDs or styles, then use KIT BALANCE so one track plays mainly kick and snare
while the other plays hats and percussion.

**Your own kit from one-shots.** The companion kit-maker tool beside the module
turns a folder of one-shot samples into a single sliced sample and matching kit
file ready to copy onto the CF card.

## Tutorial 1: a drummer from a sliced loop

You will need a one- or two-bar drum loop on your CF card.

1. **Load and slice.** Load the loop onto track 1 with a FLEX machine. Open the
   audio editor (AED), go to SLICE, and run *create slice grid* with 16 slices
   for one bar (or 32 for two bars). Check that each slice starts cleanly on a
   hit.
2. **Make it a drummer.** Press FUNC + SRC, scroll to **DRUMMER**, press
   **YES**, and press **NO** to close. When prompted with *This track has no
   kit yet*, press **YES**. A toast reports how many slices AUTO sorted.
3. **Check the kit.** Hold trig 1 and press **BANK** to open page 1 of the KIT
   window. Use UP and DOWN to audition each slice and check its assigned zone.
   If a hi-hat was labelled as PERC, turn encoder A to HAT C. Close with
   **NO**.
4. **Pick a style.** Press FUNC + SRC to open CONFIG, set **STYL** to FUNK, and
   set HUMN to 0. Press **PLAY** to hear a straight funk groove played with
   your loop's sounds.
5. **Shape it.** Press SRC to open LIVE. Turn CPLX to 0 for the simplest funk
   pattern and 127 for the busiest, or turn DENS to 30 for a sparse groove,
   then return both to 64. Slowly turn **SEED**: each value gives a different
   variation on the style, while `TBL` returns to the written pattern.
6. **Make it breathe.** On CONFIG, set HUMN to 64, VEL to 70, SWNG to 50, and
   ALT to 40. On LIVE, set GHST to 50 and ORN to 32. The snare now lays back,
   the hats swing, and ghost notes and flams enter the groove.
7. **Mix the drums.** Press SRC again for KIT BALANCE. Turn hats down to `-40`
   and kick up to `+20`. Open KIT window page 4 (FILLS) and set FILL to RUDI
   and ORCH to TOMS.
8. **Breaks.** On LIVE, hold SCENE B and turn BRK to 56, then release. Hold
   SCENE A and ensure BRK is 0. Moving the crossfader toward B near the end of
   a bar triggers a tom fill landing on a crash. You can set another scene to
   BRK 110 for stutters.
9. **Stop on the phrase.** Press SRC again to open NEXT, then set B to STOP and
   C to FILL+CR. Turn A to PHRASE: the countdown runs, plays a fill and a crash
   on beat 1, and stops. Turn A to PHRASE again to bring the drummer back on
   the next phrase.
10. **Save.** Run SAVE PROJECT to store the kit, knobs, KIT BALANCE, FILLS, and
    NEXT settings. You can also turn encoder E on KIT window page 3 to save a
    kit file beside the sample so the loop loads its kit automatically next
    time.

## Tutorial 2: REDRUM, re-drum your break

You will need a loop whose groove you like, sliced with one hit per slice.

1. **Set up** as in Tutorial 1, steps 1–3 (load, slice, choose DRUMMER, and
   accept AUTO). If the loop has many repeated hits, set COPIES on page 3 to
   LINK *before* running AUTO (or press FUNC + RIGHT in the KIT window to
   re-run AUTO) so every slice stays active in its drum group.
2. **Turn REDRUM on.** Open the KIT window, press RIGHT twice to reach page 3,
   and turn **F** once to enable `AUTO 1BAR 16SL`. Verify the bar count: a
   one-bar loop should read `1BAR` and a two-bar loop `2BAR`. If it is wrong,
   keep turning F to set the exact number of bars.

   ![REDRUM on, page 3](../../img/drummer/redrum.png)

3. **Hear the loop itself.** Set CONFIG HUMN to 0, and on LIVE set SEED 0, CPLX
   64, DENS 64, BRK 0, GHST 0, and ORN 0. Press **PLAY** to hear your original
   loop played back slice by slice at the project's tempo.
4. **Re-drum it.** On CONFIG, set HUMN to 64 and ALT to 60 so snares and kicks
   occasionally swap with other slices of the same drum. On LIVE, turn SEED to
   shift, drop, and add hits using the loop's own sounds.
5. **Thin and thicken.** Set CPLX to 0 to strip away ghosts and soft hits, or
   set CPLX to 127 with STYL set to HOUS to add house hats on empty steps. Turn
   DENS down to 30 for a sparser pattern.
6. **Fills and breaks.** STYL chooses the style of fills (ROCK, FUNK, JUNG, and
   so on). On KIT page 4 (FILLS), set TRIP to 6LET for sextuplet fills. Lock
   BRK to 56 on a scene for a full-bar fill on the crossfader, or 110 for
   stutters; fills land on a crash.
7. **Feel.** Turn VEL to 60 to add beat dynamics, and GHST to 40 to introduce
   ghost notes that were not in the original loop.
8. **Back to the source.** Return HUMN to 0, SEED to 0, and CPLX to 64 to hear
   the original loop again. REDRUM is saved per track with the project; turning
   it OFF returns the track to style mode.
