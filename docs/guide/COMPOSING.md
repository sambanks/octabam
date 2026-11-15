# Composing a remix

A remix is a selection of modules: which effects the unit's FX1 and FX2
choosers list, in which order, and which firmware mods ride along. Write
`remixes/<name>/remix.py` by hand, then build and flash it as in
[BUILDING.md](BUILDING.md) sections 3–6.

## Setup

[BUILDING.md sections 0–2](BUILDING.md#0-what-you-need) first: the Xcode Command
Line Tools, Homebrew, Python 3.10+, `brew install cmake uv`, then
`make setup` and `make os && make recon`. Every image starts from
`out/raw/section_3_MAIN_OS.bin` and is assembled with `dsp_asm`.

## What costs what

Rows are not the currency; words are. A chooser row costs no words (seven
fit in place, up to 32 in the long cave), and a stock effect on either menu
costs nothing: its code is already in the image. The budget is per payload
(two regions, the same effects at different addresses; `SPEC=1` puts each
server on its own), reported from the build's own figures. An overrun
arrives as the build's refusal, naming the payload: `payload B: SPECTRUM
overruns the region (3599 > 2724 words)`.

Measured costs, payload A (27 Sep 2026): Send 262, Euclid 362 (+33
table), MiniVerb 457, Character 999 (+51), Spectrum 1,346
(+54), Modulation 1,481 (+148), BusVerb 2,035 (+194 LFO lines and
table), BusDelay 1,437 (+60, payload B).

The build refuses these cases by name:

| case | what happens |
|---|---|
| no safe fallback | refused; `fallback="SEND"` adds it |
| a buffer clash | refused, naming the effects that need the same buffer (Flanger, Chorus, Spatializer, Comb Filter) |
| past a payload's region | refused, naming the payload |

The buffer clash is why adding BusVerb to a stock chooser costs seven
effects: FLANGER, CHORUS, SPATIALIZER, COMB and the three reverbs each
take a per-track instance buffer from the host's bump allocator (each
reads `x:>$213`: PLATE at `0x01018`, SPRING `0x01267`, DARK `0x01692`) at
the addresses BusVerb's tank hardcodes, and the chooser is one list for all
eight tracks. The collision cannot follow them to FX1: the allocator keeps
separate tables, FX1 bases `0x1000 0x1c00 0x2800 0x3400` of 3,072 words
topping out at `0x3fff`, FX2 `0x4000 0x8000` + the shared-window pair of
16,384.

### Harvesting

A remix with every stock effect listed has nothing harvested: all 6,158 words of a payload's
effect code belong to a stock effect that is using them. Taking an effect
off **both** choosers is the decision to give up its words
(`stock.harvested`); removing it from one menu while it still has a row on
the other frees nothing. The three reverbs are only the default harvest:
the biggest, and FX2-only, so taking them costs FX1 nothing. The thirteen
DSP effects are laid out contiguously, so any unbroken run of them is
ground a module can be placed into. A routine that a kept effect calls inside a harvested one
stays where it is and the run is placed around it (DARK REV calls 35 words
in SPRING's span, PLATE calls 93 in DARK's, five effects call 27 in
FILTER's; `stock.pinned`, printed by the build as `kept (... called by
...)`).

A module must fit inside one run: two runs of 1,500 words will not take a
2,000-word module, so the build report names the largest opening beside the
total. Harvesting an effect that sits between two runs joins them.
Harvested is not unlisted: an effect keeps its algorithm wherever your
code did not reach (the region packs from the lowest address upward and
the build reports which survived), so an effect can be listed and
harvested at once until the placer reaches it; the build then refuses the
row.

Stock rows are not in the cycles figure (only FILTER's is measured, 192 per
instance).

### FX1 rows

`Remix.fx1` gives an effect an FX1 row. It costs no words (the DSP dispatch is shared by both menus; the list is
rebuilt in the cave with FX1's three `lea` references, its id lookup and
its cursor table repointed) and it costs cycles: FX1 is four more slots on
the same four tracks, so an effect on both menus can double the worst
per-core load (4× → 8× instances). Only a buffer-free
insert, or an allocator reader declaring `buffer_words` ≤ 3,072, may take
one; the build refuses the rest by name. A `replaces` module is listed by its own key. Every id
a shortened FX1 list drops has its cursor row clamped to 0.

## Writing `remix.py` by hand

A remix is one directory, `remixes/<name>/`: `remix.py` holds the
selection, `README.md` says what is in it and where it has run. The
registry discovers every `remixes/*/remix.py` and `remixes/test/*/remix.py`;
nothing else registers it. A remix that carries one module for that
module's gates goes in `remixes/test/<name>/`; names are unique across
both, and every tool takes the bare name (`make check REMIX=miniverb`).

Copy an existing `remix.py` and edit it. `remixes/octabam-bus/remix.py`
is the bus with stations, hosts and ColdFire mods,
`remixes/test/euclid/remix.py` an insert beside the stock effects,
  `remixes/test/kits/remix.py` one ColdFire mod and no DSP code.

```python
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="mine",                       # == the directory name
    doc="One line: what is in it.",
    family="effects",                  # index section: rig, effects, mods, reference, probes
    evidence=(Evidence(Level.EMULATOR, ref="make check", date="2026-09-28"),),   # docs/contributing/MODULES.md
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC",
             "FILTER", "LO-FI"),       # the FX2 chooser, in row order
    fallback="SEND",                   # or "NONE"
    # fx1=("FILTER", "EQUALIZER", "SPECTRUM"),   # the FX1 chooser; omitted = stock's ten
)
```

- `modules` is the FX2 chooser in row order. A key is a module's `key`
  (`make modules` prints them) or a stock effect's name: FILTER,
  EQUALIZER, DJ EQ, PHASER, FLANGER, CHORUS, SPATIALIZER, COMB FILTER,
  COMPRESSOR, LO-FI, DELAY, PLATE REV, SPRING REV, DARK REV. A module with
  no chooser row (a ColdFire mod, a bridge, TEMPO SYNC) sits anywhere in
  the list. A stock effect on neither chooser keeps its code and
  descriptor (an old project still runs it) and its words become room for
  modules; the three reverbs are the default room, 2,724 words. The build
  refuses a listed stock effect whose words a placed module reached, and
  an overrun by payload: `payload B: SPECTRUM overruns the region (3599 >
  2724 words)`.
- `fallback` is where an FX2 id the image does not implement dispatches,
  id 0 of a fresh part included: `"SEND"` for a remix with a bus server
  (the track becomes a send), `"NONE"` for one without (the firmware's
  own NONE). `NONE` beside a bus server is refused.
- `fx1` is the FX1 chooser in row order; omitted, FX1 stays stock's ten.
  Only a buffer-free insert may take a row; the build refuses the rest by
  name. A row costs no words and does cost cycles: four more slots per
  core.
- `family` and `evidence` are the columns of the remix index.
  Without them the remix lists under Reference with proof `?`.
- Seven FX2 rows fit in place; up to 32 go to a longer list, whose
  scrolling on the panel is inferred from stock's fifteen-row list, not
  measured.
- Two selected modules that claim one address, id, hook or buffer are
  refused by name; `make modules` prints the pairwise matrix.
- `settings` fixes or re-defaults a module's settings for this image:
  `(store id, setting name) -> value` or `Pin(value)`. A module whose
  setting chooses its code builds that code; a run-time setting (USB's
  `TRACKS`, `MAIN`, `CUE`, `MASTER`, `IN`, `MIDI`) is changed on the unit unless
  the remix pins it: `settings={("octabam.usb", "IN"): Pin("OFF")}`.
  `python3 tools/remix/brain.py resolve mine` prints every setting and the
  layer its value came from; the build report prints the same.
- `defaults` replaces a knob's default in this image:
  `(module key, mode, knob) -> byte`, with `mode` None for the knob's own
  default or a MODE label for that mode's view, and `knob` the name the
  panel shows: `defaults={("DELAY SERVER", "GRAIN", "PTCH"): 96}`. A value
  outside the knob's count is refused.
- `hidden`, `named`, `grains`: [MODULES.md](../contributing/MODULES.md).

Then:

```bash
make docs                       # re-render remixes/README.md (make check refuses a stale index)
make check REMIX=mine           # build + cycles + every gate + boot under the port
make image REMIX=mine BUILD=2   # -> out/OCTATRACK_OCTABAM2.bin
```

`make check` also refuses a remix directory without a `README.md`. A remix
whose parameter layout differs from the one a project was saved under
needs the stamp before play ([BUILDING.md section 6](BUILDING.md#6-after-the-flash)).

## Known gaps

- Per-mode `defaults` land on the unit by `stamp-defaults`.
- Stock rows are not priced.
