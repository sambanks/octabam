"""scope -- SCOPE and TUNER on stock FX through the HOOKS dispatcher."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="scope",
    family="mods",
    evidence=(Evidence(Level.BUILD, ref="shared TEMPO/frame/UI dispatcher"),),
    doc="stock effects with SCOPE and TUNER sharing the TEMPO, frame and UI hooks.",
    modules=(
        "TUNER",
        "SCOPE",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
        "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
        "DELAY", "PLATE REV", "SPRING REV", "DARK REV",
    ),
    fallback="NONE",
)
