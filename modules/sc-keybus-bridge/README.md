# `sc-keybus-bridge` -- SC KEYBUS BRIDGE

SIDECHAIN_COMPRESSOR's `sctap` and KEYBUS's `kbus_tap` hook the same dispatcher instruction, the per-track
`move x:>$208,r6` (`P:0x4a7` on payload A, `P:0x29c` on B), so an image can carry both only with this bridge. It
declares a `DspOverride` of KEYBUS's hook there: the build does not plant KEYBUS's `jsr`, and
SIDECHAIN_COMPRESSOR's resident stub at the site runs `sctap` when the demand loader has it loaded and then jumps
to `kbus_tap`, which publishes the track's key word and replays the displaced instruction. With SC not loaded the
stub goes straight to `kbus_tap`, so the key words are written either way.

KEYBUS has one window copy, so the build plants one stub for both payloads (10 words). Only for
SIDECHAIN_COMPRESSOR as a `Remix.window_demand` module (octabam), as for
[SC LOAD METER BRIDGE](../sc-loadmeter-bridge/README.md). `tools/verify/verify_keybus.py octabam` runs the stub.
