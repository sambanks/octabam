from remix.schema import Proof, Remix

REMIX = Remix(
    name="pattern-mute-modes",
    family="test",
    proof=Proof.CHECK,
    proof_note="PATTERN MUTE beside MUTE_MODES",
    doc="smoke: PATTERN MUTE and MUTE_MODES together, stock effects",
    modules=("PATTERN MUTE", "MUTE_MODES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
