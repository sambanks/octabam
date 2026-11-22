# `mode-defaults` — MODE DEFAULTS

Turning a MODE on the panel re-defaults the knobs around it to that mode's
`ModeView` (`docs/contributing/MODULES.md`, "Per-mode knob names and defaults").

## Open

- The Part bytes are written by the same formulas `modules/cc-map` proves
  against the editor; the verifier reads the live lane only.

## Hook

Both page-2 editors call the project-dirty routine `0x40027e00` after their
Part and shadow stores and before the live-lane store:

| editor | entry | detoured jsr | at the site |
|---|---|---|---|
| FX2 page 2 | `0x4003a9dc(slot2, ticks)` | `0x4003aaea` | a2 = slot2, d2 = the clamped value, d4 = track, d5 = part |
| FX1 page 2 | `0x4003abe4(slot2, ticks)` | `0x4003acf2` | the same |

`modedef.s` replays the call, reads the slot's effect id from the Part
(`+0x8ed88 + track` / `+0x8ed80 + track`), and walks the table: an entry
whose id and MODE slot match, and a view whose mode equals the value, has
its pairs written -- page-1 slots through `0x40054cd8(track, flat, value)`
(flat `0x12 + k` FX1, `0x18 + k` FX2: Part, shadow, live byte, the
descriptor's clamp), page-2 slots with the editor's own stores (Part
`+0x8f084`/`+0x8f07e`, shadow `0x100a51d2`/`0x100a51cc`, lane `+0x38`/
`+0x32`, the slot's redraw flag `0x46c7d244[(slot2*5+1)*4] = 20`). The
dirty flags are the editor's, already set. Registers d2-d7/a2-a6 are
preserved as the displaced callee preserves them.

## Over MIDI

CC MAP's cave calls `CC_MODEDEF2` / `CC_MODEDEF1` after its page-2
write (a2 = slot2, d2 = the clamped value, d4 = track, d5 = part); the
build resolves the two symbols to this unit's entries when it is in the
image (ROM units are linked before the caves since 15 Sep 2026; the cave's
ratified-bytes oracle is set aside for it, as for a bridged CC_NEXT) and
to a stock `rts` (0x40027e1a) otherwise. Measured under the port: CC 62 =
1 on T1's channel lands GRAIN's view in the lane, and a CC 63 in the same
frame then sets SCTR over it.

## The table

Generated per remix by `manifest.table_inc` (`Linked.include`), one entry
per module in the image with views: `id, mode slot, nviews`, then per view
`mode, npairs, (slot, value)*`; `0xff` ends it. 528 B linked in bottleservice.
