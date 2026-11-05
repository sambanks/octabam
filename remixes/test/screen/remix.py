"""stock effects with SCREEN: the Elektron screenshot SysEx request answered on MIDI OUT."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="screen",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with SCREEN.",
    modules=("SCREEN",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
