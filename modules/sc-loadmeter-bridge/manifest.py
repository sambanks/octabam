"""SC LOAD METER BRIDGE -- lets SIDECHAIN_COMPRESSOR's `moncommit` and LOAD METER's `otop_e2` share their dispatcher site.

Both hook the FX2 slot's per-track commit, `move x:>$206,r0` at P:0x50e (payload A) and 0x303 (B). The bridge
stands in for LOAD METER's hook there (schema.DspOverride): the build plants SIDECHAIN_COMPRESSOR's resident stub
at the site, and the stub runs moncommit when the demand loader has it loaded, then jumps to LOAD METER's
otop_e2, which stamps the slot's cost and replays the displaced instruction
(docs/contributing/DEMAND_LOADER.md). The build supports this for a Remix.window_demand module only.
"""
from remix.schema import Category, DspOverride, Kind, Module, Proof

MODULE = Module(
    name="sc-loadmeter-bridge",
    key="SC LOAD METER BRIDGE",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.CHECK, proof_note="",
    doc="Shares the FX2 commit site between SIDECHAIN_COMPRESSOR's moncommit and LOAD METER's otop_e2.",
    requires=("SIDECHAIN_COMPRESSOR", "LOAD METER"),
    dsp_overrides=(DspOverride({"A": 0x50E, "B": 0x303}, "LOAD METER"),),
)
