"""drummer -- DRUMMER alone on the stock effects (its gates)."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="drummer",
    family="mods", evidence=(Evidence(Level.UNIT, unit="MKII",
        note="images 52-78 (Nov 2026); modules/drummer/verify_port.py and the module's gates"),),
    doc="DRUMMER alone: T1's sliced loop played as a drummer.",
    modules=("DRUMMER", "STORE", "PAGES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
