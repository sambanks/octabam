"""Stock effects plus DARK MODE: system-wide OLED-style Dark Mode via Brain setting"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="dark-mode",
    family="mods",
    evidence=(
        Evidence(Level.UNIT, unit="MKI", who="8thmyth", image="OCTATRACK_METALSV8", date="2026-11-18",
                 commit="HEAD", note="tested on physical Octatrack MKI hardware"),
        Evidence(Level.EMULATOR, ref="tools/verify/verify_dark_mode.py"),
    ),
    doc="stock effects with DARK MODE (system-wide high-contrast display theme toggleable via Brain setting).",
    modules=(
        "DARK MODE",
        "BRAIN",
        "BUFFER SAVER",
        "ATA WRITE GUARD",
        "FILTER",
        "EQUALIZER",
        "DJ EQ",
        "PHASER",
        "FLANGER",
        "CHORUS",
        "SPATIALIZER",
        "COMB FILTER",
        "COMPRESSOR",
        "LO-FI",
        "DELAY",
        "PLATE REV",
        "SPRING REV",
        "DARK REV",
    ),
    fallback="NONE",
)
