# Scenes + Kits: the bridge

The module that lets MIDI SCENES (bkkbrls-del), Octakit (Em) and CC→page 2
share one image. `Kind.CF_PATCH`: one DRAM unit (`chains.s`), one detour,
three `Override`s. Nothing of its own to use; it exists so the other three
compose.

## The two shared sites

**`apply_part` entry, `0x40009094`.** His `apply` wrapper and her
`engine-part-load` write both rewrite the same eight bytes. His did: save
the caller's return address into `apply_ret`, return through `after`
(which unpacks the new part's scene locks), `jsr pack` (which packs the
outgoing part's), replay the displaced prologue, jump into the routine.
Hers: `jmp gk_stock_engine_part_load_and_publish`, whose active path
replays the same prologue, runs the **stock body** through her trampoline,
and publishes the Kit bookkeeping around it. So the bridge stub is his
pre-work followed by a jump into her entry — never a second replay:

```
chain_apply_part:
        tst.l   (__gk_lifecycle_state).l      | 0 = active
        bne.s   1f
        move.l  (%sp),(apply_ret).l
        move.l  #after,(%sp)
        jsr     (pack).l
1:      jmp     (CHAIN_APPLY_NEXT).l          | her entry
```

The guard is hers to respect: while her lifecycle state is not active
(boot-time part loads) she chooses her path by comparing the **stock
caller's** return address on the stack against known sites, and anything
else is her fatal. So the swap only happens once she is active; before
that the site is hers alone, and his boot-time unpack of the first part's
locks is skipped (the next apply does it).

Why his hooks still mean something under Kits: her active path applies
the stock Part window (his `pack`/`unpack` address it through
`0x46c82456`). She wraps it; she does not replace it.

**The MIDI CC dispatch entry, `0x400d64a0`.** Her recipe installs
`gk_stock_midi_control_parameter`; CC→page 2 repoints the entry to its
cave. The cave keeps the entry; its fall-through symbol `CC_NEXT` becomes
her handler (the build defines it from her skipped write), and hers falls
through to stock's as before. Order: CCs 62–67 ours, then hers, then
stock's.

## How the build does it — `schema.Override`

An Override says "my claim at this site stands in for that module's": the
build skips the overridden detour or recipe write, and when the override
names a `defsym`, defines it as the target the skipped write carried (a
`jmp abs.l`'s address or a 4-byte pointer) for every unit and cave it
links. The ledger owns the site to the bridge and still refuses MIDI
SCENES + OCTAKIT in a remix that does not carry it. The `octakit` remix
alone is unchanged: overrides only apply when the bridge is selected.

## Measured vs inferred

- ✅ The `mods`, `rig-mods` and `mutables-mods` remixes build; `make check`
  green; the octakit-alone identities untouched.
- ✅ Under the ColdFire port with a project of static samples (boot → LOAD
  PROJECT → play): the numbers are in `docs/remixer/PLACEMENT.md`; the
  claim is that every `apply_part` during the load goes stub → her entry,
  her fatal never runs, and in the active state his `after` runs once per
  apply.
- 🟡 **Not measured**: hardware; MIDI CCs through the chained dispatch
  (the port has no MIDI input); his Part *save/reload* menu hooks
  (`0x4002dd12`, `0x4002dd56`, `0x4005e05a`) against her LOAD/SAVE KIT
  menus — they detour stock menu actions her UI may not route through.
  That is the Kits-aware work that remains his and hers; this bridge makes
  the image buildable and the apply path coherent.
