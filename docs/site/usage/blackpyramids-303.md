BLKPYRAMD is a TB-303 synthesizer voice implemented as a track machine. It runs on the DSP in 24-bit fixed point with a 4× oversampled filter at 176.4 kHz, based on Robin Schmidt's Open303 and calibrated against the TB-303 circuit and hardware recordings. You can run one voice per DSP core (one on tracks T1–T4 and one on tracks T5–T8), routed ahead of the track's stock AMP, FX1, and FX2 stages.

## Access

BLKPYRAMD appears as the sixth entry in a track's machine list. Double-tap the track key, or press [FUNC] + [SRC] and open MACHINE.

![SRC SETUP with BLKPYRAMD: WAVE, TUNE, SLID, GATE, VOL.](../../img/blackpyramids-303/setup.png)

## Controls

![BLKPYRAMD source controls: PTCH, CUT, RES, ENV, DEC, ACC.](../../img/blackpyramids-303/source.png)

The brackets above the knobs group CUT with RES and DEC with ACC to show which pairs shape the filter sweep together.

| Page | Knob | What it does |
|---|---|---|
| SRC | PTCH | Note pitch (C0–C8 by name); hold [FUNC] while turning to step by octaves |
| SRC | CUT | Filter cutoff: 0–100 covers the full TB-303 range evenly; 101–127 extends one octave higher (to about 3.2 kHz), where maximum resonance is slightly reduced |
| SRC | RES | Filter resonance across the TB-303's range, scaled linearly |
| SRC | ENV | Filter envelope modulation depth across the TB-303's range |
| SRC | DEC | Filter envelope decay time (50 ms to 2 s) |
| SRC | ACC | Accent scaling for accented steps: 127 applies each lock's full accent amount (matching a real TB-303), 0 disables accents, scaled linearly |
| SETUP | WAVE | Continuous equal-loudness blend from saw (0) to square (127) |
| SETUP | TUNE | Master tuning (A4 = 400–480 Hz; 64 is 440 Hz) |
| SETUP | SLID | Slide time (0–198 ms; default 73 matches the TB-303) |
| SETUP | GATE | Note length, calculated as (GATE + 1)/128 of a step (default 74 matches the TB-303) |
| SETUP | VOL | Output level: 0 is silent, 1–64 is clean, and 65–127 drives into soft clipping up to about +7 dB (default 99 is about +5 dB) |

## Playing it

- Each trig plays a note using the current knob settings for that step. Use parameter locks on PTCH for melodies and on ACC for accents.
- Slide trigs glide smoothly to the target note without retriggering the envelope. Placing trigless locks or trigless trigs immediately after a note ties it across steps.
- Consecutive accented steps stack into the characteristic rising 303 accent sweep.
- You can play notes live while holding the track key, the chromatic trig keys (spanning four octaves of absolute notes, with [PAGE] as the 17th key), or incoming MIDI notes. Press TRIG + YES to preview a step.
- SLOTS and SLICES modes do not apply to this machine, so their LEDs remain off.

## Notes

- Underneath, a BLKPYRAMD track is stored as a FLEX track. Stock OS opens the project with the track set to FLEX, and switching the track back to another machine restores its FLEX values.
- Like other machines, BLKPYRAMD retains its parameter values when you switch a track to another machine and back. Even while another machine is active on the track, highlighting BLKPYRAMD in [FUNC] + [SRC] lets you view and edit its saved SETUP parameters.
- Because the synth engine uses SPRING REV's DSP memory slot, SPRING REV is unavailable in remixes that include BLKPYRAMD. Any Part that still references SPRING REV shows its parameter page but passes audio through dry.
- When paired with SCALE QUANTIZER, a BLKPYRAMD track retains its four chromatic octaves and keyboard layout while other tracks follow the quantizer. That pairing has not yet been tested on hardware.
