"""Stock effects plus the REPITCH TSTR firmware modification."""

from remix.schema import Remix

REMIX = Remix(
    name="repitch",
    doc="stock effects with variable-speed REPITCH in the TSTR selector.",
    modules=("REPITCH", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
