# `keybus` -- KEYBUS

Every track's key level, each block, in eight words both DSP cores can read: the peak of |(L + R) / 2| over the
track's 16-frame input block, at X:$37F60 + track (0..7) in the shared window. CHARACTER's KEY reads it for
T1..T8 ([`modules/character`](../character/README.md)).

- **Where:** one hook at the dispatcher's per-track site `move x:>$208,r6` (payload A `P:0x4a7`, payload B
  `P:0x29c`), the site SIDECHAIN_COMPRESSOR's `sctap` also hooks. Every track on a core passes it once a block,
  with its input at X:$00..$1f and its index in x:$420; the hook stores the peak and replays the instruction.
- **Size:** 17 words, the same on both payloads, so in a remix with a window (`octabam`) one copy at `0x33e5e`
  serves both cores. Elsewhere it goes in each payload's donor region.
- **Beside SIDECHAIN_COMPRESSOR:** loaded on demand, the two share the site through
  [SC KEYBUS BRIDGE](../sc-keybus-bridge/README.md). In its per-core form there is no bridge, and the build
  refuses two hooks at one site.
- **Claims:** X:$37F60..$37F67 (`Claims.dsp_ranges`). Each word is rewritten every block: nothing to clear, no
  generation, no election.
- **Forms:** `max a,b` is stock's (payload A `P:0x1e8`); the long-displacement store `move b,x:(r1+xxx)` is
  BusVerb's class (`0a7_8e`/`8f`), which runs on the unit.

## Measured

- `tools/verify/verify_keybus.py` under dsp_host, on `test/keybus` and `octabam` (9 Nov 2026): on both payloads
  the hook reaches the tap (directly, or through SC's bridged stub on `octabam`); the tap's word for the track
  holds the input block's exact peak and the other seven stay 0, for x:$420 as dsp_host leaves it and for every
  track 0..7 (the tap's track read redirected to a planted cell in a copy of the dump); silence publishes 0; through
  SC's bridged stub with SC not loaded, the same word.

## Not covered

- That the dispatcher reaches the site for every track on the unit (stock's per-track path; SIDECHAIN_COMPRESSOR's
  `sctap` relies on the same), that no stock code writes X:$37F60..$37F67 (the ledger's stock owners say none;
  there is no write watch under the port yet), and the timing between the cores. Not flashed.
