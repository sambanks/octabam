# `verb-parts` — VERB PARTS

A Part saved with PLATE REV, SPRING REV or DARK REV opens on [VERBERATION](../verberation/README.md), in PLATE, ROOM
or HALL mode at that mode's defaults. In [`octabam-verbs`](../../remixes/octabam-verbs/README.md).

## What it does

`octabam-verbs` has no chooser row on the stock reverbs' ids (`0x14`, `0x15`, `0x16`): they are hidden rows, VERB
PLATE, VERB ROOM and VERB HALL, which run VERBERATION's code under no name. This module moves a Part off them as the
firmware applies it:

- **Where.** Two `jmp` detours, inside both routines that apply a Part to the engine: `0x400090aa` in the Part apply
  `0x40009094(bank, p)` (project and bank loads, Part paste, save, reload, the pattern's Part; bank in a5, Part in
  a6) and `0x40009e10` in the pattern-change apply `0x40009e00(bank, p)` (KITS' staged Kits go through it; bank in
  d6, Part in d5). Each replays the six-byte `move.b %dN,0x80001828` it displaced. The routines' entries are
  VARISPEED's (`rp_apply1`, `rp_apply2`), whose stubs replay the prologue and come back; nothing between the entry
  and these sites reads the Part, so no HOOKS bridge is needed and VARISPEED's bytes do not move. A census of the
  stock image finds 12 calls and jumps to the two routines, every one at the entry.
- **What.** In the working Part (`0x400e21e0 + bank·0x9b340 + 0x8ed80 + p·0x18b2`), for each track whose FX2 id
  (`+0x08 + t`) is `0x14`, `0x15` or `0x16`, it writes VERBERATION's id there, then the six page-1 bytes
  (`+0x12c + t·24`) and six page-2 bytes (`+0x304 + t·30`) of the matching mode from `vp_tab`: PLATE for `0x14`,
  ROOM for `0x15`, HALL for `0x16`. The build generates the table from the hidden rows' manifests (each is
  VERBERATION's knobs in one mode) and the id from the remix's binding.
- **The sign.** The id itself: no chooser offers `0x14..0x16` in this remix, so a Part that holds one was saved with
  a stock reverb, or with an earlier image's VERB row. Either converts.

The Part in RAM is changed, not the card: the project is converted on the card when it is next saved. A Part is
converted when it is applied, so a bank or a Kit not yet played keeps its stock values until it is.
