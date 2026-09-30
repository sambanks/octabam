# The MAIN MENU table system

How the MAIN MENU tree is stored and walked, and the firmware routines a
menu screen can call to edit a track's parameters. Markers as in `CHIP.md`:
✅ read out of the image and confirmed against `objdump -m m68k:cfv4e`
disassembly or driven under the emulator / on the unit, 🟡 inferred.
Addresses are SDRAM addresses, `address = 0x40000400 + file offset` into
`out/raw/section_3_MAIN_OS.bin`. The full record of the shortcut and
bus-screen work (modules `menushortcut` and `busscreen`, both retired and
in git history) is `MAINMENU_BUSSCREEN.md` (`git show 3ceba41:docs/history/MAINMENU_BUSSCREEN.md`).

## 1. Record types ✅

Menu row, 0x18 bytes:

| offset | field |
|---|---|
| +0x00 | label string pointer |
| +0x04 | window/geometry descriptor pointer (0 on every leaf row) |
| +0x08 | action function pointer. Also the selectable marker: cursor-move and submenu-entry code (`0x40064f0a`, `0x40064fe8`) skip rows whose +0x08 is 0 (the glyph-`0x17` separators); every real leaf carries at least the shared `rts` |
| +0x0c | right-column value getter, called by the draw function `FUN_40064908`; 0 = no value column |
| +0x10 | child list-descriptor pointer (0 on a leaf) |
| +0x14 | page id, dispatched when the action is the shared no-op (section 3) |

Stride confirmed from code: `d2 = d3*32 − d3*8` at `0x4006496a..0x40064970`.

Menu list descriptor, 0x1c bytes: `+0x00` row count, `+0x04` scroll /
first-visible index, `+0x08` cursor within the window, `+0x0c` absolute
selection (`+0x04 + +0x08`, kept by `0x4007ec7c`/`0x4007eca4`), `+0x10`
visible-row count, `+0x14` row count again, `+0x18` row array pointer.
Descriptors ship inert; `0x40064c70..0x40064cac` calls `init(&desc+4,
visible, count)` (`0x4007ec60`) at boot for the root (5 visible), the
submenus (7) and the demo menus (2), guarded once by `tst.l 0x400cbda0`,
count read from `+0x00`. A descriptor built in a cave is not in that run
and must ship with `+0x10` set or its pane draws zero rows (octalab, MKI,
13 Sep 2026; their reading of `+0x08..+0x14` as cursor / absolute
selection / visible-row count / count re-verified here). Their "eleven
pages, stride 0x1c" for the 16 × 0x14 menu-state table was dumped under
both strides here: 0x14 holds (id 12's draw = `0x40068e00`).

Root window descriptors (`0x400cbc34/48/5c/70`) are 20-byte records
`{0x13, 0x09, 0x01, ptr, ptr}`: the category icon, 19 wide × 9 tall. ✅ Each
`ptr` is a plane of 19 LONGS, one per column, with the column in the long's
top byte: a plane is `0x4c` bytes, and in all four stock icons the second
plane starts `0x4c` after the first. The second plane is `0xff800000` in
every column of all four (read from the image, 28 Sep 2026). Which bit of
the column is the top row isn't settled here: STEMS's icon is symmetric top
to bottom. ❌ Retracted: "a plane of 19 words", and "the second plane is
`0xff80`" (the high word of the long only). 🟡 The rest from octalab's
fifth category, which draws its own icon on a MKI.

## 2. The tree ✅

| list descriptor | count | row array | contents |
|---|---|---|---|
| `0x400cbd8c` ROOT | 4 | `0x400cc698` | PROJECT · SYSTEM · CONTROL · MIDI |
| `0x400cbcac` | 15 | `0x400cc308` | PROJECT: CHANGE/SAVE/RELOAD/SYNC TO CARD/SAVE TO NEW/EXPORT TO SET/CHANGE(set)/COLLECT SAMPLES/PURGE SAMPLES/SAVE CUR BANK/RELOAD CUR BANK + four glyph-`0x17` separators |
| `0x400cbd1c` | 6 | `0x400cc4e8` | SYSTEM: USB DISK MODE, OS UPGRADE, DATE/TIME, PERSONALIZE, CARD TOOLS, STATUS |
| `0x400cbd54` | 6 | `0x400cc5a8` | CONTROL: AUDIO, INPUT, SEQUENCER, MIDI SEQUENCER, MEMORY, METRONOME |
| `0x400cbd70` | 4 | `0x400cc638` | MIDI: CONTROL, SYNC, CHANNELS, TURBO STATUS |

Root rows: window descriptor set, child set, action 0. Leaf rows: window 0,
child 0, action or page id set.

## 3. Dispatch ✅

- Real handler: OS UPGRADE `0x400636bc`, USB DISK MODE `0x40063728`. A new
  row can carry a cave-resident handler; id 0 calls the row's +0x08 with
  one argument = 0 (`0x4006505a`).
- Shared no-op + page id: every other leaf points at `0x400648f8` (`rts`,
  `4e 75`) and is dispatched by +0x14: DATE/TIME `0x0f`, PERSONALIZE `0x0c`,
  CARD TOOLS `0x0d`, STATUS `0x0e`, MIDI CONTROL/SYNC/CHANNELS/TURBO STATUS
  `0x08..0x0b`. The tree-state key handler `0x40064e64` on keycode `0x31`
  ([YES]/ENTER) reads row+0x14 at `0x4006502c`; ids 1..15 (bounds-checked
  `0x40065034`) open the matching entry of the menu-state table.

Menu-state table `0x400cbdac`: 16 entries × 0x14, `{on_enter, on_exit,
draw, key_handler, encoder_handler}`, state index `DAT_400cbf40`; a NULL
member is skipped (`tstl %a0 / beqs / jsr %a0@`). State `0x0c`'s draw is
`FUN_40068e00` (PERSONALIZE). All 15 usable states are occupied (live data
follows the table); state 0 is unreachable. Every state is a screen inside
the menu window, so the id path cannot open a parameter page. The table is
named by three `lea` immediates only (`0x40064bd2`, `0x40064e34`,
`0x400650e6`); extending it = copy to a cave, append, patch three operands
(`busscreen` did this, 17th state, tags 85–90 on the unit).

## 4. The draw/nav engine ✅

Body `0x40064908..0x40064fb2` (🟡 boundaries, from the xref cluster):

```
4006495e:  addl 0x400cbd90,%d3        ; += root descriptor's scroll field
4006496a:  lsll #3,%d0                ; d3*8
4006496e:  lsll #5,%d2                ; d3*32
40064970:  subl %d0,%d2               ; d2 = d3*24
4006497a:  movel %a0@(4,%d2:l),%sp@-  ; push row+0x04
40064982:  moveal 0x400cbda4,%a0      ; row array pointer
40064988:  addal %d2,%a0
4006498a:  movel %a0@,%sp@-           ; push row+0x00 (label)
```

The root descriptor is referenced from eight sites in the engine
(`0x400649b8`, `0x40064c72`, `0x40064d22`, `0x40064e9a`, `0x40064eaa`,
`0x40064ef0`, `0x40064f40`, `0x40064f8e`) and one data cell, `0x400cbda8`:
the focus pointer (which list descriptor the cursor is in; persists across
menu close). PROJECT's and SYSTEM's descriptor addresses are hard-compared
at `0x40064fa0..c2` for an alternate-list swap keyed on `0x80000088`
(semantics unknown); add rows to CONTROL or the root, not those two.

Driven under the port with real keys, the MKII (PROJ) and the MKI
(FUNC+MIXER) alike (`tools/verify/stems_menu_probe.py`, 29 Sep 2026;
`STEM_REC.md` 16.1):

- ✅ YES and RIGHT move the focus from the root into the selected
  category's list; LEFT moves it back. NO inside a list closes the whole
  menu, and the focus pointer keeps the list.
- ✅ **The menu redraws on keys, not by itself.** A row's label pointer
  changed while the menu shows it stays off the screen (3 s, no key); the
  next key that redraws the menu draws the new label. A module that
  changes a label from outside a key handler is seen at the next key.
- ✅ A row whose action is 0 draws as plain text, and the cursor skips it:
  DOWN from AUDIO lands on SEQUENCER when INPUT's action is 0. ✅ It skips
  ONE such row, not two in a row: with two together, DOWN stops on the
  second, where ENTER calls address 0 (STEMS's first layout). ✅ It never
  moves onto a last such row: DOWN from the row above stays put. So rows
  without an action must never be adjacent; one may be the last.
- ✅ With the firmware's own font, the list pane clips a label at
  x = 118 and the root column at x = 56 (the right edge of 24 Ws). `WRITE
  FAILED` ends at 105 and `STEMS` at 45.
- ✅ PLAY and STOP work with the menu open, and it stays open.

## 5. Adding a row ✅

The root row array `0x400cc698` has one reference in the image, the rows
pointer `0x400cbda4`; live data follows the array. Copy the rows to a cave,
append, repoint the rows pointer, bump the count in the descriptor. The
menu widget reads the count at open time. Same move for a submenu
(CONTROL: rows pointer `0x400cbd6c`, count `0x400cbd54`). Hardware
precedent: PERSONALIZE extended by two items (`git show
40a1f19:tools/patch_menu.s`, `git show 3ceba41:docs/history/NOTES.md`); CONTROL > REVERB /
DELAY rows on tags 85–90. Two modules that both grow one submenu cannot
coexist (the build refuses the second: the count is no longer stock).
Cave placement: the decoded free band `0x400d2000..0x400d8000`
(`build_bus.SAFE_CAVE_CEIL`). `0x40108800` is inside the image's last
~30 KB, zero at rest and OS `.bss` (the PROJECT subsystem's RAM): a cave
there passed a static zero-check and a no-project boot and faulted on
[PROJ] (tag 91). octalab's fifth MAIN MENU category (MKI ✅ 7 Sep 2026)
added: a null-action row is a heading the cursor skips; a row inside a
pane cannot descend (`+0x10` read on the root only); the descriptor must
ship initialised. `RANDOMIZE PAGE` = `0x4005b9c0`, via `0x400bab22`.
STEMS (`modules/stems`, 29 Sep 2026) is a fifth category run under the
port on the MKII and the MKI by real keys (`verify_stems_menu`): the root
grown by a `TableGrow` of the four stock rows plus its own and a `Poke` of
the count; the list, its eleven rows and the icon in DRAM; labels switched
by one aligned pointer write, from the actions and from an RTOS task.
Unflashed; `STEM_REC.md` section 16.

## 6. Opening a parameter page from a handler ✅

Keymaps: 26-byte records `{u8 code, 0, press, release, h3, aux, 0, u16
flags}` in two tables, `0x400bfbf6..` and `0x400c01f4..0x400c0840` (the
second carries `0x1c..0x1f`; `0x1c` = the MKII MAIN MENU key, thunked to
the menu opener `FUN_40064c18` via `0x40064d78`). Page keys `0x22..0x26` →
`FUN_4005578c(keycode, edge)`, mapped through `0x400a7280` = `(0, 2, 1, 3,
4)`; [FX2] = `0x26` → kind 4. Menu keys: `0x31` [YES]/ENTER, `0x34` up,
`0x33` down (`0x32/0x35/0x36` also down on the bus screen).

- `FUN_400554e0(kind)`: the page switch. Writes the current-page-kind
  global `0x460d1684` (long; byte mirror `0x46c7d8d8`), resolves the
  descriptor via `FUN_40031ee0(-1,-1)` → `FUN_40031da4(track, kind)`,
  stages it with `FUN_400326d4`, redraws (`FUN_4004d948`).
- `FUN_4005996c()`: EFFECT 2 SETUP window opener (screen record
  `0x400bc484`: handle +0x08, title +0x10, open +0x24, close `FUN_40056830`
  +0x28, draw `FUN_40037590` +0x2c). Closes sibling setup windows, calls
  `FUN_400554e0(4)`, creates the window (`FUN_4005829c`); called while open
  it toggles closed.
- Current audio track = byte `0x80000000` (UI mirror `0x100b14cc`); current
  part `0x80000003` (UI mirror `0x100b14cf`). `0x80000012` ≠ 0 = MIDI mode,
  track +8. Page edits key off these globals, so a handler selects the host
  track with `FUN_40083bf8(track_index)` (clamps, writes both globals,
  tears down the old track, restages, redraws, LEDs; also called from
  `FUN_40061a94`).
- `FUN_40064bc0` closes the menu (destroy window, unregister the input
  overlay, reset state, MENU LED off); stock calls it from handler context
  ([NO] in `FUN_400650a0`). `DAT_400c0aac` (last page/track keycode for
  double-press, hold counter `0x460d5de0`) keeps its pre-menu value.
- Per-track FX2 ids for finding a host track: `0x80000ecc[8]`
  (`PARAM_PAGES.md` section 5d).

Menu-window destroy + setup-window create in one key dispatch is not a
stock sequence; the deferral idiom is the timer callback `FUN_40000c3c`
(used by `FUN_40063660`). The shortcut module ran on tags 85–90 and was
retired 13 Sep 2026 (broken on the unit; `git show 3ceba41:docs/history/MAINMENU_BUSSCREEN.md`).

### 6b. A page of one's own over GRID RECORDING (nordseele, MKI, 15 Sep 2026) ✅ theirs

Holding a trig registers the stock's trig-held input map over any other
(LEVEL → `0x400434d8`). LEVEL then opens the sample-lock list
(`0x40024bb4`) and the popup engine frees the popup under it, its cell
zeroed, without calling that popup's closed callback. A map that popup left
registered receives the trig's release; one that swallows it leaves the
held mask `0x460d174a` set and the firmware keeps the trig held: [REC]
offers TRIG COPY, grid recording cannot be left, the sequencer will not
stop. A page whose popup cell reads 0 must hand trig events (press and
release share `0x40060ce0(code, down)`) to the stock and unregister its
map. The current track's key pressed again in grid recording opens the
slot list over any popup, closing it; a page that forwards the track keys
has to swallow that one.

### 6c. Input layers ✅ (read from the image, driven under the port, 25 Sep 2026)

A layer is `{next, keys*, encoders*, +12, +16, -1, -1}`:
- `0x40031494(layer)` appends it to the list at `0x460d165c` and sets
  `+16` to −1.
- `0x4003146c(layer)` removes it.
- Both re-run `0x4003125c`, which walks the list head to tail and rebuilds
  a per-key cache at `0x46c7d8de + code*24` and a per-encoder cache at
  `0x46c7dede + index*20`. A later layer overrides an earlier one, so the
  last layer pushed is on top. A key held during the rebuild keeps its
  cached handlers, which is why a press handler may push a layer.

**Key record, 26 bytes**, ended by a record whose code byte is `0xff`:

| offset | field |
|---|---|
| +0 | code |
| +2 | press |
| +6 | release |
| +10 | repeat |
| +14 | a sub-map, chained through the target's `+12` |
| +18 | a flag word |
| +22 | u16 repeat delay |
| +24 | u16 repeat rate |

For press, release and repeat, −1 inherits the layer below; any other
value, 0 included, replaces it.

**Encoder record, 22 bytes**, ended by `0xff`:

| offset | field |
|---|---|
| +0 | index: A..F = 0..5, LEVEL = 6 |
| +2 | handler `(index, delta)` |
| +6 | a second handler |
| +10 | a third handler |
| +18 | a fourth handler |

These are copied without inheritance.

**Fall-through:** an encoder with no record in any layer reaches the page
underneath. TEMPO's layer (`0x400bb4ec`) has LEVEL only, which is why
A–F turn the page behind the stock TEMPO window.

**TEMPO's keys:**
- UP `0x33` / DOWN `0x20`: the tempo step `0x4004b954 → 0x4004b824(0, ±1)`,
  0.1 BPM. LEVEL (`0x4004b918`) calls it as `(delta, 0)`, whole BPM, ×7
  while LEVEL is pushed. FUNC holds the sub-map `0x400c52aa` (UP/DOWN the
  same, YES `0x4004b79c`).
- `0x4003171c(code)` reads a field of the per-key handler cache
  (`0x46c7d8ee + code*24`); it is nonzero for FUNC at all times, since FUNC's
  record carries a sub-map. A key's held state is the panel parser's row
  byte `0x46100b18[code >> 3]`, bit `code & 7` (`PANEL.md` section 4b).
- YES `0x31`, NO `0x32`, TEMPO `0x18`: close, `0x40056930`.

Arrow codes: LEFT `0x34`, RIGHT `0x21` (`PANEL.md` section 4b).
`modules/tempo-bus` pushes a layer of its own over TEMPO's.

## 7. Editing parameters from a screen ✅

Call the firmware's writers; do not reproduce them. Traced with a write
hook, the page-2 knob editor makes nine non-stack stores: the Part array,
the working mirror, two dirty bits, the staged page `0x46c7d244 +
slot*0x14` (two words; what the knob drawer reads), the live byte in the
`0x8000xxxx` block (what the frame builder reads), `DB + 0x9b332` and
`0x100f8598` (unidentified). The page-1 writer does more again (redraw
work, a UART register).

Where values live: the staged page `0x46c7d244 + slot*0x14` (built by
`FUN_400326d4`; valid only for the page currently staged); the Part, `DB =
*(0x46c82456) + part*6322` (id byte `+0x8eda2 + track`).

| control kind | Part array | mirror |
|---|---|---|
| page-1 values | `+0x8ee9a + track*24` | `0x100a4f70` |
| page-2 knobs (PLAYBACK) | `+0x8ef5a + track*30 + machine*6` | `0x100a50a8` |
| page-2 selects | `+0x8f04a + track*30 + page*6` | `0x100a5198` |

Writers:

- Page 1: `0x40054cd8(track, flat, value)`, absolute, self-contained.
  `flat` 0–5 → `DB + 0x8edaa + track*30 + machine*6 + slot` (PLAYBACK);
  `flat` 6–29 → `DB + 0x8ee9a + track*24 + flat − 6` (AMP · LFO · FX1 · FX2;
  FX2 page 1 = `flat` 24–29; measured at two tracks and a dozen indices).
  Page 2 is not reachable through it: it clears a scene-lock bit `1 <<
  flat` in a 32-bit word per track (`0x80000110 + (track + 1290)*4`) and
  zeroes `0x80001658 + track*32 + flat`, a 32-entry array (the same ceiling
  `MIDI.md` records for CC and scene locks).
- Page 2: one editor per page, `(slot2, delta)`, read-modify-write, track
  and part from the globals. `0x4003a474` is PLAYBACK's (Part
  `+0x8ef5a + track*30 + machine*6 + slot`, index `0x460d5c30`, live
  `0x80000830 + track*72 + slot`); FX1 `0x4003abe4` (Part `+0x8f07e`, live
  +0x32); FX2 `0x4003a9dc` (Part `+0x8f084`, live +0x38). Retracted 13 Sep
  2026: "`0x4003a474` is the FX page-2 editor" (the `cc_map.s` cave built
  on it wrote PLAYBACK's bytes until then; `PARAM_PAGES.md` section 5b). Slot
  argument is 0–5 (`moveq #5,d4; cmp a3,d4; bcs exit`); the `a3 == 6` arm
  is a repeat-by-delta loop gated on `0x460d1a48 == 1`. The delta comes
  from `0x4003249c(slot, delta)`, which reads the staged page and returns 0
  under the emulator with no live page; on the unit all six slots edit
  (tags 85–90). The editor clamps against the descriptor in its own
  page-kind table (`0x400d5f38[page]`, read at `0x4003a524`), i.e. whatever
  page was staged last: from a menu state this squashed a 0–127 knob to
  0..3 and ramped selects to 127. Fix used: call the editor for its stores,
  then set `clamp(before + delta, 0..count−1)` yourself into the Part, the
  live byte and the mirror.
- Selects: committer `0x40079424`, inputs from globals `0x46c8d19c` (value)
  and `0x46c8d1a0` (phase); front door `0x4006de34(kind, value)` sets both.
  Two-phase: phase 1 or 4 stages (bounds the value at 135, indexes a
  1096-byte-stride table at `0x100b14f0`, writes the pending edit to
  `0x460be9e8`/`0x460be9ec`, track/part from `0x100b14cc/cf`); phase 0
  commits (select array, machine byte `+0x8eda2`, dirty bit `+0x95048`,
  `+0x9b332`, redraw). Driven end to end under the emulator the array takes
  the value, at offset 0 (track 0, page 0, slot 0): the address term the
  staging phase leaves behind is unidentified. Not needed since MODE moved
  to the even slot 6 (`PARAM_PAGES.md` section 6).
- FX2 effect id: `0x40027e4c(struct, 0, part, kind, 0)` (calls pc-relative
  at `0x40028f9a`, `0x40028fda`; struct = fixed global `0x460bf218`, type
  tag at `+0x8ed8`, payload at `+18/+19`). Kind-4 arm with tag 29 writes
  the payload to `DB + track + 0x8ed88`, mirror `0x100a4ed6`; driven under
  the emulator, `0x07` → `0x1c`. Kind 0 / tag 26 is the `+0x8f04a` arm.
  The mirror write faults on an unmapped page in a bare emulator.

Encoder handler ABI: `encoder_handler(index, delta)`, two longs, cdecl;
both stock handlers (states 3 and 4, `0x400658f0`, `0x40065c98`) share the
prologue (`moveal %sp@(12),%a2` index, `movel %sp@(16),%d2` delta; `delta*7`
fast-turn acceleration applied when `0x4003171c(index+56)` returns
nonzero). A screen receives the raw step.

Bus-screen facts that carried (tags 85–90, `git show 3ceba41:docs/history/MAINMENU_BUSSCREEN.md`):
stock cursor bar via the rect-invert `0x40012254(window,x1,y1,x2,y2,-1)`;
window ctor `FUN_4005829c`, list drawer `FUN_40037590`, `sprintf`
`0x40013a08`; the FX2 page stages index 0, so a screen reading the Part's
page-2 bytes at `+24+slot2` was self-consistent and audible (the editor's
live-lane write carries the value) but did not survive a part reload
(`modules/cc-map`, tag 13).

## 8. Undecoded

The drawing primitives behind the state table's draw functions
(`PANEL.md` now has the surface, fonts, text blitter and the dithered
rectangle; the window/geometry descriptors above them are still unread), the
`0x80000088` alternate-list semantics, `FUN_40043728` (old-track teardown),
the two `0x46c7d8d8` readers (`FUN_4005a918`, `FUN_4005cbd8`), the indirect
widget-setup pointers `verify_menu.py` warns about (`PTR_FUN_400bb7f0`
etc.), the select committer's address term.
