# `pattern-mute` -- PATTERN MUTE

Two mute layers, as on the Digitakt II (manual OS 1.17, section 8.5.3):

| layer | applies | saved |
|---|---|---|
| GLOBAL | every pattern | with the project (`TRACK_MUTE_MASK`, `MIDI_TRACK_MUTE_MASK` in `project.work`), and in the battery SRAM mirror |
| PATTERN | the pattern it was set in | in `pmute.work` beside the bank files (a STORE client), and the current bank's in battery SRAM |

A track is muted when either layer mutes it. Double-press FUNC, with no other key between the two presses, to choose the layer the next mute edit changes (toast `GLOBAL MUTE` / `PATTERN MUTE`). The edit is whichever stock path makes it: FUNC+track key, the MIXER trig keys, MIDI. The layer is kept in battery SRAM and survives power-off (GLOBAL on a unit with empty SRAM). While PATTERN is active the current track's key holds its second LED colour lit as well, so it shows both colours. The stock FUNC press still runs on every press.

## How it works

Stock keeps one mute state per project: bits 8-15 of `0x80000008` (audio tracks 1-8) and of `0x8000000c` (MIDI tracks 1-8), a set bit = muted. Every stock writer of those words is followed by a store to a battery SRAM mirror (`0x100b14d4`, `0x100b14d8`). Those 30 stores are replaced by `pm_mirror_a` / `pm_mirror_m`:

1. read the word stock just wrote (N);
2. the mute bits that differ from the effective word published last go to the layer being edited;
3. the word is republished as GLOBAL OR PATTERN, so MUTE MODE, the LEDs, the MIXER page and MIDI read the effective state without change;
4. the mirror receives N with the GLOBAL layer in its mute bits.

| site | what | hook |
|---|---|---|
| 19 audio + 6 MIDI mirror stores | listed in `manifest.py`; `0x4000fe6c` / `0x4000fe82` clamp the mirror at power-up and are not hooked | `pm_mirror_a`, `pm_mirror_m` |
| `0x40089020`, `0x4008908c` | the project writer's loads of the mute bytes | `pm_save_a`, `pm_save_m` return the GLOBAL layer |
| `0x40062142` | the UI-side pattern commit, after a pattern change and after a project load | `pm_pat_commit` loads the PATTERN layer |
| `0x40088028`, `0x40088084`, `0x400880de`, `0x4008813a`, `0x40088196` | the settings parser's mirror stores at project load | `pm_load_a`, `pm_load_m`: same as the mirror hooks, always the GLOBAL layer |
| `0x40052228` | the UI loop's `jsr 0x400316a0`, the key-repeat tick (60 Hz) | `pm_ui_tick`: while PATTERN, `set_led(id, 6)` for the odd (second colour) bit of the current track's key, then `jmp 0x400316a0`. `0x40052222`, the call before it, is BLACKPYRAMIDS 303's |
| `0x400bfc12`, `0x400c01f6` | FUNC's press record in the MKI and MKII key tables | `pm_func_press`; two presses within 300 ms of the free-run timer DTCN3 (`0xfc07c00c`, 132 MHz) flip the layer when no other key was held between them (`pm_ui_tick` drops a pending press once the panel parser's row states, `0x46100b18`, show another key) |
| STORE's events | `pmute.work` / `pmute.strd` at load, save, store and reload; the CS1 copy at `tocs1` / `fromcs1` | `pm_st_*` (client 11) |

**Layer storage.** Bit 0 of the byte at `0x100b14dd` in battery SRAM. It is the mirror of `0x80000011` in the 22-byte state block (`0x100b14cc`, restored to `0x80000000` at boot and by the new-project reset). Nothing in the image references `0x80000011` or `0x100b14dd` as an absolute address, the power-up sanitiser (`0x4000fe20`) and the reset (`0x40025a90`) skip it, and a `--cs1-in` boot returns a marker written there unchanged.

**Pattern storage.** `pm_tab`, two bytes per pattern of each bank (`bank * 32 + pattern * 2`: the audio tracks, then the MIDI tracks; bit k = track k+1), in the runtime's DRAM. An edit in the PATTERN layer writes it, copies the current bank's 32 bytes to CS1 (`0x100fbdc0..0x100fbdf0`: `PMCS` written last, bank, sum, then the bytes) and sets the bank-edited flags as stock's Part paste does, so SAVE PROJECT runs the bank writer. `pmute.work` (`PMTW`, version 1, 512 B, CRC-32, then `pm_tab`) is written at the bank writer's end and before the project store, copied to `pmute.strd` by the store and back by a reload, and read at every bank load. At power-up the current bank comes from the CS1 copy when it is whole, else from the file. A file that is not that is listed by STORE's refusal prompt and never written over.

**Until 16 Nov 2026** the layer was bit 0 (audio) and bit 1 (MIDI) of byte 40 of each audio track record. That byte is the low byte of the track's one-shot trig mask (steps 1-8): a one-shot on step 1 read as a PATTERN mute of its track, one on step 2 as a mute of the MIDI track, and a PATTERN-layer edit rewrote the bits, so an unmute deleted the one-shot. The check below that found the byte zero was made on a project with no one-shots on steps 1 and 2 (sambanks/octabam#1143, 8thmyth: measured on an MKI over REMOTE and under the port). The same report found the double-FUNC switch firing in ordinary use: FUNC+track or FUNC+trig twice within 300 ms flipped the layer.

## Measured (stock 1.40C under the port, `OCTABAM89_setgate`)

- Byte 40 is zero in all 2,048 audio track records of the project. A SAVE PROJECT round trip returns it unchanged in all 128 records of the bank saved; offsets 95, 2150 and 2200 of the same records are rewritten, and so are the pattern chunk tail bytes +5, +7, +8. **Retracted as a basis for storage (16 Nov 2026):** byte 40 is the one-shot mask's low byte; the project had no one-shots on steps 1-2 (#1143).
- The current bank's CS1 pattern copy at `0x1001614e` equals the RAM bank byte for byte.
- The panel parser's row states (`0x46100b18`, 8 bytes): FUNC sets `0x20` of row 5, T2 `0x02` of row 2, trig 1 `0x01` of row 0 while held, and clears them on release (stock 1.40C under the port, 17 Nov 2026).
- A lone FUNC tap and a double FUNC tap change no mute word and no LED row on stock. FUNC+Tn toggles bit 8+n-1 per press.
- FUNC's press handler is called with edge 1 on each press (stack: return, code `0x2d`, edge); the stock double-press filter (`0x40040250`, edge 3) does not run for FUNC.
- Boot with valid SRAM writes nothing to `0x100b14dc..0x100b14df`; boot with empty SRAM zeroes them (the layer is then GLOBAL).
- Project load writes the mute words from `TRACK_MUTE_MASK` and `MIDI_TRACK_MUTE_MASK` (`0x40088022`..`0x40088196`).

## Gate

`tools/verify/verify_pattern_mute.py` (port, one load of the project, forked scenarios; 16 checks). It writes `TRACK_MUTE_MASK=127` and `MIDI_TRACK_MUTE_MASK=255` into its copy of the project and a one-shot trig on steps 1 and 2 of every audio track of the current bank's first two patterns, so any project with pattern A01 current serves; CI runs it in octabam's `(project)` unit on the generated project. 17 Nov 2026, on `test/pattern-mute` with a fresh project: all 16 pass; with `pm_others` returning 0 (no other-key check) the `combo` case fails (layer 1). It checks: GLOBAL edit with the one-shots muting nothing, layer flip, FUNC+T1 then FUNC+T2 inside 300 ms leaving the layer, PATTERN edit (word = GLOBAL OR PATTERN, mirror keeps GLOBAL, `pm_tab` and its CS1 copy hold the bit, bank marked edited, every one-shot unchanged), switching to another pattern and back, the MIDI word, the LED hold (countdown and the bitmap bit in PATTERN, none in GLOBAL), SAVE PROJECT (`PMUTE.WORK` holds the PATTERN bit, the bank file keeps the one-shots, `TRACK_MUTE_MASK` stays 127), and a reboot on the saved card and SRAM image (layer 1, GLOBAL `0x7f00`, PATTERN `0x8000`, LED held). Until 16 Nov 2026 it had 13 checks and no one-shots in its fixture, so the storage overlap (#1143) passed. `pattern-mute-modes` (beside MUTE_MODES), `octabam` and `octabam-bus` build with it.

## Inferred, not measured

- The layer indicator assumes a track key is a two-colour LED, as `tools/panel/KEYMAP.md` reads the even/odd LED bit pair. The port reports the LED bit and its countdown; the colour on the key is not seen. No purple.
- A restore of the words by `memcpy`
- A set bit = muted: the frame builder's solo path (`0x40004e0a`) silences a track whose mute bit is set, and the test project's `TRACK_MUTE_MASK=127`. The port has no audio path.

## Changed by the move out of the pattern record (#1143)

- A pattern copy no longer carries its PATTERN mutes: they belong to the pattern slot, not the pattern data.
- A project saved under 0.4 brings no PATTERN mutes: the bits it holds in byte 40 are one-shot trigs, and are left to be one-shots.

## Not done

- Key LEDs do not blink for a muted track that has trigs, and show the layer only on the current track's key.
- The stock "unmute the current track while it records" (`0x4005e432`) follows the active layer, so a track muted by the other layer stays muted.
- An edit in one layer cannot unmute a track the other layer mutes.
