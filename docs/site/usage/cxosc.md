CX OSC is a **Buchla-style complex oscillator** implemented as an Octatrack track machine. It provides two FM operators, a post-FM sine wavefolder, modulator feedback, and continuous **sine → saw → square** waveform morphs on each operator (**SRC SETUP** **PWM** controls sine lean, saw phase-skew, or square duty cycle without changing the **CAR**/**MOD** icons). Timbre is shaped primarily through wavefolding and FM index.

You can run up to **six** CX OSC tracks per Part when every track's **MOD** morph is set to **0**. When the waveform morphs, **PWM**, **FDBK**, **INDX**, **DEC**, and **FOLD** are all active, limit playback to **four** CX OSC tracks; the Part still lets you assign six, but extra tracks will overload the audio processor.

CX OSC is built on a local fork of Tim Hastie's FM SYNTH engine. Remixes that include CX OSC omit SYNTH MACHINE because both share the same slot.

![CX OSC signal path: mod → FM → carrier → MIX → FOLD → out.](../../img/cxosc/path.svg)

![MIX crossfades carrier and modulator into FOLD.](../../img/cxosc/mix.svg)

## Signal path

On each sample, audio flows through four stages:

1. The **modulator** runs using **RATO**, **MOD**, and **FDBK** (which feeds back into the modulator's own phase).
2. **INDX** (scaled by the **DEC** envelope) applies FM from the modulator into the **carrier** phase (**PTCH**, **FINE**, **CAR**).
3. **MIX** crossfades between the FM-modulated **carrier** and the morphed **modulator** (**MOD** morph: sine, DPW saw, or DPW square), while **FDBK** always uses the clean modulator sine. The resulting blend feeds the **wavefolder**.
4. **FOLD** (with **SYMM**) folds the blended signal and crossfades the folded output with the pre-fold signal before sending it to the track output.

### MIX

**MIX** selects what enters the wavefolder, while **FOLD** sets how heavily it is folded. After the FM stage, you have two signals: the FM-modulated carrier and the morphed modulator. **MIX** crossfades between them before the wavefolder stage.

| MIX | Folder input |
|---|---|
| **0** (default) | Carrier only (classic FM into the folder) |
| mid | Blend of carrier and modulator |
| **127** | Modulator only (morphed modulator shape, allowing you to audition it just like **CAR** on the carrier) |

Turn up **FOLD** to hear the wavefolder, and raise **MIX** when you want to fold the modulator alongside or instead of the carrier. Setting **FOLD** to 0 bypasses the folder while **MIX** continues to blend or solo the dry waveforms.

## Access

### Select

CX OSC appears as the sixth row in the machine list (under PICKUP). You can select it in three ways:

- Double-tap the **`[TRACK]`** key, select **CX OSC**, and press **`[YES]`**.
- Press **`[FUNC]` + `[SRC]`**, open **SELECT MACHINE TYPE**, select **CX OSC**, and press **`[YES]`**.
- Open **SRC SETUP**, pick **CX OSC** from the left-hand machine list, and press **`[YES]`**.

If the track already has a sample assigned, **`[FUNC]` + `[SRC]`** may open the sample list first; press **`[LEFT]`** to reach the machine list.

### Pages

- **PLAYBACK:** **PTCH**, **RATO**, **INDX**, **FINE**, **FOLD**, **MIX**.
- **SRC SETUP (`[FUNC]` + `[PLAYBACK]`):** **CAR**, **MOD**, **DEC**, **SYMM**, **FDBK**, **PWM**.
- **AMP:** **ATK**, **HOLD**, and **REL** are managed by the synth engine. Selecting CX OSC initializes **ATK** to 0, **HOLD** to INF, **REL** to 0, and **LEG** to MONO.
- **LFO:** **PMTR** lists PLAYBACK parameters (**PTCH**, **RATO**, **INDX**, **FINE**, **FOLD**, **MIX**), followed by AMP and FX parameters, and then SETUP parameters (**CAR**, **MOD**, **SYMM**, **FDBK**, **PWM**). **DEC** is not an LFO destination. There are no VOIC or CHRD entries, and LFO 3 retains **SPD3** and **DEP3**.

Holding **`[FUNC]`** while turning PLAYBACK knobs steps **PTCH** by ±12 semitones (octaves) and snaps **RATO** to classic FM ratios. Holding **`[FUNC]`** on SETUP **CAR** or **MOD** snaps between 0, 64, and 127.

### Play

Play CX OSC using sequencer trigs, chromatic keys, or MIDI with last-note priority. AMP **HOLD** controls note duration (**HOLD INF** sustains until you press **`[STOP]`**). Parameter locks, scenes, and MIDI CCs work on PLAYBACK and SETUP parameters as with any other machine, and stock FX1, FX2, and quantizer **GLIDE** work normally.

## Controls

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| PLAYBACK | PTCH | −64..+63 | 0 | Coarse pitch in semitones; chromatic keys and MIDI notes add on top |
| PLAYBACK | RATO | 0.25..4 | ~1 | Modulator-to-carrier ratio; continuous on the knob, or hold **`[FUNC]`** to snap to classic FM ratios |
| PLAYBACK | INDX | 0..127 | 0 | FM depth; **0 = no FM** (carrier/folder only) |
| PLAYBACK | FINE | −64..+63 ¢ | 0c (raw 64) | Fine pitch in cents |
| PLAYBACK | FOLD | 0..127 | 0 | Wavefolder dry/wet amount after MIX; **0 = bypass** |
| PLAYBACK | MIX | 0..127 | 0 | **Folder input:** crossfades between carrier and modulator; **0 = carrier only** |
| SETUP | CAR | 0..127 | 0 | Carrier morph: **0** sine → **64** saw → **127** square; **`[FUNC]`** snaps to landmarks |
| SETUP | MOD | 0..127 | 0 | Modulator morph (same map, using DPW saw/pulse); audible via **INDX** (FM) or **MIX 127** (solo); **`[FUNC]`** snaps |
| SETUP | DEC | 0..127 | 127 | Index decay time constant: **0 = instant**; **1–32 = 1 ms/step**, widening up to **5.061 s** at 126; **127 = HOLD** (INDX stays at the knob setting) |
| SETUP | SYMM | 0..127 | 64 | Wavefolder half-wave symmetry skew; **64 = symmetric**; requires **FOLD** above 0 |
| SETUP | FDBK | 0..127 | 0 | Modulator feedback (always uses the unmorphed modulator sine) |
| SETUP | PWM | **−64..+63** (byte 0..127) | **0** (byte 64) | Waveform cycle lean: soft lean on sine, phase-skew on saw (steep to shallow ramp), and duty cycle on square (**0** ≈ 50%) |

### How the knobs interact

- **Clean sine carrier:** Set **INDX**, **FOLD**, **FDBK**, **CAR**, and **MOD** to 0.
- **Hearing FM:** Raise **INDX** to modulate any **CAR** waveform (sine, saw, or square). **RATO** sets sideband spacing (1 produces octave harmonics, while non-integers create clangorous tones). **FDBK** requires **INDX** above 0 to be heard. Turning up **MOD** also colors the FM modulation, or you can solo the morphed modulator waveform by setting **MIX** to 127 with **INDX** at 0.
- **Wavefolder:** Raise **FOLD** first so the folder is active. Use **MIX** to choose whether the carrier, modulator, or a blend feeds the folder, and adjust **SYMM** to bias which half of the waveform the folder emphasizes.
- **Morphing while folding:** High **FOLD** settings can make a saw-like **CAR** setting still sound sine-like. Lower **FOLD** near 0 when auditioning **CAR** or **PWM** changes.
- **DEC and MIX:** SETUP **C DEC** controls the **INDX** decay envelope. Each sequencer trig resets the envelope to the full **INDX** value for that frame and begins decaying on the next frame, even while the oscillator is already sounding. Live legato notes preserve the running envelope, which decays cleanly to zero with no residual tail. PLAYBACK **F MIX** blends the carrier and modulator prior to **FOLD**.
- **CAR vs. MOD morphs:** Both share the **0** sine, **64** saw, **127** square map, with hard saw/pulse on the carrier and DPW saw/pulse on the modulator. **PWM** adapts to the current waveform region (sine lean, saw skew, or square duty). Lower **FOLD** near 0 to hear these shapes clearly.

## LFO

Standard destinations appear first (using PLAYBACK names): **PTCH**, **RATO**, **INDX**, **FINE**, **FOLD**, and **MIX**, followed by AMP, LFO speeds, FX1, and FX2. Extra SETUP destinations are listed at the end:

| PMTR | Destination |
|---|---|
| 30 | CAR |
| 31 | MOD |
| 32 | SYMM |
| 33 | FDBK |
| 34 | PWM |

**PTCH** LFO depth matches FLEX. **DEC** cannot be modulated by an LFO, though it still responds to knob turns, parameter locks, and scenes.

### A short listen path

1. Start with **INDX** at mid-range, **DEC** at HOLD, and **FOLD**, **MIX**, **FDBK**, **CAR**, and **MOD** at 0 to hear plain FM.
2. Turn up **FOLD** to fold the FM carrier.
3. Raise **MIX** to bring the modulator into the folder.
4. Sweep **CAR** across 0 → 64 → 127 (sine, saw, square) and try **PWM** at each point.
5. With **INDX** raised, sweep **MOD** to hear how modulator shapes change the FM timbre, then add **FDBK** for extra growl.

## Saved Parts

Default values are initialized only when you newly **select** CX OSC; reloaded Parts preserve their saved parameter bytes.

In earlier builds (VRCS-CX VS), PLAYBACK **D**/**E**/**F** held **FOLD**, **SYMM**, and **DEC** instead of **FINE**, **FOLD**, and **MIX**. As a result, loading an older VS Part with **DEC** set to HOLD maps to **MIX** 127, and an old **FOLD** value of 40 loads as **FINE** raw 40 (−24c). Re-select the machine or update those knobs after loading an older project.
