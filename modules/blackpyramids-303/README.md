# `blackpyramids-303` -- BLACKPYRAMIDS_303

A TB-303 voice as a track machine, shown as **BLKPYRAMD**: on the DSP56300 in 24-bit fixed point, its filter 4x oversampled at 176.4 kHz; built on Robin Schmidt's Open303 and recalibrated on the TB-303's own circuit against recordings of a real 303. One voice per DSP core (T1-T4, T5-T8), upstream of the track's stock AMP, FX1 and FX2. The sixth row of a track's machine list. The OT's own sequencer plays it: trigs are notes, p-locked `PTCH` a melody, a p-locked `ACC` an accent (the `ACC` knob scales them all), slide trigs slides, trigless trigs and locks after a note tie it. The track key, the chromatic keys (four octaves, `[PAGE]` the 17th note) and MIDI play it live. SRC: `PTCH` (C0-C8, note names, `[FUNC]` + turn or push + turn by octaves, on every held trig too) `CUT` (0-100 the real 303's range, 101-127 an octave beyond) `RES` `ENV` `DEC` `ACC` (`RES`, `ENV`, `ACC` the real 303's ranges); SETUP: `WAVE` `TUNE` `SLID` `GATE` `VOL`. The track is stored as FLEX plus a signature, so a stock OS opens the project with it as a FLEX track.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `c66cf6f`). `Kind.HYBRID`. One DRAM unit (`bp_runtime.s`, the ColdFire runtime generated from the author's C and assembly), 44 detours, 7 pokes, one `SymbolRef` (the FLEX renderer), and a DSP source integrate step (`bp_image.py`, through `Module.dsp_source`, as ANALOG BD's `tools/build/ab_image.py`): the voice over SPRING REV's P words, DARK REV's helper moved, the source seam, SPRING's X records and dispatch.
`upstream/octabam-modules/blackpyramids-303/README.md` is the full description.

A remix with it gives up SPRING REV and carries no DSP module and no other source machine; the build refuses them. A Part that still names SPRING REV shows SPRING's page and passes audio through, as with ANALOG BD.

## Credits

Built on [Open303](https://github.com/RobinSchmidt/Open303), Robin Schmidt (MIT): its filter, oscillator and envelope algorithms. The recalibration's values come from the TB-303's circuit (Roland's service notes, the x0xb0x schematics, Robin Whittle's notes) and Din Sync's recordings of a real TB-303 (measurement only). The machine registration follows repeat98's ANALOG BD (`modules/analog-bassdrum`). The design, the calibration and the voicing (by ear), the sequencer and live-play plumbing and the hardware testing: Zac Kyoti.
