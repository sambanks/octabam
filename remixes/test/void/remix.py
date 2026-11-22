"""VOID replaces COMB FILTER; PLATE REV words host its DSP."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    family="effects",
    evidence=(Evidence(Level.UNIT, unit="MKII",
        who="ilia-murzinov", date="2026-11-20",
        note="NBR beside CX: KEYBUS level drives VOID noise; confirmed on tip dafb11b3; verify_void.py"),),
    name="void",
    doc="VOID replaces COMB FILTER; PLATE REV words host its DSP.",
    modules=("VOID", "KEYBUS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMPRESSOR", "LO-FI",
             "DELAY", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
