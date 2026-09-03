# MODULATION STATION

The third BamSep26 station: one modulated line, seven modes, **FX1 only**,
replacing stock CHORUS (id 0x12). Design page:
https://claude.ai/code/artifact/1f1bfff2-9d4e-41b6-b0a7-91a3c8989aaf

| page 1 | RATE · DPTH · FDBK · MIX · →DEL · →VRB |
|---|---|
| page 2 | DLY · MODE (CHOR FLNG PHSR COMB TREM VIB PAN) · TONE · SHPE (TRI SIN SQR SAW) · WID · STGS (2P 4P 6P 8P) |

Three sample loops, chosen once per block — the Ripple pattern, which
`cycle_count` prices as "worst of N mode loops"; a dispatch *inside* a sample
loop cannot be priced at all.

- **LINE** (CHOR, FLNG, COMB, VIB): one interpolated tap with feedback and a
  one-pole damping inside the loop. The modes differ only in per-block
  coefficients — centre delay, sweep depth, feedback.
- **PHSR**: four one-pole allpass stages swept by the LFO, tapped after 1–4
  stages by four per-block weights, so STGS costs no branch.
- **AMP** (TREM, PAN): the LFO on amplitude, together or opposite, which is
  one per-block polarity word.

Every mode outputs the **wet only** and MIX blends, so MIX 0 is an exact
passthrough in all seven and 127 is vibrato or tremolo outright. The LFO runs
**per sample** (a per-block LFO steps at 2.9 kHz, which a chorus hears as
zipper), with two shaped copies — L and its WID-offset partner.

## FX1 only, and it enforces that itself

It needs a per-track line, and beside the servers the only free per-track
buffer is the FX1 slot: every FX2 instance buffer is BusVerb's tank on core
0 or BusDelay's line on tracks 3–4. It reads its base from the host's bump
allocator **at init and only there** (`docs/DSP.md` §10), and a base ≥ 0x4000
sets a flag that sends proc down the dry path, which writes nothing to Y.
`Claims(fx1_only=True, buffer_words=2048)` is that promise to the ledger, and
the first three gates below are what it rests on.

Two lines of 1,024 words (23 ms each) of the 3,072 an FX1 slot gives. The
read offset is masked, not the address, so nothing depends on where the
allocator put us.

## Measured (3 Sep 2026, local)

- **1,133 words** (payload A, 1,166 on B), **402 cycles/sample** (the LINE
  loop is the worst of the four; PHSR is 354, AMP 193, dry 20).
- `tools/verify_modstation.py`, **9 gates, all PASS**:
  - MIX=0 is a bit-exact passthrough in all seven modes;
  - **an FX2 instance is a bit-exact dry pass in all seven modes at any
    setting**, and `dsp_host -guard` reports "nothing written over a loaded
    module" — the FX1-only claim, proven;
  - the LFO is square-law in RATE (0.5 → 3.0 cycles in 0.68 s at RATE 20 vs
    110), measured in TREM **on a DC input**, where the output *is* the LFO;
  - VIB reads the line: an impulse comes back **473 samples** later, which is
    the centre delay the knob asks for;
  - PHSR is unity magnitude (+0.01 dB against the dry);
  - TREM modulates the amplitude, PAN drives the channels 3.3 M apart;
  - every knob at both extremes renders.

## What the gates cost to get right

- **An hour was spent on a stale audition dump.** The scratch image is cached
  against the newest mtime under `modules/`, and a stale hit does not fail —
  it silently measures the STOCK effect whose id this module replaces. Every
  mode read as a dry pass, the LFO looked dead, and the emulator eventually
  died on `MACRI`, an instruction stock code uses and it does not implement.
  The three station gates now delete and rebuild their dump first.
- **The delay decode shifted an already-scaled product**, pinning every line
  mode at its 8-sample floor: an 8-sample chorus, measured as an impulse
  returning 7 samples late instead of 473.
- **The feedback's one-pole accumulated instead of tracking** (`s += c*tap`
  rather than `s += c*(tap − s)`), which walks the state to the rail.
- **The allpass was not an allpass**: `y = x − c·s` instead of `y = −c·x + s`
  measured 19.6 dB down where an allpass must be 0.0.
- **The LFO topped out at 51 Hz** — audio rate, not an LFO.
- Two gates measured the wrong signal before they measured the right one: an
  envelope follower on a 438 Hz tone tracks the tone, not the sweep.

## Open

- Voicing: nothing has been heard. Every law here is a first guess — the
  delay ranges per mode, the sweep depths, the phaser's range, the SHPE
  curves.
- SHPE's fourth position is labelled SAW but the shaper implements TRI, SIN
  and SQR; SAW currently renders as TRI. Either the label or the shape.
- ⚠️ UNFLASHED, and the FX1-participant bus case has never run on hardware.
