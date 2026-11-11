## What it does

DRUMMER turns a FLEX track holding a **sliced drum sample** into a drummer.
You give it a loop (or a kit of one-shots) cut into slices; it sorts the
slices into drums and plays them, live, in a style you pick. Nothing is
written into the pattern: at every step DRUMMER decides which slice plays,
how loud and how early or late, from a handful of knobs. Turn them while it
plays and the drummer follows: simpler or busier, straighter or looser,
with fills, ghost notes, breaks on the crossfader.

It has two ways of playing:

- **A style** (REDRUM OFF). DRUMMER plays one of 29 written grooves
  (breakbeat, funk, house, jungle, dub, afrobeat, bossa, techno, trap...)
  with the sounds of your kit.
- **REDRUM** (ON). DRUMMER plays **your loop's own groove**, slice by slice,
  and the same knobs bend it: replay the break as it is, then thin it, swap
  its hits, add ghosts, fills and breaks.

The track stays a FLEX track: its sample, slices, AMP, LFOs and effects are
FLEX's, and a project opened on a stock Octatrack finds a plain FLEX track.

## Where to find it

DRUMMER is in the `drummer` test remix. It needs STORE (the kits are saved
with the project) and PAGES (KIT BALANCE and NEXT). Any of the eight
tracks can be a DRUMMER track, each with its own kit.

## Quick start

1. Load a drum loop on a FLEX track and **slice it** in the audio editor
   (a grid, transients or by hand: DRUMMER reads the slices, it never moves
   them). One hit a slice works best.
2. **FUNC + SRC** opens the machine list. Scroll down: **DRUMMER** is the
   last row. **YES** makes the track a DRUMMER track and shows its CONFIG
   knobs (RIGHT on the row picks another sample first).

   ![The machine list, DRUMMER the last row](../../img/drummer/machines.png)

3. Close with **NO**: DRUMMER asks to make a kit. **YES**: it listens to
   every slice and sorts it (kick, snare, hats...); the toast says how many
   slices it sorted. **NO** leaves the kit empty; then only the track's own
   trigs play.

   ![The kit question](../../img/drummer/ask.png)

   ![AUTO done](../../img/drummer/auto.png)

4. **PLAY**. The track plays the style shown on CONFIG (BRKB, a breakbeat,
   at first). Turn the knobs.

You do not need a single trig on the track. A trig you place still plays:
it is an accent (on an empty step, a kick on the beat, else a snare).

## The pages

A DRUMMER track has five screens of its own. **SRC** cycles the first three
(LIVE, KIT BALANCE, NEXT); **FUNC + SRC** opens CONFIG; **a trig key held +
BANK** opens the KIT window.

| screen | open with | what is on it |
|---|---|---|
| LIVE | SRC | the six knobs you play: SEED DENS CPLX ORN BRK GHST |
| KIT BALANCE | SRC again | how much each group of drums plays |
| NEXT | SRC a third time | orders on the beat: stop, come back, a fill, a style, a break |
| CONFIG | FUNC + SRC | the style and the feel: STYL VEL ALT SWNG HUMN VAR |
| KIT window | hold a trig, press BANK | the kit: each slice's drum, level, timing; the track's settings and REDRUM; the fills |

### LIVE: the knobs you play

![The LIVE page](../../img/drummer/live.png)

| knob | 0 | 64 | 127 |
|---|---|---|---|
| **SEED** | the style as written | a variation of it | the furthest variation |
| **DENS** | almost nothing: the backbone only | the style as written | busier: extra hits drawn from the complex version |
| **CPLX** | the BASIC version of the style | STANDARD | COMPLEX |
| **ORN** | no ornaments | flams on loud snares, rolls closing fills | ruffs, doubled and tripled hats too |
| **BRK** | the groove | (see below) | stutters and repeats |
| **GHST** | no ghost notes | some | many soft snares around the backbeat |

**SEED** picks a variation of the style: `TBL` at 0 is the style as written;
then eight bands of sixteen variations, shown `band:variant` (`1:01` ...
`8:15`). The band says how far the variation goes (band 1 touches about one
cell in eight, band 8 more than half), and a variation keeps its character
from band to band, only stronger. The kick on 1 and the snares on 2 and 4
never move. The same SEED always replays the same performance from PLAY.

**CPLX** goes through the style's three written levels, BASIC, STANDARD and
COMPLEX, adding the next level's hits one at a time. The screen shows where
you are: `BAS`, `STD`, `CPX`, and in between `B>50` (half-way from BASIC to
STANDARD) or `S>25` (a quarter of the way to COMPLEX).

**BRK** is the break knob, made for the crossfader (lock it on a scene, see
*Breaks on the crossfader* below). Its range is in zones:

| BRK | what happens |
|---|---|
| 0 | the groove |
| 1-31 | more of the style's busier layer, a little more each step |
| 32-63 | a fill closes every bar: half a beat at 32, one beat from 40, two from 48, a whole bar from 56. A fill of a beat or more lands on a crash on the next 1 |
| 64-79 | slices drawn from the whole kit: the groove scrambles |
| 80-95 | the same, half-time (one snare, on 3) |
| 96-127 | per beat, cuts: the beat repeats the last hit as a stutter on every 16th (tighter past 112), and now and then a beat drops out (never the 1, never two in a row) |

Back to 0, the groove returns exactly where it would have been.

**GHST** adds soft snares on free steps near the backbeat, from the kit's
GHOST slices, or a soft SNARE when there are none. KIT BALANCE's SNARE row
scales them.

### CONFIG: the style and the feel

![The CONFIG page](../../img/drummer/config.png)

| knob | 0 | towards 127 |
|---|---|---|
| **STYL** | | the style (its name is shown); see the list below |
| **VEL** | every hit as loud | beats loud, off-beats soft (hats most), some chance; past half, random full accents |
| **ALT** | always the first slice of each kind | other slices of the same kind; past half any role of the drum; near the top, now and then a neighbour (kick/tom, snare/ghost, hats/ride) |
| **SWNG** | straight | a laid-back snare and swung hats; past half every off-16th shuffles, up to a triplet feel |
| **HUMN** | the groove untouched | the amount of VEL, ALT, SWNG and VAR: 64 plays them as set, 127 twice as far |
| **VAR** | the same bar every bar | fills at the end of each phrase; past half the groove changes from bar to bar and fills grow (two beats, sometimes a bar); near the top a fill at every bar's end |

HUMN is the master of the humanisation: at 0, VEL, ALT, SWNG and VAR do
nothing, and the groove plays as written. ORN and GHST are not scaled by
HUMN.

**The styles** (STYL): BRKB breakbeat, HHOP hip-hop, FUNK, HOUS house,
JUNG jungle, DUB one drop, AFRO afrobeat, CLAV son clave 3-2, BOSS bossa,
BMBE bembe 12/8, ROCK, DISC disco, TECH techno, TRAP, RNB r&b / neo-soul,
DEMB reggaeton dembow, SAMB samba, BAIA baiao, CUMB cumbia, GARA uk garage,
DSTP dubstep, SHUF blues shuffle 12/8, SIX8 6/8 afro, ELEC electro, DEEP
deep house, MINI minimal techno, AMAP amapiano, FTWK footwork, HILF
highlife. Every style plays the whole kit: bells, claves, rims and shakers
on the PERC slices, congas and the log drum on the TOM slices. A 12/8 style
plays bars of 12 steps.

### KIT BALANCE: the mix of the drums

![KIT BALANCE](../../img/drummer/balance.png)

Six rows, one knob each: **A KICK, B SNARE** (its ghosts too), **C HATS**
(closed and open), **D CYMB** (ride, crash), **E TOMS, F PERC**. The middle
tick (`=`) is the style as written. Left of it the drum plays less (`-20`
takes a fifth of its hits out, `OUT` all of them); right of it, more: first
the hits of the style's other levels, then (past the small tick, the bar
dotted) any free step for the light drums (hats, perc, ghosts) and the
8ths for the others. One detent is 5 %; turning stops once on the middle.

KIT BALANCE is saved in the Part: each Part has its own mix, and a Part
change brings it. The track's own trigs always play.

**Locks on steps and scenes.** KIT BALANCE takes parameter locks, as a
stock page does (PAGES' locks; the remix needs EVENTS):

- **On a step.** GRID RECORDING on, place a trig (TRIG, or FUNC + TRIG for
  a trigless one), hold it and turn A-F: that step locks the zone. The
  title reads `STEP n`; a zone with a lock shows its value, the others
  `--`. FUNC held while turning removes the lock. As on stock, the lock
  plays from its step to the track's next trig.
- **On a scene.** Hold SCENE A or B and turn A-F: the scene locks the
  zone (title `SCENE n`), and the crossfader morphs between the two
  scenes' mixes. FUNC held while turning removes it.

![KIT BALANCE: step 3's locks, trig 3 held](../../img/drummer/balance-step.png)

![KIT BALANCE: scene A's lock, SCENE A held](../../img/drummer/balance-scene.png)

The locks follow their trigs like stock's: a trig taken off takes its
locks, trig + PLAY clears them, and copying a trig, a track or a pattern
carries them. They are saved with the project (`pglocks.work`).

### NEXT: orders on the beat

![NEXT, an order armed](../../img/drummer/next-armed.png)

NEXT gives the drummer an order, the way a band leader would: "at the next
phrase, a triplet fill, and we stop". The order waits for the beat, bar or
phrase you chose and plays exactly there, however early or late you turned
the knob. The six cells sit like the knobs: A B C on top, D E F below.

| knob | what it does | values |
|---|---|---|
| **A WHEN** | sends the order | `--` (nothing armed), BEAT, BAR, PHRASE, 2 PHR |
| **B RUN** | stop or come back | `--`, STOP (the track's own trigs still play), SILENT (they are silenced too); while the drummer is stopped it reads RESUME |
| **C HOW** | how it stops or comes back | DRY, CRASH (a crash on the 1), FILL (a fill ending on the 1), FILL+CR, PICKUP (a half-beat lead-in; on a resume, then the crash) |
| **D FILL** | the order's fill (it plays one even with B on `--`) | `--`, TRIP, 6LET, RUDI, 3:4, LONG (a whole bar) |
| **E STYL** | another style from the 1 | `--` or a style; kept until you turn CONFIG's STYL |
| **F BRK** | a break from the 1 | `--`, 1 BEAT, 2 BEATS, BAR (BRK's cuts), STUTTER (a bar of stutter) |

**A takes four detents a value and arms once the knob rests** (half a
second): a small knock moves nothing, and turning through BEAT on the way to
PHRASE sends PHRASE, not BEAT. **Only A comes back to `--`.**
Set B to F once; every turn of A sends the
same order again (STOP, then RESUME, then STOP...). A `*` marks the cells
set and waiting for A. Turn A back to `--` before the order plays to cancel
it.

![NEXT: the order set, waiting for WHEN](../../img/drummer/next-ready.png)

The top of the page: the drummer's state (PLAYING, STOPPED) and what the
armed order will do, the bar of the phrase on the right; under it the
phrase across the whole screen, one cell a bar, filling up with the
playhead; a mark under the place the order plays, and the beats left beside
it. The order's values are inverted while it is armed, and blink through
the last four beats. When it plays, the line flashes and A is back to `--`.

![NEXT: the last beat before the order](../../img/drummer/next-close.png)

![NEXT: the order played, the drummer stopped](../../img/drummer/next-stopped.png)

Stopped, the drummer keeps counting in silence, so a RESUME comes back in
the groove, on the 1. A fill (C on FILL, FILL+CR or PICKUP, or D set) needs
the order on a bar's 1: with A on BEAT in the middle of a bar, the order
plays without its fill. The fill is as long as FILLS' LONG says (KIT window
page 4), a beat on AUTO, a bar with D LONG.

Armed while the sequencer is stopped, an order plays on the first step:
STOP armed before PLAY starts the pattern without the drummer, ready to come
in on the next order. B to F are saved in the Part; A is not (an order is a
gesture: a project always loads with nothing armed).

### The KIT window

Hold any **trig key** and press **BANK** (BANK alone still selects a bank).
One row a slice, four pages: **LEFT / RIGHT** change page, **UP / DOWN**
move from slice to slice and play it, a **trig key** jumps to that slice
and plays it, **YES** or **NO** closes. **FUNC + RIGHT** makes the kit
again from the sound (AUTO; asked first).

**Page 1: what each slice is.**

![KIT window, page 1](../../img/drummer/kit-zones.png)

- **A ZONE**: the drum the slice plays: KICK, SNARE, GHOST, HAT C, HAT O,
  RIDE, CRASH, TOM, PERC, a two-drum combo (a kick and a crash hit
  together, say), or OUT (never played as a drum).
- **B ROLE**: ACC (accent: loud hits), NRM, SFT (soft hits). DRUMMER picks
  the role from the hit's level: a loud snare plays an ACC snare, a soft
  one an SFT snare.
- **LNK** shows `=n` on slices AUTO found to be copies of slice n
  (SIMILAR, page 3).

**Page 2: timing, level, scene.**

![KIT window, page 2](../../img/drummer/kit-align.png)

- **A ALGN**, 0-250 ms: the slice starts that much early, so a hit that
  sits late in its slice lands on the step. AUTO sets it when it finds the
  hit late in the slice.
- **B GAIN**, -24 to +6 dB: the slice's own level, on top of the hit's
  velocity. On a linked slice, its whole group turns.
- **E SCN**, -- or 1-16: a scene of the Part played on this slice's hits
  only (its LFO, AMP, FX1 and FX2 locks for this track). Keep a few scenes
  for the slices (9-16, say) and the others for the crossfader. A delay
  send on one slice only, a filter on the open hat...
- **F DOSE**, 5-100 %: how far towards the scene's values.

**Page 3: the track.**

![KIT window, page 3](../../img/drummer/kit-track.png)

- **A SHIFT**: ON, a light hit (ghost, hat, perc) that loses a collision
  with a louder one moves to the next free step instead of being dropped.
- **B PHRASE**: 4 or 8 bars, the phrase VAR's fills and crashes follow.
- **C SIMILAR**: how close two slices must sound for AUTO to call one a
  copy of the other (OFF, 1-15; 6 by default).
- **D COPIES**: what AUTO does with the copies: OUT (out of the kit) or
  LINK (kept, linked: their GAIN turns together).
- **E KIT FILE**: turn E to save the kit in a file beside the sample. The
  next time that sample goes on a DRUMMER track, its kit loads without the
  question.
- **F REDRUM**: OFF, AUTO, 1, 2, 4 or 8 BARS (see *REDRUM* below). The row
  shows what REDRUM understood of the loop, e.g. `AUTO 1BAR 16SL`.

SIMILAR and COPIES act at the next AUTO. The kit, GAIN, ALIGN, SCENE,
DOSE and the page 3 settings are saved with the project, per track.

**Page 4: FILLS, the fills' vocabulary.**

![KIT window, page 4](../../img/drummer/kit-fills-set.png)

Six choices, each AUTO first (AUTO lets the style, VAR and ORN decide). A
filled box marks a choice made by hand:

| knob | choices |
|---|---|
| **A FILL** | the kind of every fill: WRIT (the style's written fill), RUDI (drum rudiments), TRIP (triplets), 3:4 (groups of three over four) |
| **B FREQ** | when: AUTO (BRK's fills, and VAR's), BRK (only when BRK asks), 2BAR (BRK's, every second bar), PHRS (BRK's, at the phrase's end) |
| **C LONG** | how long: AUTO (BRK's zone says), 1BT, 2BT, BAR |
| **D STIK** | one sticking of the kind chosen in A (`--` while A is AUTO or WRIT) |
| **E ORCH** | which drums: TOMS (right hand round the toms, left on the snare), SNR (all on the snare), SWAP |
| **F TRIP** | triplets: 8TH (8th triplets), 6LET (sextuplets), 8>6 (8ths turning into sextuplets on the last beat). Set while A is AUTO, the fills become triplets |

The stickings (D): rudiments SNGL single stroke, DBLE double stroke, PARA
paradiddle, INVP inverted paradiddle, PDDL paradiddle-diddle, SIXS
six-stroke roll, DPAR double paradiddle, LIN3 / LIN4 linear with the kick,
FTAP flam tap, DRAG single drag tap, RTMQ ratamacue, FIVE five-stroke roll;
triplets TRPL single stroke, RLL, SIXS six-stroke, PDDL paradiddle-diddle,
LIN linear, SWIS Swiss army triplet, FACC flam accent; 3:4 TSS
(tom snare snare), LIN, KSS (kick snare snare), FSS (flam snare snare).

FILLS is saved in the Part, like KIT BALANCE. Changed while the pattern
plays, the next fill takes it. For one fill different from these, use NEXT's
D FILL.

## How a kit is made

**AUTO** listens to each slice: how much low end, how much high end, how
long it rings. A lot of low end is a kick; high end and little low a hat
(open when it holds); a ring of a second or more a cymbal; some highs over
less low end a snare (a soft one a ghost); a lower ring a tom; anything else
a perc. Within each drum, the loudest slices become ACC and the softest
SFT. AUTO is a proposal: correct a zone in the KIT window, page 1, and it
plays at once.

**SIMILAR.** A loop often hits the same sound many times (a two-bar loop
whose second bar repeats the first). AUTO spots the copies and keeps one
of each: with COPIES on OUT the others leave the kit (the toast says
`5 SIMILAR OUT`), with LINK they stay and are linked. A copy 6 dB softer or
more is kept as an SFT.

**Collisions.** A track plays one slice at a time. When the groove asks for
two drums on one step, a combo slice holding exactly those two plays; else
the drum first in the priority (kick first, then snare, then the others).

## REDRUM: your loop as the groove

With REDRUM on, DRUMMER places every slice where it falls in your loop
(its place off the 16th kept, so the feel survives) and that loop becomes
the groove. **HUMN 0, SEED 0, CPLX 64** replays the loop as it is, each step
its own slice. Then the knobs bend it:

| knob | under REDRUM |
|---|---|
| ALT (with HUMN) | now and then a slice is swapped for another of the same drum: the re-drum |
| SEED | moves, empties and fills hits, as on a style |
| DENS | thins the loop below 64 (the backbone kept) |
| CPLX | 0: the loop without its soft slices and ghosts; 64: the loop; 127: the loop plus the style's COMPLEX hits on the steps the loop leaves free (the loop's own hits never lose) |
| GHST, VAR, ORN, BRK, VEL | as on a style: ghosts, changing bars, ornaments, fills and breaks, dynamics |
| STYL | gives its fills (and their colour), not its groove, swing or lay-back: the loop has its own |
| KIT BALANCE | as on a style, per drum |

Slices that SIMILAR put OUT of the kit still play on their own steps, as
they are (KIT BALANCE and SEED do not reach them); with COPIES on LINK they
stay in their drum and every knob reaches them.

**How long is the loop?** REDRUM needs the loop's length in bars to lay it
on the steps. On **AUTO** it reads the slot's attributes (its length in bars,
else its tempo) and takes the nearest of 1, 2, 4 or 8 whole bars. A slot
that never had its own tempo takes the project's, which can make a 150 BPM
loop read as 6.4 bars at 120: AUTO rounds it to 8. When the row shows the
wrong number of bars, **set it by hand**: 1, 2, 4 or 8 BARS on F. A forced
length ignores the slot's tempo, so the loop follows the project at any
tempo.

A loop longer than the pattern simply goes on: a 4-bar loop on a 16-step
pattern plays its four bars over four passes.

## Configurations

**A steady groove for a song.** CONFIG: the style, HUMN 0. LIVE: SEED 0,
DENS 64, CPLX 64, BRK 0. Every bar the same, the style as written.

**A human drummer.** HUMN 64, VEL 64, SWNG 40-70, ALT 40. Add VAR 40 for
fills at the phrase's end, ORN 32 for flams and rolls, GHST 40.

**More and less.** DENS and CPLX are the two "busier" knobs: CPLX walks
through the written levels (more parts, more syncopation), DENS thins or
fills at random around them. A breakdown: DENS 20. A peak: CPLX 127,
DENS 90.

**Breaks on the crossfader.** Put BRK on a scene: hold SCENE B, turn BRK
to 56 (a bar of fill) or 110 (stutters); SCENE A keeps BRK 0. The
crossfader then takes the drummer from the groove to the break and back,
and a fill of a beat or more lands on a crash.

**Fills only where you want them.** KIT window page 4 (FILLS): FREQ on BRK (no fill unless BRK
asks), LONG 1BT; then a scene with BRK 40 on the crossfader gives a one-beat
fill on demand. FREQ 2BAR or PHRS: every second bar, or at the phrase's
end.

**Triplet fills.** KIT window page 4 (FILLS): TRIP 6LET (sextuplets), FILL on AUTO or TRIP.

**An ending.** NEXT: B STOP, C FILL+CR, D LONG. Near the end of the song
turn A to PHRASE: a bar of fill, a crash on the next phrase's 1, then
silence. A to PHRASE again (B now reads RESUME), C PICKUP: the drummer comes
back in on a lead-in and a crash.

**Drop the drums for a bar.** NEXT: B STOP, C DRY. A BAR stops on the next
bar; A BAR again brings it back on the one after. With B SILENT the
track's own trigs stop too.

**Change style on the phrase.** NEXT: E to the next style, B `--`. A PHRASE:
the new style from the phrase's 1; turning CONFIG's STYL gives the knob
back.

**One slice, one effect.** KIT window page 2: give the open hat SCN 9, and
on scene 9 lock the track's filter; the open hat plays filtered, the rest
untouched. A delay send on the snare alone, a pitch on the toms...

**Two drummers.** Two DRUMMER tracks on the same loop, different SEEDs or
styles, one with KIT BALANCE keeping kick and snare, the other hats and
perc.

**Your own kit from one-shots.** A computer tool beside the module
(the kit maker) turns a folder of single hits
into one sliced sample with its kit file, ready for the card.

## Tutorial 1: a drummer from a sliced loop

You need a drum loop of one or two bars on the card.

1. **Load and slice.** On track 1, load the loop on a FLEX machine. AED
   (audio editor), SLICE: *create slice grid*, 16 slices for one bar (32
   for two bars). Check that each slice starts on a hit.
2. **Make it a drummer.** FUNC + SRC, scroll to **DRUMMER**, **YES**, then
   **NO** to close. To *This track has no kit yet* answer **YES**: the
   toast says how many slices it sorted.
3. **Check the kit.** Hold trig 1, press **BANK**: the KIT window, page 1.
   UP / DOWN plays each slice with its zone. A hat called a perc? Turn A
   to HAT C. Close with **NO**.
4. **Pick a style.** FUNC + SRC (CONFIG), turn **STYL** to FUNK. HUMN 0.
   **PLAY**: a straight funk groove with your loop's sounds.
5. **Shape it.** SRC (LIVE). CPLX 0: the simplest funk; 127: the busiest.
   DENS 30: sparse. Back to 64 and 64. Turn **SEED** slowly: each value is
   another drummer's take on the same style; `TBL` is the book.
6. **Make it breathe.** CONFIG: HUMN 64, VEL 70, SWNG 50, ALT 40. LIVE:
   GHST 50, ORN 32. Now the snare lays back, the hats swing, ghosts and
   flams come in.
7. **Mix the drums.** SRC again (KIT BALANCE). Hats to `-40`, kick to
   `+20`. KIT window page 4 (FILLS): FILL RUDI, ORCH TOMS.
8. **Breaks.** Hold SCENE B and turn BRK to 56 on LIVE; let go. Hold
   SCENE A, BRK 0. Move the crossfader towards B near the end of a bar: a
   tom fill, landing on a crash. Further on a second scene, BRK 110:
   stutters.
9. **Stop on the phrase.** SRC again (NEXT): B STOP, C FILL+CR. Turn A
   to PHRASE: the countdown runs, a fill, a crash on the 1, silence. Turn
   A to PHRASE again: the drummer is back on the next phrase.
10. **Save.** SAVE PROJECT keeps the kit, the knobs, KIT BALANCE, FILLS and
   NEXT's orders.
   KIT window page 3, E: the kit file, so this loop never needs the
   question again.

## Tutorial 2: REDRUM, re-drum your break

You need a loop whose groove you like, sliced one hit a slice.

1. **Set up** as in tutorial 1, steps 1-3 (load, slice, DRUMMER, AUTO
   YES). For a loop with many repeated hits, set page 3's COPIES to LINK
   *before* AUTO (or press FUNC + RIGHT in the KIT window to redo it), so
   every slice stays in its drum.
2. **Turn REDRUM on.** KIT window, page 3 (RIGHT twice), turn **F** once:
   `AUTO 1BAR 16SL`. Check the bars: a one-bar loop must read 1BAR, a
   two-bar loop 2BAR. Wrong? Turn F on to the right number of bars.

   ![REDRUM on, page 3](../../img/drummer/redrum.png)

3. **Hear the loop itself.** CONFIG: HUMN 0. LIVE: SEED 0, CPLX 64,
   DENS 64, BRK 0, GHST 0, ORN 0. **PLAY**: your loop, slice by slice, as it
   was played, now following the project's tempo.
4. **Re-drum it.** CONFIG: HUMN 64, ALT 60: now and then a snare is
   another snare, a kick another kick. LIVE: turn SEED: hits move, drop
   out, appear, always the loop's sounds.
5. **Thin and thicken.** CPLX 0: the loop without its ghosts and soft
   hits, a stripped break. CPLX 127 with STYL HOUS: the loop plus house
   hats on the steps it leaves free. DENS 30: a sparse version.
6. **Fills and breaks.** STYL picks the fills' colour (ROCK, FUNK,
   JUNG...). KIT page 4 (FILLS): TRIP 6LET for sextuplet fills. Put BRK 56 on a scene
   for a bar of fill on the crossfader, BRK 110 for stutters; a fill lands
   on a crash.
7. **Feel.** VEL 60 brings dynamics back on the beats; GHST 40 adds ghost
   notes the original never had.
8. **Back to the source.** HUMN 0, SEED 0, CPLX 64: the original loop
   again. REDRUM is a setting per track, saved with the project; OFF gives
   the style back.
