"""restock -- put the unit back, keeping two of the three reverbs.

The honest bottom of the range: an unmodified FX2 chooser plus SEND, which
is the one thing a buildable image cannot do without (an id this image does
not implement has to alias SOMEWHERE, and a real effect would process the
unknown id rather than pass it).

THIRTEEN of the fourteen stock effects, including SPRING REV and DARK REV.
Only PLATE REV is missing, and only because SEND's 215 words land on the
first 215 of PLATE's 594 -- the donor region is packed from PLATE upward, so
the smallest possible image costs the smallest reverb and nothing else. The
build reports it: "donor ids taken (PLATE) ... KEPT STOCK: SPRING/DARK".

⚠️ UNFLASHED. What it is for: undoing a remix without reflashing the stock
OS, when some ColdFire cave is worth keeping -- and as the proof that the
three reverbs are consumed by ARITHMETIC, not by nature (PLAN §7, closed
2 Sep 2026).
"""

from remix.schema import Remix

REMIX = Remix(
    name="restock",
    doc="the stock chooser minus PLATE REV, plus SEND: put my unit back.",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "SPRING REV", "DARK REV", "SEND"),
    fallback="SEND",
)
