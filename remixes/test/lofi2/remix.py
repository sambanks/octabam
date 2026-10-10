"""LOFI2 beside 12 stock effects: PLATE REV and SPRING REV give up their words for LOFI2's code
(856 words and a 516-word table; PLATE REV alone is 594)."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.CHECK, proof_note="make check REMIX=lofi2",
              name="lofi2", doc="LOFI2 beside the stock effects (all but PLATE REV and SPRING REV, whose words it takes).",
              modules=("LOFI2",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "DARK REV"),
              fallback="NONE")
