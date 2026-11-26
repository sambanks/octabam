"""Euclid in either insert slot, with all three stock reverbs on FX2.

The remaining stock effects listed below retain their original controls.
Unlisted modulation effects provide DSP space; reverbs are never donors.
"""
from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="euclid",
    family="effects", evidence=(Evidence(Level.EMULATOR,
        note="EVENTS: firmware/render gates"),),
    doc="Euclid rhythmic modulation: 12 dB LP/BP/HP or AMP, both FX slots.",
    modules=("EVENTS", "EUCLID", *stock.effects("FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "DELAY")),
    fx1=("EUCLID", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
