## What it does

BRAIN is the settings store on the panel: card-wide knob defaults,
templates, module settings, live performance screens, and the remix
switcher.

## Where to find it

PROJ (MAIN MENU), then BRAIN, the fifth category. The pane is one list,
the most used first: TEMPLATES, REMIXES, SETTINGS, PERFORMANCE, LOG,
ABOUT. UP and DOWN move the cursor, YES acts on the row, NO goes back to
the menu.

### TEMPLATES

A template is a named record: an effect's page, a MIDI track, the
project's settings, or a whole Part. Four tabs, LEFT and RIGHT between
them: PART, FX, MIDI, PROJECT. Reopens on the tab last used.

Each tab is a list under a NEW row. YES on NEW opens the name editor on
the next free name; YES writes the template (a name the target already
has is refused, NAME IN USE). YES on a template opens its screen: the
actions APPLY TO..., SET AS DEFAULT or CLEAR DEFAULT, SAVE, RENAME and
DELETE, then a VALUES list. LEFT and RIGHT change a value by one and the
encoder by its turn. NO goes back; with unsaved changes it asks SAVE
CHANGES?

- A **PART template** is a whole Part, in sections: FX, LFO, INPUT SRC,
  MIDI TRACKS, SCENES, MACHINES. APPLY TO... asks for a section: WHOLE
  PART, or a section FROM ALL TRACKS or FROM Tn ONTO Tm. What it leaves
  as the project had them: the sample slots, the AMP pages, the FLEX and
  STATIC SRC pages and the levels. SET AS DEFAULT makes Part Clear and
  every Part of a new project start from it.
- An **FX template** is one effect's page; APPLY TO... asks onto which
  FX1 or FX2 slot, and onto a slot with another effect the effect is
  replaced. SET AS DEFAULT makes its values the effect's when newly
  selected.
- A **MIDI TRACK template** is a MIDI track's pages; it applies onto any
  MIDI track.
- A **PROJECT template** lists groups: AUDIO, INPUT, SEQUENCER, MIDI
  SEQUENCER, MEMORY, METRONOME, MIXER, MIDI CONTROL, MIDI SYNC, MIDI
  CHANNELS, each with its stock screen's rows. APPLY TO PROJECT writes
  the settings; SET AS DEFAULT makes them the settings of every new
  project (CREATE EMPTY PROJECT).

### REMIXES

REMIX SWITCH: each `.RMX` in `/BRAIN/REMIXES/`, sorted. The one whose
name matches the running image (case and spaces ignored) has `RUNNING`
at the right. YES asks `BOOT <NAME>?`; YES boots it without writing the
flash. After a switch, a `FLASHED` separator shows the image a
power-cycle returns to.

### SETTINGS

APPLY DEFAULTS (a checkbox; off, every effect takes the image's
defaults), then a heading per module that declares a setting and a value
row per setting. YES steps the value, wrapping; LEFT and RIGHT step it
down and up and stop at the ends. A value that takes effect at the next
boot ends in `*`, with `* AT NEXT BOOT` under the list. BRAIN's own MIDI
LOG and EVENT LOG live in LOG.

### PERFORMANCE

Seven tabs, LEFT and RIGHT between them (the title names the tab and its
place, `DSP 3/7`); UP and DOWN scroll; redrawn every half second.

- **LOAD**: a bar for the frame interrupt's share of the ColdFire
  (CFIRE) and one for each DSP core's busy time over its frame; WORST
  FRAME, the longest single frame-interrupt run since opening, as a
  share of the frame (`OVER` at 100%).
- **CPU**: each ColdFire task's share of the time, FRAME IRQ first, then
  the tasks by share.
- **DSP**: each effect call's cost, measured around each FX1 and FX2
  call, as cycles a sample and share of that core's frame, sorted by
  cost, with a SYSTEM A and SYSTEM B row for the rest of each core's
  busy time. Without LOAD METER the bars stay empty and DSP says so.
- **MEM**: octabam's DRAM (reserve, runtime, stage and regions), then
  the audio page arena that is left: FLEX USED, FLEX FREE, RECORDERS,
  ARENA, IN USE.
- **CARD**: reads and writes since boot as commands and KB, and the
  slowest command in ms.
- **MIDI**: messages a second and counts by kind (notes, controllers,
  program, bend and pressure, system, clock).
- **USB**: AUDIO OUT and AUDIO IN underruns and overruns and MIDI OUT
  drops; `NOT IN THIS IMAGE` when the image has none of those modules.

### LOG

Two tabs, LEFT and RIGHT between them.

- **EVENTS**: an EVENT LOG checkbox (default on; off, none are noted),
  then the last 40 events, newest first, each with the uptime it
  happened at: FRAME OVER, CPU FULL, CARD SLOW.
- **MIDI**: a MIDI LOG checkbox (the debug log records MIDI messages),
  WRITE DEBUG LOG (the last 256 MIDI messages, clock and active sensing
  left out, written to `/BRAIN/debug.txt`), and the last 24 messages
  decoded, newest first.

### ABOUT

Four tabs, LEFT and RIGHT between them.

- **IMAGE**: the image's name, the remix it was built from, the stock OS
  it is built on (1.40C) and the number of modules.
- **CARD**: BRAIN's card file as the last load or write left it
  (LOADED, NO FILE YET, FROM card.strd, DAMAGED), its size in KB of the
  64 the buffer holds, and the number of templates and defaults in it.
- **PROJECT**: what the last load found when it compared the project's
  BRAIN record with the image: SAVED WITH THIS IMAGE, N EFFECT(S)
  CHANGED SINCE THE SAVE, NO RECORD OF A SAVE, or BRAIN FILES BAD.
- **MODULES**: each module's key and its first author, alphabetical.

## The page shortcut

Hold a page key (SRC, AMP, LFO, FX1, FX2) and press FUNC: a list opens
over the page with SAVE FX DEFAULT, CLEAR FX DEFAULT, SAVE TEMPLATE,
LOAD TEMPLATE and DELETE TEMPLATE. They act on the track and page in
view. Over SRC it says to open an LFO, AMP or FX page. On a MIDI track
the list has a sixth row, NAME KNOB: a name (four characters) for each
of the track's ten assignable CCs, drawn on the CTRL1 and CTRL2 pages;
an empty name clears it.

## SAVE FX DEFAULT

Makes the current Part's page of that track's FX1 or FX2 the effect's
default on the card: a newly selected effect comes up with that page.
CLEAR FX DEFAULT removes it. SAVE PROJECT copies the card's defaults to
the recovery copy (card.strd).

## Screens

![The MAIN MENU](../../img/brain/menu.png)

![The menu scrolled to the last row](../../img/brain/menu-b5.png)

![The BRAIN pane of the menu](../../img/brain/pane.png)

![The TEMPLATES screen](../../img/brain/templates.png)

![The REMIXES screen](../../img/brain/remixes.png)

![The SETTINGS screen](../../img/brain/settings.png)

![The PERFORMANCE screen](../../img/brain/performance.png)

![The LOG screen](../../img/brain/log.png)

![The ABOUT screen](../../img/brain/about.png)
