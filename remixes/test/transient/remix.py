"""TRANSIENT beside 13 stock effects: PLATE REV gives up its words for TRANSIENT's code."""
from remix.schema import Evidence, Level, Remix
REMIX = Remix(family="effects", evidence=(Evidence(Level.UNIT, unit="MKII", who="Ignorato", image="OCTABAM2", date="2026-10-03"),),
              name="transient", doc="TRANSIENT beside the stock effects (all but PLATE REV, whose words it takes).",
              modules=("TRANSIENT",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "SPRING REV", "DARK REV"),
              fallback="NONE")
