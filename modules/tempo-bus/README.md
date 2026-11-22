# `tempo-bus` — TEMPO BUS

The TEMPO window edits the bus engines. [TEMPO] opens it at the menu
window's size (118 × 64), with two boxes, DELAY and REVERB. The boxes list
each engine's parameters with the values the host page would show.

| control | does |
|---|---|
| UP / DOWN | move the cursor one row in the focused box, with key repeat; the box scrolls, five rows visible |
| A | edits the selected parameter on the host track; ×7 while A is pushed (the stock fast turn) |
| B | the same as A |
| LEFT / RIGHT | focus DELAY / REVERB; each box keeps its own cursor |
| LEVEL | BPM in whole steps; ×7 while LEVEL is pushed (stock) |
| FUNC + LEVEL | BPM in 0.1 steps (the step stock gives UP / DOWN) |
| C–F | held while the window is open |
| [TEMPO], [YES], [NO] | close (stock) |

## Open

- The MKII keymap: the port boots the MKI one. TEMPO, LEFT and RIGHT have
  the same codes in both.
- EXT SYNC: the header prints the internal tempo, where the stock window
  prints the external one.

## The window

The header prints the tempo at its left as `TEMPO 121.2`, or `PTN 121.2`
while the pattern tempo is on (the stock TEMPO draw's test, `0x80000024`,
`0x460d1aec`). To its right is the key: the arrows, the font's ◀ and ▶ (`0x13`,
`0x14`) around the stock ▲ and ▼ icons (`0x400b9d8c`, `0x400b9da0`); then
`A` and the font's knob glyph (`0x02`), the value knob, at the right edge. The header text sits 6 px under
the window's top edge; the boxes are 41 px, five rows, 3 px under the rule.

- **Rows and labels.** Top to bottom: MODE, TIME, WET, TONE in both boxes,
  then each engine's own from most to least used: the delay's FDBK, PING,
  SIZE (GLEN/SLEN), SCTR, DENS, PTCH; the reverb's SIZE, DLY, SHMR, SHFT,
  DIFF, GATE (`ROW_ORDER` in the manifest). DEL and REV (the host pages'
  own knobs) are left out, and so are the ones the current mode names
  `---`: CLEAN lists 6 delay rows, GRAIN 10, REVERSE 6; the reverb 10. The
  list is rebuilt on every draw from the descriptor's names
  after the MODE formatter has renamed them (`rows` in `helpers.s`), so a
  MODE change adds or drops rows at once. Labels are the descriptor's names
  (GLEN/SLEN as on the host page); the MODE row is labelled MODE, and its
  value is the mode.
- **Values.** Values are printed by the slot's own formatter: TEMPO SYNC's
  divisions, the select labels. A slot with no formatter prints a plain
  number.
- **Page-1 edits** go through the firmware's page-1 writer
  `0x40054cd8(track, 24 + slot, value)`.
- **Page-2 edits** make the FX2 page-2 editor's stores: Part `+0x8f084`,
  shadow `0x100a51d2`, live lane `+0x38`, and the four dirty flags. This is
  CC MAP's write path. When MODE DEFAULTS is linked before this module,
  its `CC_MODEDEF2` then applies the view, so a MODE change re-defaults
  its knobs as it does on the panel.
- **Clamping.** Values are clamped to the descriptor's minimum and count.

## How

| site | what |
|---|---|
| `0x40059f04`, `0x40059f08` (pokes) | the TEMPO window is created at 118 × 64 instead of 73 × 48 |
| `0x40059f2c` (detour) | the opener's tail: push this module's input layer over TEMPO's, draw |
| `0x4004b528` (detour) | the TEMPO draw, for every caller (BPM edits included): the bus screen |
| `0x40056930` (detour) | the TEMPO close: pop the layer, then the stock close |

Every draw call is one the stock CONTROL INPUT (`0x40065674`) and MIDI
SYNC (`0x4006730c`) screens make:
- header text `0x40012bd8` and its width `0x40012f30`, in font `0x400ba876`;
- the key's arrow icons through `0x400128a8`;
- the rule `0x40011910`;
- the titled box `0x4007efd0`, its title plain (the row bar marks focus);
- rows at a 7-pixel pitch;
- the invert bar `0x40012254`.

The input layer format is in `docs/firmware/MAINMENU.md` section 6c.

Two units, both pinned in measured free runs:
- `helpers.s` (384 B, with the row list) at `0x400d24d0`, the start of the
  overflow run. The floating caves take the run after it (bamsep26: next
  free `0x400d2c38` of `0x400d2ce0`).
- `tempobus.s` (1,524 B) at `0x400d64e0`, below the FX2 chooser's NONE
  row; its region ends at `0x400d6b00` (1,568 B).
