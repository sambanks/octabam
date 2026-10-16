# `buffer-saver` — BUFFER SAVER

Recordings in the recorder buffers are not saved to the card by SAVE
PROJECT. Forget SAVE THIS RECORDING (or save the project but not the
buffers), turn the unit off, and the project comes back without its
sounds. This module makes SAVE PROJECT offer to save them.

## Why I made this (Chupitnik)

When you sample into a record buffer it is not automatically saved to the CF and I'm a very forgetful character when I'm in a frenzy of creativity. So if one turns off the machine before a manual save, or saves the project but not the buffers, one ends up with a project with no sounds. I’ve done this countless times. My hope is that this mod will put an end to that. When you save the PROJ it asks if you want to save the samples too and then assigns them back to their own recorder buffers. Like magic only more so!

## Using it

1. Record as usual.
2. Save the project: PROJECT > SAVE, or FUNC + PROJ.
3. If a recorder buffer holds a take not yet saved, a dialog asks
   **UNSAVED RECORDINGS! / SAVE SAMPLES?**
   - **YES**: each such buffer is saved to the card and assigned to
     itself, then the project saves as usual (stock's own SAVE PROJECT
     question follows). On reload the buffers come back with the takes.
   - **NO**: the project saves exactly as stock.
4. With nothing new to save, SAVE PROJECT is stock: no dialog.

- Names are stock's suggestion, `R<n>-YYMMDD-HHMM` (n = the buffer, 1–8).
  If that file exists, `-2`, `-3` … is added. Nothing is overwritten and
  no name is typed.
- The files go where PERSONALIZE's SAVE SAMPLES TO says (stock's rule),
  each with its `.ot`.
- A buffer still recording, or armed, is left for the next save.
- A take saved once is not offered again until the buffer records again.
  Loading a project clears the list.
- If a save fails (a full card), stock's errors show, the project is not
  saved, and the next SAVE PROJECT offers that buffer again; NO there saves
  the project as stock. Stock's failed write leaves its files under the
  name it tried: the `.wav` cut where the card filled (empty under the
  port) and an empty `.ot`. Nothing points at them, and the retry takes the
  next `-N`; they can be deleted.

## How it works

One DRAM unit (`bufsave.s`), three detours; the manifest's docstring lists
them with their addresses.

- **The list.** Stock keeps no "unsaved take" flag: under the port a take
  writes only the slot's length and trim (15 Oct 2026). So the recorder's
  per-track take start (`0x400069d6`, where LIMIT is written) sets bit n of
  a byte for buffer n, and the engine's LOAD PROJECT case (`0x4008534c`)
  clears it.
- **The question.** The PROJECT menu's SAVE (`0x40063890`; FUNC + PROJ
  reaches the same handler through `0x400648fc`) asks through stock's YES/NO
  dialog (`0x4006d57c`) when a marked buffer has audio (slot state +16 > 0)
  and its recorder is idle (`0x40004268`).
- **The save.** The way stock's SAVE ALL RECORDINGS chains (`0x4003108c`),
  one buffer at a time: FLEX object 128 + n, mode 2 (save, then assign to
  self with no menu), the done callback `0x46c8d198`, the name in
  `0x460be9f0`. Then the naming keyboard's own confirm `0x40024288(1)` runs
  instead of the keyboard. Stock writes the WAV and its `.ot`, assigns the
  buffer to the file and calls back with the result. A success clears the
  buffer's mark and moves on; after the last buffer stock's SAVE runs.

## Measured

Under the ColdFire port on stock 1.40C (15 Oct 2026), the path this module
drives: a take, SAVE THIS RECORDING with YES on the keyboard, ASSIGN TO
SELF, then SAVE PROJECT wrote `R1-000000-0000.wav` (the port's clock is
unset) and `.ot`. The project then recorded `SLOT=129
PATH=../AUDIO/R1-000000-0000.wav`, and a fresh boot's LOAD PROJECT refilled
buffer 1 (length `0xac440`, the 16 s take).

Under the port on this module's image, `tools/verify/verify_buffer_saver.py`
(in `make check`): after a take FUNC + PROJ asks SAVE SAMPLES?; YES writes
`R1-000000-0000.wav` and `.ot` and points the project's buffer 1 at it, and
the next save does not ask; with that name taken the take is saved as
`R1-000000-0000-2` and the old file is left alone; NO writes no sample and
the project saves as stock.

On a unit (Chupitnik's MKII, 15-16 Oct 2026, images AUTOSAVE1 and AUTOSAVE2
from the card, under the module's first name REC BUFFER AUTOSAVE;
`CHANGELOG.md`): the question on FUNC + PROJ and on PROJECT > SAVE; names
with the real date and time; two buffers saved in one go; no question on an
immediate re-save; a reload brings the takes back; NO saves as stock.

Two harder cases under the port (16 Oct 2026, this module's image, a
saved project, inputs on the port's tones):

- **A full card** (a filler file leaving 64 KB, a one-second take): YES,
  then stock's WAV write fails (its done callback `0x40024740` with -25),
  stock shows ERRORS OCCURED WHILE SAVING THE SAMPLE! and then the sample
  settings error (`0x400247b8`, -24). Neither calls the module's done
  callback, so the chain stops before the project save. The unit stays
  live: the next FUNC + PROJ asks SAVE SAMPLES? again (the mark kept), NO
  there opens stock's CONTINUE?, and a later save asks again. Stock leaves
  `R1-000000-0000.wav` and `.ot` at 0 bytes.
- **Saving while the sequencer plays** (PLAY, a take, FUNC + PROJ): the
  take is saved and assigned, the project saves with buffer 1's path, and a
  later FUNC + PROJ opens stock's CONTINUE? with no SAVE SAMPLES?. The port
  played an empty pattern; playback under load was not judged.

On a unit (Chupitnik's MKII, 16 Oct 2026, AUTOSAVE2):

- **Saving while a pattern plays** (samples on several tracks): the samples
  saved with no stutter or dropout, the take came back on reload, and the
  keys stayed responsive. Playback stopped at the project save itself, as
  stock SAVE PROJECT does.
- **A full card** (224 KB free, a take of several seconds): stock's ERRORS
  OCCURED WHILE SAVING THE SAMPLE! / CARD FULL, no freeze; the next save
  asked again, and saving the project without the samples worked. The
  failed write left `R5-…-0744.wav` cut at 256 KB and its `.ot` empty, with
  nothing pointing at them.

## Open

- An MKI.
- Two takes in one buffer between saves: only the last is saved, as the
  buffer holds only the last.
