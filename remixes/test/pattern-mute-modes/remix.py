from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="pattern-mute-modes",
    family="test",
    evidence=(Evidence(Level.EMULATOR,
        note="PATTERN MUTE beside MUTE_MODES"),),
    doc="smoke: PATTERN MUTE and MUTE_MODES together, stock effects",
    modules=("PATTERN MUTE", "MUTE_MODES", "STORE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
