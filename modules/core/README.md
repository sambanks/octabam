# `core` — CORE

The settings store's run-time side on the unit ([`docs/proposals/STORE.md`](../../docs/proposals/STORE.md)).
A remix lists it to give the card layer to its knob defaults.

This increment applies card-wide knob defaults and is read-only on the
unit. At each LOAD PROJECT, and at the bank load the power-up runs, the
core puts every effect's twelve descriptor defaults (`P+0x5e`) back to the
image's values. It then reads `/OCTABAM/card.work`, or `card.strd` by the
pair rule (STORE.md section 6.2), and writes each valid default record
over its effect's bytes. The FX choosers and the new-part initialiser read
those bytes when they run (`tools/verify/verify_descdefaults.py`).

The file is written on a computer:

```bash
python3 tools/hw/ot_store.py default /Volumes/CARD/OCTABAM/card.work bottleservice DELAY TIME=52 FB=5
python3 tools/hw/ot_store.py default /Volumes/CARD/OCTABAM/card.work bottleservice DELAY --clear
python3 tools/hw/ot_store.py dump /Volumes/CARD/OCTABAM/card.work
```

## What it applies

- Default records (kind 2) for target 0 with no mode, whose store id names
  an effect in the image and whose layout hash is the image's
  (`tools/remix/store.py` `fx_store_id`, `fx_layout`). The table of
  effects is generated per remix (`manifest.py` `fx_inc`).
- Byte values by key; a value outside its slot's count (read from the
  descriptor) is skipped.
- A record with a bad payload CRC, an unknown store id, another layout, a
  mode, or a second copy (STORE.md section 7.7 rule 5) is skipped and
  counted.
- An effect on both choosers (SPECTRUM, CHARACTER, MODULATION) has one
  descriptor in both id tables; an id-table entry whose descriptor carries
  another id (NONE, an effect on one chooser only) is never written.

## Measured

Under the port (`tools/verify/verify_core.py`, remix `core`, 6 Oct 2026),
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

Both hooks run during one LOAD PROJECT under the port (2 calls a load).

## On the unit

Not yet.

## Open

- Whether stock lists the card-root `OCTABAM` directory as a set. A set
  named `OCTABAM` shares the directory; the gate uses another set name.
- Timing of the card read on the unit (one file, at most 16 KB).
- A power-up with no LOAD PROJECT post: the bank-load hook, not run under
  the port.
- The next increments (STORE.md section 12): SAVE AS DEFAULT on the unit,
  the SETTINGS list, the project pair, the project record, the CS1 block.

## Gates

- `tools/verify/verify_core.py` (the manifest's gate, image stage), with
  `modules/core/generate_core.py --check`.

## Hooks

| site | stock | stub |
|---|---|---|
| `0x40085342` | `moveq #27,%d1 / movel %d1,%fp@(-570)`, LOAD PROJECT before the empty-project init `0x400909d8` | `core_on_load`: `core_load`, then the two instructions |
| `0x40084d4a` | `mvzb 0x80000002,%d1`, the bank load of every bank but the current (the power-up's path) | `core_on_bankload` |

`core.c` is compiled to `core.s` by `generate_core.py` (euclid's flags);
`hooks.s` is appended. 21 KB of `.bss`: a 16 KB file buffer, the 4 KB
I/O buffer, the image's defaults (768 B).
