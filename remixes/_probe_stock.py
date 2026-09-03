"""_probe_stock -- scratch: is an all-stock selection buildable at all?"""
from remix.schema import Remix
REMIX = Remix(
    name="_probe_stock",
    doc="all eleven stock FX2 effects, no modules",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY"),
    fallback="FILTER",
)
