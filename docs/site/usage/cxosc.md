A **Buchla-style complex oscillator** as an Octatrack track machine: two
operators in FM, a sine wavefolder after them, modulator feedback, and
**sine → saw → square** morphs on each operator (**SRC SETUP** **PWM**:
sine lean / saw phase-skew / square duty). The **PWM** knob leaves the **CAR**/**MOD** icons alone. The selector
allows up to six CX OSC tracks per Part in **MONO** and four in **POLY**.

Built on Tim Hastie's FM SYNTH engine (local fork). Remixes that ship
CX OSC omit SYNTH MACHINE (same seat).

![CX OSC signal path: mod → FM → carrier → MIX → FOLD → out.](../../img/cxosc/path.svg)

![MIX crossfades carrier and modulator into FOLD.](../../img/cxosc/mix.svg)

## Signal path

Every sample:

1. **Modulator** runs (**RATO**, **MOD**, **FDBK** into its own phase).
2. **INDX** (scaled by the **DEC** envelope) FM's that into the **carrier**
   phase (**PTCH**, **FINE**, **CAR**).
3. **MIX** crossfades the FM'd **carrier** with the **heard modulator**
   (**MOD** morph: sine / DPW saw / DPW square). **FDBK** still uses the
   clean mod sine. That blend is the **folder input**.
4. **FOLD** (+ **SYMM**) wavefolds that blend and dry/wets the folder
   against the pre-fold signal → out.

### MIX

**MIX** chooses what the folder hears. **FOLD** sets how hard you fold.

After FM you have two samples: the FM'd carrier, and the MMOR'd modulator.
**MIX** lerps between them. Whatever comes out is what the wavefolder hears.

| MIX | Folder input |
|---|---|
| **0** (default) | carrier only. Classic FM into the folder |
| mid | carrier blended with modulator |
| **127** | modulator only (MMOR shape). Solo it like CMOR on the carrier |

Open **FOLD** to hear the folder. Raise **MIX** when you want the
modulator smashed through it too. **FOLD** at 0 bypasses the folder.
**MIX** still solos / blends the dry waves.

## Access

### Select

Sixth machine-list row (**CX OSC**, under PICKUP).

- Double-tap the **`[TRACK]`** key → machine list → **CX OSC** → **`[YES]`**
- **`[FUNC]` + `[SRC]`** → **SELECT MACHINE TYPE** → **CX OSC** → **`[YES]`**
- From **SRC SETUP**'s left machine list → **CX OSC** → **`[YES]`**

On a track that already has a sample, **`[FUNC]` + `[SRC]`** may open the
sample list first. **`[LEFT]`** reaches the machines.

### Pages

- **PLAYBACK.** **PTCH** **RATO** **INDX** **FINE** **FOLD** **MIX**
- **`[FUNC]` + `[PLAYBACK]`.** **SRC SETUP.** **CAR** **MOD** **DEC**
  **SYMM** **FDBK** **PWM**
- **AMP.** **ATK** / **HOLD** / **REL** (engine-owned). Selecting CX seeds
  **ATK** 0 / **HOLD INF** / **REL** 0 and **LEG MONO**
- **LFO.** **PMTR** lists PLAYBACK (**PTCH** **RATO** **INDX** **FINE**
  **FOLD** **MIX**) then AMP / FX, then SETUP **CAR** / **MOD** / **SYMM**
  / **FDBK** / **PWM**. **DEC** stays on its knob. In the default **MONO**
  build, LFO 3 stays **SPD3** / **DEP3**. The **POLY** build (`cx-poly`)
  shows **VOIC** (1..4) and **CHRD** in those two slots. LFO 3 is muted in
  POLY. LFO 1 and 2 can target **VOIC** and **CHRD** from LFO SETUP **PMTR**;
  their current values apply when the next note starts.

**`[FUNC]`** on PLAYBACK knobs: **PTCH** ±12 (octave). **RATO** snaps
classic FM ratios. **`[FUNC]`** on SETUP **CAR** / **MOD** snaps 0 / 64 /
127.

### Play

Trigs, chromatic keys, or MIDI. **MONO** keeps the last note. In **POLY**,
**VOIC** sets the voice count and **CHRD** selects a chord shape. **LEG**
selects **OFF**, **MONO**, or **POLY** behavior. AMP **HOLD** owns note
length (**HOLD INF** = until **`[STOP]`**). P-locks, scenes, and MIDI CCs
hit PLAYBACK / SETUP like any machine. Every POLY voice uses the same **CAR**,
**MOD**, **SYMM**, **FDBK**, and **PWM** settings, plus PLAYBACK **MIX** and
**FOLD**. Stock FX1 / FX2 and quantizer **GLIDE** work as usual.

## Controls

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| PLAYBACK | PTCH | −64..+63 | 0 | coarse pitch (semitones); chromatic / MIDI add on top |
| PLAYBACK | RATO | 0.25..4 | ~1 | modulator∶carrier; free on the knob, **`[FUNC]`** snaps classic FM ratios |
| PLAYBACK | INDX | 0..127 | 0 | FM depth; **0 = no FM** (carrier / fold only) |
| PLAYBACK | FINE | −64..+63 ¢ | 0c (raw 64) | cents |
| PLAYBACK | FOLD | 0..127 | 0 | wavefolder dry/wet after MIX; **0 = bypass** |
| PLAYBACK | MIX | 0..127 | 0 | **folder input:** carrier↔modulator crossfade; **0 = carrier only** |
| SETUP | CAR | 0..127 | 0 | carrier morph: **0** sine → **64** saw → **127** square; **`[FUNC]`** snaps landmarks |
| SETUP | MOD | 0..127 | 0 | modulator morph (same map; DPW saw/pulse); hear via **INDX** (FM) or **MIX 127** (solo); **`[FUNC]`** snaps |
| SETUP | DEC | 0..127 | 127 | index envelope after a trig; **127 = HOLD** (INDX stays with the knob) |
| SETUP | SYMM | 0..127 | 64 | fold half-wave skew; **64 = even**; needs **FOLD** up |
| SETUP | FDBK | 0..127 | 0 | modulator feedback (always the unmorphed mod sine) |
| SETUP | PWM | **−64..+63** (byte 0..127) | **0** (byte 64) | cycle lean: sine soft lean; saw phase-skew (steep↔shallow ramp, still a saw); square duty (**0** ≈ 50%) |

### How the knobs interact

- **Clean sine carrier.** **INDX**, **FOLD**, **FDBK**, CMOR, MMOR at 0.
- **Hear FM.** Raise **INDX**. **RATO** sets sideband spacing (1 = octaves;
  non-integers clang). **FDBK** needs **INDX**. MMOR also colours FM then,
  or solo the MMOR wave with **MIX 127** / **INDX** 0.
- **Folder.** Raise **FOLD** first. **MIX** chooses *what* gets folded
  (carrier vs modulator). **SYMM** tips which polarity the folder
  emphasises.
- **Morph while folding.** High **FOLD** can make a saw-ish CMOR still
  sound sine-ish. Drop **FOLD** near 0 when auditioning CMOR/**PWM**.
- **DEC vs MIX.** **DEC** is SETUP **C** (index envelope). **MIX** is
  PLAYBACK **F** (folder input blend). Different jobs.
- **CMOR vs MMOR.** Same **0** sine / **64** saw / **127** square map.
  Carrier = hard saw/pulse, modulator = DPW saw/pulse. **PWM** is
  region-specific (sine lean / saw skew / square duty). Audition with
  **FOLD** near 0.

## LFO

Stock destinations first (PLAYBACK names): **PTCH** **RATO** **INDX**
**FINE** **FOLD** **MIX**, then AMP / LFO speeds / FX1 / FX2. Extra SETUP
destinations:

| PMTR | Destination |
|---|---|
| 30 | CAR |
| 31 | MOD |
| 32 | SYMM |
| 33 | FDBK |
| 34 | PWM |
| 35 | VOIC, POLY only |
| 36 | CHRD, POLY only |

**PTCH** LFO depth matches FLEX. **DEC** is not an LFO destination; it
stays under its knob (and locks / scenes). In **POLY**, use LFO 1 or 2 for
**VOIC** and **CHRD**. LFO 3's output is muted because its **DEP3** byte stores
**CHRD**.

### A short listen path

1. **INDX** mid, **DEC** at HOLD, **FOLD** / **MIX** / **FDBK** / morphs
   at 0. Plain FM.
2. Open **FOLD**. Still folding the carrier only.
3. Raise **MIX**. Modulator enters the folder.
4. CMOR 0→64→127 (sine/saw/square). **PWM** at each landmark.
5. MMOR only with **INDX** still up. **FDBK** last for growl.

## Saved Parts

New seeds apply only when you **choose** CX OSC. Reloaded Parts keep their
saved bytes.

PLAYBACK **D**/**E**/**F** used to be **FOLD** / **SYMM** / **DEC**
(VRCS-CX VS). On this tip those bytes are **FINE** / **FOLD** / **MIX**.
A VS Part with **DEC** at HOLD loads as **MIX** 127, and old **FOLD** 40
becomes **FINE** raw 40 (−24c). Re-select the machine or edit the knobs
after loading an older project.
