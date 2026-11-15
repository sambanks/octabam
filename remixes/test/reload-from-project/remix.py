"""stock effects with RELOAD_FROM_PROJECT: reload one track's sequence from the card while the transport runs."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="reload-from-project",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with RELOAD_FROM_PROJECT: reload one track's sequence from the card while the transport runs.",
    modules=("RELOAD_FROM_PROJECT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
