# `midi-scenes` — MIDI SCENES

Scene locks for the eight MIDI tracks. `Kind.CF_PATCH`: one linked DRAM
unit (`scenes.s`), 21 detours and two pokes in the OS, nothing on the DSP,
no menu row.

Credit: bkkbrls-del ([midisc](https://github.com/bkkbrls-del/midisc), MIT)
is the original author of the behaviour. This module rewrites it as
readable GNU as, checked against his MIDISC2.1 image under the port
(`tools/verify/verify_scenes.py`), the way `modules/kits` rewrites Em's
Octakit. None of his code or data is copied or linked. His repository was a
submodule here (pinned at `4f9a894`, MIDISC 2.0) until 10 Oct 2026; the
build no longer needs it.

Markers as in `CHIP.md`: ✅ measured, 📖 read from the code.

## What it does

Stock keeps scene locks for the audio tracks only (Part `+0x662`: 16
scenes × 8 tracks × 32 B) and bails out of scene editing when MIDI track
mode (`0x80000012`) is set. This module adds a second table with the same
shape, **MSC**: `scene<<8 | track<<5 | flat`, 4,096 bytes, `0xff` = no
lock. `flat` is the MIDI page × 6 + knob (NOTE, LFO, ARP, CTRL1, CTRL2;
`docs/firmware/MIDI_SCENES.md` section 6).

| # | behaviour (MIDISC2.1 numbering) | here |
|---|---|---|
| B1 | MIDI mode, scene A or B held, knob turned: the value goes to MSC for the displayed track; clamped 0..127, ARP LEG 0..1, MODE 0..6, SPD 0..95, RNGE 0..7; the mix runs at the XF | phase 1 |
| B2 | scene held: the knob readout shows that scene's lock | phase 1 |
| B3 | scene held, encoder pressed: that knob's lock cleared | phase 1 |
| B4 | lock LEDs and grey cells read MSC in MIDI mode | phase 1 |
| B5 | a scene pad lights when MSC holds a lock for it (any mode) | phase 1 |
| B6 | per-track and per-page scene-block offsets point at MSC in MIDI mode | phase 1 |
| B7 | XF moved (panel or CC 48): each track's locked parameters go A↔B, CCs sent when the value changes | phase 1 |
| B8 | scene recall completion: mix at the XF | phase 1 |
| B9 | scene pad release: the held flags clear, no mix | stock's own sequence, no site |
| B11 | track `t`'s locks affect track `t` only | phase 1 |
| B29 | CLEAR / COPY / PASTE SCENE rows carry MSC | phase 1 (the gate scenarios need them) |
| B30 | encoder press in MIDI mode: overlay refresh | phase 1 |
| B10, B15–B18, B28 | the mix follows the Part that plays; a panel write re-mixes | `verify_scenes` seq group (`sw`) |
| B12–B14 | trig snapshot as the unlocked side, a trig-locked flat left alone, the CC loop before the note-on | `verify_scenes` seq group (`tg`, `tg2`) |
| B33 | his crash fixes need no counterpart | the module writes no stock bytes outside its listed detours and two pokes, and its scratch is its own DRAM unit (📖 from the manifest) |

The mix (`scenes.s`, `mix`) reads scenes A and B from the displayed Part's
assignment bytes (Part `+0x10`, `+0x11`, bank offset `0x8ed90`). For each
track and flat: both sides unlocked, the record takes the Part's value and
nothing is sent; otherwise an unlocked side reads the Part's value and the
result is `A + ((B − A)·w >> 7)` with `w = 127 − (xf & 127)` (weight 0 =
A end, 127 = B end). The result goes to the track record `0x46c76dc0 +
0x44·t + flat` and, when it changed, out through stock's `0x4009eec8`.

## Storage

One 4,096-byte table per Part: `scn_lib`, 64 slots (bank × 4 + Part) in
`.bss` (262,144 B), filled with `0xff` at first use. Every site reads the
displayed Part's slot in the current bank (`msc_a0`). The scene clipboard
(256 B) and two mix-state longs are `.data`. The module writes no Part byte
(Part `+0x1712..+0x1832` is the LFO designer records,
`docs/firmware/PARTS.md`), so KITS' `PWSKIP` is 0 beside it.

- **`scenes.work`** in the project directory, beside `kits.work`: 16 bytes
  (`MSCW`, version 1, payload length 262,144, CRC-32 of the payload) then the
  64 slots. Written whole after the bank writer and before the project store
  when a lock changed; `scenes.strd` is its copy at the project store and is
  copied back at a project reload. STORE (`modules/store`) supplies the events
  and the file calls. A file with another version, length or a failing CRC is
  never written over (`scn_nowrite`); the banks it would have filled are empty.
  A missing file is empty. A new project is empty and due for writing.
- **CS1 copy**: `0x100fbdf0..0x100ffe00` (16,400 B): `SCS1` (written last),
  the bank, the sum of the bank and every long of the four tables, a reserved
  long, then the current bank's four tables. Rewritten on every edit and when
  stock copies a bank into CS1; at power-up, after stock's restore, it replaces
  that bank's tables when magic, bank and sum hold, and otherwise that bank is
  read from `scenes.work` at the first masked load. Stock keeps an unsaved
  audio scene lock over a power cycle the same way (`docs/firmware/MIDI_SCENES.md`
  section 8). Taken from the top of PLOCKS P2's range (its `NV_MAX` is 4,768).
- **Part Clear** empties the Part's slot. Part Save and Part Reload leave the
  locks as they are (B31 is not carried).
- An edit marks the Part changed the way a stock editor's store does
  (`bank+0x95048`, `0x100b145e`, `bank+0x9b332`, `0x100f8598`, the refresh at
  `0x40027e00`); without that SAVE PROJECT does nothing for the project.

Not done: a Kit carrying its Part's locks (`kits.work` version 2), the
conversion of 2.x projects, the on-unit prompt for a refused file, and Part
Paste and bank-copy rows.

## Differences from MIDISC2.1 (phase 1)

| 2.1 | here | why |
|---|---|---|
| a lock edit marks the Part unsaved and the project dirty, and writes the Part into its saved copy (B31) | the flags are set; no saved-copy write | the locks are in `scenes.work` and CS1, not in the Part |
| the scene clipboard starts as zeros | starts as `0xff` | a PASTE SCENE after an audio-only COPY SCENE gives his table zeros (a lock at 0 on every flat), here none |
| the mix follows the Part the sequencer plays (cached, published at the pattern boundary) | the same, as a target (bank, Part) that follows the displayed Part while the sequencer is stopped | `sw` matches his MIDI out frame for frame |
| a context key (the sparse blob's contents) decides whether a mix may reuse its state; the XF-changed test runs only once a mix has run | a due flag (set by a target change, a load, a Kit load, Part Clear) and the XF-changed test | the tables are in `scn_lib`, not in a Part blob |
| the mix refreshes the MIDI track records' setup bytes (`+0x1e..+0x43`) from the Part | not done | stock's apply already copies them; no scenario differs |

## Measured

✅ Against the oracle image (stock + `release21.json`, built from his repository at
`52eaab0`) under the port (`ot_emu`, OCTABAM89_setgate bank 3 Part 1, T1 a
MIDI track on channel 11), remix `midi-scenes`, 10 Oct 2026: scenarios b1,
b2, b7, b7play, b3, b29copy, b29clear pass every comparison. MIDI out
(bytes and frames, 0 frames apart), the lock table, the track records
`0x46c76dc0..+0x220`, the lock-mask longs and (b2) the LCD plane are
identical to the oracle's; the Part windows are identical to stock's. The
clipboard differs where untouched (table above). The scenario table and
what the compare cannot see (LED rows are identical on stock, the oracle
and this module) are in `docs/firmware/MIDI_SCENES.md` section 11 and the
docstring of `verify_scenes.py`.

On `ok-ms` the same scenarios pass except the LCD plane, whose status line
reads the Kit (`009 ONE`) where the oracle reads `Pt:1 ONE`; the gate skips
the screen compare on a remix with KITS.

Unit size (phase 1, before the library, measured with `m68k-elf-size`): 1,558 B of code and 4,360 B of data; the library adds the code of the storage section and 524,288 B of `.bss`. No site needs a ROM-resident target (`docs/firmware/MIDI_SCENES.md` section 9; every detour is a `jmp` or `jsr` into the DRAM unit and the OS ran them under the port).

## Gate

`tools/verify/verify_scenes.py REMIX [--oracle MAIN21.raw] [--persist]`: scenarios b1,
b2, b7, b7play, b3, b29copy, b29clear on the built image, stock's, and the
oracle's; with `--persist` (not in `make check`; the final batch passes it), on the built image only (MKII panel), the b1 locks through
SAVE PROJECT (`scenes.work` and `.strd`: size, header, CRC-32, the locks), a second
boot, a power cycle after a save and after none (CS1 in, nothing posted), and the
unsaved card without CS1 (the locks are absent). The docstring says what each compares and what it does not
cover.

## Open

- His freeze twin and sparse blob (Part `+0x1712..+0x1832`) are the LFO
  designer records of audio and MIDI tracks 2-8 (measured under the port, 10
  Oct 2026; `docs/firmware/PARTS.md` section 9,
  `docs/contributing/FAILURE_MODES.md`). The rewrite writes no Part bytes
  except in one case: reading a 2.x project (no `scenes.work`), the Part copy
  whose blob held up gets its design area set to what stock Part Clear leaves
  (✅ measured under the port: zeros, the last 16 bytes `0xff`). The original
  designs are not recoverable. The wiped Part is not marked changed; the
  next normal Part save writes it.
- Phase 2: B19–B27 beyond Part Clear.
- B33: 📖 his 2.1 moved the scene scratch off the native clipboard addresses and restored the recorder and master playback descriptors that earlier caves overwrote. This module has no cave in ROM and no scratch at a stock address; whether any other 2.1 crash fix has a counterpart is not checked beyond that.
- The oracle image is not in the repository and is not built by `make`: `verify_scenes.py --oracle MAIN21.raw` (or `OT_MSC21_IMAGE`) takes one made from his repository at `52eaab0` (his own build; not re-run here after the submodule left). `make check` runs the scenarios on our image and stock's.
- Hardware: the 2.0 build ran on his unit as `ok-ms` (14 Sep 2026); the
  rewrite has not run on a unit.
