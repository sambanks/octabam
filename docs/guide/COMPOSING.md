# Composing a remix

A remix defines which modules are included in a firmware image, along with which
effects appear in the FX1 and FX2 menus and in what order. Write a
`remixes/<name>/remix.py` file, then build and flash it using
[BUILDING.md](BUILDING.md) sections 3–6.

## Setup

Follow [BUILDING.md sections 0–2](BUILDING.md#0-what-you-need) first to install
the toolchain (Xcode Command Line Tools, Homebrew, Python 3.10+, `cmake`, `uv`),
run `make setup`, and unpack your stock OS with `make os && make recon`. Every
build reads `out/raw/section_3_MAIN_OS.bin` and assembles DSP code with
`dsp_asm`.

## What costs what

The limiting resource for DSP effects is program word count, not menu rows.
Adding a chooser row costs zero DSP words (seven rows fit in place, and up to 32
fit in the extended cave), and listing a stock effect costs nothing because its
code is already present in the OS image. DSP space is budgeted per payload:
payload A and payload B hold the same effects at different addresses, except
under `SPEC=1`, which puts each bus server on its own core. If your selection
exceeds a payload's available space, the build stops with an error naming the
payload, for example:
`payload B: SPECTRUM overruns the region (3599 > 2724 words)`.

Payload A word costs for built-in modules:

- Send: 262
- Euclid: 362 (+33 table)
- MiniVerb: 457
- Character: 999 (+51)
- Spectrum: 1,346 (+54)
- Modulation: 1,481 (+148)
- BusVerb: 2,035 (+194 LFO lines and table)
- BusDelay: 1,437 (+60, payload B)

The build rejects invalid selections with a descriptive error:

| Condition | Result |
|---|---|
| No safe fallback | Build fails; set `fallback="SEND"` to add one |
| Buffer conflict | Build fails and names the conflicting effects (Flanger, Chorus, Spatializer, Comb Filter) |
| Payload region exceeded | Build fails and names the overflowing payload |

That buffer conflict is why adding BusVerb to a stock FX2 menu costs seven stock
effects. FLANGER, CHORUS, SPATIALIZER, COMB, and the three stock reverbs each
allocate a per-track instance buffer via the host bump allocator (reading
`x:>$213`: PLATE at `0x01018`, SPRING at `0x01267`, DARK at `0x01692`) at the
same addresses hardcoded by BusVerb's tank, and all eight tracks share one FX2
chooser list. Those effects can still live on FX1 without conflicting because
the allocator keeps separate buffer tables: FX1 uses bases `0x1000`, `0x1c00`,
`0x2800`, and `0x3400` (3,072 words each, up to `0x3fff`), while FX2 uses
`0x4000`, `0x8000`, and the 16,384-word shared-window pair.

### Harvesting

If a remix lists every stock effect, no DSP space is reclaimed: all 6,158 words
of stock effect code remain in use. To free an effect's words for new modules
(`stock.harvested`), you must remove it from **both** FX1 and FX2 menus.
Removing it from only one menu frees nothing. The three stock reverbs are the
most common harvest target because they are large and FX2-only, so removing them
leaves FX1 intact.

Because the 13 stock DSP effects sit contiguously in memory, any unbroken span
of removed effects forms a single free block for module placement. If a kept
effect calls a helper routine inside a removed effect's span, the placer keeps
that helper in place and works around it (DARK REV calls 35 words in SPRING's
span, PLATE calls 93 words in DARK's, and five effects call 27 words in FILTER's;
the build logs these as `kept (... called by ...)` via `stock.pinned`).

Each module must fit within one contiguous span—two separate 1,500-word gaps
cannot hold a 2,000-word module—so the build report prints both total free words
and the largest single opening. Removing a stock effect sitting between two free
spans merges them. Note that unlisting an effect makes its space available
without immediately erasing it: the placer packs upward from the lowest address
and reports which unlisted effects survived untouched. If you list an effect
whose code region was overwritten by a placed module, the build rejects that
row.

Stock effect rows are not included in the cycle budget report (for reference,
FILTER uses 192 cycles per instance).

### FX1 rows

Setting `Remix.fx1` puts effects in the FX1 chooser. Adding a row to FX1 costs
no DSP words—both menus share the same DSP dispatch table, and the build
rebuilds the FX1 menu list in a cave with its three `lea` references, ID lookup,
and cursor table updated—but it does increase worst-case cycle counts. Because
FX1 adds four more slots across the same four tracks per core, putting an effect
on both FX1 and FX2 can double its worst-case load (from 4 to 8 instances per
core). Only buffer-free inserts, or effects that read the allocator and declare
`buffer_words` ≤ 3,072, can be placed on FX1; the build rejects anything else.
A module using `replaces` is listed under its own key. If you shorten the FX1
list, any dropped effect ID has its cursor row clamped to 0.

## Writing `remix.py` by hand

Each remix is a directory at `remixes/<name>/` containing `remix.py` (the module
selection) and `README.md` (a summary of what is included). The registry
automatically discovers `remixes/*/remix.py`, `remixes/test/*/remix.py`, and
`remixes/community/*/remix.py` with no manual registration. Put single-module
gate remixes in `remixes/test/<name>/`, and personal remixes you want to share
in `remixes/community/<name>/`, named after yourself or the remix's purpose
(never `octabam-*`; see `CONTRIBUTING.md`, "Remixes"). Because CI does not build
community remixes, run `make check REMIX=<name>` locally before opening a PR;
the web builder publishes any community remix that passes `make check` during
its publish run. Remix names must be unique across all three folders, and tools
accept the bare directory name (for example `make check REMIX=miniverb`).

The easiest way to start is to copy an existing `remix.py` and edit it:

- `remixes/octabam-bus/remix.py`: full bus setup with hosts and ColdFire mods
- `remixes/test/euclid/remix.py`: a single DSP insert alongside stock effects
- `remixes/test/kits/remix.py`: a single ColdFire mod with no DSP changes

```python
from remix.schema import Remix

REMIX = Remix(
    name="mine",                       # must match the directory name
    doc="One-line summary of what this remix includes.",
    family="effects",                  # index section: rig, effects, mods, reference, probes
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC",
             "FILTER", "LO-FI"),       # FX2 chooser entries, in row order
    fallback="SEND",                   # or "NONE"
    # fx1=("FILTER", "EQUALIZER", "SPECTRUM"),   # FX1 chooser; omit to keep stock's 10 effects
)
```

Field reference:

- `modules`: The FX2 menu in row order, plus any non-menu modules (ColdFire
  mods, bridges, TEMPO SYNC), which can appear anywhere in the tuple. Use each
  module's `key` (run `make modules` to list them) or a stock effect name:
  `FILTER`, `EQUALIZER`, `DJ EQ`, `PHASER`, `FLANGER`, `CHORUS`, `SPATIALIZER`,
  `COMB FILTER`, `COMPRESSOR`, `LO-FI`, `DELAY`, `PLATE REV`, `SPRING REV`,
  `DARK REV`. Any stock effect omitted from both `modules` and `fx1` makes its
  DSP code space available for placed modules (the three stock reverbs free
  2,724 words by default), while keeping its code and descriptor intact until a
  placed module overwrites it so older projects still work. The build fails if a
  listed stock effect's code is overwritten, or if a payload runs out of space.
- `fallback`: Where unrecognized FX2 IDs (including ID 0 on a fresh Part)
  dispatch. Use `"SEND"` for remixes with a bus server and `"NONE"` for remixes
  without one. Using `"NONE"` alongside a bus server is rejected.
- `fx1`: The FX1 menu in row order. If omitted, FX1 keeps the 10 stock effects.
  Only buffer-free inserts (or compatible allocator readers) are allowed here.
  Adding FX1 rows costs no DSP words, but adds four potential instances per core
  to the cycle budget.
- `family`: Controls which section of the remix index lists this remix (defaults
  to Reference). `evidence` is optional and not displayed.
- Up to 7 FX2 rows fit in place; 8 to 32 rows automatically move to an extended
  list.
- Conflicting modules that claim the same address, ID, hook, or buffer fail the
  build and are reported by name; run `make modules` to see the compatibility
  matrix.
- `settings`: Overrides default or fixed settings for this image using
  `(store id, setting name) -> value` or `Pin(value)`. Build-time settings
  select which code is compiled in; runtime settings (such as USB's `TRACKS`,
  `MAIN`, `CUE`, `MASTER`, `IN`, and `MIDI`) remain editable on the unit unless
  pinned, e.g. `settings={("octabam.usb", "IN"): Pin("OFF")}`. Run
  `python3 tools/remix/brain.py resolve mine` (or check the build report) to
  inspect resolved settings and where each value came from.
- `defaults`: Overrides knob defaults for this image using
  `(module key, mode, knob) -> byte`, where `mode` is `None` for the knob's base
  default or a `MODE` label for a mode-specific default, and `knob` matches the
  front-panel name (for example `defaults={("DELAY SERVER", "GRAIN", "PTCH"): 96}`).
  Values outside the knob's valid range are rejected.
- `hidden`, `named`, `grains`: See [MODULES.md](../contributing/MODULES.md).

Once your `remix.py` and `README.md` are ready:

```bash
make docs                       # update remixes/README.md (make check fails if stale)
make check REMIX=mine           # build, price cycles, run gates, and boot under the port
make image REMIX=mine BUILD=2   # writes out/OCTATRACK_OCTABAM2.bin
```

`make check` requires a `README.md` in every remix directory. If your remix
changes effect parameter layouts relative to an existing project, stamp the
project before playing it ([BUILDING.md section 6](BUILDING.md#6-after-the-flash)).

## Known gaps

- Per-mode `defaults` are applied to existing projects via `stamp-defaults`.
- Stock effect rows are not included in cycle budgeting.
