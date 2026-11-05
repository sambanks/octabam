"""stock effects with SCREENSHOT: the Elektron screenshot SysEx request answered on MIDI OUT."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="screenshot",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with SCREENSHOT.",
    modules=("SCREENSHOT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
