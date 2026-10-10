# `midi-scenes` — MIDI SCENES

Scene locks for the eight MIDI tracks. `Kind.CF_PATCH`: one linked DRAM
unit (`scenes.s`), 21 detours and two pokes in the OS, nothing on the DSP,
no menu row.

Credit: bkkbrls-del ([midisc](https://github.com/bkkbrls-del/midisc), MIT)
is the original author of the behaviour. This module rewrites it as
readable GNU as, checked against his MIDISC2.1 image under the port
(`tools/verify/verify_scenes.py`), the way `modules/kits` rewrites Em's
Octakit. None of his code or data is copied or linked. `upstream/` (his
repository, a submodule at `4f9a894`) stays in the tree until the last
phase and is not built.

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
| B10, B12–B28, B31–B33 | | later phases |

The mix (`scenes.s`, `mix`) reads scenes A and B from the displayed Part's
assignment bytes (Part `+0x10`, `+0x11`, bank offset `0x8ed90`). For each
track and flat: both sides unlocked, the record takes the Part's value and
nothing is sent; otherwise an unlocked side reads the Part's value and the
result is `A + ((B − A)·w >> 7)` with `w = 127 − (xf & 127)` (weight 0 =
A end, 127 = B end). The result goes to the track record `0x46c76dc0 +
0x44·t + flat` and, when it changed, out through stock's `0x4009eec8`.

## Storage

Phase 1 writes no Part byte, bank file, project file or CS1 byte. MSC (4,096
B), the scene clipboard (256 B) and two mix-state longs are `.data` of the
DRAM unit (`scn_msc`, `scn_clip`, `scn_state`), initialised to `0xff`.
MSC is one table, not one per Part: a Part change does not swap it, and a
power cycle or a project load does not restore it. The `Claims.part_window`
of the 2.0 module (Part `+0x1712..+0x1832`, the LFO designer records;
`docs/firmware/PARTS.md`) is gone, so KITS' `PWSKIP` is 0 beside it.

Phase 2 puts MSC in a project file beside `kits.work`, with a CS1 copy, and
makes a Kit carry its Part's locks.

## Differences from MIDISC2.1 (phase 1)

| 2.1 | here | why |
|---|---|---|
| a lock edit marks the Part unsaved (`bank+0x95048`, `0x100b145e`) and the project dirty (`0x100f8598`), and writes the Part into its saved copy | no flags set | nothing is saved in phase 1; the flags would announce a change `Part Save` does not store |
| the scene clipboard starts as zeros | starts as `0xff` | a PASTE SCENE after an audio-only COPY SCENE gives his table zeros (a lock at 0 on every flat), here none |
| the mix follows the Part the sequencer plays (cached, published at the pattern boundary) | follows the displayed Part | B15–B17 are phase 3; the two are the same Part in every scenario run |
| a context key (the sparse blob's contents) decides whether a mix may reuse its state; the XF-changed test runs only once a mix has run | the XF-changed test only | the key belongs to the Part storage of phase 2 |
| the mix refreshes the MIDI track records' setup bytes (`+0x1e..+0x43`) from the Part | not done | stock's apply already copies them; the Part-change timing is phase 3 |
| trig snapshot (`TRIG_SNAP`) as the unlocked side while a trig plays | the Part's value | B12 is phase 3 |

## Measured

✅ Against the oracle image (stock + `release21.json`, built from upstream
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

Unit size ✅ (`m68k-elf-size` of the `midi-scenes` runtime): 1,558 B of code and 4,360 B of data (MSC 4,096, clipboard 256, state 8). No site needs a ROM-resident target (`docs/firmware/MIDI_SCENES.md` section 9; every detour is a `jmp` or `jsr` into the DRAM unit and the OS ran them under the port).

## Gate

`tools/verify/verify_scenes.py REMIX [--oracle MAIN21.raw]`: scenarios b1,
b2, b7, b7play, b3, b29copy, b29clear on the built image, stock's, and the
oracle's. The docstring says what each compares and what it does not
cover.

## Open

- His freeze twin and sparse blob (Part `+0x1712..+0x1832`) are the LFO
  designer records of audio and MIDI tracks 2-8 (measured under the port, 10
  Oct 2026; `docs/firmware/PARTS.md` section 9,
  `docs/contributing/FAILURE_MODES.md`). The rewrite writes no Part bytes;
  phase 2 keeps the locks in a project file.
- Phase 2: storage and Parts (B19–B27); KITS carries the locks.
- Phase 3: the sequencer sites (B10, B12–B18, B28) and B33.
- Phase 4: `upstream/` and `verify_midiscenes` leave.
- Hardware: the 2.0 build ran on his unit as `ok-ms` (14 Sep 2026); the
  rewrite has not run on a unit.
