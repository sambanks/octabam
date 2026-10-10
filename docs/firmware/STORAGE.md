# The card, the project files and the slots

OS 1.40C, ColdFire side, above the ATA stack (`ARCHITECTURE.md` section 5): the
filesystem vtable, the sample-slot loader and its status records, where a
Part lives, and what the unit writes to the card. Read by nordseele for
octalab ([`nordseele/octalab-notes`](https://github.com/nordseele/octalab-notes),
MIT, findings only; read here 13 Sep 2026 at commit `40ffa53`, again 23
Sep 2026 at `e0dc56d`) on an Octatrack MKI, and re-read here where marked.

Status key as `CHIP.md`: ✅ measured on their MKI or read from our image ·
🟡 adopted on their evidence.

## 1. The filesystem layer (nordseele's `FS_LAYER.md`) ✅

A 23-slot FS vtable `0x46c823fa..0x46c82452`, three implementations
installed by `0x40014524` / `0x40014636` / `0x40014750`, variant B runs
(the load path's open `0x4001b724` in slot 0); `0x46c8242a` `open(path,
mode) → fd`, `0x46c823fa` existence probe, `0x46c8241e` file size;
`0x46c82456` is the bank pointer, not a slot. `0x40090a14` = recursive
directory walker `walk(path, *dirs, *files, mode, progress)`, stacks
`0x46070e44`/`0x46038e40`; 🟡 `mode == 0` calls `0x46c8241a` per file and
`0x46c8243a` per directory (unlink/rmdir; never call mode 0 on a card you
care about); it enumerates a whole directory before the callback.
Buffered primitives `0x40016864` open, `0x400166b8` write, `0x4001677c`
close (the `.wav` writer above them is `SAMPLE_SAVE.md`).

A directory record is 0x140 bytes (filled by the resolve-path / next-entry
slots): name at `+0`, FAT attribute byte at `+0x10d` (0x10 = directory),
first cluster the LONG at `+0x11e`. The walker keeps the record at
`sp+0x2a`, tests `+0x10d` and hands `+0x11e` to the iterator slot
`0x46c82442` (`0x40090a98..0x40090aaa`, re-read here 23 Sep 2026 ✅). The
word at `+0x120` is that long's low half: enough on FAT16, wrong on a
FAT32 card for any folder past cluster 65535 — a folder copied late to a
32 GB card was not listed (nordseele, MKI ✅).

## 2. Slot loading (nordseele's `SLOT_LOADING.md`, MKI) ✅

`0x40093980(slot, keep_trim)` has one caller (case 1 of `0x4008445c`),
followed by post-load (`0x40099148(0, slot)` / `0x40099680`),
`0x40093468(-1)` (re-arm eight tracks' voices) and `0x4009da20(-1)`
(refresh); the loader alone gives a slot that shows name and size, no
BPM, no preview, no trig. Status record `0x46c90a78 + slot*0x2c` (`+0x08`
state 0/2/3, `+0x0c` code, `+0x24` handle; `-0x10` INVALID FILENAME,
`-0x1e` INVALID FILETYPE). CLEAR SLOT `0x40025288(kind, slot)` =
`0x40093814(slot)` then zero the 0x448 record (skipping the first leaks
the handle: MAX OPEN FILES). STATIC settings `0x100d5b30`, FLEX
`0x100b14f0`, stride `0x448`.

## 3. A Part lives three times (nordseele's `FINDINGS.md`, MKI) ✅

Working `bank + 0x8ed80 + part*0x18b2`, saved `bank + 0x9504a + …`, SRAM
`0x100a4ece + part*0x18b2` (the copy that survives a power cycle;
patterns' at `0x1001614e`). A bank write alone is lost at boot.
`0x40029a4c(src, part)` writes both, sets `bank + 0x95048` / `0x100b145e`,
and re-applies with `0x40009094(bank, part)` (also copies scenes A/B at
`part + 0x10/0x11` into `0x80000ed4`). The page arrays inside a Part are
`PARAM_PAGES.md` section 5.

## 4. The card from the host (nordseele's `PROJECT_FILE.md`, MKI) ✅

`PATH=` bare, no quotes; the unit writes nested STATIC paths itself (❌
retracted 13 Sep 2026: "a STATIC PATH must be bare, `../AUDIO/…` loads
empty" — the empty slot is one with no `markers.work` record).
`TRIM_BARSx100 = 100 × 2^round(log2(seconds × tempo24 / 24 / 240))`,
capped 3200 (🟡 cap from one point), never cloned. `markers.work`: 16-byte
header `FORM 00000000 DPS1SAMP`, 264 records × 784 B (136 flex incl. 8
recorders, then 128 static), 8-byte trailer ending in `sum(body) &
0xffff`; STATIC slot n at `16 + (136 + n − 1) × 784`, frame count at `+10`
(4 bytes BE). A slot with no record falls back to 64 frames, writes
`TRIM_BARSx100=0` on the next save, shows the minimum tempo, and neither
trigs nor previews. The unit auto-saves the loaded project continuously
and its RTC runs behind wall clock (compare content, not mtimes).
`project.work` has no checksum; bank files do. octalab's `[META]` signs
`OS_VERSION=R0178     OLAB<n>`. `tools/hw/ot_project.py` never writes
`markers.work` and has no trim command in this tree.

How the firmware reads it (Tim Hastie, 22 Sep 2026, PC and write watches
under the port on stock 1.40C;
`git show 666b6154:docs/firmware/COLDFIRE_PORT.md` O24) ✅:
- The project load's markers parser (`0x40086396`, in `0x40086xxx`) reads
  `PROJECT/markers.work` field by field: his reading is a 22-byte `FORM …
  DPS1SAMP` sub-header, 264 records of 784 bytes (FLEX 1..136, 129..136
  the recorder buffers, then STATIC 1..128: trim start, trim end, loop
  point, 64 slices × 3, a count), and a trailing u16 = the byte sum of the
  sub-header and every record (−54 on a mismatch). The unit keeps a second
  copy, `markers.strd`.
- The sanitiser at `0x400994b4` (`0x40099448..94b8`) writes `end =
  min(length, max(trim_end, start + 64))` into the slot's settings record
  (`0x100b14f0 + 0x448·slot` FLEX, `0x100d5b30 + …` STATIC; trim at `a4 +
  300 + 20·(slice+1)`). The voice start (`0x4000f6e2..f78a`, stores at
  `0x4000f790/f794`) copies that region into the voice struct
  (`0x800049d8 + 0xa8·track`, +40) and pads a trim under 64 frames to 64
  (`0x4000f758..f76c`). The slot STATE records (`0x46c922c4 + 44·slot`)
  hold the file lengths regardless.
- A zero or 64-frame trim therefore plays a 64-frame stub at every trig.
  🟡 The browser's load writes `end` = the file's length (`0x40095d90..5dd8`,
  read from the code, not driven through the browser).

## 5. Project settings 📖 (read from the image, 7 Oct 2026; not run)

`project.work` carries a `[SETTINGS]` block, parsed in `0x40086c00..0x40088288`
(the `TEMPOx24` key is referenced at `0x40086d72`) and written by `0x40088288`
as `KEY=%d` lines after a `# Project Settings` header. In RAM the settings
are bytes from `0x80000000`; each byte is mirrored in CS1 at `0x100b1460 +
(address - 0x80000000)`.

| key | offset from `0x80000000` |
|---|---|
| TEMPOx24 | long `0x20` (the parser calls `0x4009c708` with the value) |
| PATTERN_TEMPO_ENABLED | `0x24` |
| CLOCK SEND / RECEIVE | `0x28` bit 1 / bit 0 |
| TRANSPORT SEND / RECEIVE | `0x2a` / `0x29` |
| PROG CHG SEND / RECEIVE | `0x2b` bit 1 / bit 0 |
| PROG CHG SEND_CH / RECEIVE_CH | `0x2c` / `0x2d` |
| GAIN_CD / GAIN_AB | `0x2e` / `0x2f` |
| DIR_CD / DIR_AB | `0x30` / `0x31` |
| PHONES_MIX | `0x32` |
| MAIN_TO_CUE | `0x33` |
| MASTER_TRACK | `0x34` |
| MAIN_LEVEL / CUE_LEVEL | `0x35` / `0x36` |
| CUE_STUDIO_MODE | `0x37` |
| MIDI_TRIG_CH1..8 | `0x3f..0x46` |
| AUTO_CHANNEL | `0x47` |
| SOFT_THRU | `0x48` |
| AUDIO_TRK CC_IN / CC_OUT / NOTE_IN / NOTE_OUT | `0x49..0x4c` |
| MIDI_TRK_CC_IN | `0x4d` |
| PATTERN_CHANGE_* | `0x4e..0x50` |
| LOAD_24BIT_FLEX, DYNAMIC_RECORDERS, RECORD_24BIT, RESERVED_RECORDER_COUNT | `0x51..0x54` |
| RESERVED_RECORDER_LENGTH | word `0x56` |
| GATE_AB / GATE_CD | `0x58` / `0x59` |
| INPUT_DELAY_COMPENSATION | `0x5a` |
| METRONOME_* | `0x5b..0x62` |
| TRIG_MODE_MIDI x8 | `0x63..` |
| WRITEPROTECTED | long at `0x100f847c` (absolute); the writer returns -53 when it is set |

UI setters found: `0x40067148` (clock send: argument 0 toggles, > 0 sets,
otherwise clears), `0x40067184` (program-change send), `0x400671c0`
(program-change receive), `0x400679a4(delta, wrap)` (TRIG_CH1; one per
channel at +0x40 spacing). The setters of AUDIO CC IN (code at `0x40068112`)
and AUTO_CHANNEL (end at `0x40067994`) were seen without their entries. The
setters write the RAM byte and the CS1 mirror and mark nothing dirty; the
file is written at project save.

