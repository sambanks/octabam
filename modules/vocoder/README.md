# `vocoder` -- VOCODER

A ten-band channel vocoder after the Roland VP-330: the track's audio (a voice) shapes a carrier.

> **It runs on FX2 of tracks 2, 4, 6 and 8 only**, and passes audio through untouched on tracks 1, 3, 5 and 7 and on any FX1 slot. The even tracks, so a NEIGHBOR machine on an even track hands it the odd track's audio before it (T1 drums, T2 NEIGHBOR + VOCODER; T3 into T4, and so on). Until 11 Oct 2026 it ran on tracks 2, 3, 6 and 7; the move to 2, 4, 6 and 8 was heard on the unit (Ignorato's MKII, 11 Oct 2026, OCTABAM25, by ear): T4 and T8 vocode cleanly, with no clicks at trigs; T1, T3 and T7 pass dry; a NEIGHBOR on T2 vocodes T1's drums; T2 and T4 together stable for several minutes. That image predates the `rep` to `do` change below (bit-identical in `dsp_host`); the image with it (OCTABAM27, 18 Oct 2026, by ear) plays the same: a project unchanged from OCTABAM26, no crackle with FILTER or PHASER on T1's FX1 and VOCODER on T2 through SETUP changes on T1 and T2, tracks 1-4 kept playing, T6 and T8 together stable for several minutes, SCAL, RANG and KEY as before. On a MKII two VOCODERs on a DSP core (tracks 1-4 share one, 5-8 the other) play, and a third overran the core (a loud glitch, then no audio and no sequencer until a reboot; OCTABAM7-9, 4 Oct 2026). The real cost is about 850-940 cycles a sample, not the 760 `make cycles` counts (one-word displaced moves measured at about 4 cycles, CHIP.md section 2), and the 3,120 usable already includes the four FX1 FILTERs the pricer does not charge. So the limit is built in rather than documented: a third VOCODER on a core stays dry instead of stalling the unit. It avoids each core's first track (T1, T5). On T1, VOCODER put left-only click bursts into the main out at one phase of the pattern, worst at trigs (measured: Ignorato's MKII, 5 Oct 2026, captured at the main outs; absent with FX2 NONE and on T2 and T3; FAILURE_MODES.md, "Left-only click bursts from VOCODER on T1"). The cause is inferred: an effect at a core's position 0 finishing before the ColdFire's pull, as in "Junk on main R ... T1 with BusDelay", though that entry is main R and 16-24 samples of junk. T5, core 0's first track, is excluded by analogy, not measured.

On the unit it is an FX2 effect. Put it on track 2, 4, 6 or 8, playing a voice, sample or live through a THRU machine: with MODE INT the carrier is built in, two sawtooths an octave apart at NOTE, so turning NOTE (or parameter-locking it on the steps) plays the vocoded voice as a melody. Version 0.2 puts the performance controls on page 1, where scenes, the crossfader, LFOs and p-locks reach them: BEND (the fader as a pitch wheel), GEND (from a male to a female voice) and WHSP (singing to whispering). With MODE EXT the carrier is the track's right channel: a THRU track with the voice on input A and a synth on input B. [`DESIGN.md`](DESIGN.md) has the law and the reasons; [`vocoder_ref.py`](vocoder_ref.py) is the float reference the DSP is proved against.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | NOTE | C1..C6 | the built-in carrier's pitch, shown as a note; parameter-lock it to play a melody; default C3 |
| 1 | 1 | BEND | -64..+63 | pitch bend on NOTE, -12 to +12 semitones with RANG 12ST (3/16 of a semitone a step, smoothed; RANG sets the reach); never quantised; a scene on each side of the crossfader makes the fader a pitch wheel; default 0 |
| 1 | 2 | GEND | -64..+63 | formants: the voice is analysed off the synthesis bands, so every formant comes out scaled, x0.84 (-3 semitones: a bigger, male voice, at -64) to x1.41 (+6: a female one, at +63); each step above the centre is twice one below it; with BEND an octave up and a little WHSP, one fader goes from a male to a female voice; smoothed over 8 ms; default 0 |
| 1 | 3 | WHSP | 0-127 | whisper: the built-in carrier from the sawtooths (0) to white noise at the same level (127); smoothed over 8 ms; default 0 |
| 1 | 4 | DRY | 0-127 | the dry voice mixed in; smoothed over 8 ms; default 0 |
| 1 | 5 | CONS | 0-127 | consonants: the voice above 4 kHz passed through, as the VP-330's high-consonant circuit does; smoothed over 8 ms; default 48 |
| 2 | 6 | MODE | INT, EXT | the carrier: INT the built-in sawtooths at NOTE; EXT the right channel |
| 2 | 7 | SCAL | CHRO, MAJ, MIN, DOR, PHRY, MIXO, HMIN, PMAJ, PMIN, BLUE | NOTE's scale: NOTE snaps to the nearest note of the scale at or below it (CHRO: every semitone, as before); MIN is natural minor, HMIN harmonic minor, PMAJ and PMIN the pentatonics, BLUE the six-note blues scale; default CHRO |
| 2 | 8 | GLDE | OFF, 30, 80, 200, 500 | glide on NOTE and BEND, in ms (a log-pitch time constant); OFF is 8 ms, which smooths BEND's steps; with a scale it glides between the snapped notes |
| 2 | 9 | RANG | 12ST, 6ST, 24ST | BEND's reach: +-12 semitones (as before), +-6, +-24; default 12ST |
| 2 | 10 | KEY | C, C#, D .. B | the scale's root; no effect with SCAL CHRO; default C |

**The snapping rule.** With a scale chosen, NOTE plays the nearest note of the scale at or below the knob's semitone, so a sweep up never goes down and every scale note is reached by the knob value that names it. The display still shows the knob's own note (C#3 in C MAJ plays C3). At the bottom, a NOTE under the key's first scale note drops to the scale note below C1 (at most 2 semitones: C1 in D MAJ plays B0). The pitch then adds BEND, smooth, at RANG's reach.

**The pitch's limits.** P = snapped NOTE + BEND is held between C0 (16.35 Hz, where the polyBLEP's 1/du fills its Q23 word) and just under C8 (OCT's top octave). With RANG 24ST, a NOTE under C2 bent down past C0 holds at C0 (C1 fully down would be C-1); the top, C6 with BEND +63 at 24ST, is 23.6 semitones up (4,096 Hz) and stays inside, so the upper clamp is a guard only. Up there the 4' sawtooth is at 8.2 kHz and only the 4 kHz and 6 kHz bands carry the carrier, so the sound thins; the aliasing in the bands is 53 dB under the carrier's harmonics there (the reference, 18 Oct 2026; 56 dB at 12ST's top, C6 + 11.8).

**Old projects.** Slots 7, 9 and 10 were blank in 0.2 before the selectors, so a part saved then holds 0 there: CHRO, 12ST and C, which play exactly what that part played (bit for bit in `dsp_host`, below).

There is no level knob (0.1 had LEVL): the track's AMP page sets the level. NOTE, BEND, GLDE and WHSP shape the built-in carrier, so with MODE EXT (the carrier is input B) they do nothing; GEND acts on the voice and works in both modes (checked in `dsp_host`: in EXT, BEND and WHSP leave the output bit-identical, GEND changes it).

**A project saved under 0.1 needs its defaults re-stamped.** 0.2 moved CONS, DRY and LEVL and put BEND, GEND, WHSP and GLDE in their slots, so a 0.1 part feeds 0.2 its old bytes: LEVL's 100 lands on WHSP and the voice turns to noise. Run `tools/hw/ot_project.py stamp-defaults <project> vocoder` on the card before playing it (AGENTS.md, "A part saved under an older slot layout").

The modulator is the left and right channels averaged (INT), or the left channel (EXT). The output is mono, on both channels.

## Open

- The VP-330's ensemble (a bucket-brigade chorus on its output) is not modelled; a chorus on the Octatrack's FX would come after FX2's output only on another track.
- More than two per core: getting four to fit beside four FILTERs needs under about 590 real cycles each; until then the limit is built in.
- The pricing gap is worth reporting upstream: displaced moves and table reads counted as one cycle, and FX1 FILTERs not charged against a budget that contains them.

## Design

[`DESIGN.md`](DESIGN.md): the VP-330 as documented, why the bands are steep, what the 24-bit version changed and why, the r7 slots and the tables.
