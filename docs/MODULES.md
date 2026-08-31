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
**Start here** — six of the ten shipping modules are inserts, and each was
built against this document alone.

A **server** owns a bus accumulator, is bank-bound to one core, and has to
take part in the rotation, the housekeeping election and the auto-gain. It
buys a whole donor region's worth of program space with that complexity.
There are two, they are documented in `docs/XBUS.md`, and you should have a
reason before writing a third.

A module can also be neither: a **bus client** (`send`) or a **ColdFire
patch** (`tempo-sync`) that changes firmware behaviour and touches no audio.

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

Copy `modules/_template/` to start, and `make remix` opens the workbench
(`tools/remix/app.py`, Textual — provisioned by `make emu-setup`; the full
manual is `docs/WORKBENCH.md`). Its home
view is a RIG of eight tracks: assign effects, dial their manifest-named
knobs, render and hear them. Its REMIX view is the composer: collisions, the
FX2 menu your selection produces, its word cost against the donor region,
save/load, build and check.

The workbench derives a **category** and a **track range** for every module
(`tools/remix/rig.py`) rather than asking for new declarations:

- **bus effect** (`harness.is_server`) — lives in ONE payload, which the
  manifest declares (`dsp.payloads`); payload A serves tracks 5-8, payload B
  serves tracks 1-4 (the measured 10 Aug 2026 inversion). A server that does
  not declare a single payload is refused, not guessed at.
- **insert** (a `DSP_EFFECT` with a menu, no server role) — both payloads,
  any track.
- **system** (SEND, ColdFire patches) — plumbing; never sits on a track.

Every effect is auditionable locally through `tools/remix/audition.py`, and
`tools/send_probe.py --set NAME=VAL` drives any knob of any module through
its own `knob_map()` — no per-effect wrapper flags to go stale. Every render
and A/B mark is journalled to `out/_audition/log.jsonl` (track, effect,
source, every knob), so a listening note like "this sounds boxy" plus the
journal tail is a full repro.

Two `Param` fields exist purely for the workbench (the build never reads
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
    name="chonverb",          # the directory. Must match.
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

- **A formatter overrides the value count it sits beside.** BongDelay clones
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
  after two steps. The schema now rejects it at construction.
- **A slot the panel does not draw is unreachable**, however completely it is
  named, defaulted and implemented — set `active=True`. The inverse trap is
  real too: a slot can draw a knob and publish nothing. See
  `docs/PARAM_PAGES.md`.

### Page 2 is three knobs and three selects

Slots 6–11 alternate knob, select, knob, select, knob, select. The selects
*are* the companion byte fields, so a stepped control can only live on slot 7,
9 or 11 — the schema enforces it. A companion field set to count 128 does not
become continuous; it stays a select and reads as a near-boolean.

### FX2 ids

`0x00`–`0x03` are the values stock treats as bare synonyms for "no effect".
The first hardware test used them and got correct chooser names with dead
knobs and garbage audio. The schema rejects them.

---

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
    cave_addr=0x400d7100,
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
core*: ChonVerb's tank is hardcoded there and so is Nimbus's granular line,
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
specialization is what puts a server on one core. BongDelay ships on payload
B and can only be rendered locally through the DEV hatch, which places it out
of region in payload A; a server on core 1 inherits that constraint.

An insert is in BOTH payloads, so it is always reachable in payload A and
renders with no hatch at all.

**No local test can reproduce a cross-core timing defect**, because
`dsp_host` is single-core. When local says clean and hardware says broken,
believe the hardware and go looking for what the harness cannot see. A
measurement can be structurally blind to the thing you are using it to rule
out — `CLAUDE.md` has two instances that each cost hours.
