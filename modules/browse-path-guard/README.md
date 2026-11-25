# `browse-path-guard` — BROWSE PATH GUARD

A sample file's full path on the card can be at most 259 characters,
counted from the card's root: `/` + the set's name + `/AUDIO/` + the folders
+ the file's name. In stock 1.40C, moving the sample browser's cursor near a
file past that limit could leave the footer reading LOADING... for good,
the folder line garbled, and the browser refusing to open on any slot, in
any project, until a power cycle.

With this module the browser shows such a file as ERR, as it already shows
files the card cannot open, and keeps working. ERR is the expected result for
any file past the limit: it cannot be loaded either way. Nothing else changes.

## The 259-character limit

The limit is the card's own and this module does not change it. A slot
whose path is longer reads ERROR in the slot list, and a project that names
one loads without it. A `PATH=` in the project file starts `../AUDIO/`, so
its longest loadable length is 260 minus the set's name: 248 in a set named
with 12 characters, 253 with 7. Keep set names, folder names and file names
short enough that every sample stays inside it.

## How

The browser keeps three 260-byte path buffers at `0x460e48f0`,
`0x460e49f8` and `0x460e4afc`, then its current folder at `0x460e4c00`.
It fills them with folder + `/` + name using `strcat` (`0x40013f94`, twice
from `0x4006a598`) and `sprintf("%s/%s")` (`0x40013a08`, from `0x4006a7de`
and `0x4006a89e`), with no bound. A path of 260 characters or more ran into
the next variable:

- past `0x460e48f0`, onto `0x460e49f4`, the browser's LOADING... flag:
  set, it never cleared, and the browser refused to open again;
- past `0x460e4afc`, onto the current folder, which then read empty or
  garbled.

Each of those sites loads the routine's address as a 4-byte operand.
`guard.s` has bounded copies (`bpg_cat`, `bpg_join`) that keep at most 259
characters and the NUL, and the manifest points the three operands at them
(`SymbolRef`). A path cut short names no file, so its row reads ERR. The
stock routines and every other caller are unchanged.

## Gate

`tools/verify/verify_browse_path_guard.py`, under the port: a blank card in
a 12-character set with one 125-character folder of WAVs whose full paths
run from 250 to 265 characters. QUICK ASSIGN on T1, RIGHT into the browser
and the folder, the cursor down each file, then NO and RIGHT again. Every
step checks the current folder, that each 260-byte buffer ends inside its
260 bytes, and that the LOADING... flag is untouched.
