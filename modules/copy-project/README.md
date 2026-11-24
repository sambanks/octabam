# COPY PROJECT

Duplicate a project folder on the CompactFlash card without loading it
first.

**PROJECT → CHANGE → highlight a project → FUNC+BANK → COPY** (under
RENAME / DELETE) asks for a name, confirms, and copies the source folder
byte-for-byte into a new folder — stock project files and module extras
alike.
After a successful copy it asks whether to open the copy (stock LOAD
PROJECT).

Entry used to be a PROJECT menu TableGrow (15→16); that blob no longer
packs beside long FX1 + QUANTIZER on a full tip (#931). The FUNC+BANK
popup grows 2→3 instead (`docs/firmware/PANEL.md`).

**Sidecars** = non-stock files modules leave in the project folder
(`kits.work` / `kits.strd`, `scenes.work`, `brain.work`, `p2lkNN.work`,
`BUFFERS/`, …). A folder copy keeps them; so does SAVE TO NEW (below). On a
live card set they show up next to `project.work` / `bankNN.work` (e.g.
`261018 IDLEYARD`, `!DEF_TMPL`).

## Use

1. Mount the set that holds the source project (CHANGE set if needed).
2. PROJECT → CHANGE → highlight the source (folders with `project.work` /
   `project.strd`; not `<CREATE EMPTY PROJECT>`).
3. FUNC+BANK → COPY.
4. Edit the suggested name (`PROJECT YYMMDD`, or FUNC+CUE with RND NAME)
   and YES. The name editor itself caps at 32 characters.
5. Confirm `COPY SRC -> DST?` (16-char display cap on the line).
6. On success: `PROJECT COPIED` / `OPEN IT?` — YES loads the copy and
   closes CHOOSE PROJECT. NO leaves the live project as it was.
   `COPY FAILED` on error; a partial destination folder is removed so a
   retry does not hit `NAME ALREADY IN USE!`.

## What gets copied (disk only)

COPY is **card-to-card**: the highlighted folder as it sits on the CF,
including stock `.work` / `.strd` and module sidecars (`kits.*`,
`scenes.*`, `brain.*`, `p2lk*`, `BUFFERS/`, …). It does **not** read live
RAM.

**Trigs / banks.** Stock already autosaves the loaded project into
`.work` (and flushes dirty banks ~1 s after STOP). So edits you hear
after a stop are usually already on disk; CHANGE often has nothing to
ask. A short window (still playing, or before that flush) can leave RAM
ahead of the card — SAVE PROJECT if you care about that snapshot before
copying.

**No “save before open” prompt.** An earlier build asked every time by
calling `0x400255ec`, which means “a project is open”, not “dirty”.
There is no reliable cheap dirty check here; OPEN IT? just loads the
copy. SAVE the live project yourself first if you need `.strd` / sidecar
commits.

**Recorder buffers (PERSISTENT BUFFERS).** That module writes
`BUFFERS/RECn.wav` only on **PROJECT → SAVE**, and reloads them on LOAD.
COPY will carry `BUFFERS/` only if SAVE already wrote it. Takes that
exist only in RAM are not in the folder and will not appear in the copy.
Takes that exist only in RAM are saved by BUFFER SAVER's own SAVE SAMPLES? step.

## SAVE TO NEW

Stock SAVE TO NEW saves the open project to its own folder, then makes the
new folder and writes the stock files into it. Two detours carry the rest:

- `0x40085012`, the call that overwrites the project name (`0x40013f40`):
  `cp_sa_capture` keeps the old folder's path. It keeps nothing when the
  project is unsaved (`0x100f847c` set), when no project is open
  (`0x400255ec` = 0) or when the old folder is not on the card.
- `0x400850ee`, after the last stock write: `cp_sa_copy` copies every file
  and folder of the old folder that the new one lacks, except `.strd` files.
  A file the new folder has (every stock `.work` file) is not touched.

Stock's save-as writes `.work` files only: with the module's copy off, a
54-file fixture (`.work` and `.strd` twins, `kits.work`) gave 26 names in
the new folder (`arr01-08`, `bank01-16`, `markers`, `project`, all `.work`) and no
`.strd`. A `.strd` is the old project's last saved state, so it is not the
new project's; SAVE PROJECT writes the new project's. A first version
copied them, and the unit's new folder then held the old project's
`bank02.strd`, which predates the take that changed `bank02.work`.

The copy runs on the engine task inside the save-as job. Stock's result
register (`d2`) is not consulted: stock reports `FILE NOT FOUND` for a
project with no `.strd` files and still writes the new folder.

`verify_copy_project` runs it under the port: `kits.work` and `scenes.work`
in the new folder byte for byte, and two module `FCOPY` calls. Not
exercised: a sidecar subfolder (`stage_card.py` stages top-level files
only), the unit, a long copy on the engine task (`BUFFERS/` with large
WAVs).

Limits that refuse with `COPY FAILED` (no silent truncate / partial
copy): more than 64 projects in the set, a directory with more than 256
entries, an entry name longer than 32 characters inside the tree, or
nesting deeper than 6 folders.

## Open

- Cross-set copy (v1 is the mounted set only).
