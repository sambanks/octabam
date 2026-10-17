"""BBD beside 12 stock effects: SPRING REV and PLATE REV give up their words for BBD's code."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.RENDER, proof_note="`tools/verify/verify_bbd.py`, 52 gates",
              name="bbd", doc="BBD beside the stock effects (all but SPRING REV and PLATE REV, whose words it takes).",
              modules=("BBD",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "DARK REV"),
              fallback="NONE")
