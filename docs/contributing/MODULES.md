# Writing a module

A module is one contribution: a DSP effect, a bus client, a ColdFire
behaviour patch, or a combination. A remix is a named selection of modules
composed into one image. `make modules` prints what exists; `make bus
REMIX=<name>` builds a selection. `AGENTS.md` lists the traps; the ones a
new module can walk into are repeated here where they apply.

Decide first which kind you are writing.

- An **insert** processes its own track's frames in place: no bus role, no
  shared-window claim, placed in both payloads, runnable on any track and
  several at once. `bus_role=BusRole.NONE`, `ybase=YBase.NEVER`, and most
  of the hazards below do not apply. `modules/character/` is the worked example.
- A **server** owns a bus accumulator, is bank-bound to one core, and takes
  part in the rotation, the housekeeping election and the auto-gain. There
  are two; [`modules/send/README.md`](../../modules/send/README.md).
- A **bus client** (`send`) taps its track into the bus.
- A **ColdFire module** changes what the firmware does (parts, kits, menus,
  MIDI, bug fixes) and touches no audio; midisc (`modules/midi-scenes`)
  and Octakit (`modules/octakit`) are this shape. Skeleton
  `modules/_template_cf/`, worked example `modules/repitch/`, section
  "Declaring a ColdFire module" below; `docs/contributing/PLACEMENT.md` says
  where the bytes land.

## The worked example: CHARACTER

`modules/character/` is an in-place insert: seven knobs, no bus role, no
buffer, both payloads, any track.

```
modules/character/manifest.py      the declaration -- knobs, donor, id, ModeViews
modules/character/character.asm    the engine -- init, proc, in place
modules/character/README.md        status, measured vs inferred, what is open
remixes/bottleservice/remix.py     a remix that carries it (FX1 and FX2)
tools/verify/verify_character.py   render gates against a float reference
```

```bash
make check REMIX=bottleservice
python3 tools/remix/audition.py character out/dry/drums_110.wav DRV=64
python3 tools/verify/verify_character.py
```

`modules/_template/` is the skeleton to copy: a manifest with every field
commented, and the `README.md` shape every module page follows (Knobs,
Measured, On the unit, Open, Gates).

Give your module one gate whose answer you can compute by hand: drive
both signs of a full-scale signal (the negative half proves an `mpy` did
not become an `mpysu`), predict the arithmetic, assert to the LSB.

Make the gate name the effect it measures: an id the image does not
implement aliases to the fallback, and dsp_host renders a plausible dry
passthrough that a unity gate passes. Read the id and the knob slots out
of the manifest and refuse if they resolve to SEND's entry points
(`verify_character.py` does).

## The shape of a module

```
modules/<name>/
    manifest.py      declares the module -- exports MODULE
    <engine>.asm     DSP56300 source, if it has any
    <patch>.s        m68k source, if it patches the ColdFire
    README.md        what it is, what is measured, what is open
```

`tools/remix/registry.py` discovers every `modules/*/manifest.py` that
exports a `MODULE`; directories starting with `_` are skipped.
`tools/remix/schema.py` is the vocabulary; its comments carry the reasoning
behind each field.

Five fields are the README's module table, rendered by `make docs`
(`tools/remix/index.py --write`) and held current by `verify_docs`:

```python
    category=Category.TRACK,            # BUS, TRACK, MACHINES, PARTS, MIDI_USB, FIXES, REFERENCE
    author="repeat98", author_url="https://github.com/repeat98",
    proof=Proof.RENDER,                 # CHECK, RENDER, PORT, HARDWARE
    proof_note="its own render gates; not on hardware",   # the unit, image, date; or the gate
```

`category` is where the module sits in the table, the index and the
remixer's AVAILABLE pane. `proof` is the vocabulary of the last column:
`CHECK` builds and boots under the port, `RENDER` was heard or measured
locally and never flashed, `PORT` has a gate under the ColdFire port that
pins its behaviour, `HARDWARE` ran on a unit. The selftest refuses a
module without all of them. A module whose manifest is executed from an
author's repository adds them with `dataclasses.replace` (`modules/synth`).

Two more fields are the checks. `gates` names the verifiers `make check`
runs when a remix carries the module, and `dear` its dearest knob
settings:

```python
    gates=(Gate("tools/verify/verify_character.py", remix_arg=False),),
    dear={"DRV": 127, "FOLD": 127, "COMP": 127, "MIX": 127, "WDTH": 127, "SAT": 0},
```

`tools/verify/module_gates.py` collects the selection's gates, runs each
script once (two modules naming one gate share it) with `REMIX` and
`BUILD` exported, the remix name as `argv[1]` when `remix_arg` is set,
and `.venv/bin/python3` when `venv` is set and the venv exists. An
`"isolated"` gate (the default) builds its own scratch image or none and
runs before the selected image is restored; an `"image"` gate reads
`out/mainos_bus.bin` and runs after `make bus` and the shared set gates
(`verify_tempobus` reads the card `verify_set` staged). A script that
does not exist fails; the gates every remix gets (the ledger selftest,
the docs, the knob census, the dirty-state render, the menu, the set
under the port) stay in the Makefile (`docs/contributing/TESTING.md`). Until 27 Sep 2026 the Makefile listed every
module's verifier by hand, each one written to SKIP when the remix
lacked its module.

`dear` is every knob at its dearest setting, by the Param's own name: the
mode the pricer calls the worst loop, knobs that gate work (a send at 0
registers nothing, MIX 0 short-circuits a stage) at their maximum. The
pressure render and the stress fixture read it; `make accept` is blocked,
by name, for a remix with a DSP module that has none. The schema checks
each name against `params` when the manifest loads, so a knob rename
refuses the build rather than failing a fixture after the merge.

`make remix` opens the remixer (`tools/remix/app.py`, Textual, provisioned
by `make emu-setup`; manual `docs/guide/REMIXER.md`). It derives a
placement role and a track range for every module (`tools/remix/rig.py`):

- **bus effect** (`harness.is_server`): one payload, declared in
  `dsp.payloads`; payload A serves tracks 5-8, payload B tracks 1-4
  (measured). A server that does not declare a single payload is refused.
- **insert** (a `DSP_EFFECT` with a menu, no server role): both payloads,
  any track.
- **stock** (`Kind.STOCK`, `tools/remix/stock.py`): a stock FX2 effect kept
  in the chooser; any track.
- **system** (SEND, ColdFire patches): plumbing; never sits on a track.

Every effect is auditionable through `tools/remix/audition.py`, and
`tools/harness/send_probe.py --set NAME=VAL` drives any knob of any module
through its own `knob_map()`. Every render and A/B mark is journalled to
`out/_audition/log.jsonl` (track, effect, source, every knob).

Two `Param` fields exist for the remixer (the build never reads them):
`doc`, one line shown under the knob cursor, and `labels`, one short label
per value of a stepped select (length pinned to `count`). The selftest
requires a `doc` on every named, drawn param of every menu-bearing module.

## The two identifiers

```python
MODULE = Module(
    name="busverb",          # the directory. Must match.
    key="REVERB SERVER",      # the build identifier
    ...
)
```

`key` appears in the build report, and the build report is API:
`verify_delay.py`, `verify_roll.py` and `verify_burn.py` parse build
stdout. Changing a key, or rewording a report line, is a breaking change.

## Declaring an effect

An effect has a `MenuEntry` (its row in the FX2 chooser), twelve `Param`s,
and a `DspSection`.

### The descriptor is cloned from a stock donor

Every field you do not write stays the donor's, so the schema makes you
state things you might assume:

- **A formatter overrides the value count it sits beside.** A slot with a
  correct count, default, name and enable bit draws as whatever the donor's
  formatter draws: an enumerated renderer with three labels asked to draw
  0..127 draws no knob at all; a bipolar pair draws a count-5 select as a
  balance dial. Declare `formatter=` per slot; `verify_menu` checks the
  renderer against the count.
- **Four per-parameter arrays carry the drawing**, `P`-relative
  (`docs/firmware/PARAM_PAGES.md` section 2, section 7): `P+0x9a` count (drawn on a
  fixed 0–127 scale: count 16 = ⅛ of the travel), `P+0x0ca` formatter A,
  `P+0x0fa` widget B, `P+0x12a` (zero for a stepped control; 20 of 20
  stock stepped params). A clone inherits all four from its donor.
  Stepped pairs: CHORUS.TAPS (count 5) `0x4003c718` / `0x40047254`
  (BusVerb's MODE uses this); SPATIALIZER.PHSE (4) `0x4003bbc0` /
  `0x400467a4`; FILTER.Q (4) `0x4003bc60` / `0x40046c28` (draws
  `none|HP|LP|BOTH`: the words come from the renderer, not the
  descriptor). Every enabled slot needs an explicit in-range default
  (`verify_menu`).
- **A `name` of `None` inherits the donor's; `b""` blanks it.** Write the
  name explicitly even when the donor has it: the harness reads these.
- A labelled select wider than five values normally falls back to a plain
  dial and uses only part of its 128-position arc. Declare
  `formatter=Formatter.WIDE_STEPPED` to keep its labels while scaling the
  drawing across the full arc. The build installs one shared hook for all
  such slots; modules do not claim the stock dial site themselves.
- **`link=True` draws the panel's link element** between this knob and the
  one on its left (stock's STRT/LEN, BASE/WDTH): bit 1 of the slot's enable
  nibble (`PARAM_PAGES.md` section 3b). Display only; the pair must sit in one row
  of three (never across slots 2–3 or 8–9), and the left knob must be drawn.
  `verify_menu` checks the bit against the manifest.
- **A default outside its own value count is used as an index** and stalls
  the sequencer; the schema rejects it at construction. **A stored value
  does the same, and the schema cannot see it**: a part saved under an
  older layout feeds the new one its old bytes. Changing a slot's count or
  moving a select means stamping every project before anyone presses play
  (`tools/hw/ot_project.py stamp-defaults <project> <remix>`), not
  re-selecting the one track under test: the sequencer runs every track of
  the part.
- **A slot the panel does not draw is unreachable**, however completely it
  is implemented: set `active=True`. The inverse holds too: a slot can draw
  a knob and publish nothing (`docs/firmware/PARAM_PAGES.md`).
- **Both name fields are NUL-terminated.** `abbr` is 5 bytes = 4
  characters; `fullname` is 13 bytes = 12, and the build tag is appended
  after your string. A 5-character abbr drew correctly and threw a line-F
  exception (faulting PC `0x48454C4C` = "HELL") the moment a parameter was
  LFO-modulated. The schema rejects both over-lengths and `build_bus.py`
  re-checks the string it writes, tag included.

### The five tables an effect needs

| # | table | keyed by | if missing |
|---|---|---|---|
| 1 | id lookup `0x400d5f58` (FX1) / `0x400d5fdc` (FX2) | id | descriptor unresolvable |
| 2 | chooser list `0x400d6060` (FX1) / `0x400d6090` (FX2) | position | not offered |
| 3 | its own 402 B descriptor, copied from `P` | — | copied from `E`: correct name and id, no knobs (the enable bitmap falls off the end) |
| 4 | the id byte at `P+0x03` | — | two list entries sharing a descriptor are one effect |
| 5 | id → cursor position `0x400d6150` | id | selecting it jumps to NONE |

(3)/(4): `FUN_40052474` does `*(Part+0x8ed88) = (char)*(int*)list[cursor]`,
the low byte of the word at `P+0`. (5): `FUN_4005996c` counts the list to
its terminator, then seeds the cursor from `0x400d6150[id]` (`FLTR`→1,
`EQ`→2, … `DARK`→14); an id absent from it selects position 0 = NONE.

`tools/build/build_bus.py` writes them (`FX1_IDS`/`FX2_IDS`,
`FX1_LIST`/`FX2_LIST`, the descriptor clone, `ID2POS`) from the module's
`MenuEntry`.

### Page 2: even slots are knob fields, odd slots are companion fields

Slots 6/8/10 are delivered in bits 16-23 of `r6+$c/$d/$e` and slots 7/9/11
in bits 8-15 of the same words (`docs/firmware/PARAM_PAGES.md`). Any slot
may carry any count (stock CHORUS TAPS sits on slot 6, stock FILTER's DIST
knob on slot 11).

Put a MODE on an even slot: the panel's page-2 knob editor (`0x4003a474`)
writes even slots (slot 6 hardware-confirmed), so a select there is
settable from a cave or a main-menu screen through the firmware's own
routine. An emulator run showed the same editor writing all six page-2
slots (`docs/firmware/MAINMENU.md` section 9c-ii / section 9e), so the odd-slot
restriction is in doubt; an even slot is the proven choice. The DSP read
must take the field the slot is delivered in.

### FX2 ids

`0x00`-`0x03` are the values stock treats as synonyms for "no effect"
(correct chooser names, dead knobs, garbage audio); the schema rejects them.

The fifteen stock ids are refused without `replaces` (`schema.STOCK_FX2_IDS`):
the two DSP dispatch tables are indexed by the raw id and shared between
FX1 and FX2, so a module on a stock id replaces that effect's code wherever
the id is selected, FX1 included, and a remix that omits the module then
aliases the id to SEND, which takes the stock effect away from FX1 too.
Free ids: `0x06 0x07 0x09 0x0a 0x0b 0x0e 0x0f 0x17 0x1a 0x1b 0x1d 0x1e
0x1f`, of which `0x0b 0x0f 0x17 0x1a 0x1e 0x1f` are unclaimed (`make
modules` is the current word). Beside OCTAKIT a module on a chooser row
takes one of `0x1c` or below: her selection wrapper halts the unit on an id
past stock's last (RETURNS on `0x1e`, 30 Sep 2026), and the registry
refuses it.

The registry is the arbiter: `registry.modules()` refuses two modules on
one id at import, whether or not any remix selects both. `make modules`
prints what is claimed.

### Per-mode knob names and defaults: `ModeView`

A multi-mode effect reuses its knobs. Declare the difference:

```python
mode_slot=7,                       # which slot carries the MODE select
mode_views=(
    ModeView(mode=0, defaults={0: 40, 1: 60}),          # CLEAN
    ModeView(mode=1, names={6: b"SCTR", 8: b"DENS"},    # GRAIN
             defaults={0: 36, 6: 40, 8: 127}),
),
```

Both maps are sparse and optional. `names` renames a slot for that mode
(four characters); `defaults` is where the other knobs land when the
operator arrives at this mode.

| | the remixer | the unit |
|---|---|---|
| `names` | the UNIT pane's rows follow the current MODE (`Module.knob_map_in`); `send_probe --set SCTR=40` resolves the alias | `tools/build/mode_names.py` emits a MODE formatter that rewrites the descriptor's name fields before printing its own word |
| `defaults` | applied the moment MODE changes | `modules/mode-defaults` (in the rig): the FX1 and FX2 page-2 editors are detoured, and a MODE turned on the panel writes the view -- page 1 through the stock page-1 writer, page 2 with the editor's own stores; without the module, `stamp-defaults` writes them; a MODE over CC MAP goes through the same unit (the cave calls it) |

The unit half needs no new hook: a descriptor carries its twelve parameter
names as 12 × 6 bytes at `E+0x4e`, the clones are writable RAM, and every
stepped select already has a formatter cave the panel calls as `fmt(buf,
value)` with the value in hand. `tools/verify/verify_modenames.py` (in
`make check`) calls each MODE formatter on the emulated ColdFire and reads
the names back out of the clone.

The MODE select also names itself: its cave writes the value's word into
its own name field before printing it, so the knob reads CLEAN / GRAIN /
REVRS rather than MODE (Character's SAT and BusVerb's MODE declare
`mode_slot` for this alone). Every other select keeps its name and the tick
widget flashes the word on a turn — on image 26 SIZE / SHFT / RATE
reading `93MS` / `RUN` / `+12` / `1x` did not say what the knob was (Sam,
15 Sep 2026; image 27 with the names back: "that's better").

Two limits, inferred: the rename lands on the draw after the one that
formats MODE if the panel draws names first (turning the encoder redraws);
and the descriptor is shared by every track running the effect, so two
tracks in different modes have one set of names between them.

Each mode's block costs 8 bytes per renamed slot plus a terminator in the
cave. Rename a slot whose meaning changes; a knob merely unused in a mode
keeps its name and says so in its `doc`.

### A station

The stations (`modules/spectrum/`, `modules/character/`,
`modules/modulation/`) are per-track inserts on a stock effect's id, FX1
only (`Claims(fx1_only=True)`, below). They never housekeep: an FX1
instance on track 5 runs before that track's FX2 instance, and position 0
housekeeps unconditionally, so an electing FX1 participant would flip the
rotation twice in the first block. The layout alphabet is exhausted
(A-W, Y, Z), so stations take digits as `layout_char`; `send_probe --feed S
--set S:SEND=100` feeds the tone to a station's own track. Every slot the
sample loop touches sits below `$40` (a displacement past 63 assembles to
the two-word form).

## Keeping stock effects in the chooser

Every image replaces the FX2 chooser wholesale. Which stock effects are
given up is derived from the choosers: an effect on neither FX1's nor
FX2's list is consumed (`stock.harvested`); by default PLATE, SPRING and
DARK REV, whose 2,724 words every module packs into. The rest keep their
code, descriptor and dispatch entries in every image.

`tools/remix/stock.py` registers them under their own keys (`"FILTER"`,
`"CHORUS"`, `"DELAY"`, …), so a remix keeps one by listing it like a
module, in the position it should draw at:

```python
modules=("REVERB SERVER", "DELAY SERVER", "SEND", "FILTER", "LO-FI", "TEMPO SYNC")
```

A stock row is a list row and a cursor position; `make cycles`
does not count it (only FILTER's cost is measured, 192 cycles per
instance). The build writes its list row and cursor position;
`verify_menu` checks that its descriptor and id entry are byte-identical to
stock. A stock effect a remix leaves out is left alone entirely: an old
project that selects it still runs it, it just has no row.
`remixes/test/mods/remix.py` lists all fourteen.

Two rules, both enforced:

- **Four stock effects allocate an instance buffer**: SPATIALIZER, FLANGER,
  CHORUS, COMB read `X:0x213` at init (measured by scanning the payload
  disassembly). The allocator hands out a base per track slot, and those
  bases are the addresses BusVerb's tank and BusDelay's line hardcode; the chooser is one list for all eight tracks, so an image cannot
  keep them apart. The ledger refuses the pair
  (`Claims.stock_instance_buffer` against any module with
  `owns_fx2_buffers` or a non-`NEVER` `ybase`). All four are legal in an
  insert-only remix.
- **More than seven rows moves the list.** The list cave at `0x400d6b00`
  holds seven rows before the first clone; a longer list goes to the tail
  of the stock zero run (`LONG_LIST`, 32 rows) and the viewport is capped at
  the screen's seven. Scrolling the relocated list on the panel is inferred
  from stock's fifteen-row list; no image with more than seven rows has
  been flashed.

Stock rows appear in the remixer with their real knobs: `stock.py` reads
each descriptor's names, defaults, value counts and enable bitmap out of
the pristine image (`out/raw/section_3_MAIN_OS.bin`); a duplicated label
gets a `2` suffix on the later slot. A select carries the firmware's own
labels: `tools/build/stock_labels.py` runs every formatter for every value
on the emulated ColdFire and checks the result in as
`tools/remix/stock_labels.json` (`make stock-labels`). Each stock effect
has a `layout_char` (L E J P A C Z O K I Y); `--pick chorus` also works.

They render locally the way an insert does, from a dump of the stock
image's payload A (`out/dsp/_stock_A.mem`), with `dsp_host -alloc 1` so a
buffered effect gets Y:0x4000 as the hardware gives track 1, and `-audio 0`
because the dispatcher's `move #$0,r0` puts the audio block at X:0 and
stock effects use X:0x20-0xff as scratch. Measured on a 438 Hz tone at
0.5 FS:

| effect | result |
|---|---|
| FILTER | unity at defaults; BASE=20 WDTH=10 Q=100 takes the tone down 27 dB |
| EQ, DJ EQ, PHASER, SPATIALIZER, COMB, COMPRESSOR | bit-exact unity at defaults |
| FLANGER | MIX=0 is a bit-exact dry pass; full modulation flanges |
| CHORUS | MIX=0 exactly dry; MIX=127 puts sidebands on the tone |
| LO-FI | renders only with `tools/patches/dsp56300.patch` (`mpyri`); DIST, SRR and AMF/AMD act. At all-zero settings it passes the tone at exactly 2× (+6 dB); whether the unit does the same is unmeasured |
| DELAY | no DSP code (the Echo Freeze delay is ColdFire-side); the audition refuses |

A stock effect that sounds wrong locally is evidence about the harness or
emulator before it is evidence about the effect.

## What an unimplemented id falls back to

The build rewrites the FX2 dispatch tables wholesale, so every one of the
32 ids points at a descriptor and a DSP entry, including id 0, which is
what a fresh part's FX2 slot holds. `Remix.fallback` names where they go:

- **`fallback="SEND"`, for a remix with a bus.** The send client passes the
  audio through and only taps it, so a track that selects a missing effect
  becomes a send. No stock effect is a safe target (it would process the
  unknown id on whatever knobs the part holds), and the target must be a
  module of ours (it needs a cloned descriptor, a cursor position and placed
  code).
- **`fallback="NONE"`, for a remix with no bus.** Unimplemented ids resolve
  to the firmware's own NONE: the descriptor a stock chooser carries at list
  row 0 and the per-payload null stub. It costs one chooser row (four bytes
  of cave) and no words.

`NONE` is refused beside any bus participant (`registry.remix()`).
Housekeeping (flipping the rotation word and clearing the accumulators) is
gated to payload A and done by the first core-0 participant dispatched that
block; with SEND on every unassigned track, core 0 always has one. Under
`NONE` an unassigned track runs nothing, so a project with tracks 5-8 all
unassigned would have no housekeeper and a server on the other core would
read an accumulator never rotated and never cleared. No local test can
settle it: `dsp_host` runs both cores lock-step or under a chosen
interleave.

Declare `bus_client=True` in a module's `Harness` if it writes the shared
accumulators; `is_server=True` is the other half. `schema.on_the_bus()`
reads both.

## Declaring DSP code

```python
dsp=DspSection(
    asm="modules/<name>/engine.asm",
    priority=1,
    ybase=YBase.XBUS,
    r7_latch_slot=None,
    gate_label="bus_notfirst",
)
```

- **`priority` is byte-load-bearing.** The donor region is packed in this
  order. The send client is first because the fallback alias needs its
  entry points to exist; the delay is last so the region's trailing free
  words belong to it.
- **`ybase` decides when `$30000` is rewritten** to the payload's own half
  of the shared window: the delay in every build, the reverb once the bus
  has moved into the shared window, the send client never. The rewrite is a
  blanket string replace over the whole source, comments included; a
  shared-window address that must not move to the other half cannot be
  spelled `$30000`, and the literal is censused.
- **`ptable`**: a tuple of words the build parks in the stock curve bank
  (X:0x4840) and points the source's `$fab1e0` literal at.
- **`hooks`**: entries from STOCK P code (`schema.DspHook(site, stock,
  label)`). The two stock words at `site` become `jsr >label` after
  placement, the build asserting them first; the section replays the
  displaced instruction. A section with hooks and no `MenuEntry` is placed
  on `payloads` only and takes no dispatch entry: USB AUDIO IN's RX inject
  at the frame head, P:0x88, on payload A. The ledger refuses two sections
  on one site of one payload.
- **Program space is per core.** `make bus REMIX=<name>` prints the live ledger.

### Rules for DSP code, each established on hardware

`AGENTS.md` has the assembler and arithmetic traps (`mpy`/`a0`, `mpysu`,
labels by prefix, Tcc and the condition codes) and the dispatcher rule
(measure r7/r6/X:0x213 facts under the port). Beside those:

- Let the AGU do address work; hand-rolled modulo cost 135 cycles/sample.
- `dsp_asm` also mis-encodes illegal parallel moves silently: `x:(rN+disp)`
  is never parallel; `mpy y0,x0,a` takes a parallel move, `mpy x0,y0,a`
  discards it; XY dual moves need the X pointer in R0–R3 and Y in R4–R7.
- Two data moves between writing an address register and using it, never
  an M-register write there; no M-register write inside the sample loop.
- A modulo offset larger than the buffer is undefined, and silent.
- Absolute Y scratch at `0x800` or above; `X:0x213` is valid in init only.
- When a register holding a constant is repurposed, grep every read.
- Check the assembler's exit status, not the generator's; `| grep` masks a
  failed assemble.
- With an impulse input, a flat RMS envelope is instability, not a long
  tail.

### Page 2: even slots are knob fields, odd slots are companion fields

Slots 6/8/10 are delivered in bits 16-23 of `r6+$c/$d/$e` and slots 7/9/11
in bits 8-15 of the same words (`docs/firmware/PARAM_PAGES.md`). Any slot
may carry any count (stock CHORUS TAPS sits on slot 6, stock FILTER's DIST
knob on slot 11).

Put a MODE on an even slot: the panel's page-2 knob editor (`0x4003a474`)
writes even slots (slot 6 hardware-confirmed), so a select there is
settable from a cave or a main-menu screen through the firmware's own
routine. An emulator run showed the same editor writing all six page-2
slots (`docs/firmware/MAINMENU.md` section 9c-ii / section 9e), so the odd-slot
restriction is in doubt; an even slot is the proven choice. The DSP read
must take the field the slot is delivered in.

### FX2 ids

`0x00`-`0x03` are the values stock treats as synonyms for "no effect"
(correct chooser names, dead knobs, garbage audio); the schema rejects them.

The fifteen stock ids are refused without `replaces` (`schema.STOCK_FX2_IDS`):
the two DSP dispatch tables are indexed by the raw id and shared between
FX1 and FX2, so a module on a stock id replaces that effect's code wherever
the id is selected, FX1 included, and a remix that omits the module then
aliases the id to SEND, which takes the stock effect away from FX1 too.
Free ids: `0x06 0x07 0x09 0x0a 0x0b 0x0e 0x0f 0x17 0x1a 0x1b 0x1d 0x1e
0x1f`, of which `0x0b 0x0f 0x17 0x1a 0x1e 0x1f` are unclaimed (`make
modules` is the current word). Beside OCTAKIT a module on a chooser row
takes one of `0x1c` or below: her selection wrapper halts the unit on an id
past stock's last (RETURNS on `0x1e`, 30 Sep 2026), and the registry
refuses it.

The registry is the arbiter: `registry.modules()` refuses two modules on
one id at import, whether or not any remix selects both. `make modules`
prints what is claimed.

### Per-mode knob names and defaults: `ModeView`

A multi-mode effect reuses its knobs. Declare the difference:

```python
mode_slot=7,                       # which slot carries the MODE select
mode_views=(
    ModeView(mode=0, defaults={0: 40, 1: 60}),          # CLEAN
    ModeView(mode=1, names={6: b"SCTR", 8: b"DENS"},    # GRAIN
             defaults={0: 36, 6: 40, 8: 127}),
),
```

Both maps are sparse and optional. `names` renames a slot for that mode
(four characters); `defaults` is where the other knobs land when the
operator arrives at this mode.

| | the remixer | the unit |
|---|---|---|
| `names` | the UNIT pane's rows follow the current MODE (`Module.knob_map_in`); `send_probe --set SCTR=40` resolves the alias | `tools/build/mode_names.py` emits a MODE formatter that rewrites the descriptor's name fields before printing its own word |
| `defaults` | applied the moment MODE changes | `modules/mode-defaults` (in the rig): the FX1 and FX2 page-2 editors are detoured, and a MODE turned on the panel writes the view -- page 1 through the stock page-1 writer, page 2 with the editor's own stores; without the module, `stamp-defaults` writes them; a MODE over CC MAP goes through the same unit (the cave calls it) |

The unit half needs no new hook: a descriptor carries its twelve parameter
names as 12 × 6 bytes at `E+0x4e`, the clones are writable RAM, and every
stepped select already has a formatter cave the panel calls as `fmt(buf,
value)` with the value in hand. `tools/verify/verify_modenames.py` (in
`make check`) calls each MODE formatter on the emulated ColdFire and reads
the names back out of the clone.

The MODE select also names itself: its cave writes the value's word into
its own name field before printing it, so the knob reads CLEAN / GRAIN /
REVRS rather than MODE (Character's SAT and BusVerb's MODE declare
`mode_slot` for this alone). Every other select keeps its name and the tick
widget flashes the word on a turn — on image 26 SIZE / SHFT / RATE
reading `93MS` / `RUN` / `+12` / `1x` did not say what the knob was (Sam,
15 Sep 2026; image 27 with the names back: "that's better").

Two limits, inferred: the rename lands on the draw after the one that
formats MODE if the panel draws names first (turning the encoder redraws);
and the descriptor is shared by every track running the effect, so two
tracks in different modes have one set of names between them.

Each mode's block costs 8 bytes per renamed slot plus a terminator in the
cave. Rename a slot whose meaning changes; a knob merely unused in a mode
keeps its name and says so in its `doc`.

### A station

The stations (`modules/spectrum/`, `modules/character/`,
`modules/modulation/`) are per-track inserts on a stock effect's id, FX1
only (`Claims(fx1_only=True)`, below). They never housekeep: an FX1
instance on track 5 runs before that track's FX2 instance, and position 0
housekeeps unconditionally, so an electing FX1 participant would flip the
rotation twice in the first block. The layout alphabet is exhausted
(A-W, Y, Z), so stations take digits as `layout_char`; `send_probe --feed S
--set S:SEND=100` feeds the tone to a station's own track. Every slot the
sample loop touches sits below `$40` (a displacement past 63 assembles to
the two-word form).

## Keeping stock effects in the chooser

Every image replaces the FX2 chooser wholesale. Which stock effects are
given up is derived from the choosers: an effect on neither FX1's nor
FX2's list is consumed (`stock.harvested`); by default PLATE, SPRING and
DARK REV, whose 2,724 words every module packs into. The rest keep their
code, descriptor and dispatch entries in every image.

`tools/remix/stock.py` registers them under their own keys (`"FILTER"`,
`"CHORUS"`, `"DELAY"`, …), so a remix keeps one by listing it like a
module, in the position it should draw at:

```python
modules=("REVERB SERVER", "DELAY SERVER", "SEND", "FILTER", "LO-FI", "TEMPO SYNC")
```

A stock row is a list row and a cursor position; `make cycles`
does not count it (only FILTER's cost is measured, 192 cycles per
instance). The build writes its list row and cursor position;
`verify_menu` checks that its descriptor and id entry are byte-identical to
stock. A stock effect a remix leaves out is left alone entirely: an old
project that selects it still runs it, it just has no row.
`remixes/test/mods/remix.py` lists all fourteen.

Two rules, both enforced:

- **Four stock effects allocate an instance buffer**: SPATIALIZER, FLANGER,
  CHORUS, COMB read `X:0x213` at init (measured by scanning the payload
  disassembly). The allocator hands out a base per track slot, and those
  bases are the addresses BusVerb's tank and BusDelay's line hardcode; the chooser is one list for all eight tracks, so an image cannot
  keep them apart. The ledger refuses the pair
  (`Claims.stock_instance_buffer` against any module with
  `owns_fx2_buffers` or a non-`NEVER` `ybase`). All four are legal in an
  insert-only remix.
- **More than seven rows moves the list.** The list cave at `0x400d6b00`
  holds seven rows before the first clone; a longer list goes to the tail
  of the stock zero run (`LONG_LIST`, 32 rows) and the viewport is capped at
  the screen's seven. Scrolling the relocated list on the panel is inferred
  from stock's fifteen-row list; no image with more than seven rows has
  been flashed.

Stock rows appear in the remixer with their real knobs: `stock.py` reads
each descriptor's names, defaults, value counts and enable bitmap out of
the pristine image (`out/raw/section_3_MAIN_OS.bin`); a duplicated label
gets a `2` suffix on the later slot. A select carries the firmware's own
labels: `tools/build/stock_labels.py` runs every formatter for every value
on the emulated ColdFire and checks the result in as
`tools/remix/stock_labels.json` (`make stock-labels`). Each stock effect
has a `layout_char` (L E J P A C Z O K I Y); `--pick chorus` also works.

They render locally the way an insert does, from a dump of the stock
image's payload A (`out/dsp/_stock_A.mem`), with `dsp_host -alloc 1` so a
buffered effect gets Y:0x4000 as the hardware gives track 1, and `-audio 0`
because the dispatcher's `move #$0,r0` puts the audio block at X:0 and
stock effects use X:0x20-0xff as scratch. Measured on a 438 Hz tone at
0.5 FS:

| effect | result |
|---|---|
| FILTER | unity at defaults; BASE=20 WDTH=10 Q=100 takes the tone down 27 dB |
| EQ, DJ EQ, PHASER, SPATIALIZER, COMB, COMPRESSOR | bit-exact unity at defaults |
| FLANGER | MIX=0 is a bit-exact dry pass; full modulation flanges |
| CHORUS | MIX=0 exactly dry; MIX=127 puts sidebands on the tone |
| LO-FI | renders only with `tools/patches/dsp56300.patch` (`mpyri`); DIST, SRR and AMF/AMD act. At all-zero settings it passes the tone at exactly 2× (+6 dB); whether the unit does the same is unmeasured |
| DELAY | no DSP code (the Echo Freeze delay is ColdFire-side); the audition refuses |

A stock effect that sounds wrong locally is evidence about the harness or
emulator before it is evidence about the effect.

## What an unimplemented id falls back to

The build rewrites the FX2 dispatch tables wholesale, so every one of the
32 ids points at a descriptor and a DSP entry, including id 0, which is
what a fresh part's FX2 slot holds. `Remix.fallback` names where they go:

- **`fallback="SEND"`, for a remix with a bus.** The send client passes the
  audio through and only taps it, so a track that selects a missing effect
  becomes a send. No stock effect is a safe target (it would process the
  unknown id on whatever knobs the part holds), and the target must be a
  module of ours (it needs a cloned descriptor, a cursor position and placed
  code).
- **`fallback="NONE"`, for a remix with no bus.** Unimplemented ids resolve
  to the firmware's own NONE: the descriptor a stock chooser carries at list
  row 0 and the per-payload null stub. It costs one chooser row (four bytes
  of cave) and no words.

`NONE` is refused beside any bus participant (`registry.remix()`).
Housekeeping (flipping the rotation word and clearing the accumulators) is
gated to payload A and done by the first core-0 participant dispatched that
block; with SEND on every unassigned track, core 0 always has one. Under
`NONE` an unassigned track runs nothing, so a project with tracks 5-8 all
unassigned would have no housekeeper and a server on the other core would
read an accumulator never rotated and never cleared. No local test can
settle it: `dsp_host` runs both cores lock-step or under a chosen
interleave.

Declare `bus_client=True` in a module's `Harness` if it writes the shared
accumulators; `is_server=True` is the other half. `schema.on_the_bus()`
reads both.

## Declaring DSP code

```python
dsp=DspSection(
    asm="modules/<name>/engine.asm",
    priority=1,
    ybase=YBase.XBUS,
    r7_latch_slot=None,
    gate_label="bus_notfirst",
)
```

- **`priority` is byte-load-bearing.** The donor region is packed in this
  order. The send client is first because the fallback alias needs its
  entry points to exist; the delay is last so the region's trailing free
  words belong to it.
- **`ybase` decides when `$30000` is rewritten** to the payload's own half
  of the shared window: the delay in every build, the reverb once the bus
  has moved into the shared window, the send client never. The rewrite is a
  blanket string replace over the whole source, comments included; a
  shared-window address that must not move to the other half cannot be
  spelled `$30000`, and the literal is censused.
- **`ptable`**: a tuple of words the build parks in the stock curve bank
  (X:0x4840) and points the source's `$fab1e0` literal at.
- **`hooks`**: entries from STOCK P code (`schema.DspHook(site, stock,
  label)`). The two stock words at `site` become `jsr >label` after
  placement, the build asserting them first; the section replays the
  displaced instruction. A section with hooks and no `MenuEntry` is placed
  on `payloads` only and takes no dispatch entry: USB AUDIO IN's RX inject
  at the frame head, P:0x88, on payload A. The ledger refuses two sections
  on one site of one payload.
- **Program space is per core.** `make bus REMIX=<name>` prints the live ledger.

### Porting a published algorithm

What is borrowed is the curve or the law, re-derived under the gates; the
source code never runs here (Character, Spectrum and Modulation are the
examples; each README has its sources, `THIRD_PARTY.md` the licences).

- No per-sample division, log, exp, tan or tanh: each becomes a P-table
  (33 pairs interpolated, as Character's tables are) or moves to the
  per-block path, which has one real division.
- A sample-loop callee may contain no control transfer; forward skips in the
  loop body are priced as the worst path (`CYCLES_FORWARD_BRANCHES`).
- Lookahead needs delay memory an FX1 station has not got: limiters and
  maximizers are out.
- 2x oversampling doubles the cycle price.
- A stepped select cannot sit on page 1 (the schema refuses it): a
  page-1 control is a knob.
- Prove each mode against a float transcription of its source
  (`modules/modulation/modulation_ref.py`, `modules/spectrum/capacitor2_ref.py`).

## Declaring a ColdFire module

Two forms. Linked units in DRAM is the default; the ROM-cave form
(`CavePatch`, next section) is for the few hundred bytes that must be
ROM-resident.

```python
from remix.schema import Detour, Kind, Linked, Module, Poke

MODULE = Module(
    name="midi-scenes", key="MIDI SCENES", kind=Kind.CF_PATCH, doc="...",
    linked=(                                   # link order
        Linked("msc",   UP + "msc.s",   dram=True),
        Linked("state", UP + "state.s", dram=True),
        Linked("stub",  UP + "stub.s",  dram=True),
        ...
    ),
    detours=(
        Detour(0x400534CE, H("4ab98000001266000586"), "stub", "hold_a",
               "scene hold: read MSC when MIDI is driving", pad_to=10),
        Detour(0x4002DCD4, H("..."), "code2", "save_all", kind="lea"),
        Detour(0x40034380, H("..."), target=0x400343C4, kind="jmp"),
        ...
    ),
    pokes=(Poke(0x4004A9B0, expect=H("6612"), write=H("6012"),
                note="bne -> bra: never re-apply after Part Save"),),
)
```

A **`Linked` unit** is a GNU-as source the build assembles and links where
it places it. Symbols the unit `.global`s are what the detours name;
cross-unit references resolve in the one link (a unit may name symbols of
units before it). `dram=True` puts it in the platform runtime: every DRAM
unit in the remix linked as one image at the base of the platform's arena
reserve (1,707 pages, 10 MiB off the bottom of stock's audio page arena,
the placement Octakit and octamax have both proven on hardware;
`tools/remix/arena.py`, `docs/contributing/PLACEMENT.md`), packed, appended
behind octabam's loader and depacked there at boot. The cost is 10 MB of
the unit's 85.5 MB sample/recorder pool. `dram=False` places the unit in
one of the OS image's free zero runs (~8 KB, shared with everyone). Prefer
DRAM unless the code has to run before the loader, or you are matching an
author's ROM layout byte for byte. Code that must run before the loader
has a third form since 29 Sep 2026: `loader=True` assembles the unit INTO
octabam's loader (`tools/remix/loader.S`), which is appended after the OS
unpacked, so it runs at its link address from the OS's first instruction
and takes no cave bytes (OS SWITCH's chainloader gate, reached from the OS
entry, `modules/os-switch/chain.s`). It shares the loader's labels (prefix
yours) and needs the platform (a DRAM unit in the remix); the loader's
bytes do not change for a remix without one. A module whose DRAM is its own (a
`Runtime` with its own window) declares the pages it takes with
`ArenaReserve` so the build stacks everyone's reservations.

`Linked.include=fn` gives a unit data that depends on the REMIX: the build
calls `fn(modules)` (the remix's modules by key), writes the text it
returns beside the unit as `remix.inc`, and the source reaches it with
`.include "remix.inc"` (`modules/mode-defaults`: the view table of every
module in the image; `modules/usb-midi`: the USB configuration descriptors,
grown with the audio function when a USB AUDIO module is in the remix, with
that module's channel count; `modules/usb-audio-*`: the layout `.set` that
picks which of three builds of one source the unit is). Works for
both forms since 25 Sep 2026.

DRAM units are assembled for the chip itself (`-mcpu=54455`, ISA C):
GNU ld refuses to link an ISA-C object beside ISA-B ones, and an ISA-C
assembly of ISA-A/B text is the same bytes (refhash, 25 Sep 2026), so a
port may keep an author's `byterev`, `mvs`, `mov3q` as written.
`Linked.cpu` still governs the ROM-cave form.

A **`Detour`** rewrites one stock instruction to reach a symbol. `expect`
is the stock bytes at `site` (whole instructions), asserted before anything
is written. `kind="jmp"` for a stub that replays what it displaced and
jumps on, `"jsr"` for a callable that returns, `"lea"` to rewrite the
operand of a six-byte `lea abs.l,An`. `pad_to` nops the rest of a displaced
span longer than six bytes; `target=` names a stock address instead of a
symbol.

A **`Poke`** is a plain asserted rewrite. **`TableGrow`** relocates a stock
pointer array into free space with your symbols appended and repoints
every reference. An **`Override`** says a bridge's claim at a site stands
in for another module's (`modules/scenes-kits/`).

**`Runtime`** is the third form: a recipe (`firmware.json`) the build
compiles, packs, identity-checks and appends as its own payload of the
loader (Octakit's shape). One per image.

### The oracle

A port is done when the author's build and this repo's build agree byte for byte.
`Linked.reference=(addr, sha256)` re-links the unit at the author's own
address on every build and compares; a `Runtime` re-derives every identity
its recipe pins. `tools/verify/verify_midiscenes.py` and
`verify_octakit.py` are the standing proofs. When you port someone else's
mod, run their build against the shared stock image first and use its
output as the oracle.

### Building from the author's repository

`modules/<name>/upstream` as a git submodule, pinned to a commit (a branch
named in `.gitmodules` when the port lives on one); `Linked.source` points
into it. Nothing inside `upstream/` is edited here: a change goes to the
author as a PR, or to a fork branch that will become one. An update is a
submodule bump with the oracle still holding. `CONTRIBUTING.md` has the
etiquette.

### What the gates prove, and what they cannot

`make check REMIX=<name>` builds, runs the ledger (detour sites, pokes,
runtime writes and caves checked against every other selected module;
`make modules` prints the pairwise matrix), the oracle, and boots the image
under the ColdFire port (`tools/verify/verify_dram_boot.py`): the loader
ran once, its hash gates passed, the boot reached the RTOS handoff, and
every DRAM window reads back equal to the linked image except the bytes the
runtime wrote about itself. What the port cannot see: caches (it has none),
the recorder, and anything after the handoff.

### Pricing a ColdFire module

From Jannik Aßfalg's note beside Tape Echo (PR #357; `COLDFIRE_DELAY.md`),
the first module to run audio on the ColdFire. Its gate,
`tools/verify/verify_tapeecho_cpu.py` on that branch, is the worked
example of every item.

- **Every instruction count names its scope**: processor (ColdFire or one
  DSP core); unit (per sample, per 16-sample frame, per control frame);
  population (one instance, one core, eight tracks, both FX slots);
  included work (effect body, or the complete stock routine around it);
  control state (settled, moving, transitioning, initialising). ColdFire
  and DSP counts are not combined and neither becomes a CPU percentage:
  the meter omits instruction timing, caches, SDRAM contention, DMA stalls
  and the scheduler.
- **Edits are a separate workload.** Benchmark settled, one control
  moving, every control moving, synchronised endpoint reversals (the
  largest deltas) and mode changes with audio and state live. Report
  mean, p95, p99 and the maximum, and profile the block that produced the
  maximum.
- **Pre-fill history.** A warm start can leave a long line partly empty;
  keep a fixture that starts with nonzero history and active feedback
  beside the ordinary one. The difference is the optimisations that
  depended on silence. Hold sample rate, block size, warm-up, length,
  input, schedule and initial history identical across comparisons.
- **Profile the complete routine, exclusive attribution.** The user pays
  for dispatch, buffer preparation, parameter publication, DMA
  coordination and fallbacks, not the kernel alone (the detour machinery
  itself: 7,628 → 7,892 per eight-track frame with every track on the
  stock path). Callee time leaves the caller's row; express rows per
  block and per active instance.
- **Measure an optimisation in its calling context**, before and after
  with the same fixture, and record code-size growth beside the saving:
  an unrolled path can execute fewer instructions and cache worse.
- **Compare persistent state after every block**, not only audio: phase,
  error carry, random state and history pointers diverge before the
  audio does. Fixtures: dirty initial memory, address wrap, control
  reversals, mode changes, active feedback, long runs. Check generated
  assembly and tables against their generators first.
- **Test transitions**, both directions, nonzero state, full-scale input;
  bound the discontinuity, then run on for delayed instability. When a
  cheap mode bypasses a stateful path, the bypassed state is preserved,
  cleared or kept running by decision, and tested.
- **Prove a guard can fail**: a memory-bound or isolation test passes for
  the wrong reason until a positive control makes the forbidden write and
  the test goes red. Same for drift checks and instruction ceilings.
- **Serialized meanings.** Parts and locks store the bytes. Append enum
  values; never insert. A slot whose meaning changes is a data migration
  even when the image loads: test old bytes across their full range, not
  the old default (`AGENTS.md`, the MODE re-slot stall).
- **Hooking the stock delay routine** means keeping its protocol: the
  scratch toggle at `0x40003624`, the state iterator `0x80006180 += 68`,
  a byte-for-byte fallback for every other id, and no ring sample held
  across frames (DMA can replace history between them). A callback-level
  test cannot show any of this; run the stock routine from `0x400031a0`
  over all eight tracks with a DMA model and compare original against
  patched after every frame.
- **Three acceptance questions, answered separately**: correct audio and
  state contracts; no edit spikes or discontinuities under the meter; the
  unit responsive and on deadline while streaming, recording and running
  its other work. The first two do not establish the third; hardware
  tests include rapid panel edits and locks under full track load, with
  UI stalls recorded apart from audio glitches and freezes.

### Two byte-matching traps

- A same-unit label makes `lea` assemble PC-relative, four bytes shorter
  than the absolute form an author's encoder emits. Write `lea SYM:l,%a0`
  when matching bytes.
- GNU as shortens `move.l #imm,Dn` to `moveq` for small immediates, and
  pads a `-Ttext` that is 2 mod 4 with a leading `nop`. Both are correct
  code and both break a byte-identity oracle; midisc's `gas_port.py` emits
  the six-byte words and strips the pad.

## Settings on the card

Three kinds of state, three homes:

| state | where it lives | who formats it |
|---|---|---|
| an effect's twelve parameters | the Part (`docs/firmware/PARAM_PAGES.md`); a saved Part feeds a new layout its old bytes, and a value outside its count stalls the sequencer (`tools/hw/ot_project.py stamp-defaults`) | the descriptor |
| personal material: Kits, grooves, presets, anything a musician would copy to another project on its own | files the module owns, beside the stock project files | the module |
| the module's settings: how it behaves or looks (a checkbox, a menu option, a USB profile) | today: nowhere, or a private file (Octakit's Kits carry their own; octalab writes `octalab_grooves.map` and `octalab_generators.map`, "OTGM" v1). Proposed: one shared store per project, OTX | the shared core |

OTX is specified in nordseele's
[`docs/proposals/OTX_PROJECT_PROPOSAL.md`](../proposals/OTX_PROJECT_PROPOSAL.md)
(draft 2, 26 Sep 2026; the format and the precedence) and
[`docs/proposals/OTX_MODULE_GUIDELINES.md`](../proposals/OTX_MODULE_GUIDELINES.md)
(what an author declares; the same texts are published in nordseele/octalab `docs/`). Nothing of it is implemented on 27 Sep 2026;
the manifest API below is the proposal's illustration, not
`tools/remix/schema.py`.

What it fixes: `<set>/<project>/otx.work` (working) and `otx.strd`
(written by SAVE PROJECT, read by RELOAD) hold every module's record in
one file, `OTX1` magic, big-endian, records of typed TLVs, CRC-32 over
the file and each payload. A firmware without a module skips that
module's record on load and writes it back byte for byte on save; a
newer minor's unknown keys get the same. An optional card-root UNIT file
takes card-wide settings (USB AUDIO's profile is the first). One
generated MAIN MENU root category (working label MODULES, name open)
lists a GENERAL module and the modules in the image. Writes run from the
storage task, coalesced ~2 s after the last edit, deferred while a
recorder, CAPTURE or tape capture writes; `open("w")`, write, close, as
stock's `project.work`.

What a module declares (the proposal's syntax):

```python
store=Store(id="org.octalab.usbaudio", scope=Scope.UNIT),
settings=(
    Setting(key=1, name="USB AUDIO", group="audio", values=("OFF", "LIGHT", "FULL"),
            default=0, apply=Apply.NEXT_CONNECT),
),
```

- a stable namespaced module `id` (the build refuses a duplicate; a menu
  label may change, the id may not);
- per setting a numeric `key` never reused for another meaning, a type
  (`Binary` 0/1, `Option` an append-only index, `Number` signed 16-bit
  with min/max/step/unit, `Trigger` never saved, `Blob` with a declared
  byte maximum and its own editor), a default, a `scope` (PROJECT or
  UNIT), an apply policy (`LIVE`, `CALLBACK`, `NEXT_CONNECT`,
  `NEXT_BOOT`), optionally a group id for the menu;
- idempotent callbacks: after every load the core hands each one the
  validated value or the default, and again after an edit; no card I/O
  from an audio interrupt; never another module's record;
- a compatibility test: with the module removed from the image, editing
  another module's setting and saving leaves this module's record byte
  for byte.

What a module does not do: invent a settings file, a save hook or a menu
root of its own for these values (`MAINMENU.md` section 5: two modules that both
grow one submenu cannot coexist). Its personal-material files stay its
own.

Open on 27 Sep 2026 (the proposal's section 5): the UNIT filename and recovery
policy, size ceilings, the menu's name and row structure, whether the
stock project-copy commands carry the pair, boot ordering for UNIT
before USB enumeration, write latency under CAPTURE.

## Declaring a ROM cave: `CavePatch`

A few hundred bytes planted in one of the OS image's free zero runs, hooked
by a `jsr`. `modules/tempo-sync/` is the worked example. A cave with a
`source` is assembled and linked at its resolved address and those bytes
are written; `pinned` (or `reference(addr)` for a floating cave) is the
ratified oracle, and a mismatch refuses the build.

```python
cf_patches=(CavePatch(
    label="my cave",
    cave_addr=None,            # floats: first free 0x80-aligned address past
                               # the clones and earlier caves; pin an int only
                               # if the code is not position-independent
    pinned=MY_BYTES,
    source="modules/<name>/my_cave.s",
    hook_addr=0x400xxxxx,
    hook_stock=bytes.fromhex("..."),
),)
```

The installer asserts the hook site still holds the stock bytes, plants a
`jsr` to the cave, and the cave replays what it displaced before its own
work. The hook span is `len(hook_stock)`: the six-byte `jsr` followed by
nops to the end of the displaced instructions, so `hook_stock` must be
whole instructions, at least six bytes and even. A pc-relative instruction
in `hook_stock` can be replaced (the cave does the work itself) but not
replayed at the cave's address; `TEMPOCAVE=replay` refuses such a cave.

A cave can register itself as another module's display formatter with
`registers_formatter=FormatterReg(module=..., slot=...)`; naming the target
lets a remix that omits it skip the registration. `FormatterReg(offset=…)`
registers an entry inside the cave.

Only position-independent code may float: short branches and OS absolutes,
no absolute reference to itself. `pinned` is what is written, so the build
needs no m68k toolchain; when one is present the source is re-assembled and
compared. A cave that filters on effect ids has those ids compiled into
`pinned`; changing a module's fx2 id does not change the cave (the tempo
cave is the live example).

## The grain count: `Remix.grains`

BusDelay's GRAIN reader runs four grains per line, or two:

```python
REMIX = Remix(name="...", modules=(...), grains=2, fallback="SEND")
```

Cycles, not sound: a core cannot carry four active stations beside a
four-grain GRAIN (3,294 of 3,120 usable by the pricer); at two grains it
fits. Measured saving 1,775 → 1,305 cycles. `tools/remix/grains.py` holds
the substitution, imported by both the builder and `cycle_count.py`: three
edits at censused markers (the two rolled loops count 2; the grain-to-grain
phase offset doubles, G/4 → G/2; the makeup doubles, because four triangle
windows at quarter offsets sum to exactly 2 while two at half offsets sum
to 1). `tools/verify/verify_grains.py` is the gate: markers present, the
pricer sees the saving, every non-GRAIN case bit-identical and every GRAIN
case different under `verify_delay`. How two grains sound is not checked.

## Placed but not listed: `Remix.hidden`

```python
REMIX = Remix(name="...", modules=(..., "REVERB SERVER"),
              hidden=("REVERB SERVER",), fallback="SEND")
```

The module's code is placed, its id dispatches to it and its descriptor is
cloned; it takes no chooser row, and its twelve parameter names are written
blank, which empties the page. Counts, defaults and enable bits are
untouched, so the firmware's parameter writer still clamps and commits
every slot (measured in the emulator: the page drew nothing, a write landed
in the Part).

- A hidden module that is also on the FX1 chooser keeps its names (one
  descriptor serves both menus). `hidden` minus `fx1` is what gets blanked;
  the registry auto-hides every `fx1_only` station from the FX2 chooser.
- `Remix.named`: a hidden module that keeps its twelve names, off the
  chooser, reached only by the project stamp, its host page drawing every
  knob. A hidden module may go blank only when the screen that edits it has
  been proven on hardware. `Remix.blanked` (hidden, not on FX1, not named)
  is the one definition the build and every verifier share.
- A blanked page gets no formatters: `build_bus.py` emits neither the
  select-label caves nor a formatter-registering cave for it, and
  `verify_labels` exempts it.
- Do not hide a module whose page is the thing you want to see: hidden,
  SEND's page went blank on every non-host track.
- The fallback may be hidden: its cursor goes to 0; its descriptor is still
  cloned and its id still resolves.
- `hidden` belongs to the remix, not the module: declared on the module, it
  emptied the plain `bus` image's chooser too.
- It does not make the id private: dispatch is per id and shared by every
  track and both menus. A hidden engine gets a host guard: `build_bus.py`
  substitutes a gate at the engine's `; HOSTGUARD` marker for the remixes
  that hide it, so the engine runs on the bank's first FX2 state block (`r7
  == 0x6200`, `docs/firmware/DSP.md` "The allocator's instance model") and
  passes dry on every other. Substituted, never compiled in: the harness
  runs the reverb at `-r7 4`, the bank's second slot, so a guard in the
  shipped source would render every voicing pass dry. A comment is build
  input: the payload-gate census greps the source for its phrase, and the
  burn probe's anchors are exact comment lines.

`tools/verify/verify_hidden.py` is the gate: the clone and its id, blank
names, manifest defaults and enable bits intact, absent from the chooser
list, a cursor entry pointing at the fallback, a page that draws none of
its names (against a control render that does draw a listed module's), the
writer still landing a value, and DSP entry points that are the module's
own.

## Resource claims and the ledger

`tools/remix/ledger.py` refuses a build whose selected modules collide, and
names both: FX2 ids, cave ranges, hook sites, detour sites, pokes, runtime
writes, DSP hook sites per payload (`DspSection.hooks`), on-chip SRAM
windows (`Claims.sram`), core-private Y words, the per-core FX2 instance
buffer region, appended runtimes (one per image), arena reserves.

Core-private Y is derived by scanning your source for `y:>$09xx`. Low Y is
per core, not per instance. Declare `Claims(reserved_private_y=…)` only for
a word you mean to own but do not yet reference.

`Y:0x4000`-`0xBFFF` is declared, not derived: `Claims(owns_fx2_buffers=True)`.
That region is two FX2 instance slots per core; BusVerb's tank is
hardcoded there, so two such modules on one core overwrite each other. A scan cannot tell an address from a mask (`and #>$7fff`), and
static scanning could not locate the stock reverbs' buffers, which compute
their bases at runtime (`docs/firmware/DSP.md` section 7c).

The shared 64K window (`Y:0x30000`-`0x3FFFF`) is not checked: the servers'
buffer extents there are not established well enough to write down.
`AGENTS.md`'s ownership notes are the map: payload A's half is fully owned.

`python3 tools/remix/selftest.py` (in `make check`) proves the ledger
catches each collision it claims to.

## Before you open a PR

The gates and the rebase: [CONTRIBUTING.md "Before you open a PR"](../../CONTRIBUTING.md#before-you-open-a-pr).
Specific to a module:

- Your gates and your `dear` settings go in the manifest, in the same PR.
- Voicing is judged by ear, level-matched, A/B/A/B, wet-only
  (`docs/history/VOICING.md`). Render locally rather than flashing.
- A `layout_char` makes your module placeable by `send_probe`, which
  measures a bus accumulator and so analyses only modules whose harness
  says `is_server`; render an insert with `--direct`.
- Disassemble what you assemble: `dsp_asm` mis-encodes several instructions
  silently (`AGENTS.md`).

`dsp_host` boots both payloads (`-memB`; `tools/harness/rig_render.py` for
the whole rig), so a server on core 1 renders on core 1 with the shared
window shared. No local test is evidence that a cross-core timing defect is
absent: the two cores run lock-step or under a chosen `-skew`.

## Replacing a stock effect

For an upgraded version of a stock effect, take its own id so that FX1,
FX2 and every saved project that selected it get yours:

```python
menu=MenuEntry(
    fx2_id=0x1c,              # LO-FI's
    replaces="LO-FI",
    ...
)
```

Without `replaces`, a stock id is refused. Your code runs wherever that id
is selected. A remix that omits your replacement leaves the stock effect
byte-identical to stock, descriptor and dispatch, both payloads (the build
prints `not in this remix, LEFT STOCK: <KEY>`). `tools/verify/verify_replaces.py`
(in `make check`) proves every stock id is either stock's own or claimed
by a module that declared it. Refused: a stock id without `replaces`;
`replaces="PHASER"` on LO-FI's id; a remix with both LO-FI and your
replacement.

FX1 is taken over too: `FX1_IDS` (`0x400d5f58`) and `FX2_IDS`
(`0x400d5fdc`) are separate tables (the DSP dispatch is shared, the
descriptors are not), so both FX1 tables are repointed in place, the
id-indexed lookup and the row the encoder scrolls; the build asserts they
hold stock's descriptor first. Replacing an FX2-only effect (DELAY, the
reverbs) leaves FX1 alone.

If your replacement allocates a buffer, size it for FX1: an FX2 slot is
16,384 words, an FX1 slot 3,072 (measured, `X:0x255` in both payloads).
Nothing checks this.

Taking a stock effect's id does not give you its code space: you spend
from the ground the remix gave up. Spans off both choosers are grouped into
contiguous runs (`stock.regions_of`) and each module is packed into a run
it fits; a module must fit inside one run, and harvesting an effect that
sits between two runs joins them. `tools/remix/selftest.py`'s placer probe
builds the three-run case and requires two modules to land in different
runs.

### The FX1 chooser: `Remix.fx1`

`modules` is the FX2 chooser in its own row order; `fx1` is the FX1 chooser
in its own. Empty means unchanged: FX1 keeps stock's ten and the build
writes no byte.

```python
REMIX = Remix(name="warped-fx1", doc="…",
              modules=("SPECTRUM",), fallback="NONE",
              fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "SPECTRUM",
                   "COMPRESSOR", "LO-FI"))
```

NONE is FX1 row 0, the firmware's own, always emitted first. FX1's list
ends at `0x400d608c` and FX2's begins at `0x400d6090`, so a composed list
is rebuilt in the cave:

| table | what it gets |
|---|---|
| the chooser list | NONE, then exactly what `fx1` names; its three `lea` references (`0x40037990`, `0x40052706`, `0x40059bd2`) repointed |
| the viewport `0x40059be6` | `min(7, rows)`; a list shorter than stock's with the stock viewport renders raw memory as text past the terminator |
| `FX1_IDS` `0x400d5f58` | your descriptor clone, the same one FX2 resolves |
| `FX1_ID2POS` `0x400d60d0` | the row each listed id opens on, 0 for every id the list drops |
| `FX2_IDS` / `ID2POS` | untouched |

It costs no words and it is not free: FX1 is four more slots on the same
four tracks, so an effect on both menus can double the worst per-core load
(`make cycles` prices it).

A `replaces` module is listed on FX1 by its own key (`fx1=("SPECTRUM",
...)`), never the stock key it replaces. Also refused: a stock effect FX1
never listed, and a key with no FX2 chooser row of its own.

#### Only a buffer-free insert may take an FX1 row

`state.fx1_hazard()` is the single statement of the rule, read by the
remixer and by `build_bus.py`. Refused:

| refused | why |
|---|---|
| a stock effect FX1 does not already list | DELAY and the three reverbs do not fit a 3,072-word FX1 allocation |
| a module that reads the allocator (`x:>$213`) without saying how much it uses | it sizes its buffer for an FX2 slot (16,384 words); an FX1 slot is 3,072. Declare `Claims(stock_instance_buffer=True, buffer_words=N)` with N ≤ 3,072; add `fx1_only=True` and it may also sit beside a server |
| a module with fixed buffers in the FX2 region | an FX1 instance still writes into another track's FX2 buffer |
| a bus server | one per core by design |

The first is measured (`docs/firmware/DSP.md` "wrong claim 1", bisected on
hardware: a 16K layout at an FX1 base runs to `0x53ff`, through the other
FX1 buffers and into FX2 slot 0).

What is left is the insert class (Spectrum, Character) plus SEND. Those keep all their state in their own
`r7` block, which the dispatcher hands out per instance: FX1 instance *k*
and FX2 instance *k* get different blocks.

#### An FX1-only allocator reader: `Claims(fx1_only=True)`

An effect that needs a per-track delay line has one safe place for it
beside the servers: the FX1 slot (every FX2 slot is BusVerb's tank on core
0 or BusDelay's line on tracks 3-4). `Claims(stock_instance_buffer=True,
buffer_words=N, fx1_only=True)` (N ≤ 3,072) promises that the module reads
its base at init and, when the base is an FX2 slot (`>= 0x4000`), runs as a
dry pass and writes nothing. The ledger then admits it beside a server,
`fx1_hazard` admits it on FX1, the registry hides its FX2 row, and
`send_probe` renders it as an FX1 instance (`-r7 1 -alloc 0`). The render
gate must prove the promise: an FX2-slot render (`-alloc 1 -r7 2`) bit-exact
dry at any setting, and `dsp_host`'s guard seeing no write above `0x3fff`
on every FX1 base. FX1 bases are `0x1000 0x1c00 0x2800 0x3400`, only
1,024-aligned on two of the four, so modulo addressing over more than 1,024
words needs the linear-plus-mask idiom (`modules/modulation/`).

#### What is different about FX1

For an eligible module: the slot size and the state block.

| | FX1 | FX2 |
|---|---|---|
| buffer slot | `0x1000 0x1c00 0x2800 0x3400`, 3,072 words each | `0x4000 0x8000` + the shared-window pair, 16,384 |
| state block (`r7`) | instance *k* → `0x6000 + (1 + 2k) * 0x100` | instance *k* → `0x6000 + (2 + 2k) * 0x100` |
| in the chain | first | second: it processes what FX1 produced |
| cycles | 4 slots per core | 4 slots per core; both are paid |

Seen in the emulator: the firmware's own draw puts a module on FX1's
chooser with its own knob names; a replacement on LO-FI's id draws in
LO-FI's slot on the FX1 chooser with its own page. `verify_replaces.py`
checks both tables in both directions.
