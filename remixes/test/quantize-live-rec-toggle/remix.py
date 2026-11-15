"""stock effects with QUANTIZE_LIVE_REC_TOGGLE: QUANTIZE LIVE REC from [REC] + [PLAY]."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="quantize-live-rec-toggle",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with QUANTIZE_LIVE_REC_TOGGLE: QUANTIZE LIVE REC from [REC] + [PLAY].",
    modules=("QUANTIZE_LIVE_REC_TOGGLE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
