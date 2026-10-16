# PLOCKS-P2 contribution notes

The page-2 editor marks a held trig as edited and clears native pending tap
masks before committing a lock. This lets release distinguish an edit from
a bare tap, preserving the lock just entered. `verify_plocksp2.py`
checks the held-step edit followed by release and subsequent bare-tap clearing.

### Stock Address Provenance

These are stock **1.40C** addresses, checked in the local MAIN_OS disassembly.
The native knob-commit routine starts at `0x4004ecfc`: at `0x4004f0aa`
it writes 1 to the 32-bit word `0x460d173a`, then clears the six 16-bit
words below. `pe_commit` mirrors that sequence.

| RAM word | Native knob-commit clear | Native trig-down read | Native release read / clear |
|---|---|---|---|
| `0x460d1a9e` | `0x4004f0b2` | `0x40050fee` | `0x4005fbe2` / `0x40060a5a` |
| `0x460d1aa0` | `0x4004f0b8` | `0x40050ff4` | `0x4006001a` / `0x40060a68` |
| `0x460d1aa2` | `0x4004f0be` | `0x40050ffa` | `0x4005feaa` / `0x40060a76` |
| `0x460d1aa4` | `0x4004f0c4` | `0x400516a6` | `0x40060674` / `0x40060a84` |
| `0x460d1aa6` | `0x4004f0ca` | `0x400516b8` | `0x40060a14` / `0x40060a92` |
| `0x460d10dc` | `0x4004f0d0` | `0x4003004a` | `0x4003013a` / `0x40030144` |

The main trig-down routine starts at `0x40050f20`; the release routine at
`0x4005fb44`. Release also reads the edited word at `0x40060b04` and clears
it at `0x40060b14` when the held-trig mask at `0x460d174a` is zero.
The sixth mask belongs to an alternate trig path starting at `0x4002fff8`,
called by release at `0x40060aa8`. Its consumed bits are cleared separately.
The common reset helper at `0x400339b0` clears all six masks as well.

The addresses, widths and matching stores are statically observed. The names
“edited” and “pending tap masks” describe their inferred role from those
read/write paths, corroborated by the release regression. They are not
firmware symbols. This is not an exhaustive claim about every reader.

Under the emulator, a recorded page-two lock survives release; a subsequent
bare tap clears it. Project/card persistence and protected-file refusal are
also covered by the passing regression. These are emulator measurements.
Hardware tested by radiohagen on an Octatrack MKII on 17 October 2026:
Octabam Core, source `b6a9d17`, local build label `OCTABAMP4`. The checklist
passed, including hold/edit/release/rehold and comparison with page-one
hold timing. Numeric
physical timing was not measured; Bus/Inserts were tested under the emulator.

## Release regression control

On 17 October 2026, the full `verify_plocksp2.py` (including `tap_clear`)
was run twice on Core, BUILD=P4, from runtime/test source
`b6a9d17fff215cd3daf32b7b5e5f73d7ee0748b0`, based on upstream
`c3f37e531f6b072b8197d93f173e063b55249363`. Both runs used the same
verifier and disposable project. The control removed only the edited-word
store and six pending-tap clears from `pe_commit`; all display hooks and
the verifier stayed unchanged.

- Fix present: lock value **3** survives release; **zero failures**, exit 0.
- Fix removed: the recorded lock is **255**, the empty-lock sentinel;
  **three failures**, exit 1. The other two failures are the FX1/FX2
  early-release Part-display assertions.
- A subsequent bare trig tap clears the page-two locks in both runs.
- The positive payload is byte-identical to the Core P4 payload tested on
  hardware: SHA-256
  `11389f83570ed0988bcb6d97a751ab1ea2a9744f8395e7c99601266386b73ab8`.

This release control is separate from the P3 immediate-redraw timing
control. These results measure emulator behavior.

## SETUP display lifecycle

- Stock dispatches trig press (event 1) to `0x40050f20`, hold (event 2)
  to `0x400587d4`, and release to `0x4005fb44`. The event-2 branch at
  `0x40060c80` reaches the hold handler via `0x40060c96`. Its page redraw
  at `0x40058958` calls `0x4004d948(-1)`. PLOCKS wraps this call and then
  refreshes active FX SETUP, following stock's hold timing without adding
  a timer. The press path and its bookkeeping call remain untouched.
- The release call to `0x4004d948(-1)` at `0x40060b38` is wrapped,
  keeping its argument and return registers. It redraws the native page
  then refreshes active FX SETUP. Committing a page-two edit also refreshes
  SETUP immediately. Unheld dials retain their native animation and timeout.
- FX1/FX2 descriptors at `0x400bc25a` / `0x400bc484` carry the window
  pointer at +8 and native draw callback at +44. The popup object is
  shared with other dialogs. Refresh requires the active pointer, its
  open flag, SETUP geometry `(7, 0, 0xf4, 0x40)`, an audio track and the
  corresponding FX page. A nonzero window pointer alone is insufficient.
- Widget argument hooks at `0x40037c14` / `0x40037878` retain the native
  renderer and formatter. `plk_dial` checks the first held step; an actual
  lock sets bit 0 of the widget flags, preserving other bits. In the stock
  dial renderer (`0x400479b4`), that bit keeps the formatted number visible
  (`0x40047a8a`) and inverts the value area (`0x40047ba0`). Names use the
  unchanged native text renderer. No lock leaves all widget flags unchanged.

`verify_plocksp2.py` drives native panel inputs and decodes the panel UART
on disposable cards. It first boots unmodified stock 1.40C and captures
COMPRESSOR ATK page-one locks at 50, 51, 52 and 53. The FX2 PLATE REV and
FX1 COMPRESSOR page-two visible dial/number region must match stock pixel for pixel after
its seven-row vertical offset. Native SETUP draws the name after the widget;
its bottom padding clears row 16 (x=62..76). That row is checked with the
unchanged name; the dial/number comparison covers rows 17..34 versus stock
10..27. It checks:

- unchanged parameter names, lock values and Part bytes;
- numeric visibility after a pause and after release/rehold without a turn;
- initial lock display timing against stock's page-one reference (10 ms
  samples, 30 ms allowance for input-scan and decoded-frame phase);
- short taps, two held trigs, and editing/releasing before the hold event;
- release, unheld +1, slow held increments and FUNC removal;
- untouched page-one locks and native MIXER/TEMPO/MIDI windows.

Screens and port logs remain in the gate output. These measure emulator
behavior; they do not measure physical panel timing. The manual hardware
check above covers perceived hold timing, not instrumented latency.

The pre-PR control restores upstream PLOCKS source at base
`c3f37e531f6b072b8197d93f173e063b55249363`. Its six initial FX2 screen
captures matched P1 (`7cb22414a58dbbd03e468ba1c69f03a862fb46ef`) exactly:
the lock bytes changed but the displayed value stayed stale. This is an
existing upstream display defect, separate from the release-erasure defect.
The initial memory/persistence regression did not decode the LCD and
therefore could not detect it.

### Broader Scenes gate limitation

The unmodified `verify_scenesp2.py` expects DELAY SERVER's page-two MODE
and TIME layout. With the local Core fixture, both the candidate and the
upstream PLOCKS control fail the same seven assertions (six frame values
and the seeded editor value). Core contains stock DELAY, not DELAY SERVER.
Changing that fixture from PLATE REV to stock DELAY does not make this
particular oracle applicable. This is not a passing aggregate Scenes
check, and it is not evidence of a new regression. The PLOCKS panel,
playback and persistence checks are reported separately. No Scenes code
or verification thresholds are changed by this contribution.
