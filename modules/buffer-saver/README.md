# `buffer-saver` — BUFFER SAVER

Recordings in the recorder buffers are not saved to the card by SAVE
PROJECT. Forget SAVE THIS RECORDING (or save the project but not the
buffers), turn the unit off, and the project comes back without its
sounds. This module makes SAVE PROJECT offer to save them.

## Why I made this (Chupitnik)

When you sample into a record buffer it is not automatically saved to the CF and I'm a very forgetful character when I'm in a frenzy of creativity. So if one turns off the machine before a manual save, or saves the project but not the buffers, one ends up with a project with no sounds. I’ve done this countless times. My hope is that this mod will put an end to that. When you save the PROJ it asks if you want to save the samples too and then assigns them back to their own recorder buffers. Like magic only more so!

## Using it

1. Record as usual.
2. Save the project: PROJECT > SAVE, FUNC + PROJ, or PROJECT > SAVE TO NEW.
3. If a recorder buffer holds a take not yet saved, a dialog asks
   **UNSAVED RECORDINGS! / SAVE SAMPLES?**
   - **YES**: each such buffer is saved to the card and assigned to
     itself, then the project saves as usual (stock's own SAVE PROJECT
     question follows). On reload the buffers come back with the takes.
   - **NO**: the project saves exactly as stock.
   - With SAVE TO NEW, YES saves the takes first, then stock's SAVE TO NEW
     asks for the new name and copies the project, the takes included
     (with SAVE SAMPLES TO = PROJ DIR they are copied into the new
     project's folder; with AUD POOL both projects point at the pool).
4. With nothing new to save, the save is stock: no dialog.

- Names are stock's suggestion, `R<n>-YYMMDD-HHMM` (n = the buffer, 1–8).
  If that file exists, `-2`, `-3` … is added. Nothing is overwritten and
  no name is typed.
- The files go where PERSONALIZE's SAVE SAMPLES TO says (stock's rule),
  each with its `.ot`.
- A buffer still recording, or armed, is left for the next save.
- A take saved once is not offered again until the buffer records again.
  Loading a project clears the list.
- **RELOAD** discards everything since the saved state, the takes in the
  buffers included (port, 19 Oct 2026: the buffer's length went to 0), and
  goes through the same LOAD PROJECT case, so the list is cleared and the
  next save does not ask. Save with YES before a RELOAD to keep a take.
- **SYNC TO CARD** writes the working state, not the saved one, and does
  not save samples: the module does not ask, the takes stay in their
  buffers and on the list, and the next SAVE PROJECT offers them. For a
  project never saved, stock's SYNC runs SAVE TO NEW's code, which asks
  (read from the code, `0x4006384c`; not run).
- **EXPORT TO SET** saves the project first by its own route, not through
  SAVE or SAVE TO NEW, so the module most likely does not ask and unsaved
  takes are not in the exported project (read from the code, `0x40063a0c`;
  not run: it needs a second set). Save with YES first, then export.
- After a power cycle nothing is offered: the recorder buffers do not
  survive a power-off on stock 1.40C, and the list of new takes starts
  empty at boot (it lives in the module's DRAM). Tried on the unit, 17 Oct
  2026 (PREMIX): a take, SAVE PROJECT with NO, power off and on; the take
  was gone and FUNC + PROJ did not ask.
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
  per-track take start (`0x400069e4`, where its state becomes recording,
  just after the LIMIT write at `0x400069d6`, which stays stock so REC
  THRESHOLD's gate still sees it) sets bit n of a byte for buffer n, and the engine's LOAD PROJECT case (`0x4008534c`)
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

## vs PERSISTENT BUFFERS

[PERSISTENT BUFFERS](../persistent-buffers/README.md) also writes recorder
buffers on SAVE PROJECT, but always dumps every non-empty slot to fixed
`BUFFERS/RECn.wav` through STORE (no dialog). This module only offers
**SAVE SAMPLES?** for marked unsaved takes and uses stock
`R<n>-YYMMDD-HHMM` names. Declared `conflicts` on PERSISTENT BUFFERS —
both would write the same buffers on one save. Pick one.

## Open

- An MKI.
- Two takes in one buffer between saves: only the last is saved, as the
  buffer holds only the last.
