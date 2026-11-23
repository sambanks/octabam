# `keybus` -- KEYBUS

Every track's key level, each block, in sixteen words both DSP cores can read, in the shared window:

| words | what | read by |
|---|---|---|
| X:$37F60 + track | the peak of \|(L + R) / 2\| over the track's 16-frame input block | CHARACTER's KEY ([`modules/character`](../character/README.md)), VOID ([`modules/void`](../void/README.md)) |
| X:$37F68 + track | the block's mean square: the mean of (L² + R²) / 2 over the 16 frames | VCA160's KEY ([`modules/vca160`](../vca160/README.md)) |

Track is 0..7 (T1..T8).

- **Where:** one hook at the dispatcher's per-track site `move x:>$208,r6` (payload A `P:0x4a7`, payload B
  `P:0x29c`), the site SIDECHAIN_COMPRESSOR's `sctap` also hooks. Every track on a core passes it once a block,
  with its input at X:$00..$1f and its index in x:$420. The hook takes the peak in one pass over the block and the
  mean square in a second, stores both and replays the instruction.
- **Size:** 27 words, the same on both payloads, so in a remix with a window (`octabam`) one copy at `0x33e55`
  serves both cores. Elsewhere it goes in each payload's donor region.
- **Cost:** about 25 cycles a sample on each core for the peak and about 11 for the mean square, paid whether or
  not anything reads them.
- **Beside SIDECHAIN_COMPRESSOR:** loaded on demand, the two share the site through
  [SC KEYBUS BRIDGE](../sc-keybus-bridge/README.md). In its per-core form there is no bridge, and the build
  refuses two hooks at one site.
- **Claims:** X:$37F60..$37F6F (`Claims.dsp_ranges`). Each word is rewritten every block: nothing to clear, no
  generation, no election.
- **Forms:** `max a,b` is stock's (payload A `P:0x1e8`); the long-displacement store `move b,x:(r1+xxx)` is
  BusVerb's class (`0a7_8e`/`8f`), which runs on the unit; the one-cycle sum `mac x0,x0,a x:(r0)+,x0` has a row
  in [`docs/firmware/CHIP.md`](../../docs/firmware/CHIP.md)'s register.

## Not covered

- That the dispatcher reaches the site for every track on the unit (stock's per-track path; SIDECHAIN_COMPRESSOR's
  `sctap` relies on the same), that no stock code writes X:$37F60..$37F6F (the ledger's stock owners say none;
  there is no write watch under the port yet), and the timing between the cores.
