# Shared ColdFire hooks: one owner per contested site

Design of 28 Oct 2026 (Sam Banks). Section 7 lists the phases; section 8
what would falsify the design.

**Status (28 Oct 2026).** Phases 1-4 are built, none flashed:
`schema.Override` covers symbol refs, pokes and table refs, and the matrix
adds each pair's requires; the bridges are a platform module of their own,
[HOOKS](../../modules/hooks/README.md), not EVENTS families -- the registry
appends it when a remix carries two modules one of its bridges joins, and a
module alone keeps its bytes (track_key, status_icon, frame_tail,
frame_entry, boot). Phase 4 is not here: radiohagen's MIDI Follow PR
(sambanks/octabam#824) already gives STORE the native Part access section 5
describes and retires MIDI PART STATE, and this design adopts it (a PARTS
module built here first was withdrawn, 28 Oct 2026). HOOKS's boot bridge
joins BOOT TRACE with STORE's native Part activation when a registered Part
client is selected; STORE alone adds no boot hook. Two departures from sections 4.3 and 7: the
in-tree participants were not rewritten as clients -- each keeps its
proven standalone bytes and, where its detour never returns, builds a
returning form under a HOOKS flag -- and the machine table (phase 6) has
its first pair, in HOOKS rather than PARTS (below).

**Phase 5 (28 Oct 2026).** The four sites SCALE QUANTIZER shares are the
CHROMATIC keyboard, not MIDI note-in: `0x4004fc58` with OCTA303, and
`0x40045918`, `0x40050254`, `0x40044968` with BLACKPYRAMIDS_303. HOOKS
bridges both pairs (chrom_pitch, chromatic). The MIDI note-on site
`0x4000e746` is contested only by the machines (BLACKPYRAMIDS_303, CX OSC,
SYNTH MACHINE) and goes with phase 6; SCALE QUANTIZER gave it to SYNTH
MACHINE on 30 Sep 2026, so section 2's row for it was wrong about SCALE
QUANTIZER.

**Phase 6, first pair (28 Oct 2026).** ANALOG BD and OCTA303 share an image
through HOOKS's `machine_rows` bridge, not a PARTS machine registry: the two
are in-tree, and chaining one's not-mine paths into the other's routines
(built under `HK_MACHINE_ROWS`) needed no registry. ANALOG BD keeps row 5 and
every shared hook; OCTA-303 moves to row 6; HOOKS pokes the lists to seven
rows and takes the machine list's drawer so it scrolls. ✅ under Unicorn
(`verify_hooks`) and under the port (both machines' UI gates on the one
image, the list scrolling, each row's commit), not flashed; each alone
byte-identical. One measured surprise: the list's five key handlers clamp
the cursor to 0..5 after moving -- one past stock's last row, which is why a
single added machine never met it ([TRAPS.md](../contributing/TRAPS.md#trap-machine-clamp)).

**Phase 6b, a chain of N (31 Oct 2026).** CX OSC joins, and the pair
became a chain rather than a registry: `machine_rows` lists the machines in
row order (ANALOG BD, OCTA303, CX OSC), each present one takes the next row,
and each is built with its place (`flags_inc` → `machine_inc`: `MC_ROW`,
`MC_ROWS_END`, and per hook `MC_HAS_*` / `MC_NEXT_*`, the next machine's
routine). The first present is the head and keeps every shared site; the
head's names table and tick take the others' names and page records
(`mc_names_tail`, `mc_publish`). Three hooks chain in their own order: the
renderer CX OSC → OCTA303 → ANALOG BD (CX OSC first: its page code reads its records from the words before the renderer the FLEX kind entry names, and with OCTA303 first the port's boot jumped through garbage; ANALOG BD's C renderer calls stock itself),
the page resolver and the START rewrite OCTA303 → CX OSC. Two adapters were
needed, both in CX OSC: its machine-window commit sits at `0x40079816`, six
bytes before the others' `0x4007981c`, so the chain enters after stock's
`adda` there and `po_machwin` replays the head's two displaced instructions;
and OCTA303's renderer is `o3_render` under the bridge, as CX OSC's `poly.s`
exports a `sy_render` into the same link. Three machines is the ceiling:
PB_TABLE has one spare word (`0x400d5f54`) before the FX1 table, and the
manifest refuses a fourth. ✅ under Unicorn (`verify_hooks`, the four
selections: each row type, the drawer over every top row, every machine's
name and main commit through the chain), each alone byte-identical (ANALOG
BD, OCTA303, CX OSC rebuilt, 31 Oct 2026); the port gates: see
[HOOKS](../../modules/hooks/README.md). Not flashed.
Still open: SYNTH MACHINE and BLACKPYRAMIDS_303 (the last can never
sit beside ANALOG BD: both put a DSP voice in SPRING REV's words), and the
MIDI note-on site `0x4000e746`.

Confidence markers: ✅ measured, 🟡 inferred with a falsifier stated,
⬜ not looked at.

## 1. The problem

The ledger allows one claim on a stock site (`tools/remix/ledger.py`), so two
ColdFire modules that hook the same instruction, poke the same word or repoint
the same table record are refused as a pair. 24 ColdFire modules are in no
shipped remix (`octabam`, `octabam-bus`, `cxosc-core`), and for several of
them the reason is a site that a CORE module already holds.

`make modules` under-reports these pairs: its matrix (`tools/remix/index.py`)
checks each pair alone, so a pair whose module needs MEMORY, STORE, EVENTS or
another module reports that requirement and stops. The table below is every
pair checked with each module's `requires` closure (and MEMORY) added, keeping
only the problems neither module has alone. ✅ (the ledger, 28 Oct 2026, main
at `1f01ce4`).

## 2. Every ColdFire conflict, by what is contested

| boundary | sites | in-tree modules | submodule modules |
|---|---|---|---|
| machine registration: chooser rows, SRC SETUP, Part validator, FLEX renderer entry, PLAYBACK resolver, LFO PMTR names | 23 sites, among them `0x400d6438`, `0x40002318`, `0x4000c634`, `0x40031ece`, `0x4003bff0`; cave `0x400d24d0` | OCTA303, ANALOG BD, CX OSC | SYNTH MACHINE (timhastie), BLACKPYRAMIDS_303 (Zac Kyoti) |
| CHROMATIC keyboard (first written here as "MIDI note in": corrected, see Phase 5 above) | `0x4004fc58`, `0x40044968`, `0x40045918`, `0x40050254` | OCTA303 | SCALE QUANTIZER (CORE), BLACKPYRAMIDS_303 |
| MIDI note-on | `0x4000e746` | CX OSC | BLACKPYRAMIDS_303, SYNTH MACHINE (not SCALE QUANTIZER, as first written) |
| `[TRACK]`-held key layer | table `0x400d1594`, its YES/NO records | MORPH | REC_TRIG_MUTE (CORE) |
| track status icon | the state-cache load `0x4004bee2` | REC THRESHOLD | REC_TRIG_MUTE (CORE) |
| frame interrupt tail, and order within it | `0x4000d9a6`, `0x4000aad0` | CF METER, CF METER IDLE, WAVE LOAD, LOAD METER (CORE), BOOT TRACE; LOAD METER before STEM REC (declared) | |
| boot entry | `0x40000512` | BOOT TRACE | MIDI PART STATE (radiohagen) |
| behaviour, not a site | | PERSISTENT BUFFERS / BUFFER SAVER | DIRECT JUMP / DIRECT_JUMP_KYOTI |

The last row is out of scope: each pair does one job two ways, and a remix
takes one.

DSP-side pairs found by the same pass, for the record (not addressed here):
SIDECHAIN COMPRESSOR and LOAD METER both claim the DSP hook site `P:0x0050e`
on payload A and `P:0x00303` on payload B; BLACKPYRAMIDS_303 takes SPRING
REV's program words, as do SIDECHAIN COMPRESSOR and TAPE ECHO; BBD and EUCLID
claim the same DSP priority.

## 3. What already exists

Three mechanisms in the tree already let modules share a stock site.

- **STORE** (`modules/store`): owns the card's save, load, copy, Part save and
  Part clear sites once and calls each client's `<prefix>_st_<event>` handler
  from a build-time table. A client not in the remix is left out of it.
- **EVENTS** (`modules/events`, radiohagen): owns native runtime boundaries
  (transport, accepted MIDI output, held-step editor, copy). Registration is
  build-time; `event_inc` generates direct calls with no pointer table; a
  family with no client in the remix installs no detour, so the stock bytes
  stay (`select`). The held editor uses first-owner precedence: a client's
  `_claim` returns non-zero to take the event.
- **`Override`** (`schema.Override`): a bridge module's detour stands in for
  another module's detour at a site; the build skips the overridden one. SCOPE
  overrides three of TUNER's detours and calls TUNER's own `tu_open`,
  `tu_analyse`, `tu_draw`, `tu_close`; nothing in TUNER's submodule is edited.

The gap ✅: `Override` covers Detours only (`overridden_detours` in
`ledger.py` and `_ovr_detours` in `build_bus.py` hold `(site, module)` for
detours). A SymbolRef, Poke or table ref cannot be stood in for.

## 4. The design

### 4.1 The rule

- A contested stock site has exactly one owner, a system module.
- Clients register at build time; the build generates the calls.
- A site is installed only when a client in the remix registers for it, so a
  remix with no client is byte-identical to today.
- The ledger refuses a direct claim on a site that a system owner holds, by
  name of the owner, so a new module is pointed at the registration instead
  of at a conflict.

### 4.2 The owners

1. **STORE**, unchanged: card persistence.
2. **EVENTS**, with new families:
   - `midi.note_in`: the note-in sites of section 2; first-owner precedence
     (consumed or passed on), as `edit.held`.
   - `frame.tail`: an ordered list, so LOAD METER's place before STEM REC is
     declared, not a conflict.
   - `boot`.
   - `track_key`: owns `0x400d1594`; each client contributes YES/NO handlers
     to one generated table.
   - `status_icon`: owns `0x4004bee2`; first-owner precedence per track.
3. **PARTS**, new: the live Part API and machine registration (section 5).

### 4.3 In-tree modules are rewritten as clients

| module | becomes | author |
|---|---|---|
| MORPH | EVENTS `track_key` client | MaMarko |
| REC THRESHOLD | EVENTS `status_icon` client | Chupitnik |
| ANALOG BD | PARTS machine client; first, as the reference client: OCTA303 already uses its seams | repeat98 |
| OCTA303 | PARTS machine client, EVENTS `midi.note_in` client | MaMarko |
| CX OSC | PARTS machine client | ilia-murzinov |
| CF METER, CF METER IDLE, WAVE LOAD, LOAD METER | EVENTS `frame.tail` clients | sambanks |
| BOOT TRACE | EVENTS `boot` client | sanderlegit |

Each rewrite is reviewed by its author.

### 4.4 Submodule modules are included unchanged

As for every submodule today ("Nothing inside `upstream/` is edited here",
`modules/mute-modes/manifest.py`): the wrapper adapts with
`dataclasses.replace`, the linked units keep their `reference` pins, and a
bridge in the tree takes the contested sites by `Override` and calls the
author's own routines, as SCOPE does with TUNER.

| module | contested | assessment |
|---|---|---|
| REC_TRIG_MUTE (CORE) | Detour `0x4004bee2`; SymbolRefs for the `[TRACK]` YES/NO records (`rtm_yes`, `rtm_no`) | 🟡 bridgeable: the handlers are separate labelled routines. Falsified if they cannot be called as routines. Needs `Override` on SymbolRefs (phase 1). |
| SCALE QUANTIZER (CORE) | 4 of its 19 detours | ⬜ depends on whether its note-path stubs fall through to the stock continuation |
| SYNTH MACHINE | 25 detours, the renderer entry, cave `0x400d24d0` | ⬜ the PARTS machine interface has to fit its renderer and page; the hardest |
| BLACKPYRAMIDS_303 | 44 detours, 7 pokes; SPRING REV's DSP words | ⬜ ColdFire half through PARTS; the DSP half stays a separate problem |
| MIDI PART STATE | `0x40000512`, `0x40020898`, `0x40005638` | retired into PARTS by its author |

When a hook cannot be bridged, the fallback is an upstream change in the
author's repository splitting the stub into a callable body; Zac Kyoti's and
radiohagen's repositories already carry octabam module trees.

## 5. PARTS

**Superseded (28 Oct 2026):** radiohagen's sambanks/octabam#824 puts this
service in STORE (`modules/store/parts.py`: edited, audio-playing and
MIDI-playing contexts, registered windows, busy writes refused, epochs and
build-time callbacks), and this design adopts it. The text below is the
design as first written.

Proposed by radiohagen (28 Oct 2026) as either an extension of STORE or a
dedicated module, to retire MIDI PART STATE: edited and playing Part access,
native-setting reads and writes with the dirty state and the battery-backed
mirror, consistent reads during Part replacement, and replacement
notifications so a module can reset its temporary playback state.

This design takes the dedicated module:

- STORE's job is persistence events; this is a live-RAM API. One module, one
  job.
- PARTS is a STORE client for `partsaved`, `partclear`, `preload_post` and
  `loadall_post`, and owns only the live boundaries (Part copy and
  replacement).
- Machines are Part data: each stores a FLEX track plus a signature in Part
  bytes and writes the battery mirror. ✅ ANALOG BD (`machine.s`),
  BLACKPYRAMIDS_303, KITS, MIDI SCENES, RELOAD_FROM_PROJECT and MIDI PART
  STATE each address the mirror themselves today. So PARTS also owns the
  machine table (chooser rows, renderer entry, resolver, validator) and
  arbitrates the signature bytes; the ledger already has `Claims.part_window`
  for them.

One inherited caution ✅: EVENTS does not patch the memcpy entry
`0x40020898` "because stock also calls it before the runtime is loaded"
(`modules/events/README.md`); MIDI PART STATE patches it through a cold-entry
unit in ROM. PARTS's proof must cover those pre-runtime calls.

## 6. What this changes in the build

- `Override` extends to SymbolRef, Poke and table refs. A build change:
  `scripts/refhash.sh check` must show the 24 configurations bit-identical,
  which it should, since no module uses it yet.
- The ledger learns system-owned sites (section 4.1).
- `tools/remix/index.py`'s matrix adds each pair's `requires` closure, so
  `make modules` shows the real conflicts. A report change only.

## 7. Phases

Sizes are 🟡 estimates from site and file counts.

1. `Override` on SymbolRef, Poke and table refs; the matrix closure. Small.
2. EVENTS `track_key` and `status_icon`; MORPH and REC THRESHOLD as clients;
   REC_TRIG_MUTE bridged. Small to medium. Puts MORPH and REC THRESHOLD in
   reach of CORE and proves the submodule bridge on a CORE module.
3. EVENTS `frame.tail`; the meters as clients. Small. CF METER, the cost
   instrument, can then share an image with LOAD METER.
4. PARTS phase 1: the Part API; MIDI PART STATE retired. Medium; radiohagen.
5. EVENTS `midi.note_in`; SCALE QUANTIZER bridged. Medium; the riskiest, a
   real-time path in a CORE module.
6. PARTS phase 2: the machine table. ANALOG BD, then OCTA303 and CX OSC, then
   the SYNTH MACHINE and BLACKPYRAMIDS_303 bridges. Large: 23 sites, five
   modules, three author repositories.

## 8. What would falsify it

- A submodule hook that cannot be called as a routine, whose author will not
  split it: that module stays a conflict.
- A one-machine remix that is not byte-identical through PARTS: the "installed
  only when registered" rule fails for machines, and each would keep a direct
  path beside the registry.
- A client order that matters and cannot be stated as a list (two frame-tail
  clients that each need to run first): the ordered family is not enough.
