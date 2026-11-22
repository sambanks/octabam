# `verb-parts` — VERB PARTS

A Part saved with PLATE REV, SPRING REV or DARK REV opens on its [VERBERATION](../verberation/README.md) row
(VERB PLATE, VERB ROOM, VERB HALL) at that row's defaults. In [`octabam-verbs`](../../remixes/octabam-verbs/README.md).

## What it does

The rows take the stock reverbs' ids (`0x14`, `0x15`, `0x16`), so an old Part already opens on the right row, but
with the stock reverb's knob values, which VERBERATION reads as its own (DARK's TIME 24 as AMNT, and so on). This
module rewrites them as the firmware applies the Part:

- **Where.** Two `jmp` detours, inside both routines that apply a Part to the engine: `0x400090aa` in the Part apply
  `0x40009094(bank, p)` (project and bank loads, Part paste, save, reload, the pattern's Part; bank in a5, Part in
  a6) and `0x40009e10` in the pattern-change apply `0x40009e00(bank, p)` (KITS' staged Kits go through it; bank in
  d6, Part in d5). Each replays the six-byte `move.b %dN,0x80001828` it displaced. The routines' entries are
  VARISPEED's (`rp_apply1`, `rp_apply2`), whose stubs replay the prologue and come back; nothing between the entry
  and these sites reads the Part, so no HOOKS bridge is needed and VARISPEED's bytes do not move. A census of the
  stock image finds 12 calls and jumps to the two routines, every one at the entry.
- **What.** In the working Part (`0x400e21e0 + bank·0x9b340 + 0x8ed80 + p·0x18b2`), for each track whose FX2 id
  (`+0x08 + t`) is `0x14`, `0x15` or `0x16` and whose FX2 page-2 slots 9 and 10 (`+0x304 + t·30 + 3`, `+4`) are
  both 0, it writes the row's six page-1 bytes (`+0x12c + t·24`) and six page-2 bytes from `vp_tab`, a table the
  build generates from the three rows' manifests (and refuses if a row's defaults would themselves look like a
  stock Part).
- **The sign.** The stock reverbs never draw page-2 slots 9 and 10: their descriptors leave both off
  (PLATE: `9:off c2 d0`, `10:off c128 d0`; SPRING and DARK the same), so a Part they saved holds 0 in both. On a
  row those slots are RATE and SIZE, and they are 0 together only when the operator set both to 0; such a Part
  would be reset to its row's defaults the next time it is applied.

The Part in RAM is changed, not the card: the project is converted on the card when it is next saved. A Part is
converted when it is applied, so a bank or a Kit not yet played keeps its stock values until it is.
