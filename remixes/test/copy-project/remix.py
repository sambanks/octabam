"""stock effects with COPY PROJECT: duplicate a project on the card without loading it."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="copy-project",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with COPY PROJECT: duplicate a project on the card without loading it.",
    modules=("STORE", "COPY PROJECT", "RND NAME",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
