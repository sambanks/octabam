"""drummer-probe -- DRUMMER phase 2 measurement: the probe alone on the stock effects."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="drummer-probe",
    family="mods", proof=Proof.CHECK,
    proof_note="port only: modules/drummer/probe_steps.py DR_PROBE=1",
    doc="DRUMMER PROBE alone: trigs added and moved after the step builder, the FLEX start's slice forced.",
    modules=("DRUMMER PROBE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
