"""BBD on id 0x25 in the 64-id layout, beside 11 stock effects."""
from remix.schema import Evidence, Level, Remix
REMIX = Remix(family="effects", evidence=(Evidence(Level.EMULATOR,
    note="port only; not flashed"),),
              name="ids64", doc="BBD on FX2 id 0x25 in a 64-id image (DSP dispatch and ColdFire tables grown).",
              modules=("BBD",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "DARK REV"),
              fallback="NONE", id_space=64, ids={"BBD": 0x25})
