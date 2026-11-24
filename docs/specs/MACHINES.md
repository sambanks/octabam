# MACHINES: one machine list for every added machine

The contract for modules that add a machine to a track's machine list. A
client declares `requires=("MACHINES",)`, an entry in MACHINES's `CLIENTS`,
and the routines that make it different from its base machine. MACHINES
holds every stock site of the machine list, SRC SETUP and the Part validator
once, for any number of clients. Which of STORE, EVENTS, HOOKS and MACHINES
fits a site: [SHARED_SITES.md](SHARED_SITES.md).

## Why

An added machine is a FLEX track signed in the Part. Showing it on the list
takes the same detours and pokes in every machine:

| site | what it does | MACHINES's stub |
|---|---|---|
| `0x400334d8` | a row's name on the list | `mc_machine_name` |
| `0x4003c928` | SRC SETUP's name table | `mc_src_names` |
| `0x4003d718`, `0x4004c36a` | the name shown for a stored machine | `mc_name_a`, `mc_name_b` |
| `0x4003c980` | SRC SETUP's highlighted row | `mc_setup_row` |
| `0x40078678`, `0x400786c8` | the list's drawer and row box, which scroll | `mc_chooser_name`, `mc_chooser_box` |
| `0x400585dc`, `0x40078886` | SRC SETUP and the list opening on the track's row | `mc_setup_open`, `mc_chooser_open` |
| `0x4003a52e`, `0x4003cd98` | SETUP's editor and drawer: a client's row edits its base's bytes | `mc_setup_edit6`, `mc_setup_draw6` |
| `0x4007981c`, `0x4005a616`, `0x4005a850` | the commits that sign or unsign the track | `mc_main_commit`, `mc_src_commit`, `mc_src_commit2` |
| `0x4003d1c0` | SRC SETUP's keys: RIGHT on a client's row opens its base's slot list | `mc_setup_key` |
| `0x40002318` | the Part validator | `mc_validate_entry` |
| `0x4005221e` | the UI tick | `mc_tick` |
| `0x40031e74` | the PLAYBACK page resolver | `mc_resolve_pb` |
| `0x4003bff0` | LFO SETUP's destination names | `mc_lfo_pb` |
| `0x40079248`, `0x400585fa`, `0x4003c950`, `0x40079904` and the five cursor clamps | the lists' row counts and bounds | pokes for 5 + N rows |

Before MACHINES, each machine carried its own copy of this code, written
for row 5. Two machines in one remix needed a chain through HOOKS
(`machine_rows`), where each machine forwards every row that is not its own
to the next. A machine outside the chain conflicted with every machine in
it.

## Clients

`CLIENTS` in `modules/machines/manifest.py` lists, per module key:

| field | meaning |
|---|---|
| prefix | the symbol prefix: the client's symbols are `<prefix>_mc_<name>` |
| signature | two ASCII bytes and a version byte, written at Part + `0x3c` + 30 × track (NEIGHBOR's PLAYBACK column, unused by FLEX) |
| name | the name on the list and in SRC SETUP |
| base | the stock machine the track stays underneath: `FLEX` |
| slot | the client plays its base's sample slot: RIGHT on its row in SRC SETUP opens the base's slot list |
| hooks | the hooks the client implements (below) |

A client exports:

- `<prefix>_mc_defaults`: the 12 knob bytes a track gets when it is first
  signed, page 1 then page 2.
- `<prefix>_mc_page`, and the other hooks it names.

MACHINES exports to each client `<prefix>_mc_row`, a word holding its row.
A client that needs its row reads that word, never a constant. Rows are
given in `CLIENTS` order, from 5, to the clients present in the remix.
With no client present, MACHINES pokes nothing and stock's five rows stand.

`manifest.py` refuses an entry the tables cannot serve: a signature or a
prefix another client has, a signature that is not two printable ASCII bytes
and a version byte, a name over nine characters or holding a quote or a
backslash, a base other than FLEX, or hooks without `page`.

## What MACHINES does

- **Signing.** Choosing a client's row stores the base machine and writes
  the client's signature, in the working Part and its battery copy. A
  first signing writes the client's defaults; choosing the same client again
  keeps the knobs. Choosing any other row clears a client's signature.
- **The list and SRC SETUP.** Every site that shows or stores a track's
  machine reads the signature, so a signed track shows its client's row.
  The list scrolls past six rows. RIGHT on the row of a client that plays its
  base's slot opens the base's slot list; LEFT, or closing SRC SETUP, ends
  that pick.
- **The pages.** Each UI tick publishes each client's page as its row's in
  PB_TABLE. A client calls `mc_publish()` when its page changes between ticks.
- **The validator.** Stock's Part validator sees the base's defaults on a
  signed track's 12 knob bytes, then the client's values are put back.

## Hooks

Hooks are C functions: arguments on the stack, the result in `d0`, `d0`-`d1`
and `a0`-`a1` free.

| hook | called | arguments | result |
|---|---|---|---|
| `page` (required) | the page resolver, LFO SETUP's names, each UI tick | the track's machine byte in the Part (0 when no bank is loaded) | the PLAYBACK descriptor |
| `tick` | each UI tick, after the pages | none | none |
| `keep` | the Part validator, before stock's (restore 0) and after (restore 1), per signed track | the Part, the track, restore | none |

A client that needs another stock site claims it itself, as any module does.

## Rules

- A client claims none of the sites above. The ledger refuses a client that
  does, as it refuses any two claims on one site.
- A client's code is its own: no test for other machines, no chain, and no
  row constant, even where it compares stock's list cursor (`0x460e738e`)
  with its row: read `<prefix>_mc_row`
  ([TRAPS.md](../contributing/TRAPS.md#trap-machine-row-constant)).
- A client writes its knob defaults through `<prefix>_mc_defaults`, never
  into the Part itself.
- A machine ported from another firmware keeps its proven bytes: it stays
  outside `CLIENTS` until its author's build is a client.

## Limits

- **Three clients in one remix.** PB_TABLE (`0x400d5f38`) has room for rows
  5 to 7. Six stock instructions read the table, two of them at MACHINES's
  own sites, so a `TableGrow` can move it and lift the limit.
- **Five machines are not clients:** OCTA303, CX OSC and WAVE CF are still
  on HOOKS's `machine_rows` chain, and BLACKPYRAMIDS_303 and SYNTH MACHINE
  are ports. MACHINES conflicts with each until it is a client
  (`modules/machines/manifest.py`).
- **The base is FLEX.** The validator masks a client's knobs with FLEX's
  defaults, so `CLIENTS` refuses another base until it looks them up per
  base.
- **A machine's CPU cost** is the client's to bound: OCTA303's limit of two
  signed tracks a Part is its own, not MACHINES's.
