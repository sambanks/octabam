"""stock effects with REC_TRIG_MUTE: [TRACK]+[NO]/[YES] mute/unmute recorder trigs."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="rec-trig-mute",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with REC_TRIG_MUTE: [TRACK]+[NO]/[YES] mute/unmute recorder trigs.",
    modules=("REC_TRIG_MUTE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
