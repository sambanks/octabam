"""TUNED COMB on FX1 beside the stock effects: PLATE REV and SPRING REV give up their words (one run of 1,657)."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    family="effects",
    evidence=(Evidence(Level.EMULATOR),),
    name="tuned-comb",
    doc="TUNED COMB on FX1 beside the stock effects (all but PLATE REV and SPRING REV).",
    modules=("TUNED COMB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "DARK REV"),
    fx1=("TUNED COMB",
         "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
