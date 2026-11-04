# `blackpyramids-303` -- BLACKPYRAMIDS_303

A TB-303 voice as a track machine, shown as **BLKPYRAMD**: on the DSP56300 in 24-bit fixed point, its filter 4x oversampled at 176.4 kHz; built on Robin Schmidt's Open303 and recalibrated on the TB-303's own circuit against recordings of a real 303. One voice per DSP core (T1-T4, T5-T8), upstream of the track's stock AMP, FX1 and FX2. The sixth row of a track's machine list. The OT's own sequencer plays it: trigs are notes, p-locked `PTCH` a melody, a p-locked `ACC` an accent (the `ACC` knob scales them all), slide trigs slides, trigless trigs and locks after a note tie it. The track key, the chromatic keys (four octaves, `[PAGE]` the 17th note) and MIDI play it live. SRC: `PTCH` (C0-C8, note names, `[FUNC]` + turn or push + turn by octaves, on every held trig too) `CUT` (0-100 the real 303's range, 101-127 an octave beyond) `RES` `ENV` `DEC` `ACC` (`RES`, `ENV`, `ACC` the real 303's ranges); SETUP: `WAVE` `TUNE` `SLID` `GATE` `VOL`. The track is stored as FLEX plus a signature, so a stock OS opens the project with it as a FLEX track.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `c66cf6f`). `Kind.HYBRID`. One DRAM unit (`bp_runtime.s`, the ColdFire runtime generated from the author's C and assembly), 44 detours, 7 pokes, one `SymbolRef` (the FLEX renderer), and a DSP source integrate step (`bp_image.py`, through `Module.dsp_source`, as ANALOG BD's `tools/build/ab_image.py`): the voice over SPRING REV's P words, DARK REV's helper moved, the source seam, SPRING's X records and dispatch.
`upstream/octabam-modules/blackpyramids-303/README.md` is the full description.

A remix with it gives up SPRING REV and carries no DSP module and no other source machine; the build refuses them. A Part that still names SPRING REV shows SPRING's page and passes audio through, as with ANALOG BD.

## Measured

- Every build re-links the runtime and compares it with the author's own bytes (`reference`, 39,736 B at 0x40a955e0); a difference refuses the build.
- `remixes/test/blackpyramids-303`: both DSP payloads' voice words are the author's standalone image's, and the author's emulator check (`tools/ot303/verify_ot303.py` upstream: the voice on both cores, the sequencer, live notes, the DSP's memory, DARK REV and PLATE REV unchanged) passes on the image. For the 936 / 932-word voice (3 Nov 2026) the author ran it on the standalone image: every check equal to the previous FINAL's.

## On the unit

- 14 Oct 2026: the standalone image on the author's MKI, everything (the voice, the grid, live play, chromatic, FUNC + PTCH octaves).
- 16 Oct 2026: the author's FINAL standalone (accents per step, push-turn octaves, equal-loudness WAVE, driven-VOL headroom, a RES trim below 20) on the author's MKI: all good.
- 3 Nov 2026: the author's FINAL standalone with the same voice 90 words smaller (output bit-exact, 936 / 932 words; mainos `5b7dfb2f…`) on the author's MKI: all tests pass. This octabam form of it is not flashed.
- 21 Oct 2026: the author's FINAL standalone with the recalibrated voice (mainos `ecc85887…`) on the author's MKI: all good; then this octabam form of it (`remixes/test/blackpyramids-303`): all good.
- 19 Oct 2026: this octabam form (`remixes/test/blackpyramids-303`), with the previous voice, on the author's MKI. The first build worked well, except that switching the track to another machine and back reset BLKPYRAMD's knobs to the defaults, which no stock machine does. With the fix, every check passes: the knobs are kept away and back, and after a save and power cycle, and SRC SETUP's BLKPYRAMD row edits them.

## Credits

Built on [Open303](https://github.com/RobinSchmidt/Open303), Robin Schmidt (MIT): its filter, oscillator and envelope algorithms. The recalibration's values come from the TB-303's circuit (Roland's service notes, the x0xb0x schematics, Robin Whittle's notes) and Din Sync's recordings of a real TB-303 (measurement only). The machine registration follows repeat98's ANALOG BD (`modules/analog-bassdrum`). The design, the calibration and the voicing (by ear), the sequencer and live-play plumbing and the hardware testing: Zac Kyoti.
