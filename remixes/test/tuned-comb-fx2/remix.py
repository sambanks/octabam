"""TUNED COMB live on FX1 and FX2 (SLOTS = FX1+FX2) beside the stock effects:
PLATE REV and SPRING REV give up their words (one run of 1,657). The fixture of verify_tuned_comb's FX2 checks."""
from remix.schema import Pin, Evidence, Level, Remix

REMIX = Remix(
    family="effects",
    evidence=(Evidence(Level.EMULATOR),),
    name="tuned-comb-fx2",
    doc="TUNED COMB live on FX1 and FX2 beside the stock effects (all but PLATE REV and SPRING REV).",
    modules=("TUNED COMB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "DARK REV"),
    fx1=("TUNED COMB",
         "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
    settings={("octabam.tuned-comb", "SLOTS"): Pin("FX1+FX2")},
)
