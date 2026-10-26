# `dlprobe` -- DLPROBE

A measurement instrument for the demand loader
([`docs/proposals/DEMAND_LOAD.md`](../../docs/proposals/DEMAND_LOAD.md)): an insert that replaces its
track's audio with a status word per 16-sample frame (the layout of
[PEXT PROBE](../pextprobe/README.md)) carrying the loader's counters. It ships in no remix but
`remixes/test/dl-probe` and `remixes/test/dl-probe-any`, which are `octabam` with DLPROBE on FX1 in
place of EQUALIZER.

The copier ([DLCOPY](../dlcopy/README.md)) keeps three counters in each demand effect's entry in the
window (`x:$33da3 + 8 k`, words 5, 6, 7): blocks received, blocks refused for their sum, blocks
published. DLPROBE sends them with each entry's BOUND word, and four counters of what the host write has left in the staging words of the core it runs on (X:$2900 and X:$2902: frames in which each was not 0, and the last non-zero value), in a cycle of 21 frames (8 ms). The staging counters mean something only with the probe on a core B track (T1..T4).

## What the counters say

Every load is sent three times, so a healthy load reads received 3, refused 0, published 3, BOUND.

| reading | what it means |
|---|---|
| received 0, staging counters 0 | nothing the host wrote reached this core's `X:0x2900..`: the pump did not run or send (read it with `tools/hw/dl_state.py`), or the host write does not land there |
| received 0, staging counters not 0 | the host write lands and the copier does not take it: the hook at `P:0x76` is not running, or the doorbell value is not `0xa55a` |
| received > 0, published 0, refused > 0 | the staging area was reached and the data did not arrive whole: lost chunks or a wrong address |
| published > 0, the effect silent or the unit crashing | the block arrived and was published; a P store into the window or running it from there failed |
| received 1, published 1 | one of the two sends was lost |

`dl-probe` sends on the frames the port delivers (ping word 0). `dl-probe-any` sends on every frame
(`DLPUMP`'s `PHASE` build setting): if the unit loses the frames the port loses, its refused count rises
and its loads fail; if not, it reads like `dl-probe`.

## Running it on a unit

1. `make image REMIX=test/dl-probe BUILD=<n>`, flash it (`docs/guide/BUILDING.md`). The remix carries
   USB audio out, TRACKS PRE (16 channels, the tracks).
2. A project with DLPROBE (FX1, `DL PROBE`) on one track, and MODULATION, SPECTRUM, CHARACTER or
   TRANSIENT on the FX2 of other tracks (they are on the FX2 chooser). Play, or only select: the
   loader works from the selection.
3. Capture the probe track's channel pair over USB, 44.1 kHz, sample exact, for a few seconds after
   choosing an effect.
4. `python3 modules/dlprobe/decode.py capture.wav --channels <L> <R>` prints each effect's BOUND
   state and its three counters.
5. Repeat with `test/dl-probe-any`.

## Files

`dlprobe.asm`, `decode.py`, `manifest.py`; gate `tools/verify/verify_dlprobe.py` (`dsp_host`: seeded
counters come out of the audio, also inverted and at half gain).
