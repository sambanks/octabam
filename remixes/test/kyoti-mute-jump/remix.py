"""stock effects with MUTE_MODES and DIRECT_JUMP_KYOTI together."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="kyoti-mute-jump",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with MUTE_MODES and DIRECT_JUMP_KYOTI together.",
    modules=("MUTE_MODES", "DIRECT_JUMP_KYOTI", "BATCH_BUGFIXES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
