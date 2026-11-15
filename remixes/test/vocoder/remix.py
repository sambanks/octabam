"""VOCODER beside 12 stock effects: PLATE REV gives up its words for VOCODER's code; DJ EQ is
left out on both menus so the module tables move to the stock curve bank in X memory (a P-memory
table read is a multi-cycle MOVEM; VOCODER reads 50 a sample)."""
from remix.schema import Evidence, Level, Remix
REMIX = Remix(family="effects", evidence=(Evidence(Level.UNIT, unit="MKII", who="Ignorato", image="OCTABAM12", date="2026-10-04",
    note="(the earlier positions T1 T2 T5 T6), 4 Oct 2026; the current positions (T2 T4 T6 T8) not flashed"),),
              name="vocoder", doc="VOCODER beside the stock effects (all but PLATE REV, whose words it takes, and DJ EQ, so its table sits in X).",
              modules=("VOCODER",
                       "FILTER", "EQUALIZER", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "SPRING REV", "DARK REV"),
              fallback="NONE",
              fx1=("FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
                   "COMB FILTER", "COMPRESSOR", "LO-FI"))
