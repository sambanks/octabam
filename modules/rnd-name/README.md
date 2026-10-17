# `rnd-name` — RND NAME

Hold **FUNC** and press **CUE** in supported name editors to fill a random
name from two 64-word pools (4096 joins).

## Behaviour

| Editor | FUNC+CUE |
|--------|----------|
| NAME THE NEW PROJECT | `YYMMDD ` + two pool words (e.g. `261014 FOGBED`) |
| SAVE PROJECT AS… / CHOOSE NEW PROJECT NAME | `YYMMDD ` + two pool words |
| COPY PROJECT (with this module in the remix) | `YYMMDD ` + two pool words |
| SAVE SAMPLE AS… | two pool words (no date) |
| NAME THE NEW DIR / NAME THE NEW SET | two pool words |
| KITS → SAVE KIT (name editor) | one short pool word (7-char max) |
| RENAME PROJECT / PART / ARR / remarks / card | stock (inert) |

Stock create still seeds `PROJECT DDMMYY` until the chord runs. Stock
FUNC+REC / PLAY / STOP (PASTE / CLEAR / COPY NAME) stay.

Date is from the DS1390 (same fields as sample timestamps). Fill length
follows the editor’s `ED_MAX`. Entropy: LCG seeded from tempo/clock words.

**Gating:** date vs words-only is decided only from the name-editor
done-callback in `CB_SLOT` (`0x460e761a`), never the window title. The
date branch is CREATE `0x400644f0`, SAVEAS `0x40063d30`, CHOOSE
`0x40063b00`, and (when linked) COPY PROJECT’s `cp_named`.

## Measured / inferred

- **Measured (port):** FUNC+CUE on CREATE EMPTY PROJECT under `ot_emu`
  (`verify_rnd_name`, `--rtc` pinned) writes `YYMMDD ` + a pool join and a
  second chord changes the words. Name-editor FUNC keys pointer leaves
  stock `0x400d0916` for DRAM `rnd_func_keys`.
- **Measured (stock image):** create seeds `PROJECT ` + `DDMMYY` via
  `0x40081b30`; editor opens and callback sites for sample / save-as /
  dir / set from pea's into `0x4007e664`.
- **Inferred:** KITS SAVE KIT is any *other* name-editor callback in the
  DRAM arena (`0x40a00000..0x4f000000`) after the known date cbs;
  falsifier: another DRAM module opens this editor with a different
  done-cb and gets an unwanted words-only fill.
- **Not gated under the port:** sample / save-as / dir / set / kits /
  COPY PROJECT chord paths (create-only in `verify_rnd_name`).

## Remix

```python
modules=(..., "RND NAME", ...)
```

Smoke: `remixes/test/rnd-name`.
