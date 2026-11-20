"""VOID replaces COMB FILTER; PLATE REV words host its DSP."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    family="effects",
    evidence=(Evidence(Level.UNIT, unit="MKII",
        note="VOID V9 (COLR/HPF tables tip dd89e2e2+); verify_void.py 3s rail"),),
    name="void",
    doc="VOID replaces COMB FILTER; PLATE REV words host its DSP.",
    modules=("VOID", "KEYBUS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMPRESSOR", "LO-FI",
             "DELAY", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
