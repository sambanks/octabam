# COPY PROJECT

Duplicate a project folder on the CompactFlash card without loading it
first.

**PROJECT → CHANGE → highlight a project → FUNC+BANK → COPY** (under
RENAME / DELETE) asks for a name, confirms, and copies the source folder
byte-for-byte into a new folder — stock project files and module extras
alike. Stock SAVE TO NEW writes a fresh project and drops those extras.
After a successful copy it asks whether to open the copy (stock LOAD
PROJECT).

Entry used to be a PROJECT menu TableGrow (15→16); that blob no longer
packs beside long FX1 + QUANTIZER on a full tip (#931). The FUNC+BANK
popup grows 2→3 instead (`docs/firmware/PANEL.md`).

**Sidecars** = non-stock files modules leave in the project folder
(`kits.work` / `kits.strd`, `scenes.work`, `brain.work`, `p2lkNN.work`,
`BUFFERS/`, …). A folder copy keeps them; SAVE TO NEW does not. On a
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
SAVE TO NEW still drops these sidecars; COPY keeps them when present.

Limits that refuse with `COPY FAILED` (no silent truncate / partial
copy): more than 64 projects in the set, a directory with more than 256
entries, an entry name longer than 32 characters inside the tree, or
nesting deeper than 6 folders.

## Open

- Cross-set copy (v1 is the mounted set only).
