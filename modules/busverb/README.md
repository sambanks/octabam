# BusVerb

An eight-line FDN reverb with ROOM/PLATE/BIG modes, modulated taps, a
shimmer, a gate and mid/side width. Hosted on payload A (core 0), which
serves **tracks 5–8** — measured, and inverted from what every doc assumed
before it was measured. Test it on track 5.

Full structure, parameters and memory layout: [`docs/effects/REVERB.md`](../../docs/effects/REVERB.md).
Voicing decisions: [`docs/effects/VOICING.md`](../../docs/effects/VOICING.md).

**v7 (4 Sep 2026): MODE is page-2 slot 6 and SHMR slot 7** — swapped so
MODE sits on a slot the panel's page-2 knob editor writes, which a main-menu
bus screen needs (`docs/firmware/MAINMENU.md` §9c-ii). Locally bit-identical in every
mode. A part saved before v7 loads its old bytes crossed (ROOM + a whisper of
shimmer): re-select the effect.

`reverb_lforoll.asm` is a parked alternate engine that frees 51 words and
fails `verify_roll` on the one case that drives the allpass hard. It is kept
because the bisect narrowed it; see `PLAN.md`.

## Open

- ~~Per-mode gain structure: the modes sit 7–9 dB apart~~ — measured 12 Sep
  2026 on the loop at the unit's level (AUX 100): ROOM −16.9, PLATE −19.1,
  BIG −19.0 dBFS wet at defaults, within 2 dB; the note predated the re-laws.
  The default MODE is PLATE now (was BIG) and DIFF 80 (was 64; R59's
  bracket).
- **The decay dial has a floor (12 Sep 2026, measured twice):** a clean
  exponential at −32..−35 dB/s (RT60 ≈ 1.7 s) in every mode that no knob
  reaches — ROOM 1.7 → 3.9 s, PLATE → 4.4, BIG → 11.7 across TIME. Ruled out
  the same evening: the shimmer (NOSHIM identical), the tank gains (a law
  taking line 0's radius to 0.43 moved only the top; reverted, it deadened
  half the dial), the input diffusers (DIFF 0 → 127: 1.78 → 1.93 s), MOD,
  SIZE, TONE, and the cross-core bus (the single-core hatch shows the same
  floor). Something recirculates at g ≈ 0.9 per ~26 ms that the knobs don't
  write. Next: `dsp_host -track` on the hatch (the reverb is instance 0
  there) to read the eight lines' energy beside the output. Open.
- A SIZE turn once killed the reverb on R44 and has not been reproduced. If
  it recurs, the one diagnostic that matters is whether tracks 5–8 *all* died.
