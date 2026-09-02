"""nimbuslite -- Nimbus Lite beside the whole stock chooser.

The thing Nimbus cannot do. Nimbus pins Y:0x4000-0xBFFF -- both core-private
FX2 slots, every buffer the host's bump allocator has to give -- so the
ledger refuses it beside the seven stock effects that need one: FLANGER,
CHORUS, SPATIALIZER, COMB and the three reverbs. Adding it to a stock chooser
costs all seven.

Nimbus Lite asks the allocator for ONE 16,384-word slot at init instead, the
way those stock effects do, so it sits beside every one of them. What it
gives up is texture: 371 ms of material to scatter grains through rather than
743.

⚠️ UNFLASHED, and the ear pass is Sam's -- halving the ring is a voicing
change, not just a resource one.
"""

from remix.schema import Remix

REMIX = Remix(
    name="nimbuslite",
    doc="Nimbus Lite plus every stock effect that still fits.",
    modules=("NIMBUS LITE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "DARK REV"),
    fallback="NONE",
)
