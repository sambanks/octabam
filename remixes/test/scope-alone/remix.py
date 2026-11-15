"""scope-alone -- SCOPE without TUNER, on stock FX."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="scope-alone",
    family="mods",
    evidence=(Evidence(Level.UNIT, who="Ilia", image="SCOPE S1.RMX", date="2026-11-15",
                       commit="3d4f296a8d25506bc7b7eeff7ac7701c27cc6c44",
                       note="Ilia reports SCOPE works without TUNER."),),
    doc="stock effects with standalone SCOPE and no TUNER module.",
    modules=(
        "SCOPE",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
        "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
        "DELAY", "PLATE REV", "SPRING REV", "DARK REV",
    ),
    fallback="NONE",
)
