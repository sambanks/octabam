# SRC3 KEY

MKI only. The Octatrack MKI has no [REC3] key, and its SRC3 combo, [TRACK] + [MIDI], leaves the audio editor. With SRC3 KEY, **[MIDI] pressed while the audio editor is open** is the SRC3 record key, so a resample is one key away while editing or chopping.

Author: [8thmyth](https://github.com/8thmyth). ColdFire only, one linked DRAM unit (`src3key.s`). Setting in BRAIN: `MIDI = SRC3`.

## Using it

- **[MIDI]** in the audio editor starts the current track's recorder with SRC3 only (the source set in its RECORDING SETUP). QREC applies, as for stock's record keys. The popup says `SRC3 RECORDING`.
- **[MIDI] again** stops the take at once, whatever RLEN (`RECORDING STOPPED`).
- If RECORDING SETUP's SRC3 is `-`, nothing records (`SRC3 IS OFF (REC SETUP)`).
- Outside the editor, [MIDI] is stock's (the MIDI tracks).
- With LAZY CHOP open in LIVE CHOP, [MIDI] starts the SRC3 take, TRIG 1 joins it at the record head, and [YES] stops it and writes the slices. In STUDIO CHOP, [MIDI] starts / stops the recording the same way.

**Setting:** BRAIN > SETTINGS > SRC3 KEY > `MIDI = SRC3` (on by default). Off, [MIDI] is stock's everywhere.

**MKII:** nothing changes; the MKII has its own [REC3] key. The MKII key table is left stock, and the code checks the model flag too.

## How

[MIDI]'s press and release longs in the MKI key table (record `0x400c0158`, code `0x35`; both stock `0x40055678`) point at `sk_press` / `sk_release`. In the editor (`0x460e5e4c` non-zero) on an MKI (`0x46c8d18c` = 0) with the setting on, the press posts `0xc010` (SRC3 + start) to the track's recorder through stock's `0x40005178`, or, if the recorder is recording, writes the stop (`0x80`) to its immediate mailbox (`0x46c7e9fa + 4t`) and posts it too; the release is dropped, so stock's MIDI page never opens. Otherwise both go to stock's. LAZY CHOP's key layer, which holds [MIDI] while it is open, calls whatever that press long holds.

## Measured

| where | build | result |
|---|---|---|
| the ColdFire port | `verify_src3_key` scenario `midi` (MKI), alone (`test/src3-key`) and with LAZY CHOP (`test/octabam-lazy-chop`); LAZY CHOP's `mkii` scenario | [MIDI] in the editor starts / stops a SRC3 take, the editor stays; SRC3 `-` records nothing; the setting off and outside the editor are stock; with LAZY CHOP in LIVE CHOP, TRIG 1 joins the take and [YES] stops it; MKII stock |
| 8thmyth's MKI | OCTABAMG6 to OCTABAMHC (`test/octabam-lazy-chop`), 11-14 Nov 2026 | works as above; no issues found |

## Inferred / open

- The editor's waveform redraws while a take records, which looks less smooth than an idle editor; the take itself is unaffected. Stock's record keys in the editor draw the same way (not compared side by side).
