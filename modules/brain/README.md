# `brain` — BRAIN

The settings store's run-time side on the unit ([`docs/proposals/BRAIN.md`](../../docs/proposals/BRAIN.md)).
A remix lists it to give the card layer to its knob defaults.

It applies card-wide knob defaults and writes them: SAVE AS DEFAULT
(`brain_post_save(track, fx)`) makes the current Part's page of that track's
FX1 or FX2 the effect's default in `card.work`, and SAVE PROJECT copies
`card.work` to `card.strd`.

## On the panel

PROJ (MAIN MENU), then BRAIN, the fifth category:

| row | does |
|---|---|
| `<REMIX> <BUILD>` | a heading the cursor skips: which image is flashed |
| SAVE AS DEFAULT | the FX1 or FX2 page in view (of the current audio track, in the current Part) becomes that effect's default on this card; a popup names the page |
| CLEAR DEFAULT | that effect's default leaves `card.work`; the descriptor goes back to the image's |

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

- A shortcut on the FX page itself (a free key combination); the
  SETTINGS list, the project pair, the project record, the CS1 block
  (BRAIN.md section 12).
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
| `0x4008485e` | `mvzb %a2@,%d0 / moveq #45,%d1 / cmpl %d0,%d1`, the engine task's job switch | `brain_on_job`: type `0x41` runs `brain_job` and returns to the receive at `0x4008484e`; other types continue at `0x40084864` |
| `0x40085642`, `0x400856dc`, `0x40085780` | `jsr 0x4008ee74`, the project store | `brain_on_store`: `card.work` -> `card.strd`, then the store |

`brain.c` is compiled to `brain.s` by `generate_brain.py` (euclid's flags);
`hooks.s` is appended. 21 KB of `.bss`: a 16 KB file buffer, the 4 KB
I/O buffer, the image's defaults (768 B), MODE DEFAULTS' table (up to 1 KB).
