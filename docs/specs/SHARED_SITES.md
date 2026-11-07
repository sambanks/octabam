# Shared stock sites: STORE, EVENTS, HOOKS and `Override`

The ledger allows one claim on a stock site (`tools/remix/ledger.py`). Two ColdFire modules that detour the same
instruction, poke the same word or repoint the same table record are refused as a pair, by name. Four mechanisms in the
tree let modules share a site. Choose by what the modules need:

| the need | use | a module declares | where |
|---|---|---|---|
| save, load, copy, CS1, Part save/clear: persistence events, and native Part access (edited / playing Part reads and writes) | **STORE** | `requires=("STORE",)`, an entry in STORE's `CLIENTS`, handlers named `<prefix>_st_<event>` | [STORE](../../modules/store/README.md) |
| transport, accepted MIDI, the held-step editor, native copy | **EVENTS** | `requires=("EVENTS",)`, an entry per family in EVENTS's `CLIENTS` | [EVENTS](../../modules/events/README.md) |
| a site that two named in-tree or submodule modules already hook, each proven alone | **HOOKS** | nothing: the registry appends HOOKS when a remix carries two participants of one bridge | [HOOKS](../../modules/hooks/README.md) |
| two modules share a site that no platform module owns | `schema.Override` in a bridge module of its own | `overrides=(Override(site, "<KEY>"),)`, `requires` both | `docs/contributing/MODULES.md`, "Claims" |

## How they differ

- **STORE and EVENTS are registries.** A client registers at build time and the platform module calls it. A client absent from the
  remix is left out, and an event with no client installs no detour, so the stock bytes stay. Clients must not also claim a site the owner holds.
  EVENTS's held editor takes the first owner whose `_claim` returns non-zero; its other families notify every client. STORE runs the handlers of one
  event in `CLIENTS` order and lets each clobber every register.
- **HOOKS is a bridge between fixed participants.** Nobody selects it. With one participant, or none, a remix gets nothing from HOOKS and the module's own bytes stand,
  so a module proven alone on a unit stays what was proven. With two, HOOKS owns the site, calls each participant's own routine in a stated order, and
  the participants build a returning form under a flag (`HK_*`). A submodule participant's source is not edited. The bridges and their sites are listed in the module's README.
- **`Override`** says a bridge's claim at a site stands in for another module's; the ledger and `build_bus.py` skip the overridden claim. It covers Detours, SymbolRefs,
  Pokes and table refs. `schema.DspOverride` is the DSP form, per payload (SC LOAD METER BRIDGE; [DEMAND_LOADER.md](../contributing/DEMAND_LOADER.md)).
  An `Override` is refused when the overridden module is not in the remix, so a bridge is a module of its own with `requires` on both.

## Machines

The track's machine list, SRC SETUP, the Part validator, the FLEX renderer entry, the playback resolver and the LFO PMTR names are 23 sites shared by every
machine module. HOOKS's `machine_rows` bridge chains them in row order (ANALOG BD, OCTA303, CX OSC). The first present is the head and keeps every shared site; the chain ceiling
is three (PB_TABLE has one spare word, `0x400d5f54`) and the manifest refuses a fourth. The list's key handlers clamp the cursor to 5
([TRAPS.md](../contributing/TRAPS.md#trap-machine-clamp)). No machine registry exists: the in-tree machines needed none.

## Open

- SYNTH MACHINE and BLACKPYRAMIDS_303 are not in the chain. BLACKPYRAMIDS_303 cannot sit beside ANALOG BD: both put a DSP voice in SPRING REV's program words.
- The MIDI note-on site `0x4000e746` is contested by BLACKPYRAMIDS_303, CX OSC and SYNTH MACHINE.
- DSP-side pairs the ledger reports: BLACKPYRAMIDS_303, SIDECHAIN_COMPRESSOR and TAPE ECHO all take SPRING REV's program words; BBD and EUCLID claim the same DSP priority.
- `make modules` checks each pair alone, so a pair whose module needs MEMORY, STORE, EVENTS or another module reports that requirement and stops; the real conflicts
  of a pair appear only with the `requires` closure added.
- Nothing from HOOKS has been flashed.

## History

`git show 76fd8466:docs/proposals/SHARED_HOOKS.md` is the design of 28 Oct 2026: the conflict table by boundary, the rule that a contested site has one system owner, and the
phases. It proposed EVENTS families for `track_key`, `status_icon`, `frame.tail`, `boot` and `midi.note_in`, and a PARTS module for the Part API and the machine table. As built (28-31 Oct 2026) those bridges are HOOKS's and in-tree
participants keep their standalone bytes. PARTS was not built: the Part service is STORE's native Part access (radiohagen, sambanks/octabam#824), which retired MIDI PART STATE.
