# `sc-loadmeter-bridge` -- SC LOAD METER BRIDGE

SIDECHAIN_COMPRESSOR's `moncommit` and LOAD METER's `otop_e2` hook the same dispatcher instruction, the FX2
slot's per-track commit (`move x:>$206,r0`, `P:0x50e` on payload A, `P:0x303` on B), so an image can carry
both only with this bridge. It declares a `DspOverride` of LOAD METER's hook there: the build does not plant
LOAD METER's `jsr`, and SIDECHAIN_COMPRESSOR's resident stub at the site runs `moncommit` when the demand
loader has it loaded and then jumps to `otop_e2`, which stamps the slot's cost and replays the displaced
instruction. MON's crossfade therefore lands before LOAD METER's end stamp, so the meter counts it.

Only for SIDECHAIN_COMPRESSOR as a `Remix.window_demand` module (octabam):
[`docs/contributing/DEMAND_LOADER.md`](../../docs/contributing/DEMAND_LOADER.md). The stub is
`verify_dlhook`'s.
