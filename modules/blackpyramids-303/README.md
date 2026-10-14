# `blackpyramids-303` -- BLACKPYRAMIDS_303

A TB-303 voice as a track machine, shown as **BLKPYRAMD**: Robin Schmidt's Open303 on the DSP56300, one voice per DSP core (T1-T4, T5-T8), upstream of the track's stock AMP, FX1 and FX2. The sixth row of a track's machine list. The OT's own sequencer plays it: trigs are notes, p-locked `PTCH` a melody, `ACC` an accent, slide trigs slides, trigless trigs and locks after a note tie it. The track key, the chromatic keys (four octaves, `[PAGE]` the 17th note) and MIDI play it live. SRC: `PTCH` (C0-C8, note names, `[FUNC]` + turn by octaves) `CUT` `RES` `ENV` `DEC` `ACC`; SETUP: `WAVE` `TUNE` `SLID` `GATE` `VOL`. The track is stored as FLEX plus a signature, so a stock OS opens the project with it as a FLEX track.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `fee95f5`). `Kind.HYBRID`. One DRAM unit (`bp_runtime.s`, the ColdFire runtime generated from the author's C and assembly), 43 detours, 7 pokes, one `SymbolRef` (the FLEX renderer), and a DSP source integrate step (`bp_image.py`, through `Module.dsp_source`, as ANALOG BD's `tools/build/ab_image.py`): the voice over SPRING REV's P words, DARK REV's helper moved, the source seam, SPRING's X records and dispatch.
`upstream/octabam-modules/blackpyramids-303/README.md` is the full description.

A remix with it gives up SPRING REV and carries no DSP module and no other source machine; the build refuses them. A Part that still names SPRING REV shows SPRING's page and passes audio through, as with ANALOG BD.

## Measured

- Every build re-links the runtime and compares it with the author's own bytes (`reference`, 28,576 B at 0x40a955e0); a difference refuses the build.
- `remixes/test/blackpyramids-303`: both DSP payloads' voice words are the author's standalone image's, and the author's emulator check (`tools/ot303/verify_ot303.py` upstream: the voice on both cores, the sequencer, live notes, the DSP's memory, DARK REV and PLATE REV unchanged) passes on the image.

## On the unit

- 14 Oct 2026: the standalone image on the author's MKI, everything (the voice, the grid, live play, chromatic, FUNC + PTCH octaves).
- This octabam form has not been flashed.

## Credits

The voice: [Open303](https://github.com/RobinSchmidt/Open303), Robin Schmidt (MIT). The machine registration follows repeat98's ANALOG BD (`modules/analog-bassdrum`). The design and the voicing (by ear), the sequencer and live-play plumbing and the hardware testing: Zac Kyoti.
