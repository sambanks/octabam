"""stock effects with DIRECT_JUMP_KYOTI: [PTN] + [YES] toggles an immediate, clock-locked pattern change."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="direct-jump-kyoti",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with DIRECT_JUMP_KYOTI: [PTN] + [YES] toggles an immediate, clock-locked pattern change.",
    modules=("DIRECT_JUMP_KYOTI", "BATCH_BUGFIXES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
