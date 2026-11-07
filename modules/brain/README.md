# `brain` — BRAIN

The settings store's run-time side on the unit (`git show 76fd8466:docs/proposals/BRAIN.md`).
A remix lists it to give the card layer to its knob defaults.

It applies card-wide knob defaults and writes them: SAVE FX DEFAULT
(`brain_post_save(track, fx)`) makes the current Part's page of that track's
FX1 or FX2 the effect's default in `card.work`, and SAVE PROJECT copies
`card.work` to `card.strd`.

## On the panel

PROJ (MAIN MENU), then BRAIN, the fifth category. Its pane is one list, the most used first (TEMPLATES, REMIXES, SETTINGS, PERFORMANCE, LOG, ABOUT); each row opens a full screen like the stock MIDI SYNC (the BRAIN icon at the left and the title at the right of the first band, a rule, then rows with the inverted cursor bar) UP and DOWN move the cursor, YES acts on the row, NO goes back to the menu.

| row | screen |
|---|---|
| TEMPLATES | Four tabs, LEFT and RIGHT between them: PART, FX, MIDI, PROJECT (`FX 2/4`, a triangle on each side that has more tabs; reopens on the tab last used). Each tab is a list under a NEW row; YES on a template opens its screen, which has the same actions on every template and then its values. Described under TEMPLATES below |
| REMIXES | REMIX SWITCH's rows (`modules/remix-switch`, sanderlegit): each `.RMX` in `/BRAIN/REMIXES/`, sorted; the one whose name matches the running image (case and spaces ignored) has `RUNNING` at the right; YES asks `BOOT <NAME>?` and YES boots it without writing the flash; after a switch a `FLASHED` separator and the image a power-cycle returns to |
| SETTINGS | `BRAIN`: APPLY DEFAULTS (a checkbox; off, every effect takes the image's defaults), then a heading per other module that declares a setting and a value row per setting (below). YES steps the value (wrapping), LEFT and RIGHT step it down and up and stop at the ends; a Binary setting is a checkbox (crossed when on); after a change to a value that takes effect at the next boot, leaving SETTINGS shows the popup `REBOOT TO APPLY CHANGES`. BRAIN's own MIDI LOG and EVENT LOG are in LOG. `NO MODULE SETTINGS` in a remix with none |
| PERFORMANCE | Seven tabs, LEFT and RIGHT between them (the title names the tab and its place, `DSP 3/7`), UP and DOWN scroll, redrawn every half second. **LOAD**: a bar for the frame interrupt's share of the ColdFire (`CFIRE`) and one for each DSP core's busy time over its frame, the peak since opening a mark on each (`-` before a sample, `?` when the records since the last tick were all bad), `WORST FRAME` (the longest single frame-interrupt run since opening as a share of the 362.8 µs frame, `OVER` at 100%). No ESAI drop count: core 0 counted the ESAI transmit underrun and receive overrun frames until 13 Oct 2026 (never seen non-zero on a unit, `docs/firmware/ARCHITECTURE.md`); the room went to the DSP tab. **CPU**: each ColdFire task's share of the time, `FRAME IRQ` first, then the tasks by share (`IDLE` is the main task's spin at priority 0). A detour in the scheduler's entry (`0x40000554`, trap #0 and PIT0, after its `movew #0x2700,%sr`: on `0x40000550` itself an interrupt could enter the scheduler again before the mask rose on a trap #0 entry, and a task resumed at a garbage PC under the port) charges the DMA timer 3 counts since the previous entry to the task that was running (`brain_ts`, 11 TCBs from `docs/firmware/KERNEL.md` and an OTHER slot); the sampler turns the counts of each half second into shares. The frame interrupt's time lands on the task it interrupted, so it is shown on its own row and taken off the tasks in proportion to their shares, which assumes the interrupt arrives independently of the task switches (inferred). Other interrupts stay inside the tasks. Four of the tasks have no known purpose and are named by their entry (`TASK 91D18`). **DSP**: each effect call's cost, measured by the DSP cores around each FX1 and FX2 call (`modules/load-meter`), as `T5 2 BusVerb79  996 22%` (track, FX slot, effect, cycles a sample, share of that core's frame; under 10% with a tenth), sorted by cost, with a `SYSTEM A` and `SYSTEM B` row for what each core's busy time holds beyond its effects. **MEM**: octabam's DRAM from the build, `DRAM RESERVE` (the platform's pages at the bottom of the audio arena: the arena base the build moved to less the stock base `0x40a955e0`), `RUNTIME` (code, data and bss, linked at the stock base: the linker's `_end`) and `STAGE, REGIONS` (the rest of the reserve: the loader stage, DRAM regions, fixed claims, page rounding); then the audio page arena that is left (`modules/memory/README.md`): FLEX USED, FLEX FREE, RECORDERS, ARENA in MB (6,144-byte pages), IN USE. The DRAM rows are sizes fixed at build, not live use (`test/brain`, before it was removed, read 10.0 MB reserve, 3.3 MB runtime, under the port). **CARD**: reads and writes since boot as commands and KB, and the slowest command in ms, counted by a detour pair on the ATA dispatcher (`0x4001513c` entry, `0x40015284` common exit; opcode `0x46c8656d`, sector count `0x46c8656c`, timed by DMA timer 3 at 132 MHz). **MIDI**: messages a second and counts by kind (notes, controllers, program, bend and pressure, system, clock; counted before the MIDI LOG switch is read). **USB**: AUDIO OUT and AUDIO IN underruns and overruns and MIDI OUT drops, read from `usbaudio_*`, `in_counters` and `usbmidi_tx_drops`; `NOT IN THIS IMAGE` when the image has none of those modules. Without LOAD METER the bars stay empty and DSP says so. A sampler timer, started at the first project load, runs for good: it samples the processors every half second, keeps the MIDI rate and notes the EVENTS |
| LOG | Two tabs, LEFT and RIGHT between them (the title names the tab, `EVENTS 1/2`); the cursor walks every row. **EVENTS**: an `EVENT LOG` checkbox (a setting, default on; off, none are noted), then an `EVENTS` heading and the last 40 events (`NO EVENTS YET` under it when there are none), newest first, each with the uptime it happened at (the sampler's tick count at 0.5 s, the timer's nominal period): `FRAME OVER` (the frame interrupt's run reached the 363 µs frame, in µs), `CPU FULL` (a processor at 100%), `CARD SLOW` (an ATA command over 100 ms, in ms). **MIDI**: a `MIDI LOG` checkbox (the debug log records MIDI messages; off, the MIDI thread's handler call returns at once after the handler), `WRITE DEBUG LOG` (the last 256 MIDI messages, clock and active sensing left out, each with the sync flags, the playing pattern and the next pattern after its handler ran, written to `/BRAIN/debug.txt` by the engine task; a popup says so when MIDI LOG is off) and the last 24 messages decoded, newest first (`CH01 CC 7= 20`, `CH01 PC 2 P3`: the pattern the program change queued, `CH02 NOTE 36 100`), redrawn every half second |
| ABOUT | Four tabs, LEFT and RIGHT between them (`PROJECT 2/4`). **IMAGE**: the image's name (`BRAIN 79`), the remix it was built from (`BRAIN`, its last path part), the stock OS it is built on (`1.40C`) and the number of modules. No build date or commit: the image is bit-identical for the same inputs (`scripts/refhash.sh`), and a date would end that. **CARD**: BRAIN/card.work as the last load or write left it (`LOADED`, `NO FILE YET`, `FROM card.strd` when `card.work` was damaged and `card.strd` was read, `DAMAGED`), its size in KB of the 64 the buffer holds, and the number of templates and defaults in it (records whose CRC is good). **PROJECT**: what the last load found when it compared the project's BRAIN record with the image: `SAVED WITH THIS IMAGE`, `N EFFECT(S) CHANGED SINCE THE SAVE`, `NO RECORD OF A SAVE`, `BRAIN FILES BAD`, and under it each changed effect with `MOVED` (its FX id names another store), `LAYOUT` (same store, another layout hash) or `GONE` (the image has no such store); up to 12, a gone store by its id. **MODULES**: each module's key and its first author, alphabetical, from a table the build writes. Scrolled by UP and DOWN |

### TEMPLATES

A template is a named record of kind 3 in `card.work`, per target: an effect (its page's twelve values), a MIDI track, the project's settings, or a whole Part. No page needs to be open. The FUNC shortcut (hold a page key, FUNC) still saves and loads the page in front, under a name asked for, and for the AMP, LFO and SRC pages too (`stock.amp`, `stock.lfo`, `stock.static` ... records); those three have no tab in TEMPLATES since 13 Oct 2026: a PART template applied by section and track does what they did, so a page template of those kinds is reached only by the shortcut's LOAD TEMPLATE and DELETE TEMPLATE.

**The list.** Under the tab's NEW row (`<NEW PART TEMPLATE>`) the tab's templates, names alphabetical (a heading per target: the effect on the FX tab, the tab's own name on the others); a template that is its target's default ends in `*`; redrawn every half second. NEW opens the stock name editor (`0x4007e664`) on the next free name (`PART 01`; `CHAR 01`, an effect's four-character abbreviation, its descriptor's `P + 4`; `MIDI 01`; `PROJ 01`); YES writes the template under the name (NO writes nothing; a name the target already has is refused with `NAME IN USE`, since a save under it would replace that template) and, once it is on the card (a soft timer polls, up to about six seconds), opens its screen. NEW FX TEMPLATE asks for the effect first (a list of the image's effects, alphabetical). NEW MIDI TEMPLATE and NEW FX TEMPLATE are the descriptor's default values (`E + 0x96`; an effect's are its current defaults); NEW PART TEMPLATE is the current Part; NEW PROJECT TPL the current project's settings.

**A template's screen.** The title is its target (`PART`, `CHARACTER`, `MIDI TRACK`, `PROJECT`). First the actions, the same on every template: `APPLY TO...` (`APPLY TO PART`, `APPLY TO PROJECT`), `SET AS DEFAULT` or `CLEAR DEFAULT` (PART, PROJECT and effects), `SAVE`, `RENAME` (its name at the right; YES: the stock name editor) and `DELETE`; the cursor opens on the first. Then a `VALUES` line and the values, by the name in the target's page descriptor (`E + 0x4e`, six characters; an empty position `---` is left out), as the page shows them (the slot's formatter `E + 0x102`, PARAM_PAGES.md section 7, called with a 16-byte buffer, eight characters shown: `+0`, `TAPE`, `SELF`; the number when the slot has none). LEFT and RIGHT change a value by one and the encoder by its turn (at most 8 a click), stopping at the descriptor's range; SAVE has the engine task rewrite the record. NO goes back to TEMPLATES with the cursor on the template's row (the stock NO path runs the exit member and opens the menu's state 1; a soft timer reopens TEMPLATES a moment later, so the menu can show for one redraw); with unsaved changes it asks `SAVE CHANGES?` there (YES saves). When the menu closes from the screen (the window `0x400cbf4c` is 0 at the timer), unsaved changes are saved. DELETE removes the template and goes back to TEMPLATES with a `DELETED` popup; the list leaves it out from the start, while the engine task's write is still to land.

**FX and MIDI TRACK templates.** APPLY TO... asks onto which slot or track: an effect onto any FX1 or FX2 slot whose chooser lists it (`T2 FX1`); onto a slot with another effect, the effect is replaced: the Part with that slot's id and its twelve page values (the template's, the descriptor's defaults for the rest) through the stock Part paste `0x40029a4c(src, p)`, which writes the working Part and its CS1 copy, sets the unsaved bit and applies it to the engine (under the port, T2 FX1 went from id 0x04 to CHARACTER's 0x1c in the Part and in the live id array `0x80000ec4`; not on hardware). A MIDI TRACK template goes onto any MIDI track, with its knob names. SET AS DEFAULT on an effect makes its values the stored default `card.work` applies to a newly selected effect.

**PROJECT templates.** A PROJECT template lists groups instead, YES opening one and NO going back to them: AUDIO, INPUT, SEQUENCER, MIDI SEQUENCER, MEMORY, METRONOME (the stock CONTROL screens), MIXER, MIDI CONTROL, MIDI SYNC and MIDI CHANNELS (the stock MIDI screens), each with the rows its stock screen has. A row's label, its drawn value and its step are stock's own: the screen's getter (it returns the string the screen draws) and setter (`(delta, wrap)`, as that screen's key handler calls it: LEFT and RIGHT `(±1, 0)`, YES `(1, 1)`, on MIDI SYNC YES `(0, 0)`), from the screens' tables (`0x400b277c..0x400b2a0c`; MEMORY's row records at `0x400cc834`), called with interrupts off on the template's bytes swapped into the live settings, their CS1 mirror and MEMORY's pending copy (`0x460e4550`), then swapped back; the live settings are unchanged (read before and after, under the port). Four setters also tell the engine (TRACK 8, CUE CFG, AUDIO NOTE IN, CLOCK RECV): those step the byte here with the setter's own rule. The MIXER's knobs are 0..126, drawn as the byte less 64 with its sign (DIR as the byte), as the mixer page draws them (measured under the port). PATTERN TEMPO, MAIN TO CUE, MIDI SOFT THRU and TRIG MODE MIDI are stored and not listed (no stock screen in this image draws them). APPLY TO PROJECT writes the settings bytes and their CS1 mirror. SET AS DEFAULT makes them the settings of every new project (CREATE EMPTY PROJECT; the detour at `0x40085176`, hooks.s `brain_on_newproj`).

**PART templates.** A PART template is a Part: its 6,322 bytes as one Blob value (the long length form: `0xff`, a u32 length), and the name of the project folder it was taken in as a second (store `stock.part2`, layout `PRT2`; the 208-byte `stock.part` records of 13 Oct's first build are not read). `card.work` holds up to 64 KB, ten of them. What a PART template shows, edits and applies is what means the same in any project, so it leaves out the sample slots, the AMP pages, the FLEX and STATIC SRC pages (shaped around a sample) and the levels; the Part holds them and the template keeps them in its image without reading them. The sections:
- `FX`: the FX1 and FX2 ids and both pages of each track.
- `LFO`: the three LFOs of each track (both pages), and the LFO designer shapes when taken for all tracks.
- `INPUT SRC`: the SRC pages of the THRU, NEIGHBOR and PICKUP machines (inputs, volumes, record settings), 36 bytes a track.
- `MIDI TRACKS`: a MIDI track's two pages.
- `SCENES`: a track's lock in each of the 16 scenes; scene A and B with all tracks. The MIDI SCENES module's lock table is not in a Part and not in a template.
- `MACHINES`: each track's machine type.

**The screen** (below `TAKEN IN`, the project it was taken in): one row per section, YES opens it, NO goes back a level with the cursor on the row left. MACHINES: the eight machine types (LEFT and RIGHT step STATIC, FLEX, THRU, NEIGHBOR, PICKUP). FX: the sixteen slots (`T1 FX1`, its effect's name at the right; LEFT and RIGHT change the effect to the next or previous id its chooser lists, NONE first, its values the new effect's defaults; YES opens the slot's values by the effect's page descriptor). LFO and MIDI TRACKS: the tracks (`T1`...`T8`, `M1`...`M8`), YES opens a track's page, its slots by the stock page descriptors with their formatters (`SPD1 32`, `NOTE C 3`, `LEN 1/16`). INPUT SRC: the tracks whose machine in the template is THRU, NEIGHBOR or PICKUP, each its machine's page (`INAB A B`, `VOL +63`). SCENES: SCENE A and SCENE B (1-16). The values are bytes of the template's Part image (`ted_part`, copied from the record when the screen opens); SAVE writes the image back whole.

**APPLY TO...** asks for a section (`WHOLE PART`, `FX`, `LFO`, `INPUT SRC`, `MIDI TRACKS`, `SCENES`, `MACHINES`), then for a section a track:
- `WHOLE PART`: every section above.
- `FROM ALL TRACKS`: each track onto itself (with the section's extras: the LFO designer shapes, scene A and B). Or `FROM Tn` then `ONTO Tm`: track n of the template onto track m of the current Part (what the AMP, LFO and SRC templates did). An FX section whose ids are not in this image's choosers is refused (`EFFECT NOT IN IMAGE`).
- The apply is `part_merge` on a copy of the working Part and the stock paste; with MACHINES in it, the calls Part Reload makes follow (PARTS.md section 2: `0x40009848(bank, part)`, then `0x400972fc(part, track, old)` for each track, `old` the machine it had).

Measured under the port (13 Oct 2026; `verify_brain`, 118 checks, run alone): NEW PART TEMPLATE writes one `stock.part2` record, the Part's 6,322 bytes and the project's name; APPLY TO..., FX, FROM T1 ONTO T2 sets T2's FX1 and leaves T2's AMP; WHOLE PART makes every section equal the template's (FX ids and pages, LFO, the LFO designer shapes, INPUT SRC, MIDI TRACKS, SCENES, scene A and B, MACHINES) and leaves the AMP page, the levels and the sample slots as the project had them. By hand on the panel: every group's screen draws with the stock names and formatters, an edit of SCENE A saves, and closing the menu from a template screen (PROJ) saves its unsaved edits without asking. MACHINES, FROM ALL TRACKS, on a Part whose T3 had been assigned FLEX through QUICK ASSIGN: the machine bytes went back to the template's, no fault (the engine's own per-track machine state not read). Not measured: each of LFO, INPUT SRC, MIDI TRACKS and SCENES applied alone (WHOLE PART covers them together); what the machine transition does to a playing track; anything on hardware.

**The PART default.** SET AS DEFAULT copies the template's Part image into a `K_DEFAULT` record (`stock.part2`, an 8-byte prefix and the same Blob). A detour at the end of stock's Part initialiser (`0x40005a38`, in `0x40005638(part)`, hooks.s `brain_partinit`; it replaces the two instructions before the tail call to the Part validator) puts the default's sections on the Part just initialised (all six; nothing else of the image). Part Clear, every Part of a new project (16 banks of 4, working and saved copies) and KITS' test for a free slot (its default Part is that routine's) all start there, so they agree on what a default Part is. Measured (`verify_brain`): CREATE EMPTY PROJECT with a default on the card writes the default's scene locks into every one of the new project's 16 bank files (8 copies in each: 4 Parts, working and saved) and not its sample slots; Part Clear (called as the Part window's CLEAR calls it) of Part 3 leaves the default's FX ids, LFO, machines and scene locks on it and not its sample slots; by hand, 128 of 128 Parts in RAM equalled the first build's default outside the sample slots. The stock Part validator (`0x40002318`, the initialiser's tail call) clamps the MIDI pages to their descriptors' counts after the default lands, so a default's out-of-range MIDI bytes do not survive; the tests use 0 and 1 bytes. Not run: KITS' staging in a new project that has a default. `card.work`'s default is read by `cache_defaults` (the engine task) into a 6,322-byte copy the UI and the initialiser read. FX defaults apply at selection, PROJECT's at CREATE EMPTY PROJECT; there is no default for a MIDI TRACK (the PART default carries the MIDI tracks) or the page templates.


A setting row reads `NAME` at the left and its value at the right (a Binary a checkbox); YES steps the value (a Binary toggles; an Option steps by one and a Number by its step, each wrapping to its minimum past the maximum) and writes it to `card.work` through an engine-task job.

The stock menu engine is two levels deep (the root and a category's list), so BRAIN's screens are states of its menu-state table: the table (16 entries of `{enter, exit, draw, key, encoder}` at `0x400cbdac`) is copied to DRAM with seven states appended (16..22, `brain_stab` in `manifest.py`) and its six references repointed (the same as `modules/busscreen`, in history, did for its 17th state, tags 85-90 on the unit). A row's action calls the engine's state opener (`0x40064e20`); the key dispatcher (`0x4006510a`) passes each key to `brain_scr_key` and redraws after it; NO runs the state's exit member and returns to the menu (`0x400650a0`). The screens draw with the stock routines the MIDI screens use (`0x400128a8` the icon, `0x40012bd8` text, `0x40011910` the rule, `0x40012254` the inverted bar, `0x40011a58` a dotted line) and are rebuilt from `sr[]` on entry and after each action. MAIN MENU's opening resets the pane to its top (REMIX SWITCH's detour at `0x40064c32`). Measured under the port, 12 Oct 2026 (`verify_brain`, `verify_remix_switch`, screens rendered with `ot_emu --lcd`).

Opened over any other page, or on a MIDI track, the popup says to open an
FX page and nothing is written. The category is a fifth root row: the root
list's rows pointer (`0x400cbda4`, a `SymbolRef`) points at a copy of the
four stock rows (read from the stock image at build time) with BRAIN
appended, and the root count (`0x400cbd8c`, a `Poke`) is 5; a second
module growing the root is refused by the ledger. The icon is one long
per column (pixels in the high byte, bit 0 at the top) with the stock
categories' shared second plane (`0x400cbfc4`). At each LOAD PROJECT, and at the bank load the power-up runs, the
core puts every effect's twelve descriptor defaults (`P+0x5e`) back to the
image's values. It then reads `/BRAIN/card.work`, or `card.strd` by the
pair rule (BRAIN.md section 6.2), and writes each valid default record
over its effect's bytes. The FX choosers and the new-part initialiser read
those bytes when they run (`tools/verify/verify_desc_defaults.py`).

The file is written on a computer:

```bash
python3 tools/hw/ot_brain.py default /Volumes/CARD/BRAIN/card.work bottleservice DELAY TIME=52 FB=5
python3 tools/hw/ot_brain.py default /Volumes/CARD/BRAIN/card.work bottleservice "DELAY SERVER" --mode GRAIN SCTR=30
python3 tools/hw/ot_brain.py default /Volumes/CARD/BRAIN/card.work bottleservice DELAY --clear
python3 tools/hw/ot_brain.py dump /Volumes/CARD/BRAIN/card.work
```

## Settings

`SETTINGS` lists the settings of the modules in the remix that declare a
`Store` (BRAIN.md section 5). BRAIN's own store is `octabam.brain`:

| key | name | kind | default | does |
|---|---|---|---|---|
| 1 | MIDI LOG | Binary | off | the debug log (LOG > MIDI, WRITE DEBUG LOG) records MIDI messages; off, the MIDI thread's handler call returns at once after the handler |
| 2 | APPLY DFLTS | Binary | on | the card's knob defaults (SETTINGS, BRAIN > APPLY DEFAULTS) apply at each project load; off, every effect takes the image's defaults |

At each load the core reads kind-1 records from `BRAIN/card.work` into
`brain_values[]` (one long per setting): a value outside its bounds or of
another type is skipped, a second record for a store is skipped, and a
setting with no record keeps its manifest default. A row's YES writes one
record per store to `card.work`, keeping the keys it does not know, in an
engine-task job (`brain_post_settings`, `job_args` `0x40000`). A name plus
its widest label must fit the 15-character pane (`PANE_W`); the build
refuses a setting that does not.

A module declares a setting and reads it:

```python
store=Store("octabam.<name>"),
settings=(Setting(1, "SHOW", Binary(), default=1),),
```

```python
from remix import brain
inc = brain.read_macro(remix, mods, "octabam.<name>", "SHOW", "get_show")  # text for the unit's include
```

The source then writes `get_show %d0`. With BRAIN in the remix and the
value neither pinned nor `Apply.BUILD`, the macro is one absolute load of
`brain_v_octabam_<name>_1`; otherwise it is `move.l #<value>,%d0`
(`docs/contributing/MODULES.md`, "Settings on the card"). Not built:
Blob and Trigger rows; `Apply.CALLBACK` has no callback field.

## The page shortcut and templates

Hold a page key (SRC, AMP, LFO, FX1, FX2) and press FUNC: a list opens
over the page with SAVE FX DEFAULT, CLEAR FX DEFAULT, SAVE TEMPLATE, LOAD
TEMPLATE and DELETE TEMPLATE. They act on the track and page in view.
SAVE FX DEFAULT and CLEAR FX DEFAULT take an FX page; with the stored defaults
they are the shortcut's only way to set or clear one without a template (TEMPLATES'
SET AS DEFAULT and CLEAR DEFAULT are the other). The three template rows also take the AMP and LFO pages
of an audio track and, in MIDI mode, the whole MIDI track (all five pages
and their setup pages); over SRC they say to open an LFO, AMP or FX page.

- **The combination.** A page key's record names a key layer that is
  active while the key is held (`0x400bab6e`, keys `0x400baad2`, the same
  on MKI and MKII); stock's table there has REC, STOP, PLAY, YES and NO.
  BRAIN repoints the layer's keys (`SymbolRef` at `0x400bab72`) at a copy
  of those five records, read from the stock image at build time, with a
  record for FUNC that calls `brain_page_func`. ✅ Under the port on stock
  (10 Oct 2026): holding FX1 shows the knob values under the knobs, and
  FUNC pressed then changes nothing (the FUNC handler sets its held flag
  and redraws); stock's FUNC-then-page gesture (the chooser) is the other
  order and is unaffected. The keymap census is in `git show 76fd8466:docs/proposals/BRAIN.md`
  section 9.
- **The list** is stock's (`0x4006d94c(count, sel, &sel_out, labels,
  handlers)`): YES stores the row, closes it and calls the row's handler.
- **Templates** are records of kind 3 in `card.work` (BRAIN.md section
  7.3): target 0, no mode, the target's layout word, an 8-byte name, its
  slots as Part bytes by key. SAVE TEMPLATE asks for the name (the stock name
  editor, `TPL nn` filled in); DELETE TEMPLATE and LOAD TEMPLATE list the
  target's templates by name. The targets:

  | target | store id | slots and keys | range per slot |
  |---|---|---|---|
  | FX1 or FX2 page | the effect's | its twelve slots by `Param.key` | the effect's descriptor |
  | AMP page | `stock.amp` | 1-6 page 1, 7-12 AMP SETUP | AMP descriptor `0x400d3950` |
  | LFO page | `stock.lfo` | 1-6 SPD/DEP, 7-9 PMTR, 10-12 WAVE, 13-15 MULT, 16-18 TRIG | audio LFO descriptor `0x400d37be` |
  | SRC page | `stock.static`, `stock.flex`, `stock.thru`, `stock.neighbor`, `stock.pickup`: the track's machine type (Part `+0x8eda2 + t`) | 1-6 page 1, 7-12 page 2 | the PLAYBACK descriptor of that machine (`0x400d2fe4 + 0x192 * machine`) |
  | MIDI track | `stock.midi` | 64 + flat for page 1 (0-29; 94, 95 the CTRL1/CTRL2 enable bitmaps), 1 + offset for the setup record (`docs/firmware/MIDI_TRACKS.md` section 1) | NOTE, LFO, ARP, CONTROL 1, CONTROL 2 descriptors; the bitmaps raw |

  A slot whose descriptor enable nibble has bit 0 clear is neither
  stored nor written (`docs/firmware/PARAM_PAGES.md` section 3b): the page-1
  writer refuses it (`0x40054d20`). In the stock image those are AMP XVOL
  (key 6) and TRIG (key 12), and the MIDI setup bytes with no parameter
  (offsets 3, 5, 0x0c, 0x0d, 0x0f, 0x10, 0x12, 0x13). The stock layout
  words are fixed (`tools/remix/brain.py` `STOCK_TARGETS`). Saves and deletes run in the engine task;
  `brain_load` and every template write keep a copy of the template
  records (64 KB, `card.work`'s largest, so every template fits) that the lists and APPLY TO... read.
- **LOAD** writes the values as the user's knobs would: page 1 through
  the stock writer `0x40054cd8(track, flat, value)` (a MIDI track as
  `8 + track`), the other bytes as the editors store them
  (`modules/cc-map`'s measured recipe: the Part byte, the CS1 mirror
  `0x1001614e + offset + part * 0x18b2`, the live byte, the four dirty
  flags), each value clamped to its descriptor's `[min, min + count - 1]`.
  The live byte of an audio page-2 byte is the lane `0x80000810 + 72 * t
  + 0x26 + index` (index from `+0x8f072 + 30 * t`; `LFO.md` section 2), of
  a MIDI byte the live copy `0x46c76dc0 + 0x44 * t` (`MIDI_TRACKS.md`
  section 2). A MIDI track takes its setup first, then `0x4009a3e0` when
  CHAN changed and `0x4009ec70(bank, part)` (bank and program out), then
  its page-1 values. A template carries MODE with the other knobs, so MODE
  DEFAULTS' re-default is not called.
- **Rename** opens the stock name editor (`0x4007e664(max, title,
  buffer, 1, done(confirmed))`, the call KITS' SAVE KIT makes); on
  confirm the engine task rewrites the record's name field and payload
  CRC, every other byte kept.
- Not built yet: template files on the card for sharing.

## Project settings for new projects

SET AS DEFAULT on a PROJECT template (BRAIN > TEMPLATES) writes a card default of store
`stock.project`: the stock PROJECT menu's bytes (`0x80000024..0x8000006a`
as `docs/firmware/STORAGE.md` section 5 lists them, TEMPOx24 left out;
keys `1 + offset`, raw bytes). CREATE EMPTY PROJECT applies it: a detour
at `0x40085176`, the call after the empty project's RAM (`0x400909d8`) in
the new-project job, writes each byte and its CS1 mirror (`0x100b1460 +
offset`) before the job writes the new `project.work`. Measured under the
port: a new project's own settings differ from a loaded project's in 11 of
56 keys (TEMPO, clock and transport receive, program change, AUTO CHANNEL,
24-bit loading and recording), and with the record the new `project.work`
carries the card's values.

## MIDI knob names

On a MIDI track the page shortcut has a sixth row, NAME KNOB: a list of
the track's ten assignable CCs (`CC1  NAME`, `----` without a name); YES
opens the stock name editor on that CC's name (four characters; an empty
name clears it).

- The names are per bank, Part, MIDI track and CC, in the project's
  `brain.work` as field blocks (kind 5) of store `stock.midi`: one per Part
  with a name, target `bank * 4 + Part`, a Name value keyed `track * 10 +
  cc + 1`. `brain_load` clears them and reads the project's blocks; the
  engine task rewrites the blocks after each edit (`write_names`).
- The CTRL1 and CTRL2 pages draw them: a detour at `0x4004e474`, the
  drawer's label push (`docs/firmware/MIDI_TRACKS.md` section 6), calls
  `brain_klabel(P, slot, stock label)`, which returns the current track's
  name for CTRL1 slots 2-5 (CC1-CC4) and CTRL2 slots 0-5 (CC5-CC10) when
  it has one.
- A MIDI track's template (`stock.midi`) carries its names as Name values
  keyed `129 + cc`; LOAD TEMPLATE puts them on the track and rewrites the
  blocks.

## The live screens

PERFORMANCE and LOG redraw every half second from a soft timer (`0x40031a0c`,
about 0.5 s on the sys task's tick; REMIX SWITCH's boot picker uses the same
call, PR #542): the tick refreshes the screen's figures and calls the menu
redraw (`0x40064d7c`). It stops itself when the state changes (it clears its
slot's function word, which the service re-links only while nonzero); the
state's exit member and its enter member stop it with `UNTIMER`
(`0x40031abc`).

## SAVE FX DEFAULT

`brain_post_save(track, fx)` posts a message of type `0x41` to the engine
task's queue (`0x460d17ce`, through stock's `0x40000c3c`); stock's job
switch ignores types above 45, and the detour at `0x4008485e` runs
`brain_job` for this one in the engine task, where stock writes the
project's files. The job takes the twelve page bytes from the current
Part, replaces that effect's default record (no mode) in `card.work` with
them, keeps every other record's bytes, creates `/BRAIN` on a card that
has none (the file system's directory slot `0x46c8240a`, as stock's new
set does), and writes the values onto the descriptor at once. A damaged
`card.work` with no valid `card.strd` is not overwritten (error 2). One
job is pending at a time.

SAVE PROJECT's project store (`0x4008ee74`, KITS hooks its entry) is
reached through its three call sites (`0x40085642`, `0x400856dc`,
`0x40085780`); each copies a valid `card.work` to `card.strd` before the
store runs, as PLOCKS P2 does at the load call sites.

## What it applies

- Default records (kind 2) for target 0 with no mode, whose store id names
  an effect in the image and whose layout hash is the image's
  (`tools/remix/brain.py` `fx_store_id`, `fx_layout`). The table of
  effects is generated per remix (`manifest.py` `fx_inc`).
- Byte values by key; a value outside its slot's count (read from the
  descriptor) is skipped.
- A record with a mode writes into MODE DEFAULTS' view table
  (`MODEDEF_TABLE`, through `Linked.defsyms`; 0 without that module): the
  values of the slots that mode's view already re-defaults. The table is
  sparse and keeps its size, so a slot the view does not list is skipped
  and counted (`skip_slot`), and a mode record without MODE DEFAULTS in the
  remix is skipped (`skip_mode`).
- A record with a bad payload CRC, an unknown store id, another layout, a
  mode, or a second copy (BRAIN.md section 7.7 rule 5) is skipped and
  counted.
- An effect on both choosers (SPECTRUM, CHARACTER, MODULATION) has one
  descriptor in both id tables; an id-table entry whose descriptor carries
  another id (NONE, an effect on one chooser only) is never written.

## Measured

Under the port (`tools/verify/verify_brain.py`, remix `brain`, 6 Oct 2026),
with T2's FX2 chooser select (SEND -> stock DELAY) and FX1 select
(SPECTRUM -> CHARACTER):

| card | lands | state |
|---|---|---|
| no file | the image's defaults | fresh |
| `card.work` with DELAY and CHARACTER records | their knobs; one value outside its count skipped | card.work |
| `card.work` damaged, `card.strd` valid | `card.strd`'s values | recovered |
| `card.work` damaged, no `card.strd` | the image's defaults | damaged |
| a record with another layout | the image's defaults | card.work, 1 skipped |
| two records for one effect | the image's defaults | card.work, both skipped |

| SAVE FX DEFAULT for T1's FX2 and T2's FX1, then the store copy, on a card holding two other records | the two records hold the live pages; the others keep their bytes; `card.strd` = `card.work`; a second boot puts the saved page on BusDelay's descriptor | card.work |
| the panel: T1, FX2 page, PROJ, DOWN x4, RIGHT, YES on SAVE FX DEFAULT; then OK, DOWN, YES on CLEAR FX DEFAULT | `card.work` holds T1's FX2 page; after CLEAR no BusDelay record | |
| SAVE FX DEFAULT on a card with no `BRAIN` folder | the folder and `card.work` with one record | |
| out-of-count bytes in every Part of every bank, no file | read count - 1 after the load: stock's Part validator `0x40002318`, so the brain has no clamp | |
| `card.work` with MIDI LOG and APPLY DFLTS off and an unknown key 99 | values (0,0); no default record applied; the unknown key kept on write | card.work |
| a settings record with an out-of-bounds Binary and a wrong type | values stay (1,1); 2 skipped | card.work |
| the panel: PROJ, DOWN x4, RIGHT, DOWN x2, YES on SETTINGS, DOWN, YES on MIDI LOG | `card.work` holds one settings record {1:1, 2:1, 99:1}; screens rendered under `ot_emu --lcd` | card.work |
| the shortcut on T1's FX1 page: SAVE TEMPLATE (YES on the name editor), knob A +10, LOAD TEMPLATE `TPL 01` | one template record of CHARACTER with the saved page; the page moves with the knob and comes back to the saved values on LOAD; screens rendered under `ot_emu --lcd` | card.work |
| a GRAIN record for BusDelay (FDBK, SCTR, GLEN listed by the view; DEL not), then MODE CLEAN -> GRAIN through the FX2 page-2 editor on T1 | the view with the card's three values; DEL skipped and untouched | card.work |

Both hooks run during one LOAD PROJECT under the port (2 calls a load). A power-up with no LOAD PROJECT post
(`--no-post`, CS1 from an earlier boot) runs the bank-load hook alone and
the card's DELAY default (TIME 52, FB 5) lands on T2's FX2 select (7 Oct
2026, by hand; not in the gate).

## The project pair

`<set path>/<project folder>/brain.work` and `brain.strd` (file kinds 2 and
3), the set path read from `0x100f8480` and the folder name from
`0x100f8378`. The pair rule is the card pair's (BRAIN.md section 6.2).

- SAVE PROJECT: the engine task copies `card.work` to `card.strd`, then
  writes the project's `brain.work` and copies it to `brain.strd`. The
  file holds the PROJECT-scope settings records (one per store with such a
  setting; no module declares one yet) and one project record (kind 4,
  store id `octabam.brain`): per effect in `brain_fx[]`, the FX id, store
  id and layout hash. Other records of an existing `brain.work` (unknown
  kinds, other stores) are kept byte for byte; a previous project record
  is replaced. A damaged pair with no valid copy is not overwritten
  (write error 2); no project named gives error 5.
- Each load (LOAD PROJECT, power-up bank load): the pair is read, its
  PROJECT-scope settings land in the value table, and the project record
  is compared with the image. Counters, `brain_pcounts` (`.data`): state
  (0 none, 1 `brain.work`, 2 recovered from `brain.strd`, 3 damaged),
  record found, entries, and per entry one of same, moved (its FX id now
  names another store), layout (same store, another layout hash), gone
  (the image has no such store); skipped records (CRC, schema major, a
  second record). `brain_proj_counts` holds the last project save's result.
- ABOUT's PROJECT tab shows the last load's result:
  `SAVED WITH THIS IMAGE`, `N EFFECT(S) CHANGED SINCE THE SAVE` (moved +
  layout + gone), `NO RECORD OF A SAVE`, or `BRAIN FILES BAD`.
- Parts are not rewritten and not clamped: stock's Part validator clamps
  out-of-count bytes at the load (BRAIN.md section 8).
- `set_ent` (`brain_set[]`) is 44 bytes: a scope word follows the group
  pointer (0 CARD, 1 PROJECT). `card.work` carries the CARD entries.

Measured under the port (`verify_brain`, remix `brain`, project fixture
staged as set `BRAINSET`, project `BRAINPRJ`): SAVE PROJECT on a project
folder holding an unknown-kind record and a stale project record writes
`brain.work` with the unknown record unchanged and one project record
equal to the image's table, and `brain.strd` equal to it with kind 3; a
load with a project record of four entries (one unchanged, one with
another layout, one for an unknown store, one whose FX id names another
store) counts 1 same, 1 layout, 1 gone, 1 moved; a damaged `brain.work`
with a valid `brain.strd` reads the same counts with state 2; a damaged
`brain.work` alone gives state 3 and no record read.

## On the unit

Not yet.

## Open

- A set named `BRAIN` shares the directory: the store's files sit in
  that set's folder beside its `AUDIO` and project folders. Whether the
  project list then shows `templates/` is not checked. The gate uses
  another set name. Stock lists a root directory as a set only when it has
  an `AUDIO` folder (📖 the set list's filler `0x40080d0c` lists `/` and
  keeps an entry when `0x40025650("/<name>")` returns nonzero: the
  directory and `"%s/AUDIO"` both pass the file system's existence probe
  `0x46c823fa`), so `/BRAIN` holding only the store is not listed;
  not measured on a unit.
- Timing of the card read on the unit (one file, at most 64 KB; 16 KB until 13 Oct 2026).

- The CS1 block (BRAIN.md section 12). ABOUT's PROJECT text
  is rendered under `--lcd` with a project that has no BRAIN record only.
- LOAD TEMPLATE writes the current bank's Part through the stock writers
  (✅ under the port, the Part bytes). The live lane, what the DSP plays,
  follows when that bank is the one playing (the page-1 writer updates the
  lane only then); the port's fixture plays another bank than the UI
  shows, so the sound after a LOAD is a hardware-round item.
- `--step call` runs as main under the port, where file I/O does not
  return (an unimplemented opcode at `0x4003b108`); the gate posts the job
  instead. The menu rows post from the UI task (measured under the port).

## Gates

- `tools/verify/verify_brain.py` (the manifest's gate, image stage), with
  `modules/brain/generate_brain.py --check`.

## Hooks

REMIX SWITCH stores its last selected filename as a CARD Blob under
`octabam.remix-switch`, key 1. `brain_remix_get` / `brain_remix_save` read
and update it in card.work (card.strd is the SAVE PROJECT recovery copy),
preserving unrelated records and unknown keys. The filename is bounded
to 24 bytes, NUL-terminated and confined to `/BRAIN/REMIXES/`; malformed
names, duplicate records and unsupported schemas never trigger a boot.
The switcher calls the writer only after the engine's sync has drained.

| site | stock | stub |
|---|---|---|
| `0x40085342` | `moveq #27,%d1 / movel %d1,%fp@(-570)`, LOAD PROJECT before the empty-project init `0x400909d8` | `brain_on_load`: `brain_load`, then the two instructions |
| `0x40084d4a` | `mvzb 0x80000002,%d1`, the bank load of every bank but the current (the power-up's path) | `brain_on_bankload` |
| `0x40005572` | `moveal %a2@(0,%d0:l:4),%a0 / jsr %a0@`, the MIDI thread's handler call (table `0x400d6474`) | `brain_on_midi`: copies the message, calls the handler, logs it with what it left |
| `0x4008485e` | `mvzb %a2@,%d0 / moveq #45,%d1 / cmpl %d0,%d1`, the engine task's job switch | `brain_on_job`: type `0x41` runs `brain_job` and returns to the receive at `0x4008484e`; other types continue at `0x40084864` |
| `0x40085642`, `0x400856dc`, `0x40085780` | `jsr 0x4008ee74`, the project store | `brain_on_store`: `card.work` -> `card.strd`, then the store |

`brain.c` is compiled to `brain.s` by `generate_brain.py` (euclid's flags);
`hooks.s` is appended. `.bss` (`nm`, 13 Oct 2026): three 64 KB buffers (`buf` the file, `out` the file being written, `tpl_cache` the template copy), the MIDI knob names (30 KB), the 4 KB
I/O buffer, the image's defaults (768 B), MODE DEFAULTS' table (up to 1 KB).
