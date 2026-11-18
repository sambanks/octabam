# DARK MODE

System-wide high-contrast Dark Mode for Elektron Octatrack MKI & MKII.

Author: [8thmyth](https://github.com/8thmyth). ColdFire only, one linked DRAM unit (`darkmode.s`). Setting in BRAIN: `DARK MODE`.

## Using it

- **Live Brain Setting**: `MAIN MENU > BRAIN > SETTINGS > DARK MODE` > `DARK MODE` (default 0 / OFF).
  - `0`: Stock light mode (black on white).
  - `1`: High-contrast Dark Mode (white graphics and text on deep black).
- **Takes Effect Live**: Configured as `Apply.LIVE` — changing the setting in the Brain menu or editing `BRAIN.TXT` on the CF card switches the display theme immediately without requiring a reboot.
- **System-Wide Coverage**: Inverts all UI layers and pages consistently:
  - Main sequencer pages, track parameters, and trigs.
  - Mixer and audio levels.
  - Audio Editor (AED) slice grid and sample waveforms.
  - Arranger window and playback cursor.
  - Setup menus, project settings, and dialog popups.
  - Community extensions including Step View (8-track and 16-track matrix).

## How

Hooks the display compositor flush routine at `0x40013cae` (displacing 6-byte instruction `moveal 0x400b9710,%a5` with a jump detour to `dm_flush_hook`). This executes immediately after the page plane and all window layers (Mixer, Audio Editor, Arranger, Menus, Popups, Step View) have finished compositing into the 1,024-byte backbuffer (`0x400b9710`), and right before the diff-and-send loop transmits changed blocks to the LCD controller over UART1.

When Dark Mode is enabled (`get_dark_mode %d0` returns non-zero), `dm_flush_hook` inverts all 256 longwords (1,024 bytes) of the backbuffer in a fast 64-iteration unrolled ColdFire loop (`movel %a0@,%d1; notl %d1; movel %d1,%a0@+` x 4, `subql #1,%d0; bpls .Ldm_loop`). Execution cost is ~30 microseconds per frame. When disabled (`0`), the inversion is completely bypassed.

## Measured

| where | build | result |
|---|---|---|
| the ColdFire port | `tools/verify/verify_dark_mode.py` gate | 1,024-byte bitwise inversion verified; stock detour bytes `2a79400b9710` verified; dynamic `remix.inc` macro verified; setting bypass verified |
| 8thmyth's MKI | `OCTATRACK_METALSV7.bin` to `OCTATRACK_METALSV9.bin`, 18 Nov 2026 | Inverts all pages cleanly; zero freeze or bus stall; live USB telemetry healthy; tested across Main, Mixer, AED, Arranger, and Step View |

## Notes on Hardware & Contrast

- On physical Octatrack MKI hardware (transflective STN LCD), dropping the physical LCD contrast by 1–2 notches in `[PROJECT] > SYSTEM > PERSONALIZE > LCD CONTRAST` eliminates crystal cross-talk, significantly sharpens white text, and eliminates vertical shadow trails.
