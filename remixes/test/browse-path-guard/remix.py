"""stock effects with BROWSE PATH GUARD: the sample browser stops at its 260-byte path buffers."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="browse-path-guard",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with BROWSE PATH GUARD: the sample browser stops at its 260-byte path buffers.",
    modules=("BROWSE PATH GUARD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
