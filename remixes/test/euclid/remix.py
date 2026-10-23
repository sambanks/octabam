"""Euclid in either insert slot, with all three stock reverbs on FX2.

The remaining stock effects listed below retain their original controls.
Unlisted modulation effects provide DSP space; reverbs are never donors.
"""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="euclid",
    family="effects", proof=Proof.PORT, proof_note="Shared event migration: firmware/render validation; shared EVENTS migration is software-only, not hardware-tested",
    doc="Euclid rhythmic modulation: 12 dB LP/BP/HP or AMP, both FX slots.",
    modules=("EVENTS", "EUCLID", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "COMPRESSOR", "LO-FI",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("EUCLID", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
