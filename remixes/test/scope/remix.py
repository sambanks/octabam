"""scope -- SCOPE and TUNER on stock FX through the HOOKS dispatcher."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="scope",
    family="mods",
    evidence=(Evidence(Level.UNIT, who="Ilia", image="SCOPE T1.RMX", date="2026-11-15",
                       commit="3d4f296a8d25506bc7b7eeff7ac7701c27cc6c44",
                       note="Ilia reports SCOPE and TUNER both work through the shared hooks."),),
    doc="stock effects with SCOPE and TUNER sharing the TEMPO, frame and UI hooks.",
    modules=(
        "TUNER",
        "SCOPE",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
        "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
        "DELAY", "PLATE REV", "SPRING REV", "DARK REV",
    ),
    fallback="NONE",
)
