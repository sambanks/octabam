# `cfmeter-post` — CF METER with USB AUDIO OUT TRACKS POST

[`cfmeter`](../cfmeter/README.md) with [USB AUDIO OUT TRACKS
POST](../../../modules/usb-audio-out/README.md#tracks-post) in place of
USB AUDIO OUT TRACKS MAIN CUE, everything else the same: the ColdFire's
frame-interrupt time with this layout, read out over USB from T8 on
channels 15/16. T8's channels carry T8's MAIN gain here, so the readout
needs T8 unmuted, not soloed out and at a LEVEL above 0; the decoder
divides two words of one block, so the gain itself cancels.
[`cfmeter-post`](../cfmeter-post/README.md) and
[`cfmeter-tracks`](../cfmeter-tracks/README.md) are a pair: POST minus
TRACKS on the same project is POST's cost.

## Status

Flashed as BUILD C2 on allmyfriendsaresynths's (@clickysteve) MKII, 7 Oct 2026: three 8 s streaming takes decoded (period 362.8 µs, TUE/ROE 0); results in the [USB AUDIO OUT README, TRACKS POST](../../../modules/usb-audio-out/README.md#tracks-post), *On the unit*. The no-host takes were not run.

## Procedure (PR #625's CPU comparison)

1. `make bus REMIX=cfmeter-post` (or `make image REMIX=cfmeter-post BUILD=N`), flash.
2. Load the comparison project fresh: seven tracks playing, T8 FX2 = CF
   METER, T8 unmuted, not silenced by a solo, at a fixed LEVEL.
3. Streaming, USB to the host, 8 s:
   `tools/rec 8 cpu_stream.wav Octatrack`, then
   `.venv/bin/python tools/harness/cfmeter.py cpu_stream.wav --lr 14,15`
   (0-based indices: T8 = channels 15/16 of the sixteen).
4. No host (needs an audio interface): USB cable out, T8 cued, CUE into
   the interface; `tools/rec 8 cpu_nohost.wav <interface>`, then
   `cfmeter.py cpu_nohost.wav --lr <CUE L>,<CUE R> --analog`.

Results: [`modules/usb-audio-out/README.md#tracks-post`](../../../modules/usb-audio-out/README.md#tracks-post), *Cost*.
