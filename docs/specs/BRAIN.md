# BRAIN: declarations, layers and the brain file

The contract for modules that declare settings and for tools that read or write the brain's files: what a module declares
(`Store`, `Setting`, `Pin`, `Param.key`), how a value is resolved through four layers (manifest, remix, card, project),
the run-time value table, the files on the card and in the project, the brain file's byte format, and compatibility.
Design of 6 Oct 2026 (Sam Banks), restored from `git show 76fd8466:docs/proposals/BRAIN.md`, which also has the sections
left out here: 9 menu, 10 tooling, 11 gates, 12 phases, 13 to find out, 14 relation to nordseele's OTX proposal, 15 retracted.
Section numbers are those of the original; code comments cite them as "BRAIN.md section N".

The implementation is `tools/remix/schema.py` (declarations), `tools/remix/brain.py` (resolution, refusals, lock file),
`tools/remix/brainfile.py` (the file format; the reference implementation), `tools/hw/ot_brain.py` and `modules/brain`
(the run-time side on the unit; [BRAIN module](../../modules/brain/README.md)). Phases 0-4 are built and measured under the port;
the module README records what has run on a unit. A statement here about what is "not built" was true on 6 Oct 2026; the module README and the
code are current.

Confidence markers: ✅ measured, 🟡 inferred with a falsifier stated, ❌ retracted.

## 1. What it holds

| word | meaning | example |
|---|---|---|
| **setting** | a value that configures a module | USB's output layout; KITS's AUTOSAVE |
| **default** | the value something takes when nothing is stored for it | BusDelay's twelve knob bytes on a newly selected effect |
| **template** | a named set of values for one target, applied by copy | a MIDI track set up for one external instrument |
| **target** | a thing that has values: its owner declares the fields, where each lives, and a capture and an apply routine | an FX page; a MIDI track; a module's settings |

A default is the template the system applies at a target's birth events.
A setting is a target with one live instance whose value is persisted.

Outside the system: the values a Part stores (the Part keeps them) and
creative material in files a module owns (KITS's `kits.work`, Octalab's
grooves).

## 2. Layers

Every value has an address `(store id, key)` and resolves through four
layers. The later layer wins.

| # | layer | written by | when |
|---|---|---|---|
| 1 | manifest | the module's author | build |
| 2 | remix | `remix.py`: a new default, or a `Pin` | build |
| 3 | card | the user, on the unit or with the host tool | run time, shared by every project on the card |
| 4 | project | the user | run time, stored with the project |

- A setting declares `Scope.CARD` (resolves 1, 2, 3) or `Scope.PROJECT`
  (resolves 1, 2, 4).
- A default resolves 1, 2, 3. A project that wants other starting values
  applies a template.
- A pinned value has no menu row and no stored value. A stored value for
  it on the card is preserved and not applied.
- A changed default takes effect at the next birth event. Existing Parts
  keep their bytes.
- With the card absent or unreadable the unit runs on layers 1 and 2.

## 3. Targets

| target | owner | fields | home of the values | birth events |
|---|---|---|---|---|
| FX page of an effect, per mode | the effect's module; the stock provider for a stock effect | 12 slot bytes, by `Param.key` | the Part | effect select, MODE turn, new part |
| MIDI track | stock provider | channel, bank, program, CTRL 1/2 CC numbers and values; knob names | the Part; names in the project store, per Part and MIDI track | new part |
| audio track pages | stock provider | SRC/PLAYBACK, AMP, LFO pages and their setup pages | the Part | new part |
| Part | stock provider (RIG HOSTS sets layer 2) | FX1 and FX2 id per track | the Part | new part |
| project-level stock settings | stock provider | entries of the stock PROJECT menu | the project | new project |
| incoming CC map | CC MAP | blocks of CC number to page and slot | project store | project load |
| controller preset | host tool, from the manifests | the layout sent to a controller | a template file | none |
| module settings | each module | its `Setting` declarations | card or project store | boot, project load |

A field's value lives in stock storage (the Part: the MIDI track channel is
at `Part + 0x8f262 + t*0x24`, `docs/firmware/MIDI.md` appendix A,
section 1) or, where stock has no place for it, in the store.

An instrument template holds the MIDI track setup, the knob names, the
incoming CC map and the controller preset for one external instrument.

Knob names: 8 MIDI tracks x 10 assignable CCs x 6 bytes = 480 bytes per
Part (🟡 the 10 CCs are read from the panel's CTRL 1 and CTRL 2 pages; no
record in `docs/firmware/` yet). 64 Parts are 30,720 bytes; with KITS the
block is indexed by Kit, 256 Kits are 122,880 bytes, and KITS raises an
event to the brain at Kit load and save.

## 4. Declarations

### 4.1 A module

```python
store=Store(id="octabam.usb"),
settings=(
    Setting(7, "TRACKS", Option("OFF", "PRE", "POST"), default="PRE", apply=Apply.NEXT_BOOT, early=True),
    Setting(8, "MAIN", Binary(), default=1, apply=Apply.NEXT_BOOT, early=True),
    Setting(9, "CUE", Binary(), default=1, apply=Apply.NEXT_BOOT, early=True),
    Setting(10, "MASTER", Binary(), default=0, apply=Apply.NEXT_BOOT, early=True),
    Setting(11, "IN", Option("OFF", "AB", "CD", "ABCD"), default="OFF", apply=Apply.NEXT_BOOT, early=True),
    Setting(12, "MIDI", Binary(), default=1, apply=Apply.NEXT_BOOT, early=True),
),
```

- `Store.id`: ASCII, 1 to 63 bytes, `octabam.<module directory>` for a
  module in this repository, the author's own namespace otherwise;
  `stock.<page>` is the stock provider's. `Store.major` and `Store.minor`
  default to 1 and 0.
- `Setting.key`: 1 to 65535, never reused for another meaning.
- `Setting.kind`:

  | kind | value | stored as |
  |---|---|---|
  | `Binary()` | 0 or 1 | 1 byte |
  | `Option(*labels)` | an index; labels are append-only | 1 byte |
  | `Number(min, max, step=1, unit="")` | signed 16-bit | 2 bytes |
  | `Trigger()` | an action | never stored |
  | `Blob(max_bytes)` | bytes the module packs and unpacks | up to `max_bytes` |

- `Setting.scope`: `Scope.CARD` or `Scope.PROJECT`.
- `Setting.apply`: `LIVE` (the module reads the value table), `CALLBACK`
  (its routine is called after a load and after an edit; it is safe to
  receive the same value twice), `NEXT_BOOT`, `BUILD` (the value selects
  code and exists only at build; it takes layers 1 and 2).
- `Setting.early`: a `Scope.CARD` setting of fixed size that is also kept
  in the CS1 block (section 6.4) and read from there at boot.
- `Module.requires_brain`: the module's function is stored state. The
  build refuses it in a remix without the brain, by name.
- `Param.key`: 1 to 65535, unique in the module, never reused. Stored
  defaults and templates are keyed by it, so a renamed or moved knob keeps
  its value and a removed knob's value is skipped. A module that keys one
  drawn slot keys every drawn slot. Stock pages take key = slot + 1 from
  `tools/remix/stock.py`.

### 4.2 A remix

```python
REMIX = Remix(...,
    modules=(..., "BRAIN"),
    settings={("octabam.usb", "TRACKS"): Pin("PRE"),
              ("octabam.usb", "IN"): "CD"},
    defaults={("DELAY SERVER", "GRAIN", "PTCH"): 96},
)
```

- `settings`: `(store id, setting name)` to `Pin(value)` or a plain value
  (a new default). An Option takes a label or an index.
- `defaults`: `(module key, mode label or None, knob name)` to a byte;
  it replaces `Param.default` or the `ModeView` entry in this image.
- Image templates (`templates=`, JSON files in `templates/`) were built 11 Oct 2026
  and removed 12 Oct 2026: templates are the user's, on the card.

### 4.3 What the build refuses

- two modules with one store id; two settings with one key or one name in
  a store; a key of 0;
- a default outside its bounds or its label count; a `Pin` or a remix
  value outside them;
- `early=True` on a `PROJECT` setting, a `Blob` or a `Trigger`; early
  settings larger than the free CS1 run of the remix;
- `Apply.BUILD` on a `Blob` or a `Trigger`;
- a `settings`, `defaults` or `templates` entry that names nothing in the
  remix; `templates` or a `requires_brain` module without the brain;
- two `Param.key`s equal in a module; a module with some drawn slots
  keyed and some not;
- a manifest that breaks its lock file (4.4).

### 4.4 The lock file

A module with a store or with `Param.key`s commits
`modules/<dir>/brain.lock`, generated JSON: the store id and major, and
per key the type, the labels or bounds, and for a `Param` its count. The
build compares the manifest with it and refuses a removed key that is not
listed as retired, a changed type, a reordered, removed or renamed label,
and a reused retired key. Adding a key or appending a label regenerates
the file (`python3 tools/remix/brain.py lock <module>`).

## 5. The brain

The brain is a module (`BRAIN`), a DRAM unit written in C. A remix lists it
explicitly.

- **Without the brain** every value resolves at build through layers 1 and
  2. A module reads a setting through a macro that assembles a constant,
  so its source is the same either way. `Apply.BUILD` values, `Pin`s and
  remix `defaults` need no core.
- **With the brain**: the registry table (generated: per `(store id, key)`
  the type, bounds, the default after layers 1 and 2, scope, apply policy,
  callback symbol, value-table offset), the value table in RAM with a
  generated include naming each offset, the store I/O, the events and the
  menu.

Reading a setting from ColdFire source:

| the value is | the macro assembles |
|---|---|
| live | one absolute read from the value table |
| pinned, or the brain is absent | a constant |
| `Apply.BUILD` | an assembler symbol (`layout_inc(n)` passed `USB_LAYOUT` until the USB merge, 15 Oct 2026) |

Events: `card_loaded`, `project_loaded`, `project_saving`,
`project_closing`, `setting_changed`, and the birth events
`effect_selected`, `mode_turned`, `part_born`. Callbacks run in store id
order; the build report prints the order.

### 5.1 FX-page defaults

Layers 1 and 2 are the descriptor bytes the build writes today
(`Param.default`: page 1 at `desc+0x5e`, page 2 at `desc+0x64`, read by
`FUN_400526e4`, ✅ `docs/firmware/PARAM_PAGES.md` 5g) and MODE DEFAULTS'
table. For layer 3 the brain writes the card's values over those bytes in
RAM after the card store loads; the OS image runs from cached SDRAM at
`0x40000000` (✅ `docs/contributing/PLACEMENT.md`). The consuming sites
are unchanged: the stock effect select, the new-part initialiser
`0x40005638` with RIG HOSTS' detours, and MODE DEFAULTS at `0x4003aaea` /
`0x4003acf2`, whose table moves into the brain's data when the brain is in
the image.

Measured under the port (6 Oct 2026, bottleservice,
`tools/verify/verify_desc_defaults.py`): the FX2 chooser's select (T2 SEND
-> stock DELAY) and the FX1 chooser's select (T2 SPECTRUM -> CHARACTER)
land the descriptor's twelve defaults in the live lane, and with those
twelve bytes poked in RAM after the load they land the poked bytes ✅. The
new-part initialiser `0x40005638` reads the same bytes at execution time
(✅ `lea P,%a1 / lea %a1@(5e,%d2:l)`, RIG HOSTS' sites); the read watch on
stock DELAY's defaults shows it at `0x4000583c`/`0x4000584a` during the
project load and no other reader in that window (the watch logs the first
64 reads). 57 stock instructions read at `+0x5e`/`+0x64` through a
register (`0x40005736..0x400058d2`, `0x4005aff8`, `0x4005b174`,
`0x4005d180..0x4005db88`, `0x4008c912`); which gestures reach the last
three groups is not traced. Falsifier for the design: one of them reading
a copy taken before the brain's write.

A card value is checked against the slot's count before it is written: a
default outside its count is used as an index (`../contributing/TRAPS.md`).

### 5.2 Capture and apply

Capture reads a target's fields from their homes. Apply writes
Part-homed fields through the stock writers (`0x40054cd8(track, flat,
value)` for page 1, the page-2 editors' stores for page 2;
`docs/firmware/MAINMENU.md` section 7), so the shadow, the live lane and
the DSP record follow. SAVE AS DEFAULT is a capture into the card store;
SAVE TEMPLATE is the same capture into a template file.

### 5.3 DSP modules

A pinned or `Apply.BUILD` setting reaches DSP source as an assembler
constant. A run-time setting needs a ColdFire-to-DSP route, which is not
chosen: the per-track voice record is the only carrier in use and every
halfword of it is read (`docs/firmware/MIDI.md`, "The DSP record"); the
shared window `Y:0x30000+` is visible to both cores, so one delivery point
serves both payloads. Candidates: a record kind of our own through the
poster `0x400053d8`, or spare bits of a record halfword. Either is
measured under the port and probed on hardware before a module uses it
(`../contributing/TRAPS.md`, "An instruction form the chip has never run").

## 6. Files on the card

### 6.1 Places

| file | holds | written |
|---|---|---|
| `BRAIN/card.work`, `BRAIN/card.strd` at the card root | `Scope.CARD` settings; card-layer defaults | `.work` after an edit or SAVE AS DEFAULT; `.strd` copied at SAVE PROJECT |
| `<set>/<project>/brain.work`, `brain.strd` | `Scope.PROJECT` settings; store-homed fields; the project record (section 8) | `.work` after an edit; `.strd` copied by the project store, copied back by the project reload |
| `BRAIN/templates/<store id>/<NAME>.brain` | one template | SAVE TEMPLATE on the unit, or the host tool |
| the brain's read-only data | the templates the remix selected | build |

A template's name is 1 to 8 characters, the record's name field and the
list row.

### 6.2 The pairs

The rules are KITS's (`modules/kits/README.md`, "Files"; ✅ on the unit,
image A6): a header with magic, version, length and a CRC-32 of the rest;
`.work` rewritten when something changed; `.strd` copied where stock
copies `.work` to `.strd` (`0x4008ee74`) and back (`0x4008f180`); a
`.work` that fails its CRC is never overwritten.

What the brain does at a load depends on which files are on the card (the
table of OTX_PROJECT_PROPOSAL.md section 3.3):

| `.work` | `.strd` | meaning | action |
|---|---|---|---|
| absent | absent | fresh | layers 1 to 3; normal first write |
| valid | absent | edited, never saved | use `.work` |
| valid | valid | normal | use `.work` |
| valid | invalid | saved copy damaged | use `.work`, report; SAVE PROJECT rewrites `.strd` |
| absent | valid | interrupted rewrite | load `.strd`, report |
| invalid | valid | working copy damaged | load `.strd`, report |
| invalid | absent | damaged | report; no write until the user confirms a replace |
| absent or invalid | invalid | damaged | report; no write until the user confirms a replace |

### 6.3 The write path

A job on the stock engine job queue; the UI task does no file access for
the store. `open("w")`, write, close through the stock buffered calls; edits coalesced about 2 s
after the last one; deferred while a recorder is writing. ✅ on
nordseele's MKI for Octalab's own files (OTX_PROJECT_PROPOSAL.md section
2.2); not measured under an octabam image.

Each record and each `Blob` has a declared byte maximum and the build
checks the sum against a file ceiling. The ceiling is set in phase 2 from
the measured write latency.

### 6.4 The CS1 block

`early` settings are copied into CS1 and read from there before the card
mounts. The scope stays `CARD`: the card store is the home and CS1 a copy,
rewritten when the card store loads and after an edit.

| CS1 range | holder | bytes |
|---|---|---|
| `0x100f859c..0x100fff00` | stock references nothing here (`docs/firmware/STEP_LOCKS.md` section 6) | 31,076 |
| `0x100f85a0..0x100f85e8` | KITS | 72 |
| `0x100f8600..0x100ffe00` | PLOCKS P2 | 30,720 |
| `0x100ffe00..0x100fff00` | KITS | 256 |
| `0x100f859c..0x100f85a0`, `0x100f85e8..0x100f8600` | free in bottleservice | 4 + 24 |

The block is a 4-byte header (magic, version, 16-bit sum) and the early
values at build-assigned offsets: 20 value bytes at `0x100f85e8` in a
remix that carries KITS and PLOCKS P2. The build sizes it from the
declarations, claims the range in the ledger and refuses on overflow.

🟡 CS1 keeps its contents with the power off. Inferred from stock's use
of it (`STEP_LOCKS.md` section 6); both module READMEs record it as not
measured on the unit.

## 7. The brain file

One container for the card store, the project store and a template file.
Big-endian. CRC-32 is the IEEE 802.3 polynomial (zlib's `crc32`).
`align4(n)` rounds up to a multiple of 4; padding bytes are zero.

### 7.1 File header, 32 bytes

```text
  0   char[4]  "BRAIN"
  4   u16      header size = 32
  6   u8       container major = 1
  7   u8       container minor = 0
  8   u8       file kind: 0 card .work, 1 card .strd, 2 project .work,
               3 project .strd, 4 template
  9   u8       reserved = 0
  10  u16      record count
  12  u32      total file bytes
  16  u32      CRC-32 of bytes 20 .. total-1
  20  char[8]  build tag of the writing image, zero-padded
  28  u32      reserved = 0
```

A file is invalid when its magic or header size is wrong, its total differs
from the file's length, its CRC fails, or the records do not end exactly at
the total. A file with a newer container major is unreadable to this
reader: the unit runs on the layers below it and does not write the file.
A newer minor is read.

### 7.2 Record

```text
  0   u8       record kind (7.3)
  1   u8       store id length, 1..63
  2   u16      schema major
  4   u16      schema minor
  6   u16      flags = 0
  8   u32      payload length
  12  u32      CRC-32 of the payload bytes
  16  u32      record size = 20 + align4(id length) + align4(payload length)
  20  byte[]   store id (ASCII), zero-padded to 4
      byte[]   payload, zero-padded to 4
```

A reader advances by the record size. A record whose size disagrees with
its two lengths, or runs past the total, makes the file invalid.

### 7.3 Record kinds and payload prefixes

| kind | holds | prefix before the values |
|---|---|---|
| 1 settings | a store's settings | none |
| 2 default | a card-layer default for one target and mode | `u16 target`, `u16 mode` (`0xffff` none), `u32 layout hash` |
| 3 template | one template | `u16 target`, `u16 mode` (`0xffff` none), `u32 layout hash`, `char[8] name` (zero-padded) |
| 4 project record | FX id to store id and layout, as saved | none; entries of 7.5 in place of values |
| 5 field block | store-homed fields of one target instance | `u16 target`, `u16 instance` |

Target 0 of a store is its effect's FX page. A store's other targets take
keys from 1, declared by the owner. A template of an FX page carries the
MODE knob among its values and has mode `0xffff`.

### 7.4 Value

```text
  0   u16      key
  2   u8       type
  3   u8       length n of the data; 255 = a u32 length follows (Blob only)
  4   byte[n]  data, zero-padded to 4
```

| type | data |
|---|---|
| 1 Binary | 1 byte, 0 or 1 |
| 2 Option | 1 byte, the index |
| 3 Number | 2 bytes, signed |
| 4 Blob | n bytes |
| 5 Byte | 1 byte: a Part byte, 0..127 |
| 6 Name | 6 bytes: up to 5 characters, zero-padded, byte 5 zero |

### 7.5 Project record entry

```text
  0   u8       FX id
  1   u8       store id length, 1..63
  2   u16      reserved = 0
  4   u32      layout hash
  8   byte[]   store id, zero-padded to 4
```

### 7.6 Layout hash

CRC-32 over 49 bytes: for slots 0 to 11 in order `u16 key, u16 count`
(both 0 for a slot that is not drawn), then `u8` MODE slot (`0xff` when
the effect has none).

### 7.7 Reader and writer rules

1. A record whose store id the image does not carry, whose schema major
   the image does not support, whose kind is unknown, or whose payload CRC
   fails is not applied. Its bytes are written back unchanged on every
   save.
2. In an applied record, a value with an unknown key or an unknown type is
   kept byte for byte when other values are edited.
3. A known key whose stored type differs from the declared one takes the
   layer below; the stored bytes are kept.
4. A stored value outside its bounds, label count or slot count takes the
   layer below; a Part byte outside its count is stock's validator's (section 8).
5. Two records with the same kind, store id and prefix: neither is
   applied, both are kept.
6. A newer schema minor is applied: known keys are read, the rest kept.
7. New records and values write zero in flags and reserved fields. A
   reader ignores them and keeps them.
8. A save assembles the whole file, checks it against the declared
   maxima, and fails visibly before the open when a kept record no longer
   fits.

## 8. Compatibility

- A card moved to an image without a module keeps that module's records
  (7.7 rule 1). A card in a stock OS keeps the files as written; stock
  ignores the `BRAIN` directory.
- A template or default for a target the image does not carry is hidden
  and its file untouched.
- **The project record.** FX ids are assigned per remix and a Part stores
  the id; a slot's count, position or meaning can change between images
  (`../contributing/TRAPS.md`, "A part saved under an older slot layout"). At
  `project_saving` the brain writes, per FX id in the image, the store id
  and layout hash. At `project_loaded` it compares them with the running
  image, and reports an id that now names another store or a changed
  layout. It does not rewrite Parts to a new layout, and needs no clamp:
  stock's Part validator `0x40002318` rewrites every FX page byte outside
  its descriptor's `[min, min + count - 1]` to the nearer end during the
  load, in all 16 banks x 8 Parts (measured under the port, 6 Oct 2026,
  `tools/verify/verify_brain.py`; reached from the new-part initialiser's
  tail `0x40005a44`, from `0x4002579e` and from the load at `0x4008cea0`).
