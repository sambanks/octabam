"""SC KEYBUS BRIDGE -- lets SIDECHAIN_COMPRESSOR's `sctap` and KEYBUS's `kbus_tap` share their dispatcher site.
Both hook the dispatcher's per-track `move x:>$208,r6` at P:0x4a7 (payload A) and 0x29c (B). The bridge stands
in for KEYBUS's hook there (schema.DspOverride): the build plants SIDECHAIN_COMPRESSOR's resident stub at the
site, and the stub runs sctap when the demand loader has it loaded, then jumps to KEYBUS's kbus_tap, which
publishes the track's key word and replays the displaced instruction. sctap's own replay of it before the jump
is the same load, so the second is harmless. The build supports this for a Remix.window_demand module only, as
for SC LOAD METER BRIDGE (modules/sc-loadmeter-bridge).
"""
from remix.schema import Category, DspOverride, Kind, Module, Proof

MODULE = Module(
    name="sc-keybus-bridge",
    key="SC KEYBUS BRIDGE",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.CHECK, proof_note="",
    doc="Shares the dispatcher's per-track site between SIDECHAIN_COMPRESSOR's sctap and KEYBUS's tap.",
    requires=("SIDECHAIN_COMPRESSOR", "KEYBUS"),
    dsp_overrides=(DspOverride({"A": 0x4A7, "B": 0x29C}, "KEYBUS"),),
)
