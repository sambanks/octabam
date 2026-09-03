"""restock -- put the unit back. All fourteen stock FX2 effects, no words spent.

The honest bottom of the range, and since 2 Sep 2026 it is the WHOLE stock
chooser rather than thirteen fourteenths of it.

It used to carry SEND, because an id this image does not implement has to
alias somewhere and a real effect would PROCESS the unknown id rather than
pass it. SEND's 215 words land on the first 215 of PLATE's 594 -- the donor
region is packed from PLATE upward -- so the smallest possible image cost
the smallest reverb, and PLATE REV was missing for that reason and no other.

Unimplemented ids now resolve to the FIRMWARE's own NONE instead
(schema.NO_FALLBACK): the descriptor a stock chooser carries at list row 0,
and the per-payload null stub on the DSP side. That costs one chooser row
and NOT ONE WORD, so nothing is placed over PLATE and all three reverbs
survive. The build reports it: "KEPT STOCK: PLATE/SPRING/DARK".

It is safe here for the reason it is refused anywhere else: with no server
and no SEND there is no bus in this image, so there is no rotation to flip
and no accumulator to clear, and an unassigned track running nothing costs
nothing.

⚠️ UNFLASHED. What it is for: undoing a remix without reflashing the stock
OS, when some ColdFire cave is worth keeping -- and as the proof that the
three reverbs are consumed by ARITHMETIC, not by nature (PLAN §7, closed
2 Sep 2026). With nothing placed at all, that proof is now exact: the
chooser an unmodified unit shows, rebuilt from our own tables.
"""

from remix.schema import Remix

REMIX = Remix(
    name="restock",
    doc="every stock FX2 effect, all fourteen: put my unit back.",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
