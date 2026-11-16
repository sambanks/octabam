# LOCK EDIT

[TRIG] + [BANK] in grid recording opens the audio editor on that step's sample, on the SLICE page, with the slice the step plays selected and in view. While the trig is held, the page's encoders edit that slice (stock's: A start, B loop, C end, D height, E pan, F zoom).

Author: [8thmyth](https://github.com/8thmyth). ColdFire only, one linked DRAM unit (`lockedit.s`), no settings.

## What it does

- **Which sample:** the step's sample lock (FLEX or STATIC), else the track's own sample (the Part's slot for its machine). THRU, NEIGHBOR and PICKUP tracks keep stock's [BANK].
- **Which slice** (STRT is the step's lock, else the Part's):
  - **SLIC on, the sample sliced:** slice STRT / 2, at most the last slice. This is the slice the sequencer plays (measured: STRT 8 and 9 both play slice 5).
  - **Otherwise** (SLIC off, or a sample without slices): the frame the sequencer starts the step from, trim start + STRT x trim length / 128 (measured: STRT 64 of a 22050..88200 trim plays from 55125; with SLIC on and no slices it is the same frame, 44100 of 88200). The slice starting there is selected (64 frames of tolerance for grid rounding); with no slice there, the view is centred on that frame (the SLICE page draws no marker without slices).
- **The view:** the selected slice with a quarter of its length of room either side (the editor's own fit, 0x40077138, forced).
- **Stock otherwise:** [BANK] alone, [BANK] outside grid recording, and audio tracks with no editor-able machine are stock's.
- A held trig's lock popup (shown after a long hold on a locked step) is taken down first, so the editor opens over it; while the editor is up a trig's hold event is dropped (`le_trighold`), because the popup it opens would shut the editor. The trig's release leaves the step alone (stock's p-lock store bookkeeping is done as stock does it).

## How

- [BANK]'s press long in both key tables (0x400c00a4, 0x400c0688; stock 0x4007af80, referenced by nothing else) points at `le_bank`.
- The grid TRIG records' hold longs (0x400bfd96 + 26k + 10, stock 0x40060ce0) point at `le_trighold`.
- The editor is opened with stock's own calls: 0x4006de34(type, slot), the page word 0x460e5e5c = 1 (SLICE), 0x4006e160; the slice with stock's select 0x40071668(type, slot, n).
- Read from the step record: STRT at track + 0x59 + 32·step + 1 (the value; 0xff = no lock), the sample lock at + 31. From the Part: STRT at values + 30t + 6m + 1, SLIC at SETUP + 30t + 6m + 1.

## Measured

- Under the ColdFire port (`tools/verify/verify_lock_edit.py`, scenarios `lockedit` and `lock`): the sample lock opens (FLEX slot 2, STATIC slot 3), the track's own sample without one; SLIC off STRT 64 selects the slice holding that frame with room before it; the encoders edit it while held; SLIC on STRT 4, 8, 9 select slices 3, 4, 4 of four (capped); SLIC on with an unsliced sample centres on frame 44100 of 88200; no lock uses the Part's STRT; the trig is released clean and keeps its trig; [BANK] alone and outside grid recording stay stock. With LAZY CHOP in the image, LAZY CHOP arms on, plays and writes the locked slot.
- The STRT byte and the sequencer's start frame were measured under the port: the knob stores STRT 64 as 64; the voice's start (voice + 64) for SLIC off, SLIC on with slices, and SLIC on without slices.
- On 8thmyth's MKI (image OCTABAMHC, remix `test/octabam-lazy-chop`, 14 Nov 2026): STRT locks with SLIC on and off, sliced and unsliced samples, sample locks on FLEX and STATIC tracks. No issues found.

## Inferred / open

- On the MKII the second key table's [BANK] record is patched too; LOCK EDIT's checks ran on an MKI image under the port and on an MKI unit only.
- STRT has 128 positions over the trim, so on an unsliced sample the step can only start on that grid; LOCK EDIT shows where it starts, it does not change it.
