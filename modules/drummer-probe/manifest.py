"""DRUMMER PROBE -- phase 2 measurement for DRUMMER, never shipped in a user remix.

One DRAM unit (probe.s): a detour after the sequencer's step builder (0x400a2d82) adds trigs to
empty steps of track 1 and moves one in time; the FLEX entry of the voice-start table (0x400d6458)
is wrapped to force the slice of chosen starts. modules/drummer/probe_steps.py (DR_PROBE=1) drives
it under the port and reads the voice starts back. Findings: modules/drummer/INVESTIGATION.md.
"""

from remix.schema import Category, Detour, Kind, Linked, Module, Proof, SymbolRef

MODULE = Module(
    name="drummer-probe",
    key="DRUMMER PROBE",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="djib", author_url="https://github.com/Djibdjib",
    proof=Proof.PORT, proof_note="modules/drummer/probe_steps.py (DR_PROBE): measurement only, never shipped",
    doc="DRUMMER phase 2 probe: trigs added and moved after the step builder, the FLEX start's slice forced (measurement only).",
    linked=(Linked("probe", "modules/drummer-probe/probe.s", dram=True),),
    detours=(
        Detour(0x400A2D82, bytes.fromhex("71b98000668d"), "probe", "dp_step",
               "sequencer tick, after the step builder 0x4009d1e8: add / move track 1's trigs"),
    ),
    symbol_refs=(
        SymbolRef(0x400D6458, 0x4000F450, "probe", "dp_start",
                  "voice-start table, FLEX entry -> dp_start (forced slice)"),
    ),
)
