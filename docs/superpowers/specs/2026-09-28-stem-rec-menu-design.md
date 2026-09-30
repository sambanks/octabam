# STEM REC: the STEMS category in MAIN MENU

Piece 3 of the roadmap in
`docs/superpowers/specs/2026-09-26-stem-rec-upstream-port-design.md`,
section 0. Piece 2, eight tracks under the emulator, is on branch
`stem-rec-p2-up`, merged with upstream `main` at `f331c30`. This piece
branches from it (`stem-rec-p3`).

## 1. Purpose

Give STEM REC a menu, so a take can be started, watched, and shaped from
the unit before the first flash (piece 4). The roadmap asks for:

- REC and STOP;
- T1 to T8, each on or off;
- a status row: the elapsed time, the peak ring fill, and any error by
  name;
- 16-bit only;
- checked on the emulator's MKII and MKI panels;
- a gate: the cursor reaches every category, and SYSTEM reaches OS
  UPGRADE, because MAIN MENU is also the recovery screen.

## 2. Decisions (Yves, 28 Sep 2026)

| Question | Decision |
|---|---|
| Keep MAIN MENU › CONTROL › STEM REC beside the new category? | No. The category replaces it, and CONTROL goes back to its six stock rows. One place starts a take, and the CONTROL-row failure of tag 16 (`FAILURE_MODES.md`, cause unknown) stays out of the way. |
| Can a track be turned on or off during a take? | No. The track rows are locked while a take records or saves. They work while stopped or armed, since the track set isn't fixed until recording starts. What the screen shows is always what's recording. |
| The category's name | `STEMS`: seven characters, like the longest stock name. |
| How it's built | A category made of data, whose row labels STEM REC rewrites in memory (section 4). A screen of its own is left for piece 7; a pop-up list can't redraw by itself. |
| After a take ends | Back to READY: one take per REC, as today. The next PLAY doesn't record unless REC is pressed again. Staying armed would need seconds in the folder name first. |
| The cursor stopped on PEAK: the engine skips one row without an action, not two in a row (measured 29 Sep 2026) | PEAK moves to the bottom, the last row. The cursor never moves onto a last row without an action (measured), so it stays a plain row and can't be pressed. |
| The menu doesn't redraw by itself (measured 29 Sep 2026, `STEM_REC.md` 16.1) | The status refreshes on any key: opening the menu, or a key inside it, shows it current. The labels the actions change show at once, since a key press redraws the menu. A status that ticks by itself is left for piece 7. |

## 3. What you see

**Opening it.** MAIN MENU opens as usual: the MAIN MENU key on the MKII,
FUNC+MIXER on the MKI. `STEMS` is a fifth category, under MIDI, with its
own icon: a record dot.

**The rows, top to bottom.** The pane shows seven rows at a time and
scrolls.

| Row | Shows | ENTER |
|---|---|---|
| 1 | What pressing does: `REC`; `CANCEL` while armed; `STOP` while recording; `SAVING` while the files are finished | Arms, cancels, or stops the take. Nothing while saving |
| 2 | The status: `READY`, `ARMED`, `REC 01:23`, `SAVING`, `DONE 12:34`, `NO CARD`, or an error by name | None: the cursor skips the row |
| 3-10 | `T1 [X]` to `T8 [X]` | Turns the track on or off. Ignored while recording or saving |
| 11 | `PEAK 12%`: the take's largest ring fill, reset when a take is armed, kept after it | None: the last row, which the cursor never reaches |

The two rows without an action are never next to each other: the menu
engine skips one such row but not two in a row, and never moves onto a
last one (measured, `STEM_REC.md` 16.1). PEAK was row 3 until the gate
found the cursor stopping on it; Yves moved it to the bottom (29 Sep 2026).

**The recorder, as today** (`modules/stems/README.md`):

- REC while the sequencer is stopped arms the take, and recording starts
  on the first frame it plays. REC while it plays starts recording on the
  next frame.
- The take stops when the sequencer stops, when STOP is pressed, after 60
  minutes, or when the ring fills.
- Then the writer finishes the files, and STEM REC is READY again.

**The status texts.**

| State | Status | Row 1 |
|---|---|---|
| Idle, before any take, or after CANCEL | `READY` | `REC` |
| Armed | `ARMED` | `CANCEL` |
| Recording | `REC mm:ss`, the take's length so far | `STOP` |
| Saving | `SAVING` | `SAVING` |
| Idle, after a take with no error | `DONE mm:ss`, the take's length | `REC` |
| Idle, after a take with an error | the error's name | `REC` |
| REC pressed with no card | `NO CARD` | `REC` |

**The errors by name**, one per code in `modules/stems/stems.s`:

| Code | Name | Meaning |
|---|---|---|
| `ERR_OVERFLOW` | `RING FULL` | The card fell behind. The take stopped at the last whole frame, and its files still play |
| `ERR_EXISTS` | `SAME MINUTE` | A take already exists for this minute. The first stays intact |
| `ERR_WRITE` | `WRITE FAILED` | The card refused a write |
| `ERR_OPEN` | `OPEN FAILED` | A track's file couldn't be opened |
| `ERR_PATH` | `PATH FAILED` | The take's folder path couldn't be built |
| `ERR_SEEK` | `SEEK FAILED` | A file's header couldn't be written back |
| `ERR_CLOSE` | `CLOSE FAILED` | A file couldn't be closed |
| `ERR_TASK` | `TASK FAILED` | The writer task couldn't be created |

**Width.** The first task of the plan measures, under the port, how many
characters fit in the category column and in the row pane. The port draws
with the firmware's own font, so the measurement is exact. Any text that
doesn't fit takes a shorter form, fixed in the plan: for example
`SAME MIN`, `WRITE FAIL`.

**Other rules.**

- Closing the menu doesn't stop a take; reopening it shows the status as
  it is then. While the menu stays open, the status is as of the last key
  (section 2).
- Nothing is saved: every boot starts with all eight tracks on and READY.
- A card that hangs on a write freezes the status timer. The stock card
  driver has no timeout, and recovery is a power cycle, as today
  (`STEM_REC.md` 11.4).

## 4. How it's built

All in the `stems` module: `modules/stems/stems.s` and
`modules/stems/manifest.py`. No new module.

**The category.** `docs/firmware/MAINMENU.md` sections 1, 2 and 5, and
octalab's `docs/MENU.md` (a fifth category, run on a MKI, 7 Sep 2026):

- The manifest drops its CONTROL `TableGrow` and its CONTROL count `Poke`.
- A `TableGrow` copies the four stock root rows (`0x400cc698`) from the
  user's image and appends the STEMS row: its label, its icon's window
  descriptor, action 0, no value getter, its list descriptor as the child,
  page id 0. It repoints the root's rows pointer (`0x400cbda4`).
- A `Poke` changes the root's count at `0x400cbd8c` from 4 to 5. The
  boot's descriptor set-up passes that count field, not a constant, so the
  root's visible count and count follow it (octalab).
- The ledger then refuses any second module that grows the root, by name,
  as it does for CONTROL today.

**In the runtime**, STEM REC's DRAM unit, which is writable:

- **The list descriptor** (0x1c bytes), shipped filled in, because the
  boot's set-up run covers only the stock descriptors: count 11, scroll 0,
  cursor 0, selection 0, visible 7, count 11, the rows pointer.
- **Eleven rows** (0x18 bytes each). Rows 1 and 3-10 carry an action and
  page id 0, so ENTER calls the action with one argument, 0. Rows 2 and 11
  carry action 0: headings the cursor never lands on.
- **The icon**: a window descriptor `{0x13, 0x09, 0x01, plane0, plane1}`,
  19 by 9 pixels, `plane1` the stock constant `0xff80` words.
- **The label strings.**

**Changing a label.** A row's label is a pointer. Every change writes the
new text somewhere the row isn't pointing, then switches the pointer with
one aligned long write. The draw sees a whole old label or a whole new one.

- Row 1, the track rows, and every status text without a number point at
  fixed strings (`REC`, `STOP`, `T3 [X]`, `T3 [ ]`, `READY`, `ARMED`,
  `NO CARD`, `PEAK 0%`, the error names), so their change is the pointer
  write alone.
- The texts with numbers (`REC mm:ss`, `DONE mm:ss`, `PEAK n%`) are
  formatted only by the writer task, with the stock `sprintf`
  (`0x40013a08`), into one of two buffers per line, the one not showing,
  and the pointer then switches.

**Who writes which label.**

- **The actions**, in the UI task, update their own rows at once, with
  fixed strings only:
  - REC runs today's `stems_action` (arm, cancel, stop), then sets row 1
    and the status from the new state (arming also sets `PEAK 0%`). No
    card: the status reads `NO CARD`. No task: `TASK FAILED`.
  - A track row finds its track from the descriptor's absolute selection
    (`+0x0c`, minus 3), as octalab's checkbox rows do. While recording or
    saving it returns. Otherwise it flips that bit of `stems_tracks` and
    switches the row's label.
- **The writer task** (every pass, about every 10 ms) compares the state,
  the error, the take's whole seconds, and its PEAK percent with what it
  last showed, and rewrites a line only when one changed. That covers the
  changes the sequencer makes: the take starting on PLAY and stopping on
  STOP. The task derives every text from the state, so if it's
  interrupted between reading the state and switching a pointer, and an
  action changes the state meanwhile, its next pass sees the change and
  corrects the line within about 10 ms. `NO CARD` and `TASK FAILED`
  change no state, so the task leaves them showing.
- **The frame hook** writes the state only, as today. It never formats a
  label, so the audio interrupt costs nothing more.
- **Before the first REC** the task doesn't exist (it's created by the
  first press, as today), so the image ships `READY` and `PEAK 0%`.

**The numbers.**

- Seconds: recorded frames × 16 / 44,100 (a frame is 16 samples), shown
  as `mm:ss`, at most `60:00`.
- PEAK: `stems_peak` × 100 / `stems_rframes`, the ring's capacity for the
  take's track count; 0 while `stems_rframes` is 0 (before any take).

**Cost.** The frame hook doesn't change. The task formats at most two
lines when something shown has changed, about once a second while
recording. Memory: a few hundred bytes of the runtime.

**Test seams kept.** The verifiers still call `stems_action` before play,
and poke `stems_tracks`. Both stay where they are.

## 5. The checks

**`tools/verify/verify_stems.py`** (STEM REC's existing gate):

- The static checks move from CONTROL to the root:
  - the root count is 5, and the four stock rows are byte for byte the
    user's image;
  - row 5 points at the STEMS label, the icon, and the list descriptor;
  - the list descriptor ships filled in: count 11, visible 7, the rows;
  - CONTROL is stock: count 6, its stock rows pointer;
  - rows 2 and 11 have action 0; the others have their actions.
- The take runs stay, and check the labels, read from the runtime's memory:
  - during a take the status reads `REC mm:ss`, and the seconds rise;
  - after it, `DONE mm:ss` with the take's length, and row 1 reads `REC`;
  - the overflow run ends on `RING FULL`;
  - the second take in the same minute ends on `SAME MINUTE`;
  - REC with the card-mounted word (`0x460d1cb8`) poked to 0 shows
    `NO CARD`, and the state stays READY;
  - PEAK equals `stems_peak` over the ring's capacity.

**A new gate, `tools/verify/verify_stems_menu.py`**, declared in the
manifest (per remix). It drives the port through `ot_emu --interactive`
(the protocol `make panel` uses: `run <ms>`, `key`, `peek`), so emulated
time advances in exact steps, and reads the screen from the panel link
(`tools/panel/panel_link.py`). One boot as an MKII (`--mkii`) and one as an
MKI, each on the one-track fixture card:

1. MAIN MENU opens (the MAIN MENU key; FUNC+MIXER on the MKI). The cursor
   steps through all five categories, and the root descriptor's selection
   reads each one.
2. **The recovery check:** SYSTEM opens and the cursor reaches OS UPGRADE.
   ENTER is never pressed there.
3. In STEMS the cursor starts on REC, skips row 2 both ways, reaches T1
   to T8, and stays on T8: it never lands on row 11.
4. T3 off: bit 2 of `stems_tracks` clears and the row reads `T3 [ ]`. On
   again: both restored.
5. REC while stopped: ARMED, row 1 `CANCEL`. REC again: READY. Then REC,
   PLAY and STOP make a take: `STOP` and `REC 00:0x` while it records; a
   T3 press changes nothing; then `SAVING`, `DONE`, and the files on the
   card.
6. Every string the module can show fits the widths measured in the plan's
   first task.

The gate saves a PNG of the screen at every step into `out/stems_runs/`,
for a person to look at. Pass or fail comes from memory, not the pictures.
Without the port or the fixture template it prints a named `[SKIP]`, which
`make accept` refuses, as it must.

**Sam's procedure** (`docs/remixer/TESTING.md` section 10): `make reach`
lists the gates the branch's diff reaches, and `STRESS_SOURCE=<template>
STEMS_TEMPLATE=<template> make reach RUN=1 KEEP=1 JOBS=2` runs them. Each
command and its result go in the ledger and, later, in a PR body.

## 6. The records

- `docs/firmware/STEM_REC.md` section 16: the menu, the widths measured,
  and the gate's runs.
- `docs/firmware/MAINMENU.md`: the facts this piece measures that any
  module can use (the widths, how a heading row draws, a fifth category on
  the MKII under the port).
- `modules/stems/README.md` ("How to use it", "Limits"),
  `remixes/stems/README.md`, and the manifest's `doc` say MAIN MENU ›
  STEMS.
- The STEM REC block of `docs/remixer/FAILURE_MODES.md`: "The unit hangs
  when STEM REC is selected" names the new path.

## 7. Rules

- The recorder's logic doesn't change: the state machine, the hook, the
  streaming, the files. Every existing check still passes.
- Every value that moves is a finding: re-measured, explained, and written
  down, never loosened to pass.
- Every gate runs on a committed tree, and its log's first line shows it.
- The build uses the bare-metal `m68k-elf` toolchain (binutils 2.47, GCC
  16.1.0), as upstream's authors do. STEM REC's bytes differ from the
  Ubuntu toolchain's (PC-relative reads of its own globals); piece 2's
  gates run again on it first.
- No Elektron byte in the repository.
- Nothing is pushed.

## 8. Risks

- **MAIN MENU is the recovery screen.** A root that won't draw costs a
  SysEx recovery. Guarded by the four stock rows copied byte for byte and
  checked, the recovery check on both panels, and flash A's precondition
  of a stock 1.40C `.syx` at hand.
- **The MKII root hasn't run a fifth category on a unit.** octalab's ran
  on a MKI. Under the port both run; flash A proves the MKII.
- **Text width is unknown until measured.** The plan measures it first;
  shorter forms are ready.
- **How a heading row draws** (rows 2 and 11) is known only from octalab's
  MKI photos. The plan measures it under the port.
- **The draw may read a label's pointer twice** in one redraw (to measure,
  then to draw). A switch between the two reads would draw one frame with
  the new text at the old width: cosmetic, and gone on the next redraw.
- **Two modules that grow the root can't share an image.** None in this
  tree does today. OTX's proposed shared settings menu
  (`docs/proposals/OTX_MODULE_GUIDELINES.md`) would need STEMS to move into
  it later.

## 9. Done when

- MAIN MENU shows STEMS as a fifth category on the MKII and the MKI under
  the port, and CONTROL is stock.
- The rows and texts are as section 3 says, and every text fits the
  measured widths.
- `verify_stems.py` passes with the root and label checks, and
  `verify_stems_menu.py` passes on both panels, on a committed tree.
- `make reach` against upstream `main` lists the gates, and they pass
  (`make accept REMIX=stems` included, on the bare-metal toolchain).
- The records in section 6 are written.

## 10. Not in this piece

The flash (piece 4), 24-bit and a bit-depth row, the ring's size, the file
length set during the take (piece 5), seconds in the folder name and
re-arming after a take, saved track choices, a screen of its own (piece
7), OTX's shared settings menu, and any pull request.
