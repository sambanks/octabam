A **Buchla-style complex oscillator** as an Octatrack track machine: two
operators in FM, a sine wavefolder after them, modulator feedback, and
**sine → saw → square** morphs on each operator (SETUP **PWM**: sine lean /
saw phase-skew / square duty; does **not** move the CAR/MOD icons). West
Coast voice — timbre from folding and index, not a filter ladder. Up to
**six** CX OSC tracks per Part (`ML_FM_MAX=6`; seven saturates the
ColdFire — measured MKII with CF METER).

Built on Tim Hastie’s FM SYNTH ColdFire engine (local fork); remixes that
ship CX OSC omit SYNTH MACHINE (same seat).

![CX OSC signal path: mod → FM → carrier → MIX → FOLD → out.](../../img/cxosc/path.svg)

![MIX crossfades carrier and modulator into FOLD.](../../img/cxosc/mix.svg)

## Signal path

Every sample:

1. **Modulator** runs (RATO, MOD, FDBK into its own phase).
2. **INDX** (scaled by the DEC envelope) FM’s that into the **carrier**
   phase (PTCH, FINE, CAR).
3. **MIX** crossfades the FM’d **carrier** with the **heard modulator**
   (MOD morph — sine / DPW saw / DPW square). FDBK still uses the clean
   mod sine. That blend is the **folder input**, not a wet/dry of the
   final sound.
4. **FOLD** (+ SYMM) wavefolds that blend and dry/wets the folder against
   the pre-fold signal → out.

### MIX

**MIX does not set how hard you fold.** FOLD does that.

After FM you have two samples: the FM’d carrier, and the MMOR’d modulator.
MIX lerps between them (`c + (m − c) · mix`). Whatever comes out is what
the wavefolder hears.

| MIX | Folder input |
|---|---|
| **0** (default) | carrier only — classic FM into the folder |
| mid | carrier blended with modulator |
| **127** | modulator only (MMOR shape — solo it like CMOR on the carrier) |

Open **FOLD** to hear the folder; raise **MIX** when you want the
modulator smashed through it too. FOLD at 0 bypasses the folder — MIX
still solos / blends the dry waves.

## Access

### Select

Sixth machine-list row (**CX OSC**, under PICKUP).

- Double-tap the track key → machine list → **CX OSC** → YES
- **FUNC + SRC** → **SELECT MACHINE TYPE** → **CX OSC** → YES
- From **SRC SETUP**’s left machine list → **CX OSC** → YES

On a track that already has a sample, **FUNC + SRC** may open the sample
list first — **LEFT** reaches the machines.

### Pages

- **PLAYBACK** — PTCH RATO INDX FINE FOLD MIX
- **FUNC + PLAYBACK** — **SRC SETUP** — CAR MOD DEC SYMM FDBK PWM
- **AMP** — ATK / HOLD / REL (engine-owned). Selecting CX seeds ATK 0 /
  HOLD INF / REL 0 and LEG MONO
- **LFO** — PMTR lists PLAYBACK (**PTCH RATO INDX FINE FOLD MIX**) then
  AMP / FX; **30..34** reach SETUP CAR / MOD / SYMM / FDBK / PWM (not
  DEC). No VOIC / CHRD — LFO 3 stays SPD3 / DEP3

**FUNC** on PLAYBACK knobs: PTCH snaps −32 / 0 / +32; RATO snaps classic
FM ratios. **FUNC** on SETUP CAR / MOD snaps 0 / 64 / 127.

### Play

Trigs, chromatic keys, or MIDI — last note wins. AMP **HOLD** owns note
length (**HOLD INF** = until STOP). P-locks, scenes, and MIDI CCs hit
PLAYBACK / SETUP like any machine. Stock FX1 / FX2 and quantizer GLIDE
work as usual.

## Controls

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| PLAYBACK | PTCH | −32..+32 | 0 | coarse pitch (semitones); chromatic / MIDI add on top |
| PLAYBACK | RATO | 0.25..4 | ~1 | modulator∶carrier; free on the knob, **FUNC** snaps classic FM ratios |
| PLAYBACK | INDX | 0..127 | 0 | FM depth; **0 = no FM** (carrier / fold only) |
| PLAYBACK | FINE | −64..+63 ¢ | 0c (raw 64) | cents |
| PLAYBACK | FOLD | 0..127 | 0 | wavefolder dry/wet after MIX; **0 = bypass** |
| PLAYBACK | MIX | 0..127 | 0 | **folder input:** carrier↔modulator crossfade; **0 = carrier only** |
| SETUP | CAR | 0..127 | 0 | carrier morph: **0** sine → **64** saw → **127** square; **FUNC** snaps landmarks |
| SETUP | MOD | 0..127 | 0 | modulator morph (same map; DPW saw/pulse); hear via **INDX** (FM) or **MIX 127** (solo); **FUNC** snaps |
| SETUP | DEC | 0..127 | 127 | index envelope after a trig; **127 = HOLD** (INDX stays with the knob) |
| SETUP | SYMM | 0..127 | 64 | fold half-wave skew; **64 = even**; needs **FOLD** up |
| SETUP | FDBK | 0..127 | 0 | modulator feedback (always the unmorphed mod sine) |
| SETUP | PWM | **−64..+63** (byte 0..127) | **0** (byte 64) | cycle lean: sine soft lean; saw phase-skew (steep↔shallow ramp, still a saw); square duty (**0** ≈ 50%) |

### How the knobs interact

- **Clean sine carrier:** INDX, FOLD, FDBK, CMOR, MMOR at 0.
- **Hear FM:** raise INDX. RATO sets sideband spacing (1 = octaves;
  non-integers clang). FDBK needs INDX; MMOR also colours FM then, or
  solo the MMOR wave with **MIX 127** / INDX 0.
- **Folder:** raise FOLD first. MIX chooses *what* gets folded (carrier
  vs modulator). SYMM tips which polarity the folder emphasises.
- **Morph while folding:** high FOLD can make a saw-ish CMOR still sound
  sine-ish — drop FOLD near 0 when auditioning CMOR/PWM.
- **DEC vs MIX:** DEC is SETUP C (index envelope). MIX is PLAYBACK F
  (folder input blend). Different jobs.
- **CMOR vs MMOR:** same **0** sine / **64** saw / **127** square map;
  carrier = hard saw/pulse, modulator = DPW saw/pulse. **PWM** is
  region-specific (sine lean / saw skew / square duty) — audition with
  FOLD near 0.

## LFO

Stock destinations first (PLAYBACK names, not Flex): **PTCH RATO INDX FINE
FOLD MIX**, then AMP / LFO speeds / FX1 / FX2. Extra SETUP destinations:

| PMTR | Destination |
|---|---|
| 30 | CAR |
| 31 | MOD |
| 32 | SYMM |
| 33 | FDBK |
| 34 | PWM |

PTCH LFO depth matches FLEX (÷5 vs raw synth semitone units, Tim 2.20). DEC is not an LFO destination — it stays under its knob (and locks / scenes).

### A short listen path

1. INDX mid, DEC at HOLD, FOLD / MIX / FDBK / morphs at 0 — plain FM.
2. Open **FOLD** — still folding the carrier only.
3. Raise **MIX** — modulator enters the folder.
4. CMOR 0→64→127 (sine/saw/square); PWM at each landmark.
5. MMOR only with INDX still up; FDBK last for growl.

## Saved Parts

New seeds apply only when you **choose** CX OSC. Reloaded Parts keep their
saved bytes.

PLAYBACK D/E/F used to be FOLD / SYMM / DEC (VRCS-CX VS). On this tip those
bytes are **FINE / FOLD / MIX** — a VS Part with DEC at HOLD loads as MIX
127, and old FOLD 40 becomes FINE raw 40 (−24c). Re-select the machine or
edit the knobs after loading an older project.
