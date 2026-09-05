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

## 4b. BUILT: `modules/menushortcut/` — CONTROL > REVERB / DELAY ✅ (3 Sep 2026)

**Two rows, emulator-walked, unflashed.** `modules/menushortcut/manifest.py`
copies CONTROL's six rows into a cave, appends REVERB and DELAY, repoints the
rows pointer at `0x400cbd6c` and bumps the count at `0x400cbd54` to 8 — the
§5 move, applied to CONTROL rather than the root for the reason §7 gives.
Both writes assert the stock bytes first.

The action (`menu_shortcut.s`, 92 bytes, assembled and pinned) is §7's
sketch with one change: **the track is not hardcoded.** It scans the eight
per-track FX2 id bytes at `0x80000ecc` for its server's id — 7 BusVerb,
6 BusDelay — and selects whichever track hosts it, so the row follows the
project rather than assuming T5. If that address is wrong the scan simply
never matches and the handler opens the current track's page: a wrong
screen, not a crash, which is why it scans rather than trusting.

⚠️ The cave is PINNED at `0x400d24d0`, the unclaimed 2,064-byte zero run §5
names, **not** in the clone/label region — the BamSep26 rig leaves 84 bytes
there and this cave is 300. `build_bus.py` allows a cave outside that window;
it still refuses one whose target is not free.

`tools/verify_menushortcut.py` (in `make check`) checks the table statically,
boots the image and walks the menu out of RAM with the firmware's own layout
— both rows resolve with their labels, id 0 (the action path) and actions in
the cave — and calls the REVERB action with MIDI mode set, where it must
return having touched nothing.

⬜ What no local test can reach: whether closing the menu from inside an
action and then selecting a track lands on the FX2 page. That is §7's ~65%
and the flash is the test.

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

## 9. The global edit screen: the four unknowns, measured (3 Sep 2026)

Sam's actual ask, once §4b landed: *"I missed that it would still be on the
track, that was the whole point"*. A shortcut removes the hunting; it does not
remove the coupling. What CAN move is where you edit from -- §6's bespoke list
screen, whose setters call the stock parameter writer for the host track. Four
things had to be known before that could be priced. Three are now known.

### 9a. Relocating the menu-state table ✅ EASY

`0x400cbdac` is named by exactly **three `lea` immediates** -- `0x40064bd2`,
`0x40064e34`, `0x400650e6`, all `lea 0x400cbdac,%aN` -- and by no pointer
cell. Extending it is therefore the same relocate-and-repoint move the build
already performs for the FX1 chooser list: copy 16 x 0x14 bytes to a cave,
append a 17th, patch three 4-byte operands.

Read out of booted RAM, the entries confirm the layout
`{on_enter, on_exit, draw, key_handler, encoder_handler}` and that **a NULL
member is skipped** (`tstl %a0 / beqs / jsr %a0@`), so an unused handler can
be left zero. State 0 is all zeros but is unreachable: id 0 is the action
path, which is why §3's "all 15 occupied" stands.

### 9b. Where the values live ✅ BOTH SOURCES LOCATED

- **The staged page**, which is what the panel draws:
  `0x46C7D244 + slot * 0x14` (`FUN_400326d4` builds it;
  `docs/midi_re_cc.md` already knew `0x46c7d244[2*slot+1] = 0x14` as the
  redraw marker). Only valid for the page currently staged -- so a global
  screen cannot read it without staging the page it is trying to avoid.
- **The Part**, which is what the writer commits to and therefore the
  authoritative store: `*(0x46c82456) + part * 6322 + 0x8EDA2 + track` is the
  per-track id byte (`0x100b14cf` is the current part), with the parameter
  bytes in the same record. A global screen reads and writes here.

### 9c. The `flat` index ✅ RESOLVED, and the answer constrains the screen (4 Sep 2026)

`FUN_40054cd8(track, flat, value)` splits `flat` by six into page and slot,
and the page goes to the same resolver the [FX2] key path uses. Read past
the early bail, the address arithmetic is explicit:

| | |
|---|---|
| page 0, `flat` 0–5 | `DB + part*6322 + 0x8edaa + track*30 + machine*6 + slot` — the PLAYBACK page, which varies by MACHINE TYPE, hence the extra term |
| pages 1–4, `flat` 6–29 | `DB + part*6322 + 0x8ee9a + track*24 + (flat − 6)` — one flat 24-byte block per track: AMP, LFO, FX1, **FX2** |

**FX2 page 1 is `flat` 24–29.** ✅ Derived from the code above and measured
independently on the booted machine: every write landed at `0x8ee9a +
track*24 + flat − 6`, checked at two tracks and a dozen indices.

**❌ FX2 PAGE 2 IS NOT REACHABLE THROUGH THIS FUNCTION, and neither is any
other page's.** The writer covers 30 values — five pages of six — and two
things in its own body cap it there:

- it clears a scene-lock bit with `1 << flat` in a **32-bit** word per track
  (`0x80000110 + (track + 1290)*4`), so `flat` ≥ 32 shifts out of the mask;
- it zeroes `0x80001658 + track*32 + flat`, a **32-entry** per-track array.

✅ **This agrees with something already measured from the other side.**
`docs/MIDI.md` records that page 2 is unreachable from CC and cannot be
scene-locked. Same 32-slot ceiling, found independently — which is the
cross-check that makes this worth relying on.

**What it means for the bus screens.** A screen built on the stock writer
edits an engine's **page-1 six knobs only**: BusVerb's TIME MOD SIZE HP LP
IN, BusDelay's TIME FDBK TONE PING →VRB PTCH. Page 2 — MODE, DIFF, SHFT,
GATE, RATE, and the delay's MDEP MODE MRAT SIZE DRV FRZE — needs a
different path: a direct Part write plus the working mirror at
`0x100a4f70`+, which is exactly the coupling the writer exists to hide, or
another firmware entry point nobody has found. That is the next question,
and it is a smaller one than the six-versus-twelve decision it forces:
**a twelve-row screen is not free, and a six-row screen leaves each engine's
mode select on a page nobody can reach.**

### 9c-ii. The PAGE-2 store, located ✅ (4 Sep 2026)

The stock page-1 writer stops at 30 values (9c). The panel edits page 2
every time you turn an encoder there, so a second path exists, and this is
it: the routine around **`0x4003a548..0x4003a5e8`**, reached from the FX
page's own edit path.

It is the mirror image of the page-1 writer, over a different array:

```
    a0 = DB + part*6322 + track*30 + slot + 0x8ef5a      ; the PAGE-2 array
    moveb  d2,(a0)                                        ; the value
    moveb  d2,(a1 + 0x100a50a8 + slot)                    ; the WORKING MIRROR
    or     1<<track, byte[DB + 0x95048]                   ; per-track dirty bit
    or     1<<track, byte[0x100b145e]                     ; the UI's own dirty bit
```

Three things worth having:

- ✅ **The page-2 array is `+0x8ef5a`, stride 30 per track**, which is the
  same stride the PROJECT FILE uses for page 2 (`tools/ot_project.py`,
  `P2_STRIDE`) — two independent decodings agreeing, after that stride cost
  a day of hardware time on 4 Sep.
- ✅ **It writes a working mirror too**, at `0x100a50a8`+, exactly as the
  page-1 writer writes its own at `0x100a4f70`+. A screen that pokes the
  Part and skips the mirror gets a value the panel shows and the frame
  builder never reads — the failure mode that is invisible locally.
- ✅ **It marks the part dirty**, twice: a per-track bit in the project DB
  and one in a UI byte at `0x100b145e`. That is what makes an edit survive
  a part save, and skipping it would lose every screen edit on reload.

**So a twelve-row screen is buildable on two firmware calls**, one per page,
and the second is a routine we can call the same way the panel does rather
than arithmetic we reimplement.

✅ **The entry point, traced (4 Sep 2026): `FUN_4003a474`.**

```c
void fx_page2_edit(int slot, int delta);      /* 4(sp), 8(sp) */
```

- **Two stack arguments.** The prologue is `lea -32(sp),sp` + `movem.l
  d2-d5/a2-a5,(sp)`, so the args sit at `sp@(36)` and `sp@(40)`: the first
  goes to `a3`, the second to `d3`.
- **`a3` is the SLOT, not an encoder position.** It is compared against
  **6** and branches to its own arm — and 6 is the first page-2 slot, which
  is exactly the boundary a page-2 editor would special-case.
- **`d3` is a DELTA, and this is a read-modify-write.** The body reads the
  current byte (`mvsb (a0),d2` off the `+0x8ef5a` array), adds `d3`, clamps
  against the descriptor's range, and stores. It does NOT take an absolute
  value the way the page-1 writer does.
- **Track and part come from GLOBALS, not arguments**: `0x80000000` (current
  audio track) and `0x80000003` (current part). §7 already established that
  a page edit keys off those globals rather than taking a track, which is
  why the FX2 shortcut has to SELECT the host track rather than aim at it.

**What this means for a twelve-row screen.** Page 1 is set absolutely
through the stock writer; page 2 is nudged relatively through this one. That
is not a problem — the screen can read the current value and pass the
difference — but it is a real difference in shape, and a screen that assumes
both calls take an absolute value would write page 2 to a value that drifts
by whatever was already there.

✅ **CALLED ON THE WARM MACHINE (4 Sep 2026), and it corrects one reading.**

```
    address = DB + part*6322 + 0x8ef5a + track*30 + page*6 + slot
```

measured by sweeping both arguments with the page global set by hand:

| what was checked | result |
|---|---|
| the address | page 4, slot 2, track 4 landed at `0x8efec` = `0x8ef5a + 120 + 24 + 2` ✅ |
| the page | pages 0–4 stepped the target by exactly 6 bytes each ✅ — **page 4 is FX2**, the same numbering the page-1 writer uses |
| the delta | a slot at 5 was reported taking `+3` to become **8** — ⚠️ **NOT REPRODUCED 4 Sep pm**: the delta does not re-apply on later emulator runs under any setup tried (staged page, page open, helper live) |
| the clamp | `+5` into pages 0 and 1 landed on **1**, not 5 — clamped to a two-value control's range, while pages 2–4 took the full 5 ✅ |

❌ **`a3` is NOT the absolute slot 0–11.** It is the slot WITHIN page 2,
0–5, and the general arm rejects anything above 5 outright (`moveq #5,d4;
cmp a3,d4; bcs exit`). The `a3 == 6` arm is real but is a different thing,
gated on `0x460d1a48 == 1`, and it is not the page-2 boundary the earlier
read took it for.

⚠️ **First reading (4 Sep 2026 am): ONLY THE KNOBS WRITE — slots 0, 2 and 4
moved a byte; 1, 3 and 5 did nothing.** That matched the page-2 map
`docs/PARAM_PAGES.md` records from the other direction and was taken to mean
the routine edits the three page-2 KNOBS and not the three SELECTS.

🟡 **CHALLENGED, same day pm (emulator, tag-84 image) — but only partly, and
here is exactly how far.** Driven again on a warm machine with its **page
global set** (`0x460d5c30` = FX2 kind), the `0x4003249c` spin-helper stubbed,
and the `0x100a0000` mirror mapped, `0x4003a474(slot, delta)` **runs to
completion for all six page-2 slots** on both engines and reads/writes the
per-slot byte at `+0x8ef5a + track*30 + page*6 + slot`. That much is solid.

⚠️ **What is NOT shown: that the delta is applied.** Seed that byte to any
value, call with delta ±1, and it comes back UNCHANGED — the routine reads
the current value (measured: it reads that same `+0x8ef5a` byte, at PC
`0x4003a560`) but the modify-and-store does not land a changed value from
this cold, un-staged context. So the pm run downgrades the am "only even
slots write" to "the reading is not trustworthy either way": neither
even-only nor all-six is demonstrated, because from outside a live FX2 page
the editor does not visibly edit. This is the CLAUDE.md blind spot — these
panel routines expect to be entered with the page staged, and the emulator
cannot stand in for that.

**Traced to the cause (4 Sep pm).** The delta is not stored directly: the
editor computes an increment via `0x4003249c` and adds it to the current
value (`d0 = 0x4003249c(slot,delta) + current`, at `0x4003a574`). That helper
reads the **staged page** `0x46c7d244` and loops on it. In the emulator it
either spins (staged page empty) or, with the page opened, returns an
increment of zero — so the value never changes. Staging the page, leaving it
open, and running the helper live were all tried; none moved a mid-range
knob, and the AM "5→8" could not be reproduced. So the dependency is **live
encoder/page-dispatcher state** (what `0x4003249c` reads while a page is
actively being edited), PLAN §5's RTOS "route A" — NOT a loaded project.
**Card emulation does not close this gap.**

✅ **RESOLVED ON HARDWARE (tags 85–90, 4 Sep 2026).** The screen was built
and flashed, and `0x4003a474` **edits all six page-2 slots** from a menu
state on the unit — knobs and selects, even and odd. The emulator's
zero-increment was the blind spot, not a property of the routine: the
"even slots only" am reading is retired.

⚠️ **The defect that WAS real: the editor's clamp is STALE.** It clamps a
turn against the descriptor it finds in its own page-kind table
(`0x400d5f38[page]`, read at `0x4003a524`), which is whatever page was
staged LAST. A menu-state screen never stages the FX2 page, so on the unit
that table pointed at some other effect: page-2 index 4 (GATE / DRV) was
squashed to 0..3 — Sam saw GATE become "a 3-way chooser" — and the selects
were ramped to 127, which the engines do not decode, so MODE looked stuck.
Its STORE addresses are computed from slot and track and were always right;
only the clamp consulted the wrong descriptor. **Fix (`modules/busscreen`):
call the editor for its stores, mirror and dirty bits, then set the value
yourself** — `clamp(before + delta, 0..count-1)`, count 128 for a knob or
the select's own — into the Part, the live byte `0x80000950 + slot2` the
DSP frame reads, and the working mirror `0x100a5138 + slot2`. Never trust
that clamp from outside a staged page.

**Where that leaves a twelve-row screen (revised 4 Sep 2026 pm).** The
target is and has always been TWELVE rows. Two firmware writers reach them:
`0x40054cd8(track, flat, value)` for page 1's six, and `0x4003a474(slot,
delta)` for page 2. The open question is only how many of page 2's six the
second routine reaches — the am reading said three (the even/knob slots), the
pm reading said all six. ✅ Settled on hardware: all six edit (tags 85–90). Twelve rows ARE built on
those two routines alone; the select path below and card emulation were not
needed. The probes are what this note retired, and the screen is what
answered the question they could not.

**The selects' path, part-way (4 Sep 2026).**

- ❌ **Not the `a3 == 6` arm.** Read: a repeat-by-delta loop that calls
  through the pointer at `0x4007ec7c` once per step, behind a
  `0x460d1a48 == 1` gate. A stepping action, not a parameter store.
- **The SELECT values have their own array and their own working mirror**,
  the same shape as the other two: `DB + part*6322 + 0x8f04a + ...` with the
  mirror at `0x100a5198 + ...`, found at the store `0x40027ebc` (`moveb
  d7,(a0)` into the array, then the same byte into the mirror). So there are
  three arrays and three mirrors, one per control kind: page-1 values,
  page-2 knobs, page-2 selects.
- 🟡 **The function that owns that store, `0x40027e4c`, is a bigger thing
  than the other two:** five stack arguments — a struct pointer, two values,
  a page kind 0–4 dispatched through a five-way jump table, and a fifth that
  must be zero — with a page-0 arm that reads the struct at offsets 18 and
  19, the pair a staging copy elsewhere fills from the page-1 and page-2
  arrays. A general commit path, not a two-argument setter.
- ✅ **THE CALLER, found (4 Sep 2026).** Not a pointer table at all: the
  address appears in NO data word in the image, and the two calls are
  **pc-relative**, at `0x40028f9a` and `0x40028fda` — which is why scanning
  for the immediate found nothing. The call site pushes:

  ```
      pea  0x460bf218        ; arg1: the context struct -- a FIXED GLOBAL
      move.l d5,-(sp)        ; arg2
      move.l d4,-(sp)        ; arg3   (the part; the body multiplies by 6322)
      move.l d3,-(sp)        ; arg4   (the page kind, 0-4, the jump table)
      move.l d2,-(sp)        ; arg5   (must be 0 for the main path)
      jsr    0x40027e4c
  ```

  **The struct is not built per call.** `0x460bf218` is a fixed global, so a
  screen can pass the same pointer the firmware does — which was the open
  question and is the reason this path looked harder than it is.

- ❌ **AND `0x40027e4c` IS NOT THE SELECT WRITER.** Read properly, it is a
  GENERIC EDIT APPLIER: `arg1` points at a struct carrying a TYPE TAG at
  `+0x8ed8` and a payload at `+18`/`+19`, and the five-way jump table is on
  the page kind. Its **kind-4 arm demands tag 29 and writes the payload to
  `DB + part*6322 + track + 0x8ed88` — the FX2 EFFECT ID byte**, mirroring
  it at `0x100a4ed6`. The `+0x8f04a` store that led here is in a DIFFERENT
  arm (kind 0, tag 26). So the array and mirror are real; the function is
  not a parameter setter.

- ✅ **Driven end to end on the warm machine (4 Sep 2026)**, which is what
  settles it: write 29 at `struct+0x8ed8` and an effect id at `struct+18`,
  call `(struct, 0, track, 4, 0)`, and **the track's FX2 effect id changed
  from `0x07` to `0x1c`.** The struct is a fixed global and its fields can
  simply be filled, so no card image was needed after all — the blocker was
  the tag, not an empty project.

  ⚠️ Its mirror write faults on an unmapped page in a bare emulator, as the
  parameter writers' do; that is the write happening, not failing.

- ✅ **The select's COMMITTER, found (4 Sep 2026): `0x40079424`.** Same
  shape as the page-2 knob editor — array, mirror, two dirty bits:

  ```
      a0 = DB + part*6322 + ... + 0x8f04a ; moveb d1,(a0)   ; the select array
      moveb d1,(0x100a5198 + ...)                            ; its mirror
      or 1<<track into the DB's per-track dirty byte
      or 1<<track into 0x100b145e                            ; the UI's dirty byte
  ```

  It takes its **value from `0x46c8d19c` and its slot from `0x46c8d1a0`**,
  globals rather than arguments. Its caller in the FX-page region
  (`0x4005a7d8`) reads the current select out of `+0x8f04a` first and
  compares before calling — a UI edit path, not a setter.

- ❌ **Setting those two globals and calling it writes nothing.** Tried on
  the warm machine: it bails on further UI state that has not been
  identified. That is the THIRD of these paths to depend on state rather
  than arguments, and the pattern is the point — **the panel's edit paths
  are written to be called by the panel.**

**The three arrays, for reference.** Each control kind has its own array and
its own working mirror:

| control kind | array | mirror |
|---|---|---|
| page-1 values | `+0x8ee9a` (track*24) | `0x100a4f70` |
| page-2 knobs | `+0x8ef5a` (track*30 + page*6) | `0x100a50a8` |
| page-2 selects | `+0x8f04a` (track*30 + page*6) | `0x100a5198` |

❌ **AND A SCREEN MUST NOT WRITE THEM ITSELF.** That was the plan for one
afternoon, on the reasoning that each committer was "an array, a mirror and
two dirty bits" — five stores a cave could make. **Traced with a write hook
rather than read, the page-2 knob editor makes NINE distinct non-stack
stores**, and the four that would have been missed are the ones that matter:

| store | what it is |
|---|---|
| `0x46c7d244 + slot*0x14`, two words | the **STAGED PAGE** — what the knob drawer reads. Skip it and the panel shows the old value |
| `0x80000952` | the value into the `0x8000xxxx` block, which is where the frame builder and the DSP side live. **Skip it and the edit never reaches the audio** |
| `DB + 0x9b332` | bookkeeping, unidentified |
| `0x100f8598` | bookkeeping, unidentified |

on top of the array, the mirror, and the two dirty bits. The page-1 writer
does **substantially more again** — its trace reaches UI redraw work and
even a UART register — so it is further still from anything worth
reimplementing.

✅ **So: call the firmware's routines, do not reproduce them.** Two of the
three are callable today, with signatures confirmed by driving them:
`0x40054cd8(track, flat, value)` for page 1 and `0x4003a474(slot, delta)`
for page-2 knobs. Hand-rolling any of them is now known to be unsafe rather
than merely untidy.

✅ **The select committer, driven (4 Sep 2026).** `0x40079424` reads two
globals at entry — `0x46c8d19c` (a value) and `0x46c8d1a0` — and **branches
on the second**: nonzero takes an arm needing state we have not mapped,
**zero takes the arm that stores.** With it zero the routine runs to
completion, through the redraw calls at its tail, and writes:

```
    DB + 0x8f04a      the select array        <- the value
    DB + 0x8eda2      machine type
    DB + 0x95048      the per-track dirty bit
    DB + 0x9b332      the bookkeeping word the page-2 knob editor also writes
```

So it is callable, and it does the FULL job rather than a partial one —
which, after the enumeration above, is the property that matters.

⚠️ **What is not yet controllable is WHICH control it targets.** The store
landed at `+0x8f04a` exactly — offset zero, so track 0, page 0, slot 0 —
because in that arm the address term comes from the same global that has to
be zero to reach the store at all. It writes, and writes correctly, but the
inputs that aim it are unidentified. Its caller (`0x4005a7d8`, the FX-page
region) sets more state than those two globals before calling, and that is
where they will be.

**The front door that sets those globals, found (4 Sep 2026):
`0x4006de34(kind, value)`.** It stashes `kind` into `0x46c8d1a0` and `value`
into `0x46c8d19c` — the committer's two inputs — then dispatches on
`kind == 4`. So the aiming API has the shape we wanted.

✅ **AND THE EDIT IS TWO-PHASE — STAGE, THEN COMMIT (4 Sep 2026).** That is
why single calls wrote nothing. `0x46c8d1a0` is a PHASE selector, not a
slot:

| its value | what the call does |
|---|---|
| 1 or 4 | **stages**: bounds `0x46c8d19c` at 135, indexes a 1096-byte-stride table at `0x100b14f0`, and writes the pending edit into `0x460be9e8`/`0x460be9ec`. Track and part come from the UI globals `0x100b14cc` and `0x100b14cf` |
| 0 | **commits**: writes the select array, the machine byte, the dirty bit and the bookkeeping word, then redraws |

**Driven end to end:** stage with `0x46c8d1a0 = 4` and an index in
`0x46c8d19c`, then call again with `0x46c8d1a0 = 0` and the VALUE in
`0x46c8d19c`, and **the select array takes the value**. Two calls to one
entry point, no arguments, everything through globals.

⚠️ **The offset still lands at zero.** The value went to `+0x8f04a` exactly,
not to the staged track's block, so something the staging phase is meant to
leave behind is not surviving into the commit on a machine with no project
loaded — the commit's address term reads state the staging phase populates.
Both phases now run and the array is written, which is further than this
had got; what is not yet controlled is WHICH byte.

⚠️ **THE PATTERN IS NOW THE FINDING, across five routines.** Every panel
edit path here — the page-1 writer, the page-2 knob editor, the select
committer, the edit applier, and this setter — is layered UI code that
expects to be entered from the key and encoder dispatcher with a live page
open. Two of them happen to take enough as arguments to be driven from
outside. The rest do not, and each one costs a session to find that out.
Driving them piecemeal from a cave is working against how they are written.

**So the honest options for the bus screens are three, and the choice is a
design one rather than a research one:**

1. ~~**A NINE-ROW screen**~~ — SUPERSEDED 4 Sep 2026. This was written when
   (a) MODE was on an odd slot and (b) the page-2 editor was read as
   even-slots-only. Both changed the same day: MODE moved to slot 6 (an even
   slot, HARDWARE-CONFIRMED on tag 84), and the emulator then showed
   `0x4003a474` writing all six page-2 slots. The goal is TWELVE rows; nine
   was an artifact of those two facts (one now stale, one now in doubt), not
   a decision. See the revised "where that leaves a twelve-row screen" above.
2. **Keep digging for the select aiming.** Narrow, but this thread has cost
   five reads and each answer has produced another layer.
3. **Use the shortcut that is already built.** `modules/menushortcut`
   already puts REVERB and DELAY in the main menu and opens the host track's
   FX2 page, which gives ALL TWELVE controls with no new reverse
   engineering at all. What it does not give is a blank host page — the
   controls are on the track, reached from the menu, rather than off it.

Option 3 is the original §6 shortcut design, and it is worth re-reading
before spending more on 2: the goal that grew into "a screen" started as
"reachable without hunting", which the shortcut already does.

⚠️ **The lesson is the method, not the addresses.** Four of the nine stores
were invisible to reading and obvious to a write hook, and one of them is
the path to the DSP. Any future claim of the form "this routine just writes
X" should be traced before it is believed.

- ✅ **Worth having on its own:** an entry point that sets a track's FX2
  effect id from a struct, verified locally, is exactly what a screen that
  CHOOSES an effect would call — the thing `Remix.hidden` currently does by
  taking the chooser away.
**The shape of the problem, stated once — and then RETRACTED (4 Sep 2026).**
This said: page 2 alternates knob, select, knob, select, the panel's own
layout, so every effect has exactly three selects on 7/9/11 and no knob map
avoids them. **False.** The stock descriptors put CHORUS TAPS (5-way) on
slot 6, FILTER's HP/ENV/Q2 on 6/8/10, and 128-value knobs on 9 and 11. The
alternation was our schema's rule. The field a slot is delivered in is fixed
(even → bits 16–23, odd → bits 8–15); count and renderer are free.

✅ **RESOLVED by moving MODE to slot 6 in both bus engines** (same day). Slot
6 is written by the page-2 knob editor `0x4003a474(slot, delta)`, which is
driven and clamps to the descriptor's count — so MODE now sits on a path
that is callable and aimed, and the select committer, its two-phase
staging and the array formula are no longer needed for the screen. Option 1
above becomes a nine-row screen WITH MODE: page 1's six through
`0x40054cd8`, and slots 6/8/10 (MODE, DIFF, GATE / MODE, MRAT, DRV)
through `0x4003a474`. Off the screen: the odd slots (SHMR, SHFT, RATE /
MDEP, SIZE, FRZE), still on the track page. Proven locally: all six
engine-modes render bit-identically through the new fields. ✅ **Confirmed
on hardware, tag 84, the same day:** MODE draws and steps as a select on
slot 6; SHMR / MDEP sweep smoothly from slot 7. (The first play stalled the
sequencer on a project saved under the old layout — `docs/FLASHPLAN.md`.)

**The SELECT PROBE line is closed.** Four builds (80–83) and no signal on
the fourth either: after the re-slot nothing depends on the select array
formula, so it is not worth a fifth. The unresolved ambiguity is recorded
here rather than chased: either the panel commits a select turn to the Part
array later than the turn (staged page and live byte first), or the probe's
UI track/part globals (`0x100b14cc/cf`) are not the ones the writer keys on
(`0x80000000/03`). A zero-flash discriminator exists on image 83 — turn
MODE, SAVE the part, re-read — if anyone ever needs it.

**Card emulation** (a project loaded in the emulator) is what would have
made the select path researchable without flashes; it is parked in
`PLAN.md` as the next emulator milestone, for the next project-dependent
path, not for this one.

### 9e. The twelve-row bus screen — SHIPPED (4 Sep 2026, `modules/busscreen`, tags 85–90)

✅ **Built, emulator-proven, and walked on the unit across six flashes.**
`modules/busscreen` (remix `busscreen` = `bus` + this; `tools/verify_busscreen.py`
in `make check`) grows the menu-state table to a 17th state and fills its
draw / key / encoder members. As shipped on tag 90:

- **Two CONTROL rows, REVERB and DELAY.** Each scans the per-track FX2 ids
  at `0x80000ecc` for its engine (7 / 6), selects that track (`0x80000000`),
  and opens the screen — so you edit the reverb or the delay from anywhere.
  The label set follows the selected track's id.
- **Double-wide: all twelve at once.** Two columns of six (left slots 0–5,
  right 6–11), name + value, on the stock 7px row pitch. No scroll, no page.
- **Stock look.** The cursor row is the same inverted bar the stock lists
  draw, via the firmware's own rect-invert `0x40012254(window,x1,y1,x2,y2,-1)`
  after the row's text.
- **Selects read as words** (MODE ROOM/PLATE/BIG or CLEAN/GRAIN/REVRS, SHFT,
  RATE, SIZE, FRZE), knobs as numbers — per-engine label records in the cave.
- **Keys:** `0x34` (the UP arrow) moves up, `0x33` moves down — the key under
  Sam's thumb as "left" is what goes down on this unit, kept per his call;
  `0x32/0x35/0x36` also accepted as down. Cursor WRAPS 0 ↔ 11.
- **Edits:** page 1 through the self-contained `0x40054cd8(track, 24+slot,
  value)`; page 2 through `0x4003a474` for its stores, then the screen sets
  the count-clamped value itself (the stale-clamp finding, §9c-ii). Every
  one of the 24 slot/engine pairs proven on the harness to draw and edit as
  its type, and confirmed on the unit.

- **A 13th row, the bus's RETURN level, is BUILT but DEFERRED (4 Sep pm).**
  When T8's FX1 is the Character station, each screen would grow a row 6:
  RVRB = T8 CRSH (page-1 slot 2, the page-1 writer on track 7, flat 20);
  DLY = T8 RING (page-2 index 2, the editor on (track 7, page 3) then the
  value set into Part `+0x8f040`, live `0x80000a2a`, mirror `0x100a518e`).
  The handler carries it (NSLOT = 13 only when T8's FX1 id is `0x1c`), but it
  is only reached from a rig that hosts the screen AND the Character master —
  and the screen is not in a rig yet (below). The code stays dormant.

- ❌ **The pin at `0x40108800` was a CRASH, retracted 4 Sep pm.** That
  address is inside the OS image's last ~30 KB — a zero run at rest that is
  really OS `.bss` (the PROJECT subsystem's RAM). It passed a static
  zero-check and a no-project emulator boot, then faulted the instant you hit
  [PROJ] on tag 91. The lesson: a zero run inside the loaded image is not
  free space. `build_bus`'s `SAFE_CAVE_CEIL` (0x400d8000) now refuses any
  cave above the decoded free band.

The cave FLOATS in the decoded free band (`0x400d2000..0x400d8000`), where
tags 85–90 ran it safely. Draw and edit read/write the SAME Part arrays
(`0x8ee9a` page 1, `0x8ef5a` page 2) keyed by the `0x80000000/03` track/part
pair, so an edit is visible by construction.

⬜ **The screen is NOT in a rig yet.** `bamsep27`'s clones and label
formatters fill the safe band, so the 2,296-byte cave does not fit there, and
the image tail is off limits. Screen-in-rig waits on a split cave or a
trimmed rig; `bamsep27` keeps MENU SHORTCUT meanwhile. The plain `busscreen`
remix carries the full screen.

⚠️ **`busscreen` SUPERSEDES `menushortcut` and the two cannot coexist**: both
grow the CONTROL submenu (relocate its rows, bump its count), and the build
refuses the second because CONTROL's count is no longer stock. The screen's
REVERB/DELAY rows do everything the shortcut's did and more.

The original plan (kept below for provenance):

#### Original plan (4 Sep 2026)


The goal is a MAIN MENU screen that edits ALL TWELVE controls of BusVerb and
BusDelay, off the track. `modules/menushortcut` already reaches the twelve
controls ON the track (it opens the host's FX2 page); this replaces "on the
track" with "a screen of its own". What made that the swamp §6 declined was
the select-committer's unmapped aiming state — and the MODE re-slot plus the
pm re-reading of `0x4003a474` together remove it, IF the all-six reading
holds. So the screen is now the cheapest way to settle that too.

**The pieces, known vs open:**

1. ✅ **Relocate the menu-state table (§9a).** Copy 16 × 0x14 from
   `0x400cbdac` to a cave, append a 17th entry, patch the three `lea`
   immediates (`0x40064bd2/e34`, `0x400650e6`). Same relocate-and-repoint the
   FX1 chooser build already does. A NULL handler member is skipped, so an
   unused one is left zero.
2. ✅ **Add the row to CONTROL (or the root).** `menushortcut` already does
   exactly this for its two action rows; the screen is one more row whose
   action enters the new menu-state instead of opening the FX2 page.
⚠️ **The DRAW side is locally verifiable; the EDIT side is not.** The draw
handler (piece 3) renders in the emulator and can be walked with no flash.
The encoder handler (piece 4) calls `0x4003a474`, whose delta comes from
`0x4003249c` reading live page-dispatcher state the emulator does not supply
(traced 4 Sep pm, above) — staging the page did not help, and a loaded
project would not either, so **card emulation is not the lever here**. The
edit side is a flash question (or an RTOS "route A" build, PLAN §5). Build the
draw side and the plumbing locally; let the flash settle whether turning a
row moves the value.

3. 🟡 **The draw handler.** Render twelve labelled rows with live values. The
   pieces are decoded — window ctor `FUN_4005829c`, list drawer
   `FUN_40037590`, sprintf `0x40013a08`, and the value source is the Part
   arrays (`+0x8ee9a` page 1, `+0x8ef5a` page 2) for the host track. Novel
   code, but every primitive it calls is already used elsewhere.
4. 🟡 **The encoder handler.** On a turn of the selected row, call the writer
   for that slot: `0x40054cd8(track, flat, value)` for rows 0–5,
   `0x4003a474(slot, delta)` for rows 6–11. Its ABI is §9d, SHAPE ONLY — two
   stack args, index vs delta unsettled. **This is the first thing to settle,
   and it is a local read, no flash:** disassemble the two stock encoder
   handlers (`0x400658f0`, `0x40065c98`) far enough to fix the argument
   order, then confirm in the emulator by driving one.
5. ⬜ **Which track the screen edits.** Reuse `menushortcut`'s scan of the
   per-track FX2 id bytes so the screen follows the project rather than
   assuming T5, or make the screen itself track-agnostic and edit whichever
   track is current.

**Order of work:** (4) first — settling the encoder ABI is the gate and costs
no flash. Then (1)+(2) under the emulator's menu walk (a cave that breaks
early init faults in the emulator, not on the unit). Then (3), drawing the
real values. One flash carries the lot, and that flash is also the odd-slot
test from §9c-ii: if rows 6–11 all edit on the unit, the pm reading was
right and the screen is done; if only the even ones move, the three odd rows
fall back to the select path and card emulation.

**What NOT to do:** hand-roll any of the three parameter writers into the
cave. §9c-ii enumerated why — the page-2 knob editor alone makes nine
distinct stores, four of them invisible to a read hook and one the path to
the DSP. Call the firmware's routines.

### 9d. The encoder handler's ABI ✅ SETTLED (4 Sep 2026)

`encoder_handler(index, delta)` — two longs, cdecl. Both stock handlers
(states 3 and 4, `0x400658f0` and `0x40065c98`) are **byte-identical** in the
prologue, disassembled with objdump cfv4e (`scripts/disasm.sh emac`, the tool
that decodes this CPU; the earlier "unsettled" read was before this pass):

```
    movel %a2,%sp@-        ; save
    movel %d2,%sp@-
    moveal %sp@(12),%a2    ; arg1 -> a2   THE INDEX
    movel  %sp@(16),%d2    ; arg2 -> d2   THE DELTA
    pea    %a2@(56)        ; predicate keyed by the index
    jsr    0x4003171c
    tstl %d0 / beqs ...    ; if it returns nonzero:
    movel %d2,%d0 / lsll #3,%d0 / subl %d2,%d0 / movel %d0,%d2   ; d2 = delta*7
    moveq #6,%d0 / cmpl %a2,%d0 / bnes ...                       ; index==6 arm
```

- **arg1 is the INDEX.** It is compared against the small integer 6 and
  dispatched, so it holds a small int, not a pointer. (`pea %a2@(56)` passes
  `index+56` to a predicate `0x4003171c` — an enum arg, not a dereference;
  that is what the old reading mistook for a pointer base.)
- **arg2 is the DELTA, and it arrives RAW.** The `delta*7` is the handler's
  own fast-turn acceleration, applied only when `0x4003171c` returns nonzero
  — so a screen handler receives the plain encoder step and is free to ignore
  the acceleration. Perfect for feeding `0x4003a474(slot, delta)`, which is
  itself a read-modify-write by delta.

**The m68k toolchain is on PATH here** (`m68k-elf-as`, used by `build_bus.py`
for every cave), so a screen's draw and encoder handlers can be assembled and
walked in the emulator with no flash — the §9e order stands, and step 4 is
now done.


### 9e-i. Correction, 5 Sep 2026 — the page-2 store the screen reads/writes

The screen read and overwrote the page-2 Part byte at
`DB+part*6322+0x8ef5a+track*30+18+slot` (= `+24+slot2`), staging
`PAGEGLOB = 4` for `0x4003a474`. That is the wrong slot. The FX2 page really
stages **index 0**, so the store is `+0+slot2` — measured on hardware by
`modules/ccpage2` (tag 12 wrote the staged index into GATE and the dial sat at
zero; tag 13 pinned `+0` and works with the page off screen;
`docs/midi_re_cc.md` §7). The screen was self-consistent (draw and edit both
`+24`) so it drew correctly, and its edits DID change the sound, because
`0x4003a474`'s live-lane write (`0x80000830+track*72+slot2`) carries the
value to the DSP regardless of where the Part byte lands — but the stored
bytes would not survive a part reload. Fixed in commit 2fcdca3 (`+0`,
`PAGEGLOB 0`, track-4 shadow `0x100a5120`); `verify_busscreen` green;
**unflashed**. The T8-FX1 return row (`0x8f040`, `PAGEGLOB 3`) is left as it
was: its staged index has not been measured.

### 9e-ii. In the rig at last: three caves (5 Sep 2026)

The screen never fitted `bamsep27` as one 2.3 KB floating cave: floats round
up to 0x80 in the clone window, which had 16 B to spare, and the second zero
run (2064 B) is too small for the whole. It now ships as three pieces:

| piece | size | where |
|---|---|---|
| 17-entry menu-state table | 340 B | floats in the clone window -- BUS SCREEN is listed before TEMPO SYNC so it is placed first (`0x400d7500` on the rig) |
| draw/key/enc handler | 994 B | pinned at `0x400d24d0`, the start of the second zero run, where MENU SHORTCUT used to sit (the screen supersedes it) |
| names, select words, scratch, CONTROL rows | 748 B | pinned at `0x400d28b4`, right after the handler |

Every cross-reference is a constant once the last two are pinned, so each
`emit()` needs only its own address (`modules/busscreen/manifest.py`). Two
other changes made the room: a BLANKED module gets no label formatters and
no TIME formatter (`build_bus.py`, ~800 B on the rig, `docs/MODULES.md`),
and the dormant 13th return-row editor (T8 Character's RVRB/DLY at the
master) was stripped from `screen_draw.s` (1206 -> 994 B; NSLOT is 12;
history: `git show 44aa987:modules/busscreen/screen_draw.s`). The rig build
leaves 10 B in the clone window and 320 B in the run; one station formatter
spills into the run. `verify_busscreen` checks the 17th entry against the
pinned handler's exact addresses. **Unflashed** at the time of writing.
