# `kits` — KITS

255 Kits per project. A Kit is a saved Part; each pattern plays the Kit
assigned to it, through the stock Part slots. `Kind.CF_PATCH`: one DRAM
unit (`kits.s`), 23 detours, nothing on the DSP. The firmware facts it
stands on are [`docs/firmware/PARTS.md`](../../docs/firmware/PARTS.md).

Credit: Em ([emuyia](https://github.com/emuyia)) designed Kits on the
Octatrack in [Octakit](https://github.com/emuyia/ems-octakit) (MIT,
Copyright (c) 2026 June Kiff). KITS follows its design: Kits per
project, LOAD KIT and SAVE KIT on PART and FUNC+PART with its key map, the
list copy, paste, clear and undo, the pattern clipboard carrying the Kit, and the
`NNN name` status line. It reads Octakit's `kits3a/b.work` files.
Markers as in `CHIP.md`: ✅ measured, 📖 read from the code.

## What a Kit is

A Kit is the 6,322 bytes of one Octatrack Part, plus an eight-byte name.
Loading a Kit loads those bytes into a Part slot.

The Octatrack manual's Part (OS 1.40A, section 10.2 PARTS: page 52 of the
[MKII manual](https://www.elektron.se/wp-content/uploads/2024/09/Octatrack-MKII-User-Manual_ENG_OS1.40A_210414.pdf),
page 53 of the [MKI manual](https://www.elektron.se/wp-content/uploads/2024/09/Octatrack-User-Manual_ENG-OS1.40A_220204.pdf);
summary in section 4.7): "machine, sample and effect assignments along
with track parameter settings and up to 16 scenes". Per track, from the
Part's layout (`docs/firmware/PARAM_PAGES.md` section 5 and the offsets
after section 7; `docs/firmware/PARTS.md` section 9; `docs/firmware/MIDI.md`
Appendix A section 3):

| in a Kit | Part offset |
|---|---|
| FX1 and FX2 effect selections, eight tracks each | `+0x00`, `+0x08` |
| track levels and cue levels | `+0x12 + 2t`, `+0x13 + 2t` |
| the machine type (Flex, Static, Thru, Neighbor, Pickup) | `+0x22 + t` |
| PLAYBACK page settings, one set per machine type | `+0x2a + 30t + 6·machine` |
| the Flex or Static sample slot each machine plays | not located |
| LFO, AMP, FX1, FX2 page 1 | `+0x11a + 24t` |
| LFO page 2 (destination, wave, multiplier, trig mode), AMP, FX1, FX2 page 2 | `+0x2f2 + 30t` |
| the eight MIDI tracks' parameters | `+0x3e2 + 32(t−8)` |
| the 16 scenes' locks | `+0x662 + 32(8·scene + t)` |
| the LFO designer shapes, audio and MIDI tracks | `+0x1702`, `+0x1792` |

Not in a Kit, as with a Part:

- The samples. A Kit holds a sample slot number; the slot's file and its
  settings are in the project's Flex and Static slot lists (manual section
  4.3). Kits are per project (`kits.work` in the project directory), so a
  slot number always refers to the same project's list.
- Everything the pattern holds: trigs, parameter locks, track lengths and
  scales (manual section 4.6).
- Tempo: the project's, or the pattern's when tempo is per pattern
  (manual section 8.9.1).
- Arrangements, track recorders and project settings (manual section 4.3).

### Against the Machinedrum and Monomachine

Octakit's README: "I prefer the silver boxes' (MnM & MD's) Kit approach
over Parts". What KITS takes from them is the link: each pattern names a
Kit and plays it, Kits are saved and loaded by name from one list, and
LOAD KIT keeps an UNDO KIT. A Kit's contents are the Octatrack's Part,
which is not what an MD or MnM Kit holds.

| | Machinedrum ([manual](https://www.elektron.se/wp-content/uploads/2024/09/machinedrum_manual_OS1.63_1.pdf), OS 1.63, p. 14 "MACHINEDRUM KITS", p. 35 "CLASSIC VS EXTENDED") | Monomachine ([manual](https://www.elektron.se/wp-content/uploads/2024/09/monomachine_manual_OS1.32.pdf), OS 1.32, p. 1-18 "MONOMACHINE KITS") | KITS |
|---|---|---|---|
| how many | 64 (8,192 on +Drive) | 128 (16,384 on +Drive) | 255 per project |
| a pattern plays its Kit | in EXTENDED mode | yes | yes |
| machine per track, its parameters | 16 tracks | 6 tracks | 8 audio tracks (and 8 MIDI tracks) |
| track effects | yes | yes | FX1, FX2 and their settings |
| LFOs | yes (p. 33: "the LFO settings are stored in the kit") | 6×3 | 3 per track, and the LFO designer shapes |
| master effects and their routing | yes | — | no master effects on the Octatrack |
| MIDI sequencer track settings | — | yes | the MIDI tracks' parameters |
| scenes | — | — | 16 |
| sample assignments | — | — | the slot number per machine |
| tempo | not in a Kit | not in a Kit | not in a Kit |
| UNDO KIT | yes | yes | yes |

## Use

| keys | MKII | MKI |
|---|---|---|
| LOAD KIT | PART | FUNC+MIDI |
| SAVE KIT | FUNC+PART | FUNC+MIDI, then FUNC+BANK |
| quick save (the Kit under the cursor, its name kept) | FUNC+PART, then FUNC+YES | FUNC+MIDI, FUNC+BANK, then FUNC+YES |
| reload the current Kit | FUNC+CUE (stock Part Reload) | FUNC+CUE |
| the pasted pattern plays a copy of its Kit in the next empty Kit | FUNC+PASTE+PART (PART while STOP is held after the paste) | FUNC+PASTE+MIDI |
| save the Kit, copy it and the pattern to the next empty ones, play the copy | PTN+FUNC+RIGHT | PTN+FUNC+RIGHT |
| copy / paste / clear an inactive pattern of the current bank (paste or clear again: undo) | hold PTN, FUNC and the pattern's TRIG; REC / STOP / PLAY | the same |

- **LOAD KIT** lists UNDO KIT (the Kit the current pattern had before
  the last load), the 255 Kits (`NNN name`, `*` on a Kit no pattern
  plays, `NNN ---` on an empty one). YES on a Kit: the current pattern
  plays it, now.
- **MKI FUNC+BANK** is SAVE KIT only while the LOAD KIT list is open
  (Octakit's key map); with SAVE KIT open it closes it, over the Kit name
  editor it cancels it, and anywhere else it is stock's (PATTERN SETTINGS
  on the main screen). RECORDING SETUP has its own key map
  (`0x400b9e36`): FUNC+BANK there never reaches the hook. The open
  list is KITS' when the stock list's callbacks pointer (`0x460e5e28`) is
  KITS' table; the editor when its done callback (`0x460e761a`) is
  KITS'.
- **SAVE KIT** lists the 255 Kits, the cursor on the current Part's
  (the first empty Kit when the slot holds none).
  YES opens the name editor (seven characters, `NEW KIT` for an empty
  Kit); the current Part is saved into the Kit and the current pattern
  plays it.
- In either list, LEVEL moves the cursor a row per detent (Octakit's
  LEVEL scroll; the encoder dispatch call `0x40061e00`), UP and DOWN as
  stock.
- In either list, FUNC+REC copies the Kit under the cursor, FUNC+STOP
  pastes onto it, FUNC+PLAY clears it; the same paste or clear again on
  the same Kit undoes it.
- The status line's Part field shows the current slot's Kit as `NNN
  name` (Octakit's form; measured on the port's LCD: `009 ONE`). The
  stock Part name is the Kit's first six characters (its field is seven
  bytes).

## How it works

- **Staging.** Before a pattern is scheduled (`0x400a0570`: the panel,
  program changes, the project load) or appended to a chain
  (`0x4009c634`), its Kit is copied into a Part slot of its bank that
  nothing is playing, and the pattern's Part byte names that slot; the
  switch reads the Part byte then (PARTS.md section 3). A slot is free when
  no engine track names it while the transport runs, no queued or
  chained pattern's Part byte names it, and its working Part is byte for
  byte the Kit KITS recorded there (outside MIDI SCENES' Part-window
  bytes when it is in the remix: his code rewrites them in the current
  Part from his own table after a project load, measured in ok-ms). A
  slot whose content is in no Kit is
  never copied over. With no free slot, or a request with an interrupt
  level set (the arranger and repeat publish from the tick), the pattern
  plays what is resident and the request is counted.
- **LOAD KIT** writes the Kit into the current Part's saved copy and runs
  the stock Part Reload `0x4004aab4` (working copy, CS1 copy, engine
  apply, machine transitions). **SAVE KIT** runs the stock Part Save
  `0x4004a908`; its tail copies the saved Part into the slot's Kit, so a
  plain Part Save and SAVE ALL update the resident Kits too. Other slots
  holding an unedited copy of a saved Kit get the new content.
- **The pattern clipboard carries the Kit**: the stock pattern copy
  (`0x40026eb0`), the paste's undo snapshot (`0x40026ef0`) and the paste
  or undo restore (`0x4002b9b0`).
- **Files.** `kits.work` and `kits.strd` in the project directory:
  64 bytes of header (`KITS`, version 1, length, CRC-32 of the rest,
  an unused word), ASSIGN (256), the valid bits (32), RESID (64), then 256
  records of an 8-byte name, 8 reserved bytes and the 6,322-byte Part:
  1,622,944 bytes. Record 256 is never a Kit: ASSIGN and RESID use 0xff
  for "no Kit". A Part found there at a load (Em's Kit 256, or a save
  into Kit 256 by a build before 255) moves to the next empty Kit; on
  Em's import the patterns her manifest gives Kit 256 move with it.
  Written after the bank writer (`0x400917c8`) when a
  Kit or an assignment changed, copied to `.strd` by the project store
  (`0x4008ee74`) and back by the project reload (`0x4008f180`). A
  `kits.work` that fails its CRC is never overwritten; the project then
  plays its Parts as stock.
- **First load of a project.** With no `kits.work`: Em's `kits3a.work`
  and `kits3b.work`, when present, are imported (per Kit the newest
  record whose CRC-32 holds, ASSIGN from the newest manifest); each slot
  is matched to the Kit equal to its working Part, and a slot equal to
  none is saved into the next empty Kit. Without them the stock Parts
  migrate: Kit `bank·4 + part` is the working Part with its name, each
  pattern with content plays its Part's Kit. Her files are left on the
  card.
- **Power-off.** RESID (with a magic and a sum) at `0x100f85a0` and ASSIGN
  at `0x100ffe00` in CS1 (stock references nothing there; PLOCKS P2 holds
  `0x100f8600..0x100ffe00`). The power-up's bank load (the masked load
  returning to `0x40084d66` when no project has been loaded since boot)
  takes them from CS1.
- The masked bank load `0x400905d4` is told apart by its return address
  (PARTS.md section 8): LOAD PROJECT (`0x400853de`), the power-up
  (`0x40084d66`), anything else (the masked banks' slots are forgotten
  and restaged).
- No `illegal`. The counters (`KSTATE` in the unit, read by the gate):
  READY, CNT_ISR, CNT_NOSLOT, CNT_INVALID (an assignment naming an empty
  Kit), CNT_IOERR, CNT_BADFILE, CNT_STAGED, CNT_REPOINT.

## Measured

Under the port, 6 Oct 2026, `tools/verify/verify_kits.py kits` on
OCTABAM89_setgate (bank 3), each scenario forked from one load:

- ✅ The load migrates the Parts and writes `kits.work` (CRC holds); no
  stock file rewritten; the firmware's LOG has no new error.
- ✅ PTN+TRIG while playing, while stopped, a program change (channel 1)
  and a three-pattern chain each stage their Kits, repointing Part bytes
  off the playing slot; the engine plays the staged slot after the switch.
- ✅ The chain with a track key every 25 ms for 3 s across the first
  switch (ems-octakit #5), the same sweep across a single PTN+TRIG
  switch, 250 track presses at 180 ms over the chain, and
  a CC 7 every frame for 3,000 frames: no halt, every counter zero.
- ✅ The transport on MIDI start and a 120 BPM MIDI clock (the Rytm as
  master): a PTN+TRIG switch lands on the clock (with MIDI start and no
  clock it does not: the clock is what moves the sequencer); STOP,
  PTN+TRIG, PLAY three times over the chain's patterns, each playing its
  Kit; the chain for 60 s on the clock with a CC every 250 ms across
  tracks 1-8 (CC 7, 46, 47, 55). No halt, every counter zero.
- ✅ LEVEL in LOAD KIT: +3 then −1 moves the cursor two rows; on the main
  screen LEVEL still sets the current track's level (stock).
- ✅ Playing, PATTERN held, TRIG 2 then TRIG 3 tapped one after the other:
  two switches, the held-TRIG mask (`0x460d1ab6`) back at 0, as stock.
- ✅ A slot with no Kit: SAVE KIT opens on the first empty Kit, LOAD KIT
  on UNDO KIT; a Part in record 256 moves to the next empty Kit with the
  patterns noted on it.
- ✅ LOAD KIT while stopped draws the loaded Kit at once (the screen equals
  the one after a further FUNC tap): the load runs stock FUNC+CUE's
  refresh after the Part Reload.
- ✅ LOAD KIT, UNDO KIT, SAVE KIT with the name editor, quick save, the list
  copy / paste / clear and their undos, a pattern copy and paste carrying its Kit (and the undo
  restore, its stock routines called in order: the panel's second
  FUNC+STOP pastes again under the port, on stock too), FUNC+PASTE+PART,
  PTN+FUNC+RIGHT, PTN+FUNC+TRIG paste and its undo.
- ✅ The MKI panel (the port without `--mkii`): FUNC+BANK on the main
  screen opens PATTERN SETTINGS; FUNC+MIDI then FUNC+BANK opens SAVE KIT,
  and a save from it lands; FUNC+BANK again closes it; over the name
  editor it cancels, nothing saved; after LOAD KIT closed by NO, and with
  a list open that is not KITS' (its callbacks pointer poked to stock's
  Part menu table), FUNC+BANK is stock's.
- ✅ SAVE PROJECT writes `kits.work` and `kits.strd`; a second boot of the
  card, a power cycle of it (`--cs1-in`, `--no-post`) and a power cycle
  of a card whose change was never saved each come back with the same
  ASSIGN and RESID.
- ✅ Em's files from the Bottleservice 2026 backup: 64 occupied Kits,
  each name and Part equal to what her format gives, ASSIGN from her
  newest manifest, `kits.work` written, hers left in place.
- ✅ `PROJECT 261004p` (its `bank01.work` rejected by the firmware, her
  files holding one Kit): the load, 400 frames playing and a pattern
  paste, no halt, every counter zero.
- ✅ A project name with no directory: the load runs, the `kits.work`
  write fails and is counted.
- ✅ Cost: a stage that copies one Kit took 133,563 instructions in the
  first build (four whole-Part compares); the compare now runs only on
  slots no track names.

## On the unit

Image A6 (bottleservice), Sam's MKII, 6 Oct 2026. No halt in any of:

- Bottleservice 2026 (Em's `kits3a/b.work`, no `kits.work`): the load
  imports (a pause at its end; not timed), the status line reads `065
  three`, the LOAD KIT list and the patterns play Octakit's Kits.
- A four-pattern chain with track buttons pressed through each switch,
  two to three passes; the same across a single PTN+TRIG switch
  (ems-octakit #5).
- The Rytm as clock and transport master: STOP, PTN+TRIG, PLAY about
  ten times, with bank changes (image A5's halt).
- PROJECT STRAND (its `bank01.work` rejected): load, PLAY, a pattern
  paste, a bank change.
- LOAD KIT then a power cycle without saving; LOAD KIT, SAVE PROJECT,
  a power cycle and a project reload: the loaded Kit each time.
- SAVE PROJECT while playing: playback stops for the save and resumes
  (stock behaviour), no LED flash.
- SAVE KIT with the name editor, quick save, UNDO KIT, FUNC+CUE.

Not run on the unit: an unattended run with the BCR2000.

## Open

- The arranger: its schedule runs in the tick, so its patterns play what
  is resident (counted as CNT_ISR). Not exercised.
- PER TRACK scale and plays-free tracks: how many Parts the engine names
  at once is measured only for the normal case (one).
- PTN+FUNC+TRIG covers the current bank; Octakit's BANK+TRIG > BANK+FUNC+
  TRIG for other banks is not carried. Its clear clears the eight audio
  tracks' steps and locks (`0x40039df4`), not the MIDI tracks.
- `kits.work` is written whole (1.6 MB) when anything changed; Octakit's
  per-record writes are not carried.
- MIDI SCENES' own Part reload hooks are on the stock call sites; LOAD
  KIT calls the reload directly, so his post-reload restore does not run
  for a Kit load (FUNC+CUE goes through his hooks as on stock). A staged
  Kit carries the MIDI scene locks it was saved with in his Part-window
  bytes; whether his table follows a staged slot is not measured.
- Whether the CS1 range holds over a power-off on the unit is read from
  stock's use of CS1 (as PLOCKS P2), not measured.

## Gates

- `tools/verify/verify_kits.py`.
