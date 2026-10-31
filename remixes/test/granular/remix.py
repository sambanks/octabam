"""Granular source engine with stock effects, for its port and source gates."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="granular",
    family="test",
    proof=Proof.CHECK,
    proof_note=(
        "Granular image built and booted to the RTOS handoff under the ColdFire port; "
        "synthetic-source gate runs under Unicorn; full make check and hardware testing "
        "not run."
    ),
    doc="The four-grain FLEX source engine and stock effects.",
    modules=(
        "GRANULAR",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
        "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
        "DELAY", "PLATE REV", "SPRING REV", "DARK REV",
    ),
    fallback="NONE",
)
