"""TESTGEN on FX1 beside the stock effects: PLATE REV gives up its words for TESTGEN's code.

A test source belongs at the head of a track's chain, so TESTGEN takes an FX1
row (it is buffer-free) and no FX2 row (Claims.fx1_only, so the registry hides
it from FX2); FX1 keeps all ten of its stock effects and FX2 its stock list. A
project saved with TESTGEN on FX2 (0.1) passes that track's audio through
untouched. Two TESTGENs in series on one track crackled on Ignorato's MKII (FX1
PINK into FX2 TESTGEN, OCTABAM10, 4 Oct 2026; cause not found)."""
from remix.schema import Evidence, Level, Remix
REMIX = Remix(family="effects", evidence=(Evidence(Level.UNIT, unit="MKII", who="Ignorato", image="OCTABAM6", date="2026-10-04"),),
              name="testgen", doc="TESTGEN on FX1 beside the stock effects (all but PLATE REV, whose words it takes).",
              modules=("TESTGEN",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "SPRING REV", "DARK REV"),
              fx1=("TESTGEN",
                   "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
                   "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
              fallback="NONE")
