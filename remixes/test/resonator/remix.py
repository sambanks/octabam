"""RESONATOR on FX1 beside the stock effects: PLATE REV gives up its words."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    family="effects",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="Ilia", date="2026-10-19",
        note="BUILD RR / RESON RR.RMX, 19 Oct 2026: page-1 GN1–4/DECY/MIX, page-2 PIT1–4/SCAL 8 and 127, DECY low "
             "and high, FX2 dry-pass, two FX1 instances"),),
    name="resonator",
    doc="RESONATOR on FX1 beside the stock effects (all but PLATE REV).",
    modules=("RESONATOR",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "SPRING REV", "DARK REV"),
    fx1=("RESONATOR",
         "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
