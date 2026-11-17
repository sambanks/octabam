"""Stock effects plus ZOOM KEEP: the audio editor keeps its zoom when a slice is auditioned"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="zoom-keep",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="tools/verify/verify_zoom_keep.py"),),
    doc="stock effects with ZOOM KEEP (the audio editor keeps its zoom when a slice is auditioned).",
    modules=("ZOOM KEEP",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
