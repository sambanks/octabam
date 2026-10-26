"""Demand-load spike: MODULATION loaded on demand (Remix.window_demand), beside the stock effects.

A port-only instrument (docs/proposals/DEMAND_LOAD.md): MODULATION's id dispatches to a stub that is dry until DLCOPY
has published the code, which DLPUMP stages when a track uses MODULATION. The guard wrappers front PLATE REV, DARK REV and SPRING REV."""
from remix.schema import Pin, Proof, Remix
REMIX = Remix(family="effects", proof=Proof.CHECK, proof_note="",
              name="dlspike", doc="Demand-load spike: MODULATION loaded on demand.",
              modules=("USB", "LOAD METER", "DLPUMP", "DLCOPY", "MODULATION",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
                       "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "SPRING REV", "PLATE REV", "DARK REV"),
              fx1=("MODULATION", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
                   "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
              window=(("DLCOPY", 0x33DC3), ("MODULATION", 0x3B820), ("LOAD METER", 0x37DA3), ("LOAD METER:B", 0x37E50)),
              window_demand=("MODULATION",),
              window_homes=(("MODULATION", 0x3F820),),
              window_guard=("PLATE REV", "DARK REV", "SPRING REV"),
              window_loader=0x33E56,
              fallback="NONE",
              settings={("octabam.dlpump", "GRACE"): Pin("2 S"), ("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 0,
                        ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
                        ("octabam.usb", "IN"): "OFF"})
