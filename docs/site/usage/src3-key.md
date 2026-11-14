## What it does

On an Octatrack MKI, [MIDI] in the audio editor becomes the SRC3 record key, so you can resample the internal mix without leaving the editor. The MKII already has its own [REC3] key and is left as it is.

## How to use it

1. In the track's RECORDING SETUP, set SRC3 to the source you want to resample.
2. Open the audio editor and press **[MIDI]**: the track's recorder starts recording SRC3. Quantized recording (QREC) applies as usual.
3. Press **[MIDI]** again to stop. The editor stays open throughout.

## Notes

- With SRC3 set to `-`, [MIDI] records nothing and says so.
- Outside the editor, [MIDI] opens the MIDI tracks as usual.
- With lazy-chop.md in LIVE CHOP, [MIDI] starts the recording and TRIG 1 chops it as it comes in.
- To get stock's [MIDI] everywhere, turn off BRAIN > SETTINGS > SRC3 KEY > MIDI = SRC3.
