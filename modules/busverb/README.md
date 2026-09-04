# BusVerb

An eight-line FDN reverb with ROOM/PLATE/BIG modes, modulated taps, a
shimmer, a gate and mid/side width. Hosted on payload A (core 0), which
serves **tracks 5–8** — measured, and inverted from what every doc assumed
before it was measured. Test it on track 5.

Full structure, parameters and memory layout: [`docs/REVERB.md`](../../docs/REVERB.md).
Voicing decisions: [`docs/VOICING.md`](../../docs/VOICING.md).

**v7 (4 Sep 2026): MODE is page-2 slot 6 and SHMR slot 7** — swapped so
MODE sits on a slot the panel's page-2 knob editor writes, which a main-menu
bus screen needs (`docs/MAINMENU.md` §9c-ii). Locally bit-identical in every
mode. A part saved before v7 loads its old bytes crossed (ROOM + a whisper of
shimmer): re-select the effect.

`reverb_lforoll.asm` is a parked alternate engine that frees 51 words and
fails `verify_roll` on the one case that drives the allpass hard. It is kept
because the bisect narrowed it; see `PLAN.md`.

## Open

- Per-mode gain structure: the modes sit 7–9 dB apart at the output, and BIG
  crosses the clip knee at an input PLATE never reaches. Interim practice is
  to back BIG off by hand.
- A SIZE turn once killed the reverb on R44 and has not been reproduced. If
  it recurs, the one diagnostic that matters is whether tracks 5–8 *all* died.
