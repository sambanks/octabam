"""STORE + PLOCKS P2 + SEQ (seq.work client) with the stock effects."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="seq",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="STORE + PLOCKS P2 + SEQ (seq.work client) with the stock effects.",
    modules=("STORE", "SCENES P2", "EVENTS", "PLOCKS P2", "SEQ",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
