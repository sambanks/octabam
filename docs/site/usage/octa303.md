**OCTA-303** is a circuit-modelled Roland TB-303 synthesizer machine (one
voice per track). It requires no sample, replaces no stock effect, and is
fitted to recordings of a real TB-303 (Din Sync's x0xb0x reference set).

## Limit

A Part supports at most two OCTA-303 tracks (or two tracks total across
OCTA-303 and [WAVE](wavecf.md) when both are installed). Choosing OCTA-303 for
a third track displays `MAX 2 OCTA-303` (or `MAX 2 MACHINES` when WAVE is
present) and assigns FLEX instead. If a loaded project has more than two, the
extra tracks load as FLEX. Each playing voice uses a large share of the CPU,
and running more than two causes the front panel to stop responding while
audio keeps playing.

## Access

Double-tap [TRACK] to open the machine list, select **OCTA-303** (below
PICKUP, or below ANALOG BD when [Analog BD](analog-bassdrum.md) is also
installed, with the list scrolling to it), and press [YES]. [FUNC] + [SRC]
opens the same list; on a track with a sample it opens the sample list first,
and pressing [LEFT] switches to the machine list. A new OCTA-303 track starts
with TUNE at C3, CUT/RES/ENV/DEC at 64, and ACC at 0.

![SRC SETUP with OCTA-303: WAVE, GATE, FINE, SLID, DRIV, ACCV.](../../img/octa303/setup.png)

## Controls

![OCTA-303 source controls: TUNE, CUT, RES, ENV, DEC, ACC.](../../img/octa303/source.png)

| Page | Knob | What it does |
|---|---|---|
| SRC | TUNE | note pitch, C1–C5 by name |
| SRC | CUT | filter cutoff (TB-303 CUTOFF FREQ law) |
| SRC | RES | filter resonance |
| SRC | ENV | envelope modulation depth |
| SRC | DEC | decay time, ~0.13–2.4 s |
| SRC | ACC | accent amount, applied on steps with an ACC lock |
| SETUP | WAVE | SAW, SQR, SAW+D, SQR+D (+D adds a distortion pedal after the VCA) |
| SETUP | GATE | OFF lets the AMP page shape the note; 303 uses the TB-303 gate (3.5 of 6 clocks), tied into slides |
| SETUP | FINE | fine tune, ±½ semitone |
| SETUP | SLID | slide time (0 matches the TB-303) |
| SETUP | DRIV | output drive into a soft ceiling, up to +18 dB |
| SETUP | ACCV | accent loudness (64 matches the calibrated TB-303) |

## Playing it

- **Accent:** parameter-lock ACC on the steps you want accented; the ACC knob
  sets the accent amount.
- **Slide:** place a trigless trig or trigless lock ([FUNC] + [TRIG]) on the
  next step. As soon as you place it, it copies the note from the previous
  trig or slide as its TUNE lock, tying the note as on a TB-303. Hold the step
  and turn TUNE to slide to a different pitch. A step that already has a TUNE
  lock keeps its existing pitch.
- **Octave up / down** (like the TB-303's UP and DOWN): in GRID RECORDING,
  hold one or more trigs and press [UP] or [DOWN] to shift each held step's
  TUNE by an octave. Steps without a TUNE lock start from the track's TUNE, and
  notes outside C1–C5 stay unchanged. The screen shows the resulting note (for
  example, `C4 +OCT`). On other tracks, [TRIG] + [UP] / [DOWN] still opens the
  sample list as on stock firmware.
- **LFOs:** LFO SETUP lists destinations using OCTA-303's parameter names
  (TUNE, CUT, RES, ENV, DEC, ACC).
- The chromatic keys play semitones, and AMP, FX1, FX2, LFOs, scenes, and
  p-locks work as on any track.
- When SCALE QUANTIZER is also installed, an OCTA-303 track's chromatic keys
  remain semitones while other tracks follow the selected scale.
