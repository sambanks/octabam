# Composing a remix

A remix is a selection of modules: which effects the unit's FX1 and FX2
choosers list, in which order, and which firmware mods ride along. Compose
one in the remixer (`make remix`), or write `remixes/<name>/remix.py` by
hand; then build and flash it as in [BUILDING.md](BUILDING.md) sections 3–6.

## Setup

[BUILDING.md sections 0–2](BUILDING.md#0-what-you-need) first: the Xcode Command
Line Tools, Homebrew, Python 3.10+, `brew install cmake uv`, then
`make setup` and `make os && make recon`. The remixer also needs:

```bash
make emu-setup                      # uv: textual, unicorn, sounddevice into .venv
python3 scripts/make_test_audio.py  # dry wavs to audition on -> out/test_audio/
REMIXER_SOURCES=out/test_audio make remix
```

| missing | what happens |
|---|---|
| `make emu-setup` | `make remix` exits: `the remixer frontend needs textual -- run: make emu-setup` |
| `make setup` or `make os && make recon` | nothing builds or renders: every image starts from `out/raw/section_3_MAIN_OS.bin` and is assembled with `dsp_asm`, rendered with `dsp_host` |
| a source folder | the SOURCE row is empty: it lists the wavs in `REMIXER_SOURCES`, else the folder `d` last chose, else `out/dry/`, which nothing creates |

Playback is `afplay` (macOS). On Linux or WSL2 `r` renders and nothing
plays until `afplay` exists; WSLg already runs a PulseAudio server wired to
Windows audio, and `paplay` from `pulseaudio-utils` takes a wav:

```bash
sudo tee /usr/local/bin/afplay >/dev/null <<'SH'
#!/bin/sh
exec paplay "$@"
SH
sudo chmod +x /usr/local/bin/afplay
```

`exec` matters: the remixer stops playback by killing that pid.

## The remixer: three panes

Nothing in it touches hardware. `ok-ms` loaded (`l`), the cursor in
AVAILABLE, a 118-column terminal (captured while `ok-ms` carried Octakit
and KITS RELOAD, before 6 Oct 2026):

```
 Available                      Choosers · ok-ms                BusDelay
── Effects: the bus ──           FX1  10 rows                   Effects: the bus · Bus · id 0x06 · FX2 · tracks 1-4
   BusDelay           FX2         1 Filter                      Multi-mode delay: CLEAN / pitched GRAIN cloud / REVERSE, tape wow.
   BusVerb            FX2         2 Equalizer                   FX1  no row — and cannot take one: a bus server is one per core
   Mode Defaults      ✓           …                             FX2  pins all 4 buffer slots on the core serving tracks 1-4
   Send               FX2        FX2  17 rows                    SOURCE …/out/test_audio
── Effects: on a track ──         · Midi Scenes                  DEL      0    [............] p1
   Character          FX1+FX2     · Octakit                      FDBK    60    [######......] p1
   Spectrum           FX1+FX2     · Kits Reload                  WET    127    [############] p1
── Machines and the sequencer ──  1 Filter                       MODE   CLEAN  [············] p2
   Repitch            ✓           …                              TIME    20    [##..........] p2
Budget free:  words A none  ·  words B none  ·  buf A 4/4  ·  buf B 4/4  ·  rows 17  ·  cave 4,412 B
```

(Rendered from the app under Textual's test pilot on 30 Sep 2026, rows
elided.) Three panes need 118 columns, two need 92; narrower shows one
pane at a time, with a tab bar naming all three (`WIDE_COLS`,
`TWO_UP_COLS` in `tools/remix/app.py`).

| key | does |
|---|---|
| `tab` / `shift+tab` | next / previous pane |
| `up` `down` (`j` `k`) | move within a pane |
| `left` `right` (`h`) | in UNIT: step the knob ±1 (`shift` ±10); in CHOOSERS: move the row |
| `enter` | AVAILABLE: add the highlighted module to the image; CHOOSERS: remove the row from its list |
| `1` | give the highlighted effect an FX1 row, or take it off |
| `f` | pick the fallback explicitly |
| `x` | apply the fix the ⚠ line names |
| `l` / `s` / `K` | load a remix (or `stock`) / save the selection as one / reset to stock |
| `c` | `make check` |
| `r` / `space` / `esc` | render the effect under the cursor on the source and play it / replay / stop |
| `a` / `b` / `,` / `.` | mark A / render and mark B / play A / play B |
| `d` | choose the sample folder |
| `?` / `q` | help / quit |

**AVAILABLE** is everything that could be in an image: modules grouped
as in the module table (the bus, on a track, machines and the sequencer,
Parts/Kits/scenes, MIDI and USB, fixes, reference), then the stock effects
the unit ships. `✓` marks what the selection holds; for an effect the `FX1+FX2`
column is which choosers it *can* appear on (`stock.fx1_ids()` from the
pristine image). A firmware mod (midisc, KITS, the bridges, the fixes)
has no chooser; its column is the ledger's verdict against what is loaded
— `✓` shares the image, `x direct-jump` names what it collides with, and
`· add <bridge>` names the bridge that would clear it (the same
`ledger.check` the build refuses on). The unit pane lists every ledger
line the pointed-at module is party to. `enter` adds and displaces
nothing.

**CHOOSERS** holds both of the unit's effect menus, stacked, in panel row
order; `left`/`right` is a real edit. FX2 starts empty (every row is one
the remix listed); FX1 starts as stock's ten, with the firmware's own NONE
as row 0, never shown and never losable. Leaving an effect off a chooser
removes the row; its code, descriptor and dispatch stay stock. `◀fb` marks the fallback; `·` in the number column is a ColdFire
patch with no row. Each module's word cost comes from the real assembly
the background rebuild runs. The pane closes with one line: the per-payload
budget (`A 74 free · B 5 free`), a ⚠ naming what to remove, or `building…`;
it ends in `boots` when the built image reaches the RTOS handoff in the
emulator.

**UNIT** follows the cursor, so pointing at something in the library
previews it before you add it: kind, id, menus, track range, the one-line
doc, the resource line, and the drawn parameters with values. Values live
per module, seeded from the manifest defaults. `SOURCE` is the first row;
`left`/`right` cycles the wavs in the source folder.

## What costs what

Rows are not the currency; words are. A chooser row costs nothing (seven
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

The ⚠ line describes the image, not the cursor, and names the cause and
the count; `x` applies its fix and removes every row the build named:

| after you add | what happens |
|---|---|
| no safe fallback | SEND is added: `added Send as the fallback` |
| a buffer clash | `x removes Flanger, Chorus, Spatializer, Comb Filter — they need the same buffer` |
| past a payload's region | the build refuses and names it |

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

The remixer opens with nothing harvested: all 6,158 words of a payload's
effect code belong to a stock effect that is using them. Taking an effect
off **both** choosers is the decision to give up its words
(`stock.harvested`); removing it from one menu while it still has a row on
the other frees nothing. The three reverbs are only the default harvest:
the biggest, and FX2-only, so taking them costs FX1 nothing. The thirteen
DSP effects are laid out contiguously, so any unbroken run of them is
ground a module can be placed into; the map under the budget draws a
bracket per run. A routine that a kept effect calls inside a harvested one
stays where it is and the run is placed around it (DARK REV calls 35 words
in SPRING's span, PLATE calls 93 in DARK's, five effects call 27 in
FILTER's; `stock.pinned`, printed by the build as `kept (... called by
...)`).

A module must fit inside one run: two runs of 1,500 words will not take a
2,000-word module, so the budget names the largest opening beside the
total. Harvesting an effect that sits between two runs joins them.
Harvested is not unlisted: an effect keeps its algorithm wherever your
code did not reach (the region packs from the lowest address upward and
the build reports which survived), so an effect can be listed and
harvested at once, `✓⌁`, until the placer reaches it; the build then
refuses the row and `x` removes it.

The resource line under the doc:

| | says |
|---|---|
| a listed stock effect | `727 words, already placed` |
| one given up (off both menus) | `594 words — off both menus, so they are yours to place into` |
| DELAY | `no DSP words — it runs on the ColdFire side` |
| a module with DSP code | `2,411 of 2,724 words` |

Stock rows are not in the cycles figure (only FILTER's is measured, 192 per
instance); the row says `14 stock rows not counted`.

### FX1 rows

`1` gives the highlighted effect an FX1 row (`Remix.fx1`, written by `s`).
It costs no words (the DSP dispatch is shared by both menus; the list is
rebuilt in the cave with FX1's three `lea` references, its id lookup and
its cursor table repointed) and it costs cycles: FX1 is four more slots on
the same four tracks, so an effect on both menus can double the worst
per-core load (4× → 8× instances). Only a buffer-free
insert, or an allocator reader declaring `buffer_words` ≤ 3,072, may take
one; the UNIT pane says which cannot and why (`FX1 no row — and cannot
take one: it sizes its buffer for an FX2 slot (16,384 words)`; `FX1 ONLY:
passes dry on FX2`). A `replaces` module is listed by its own key. Every id
a shortened FX1 list drops has its cursor row clamped to 0.

## Hearing

`r` renders the effect under the cursor on the SOURCE wav through the
audition backend (`tools/remix/audition.py`) and plays it; `space`
replays. `a` parks the current render as A; point at the rival, `b`
re-renders it on the same source; `,` / `.` flip between them. `d` sets
the source folder and remembers it in `out/_audition/remixer.json`
(`REMIXER_SOURCES` overrides; default `out/dry/`; `WORKBENCH_SOURCES` and
`out/_audition/workbench.json` are still honoured).

Six of the stock effects render dry at their defaults (PHASER, FLANGER,
CHORUS, COMB at `MIX 0`; SPATIALIZER, DELAY at `SEND 0`): stock defaults
are the firmware's own, and the UNIT pane says `⚠ MIX is 0 — this renders
DRY`.

How each effect is rendered: [`tools/remix/README.md`](../../tools/remix/README.md).

## The image follows the selection

Every selection change rebuilds (~0.3 s) and re-boots the ColdFire
emulator (~5 s) in the background; the panel on the right draws what
CHOOSERS says. The emulator draws the FX1 and FX2 choosers and an effect's
page with the firmware's own code. Its limits (`tools/emu/README.md`): no
audio, no key matrix, and item-level menu descent needs the real key
handler.

## Editing in another window

The remixer follows the source: edit a module's `.asm` or manifest and
`r` re-renders it (the scratch image is cached against the newest mtime
under `modules/`).

## Theming

`REMIXER_THEME` picks any built-in Textual theme (default `ansi-dark`;
`WORKBENCH_THEME` still honoured). Colours: aqua = a module, plain =
the box's own; green fits, ochre is a trade or caution, red blocks; a
knob's level is a warm ramp by where the value sits in its range; the
source wav muted blue; the fallback soft purple; the panel frame grey.

## Writing `remix.py` by hand

A remix is one directory, `remixes/<name>/`: `remix.py` holds the
selection, `README.md` says what is in it and where it has run. The
registry discovers every `remixes/*/remix.py` and `remixes/test/*/remix.py`;
nothing else registers it. A remix that carries one module for that
module's gates goes in `remixes/test/<name>/`; names are unique across
both, and every tool takes the bare name (`make check REMIX=miniverb`).

Copy an existing `remix.py` and edit it, or save one from the remixer (`s`). `remixes/bottleservice/remix.py`
  is the bus with stations, hosts and ColdFire mods,
  `remixes/test/euclid/remix.py` an insert beside the stock effects,
  `remixes/ok-ms/remix.py` two ColdFire mods and no DSP code.

```python
from remix.schema import Proof, Remix

REMIX = Remix(
    name="mine",                       # == the directory name
    doc="One line: what is in it.",
    family="effects",                  # index section: rig, effects, mods, reference, probes
    proof=Proof.CHECK,                 # CHECK, RENDER, PORT, HARDWARE
    proof_note="make check, 28 Sep 2026",
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
- `family`, `proof`, `proof_note` are the columns of the remix index.
  Without them the remix lists under Reference with proof `?`.
- Seven FX2 rows fit in place; up to 32 go to a longer list, whose
  scrolling on the panel is inferred from stock's fifteen-row list, not
  measured.
- Two selected modules that claim one address, id, hook or buffer are
  refused by name; `make modules` prints the pairwise matrix.
- `settings` fixes or re-defaults a module's settings for this image:
  `(store id, setting name) -> value` or `Pin(value)`. A module whose
  setting chooses its code (USB AUDIO OUT's `LAYOUT`, USB AUDIO IN's
  `INPUTS`) builds that code:
  `settings={("octabam.usb-audio-out", "LAYOUT"): Pin("MASTER")}`.
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

- Per-mode `defaults` apply in the remixer; on the unit they land by
  `stamp-defaults`.
- The emulator limits above.
- Stock rows are not priced.
