# MACHINES

Platform module: the track's machine list, SRC SETUP and the Part validator,
held once for every added machine. A machine is a client of MACHINES: it
says what it is (its signature, its name, its base machine, its defaults and
its page), and MACHINES puts it on the list: the first client on row 5, the
next on row 6, and the list scrolls past six rows.

The contract: [docs/specs/MACHINES.md](../../docs/specs/MACHINES.md).

## Using it

A musician sees no MACHINES of its own: every added machine in the remix
appears after stock's five on the track's machine list and in SRC SETUP.
Choosing one makes the track a FLEX track signed by that machine. Choosing
FLEX or any stock machine again clears the signature. On a machine that plays
FLEX's sample slot (DRUMMER), RIGHT on its row in SRC SETUP opens FLEX's slot
list, and LEFT returns to the row. While the list is open, FLEX's SETUP knobs
show the machine's; closing SRC SETUP from the list (NO, FUNC + SRC) gives
them back to FLEX.

## Writing a client

1. Add the module to `CLIENTS` in `manifest.py`: key, prefix, signature,
   name, base, whether it plays the base's slot, and its hooks.
2. Declare `requires=("MACHINES",)` in the module's manifest, and claim none of
   the sites in the spec.
3. Export `<prefix>_mc_defaults` (12 bytes) and `<prefix>_mc_page`, plus
   `<prefix>_mc_tick` and `<prefix>_mc_keep` when named.
4. Where the client needs its row, read `<prefix>_mc_row`.

DRUMMER (`modules/drummer/adapter.c`) is the reference client.

## How it works

`machines.s` holds one stub per stock site. Each stub asks `mc_type`
(`machines.c`) for the track's row: 5 plus the client's index when the track
is FLEX and carries a client's signature, else the stored machine.
`manifest.py` writes the remix's client tables into `remix.inc`:

- the signatures;
- the defaults;
- the flags (base, slot);
- the hooks;
- the name table;
- each client's row word.

`machines_unit.s` is generated: edit `machines.c` or `machines.s`, then run
`python3 generate.py`.

The stubs come from ANALOG BD's registration (repeat98), which DRUMMER,
OCTA303 and WAVE CF each carried a copy of, and from HOOKS's scrolling list
(Sam Banks).

## Gate

`verify.py` runs MACHINES under Unicorn with two test clients, for one client
and for two. It checks:

- the rows and names;
- the list's drawer and box over every top row;
- the commits from every starting machine;
- the slot-list pick;
- SETUP's editor and drawer;
- the page resolver and LFO names;
- the tick and the validator.

It also checks that the real clients define every hook they name, and that
each site in a built image holds MACHINES's jump.

## Open

- ANALOG BD, OCTA303, CX OSC and WAVE CF are still on HOOKS's `machine_rows`
  chain, and conflict with MACHINES until each is a client.
- The base is FLEX: the validator masks a client's knobs with FLEX's defaults.
- BLACKPYRAMIDS_303 and SYNTH MACHINE are ports. They stay outside until their
  authors' builds are clients.
- Three clients at most: PB_TABLE has room for rows 5 to 7 until it is moved.
