# Nimbus

A Mutable-Instruments-Clouds-flavoured **granular texture** insert, and the
first outsider module with a real buffer: the track's audio records
continuously into a 32,768-word mono line (743 ms) and four unity-rate
grains read it back — two per channel at a half-period offset, so each
channel's triangle windows sum to constant power.

## Knobs

| slot | name | what |
|---|---|---|
| p0 | POS  | how far back the grains reach, 23–370 ms behind the write head |
| p1 | SIZE | grain length 23 / 46 / 93 / 186 ms (powers of two) |
| p2 | DENS | per-grain random scatter, up to ~92 ms, latched at each grain's own wrap |
| p3 | MIX  | dry/wet; 0 = exact passthrough |
| p7 | FRZE | OFF / FROZEN (stops the write head) |

## ⚠️ One Nimbus per core

The buffer is the fixed core-private FX2-instance region `Y:0x4000–0xBFFF` —
not per-instance. That ground is only free because every other insert has no
Y footprint at all (the argument `BUS.md`'s hardcoded-base probe made), so:
two Nimbus instances on one core would share one buffer, and it cannot
coexist with ChonVerb, whose tank lives in exactly that region. Hence its own
remix, `nimbus`, rather than a seat in `mutables`. The legacy-stock-FX2
caveat `PLAN.md` records for the servers applies here identically.

## Status

Assembles (500 words), disassembly-audited, and rendered locally:

- MIX=0 **bit-exact** passthrough; warm-up (3,840 samples) is pure dry, so
  boot garbage is never played.
- **The window gate**: DC in comes back flat to −122 dB, which is what proves
  the grain pair sums to constant power. This is the test that caught the
  `a0` fractional-shift trap now recorded in `CLAUDE.md` — with the
  arithmetically obvious multiplier the window ran at double rate and the
  pair collapsed in phase.
- POS reaches back as specified (echo at +1,303 samples at POS=0, +16,603 at
  POS=127); DENS decorrelates the channels; peak stays at 0.400 FS across the
  DENS sweep.

- **The musical freeze renders locally** since `NFRZAT=n` (DEV-only,
  `build_bus.py`'s `_dev_hooks`): the freeze engages after n post-warm-up
  blocks, so a render can capture real material and then hold it. Verified
  by cutting the input to digital silence just after the freeze — the output
  sustains indefinitely (−15.5 dB at +1 s, −16.2 dB at +3 s) on buffer
  content alone. ⚠️ Freeze **n late enough to matter**: at `NFRZAT=40` only
  600 samples had been recorded while the grains read ~9,400 back, so the
  cloud froze the warm-up's cleared silence and rendered nothing. Allow at
  least POSbase + grain length of material first.

**Not yet flashed** — knob publishes and the FRZE select ride the standing
on-unit reconfirm.

## Open

- Voicing: grain density is fixed at four. Clouds' texture/diffusion stage
  and pitch-shifted grains are both out of scope for v1.

## Closed 3 Sep 2026 (evening): the read geometry now carries `+ phase`; what the measurement actually showed

`tools/verify_nimbus.py` renders this module (its own audition dump, rebuilt
every run) and measures the two things the note below names. **Measured,
both geometries:**

| | tone 438 Hz, MIX 127, FRZE 0, DENS 127 | DC in, same knobs |
|---|---|---|
| `- phase` (as shipped until today) | **441 Hz, unity** — the octave-up claim below is NOT reproduced here | p-p ripple **−3.2 dB** |
| `+ phase` (now) | 441 Hz, 2f/f −42 dB | flat, −180 dB |

So the delay's measurement did not transfer: BongDelay v5's copy of this
geometry carries an `advance` term this module never had, and that is where
its octave came from. The `+ phase` term is kept anyway — it is the geometry
that reads a fixed tap behind the moving head, and with it the window sum
is exact where it was 3 dB of ripple before. Why the old geometry rippled at
DC is **inferred, not shown**: with the distance shrinking as the grain ages,
a pair's two reads no longer sit a half period apart in the line. The gate
is what stands; the story is a candidate.

### The note as it was written (kept: it is what sent us looking)


BongDelay v5 took this engine's read geometry -- a grain reads
`W - (POSbase + s + G + 1 - phase)` -- and measured it with a tone: at
"unity" the output was **2x the input frequency**. The write head `W` moves
one sample per sample and `phase` grows one per sample, so the absolute read
position advances at TWO samples per sample: unity relative to the moving
head is an octave up in absolute terms. The DC gate cannot see rate, which
is why it passed. In FREEZE the head is still, so frozen clouds play at
unity, which is the case that was listened to. **Unverified here** (this
module was not re-rendered); the fix in the delay is a `+ phase` term in the
distance so unity is a fixed tap behind the head. Falsifier: a tone through
this module at MIX=127 with FRZE=0 reads back at its own frequency.
