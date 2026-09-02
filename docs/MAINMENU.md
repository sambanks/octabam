# The MAIN MENU table system

Decoded 31 Aug 2026 while assessing whether the custom delay/reverb could get
dedicated menu entries (like the newer Elektron boxes) instead of living on a
host track's FX2 setup pages. The parameter-*page* system was already fully
decoded (`PARAM_PAGES.md`); the menu shell above it was not — `COVERAGE.md`
still lists the UI framework as a gap. This page closes the *table* half of
that gap: how the MAIN MENU tree is stored and walked. The renderer/input
half is still open.

Markers as in `CHIP.md`: ✅ measured (here: read out of the image and, where
it matters, confirmed against `objdump -m m68k:cfv4e` disassembly of the code
that consumes it), 🟡 inferred with falsifier.

All addresses are SDRAM addresses; the raw image maps as
`address = 0x40000400 + file offset` into `out/raw/section_3_MAIN_OS.bin`
(the base `scripts/disasm.sh` already documents, re-confirmed here by string
anchors).

---

## 1. The two record types ✅

**Menu row — 0x18 (24) bytes:**

| offset | field |
|---|---|
| +0x00 | label string pointer |
| +0x04 | window/geometry descriptor pointer (0 on every leaf row observed) |
| +0x08 | action function pointer — called by the firmware (see §3). **Doubles as the selectable marker**: cursor-move and submenu-entry code (`0x40064f0a`, `0x40064fe8`) skip rows whose +0x08 is 0 — that is what makes the glyph-`0x17` separators unselectable, and why every real leaf carries the shared `rts` |
| +0x0c | right-column value-getter function pointer (called by the draw fn `FUN_40064908`); 0 when the row has no value column |
| +0x10 | child list-descriptor pointer (0 on a leaf) |
| +0x14 | page id, dispatched when the action is the shared no-op (see §3) |

**Menu list descriptor — 0x1c (28) bytes:** `+0x00` row count, `+0x04`
scroll / first-visible index, `+0x18` pointer to the row array. Fields
`+0x08..+0x14` are not yet interpreted (🟡 — falsified if the draw engine
reads them for something load-bearing; only `+0x00`, `+0x04` and `+0x18`
were seen consumed in the window disassembled).

The stride is confirmed from code, not just layout: the draw/nav engine
computes `d2 = d3*32 − d3*8` (= ×24) at `0x4006496a..0x40064970` and indexes
the row array with it.

## 2. The tree ✅

| list descriptor | count | row array | contents |
|---|---|---|---|
| `0x400cbd8c` **ROOT** | 4 | `0x400cc698` | PROJECT · SYSTEM · CONTROL · MIDI |
| `0x400cbcac` | 15 | `0x400cc308` | PROJECT submenu: CHANGE/SAVE/RELOAD/SYNC TO CARD/SAVE TO NEW/EXPORT TO SET/CHANGE(set)/COLLECT SAMPLES/PURGE SAMPLES/SAVE CUR BANK/RELOAD CUR BANK, plus four separator rows whose labels are runs of glyph `0x17` |
| `0x400cbd1c` | 6 | `0x400cc4e8` | SYSTEM: USB DISK MODE, OS UPGRADE, DATE/TIME, PERSONALIZE, CARD TOOLS, STATUS |
| `0x400cbd54` | 6 | `0x400cc5a8` | CONTROL: AUDIO, INPUT, SEQUENCER, MIDI SEQUENCER, MEMORY, METRONOME |
| `0x400cbd70` | 4 | `0x400cc638` | MIDI: CONTROL, SYNC, CHANNELS, TURBO STATUS |

Root rows have a non-zero window descriptor at `+0x04` and a child pointer at
`+0x10` with action = 0; submenu leaf rows are the mirror image (window 0,
child 0, action or page id set). The four root window descriptors
(`0x400cbc34/48/5c/70`) are uniform 20-byte records
`{0x13, 0x09, 0x01, ptr, ptr}` — plausibly geometry plus two resource
pointers, uninterpreted (🟡).

## 3. Dispatch ✅

Two mechanisms coexist in the same field:

- **Real handler.** OS UPGRADE's action is `0x400636bc`, USB DISK MODE's is
  `0x40063728` — ordinary function pointers the firmware calls. This is what
  makes the table extensible: a new row can carry its own cave-resident
  handler.
- **Shared no-op + page id.** Every other leaf points at `0x400648f8`, which
  is a bare `rts` (bytes `4e 75`, read off the image), and is dispatched by
  the id at `+0x14` instead: DATE/TIME `0x0f`, PERSONALIZE `0x0c`, CARD
  TOOLS `0x0d`, STATUS `0x0e`; MIDI CONTROL/SYNC/CHANNELS/TURBO STATUS
  `0x08..0x0b`. ✅ **Traced (31 Aug 2026):** the consumer is the tree-state
  key handler at `0x40064e64` — on keycode `0x31` ([YES]/ENTER) it reads
  row+0x14 at `0x4006502c`; ids `1..15` (bounds-checked, `0x40065034`) open
  the matching entry of a **16-entry menu-state table at `0x400cbdac`,
  stride 0x14**: `{on_enter, on_exit, draw, key_handler, encoder_handler}`,
  state index in `DAT_400cbf40`. Cross-confirmed: state `0x0c`'s draw is
  `FUN_40068e00`, the known PERSONALIZE renderer. Id 0 falls through to
  calling the row's +0x08 action with one argument = 0 (`0x4006505a`).
  Two consequences: **all 15 usable states are occupied** (no free slot —
  live data follows the table), and every state is a screen *inside* the
  menu window, so **the id path cannot open a parameter page**. The action-fn
  path is the only extension point.

## 4. The draw/nav engine ✅ (the parts disassembled)

Engine body around `0x40064908..0x40064fb2` (🟡 boundaries — taken from the
xref cluster, not from function-boundary analysis). Confirmed with
`scripts/disasm.sh emac 0x40064940`:

```
4006495e:  addl 0x400cbd90,%d3        ; += root descriptor's scroll field
4006496a:  lsll #3,%d0                ; d3*8
4006496e:  lsll #5,%d2                ; d3*32
40064970:  subl %d0,%d2               ; d2 = d3*24  — row stride
4006497a:  movel %a0@(4,%d2:l),%sp@-  ; push row+0x04 (window descriptor)
40064982:  moveal 0x400cbda4,%a0      ; load the ROW ARRAY POINTER
40064988:  addal %d2,%a0              ; index the row
4006498a:  movel %a0@,%sp@-           ; push row+0x00 (label)
```

The root descriptor `0x400cbd8c` is referenced from eight code sites, all
inside this engine (`0x400649b8`, `0x40064c72`, `0x40064d22`, `0x40064e9a`,
`0x40064eaa`, `0x40064ef0`, `0x40064f40`, `0x40064f8e`) plus one data site,
`0x400cbda8` — the word immediately after the descriptor's own rows pointer
holds a pointer back to the descriptor. ✅ Resolved (31 Aug 2026): it is the
**focus pointer** — the "which list descriptor is the cursor in" cell the
nav engine reads and writes; it persists across menu close (the menu
remembers its position), which is stock behavior.

## 5. Why this matters: adding a fifth top-level entry is two writes ✅

**The root row array `0x400cc698` has exactly ONE reference in the whole
image: the rows pointer at `0x400cbda4`** (single 4-byte match for the value,
whole-image scan). The array cannot grow in place — live data follows it —
but it doesn't need to:

1. copy the four 24-byte rows into a cave, append a fifth,
2. repoint `0x400cbda4` at the copy,
3. bump the count at `0x400cbd8c` from 4 to 5.

The new row's label string and its action handler (or child list) live in the
same cave. Natural homes: the 1,024-byte `0xff` pad at `0x400c4702` (~5 KB
from these tables, free, unclaimed — `MIDI.md`) or the unclaimed zero run at
`0x400d24d0..0x400d2ce0`. The generic cave installer in `tools/build_bus.py`
already handles hook/cave verification for modules.

Hardware precedent: the PERSONALIZE menu was extended with two working items
in the archaeology era by exactly this relocate-and-repoint move
(`git show 40a1f19:tools/patch_menu.s`; `docs/history/NOTES.md` §PERSONALIZE).

## 6. What a new entry could actually *do* — the honest constraints

The menu shell is the cheap half. Feeding controls to the DSP is not, and
the viable designs all reuse the existing descriptor pipeline
(`PARAM_PAGES.md`, `MIDI.md`):

- **Shortcut into the host track's FX2 page.** The action handler selects
  the host track and restages the FX2 page through the firmware's own
  transition functions. Real dials, formatters, Part storage, scene
  locks — the host-track architecture stays as the data model; only the
  navigation jank goes away. ✅ **Traced end to end, 31 Aug 2026 — see §7**
  for the decoded open path, the handler, and the residual risks. (Still
  never executed: the Unicorn ColdFire harness was pruned, so a menu patch
  goes static-verify → flash until the remixer emu of `PLAN.md` §5
  exists.)
- **A bespoke PERSONALIZE-style list screen** whose setters call the stock
  parameter writer `FUN_40054cd8(track, flat, value)` for the host track, so
  values land in the Part and flow through the normal frame builder.
- **Not viable: independent controls outside the pipeline.** They could only
  reach the DSP via a ColdFire cave publishing into the r6 window, and after
  tempo-sync + MIDI there is one free 16-bit word left (`r6+$a`, `DSP.md`).

Also already ruled out elsewhere: the MIXER page as a control surface (it
does not use the generic renderer — `PARAM_PAGES.md`).

## 7. The FX2-page shortcut, traced end to end (31 Aug 2026)

Everything below is read from disassembly/decompilation (`objdump cfv4e` +
Ghidra 12 headless on `out/ghidra_fx`), none of it executed.

### How the firmware itself opens the FX2 page ✅

Keymaps are 26-byte records `{u8 code, 0, press, release, h3, aux, 0, u16
flags}` in two tables, `0x400bfbf6..` and `0x400c01f4..0x400c0840` — the
second carries codes `0x1c..0x1f` (`0x1c` = the dedicated MKII MAIN MENU
key, thunked to the menu opener `FUN_40064c18` via `0x40064d78`). **[FX2] is
keycode `0x26`**, one of five page keys `0x22..0x26` →
`FUN_4005578c(keycode, edge)`, mapped through the u32 table at `0x400a7280`
= `(0, 2, 1, 3, 4)` → page kind 4 = FX2 (matches the resolver's case
numbering).

A single press runs `FUN_400554e0(kind)`, which is the **entire page
switch**: it writes the current-page-kind global **`0x460d1684`** (long,
with a byte mirror at `0x46c7d8d8` written by the key handler), resolves the
descriptor via `FUN_40031ee0(-1,-1)` → `FUN_40031da4(track, kind)`, stages
it into four fixed working arrays with `FUN_400326d4`, and redraws
(`FUN_4004d948`). A double press instead reaches **`FUN_4005996c`** through
`PTR_FUN_400bc4a8` — the **EFFECT 2 SETUP window opener** (screen record
`0x400bc484`: window handle +0x08, title "EFFECT 2 SETUP" +0x10, open
+0x24, close `FUN_40056830` +0x28, draw `FUN_40037590` +0x2c). It takes no
arguments: it closes sibling setup windows, calls `FUN_400554e0(4)` itself,
creates the window (`FUN_4005829c`), and derives track and part from
globals. Called again while open, it toggles closed.

### The current-track global ✅ — and the shortcut must select the track

`FUN_40031ee0`: track −1 → `mvzb 0x80000000` — **the current audio track is
the byte at `0x80000000`**, with a UI mirror at `0x100b14cc`; and if
`0x80000012` ≠ 0 (MIDI mode) the track gets +8, resolving MIDI pages
instead. Staging for a track without selecting it is not viable: the screen
draw re-reads `0x100b14cc` directly and the encoder write path
(`FUN_40054cd8`) keys off the same globals. The committed selector is
**`FUN_40083bf8(track_index)`** — clamps, writes both globals, tears down
the old track, restages the current page kind, redraws, updates LEDs — and
it is already called from non-key UI code (`FUN_40061a94`), not only from
the track-key release path. Selecting the host track is also the honest UX:
the track LED moves, confirming where the knobs point.

### Exit safety ✅

Closing the menu from inside an action is tolerated by construction: the
code after both key-handler tails is gated on the menu window handle
`DAT_400cbf4c != 0`, and stock itself closes from handler context ([NO] in
`FUN_400650a0` → `FUN_40064bc0`). `FUN_40064bc0` is the full cleanup:
destroy window, unregister the input overlay (the dispatcher finishes list
surgery before calling handlers, so unlinking inside one is safe), reset
state, MENU LED off. After the shortcut the machine is in a 100% stock
configuration, so every subsequent exit gesture is stock. One hygiene item:
`DAT_400c0aac` (last page/track keycode for double-press detection, hold
counter `0x460d5de0`) keeps its pre-menu value; optionally write −1.

### The handler (~15 instructions, invoked as `action(0)`; only d0 live)

```
fx2_shortcut:
    tstl  0x80000012             ; MIDI mode? kind 4 would resolve track+8
    bnes  .out                   ; bail — menu just stays open
    moveq #4,d0
    movel d0,0x460d1684          ; current page kind = FX2 (long)
    moveb d0,0x46c7d8d8          ; page-kind byte mirror
    jsr   0x40064bc0             ; close MAIN MENU (full stock cleanup)
    pea   4                      ; track index 4 = displayed "T5"
    jsr   0x40083bf8             ; select track + restage FX2 + redraw
    addql #4,%sp
    jsr   0x4005996c             ; VARIANT B only: open EFFECT 2 SETUP
.out:
    rts
```

Variant A (no last `jsr`) lands on T5's FX2 knob page; variant B on the
EFFECT 2 SETUP window. The row hangs off the **CONTROL** submenu
(`0x400cbd54`) via the §5 relocate/bump/repoint move — avoid PROJECT and
SYSTEM, whose descriptor addresses are hard-compared at `0x40064fa0..c2`
for an alternate-list swap keyed on `0x80000088` (semantics unknown,
untouched by this design). The menu widget init reads the count from the
descriptor cell at open time, so a flash-time data edit is picked up.

### Residual risk, honestly priced 🟡

Confidence of surviving a first flash: **~75% variant A, ~65% variant B.**
The risk concentrates in two inferences, both with cheap pre-flash
falsifiers:

1. `FUN_40083bf8` from a menu action ≡ a track-key release — the
   `FUN_40043728(old_track)` teardown and the `DAT_8000004b` gate are
   undecoded. Falsifier: decompile `FUN_40043728`.
2. Menu-window destroy + setup-window create in ONE key dispatch is not a
   stock sequence (stock precedent covers each half separately). Falsifier
   on hardware: garbled/blank screen; mitigation: defer via the
   timer-callback idiom `FUN_40000c3c` that `FUN_40063660` uses.

Smaller: the MIDI-mode gate is inferred from the `+8`, never executed; the
`0x46c7d8d8` mirror's two readers (`FUN_4005a918`, `FUN_4005cbd8`) are
undecoded (cheap to close). Doing the two decompiles first should push
variant A toward ~85%.

## 8. Still undecoded

What remains of the renderer/input half after the §7 trace: the
window/geometry descriptor internals (the uniform `{0x13,0x09,0x01,ptr,ptr}`
records), the drawing primitives behind the state table's draw functions,
the `0x80000088` alternate-list semantics, `FUN_40043728` (old-track
teardown) and the two `0x46c7d8d8` readers — plus everything
`verify_menu.py`'s warning about the indirect widget-setup pointers
(`PTR_FUN_400bb7f0` etc.) covers. None of it blocks the two-write table
extension in §5 or the §7 shortcut; authoring a *new* screen of your own is
the part that still costs real decode work.
