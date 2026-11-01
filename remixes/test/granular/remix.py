"""Granular source engine with stock effects, for its port and source gates."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="granular",
    family="test",
    proof=Proof.PORT,
    proof_note=(
        "Linked initialization/ABI/arithmetic and actual loader delivery pass; a 27-case "
        "generated-project firmware run pins pitch, formats, controls, lifecycle, stock "
        "identity and clean four-reference MAIN output. Not hardware-qualified; "
        "no full make check."
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
