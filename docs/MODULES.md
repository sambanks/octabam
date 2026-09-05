# Writing a module

octabam builds firmware images out of **modules**. A module is one
contribution: a DSP effect, a bus client, a ColdFire behaviour patch, or a
combination. A **remix** is a named selection of modules composed into one
image. `make modules` prints what exists; `make bus REMIX=<name>` builds a
selection.

This document is for adding one. Read `PLAN.md` for where the project stands
and `CLAUDE.md` for the traps that have already cost real work — several of
them are traps a new module can walk straight into, and they are repeated
here where they apply.

**Decide first which kind you are writing, because it decides most of what
follows.**

An **insert** processes its own track's frames in place: no bus role, no
shared-window claim, placed in both payloads, runnable on any track and
several at once. Nothing negotiates with anything. `bus_role=BusRole.NONE`,
`ybase=YBase.NEVER`, and most of the hazards below simply do not apply.
**Start here** — seven of the eleven shipping modules are inserts, and each
was built against this document alone. `modules/hello/` is the worked example
below.

A **server** owns a bus accumulator, is bank-bound to one core, and has to
take part in the rotation, the housekeeping election and the auto-gain. It
buys a whole donor region's worth of program space with that complexity.
There are two, they are documented in `docs/XBUS.md`, and you should have a
reason before writing a third.

A module can also be neither: a **bus client** (`send`) or a **ColdFire
patch** (`tempo-sync`) that changes firmware behaviour and touches no audio.

---

## Your first module: read HELLO WORLD

`modules/hello/` is a linear volume knob and the **complete worked example**:
one page-1 knob, 27 words of DSP, no state, no bus role, no shared window. It
is the smallest thing the contract can express, and every piece a real module
needs is there and no piece it does not:

```
modules/hello/manifest.py    the declaration -- one knob, one donor, one id
modules/hello/gain.asm       the engine -- init, proc, in place, 27 words
modules/hello/README.md      status, measured vs inferred, what is open
remixes/hello.py             a two-module remix: HELLO WORLD + SEND
tools/verify_hello.py        render gates with exactly predictable arithmetic
```

Build and hear it in three commands:

```bash
make check REMIX=hello
python3 tools/remix/audition.py hello out/dry/drums_110.wav GAIN=64
python3 tools/verify_hello.py            # ALL GATES PASSED, 0 LSB
```

`modules/_template/` is the *skeleton* to copy — a manifest with every field
commented and nothing else. Read `hello` for what a finished one looks like;
copy `_template` when you start typing.

**Its gates are the part worth stealing.** `verify_hello.py` drives the effect
with a full-scale bipolar ramp and asserts the output *exactly*: unity at
GAIN=127 is bit-identical, GAIN=0 is all zero, and every intermediate gain is
`(in × g) >> 23` to 0 LSB. Arithmetic you can predict to the bit is what turns
"it rendered and sounded plausible" into a measurement — and the negative half
of that ramp is what proves the `mpy` did not silently become an `mpysu`.
Nimbus's double-rate window (`CLAUDE.md`) got through *ear* review and every
existing check; a DC gate caught it. Give your module one gate whose answer
you can compute by hand.

⚠️ And make it name the effect it thinks it is measuring. An id the image does
not implement **aliases to the fallback**, and dsp_host renders a perfectly
plausible dry passthrough — `verify_hello.py` shipped with a hardcoded id,
measured SEND after the module moved, and its unity gate *passed*. It now
reads the id and the knob slot out of the manifest and refuses if they
resolve to SEND's entry points. Do the same.

---

## The shape of a module

```
modules/<name>/
    manifest.py      declares the module -- exports MODULE
    <engine>.asm     DSP56300 source, if it has any
    <patch>.s        m68k source, if it patches the ColdFire
    README.md        what it is, how it sounds, what is open
```

Nothing registers a module but the directory. `tools/remix/registry.py`
discovers every `modules/*/manifest.py` that exports a `MODULE`, so adding one
is adding a directory. Directories starting with `_` are skipped, which is
what keeps `modules/_template/` out of every build.

`tools/remix/schema.py` is the vocabulary and is worth reading in full — it is
short, and its comments carry the reasoning behind each field.

Copy `modules/_template/` to start (and read `modules/hello/` for a
finished one), and `make remix` opens the remixer
(`tools/remix/app.py`, Textual — provisioned by `make emu-setup`; the full
manual is `docs/REMIXER.md`). Its home
view is a RIG of eight tracks: assign effects, dial their manifest-named
knobs, render and hear them. Its REMIX view is the composer: collisions, the
FX2 menu your selection produces, its word cost against the donor region,
save/load, build and check.

The remixer derives a **category** and a **track range** for every module
(`tools/remix/rig.py`) rather than asking for new declarations:

- **bus effect** (`harness.is_server`) — lives in ONE payload, which the
  manifest declares (`dsp.payloads`); payload A serves tracks 5-8, payload B
  serves tracks 1-4 (the measured 10 Aug 2026 inversion). A server that does
  not declare a single payload is refused, not guessed at.
- **insert** (a `DSP_EFFECT` with a menu, no server role) — both payloads,
  any track.
- **stock** (`Kind.STOCK`, `tools/remix/stock.py`) — a stock FX2 effect
  kept in the chooser; any track, no knobs in the rig, no local render.
- **system** (SEND, ColdFire patches) — plumbing; never sits on a track.

Every effect is auditionable locally through `tools/remix/audition.py`, and
`tools/send_probe.py --set NAME=VAL` drives any knob of any module through
its own `knob_map()` — no per-effect wrapper flags to go stale. Every render
and A/B mark is journalled to `out/_audition/log.jsonl` (track, effect,
source, every knob), so a listening note like "this sounds boxy" plus the
journal tail is a full repro.

Two `Param` fields exist purely for the remixer (the build never reads
them — the refhash gate proves it): **`doc`**, one line saying what the knob
does, shown under the knob cursor; and **`labels`**, one short label per
value of a stepped select (the schema pins the length to `count`). The
selftest requires a `doc` on every named, drawn param of every menu-bearing
module — a knob without one is a knob the operator has to reverse-engineer
by ear.

---

## The two identifiers

```python
MODULE = Module(
    name="busverb",          # the directory. Must match.
    key="REVERB SERVER",      # the build identifier
    ...
)
```

`key` appears in the build report, and **the build report is API**:
`verify_delay.py`, `verify_roll.py` and `verify_burn.py` parse build stdout.
Changing a key, or rewording a report line, is a breaking change rather than
a cosmetic one.

---

## Declaring an effect

An effect has a `MenuEntry` (its row in the FX2 chooser), twelve `Param`s, and
a `DspSection`.

### The descriptor is CLONED from a stock donor

Every field you do not write stays the donor's. That inheritance is the single
most expensive thing about this mechanism, so the schema makes you state
things you might assume:

- **A formatter overrides the value count it sits beside.** BusDelay clones
  SPRING REV; until this was fixed, three of six page-2 slots drew as whatever
  SPRING REV drew — WOW drew no knob *at all* (an enumerated renderer with
  three labels asked to draw 0..127), MODE drew as a bipolar balance dial
  reading −64..−60. Counts, defaults, names and enable bits were all correct,
  which is why every check passed. Declare `formatter=` per slot.
- **A `name` of `None` inherits the donor's; `b""` blanks it.** Both are
  useful and they are not the same. Prefer writing the name explicitly even
  when the donor already has it — a label that exists only inside a stock
  descriptor is a label no tool can read, and the harness reads these.
- **A default outside its own value count is used as an INDEX.** That shipped
  once (slot 7, default 64, count 5) and stalled the sequencer on hardware
  after two steps. The schema now rejects it at construction. **A STORED
  value does the same, and the schema cannot see it**: when MODE moved to
  slot 6 (4 Sep 2026), every part saved under the old layout still held a
  0–127 knob byte in what was now a count-3 slot, and the first play stalled
  the sequencer the same way (inferred from the symptom; a refreshed project
  ran clean). **Changing a slot's count or moving a select means stamping
  every project before anyone presses play** — `tools/ot_project.py
  stamp-defaults <project> <remix>` — not re-selecting the one track under
  test, because the sequencer runs every track of the part.
- **A slot the panel does not draw is unreachable**, however completely it is
  named, defaulted and implemented — set `active=True`. The inverse trap is
  real too: a slot can draw a knob and publish nothing. See
  `docs/PARAM_PAGES.md`.
- **Both name fields are NUL-terminated, so the usable length is one less
  than the field.** `abbr` is 5 bytes = **4 characters**; `fullname` is 13
  bytes = **12** (and the build tag is appended *after* your string, so a
  tagged name has 2 fewer). Filling a field exactly leaves no terminator.
  A 5-character abbr drew correctly, behaved normally under manual knob use,
  and threw a line-F exception the moment a parameter was **LFO-modulated** —
  faulting PC `0x48454C4C`, which is `"HELL"`. It presented as "custom
  effects can't be modulated". Found on hardware 2 Sep 2026 by Bryan T while
  contributing HELLO WORLD, after the build had silently accepted it; the
  schema rejects both over-lengths now, and `build_bus.py` re-checks the
  string it actually writes. `modules/hello/README.md` separates what was
  measured there from what is still inferred about the mechanism.

### Page 2: even slots are knob fields, odd slots are companion fields

Slots 6/8/10 are delivered in bits 16–23 of `r6+$c/$d/$e` and slots 7/9/11
in bits 8–15 of the same words (`docs/PARAM_PAGES.md`). **Any slot may carry
any count.** Until 4 Sep 2026 this page said a stepped control could only
live on 7, 9 or 11; stock CHORUS TAPS sits on slot 6 and stock FILTER's DIST
knob on slot 11, so the panel never had that rule — only our schema did.

**Put a MODE on an EVEN slot.** The panel's page-2 knob editor
(`0x4003a474`) was first read as writing even slots only, so a select there
is settable from a cave or main-menu screen through the firmware's own
routine while the odd slots looked to need unmapped UI state. Both bus
engines moved MODE to slot 6 on 4 Sep 2026 for that, and slot 6 is
HARDWARE-CONFIRMED (tag 84). 🟡 A later emulator run showed the same editor
writing ALL SIX page-2 slots — see `docs/MAINMENU.md` §9c-ii / §9e — so the
odd-slot restriction is in doubt; an even slot is simply the proven choice.
Whatever slot you pick, the DSP read must take the field that slot is
delivered in (even → bits 16–23, odd → bits 8–15).

### FX2 ids

`0x00`–`0x03` are the values stock treats as bare synonyms for "no effect".
The first hardware test used them and got correct chooser names with dead
knobs and garbage audio. The schema rejects them.

**The fifteen STOCK ids are off limits too** (`schema.STOCK_FX2_IDS`), and
the reason is not tidiness: the two DSP dispatch tables are indexed by the
raw id and are **shared between FX1 and FX2**. A module on a stock id
replaces that effect's descriptor in the FX2 lookup and its code wherever
the id is selected — FX1 included — and a remix that *omits* the module
then aliases the id to SEND, which takes the stock effect away from FX1 as
well. Rungs shipped on `0x0c` (EQUALIZER) and Nimbus on `0x0d` (DJ EQ) from
29 Aug until 2 Sep 2026, so every local image in between ran Rungs where
FX1 selected EQUALIZER and the bus image aliased FX1's EQ to a send.
It never reached the unit (tag 77 predates it); the schema now refuses at
construction. Free ids: `0x06 0x07 0x09 0x0a 0x0b 0x0e 0x0f 0x17 0x1a 0x1b
0x1d 0x1e 0x1f`, of which all but `0x1d 0x1e 0x1f` are taken.

The **registry** is the arbiter, not the ledger: `registry.modules()` refuses
two modules on one id at import, whether or not any remix selects both. So a
contributed module can arrive on an id that was free when it was written and
is not when it lands — HELLO WORLD arrived on `0x17` and was moved to `0x1b`,
`0x17` having become Rungs's on 2 Sep 2026. `make modules` prints what is
claimed today.

## PER-MODE KNOB NAMES AND DEFAULTS -- `ModeView`

A multi-mode effect reuses its knobs, and a panel that prints one name for
both meanings is telling the operator the wrong thing half the time.
BusDelay's MDEP is the tape modulation depth in CLEAN and the grain scatter
in GRAIN; its MRAT is the rate and the density. Declare the difference:

```python
mode_slot=7,                       # which slot carries the MODE select
mode_views=(
    ModeView(mode=0, defaults={0: 40, 1: 60}),          # CLEAN
    ModeView(mode=1, names={6: b"SCAT", 8: b"DENS"},    # GRAIN
             defaults={0: 36, 6: 40, 8: 127}),
),
```

Both maps are SPARSE and both are optional. `names` renames a slot for that
mode -- four characters, the field's width. `defaults` is where the OTHER
knobs should land when the operator arrives at this mode.

**What each half drives:**

| | the remixer | the unit |
|---|---|---|
| `names` | the UNIT pane's rows follow the current MODE (`Module.knob_map_in`), and `send_probe --set SCAT=40` resolves the alias | ✅ `tools/mode_names.py` emits a MODE formatter that REWRITES the descriptor's name fields before printing its own word |
| `defaults` | applied the moment MODE changes | ⬜ not yet: it needs a write into the part, which nothing here does live |

**How the unit half works, and why it needs no new hook.** A descriptor
carries its twelve parameter names as 12 x 6 bytes at `E+0x4e`
(`docs/PARAM_PAGES.md`), and our clones are ordinary writable RAM. PLAN §6
already gives every stepped select a formatter cave that the panel calls as
`fmt(buf, value)` **with the value in hand**, so the rename rides in there:
no per-frame writer, no decode of which track is selected, no read of the
part. `tools/verify_modenames.py` (in `make check`) calls each MODE formatter
on the emulated ColdFire and reads the names back out of the clone.

⚠️ **Two limits, both inferred rather than measured.** The rename lands on
the draw AFTER the one that formats MODE, if the panel draws names first --
invisible when you turn the encoder, since that redraws. And the descriptor
is shared by every track running that effect, so two tracks in different
modes have one set of names between them: the one drawn last.

⚠️ **The names are not free.** Each mode's block is 8 bytes per renamed slot
plus a terminator, in a cave that had 84 bytes to spare on the shipping rig.
Rename a slot whose MEANING changes; a knob that is merely unused in a mode
keeps its name and says so in its `doc`.

## A STATION: an insert that is also a bus client

The BamSep26 stations (`modules/spectrum/` is the first) are per-track
inserts that also SEND: page-1 →DEL / →VRB knobs, the processed mono added
into both accumulators. What that takes, beyond the insert contract:

- `Harness(bus_client=True)` on a `Kind.DSP_EFFECT`, so the registry treats
  the image as having a bus (`fallback="SEND"`, never NONE), and the build
  relocates the module's `$9xx` scratch literals under XBUS exactly as
  SEND's — **without** the housekeeping gate, because
- **a station never housekeeps.** It carries SEND's split-offset block, the
  `; ROTINIT` / `; ROTLATCH` markers (substituted per payload, keyed on
  `r7_latch_slot=0x69`), the knob-gated registration and the per-sample
  writer — but not the election. An FX1 instance on track 5 runs BEFORE that
  track's FX2 instance, and position 0 housekeeps unconditionally, so an
  electing FX1 participant would flip the rotation twice in the first block
  and leave core 1's private tracking one step behind forever. The price is
  16 samples less bus latency for a station on core 0 (it adds into the
  buffer written last block, which is read next block); nothing is lost.
- The layout alphabet is exhausted (A–W, Y, Z), so stations take DIGITS as
  `layout_char`. `send_probe --feed 1 --set 1:-VRB=100` feeds the tone to
  the station's own track and drives its knob; `LETTER:NAME=VAL` drives any
  live slot. The registration gate is: a second instance with its send at
  zero must not move the server's level (the N/(N+1) trap).
- Every slot the sample loop touches sits **below `$40`**: the module's
  README records why.

## Keeping STOCK effects in the chooser

Every image replaces the FX2 chooser wholesale, and until 2 Sep 2026 that
hid all fourteen stock FX2 effects although only the ones a remix actually
**gives up** are consumed — by default PLATE, SPRING and DARK REV, whose
2,724 words every module packs into. The rest keep their code, descriptor
and dispatch entries in every image; they only lost their row. Since 3 Sep
2026 which ones are given up is derived from the choosers: an effect on
neither FX1's nor FX2's list is one this remix does not want, and that IS
the decision to take its words (`stock.harvested`).

`tools/remix/stock.py` registers them under their own keys (`"FILTER"`,
`"CHORUS"`, `"DELAY"`, …), so a remix keeps one by listing it exactly like
a module, in the position it should draw at:

```python
modules=("REVERB SERVER", "DELAY SERVER", "SEND", "FILTER", "LO-FI", "TEMPO SYNC")
```

A stock row costs **nothing** — no clone, no placement, no words, and
`make cycles` says so rather than counting it (only FILTER's cost is
measured, 192 cycles per instance, ×4 at worst like an insert). What the
build writes is its list row and its cursor position; `verify_menu` checks
that its descriptor and id entry are byte-identical to stock. A stock
effect a remix leaves *out* is left alone entirely — an old project that
selects it still runs it, it just has no row — which is what keeps FX1
whole. `remixes/restored.py` is `bus` plus the seven that can sit
beside the servers.

`remixes/restock.py` is all fourteen and nothing else: zero words placed,
all three reverbs alive — the unit's own chooser, rebuilt from our tables.

Two rules, both enforced:

- **Four stock effects allocate an instance buffer** — SPATIALIZER,
  FLANGER, CHORUS, COMB read `X:0x213` at init (measured 2 Sep 2026 by
  scanning the payload disassembly; the other seven do not). The
  allocator hands out a base **per track slot**, and those bases are the
  addresses BusVerb's tank, Nimbus's line and BusDelay's line hardcode:
  CHORUS on track 6 beside BusVerb on track 5 writes into the tank. The
  chooser is one list for all eight tracks, so an image cannot keep them
  apart; the ledger refuses the pair (`Claims.stock_instance_buffer`
  against any module with `owns_fx2_buffers` or a non-`NEVER` `ybase`).
  All four are legal in an insert-only remix.
- **More than seven rows moves the list.** The list cave at `0x400d6b00`
  holds seven rows before the first clone, so a longer list goes to the
  tail of the stock zero run (`LONG_LIST`, 32 rows) and the viewport is
  capped at the screen's seven, so it scrolls as stock's fifteen-row list
  does. Seven or fewer stays where it was, byte for byte. ⚠️ Scrolling our
  relocated list on the real panel is inferred from stock behaviour, not
  yet measured — `restored` is the first image with more than seven rows
  and is unflashed.

Stock rows appear in the remixer (a STOCK FX2 group in the composer, any
track in the rig) **with their real knobs**: `stock.py` reads each
descriptor's names, defaults, value counts and enable bitmap out of the
pristine image (`out/raw/section_3_MAIN_OS.bin`), so `knob_map()`,
`send_probe --set NAME=VAL` and the rig's knob rows all work by the panel's
own names (a duplicated label, FILTER's two Qs, gets a `2` suffix on the
later slot). A select carries the **firmware's own labels**: the words are
printed by each slot's display-formatter function, not stored, so
`tools/stock_labels.py` runs every formatter for every value on the
emulated ColdFire and checks the result in as `tools/remix/stock_labels.json`
(`make stock-labels`; the selftest re-asks the firmware whenever the venv
exists). Nothing is ever written back — a stock row is not cloned.
Each has a `layout_char` (L E J P A C Z O K I Y), so `--pick` takes it —
or, more usefully, the key or name: `--pick chorus`.

**They render locally the way an insert does**, from a dump of the STOCK
image's payload A (`out/dsp/_stock_A.mem`, made once by the audition):
the pristine dump, because a DEV build takes CHORUS as a fourth donor and
every build null-stubs the reverbs. dsp_host's `-alloc 1` gives a buffered
effect Y:0x4000, as the hardware gives track 1. Measured 2 Sep 2026 on a
438 Hz tone at 0.5 FS:

| effect | result (audio block at X:0 — see below) |
|---|---|
| FILTER | unity at defaults; BASE=20 WDTH=10 Q=100 takes the tone down 27 dB |
| EQ, DJ EQ, PHASER, SPATIALIZER, COMB, COMPRESSOR | bit-exact unity at defaults (THD −54 dB = the tone's own) |
| FLANGER | MIX=0 is a **bit-exact** dry pass (THD −143 dB); full modulation gives a flanged tone |
| CHORUS | MIX=0 is exactly dry; MIX=127 puts sidebands on the tone (THD −31 dB) |
| LO-FI | rendered only after `tools/dsp56300.patch` (the vendored emulator had `mpyri` unimplemented in both interpreter and JIT and aborted at init). DIST, SRR and AMF/AMD all act. ⚠️ At all-zero settings it passes a clean tone at **exactly 2× the input** (+6 dB), independent of the control flags; whether the unit does the same is unmeasured — falsifier: a hardware A/B at zero settings |
| DELAY | **no DSP code** — the Echo Freeze delay is ColdFire-side; the audition refuses with that reason |

**The harness lesson that closed FLANGER (2 Sep 2026).** Its first render
was a Nyquist-rate alternation (+0.94, −0.02, …) that read as hash and
earned a "not credible" verdict; the emulator's handling of its negative
immediate multiply was the suspect. Eight instruction probes with exact
predicted results (modulo copies, `lua (r0)+n0,r4`, `asr #$a`, `lsr`,
long moves, `move n7,a`) all passed, and its coefficient table was loaded.
The cause was the harness: the dispatcher's `move #$0,r0` puts the audio
block at **X:0** on hardware, and stock effects use the X memory right
after it as scratch — the flanger writes X:0x20–0xff every block —
while `dsp_host` defaulted the audio block to X:0x80, inside that
scratch. `send_probe` now passes `-audio 0` for a stock render, which also
cleaned EQ, DJ EQ, PHASER, SPATIALIZER and COMB by 5–17 dB (they had been
quietly reading their own scratch as input). Our own modules never touch
low X, which is why the default never mattered before. The selftest holds
the line with FLANGER at MIX=0 being bit-exact dry.

⚠️ These are emulator renders of stock code that was never exercised under
`dsp_host` before; the servers and inserts were written against it. A
stock effect that sounds wrong locally is evidence about the **harness or
emulator** before it is evidence about the effect — twice now.

---

## What an unimplemented id falls back to

The build rewrites the FX2 dispatch tables wholesale, so every one of the 32
ids has to point at a descriptor and a DSP entry — including **id 0, which
is what a fresh part's FX2 slot holds**. `Remix.fallback` names where they
go, and there are two answers.

**`fallback="SEND"` — for a remix with a bus.** The send client passes the
audio through and only taps it, so an id aliased to it degrades in the
useful direction: a track that selects a missing effect becomes a send, not
silence and not noise. No *stock* effect is a safe target — it would
PROCESS the unknown id on whatever knobs the part holds — and the target
must be a module of ours anyway: it needs a cloned descriptor, a cursor
position in the list, and placed code.

**`fallback="NONE"` — for a remix with no bus.** Unimplemented ids resolve
to the **firmware's own NONE**: the descriptor a stock chooser carries at
list row 0 (which our rebuilt list otherwise drops) and, on the DSP side,
the per-payload null stub the build already points silenced donor ids at.
It costs one chooser row — four bytes of cave — and **not one word**.

That matters more than it sounds. Every insert-only remix used to carry
SEND purely to satisfy the rule, at 215–250 words, for a bus client nothing
in the image reads: with no server, nothing ever consumes the accumulators
it writes. On `restock` those words landed on PLATE REV's, which is the only
reason the stock chooser was ever thirteen effects instead of fourteen.

⚠️ **`NONE` is refused beside any bus participant**, and that refusal is the
whole safety argument. Housekeeping — flipping the rotation word and
clearing the accumulators, once per block — is gated to payload A and done
by the first core-0 participant dispatched that block (`send_client.asm`'s
`bus_seen` election). With SEND on every unassigned track, core 0 always has
one. Under `NONE` an unassigned track runs *nothing*, so a project with
tracks 5–8 all unassigned would have no housekeeper, and a server on the
other core would read an accumulator that is never rotated and never
cleared. With no server and no SEND in the image there is no bus, no
rotation and nothing to clear, so the question does not arise — and that is
the only case this is allowed in. `registry.remix()` enforces it.

⚠️ And it could not be settled by measurement either way: `dsp_host` is
single-core, so **no local test can reproduce a bus timing defect**. The
refusal keeps the question off the table rather than answered by inference.

Declare `bus_client=True` in a module's `Harness` if it writes the shared
accumulators, the way `modules/send` does; `is_server=True` is the other
half. Those two are what `schema.on_the_bus()` reads.

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
  order, so changing it moves every module after it and changes the image.
  The send client is first because the fallback alias needs its entry points
  to already exist; the delay is last so the region's trailing free words
  belong to it.
- **`ybase` decides when `$30000` is rewritten** to the payload's own half of
  the shared window. The rule differs per module and the difference matters:
  the delay is substituted in every build, the reverb only once the bus has
  moved into the shared window, the send client never. ⚠️ The rewrite is a
  **blanket string replace over the whole source, comments included**. A
  module wanting a shared-window address that must *not* move to the other
  half cannot spell it `$30000`.
- **Program space is per core and effectively full.** `make bus` prints the
  live ledger. A new effect needs a lever first; `PLAN.md` lists them.

---

## Declaring a ColdFire patch

This is how a module changes what the firmware *does* — parts, kits, menus,
display formatters — rather than adding an effect. `modules/tempo-sync/` is
the worked example.

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

The pattern is always the same: assert the hook site still holds the stock
bytes, plant a `jsr` to the cave, and have the cave replay what it displaced
before doing its own work. The installer is generic — contributing a cave
needs no change to the build.

**The hook span is `len(hook_stock)`** (4 Sep 2026): the six-byte `jsr`
followed by nops to the end of the displaced instructions, so `hook_stock`
must be whole instructions, at least six bytes and even. Both tempo-sync
hooks are ten; `modules/cfprobe` is the first eight-byte one (a `jsr` and a
move-to-SR). A pc-relative instruction in `hook_stock` is fine to *replace*
— the cave does the work itself — but cannot be *replayed* at the cave's
address, so `TEMPOCAVE=replay` refuses such a cave rather than mis-jump.

**A cave can be both a hook target and a formatter**: `FormatterReg(offset=…)`
registers an entry *inside* the cave (`cfprobe` puts its formatter at
`+0x100` with an `.org`), so one address and one pc-relative state block
serve the interrupt and the panel. `offset=0` is the tempo-sync shape.

## THE GRAIN COUNT IS A REMIX LEVER -- `Remix.grains`

BusDelay's GRAIN reader runs four grains per line, or two:

```python
REMIX = Remix(name="...", modules=(...), grains=2, fallback="SEND")
```

**Cycles, not sound.** A core cannot carry four active stations beside a
four-grain GRAIN -- 3,294 of 3,120 usable by the pricer -- and at two grains
it fits. Measured saving: **1,775 -> 1,305 cycles, 470**.

`tools/remix/grains.py` holds the substitution, imported by BOTH the builder
and `cycle_count.py`. That sharing is not tidiness: the first version of the
lever was applied only in the build, so `make cycles` priced four grains for
a two-grain image and the saving was invisible in the tool that measures it.

Three edits at censused markers in the engine, and nothing else: the two
rolled loops count 2; the grain-to-grain phase offset doubles, `G/4 -> G/2`,
so two grains still tile the cycle; and the makeup doubles, because **four
triangle windows at quarter offsets sum to exactly 2 while two at half
offsets sum to exactly 1** -- the same coefficient would land 6 dB down.

`tools/verify_grains.py` is the gate: the markers are where the lever expects
them, the pricer sees the saving, and -- rendered through the real send path
by `verify_delay` -- every NON-GRAIN case is bit-identical while every GRAIN
case differs. Both halves matter: all-identical would mean the lever did
nothing, a difference in CLEAN would mean it did too much.

⚠️ **What is not checked is how two grains SOUND.** The arithmetic that would
make it exactly checkable -- two half-offset triangle windows summing to 1,
so DC in comes back flat, the identity that caught Nimbus's double-rate
window -- needs a DC feed over the delay bus that this harness does not have.

## PLACED BUT NOT LISTED -- `Remix.hidden`

A remix can carry a module with **no chooser row and no knobs on the page**:

```python
REMIX = Remix(name="...", modules=(..., "REVERB SERVER"),
              hidden=("REVERB SERVER",), fallback="SEND")
```

The module's code is placed, its id dispatches to it and its descriptor is
cloned as usual. What changes is that it takes no row, and its twelve
parameter NAMES are written blank -- which is what empties the page. The
counts, defaults and enable bits are untouched, so the firmware's own
parameter writer still clamps and commits every slot and the frame builder
still carries it to the DSP. Both halves measured in the emulator, 4 Sep
2026: the page drew nothing, and a write landed in the Part.

That is how an effect stops being a per-track choice and becomes part of the
instrument -- the bus engines are hosted by the project's stamp, and their
controls belong on a main-menu screen (`docs/MAINMENU.md` section 6).

⚠️ **A hidden module that is also on the FX1 chooser KEEPS its names.** One
descriptor serves both menus, so blanking it would empty its FX1 page too.
The rule is automatic: `hidden` minus `fx1` is what gets blanked, which is
how the stations come off the FX2 chooser and still draw when chosen on FX1.

⚠️ **A blanked page gets no formatters (5 Sep 2026).** Nothing ever calls a
select-label formatter or a formatter-registering cave for a module whose
names are blank, so `build_bus.py` emits neither for `hidden` minus `fx1`
(the two hosts' six label caves and BusDelay's TIME formatter, ~800 B on the
rig -- the room the bus screen needs). `verify_labels` exempts those
modules: the firmware printing plain numbers for their selects is correct.

⚠️ **Do not hide a module whose page IS the thing you want to see.** SEND's
page is the labelled send pair every non-host track shows; hidden, it was
blanked with the rest and every send page went empty (found on the unit,
5 Sep 2026). Visible, it is the FX2 chooser's one row and the pair draws.

⚠️ **The fallback may be hidden.** It has no row to park a cursor on, so the
cursor goes to 0; its descriptor is still cloned and its id still resolves to
it, which is the half that matters -- an unassigned track has to dispatch to
real code. Hide every module and the FX2 chooser is a bare terminator with a
zero-row viewport; the window still opens and draws (emulator, 4 Sep 2026).

⚠️ **It belongs to the REMIX, not the module**, and the bit-identity gate is
what said so: declared on the module, hiding the engines emptied the plain
`bus` image's chooser too, three rows to one. A remix hides an engine only
when it also carries the screen that edits it.

⚠️ **It does not make the id private.** Dispatch is per id and shared by
every track and both menus, so a saved part naming that id ANYWHERE runs the
code. A module that must run on one track only has to detect that itself,
the way `modules/modulation` does with its allocator slot.

**A hidden engine also gets a HOST GUARD.** Hiding takes an engine off the
panel; it does not make its id private, because dispatch is per id and shared
by every track. So `build_bus.py` substitutes a gate at each engine's
`; HOSTGUARD` marker for the remixes that hide it: the engine runs on the
bank's FIRST FX2 state block (`r7 == 0x6200` — `docs/DSP.md`, "The
allocator's instance model") and passes dry on every other, which is exactly
the condition its position-0 housekeeping election already uses, so the two
can never disagree. An old part naming the id on another track then gets a
bit-exact dry pass instead of a second instance writing the host's tank.

⚠️ **Substituted, never compiled in unconditionally**, and the local harness
is why: `render_reverb.py` runs the reverb at `-r7 4`, the bank's SECOND
slot, so a guard in the shipped source would render every voicing pass and
every `verify_roll` comparison dry.

⚠️ **Two traps bit while placing that marker**, both caught by refhash and
both of the family CLAUDE.md names. The comment first contained the phrase
the payload-gate census greps for, which reported the untouched `bus` image's
payload A as gated out; and it sat inside the burn probe's cut anchor,
which made `make burn` refuse. A comment is build input here.

`tools/verify_hidden.py` is the gate: the clone and its id, blank names,
manifest defaults and enable bits intact, absent from the chooser list, a
cursor entry pointing at the fallback, a page that draws none of its names
(against a baseline render, because the playback page's own knobs are
captured too and one of them is called RATE), a control render that DOES
draw a listed module's names, the writer still landing a value, and DSP
entry points that are the module's own rather than the fallback's.

**Caves float unless pinned** (3 Sep 2026). A remix with more than three
descriptor clones used to run the clone block straight into the tempo cave
pinned at `0x400d7000` — three clones end exactly there, so the shipping
image had fit by arithmetic coincidence. `cave_addr=None` plants the cave at
the first free address after whatever precedes it, rounded up to `0x80`,
which reproduces the shipping image byte for byte and clears six clones.
Only position-independent code may float: short branches and OS absolutes,
no absolute reference to itself (both tempo-sync caves qualify).

`pinned` is what actually gets written, so the build needs no m68k toolchain.
When one *is* present the source is re-assembled and compared, so a source
that has drifted from the bytes we ship cannot pass unnoticed. Keep both in
step deliberately.

⚠️ **A cave that filters on effect ids has those ids compiled into `pinned`.**
Changing a module's fx2 id does not change the cave, and the two then
disagree silently. The tempo cave is the live example.

A cave can register itself as another module's display formatter with
`registers_formatter=FormatterReg(module=..., slot=...)`. Naming the target is
what lets a remix that omits it skip the registration rather than writing a
pointer into a descriptor that was never cloned.

---

## Resource claims and the ledger

`tools/remix/ledger.py` refuses a build whose selected modules collide, and
names both. It checks FX2 ids, cave ranges, hook sites, core-private Y words,
and the per-core FX2 instance buffer region.

Core-private Y is **derived** by scanning your source for `y:>$09xx`, because
a scan cannot go stale. Low Y is per *core*, not per instance, so every effect
sharing a core shares those words. Only declare `Claims(reserved_private_y=…)`
for a word you mean to own but do not yet reference.

**`Y:0x4000`–`0xBFFF` is DECLARED, not derived** —
`Claims(owns_fx2_buffers=True)`. That region is two FX2 instance slots *per
core*: BusVerb's tank is hardcoded there and so is Nimbus's granular line,
so two such modules on one core overwrite each other while each works
perfectly alone. It is declared because a scan cannot tell an address from a
mask — scanning for the range flags `and #>$7fff` and any coefficient that
lands in it, and `docs/DSP.md` §7c records that static scanning could not
locate even the stock reverbs' buffers, which compute their bases at runtime.
A checker that fires on six modules out of eight teaches people to ignore it.

⚠️ **The shared 64K window (`Y:0x30000`–`0x3FFFF`) is not checked yet** — the
existing servers' buffer extents are not established well enough to write
down, and a merely plausible claim reads like a guarantee. Until it is, treat
`CLAUDE.md`'s ownership notes as the map: payload A's half is fully owned.

`python3 tools/remix/selftest.py` (part of `make check`) proves the ledger
still catches each collision it claims to.

---

## Before you open a PR

**`make check` is the floor.** It builds, counts cycles, runs the ledger
selftest and verifies the ColdFire menu edits. Never claim an effect works
because it assembled.

**If you changed the build rather than adding a module, prove it changed
nothing.** `scripts/refhash.sh save` on a tree you trust, make your change,
`scripts/refhash.sh check` — 26 build configurations must come back
bit-identical, artifacts *and* build reports. This is how every refactor in
the remix work proved itself, and it caught things reading the diff did not.

**Voicing is judged by ear**, level-matched, A/B/A/B, wet-only, logged in
`docs/VOICING.md`. Render locally rather than flashing: every hardware test
costs a manual firmware write.

**A `layout_char` makes your module placeable by `send_probe`**, whose
alphabet is derived from the manifests. But `send_probe` measures a BUS
ACCUMULATOR, so it only analyses modules whose harness says `is_server`. An
insert has no accumulator to read: render it with `--direct`, which puts the
audio through the effect's own track, or drive `dsp_host` yourself. The tool
says so if you ask for a layout it cannot measure.

**Disassemble what you assemble.** `dsp_asm` mis-encodes several instructions
silently — `tfr a,b` as `rnd b`, and any `mpy` operand order it does not know
as `mpysu`, which treats its second operand as unsigned. `CLAUDE.md` has the
full list. All of them assemble clean and do the wrong thing.

**Never attach a built image** to an issue or PR. Tooling and patches only.

---

## Two things that will surprise you

**`dsp_host` cannot boot payload B.** Local testability therefore depends on
which payload a module lands on — and that is a SERVER's problem, because
specialization is what puts a server on one core. BusDelay ships on payload
B and can only be rendered locally through the DEV hatch, which places it out
of region in payload A; a server on core 1 inherits that constraint.

An insert is in BOTH payloads, so it is always reachable in payload A and
renders with no hatch at all.

**No local test can reproduce a cross-core timing defect**, because
`dsp_host` is single-core. When local says clean and hardware says broken,
believe the hardware and go looking for what the harness cannot see. A
measurement can be structurally blind to the thing you are using it to rule
out — `CLAUDE.md` has two instances that each cost hours.

## Replacing a stock effect

A module normally takes a **free** FX2 id and appears as an extra row. If
instead you are writing an **upgraded version of a stock effect** — a better
LO-FI, say — you want the stock effect's own id, so that FX1, FX2 and every
saved project that already selected it get yours. Declare it:

```python
menu=MenuEntry(
    fx2_id=0x1c,              # LO-FI's
    replaces="LO-FI",         # ...and say so
    ...
)
```

Without `replaces`, a stock id is **refused** — that is the default and it is
the safe one.

**What you are asking for.** The DSP dispatch tables are indexed by the raw id
and shared by both menus, so your code runs wherever that id is selected. That
is the point, and it is also the whole hazard: Rungs sat on EQUALIZER's `0x0c`
and Nimbus on DJ EQ's `0x0d` from 29 Aug to 2 Sep 2026, in every local image,
and the remixes *without* them aliased those ids to SEND — which took FX1's
EQUALIZER away in the shipping image too. Every existing check passed, because
each module was individually correct.

**What the build guarantees now.** A remix that omits your replacement leaves
the stock effect **byte-identical to stock** — descriptor and dispatch, both
payloads — rather than aliasing its id to the fallback. The build says so:
`not in this remix, LEFT STOCK: <KEY>`. `tools/verify_replaces.py` (in `make
check`) proves the property for every remix: every stock id is either stock's
own or claimed by a module that declared it. The four cases it and the schema
between them refuse:

| you wrote | what happens |
|---|---|
| a stock id, no `replaces` | refused at import — the Rungs/Nimbus shape |
| `replaces="PHASER"` on LO-FI's id | refused: the declaration must name the effect whose id you carry |
| a remix with both LO-FI and your replacement | refused: `fx2 id: hijack and lofi both claim 0x1c` |
| a remix with neither | LO-FI stays stock, untouched |

**FX1 is taken over too.** `FX1_IDS` (`0x400d5f58`) and `FX2_IDS`
(`0x400d5fdc`) are separate tables — the DSP dispatch is shared, the
descriptors are not — so a replacement that only took FX2 would *run* from
FX1 under the stock effect's knob names. Both FX1 tables are therefore
repointed as well: the id-indexed lookup, and the row the encoder scrolls.

Both writes are **in place**, because a replacement's effect is already on
FX1 — there is no list to grow and no cave to relocate into. Adding a row for
a module on a *new* id does need both, and that is the other way onto FX1:
see below.

The build asserts the tables hold stock's descriptor before touching them,
and that the chooser list contains it exactly once.

### The FX1 chooser: `Remix.fx1`

`modules` is the FX2 chooser in its own row order; `fx1` is the FX1 chooser
in its own. Both hold the same kind of keys — stock effects and modules of
ours — because which menu an effect appears on is a composition choice, not
a property of the code. **Empty means unchanged**: FX1 keeps stock's own ten
and the build writes not one byte, which is what keeps every remix that
predates this byte-identical.

```python
REMIX = Remix(name="bothslots", doc="…",
              modules=("WARPFOLD",), fallback="NONE",
              # FX1's chooser, in its own row order. Six of stock's ten,
              # WarpFold among them; FLANGER, CHORUS, SPATIALIZER and COMB
              # lose their FX1 row and nothing else.
              fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "WARPFOLD",
                   "COMPRESSOR", "LO-FI"))
```

⚠️ **NONE is not listed and cannot be lost.** FX1 row 0 is the firmware's own
NONE — how the slot is turned off — and the build always emits it first.

⚠️ **A list SHORTER than stock's needs the viewport shrunk**, or the draw
loop iterates its hard-coded row count past the terminator and renders raw
memory as text (the "bunch of symbols" of hardware test 1, on FX2). FX1's
literal is at `0x40059be6`, located 3 Sep 2026: FX1's setup function is
**byte-identical to FX2's apart from the list address**, and this sits at
the identical offset (+0x14) from FX1's own list reference.

The DSP side needs nothing: the dispatch table is indexed by the raw id and
shared, so the code already ran from FX1 the moment FX1 selected the id. The
panel side needs the list **relocated** — FX1's ends at `0x400d608c` and
FX2's begins at `0x400d6090`, so it cannot grow in place — plus FX1's own
id lookup and its cursor table. The build does all four:

| table | what it gets |
|---|---|
| the chooser list | rebuilt in the cave — NONE, then exactly what `fx1` names; its three `lea` references (`0x40037990`, `0x40052706`, `0x40059bd2`) repointed |
| the viewport `0x40059be6` | `min(7, rows)`, so a list shorter than the screen has no rows left to pad |
| `FX1_IDS` `0x400d5f58` | your descriptor clone — the **same** one FX2 resolves, as stock does for the ten shared effects |
| `FX1_ID2POS` `0x400d60d0` | the row each listed id opens on, and **0 for every id the list drops** — a shorter list would otherwise seed the cursor past the end for an old project holding a dropped id. ⚠️ `tools/build_fx1.py`'s experiment never wrote this table at all |
| `FX2_IDS` / `ID2POS` | untouched by this — the FX2 row is the ordinary one |

**It costs no words** — the code is placed either way — and it is not free:
FX1 is four more slots on the same four tracks, so listing an effect on both
menus can double the worst per-core load (`make cycles` prices it; WarpFold
goes 4× → 8×, 404 → 808 of the 3,120 our code may spend).

#### Only a buffer-free INSERT may take one

`state.fx1_hazard()` is the single statement of the rule — read by both the
remixer, at the keystroke, and `build_bus.py`, at the build, because those
two drifting apart is how a UI comes to offer what the build refuses. Three
classes are refused:

| refused | why |
|---|---|
| a **stock** effect FX1 does not already list | DELAY and the three reverbs do not fit a 3,072-word FX1 allocation either — that is *why* stock keeps them off it |
| a module that reads the allocator (`x:>$213`) **without saying how much it uses** | it sizes its buffer for an **FX2** slot, 16,384 words; an **FX1** slot is **3,072**. Declare `Claims(stock_instance_buffer=True, buffer_words=N)` with N ≤ 3,072 and the row is allowed; add `fx1_only=True` and it may also sit beside a server (see below) |
| a module with **fixed** buffers in the FX2 region | an FX1 instance still writes to `Y:0x4000`+, i.e. into another track's FX2 buffer |
| a bus **server** | one per core by design; an FX1 row is a second instance on the same core |

⚠️ **The first is measured, not reasoned.** It is `docs/DSP.md`'s "wrong
claim 1", bisected on hardware: a 16K layout placed at an FX1 base "runs to
`0x53ff`, through the other FX1 buffers and into FX2 slot 0". **NIMBUS LITE
reads the allocator and is exposed** — the first draft of the schema comment
claimed nothing of ours was, having checked only the fixed-base modules.

The second is not a *new* hazard: Nimbus is already documented "one per
core" because its buffers are fixed rather than per-instance. An FX1 row
doubles the slots it can be reached from, a second instance on the **same
track** included.

What is left is exactly the INSERT class — WarpFold, Ripple, Rungs, Streamz,
BodeShift, Hello World — plus SEND, which is buffer-free (untested there,
but nothing measured argues against it). Those keep **all** their state in
their own `r7` block, which the dispatcher hands out **per instance**, not
per track: FX1 instance *k* and FX2 instance *k* get different blocks, so the
same effect on both slots of one track is two independent instances that
happen to run in series.

**A `replaces` module is listed on FX1 by its own key** (since 3 Sep 2026):
`fx1=("SPECTRUM", ...)`, never the stock key it replaces — the build
refuses `fx1=("FILTER",)` beside a module that replaces FILTER, because
that row would draw the stock name over our code. A composed list is
rebuilt from scratch in the cave, so the stock row the replacement inherited
cannot appear beside it (the old refusal, "would list it twice", was true
of the in-place stock list and false of the composed one). With `fx1=()` the
stock list stands and the replacement inherits its effect's row there, as
before. Also refused: a stock effect FX1 never listed, and a key with no FX2
chooser row of its own (nothing for FX1's list to point at).
`verify_menu.py` proves the rest, `verify_replaces.py` walks the composed
list for every declared replacement, and both assert FX1 is byte-identical
to stock in every remix that asks for nothing.

#### An FX1-ONLY allocator reader — `Claims(fx1_only=True)`

An effect that needs a per-track delay line has exactly one safe place for
it beside the servers: the **FX1** slot. Every FX2 slot is BusVerb's tank
on core 0 or BusDelay's line on tracks 3–4, which is why the ledger refuses
every other allocator reader beside them. A module declaring
`Claims(stock_instance_buffer=True, buffer_words=N, fx1_only=True)` (N ≤
3,072) promises that it reads its base at **init** and, when the base is an
FX2 slot (`>= 0x4000`), runs as a dry pass and **writes nothing** — so the
ledger admits it beside a server, `fx1_hazard` admits it on FX1, and
`send_probe` renders it as an FX1 instance (`-r7 1 -alloc 0`). The claim is
a promise the module's render gate must prove: an FX2-slot render
(`-alloc 1 -r7 2`) bit-exact dry at any setting, and `dsp_host`'s guard
seeing no write above `0x3fff` on every FX1 base. ⚠️ FX1 bases are
`0x1000 0x1c00 0x2800 0x3400` — only 1,024-aligned on two of the four — so
modulo addressing over more than 1,024 words needs the linear-plus-mask
idiom (`modules/nimbuslite/`), not an `m` register.

#### What is actually different about FX1

For an eligible module: **the slot size, the state block, and nothing else.**
The DSP dispatch is one shared table, the entry point is the same code, and
`r0`/`r6`/`r7` are set the same way — so there is no separate FX1 build, no
separate render, and locally nothing to test that the FX2 render does not
already cover. The differences that exist are all about memory and order:

| | FX1 | FX2 |
|---|---|---|
| buffer slot | `0x1000 0x1c00 0x2800 0x3400`, **3,072 words** each | `0x4000 0x8000` + the shared-window pair, **16,384** |
| state block (`r7`) | instance *k* → `0x6000 + (1 + 2k) * 0x100` | instance *k* → `0x6000 + (2 + 2k) * 0x100` |
| in the chain | first | second — it processes what FX1 produced |
| cycles | 4 slots per core | 4 slots per core; both are paid |

The last row is the one that bites, and it is why `make cycles` prices FX1's
four slots: an effect on both menus can double the worst per-core load.

⚠️ Seen in the emulator, not on hardware: the firmware's own draw puts
`WarpFold78` on row 11 of a twelve-entry FX1 chooser with its own knob names.

Confirmed without a flash: with a throwaway module on LO-FI's id, the
emulated firmware draws `HIJACK` in LO-FI's slot on the **FX1** chooser and
its own `GAIN` knob on the page. `verify_replaces.py` checks both tables in
both directions, and was itself negative-tested by restoring FX1's two
entries to stock in a built image — it catches "FX2 repointed, FX1
forgotten", which is the shape this half exists to prevent.

⚠️ **Replacing an FX2-ONLY effect leaves FX1 alone.** DELAY and the three
reverbs are not on FX1 (their `FX1_IDS` slots are NONE), so there is nothing
to repoint; the build says so rather than silently doing nothing.

⚠️ **If your replacement allocates a buffer, size it for FX1.** The
allocator keeps separate tables and they are not the same size (measured,
`X:0x255` in both payloads): an **FX2 slot is 16,384 words, an FX1 slot is
3,072**. Your code runs from *both* menus the moment it takes a stock id, so
an effect that asks for a buffer and assumes the FX2 size overruns its
allocation by 13,312 words the first time somebody selects it on FX1. Same
class as the stock reverbs being FX2-only — they do not fit an FX1
allocation either. **Nothing checks this**: a buffer size is not visible to
the schema.

**Words.** Taking a stock effect's *id* does not give you its *code space* —
you spend from the ground the remix gave up, shared with every other module.
Which ground that is depends on which effects are off BOTH choosers: their
spans are grouped into contiguous **runs** (`stock.regions_of`) and each
module is packed into a run it fits.

⚠️ **A module must fit inside ONE run.** It is a single code stream, so
3,880 words spread over three runs will not take a 3,500-word module — the
remixer names the largest opening beside the total for that reason, and
harvesting an effect that sits *between* two runs joins them. Until 3 Sep
2026 the build wrote one contiguous stream and only the largest run was
placeable at all; every other run was given up and then left empty.
`remixes/scattered.py` is the worked example.
