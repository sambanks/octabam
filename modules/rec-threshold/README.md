# `rec-threshold` — REC THRESHOLD

A recorder TRIG mode that waits for the input: TRACK + REC arms the
recorder, and the take starts by itself when the input gets louder than the
track's threshold. The Digitakt 2's threshold recording, on an Octatrack.

## Using it

1. Hold **FUNC** and press **REC AB** (RECORDING SETUP 1). Turn **TRIG**
   past ONE, ONE2 and HOLD to **THR**.
2. Hold **FUNC** and press **REC CD** (RECORDING SETUP 2). On a THR track
   two cells change:

   | stock | on a THR track | what it is |
   |---|---|---|
   | QREC | **LEV** | the threshold: −60, −56 … −8 (4 dB steps), −6, −4, −2, 0 dB. Saved with the Part, per track. Setting TRIG to THR makes it −40 if it was never set. |
   | QPL | **IN** | the live input level in dB: the loudest of inputs A–D, held ~0.5 s, then falling ~29 dB/s; `---` below −60. Its knob does nothing; QPL is left as it was. |

   Play the source, read IN, set LEV a few dB below it.
3. Arm: hold **TRACK** and press **REC** (or REC alone for the active
   track), with RECORDING SETUP open or closed; as on stock, the REC keys
   do nothing inside it while GRID RECORDING is on. While it waits, the
   track's status icon at the screen edge blinks (about 0.37 s on, 0.37 s
   off), whatever it shows.
4. The take starts when the input reaches LEV, and ends at RLEN as usual
   (with RLEN MAX, a press stops it). Arm again for the next one.
5. An arm is dropped, without a take, if the track's TRIG is no longer THR
   (edited, or another Part loaded): at the next draw of the status icons,
   and in any case when the input arrives. It is also dropped if the
   recorder is already recording when the input arrives.

- A second press while armed cancels.
- A press while recording stops the take (THR behaves as ONE2 there).
- The start is immediate: QREC is not applied, by design. Its byte is
  LEV, and a start quantised to the next beat would cut off the attack
  the threshold just caught.
- On a track not set to THR, nothing changes: RECORDING SETUP 2 shows QREC
  and QPL, and both edit as stock.
- A Part saved with THR loads on stock 1.40C as TRIG HOLD, with its LEV as
  a QREC value.

## How it works

One DRAM unit (`thresh.s`), ten detours, three pokes. The manifest's
docstring lists them with their addresses.

- **The keys.** TRACK + REC reaches `0x400836d8` (a loop over the held
  tracks) and the other REC path `0x40083544`. On an idle recorder (voice
  byte 1, "recorder running", clear) both post the start through
  `0x40005178` without reading TRIG. Under THR the hooks hold that start
  word, `(keys + 0x8000) | 0x10`, and the track's level instead. On a
  running recorder TRIG is decoded, and THR takes ONE2's path; without
  that hook a value of 3 falls to HOLD, whose key release stops the take.
- **The frame interrupt.** At `0x4000ab72`, where the input page index
  advances, while a track is armed or the meter is wanted: the peak
  |sample| of the newest complete input page (the previous page; 64 longs,
  inputs C D A B × 16) is compared with each armed track's level. At or
  over it, if the track's TRIG is still THR and its recorder is idle (voice
  byte 1 clear), the held word goes into the immediate mailbox
  `0x46c7e9fa`, which the dispatcher at `0x4000d2a0` acts on later in the
  same interrupt; the arm is spent either way. (At or over, not over:
  nothing exceeds full scale, so 0 dB could not fire otherwise.)
- **The pages.** TRIG's count 3 → 4 (the editor clamps by it) and the Part
  validator's hard-coded TRIG maximum 2 → 3 (it rewrites anything larger
  on every bank load). RECORDING SETUP 1 draws THR through its own
  formatter; RECORDING SETUP 2's cell loop and editor are hooked for LEV
  and IN; after the editor's store, TRIG becoming THR sets an unset LEV.
- **The blink.** The status icon renderer draws a track's icon only when
  its state differs from the one it drew last (`0x400c0cb8`), clearing the
  box first and drawing nothing for a state it has no glyph for. While a
  track is armed, every other blink phase hands it `0x10` + the state: the
  box is cleared and left empty, and the next phase draws the icon again.
  The phase is bit 10 of a frame count kept while something is armed. A
  track whose TRIG is no longer THR loses its arm there and shows its icon
  as stock. (THR7 dropped the arm in the setup editor instead, on the TRIG
  edit. Its failure on the unit to record from inside RECORDING SETUP was
  GRID RECORDING, not that code: stock's REC keys do nothing there while
  GRID RECORDING is on, `0x460d1736` with `0x460d5db4 == 3`, tested at
  `0x400836e4` and `0x40030ed0`; confirmed on the unit, 13 Oct.)
  FREE LOOP hooks the same load (`0x4004bee2`): beside it the registry adds
  [HOOKS](../hooks/README.md), which calls this, then FREE LOOP's fold
  (under Unicorn only, verify_hooks; not flashed). REC TRIG MUTE shared it
  until its pin after `553d8d2`, when its mute dots moved to the tab letter.

## Open

- REC CD, an MKI.
- `0x400828e0` names TRIG values (N/A past 2); which screen draws it is
  not known. `0x40068a94` and `0x40068b0c` are PERSONALIZE's DEFAULT TRIG
  MODE and DEFAULT REC MODE (`0x80000094`, `0x80000098`; ONE, ONE2,
  HOLD, blank past 2). A fresh Part copies DEFAULT REC MODE into each
  track's TRIG (`0x40005926`): THR is not offered there.
- The port's REC keys differ from the unit's: REC AB alone does nothing
  there, and TRACK + REC records with RECORDING SETUP open. The gate uses
  TRACK + REC with the page closed, as the unit does.
- An earlier version kept the level in a BRAIN setting. As an Option with
  labels it crashed under the port after RECORDING SETUP and TRACK + REC
  (with every detour removed); as a Number it was clean. Not chased
  further: the level now lives in the Part.

## Thanks

- [Sam Banks](https://github.com/sambanks), octabam's author: the build, the
  hooks and their checks, the ColdFire port this was measured under, and
  RLEN PLEN, whose RECORDING SETUP formatter hook THR's label follows.
- [Bryan T](https://github.com/bryantysinger): the recorder's control path,
  buffers and write path read out of the binary (`docs/firmware/RECORDER.md`).
- [Yves Rosius](https://github.com/yvesrosius): STEM REC's measurement of
  the input pages (`docs/firmware/STEM_REC.md` 18.7), the layout the
  detector reads.
