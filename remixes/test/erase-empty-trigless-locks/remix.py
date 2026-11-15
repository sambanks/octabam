"""stock effects with ERASE_EMPTY_TRIGLESS_LOCKS: an emptied trigless lock disappears."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="erase-empty-trigless-locks",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with ERASE_EMPTY_TRIGLESS_LOCKS: an emptied trigless lock disappears.",
    modules=("ERASE_EMPTY_TRIGLESS_LOCKS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
