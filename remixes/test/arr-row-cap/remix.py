"""stock effects with ARR ROW CAP: the arranger's append stops at 256 rows."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="arr-row-cap",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with ARR ROW CAP: the arranger's append stops at 256 rows.",
    modules=("ARR ROW CAP",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
