"""scope-alone -- SCOPE without TUNER, on stock FX."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="scope-alone",
    family="mods",
    evidence=(Evidence(Level.BUILD, ref="SCOPE standalone hooks"),),
    doc="stock effects with standalone SCOPE and no TUNER module.",
    modules=(
        "SCOPE",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
        "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
        "DELAY", "PLATE REV", "SPRING REV", "DARK REV",
    ),
    fallback="NONE",
)
