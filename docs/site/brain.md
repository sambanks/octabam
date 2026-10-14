# BRAIN

BRAIN is the on-unit screen for the shared settings, defaults and templates
store, and the way you switch remixes from the card. It is the fifth
category of the MAIN MENU: PROJ (MAIN MENU), then BRAIN. Its pane is one
list, most used first: TEMPLATES, REMIXES, SETTINGS, PERFORMANCE, LOG,
ABOUT. UP and DOWN move the cursor, YES acts on the row, NO goes back to the
menu.

BRAIN is verified under the port. It has not run on a unit.

## TEMPLATES

Four tabs: PART, FX, MIDI, PROJECT, each with a NEW row. A template's screen
has APPLY TO…, SET AS DEFAULT / CLEAR DEFAULT, SAVE, RENAME, DELETE, then its
VALUES.

- PART templates hold a whole Part, applied by section and track: FX, LFO,
  INPUT SRC, MIDI TRACKS, SCENES, MACHINES.
- PROJECT templates cover the stock PROJECT / CONTROL / MIDI screens. SET AS
  DEFAULT on one makes it the settings of every new project.

A page shortcut saves and loads the page in front of you as a template:
hold a page key (SRC, AMP, LFO, FX1, FX2) and press FUNC. The list that
opens has SAVE FX DEFAULT, CLEAR FX DEFAULT, SAVE TEMPLATE, LOAD TEMPLATE,
DELETE TEMPLATE (plus NAME KNOB on a MIDI track). On an MKII, FUNC + a push
of the LEVEL encoder opens TOOLS > LOAD.

## REMIXES

The remix switch. Every `.RMX` file in `/BRAIN/REMIXES/` on the CF card is
listed, sorted; the one whose name matches the running image (case and
spaces ignored) has RUNNING at the right. YES on one asks `BOOT <NAME>?` and
boots it without writing the flash. After a switch, a FLASHED separator
shows the image a power-cycle returns to: switching is temporary, and
OFF/ON always comes back to the flashed image.

Making `.RMX` files (an image is a whole OS: stock 1.40C with one remix's
modules built in):

```bash
make image REMIX=<name> BUILD=<nn>      # writes the .RMX beside the .bin
make rmx REMIX=<name>                   # the same, any remix
make rmx-stock                          # -> out/STOCK 1.40C.RMX
```

Copy the `.RMX` files to `/BRAIN/REMIXES/` on the card. Delete any Mac
`._<name>` files first, or they are listed too. Stock 1.40C itself is a
valid switch target. A switch stops playback, syncs the project (as OS
UPGRADE does), loads and resets.

## SETTINGS

A heading per module that declares settings, then its value rows. YES steps
the value (wrapping); LEFT and RIGHT step down and up, stopping at the ends.
A value that takes effect at the next boot ends in `*`, with `* AT NEXT
BOOT` under the list.

BRAIN's own settings are `APPLY DFLTS` (default on — off means every effect
takes the image's defaults rather than the card's) and `MIDI LOG` and
`EVENT LOG` (defaults on). Settings persist to the card's `card.work`.

## PERFORMANCE

LOAD / CPU / DSP / MEM / CARD / MIDI / USB tabs, redrawn every half second.
The DSP and LOAD rows come from the LOAD METER module, which measures the
frame interrupt's share of the ColdFire and each DSP core's busy time.

## LOG

EVENTS lists the recorded events: `FRAME OVER`, `CPU FULL`, `CARD SLOW`.
MIDI mirrors MIDI traffic when MIDI LOG is on, and WRITE DEBUG LOG writes
`/BRAIN/debug.txt` on the card.

## ABOUT

IMAGE / CARD / PROJECT / MODULES tabs. IMAGE shows the image name, the remix
name, and the stock OS it is built on (1.40C). MODULES credits each module's
key and first author.

## Card files

| file | holds |
|---|---|
| `BRAIN/card.work`, `BRAIN/card.strd` at the card root | card-scope settings; the `.strd` is the card-layer defaults, copied at SAVE PROJECT |
| `<set>/<project>/brain.work`, `brain.strd` | project-scope settings; the project record |
| template records in `BRAIN/card.work` | saved templates and card-wide defaults; standalone template import/export is not implemented |

The pair rule: `.work` is the working copy, `.strd` the last saved. A
damaged `.work` falls back to its `.strd`; a damaged pair falls back to the
image's defaults, and nothing is overwritten.

How the defaults work: at each LOAD PROJECT and at power-up, the core resets
every effect's twelve descriptor defaults to the image's values, then reads
`/BRAIN/card.work` (or `card.strd` by the pair rule) and writes each valid
default record over its effect's bytes. The FX choosers and the new-part
initialiser read those bytes. SAVE FX DEFAULT (the page shortcut above)
makes the current FX page the stored default; SAVE PROJECT copies `card.work`
to `card.strd`. A `card.work` on a card with no `BRAIN` folder: the folder
and file are created.

## Writing defaults from a computer

The host tool reads and writes the same `card.work`:

```bash
python3 tools/hw/ot_brain.py default /Volumes/CARD/BRAIN/card.work bottleservice DELAY TIME=52 FB=5
python3 tools/hw/ot_brain.py default /Volumes/CARD/BRAIN/card.work bottleservice "DELAY SERVER" --mode GRAIN SCTR=30
python3 tools/hw/ot_brain.py default /Volumes/CARD/BRAIN/card.work bottleservice DELAY --clear
python3 tools/hw/ot_brain.py dump /Volumes/CARD/BRAIN/card.work
```

The examples write defaults for the `bottleservice` remix; use the name of
the remix you run.

The design record:
https://github.com/sambanks/octabam/blob/main/docs/proposals/BRAIN.md
