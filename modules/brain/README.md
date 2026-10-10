# `brain` — BRAIN

The settings store's run-time side on the unit ([`docs/proposals/BRAIN.md`](../../docs/proposals/BRAIN.md)).
A remix lists it to give the card layer to its knob defaults.

It applies card-wide knob defaults and writes them: SAVE AS DEFAULT
(`brain_post_save(track, fx)`) makes the current Part's page of that track's
FX1 or FX2 the effect's default in `card.work`, and SAVE PROJECT copies
`card.work` to `card.strd`.

## On the panel

PROJ (MAIN MENU), then BRAIN, the fifth category. Its pane:

| row | does |
|---|---|
| SETTINGS ► | its sub-list: `◄ SETTINGS`, then a heading row per module and a value row per setting (below) |
| DEFAULTS ► | its sub-list: `◄ DEFAULTS`, SAVE AS DEFAULT, CLEAR DEFAULT |
| REMIXES ► | its sub-list: `◄ REMIXES`, then REMIX SWITCH's rows (`modules/remix-switch`, sanderlegit): each `.RMX` in `/BRAIN/REMIXES/`, sorted; after a switch a `FLASHED` separator and the image a power-cycle returns to |
| TOOLS ► | its sub-list: `◄ TOOLS`, WRITE DEBUG LOG |

| sub-list row | does |
|---|---|
| `◄ <NAME>` | back to the pane's top, the cursor on the row it came from |
| SAVE AS DEFAULT | the FX1 or FX2 page in view (of the current audio track, in the current Part) becomes that effect's default on this card; a popup names the page |
| CLEAR DEFAULT | that effect's default leaves `card.work`; the descriptor goes back to the image's |
| a setting row | `NAME  VALUE` (a Binary reads ON or OFF); YES steps the value (a Binary toggles; an Option steps by one and a Number by its step, each wrapping to its minimum past the maximum) and writes it to `card.work` through an engine-task job |
| an image | [YES]: `SWITCH TO <NAME>?`; YES boots it without writing the flash (REMIX SWITCH) |
| WRITE DEBUG LOG | the last 256 MIDI messages (clock and active sensing left out), each with the sync flags, the playing pattern and the next pattern after its handler ran, written to `/BRAIN/debug.txt` by the engine task |

The stock menu engine is two levels deep: LEFT always focuses the root and
YES on a list row runs its action (`0x40064e64`). A sub-list is BRAIN's
list descriptor (`brain_list`) repointed at another row array by the row's
action (`brain.c` show()); the redraw after every key (`0x40064d7c`) shows
it. MAIN MENU's opening resets the pane to its top (REMIX SWITCH's detour
at `0x40064c32`). Measured under the port, 8 Oct 2026 (`verify_brain`
menu, `verify_remixswitch` ui, screens rendered with `ot_emu --lcd`).

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
those bytes when they run (`tools/verify/verify_descdefaults.py`).

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
| 1 | MIDI LOG | Binary | on | the debug log (TOOLS, WRITE DEBUG LOG) records MIDI messages; off, the MIDI thread's handler call returns at once after the handler |
| 2 | DEFAULTS | Binary | on | the card's knob defaults apply at each project load; off, every effect takes the image's defaults |

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
over the page with SAVE AS DEFAULT, CLEAR DEFAULT, SAVE TEMPLATE, LOAD
TEMPLATE and DELETE TEMPLATE. They act on the track and page in view, as
the BRAIN pane's DEFAULTS rows do; over SRC, AMP or LFO, or on a MIDI
track, each says to open an FX page.

- **The combination.** A page key's record names a key layer that is
  active while the key is held (`0x400bab6e`, keys `0x400baad2`, the same
  on MKI and MKII); stock's table there has REC, STOP, PLAY, YES and NO.
  BRAIN repoints the layer's keys (`SymbolRef` at `0x400bab72`) at a copy
  of those five records, read from the stock image at build time, with a
  record for FUNC that calls `brain_page_func`. ✅ Under the port on stock
  (10 Oct 2026): holding FX1 shows the knob values under the knobs, and
  FUNC pressed then changes nothing (the FUNC handler sets its held flag
  and redraws); stock's FUNC-then-page gesture (the chooser) is the other
  order and is unaffected. The keymap census is in `docs/proposals/BRAIN.md`
  section 9.
- **The list** is stock's (`0x4006d94c(count, sel, &sel_out, labels,
  handlers)`): YES stores the row, closes it and calls the row's handler.
- **Templates** are records of kind 3 in `card.work` (BRAIN.md section
  7.3): target 0, no mode, the effect's layout hash, an 8-byte name, the
  twelve slots as Part bytes. SAVE TEMPLATE names it `TPL nn`, the lowest
  free number for that effect; DELETE TEMPLATE and LOAD TEMPLATE list the
  effect's templates by name. Saves and deletes run in the engine task;
  `brain_load` and every template write keep a copy of the template
  records (4 KB) that the lists and LOAD read.
- **LOAD** writes the twelve values as the user's knobs would: page 1
  through the stock writer `0x40054cd8(track, flat, value)`, page 2 as the
  page-2 editors store it (`modules/cc-map`'s measured recipe: the Part
  byte, the shadow, the live lane byte, the four dirty flags), each value
  clamped to the descriptor's `[min, min + count - 1]`. A template carries
  MODE with the other knobs, so MODE DEFAULTS' re-default is not called.
- Not built yet: renaming (names are `TPL nn` until a host tool or a name
  editor renames them), templates from the image (`templates/`, BRAIN.md
  section 3), template files on the card for sharing, a TEMPLATES list in
  the BRAIN pane, templates for SRC/AMP/LFO pages and MIDI tracks
  (phase 4).

## The boot screen

The OS's own boot animation (2.8 s after the bootstrap's logo, the
LED/key-scan task) draws a brain over OCTABAM instead of stock's sprite
field: the brain draws in from the left, then the word. A `jsr` detour at
the animation's per-frame flush (`0x40055aa2`, PIRATE FLAG's site,
sanderlegit, PR #542) replaces the plane's 128 columns each frame, then
calls the flush stock called. The frame value in `d2` is DTIM3 time
(0..559, by steps of varying size). The art is `bootart.py`'s, drawn from
shapes and generated into the build (`manifest.py boot_inc`). The
bootstrap's logo and version line before it are NOR's and do not change.
Every image carrying BRAIN shows it, after a REMIX SWITCH too.

## SAVE AS DEFAULT

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

| SAVE AS DEFAULT for T1's FX2 and T2's FX1, then the store copy, on a card holding two other records | the two records hold the live pages; the others keep their bytes; `card.strd` = `card.work`; a second boot puts the saved page on BusDelay's descriptor | card.work |
| the panel: T1, FX2 page, PROJ, DOWN x4, RIGHT, YES on SAVE AS DEFAULT; then OK, DOWN, YES on CLEAR DEFAULT | `card.work` holds T1's FX2 page; after CLEAR no BusDelay record | |
| SAVE AS DEFAULT on a card with no `BRAIN` folder | the folder and `card.work` with one record | |
| out-of-count bytes in every Part of every bank, no file | read count - 1 after the load: stock's Part validator `0x40002318`, so the brain has no clamp | |
| `card.work` with MIDI LOG and DEFAULTS off and an unknown key 99 | values (0,0); no default record applied; the unknown key kept on write | card.work |
| a settings record with an out-of-bounds Binary and a wrong type | values stay (1,1); 2 skipped | card.work |
| the panel: PROJ, DOWN x4, RIGHT, YES on SETTINGS, YES on MIDI LOG | `card.work` holds one settings record {1:0, 2:1, 99:1}; screens rendered under `ot_emu --lcd` | card.work |
| the shortcut on T1's FX1 page: SAVE TEMPLATE, knob A +10, LOAD TEMPLATE `TPL 01` | one template record of CHARACTER with the saved page; the page moves with the knob and comes back to the saved values on LOAD; screens rendered under `ot_emu --lcd` | card.work |
| `--boot-logo`: the first animation frame at or past 280 | equals `bootart.py`'s pixels for that frame, bit for bit | |
| a GRAIN record for BusDelay (FDBK, SCTR, GLEN listed by the view; DEL not), then MODE CLEAN -> GRAIN through the FX2 page-2 editor on T1 | the view with the card's three values; DEL skipped and untouched | card.work |

Both hooks run during one LOAD PROJECT under the port (2 calls a load). A power-up with no LOAD PROJECT post
(`--no-post`, CS1 from an earlier boot) runs the bank-load hook alone and
the card's DELAY default (TIME 52, FB 5) lands on T2's FX2 select (7 Oct
2026, by hand; not in the gate).

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
- Timing of the card read on the unit (one file, at most 16 KB).

- The project pair, the project record, the CS1 block (BRAIN.md
  section 12).
- `--step call` runs as main under the port, where file I/O does not
  return (an unimplemented opcode at `0x4003b108`); the gate posts the job
  instead. The menu rows post from the UI task (measured under the port).

## Gates

- `tools/verify/verify_brain.py` (the manifest's gate, image stage), with
  `modules/brain/generate_brain.py --check`.

## Hooks

| site | stock | stub |
|---|---|---|
| `0x40085342` | `moveq #27,%d1 / movel %d1,%fp@(-570)`, LOAD PROJECT before the empty-project init `0x400909d8` | `brain_on_load`: `brain_load`, then the two instructions |
| `0x40084d4a` | `mvzb 0x80000002,%d1`, the bank load of every bank but the current (the power-up's path) | `brain_on_bankload` |
| `0x40005572` | `moveal %a2@(0,%d0:l:4),%a0 / jsr %a0@`, the MIDI thread's handler call (table `0x400d6474`) | `brain_on_midi`: copies the message, calls the handler, logs it with what it left |
| `0x4008485e` | `mvzb %a2@,%d0 / moveq #45,%d1 / cmpl %d0,%d1`, the engine task's job switch | `brain_on_job`: type `0x41` runs `brain_job` and returns to the receive at `0x4008484e`; other types continue at `0x40084864` |
| `0x40085642`, `0x400856dc`, `0x40085780` | `jsr 0x4008ee74`, the project store | `brain_on_store`: `card.work` -> `card.strd`, then the store |

`brain.c` is compiled to `brain.s` by `generate_brain.py` (euclid's flags);
`hooks.s` is appended. 21 KB of `.bss`: a 16 KB file buffer, the 4 KB
I/O buffer, the image's defaults (768 B), MODE DEFAULTS' table (up to 1 KB).
