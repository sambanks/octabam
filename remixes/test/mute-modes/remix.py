"""stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T)."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="mute-modes",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T).",
    modules=("MUTE_MODES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
