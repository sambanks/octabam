"""VIBRATO live on FX1 and FX2 (SLOTS = FX1+FX2) beside the stock effects:
PLATE REV gives up its words. The fixture of verify_vibrato's FX2 checks."""
from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    family="effects",
    proof=Proof.CHECK,
    proof_note="",
    name="vibrato-fx2",
    doc="VIBRATO live on FX1 and FX2 beside the stock effects (all but PLATE REV).",
    modules=("VIBRATO",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "SPRING REV", "DARK REV"),
    fx1=("VIBRATO",
         "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
    settings={("octabam.vibrato", "SLOTS"): Pin("FX1+FX2")},
)
