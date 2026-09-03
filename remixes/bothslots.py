"""bothslots -- WarpFold on BOTH effect slots, and a curated FX1 chooser.

The worked example for `Remix.fx1`. Two things it demonstrates:

**A module of ours on FX1.** Until 3 Sep 2026 an effect of ours could only be
reached from the FX2 slot -- not for any DSP reason (the dispatch tables are
indexed by the raw id and shared by both menus, so WarpFold's code already
ran the moment FX1 selected 0x0a) but because FX1's chooser list ends at
0x400d608c and FX2's begins four bytes later, so it could not grow where it
sat. It moves into the cave instead, exactly as the FX2 list already does
when it outgrows its own.

**FX1 is COMPOSED, not just appended to.** This lists six of stock's ten and
drops the other four, so the chooser is shorter than the one the box ships --
which needs the viewport literal at 0x40059be6 shrunk to match, or the draw
loop reads past the terminator and renders raw memory as text.

⚠️ AND THOSE FOUR ARE ON NO MENU AT ALL. FLANGER, CHORUS, SPATIALIZER and
COMB FILTER are off this FX1 list and were never on its FX2 one, so they are
unreachable -- and since 3 Sep 2026 that IS the decision to give up their
words (stock.harvested). CHORUS and FLANGER sit immediately below PLATE, so
the region runs from FLANGER: 3,342 words rather than 2,724, and WarpFold's
322 land at FLANGER's address. Their dispatch goes to the null stub. If you
want them kept, put them back on either chooser.

It costs no words: 32 bytes of cave for the list plus FX1's id and cursor
tables. What it DOES cost is cycles. FX1 is four more slots on the same four
tracks, so the worst per-core load goes from 4x WarpFold to 8x -- 404 to 808
of the 3,120 our code may spend (`make cycles`).

⚠️ UNFLASHED. The FX1 chooser has been seen only in the local ColdFire
emulator, which draws it with the firmware's own code.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bothslots",
    doc="WarpFold on FX1 and FX2, with a curated FX1 chooser.",
    modules=("WARPFOLD",),
    fallback="NONE",
    # The FX1 chooser, in its own row order. NONE is row 0 always and is not
    # named here. Empty would mean "leave stock's ten alone".
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "WARPFOLD",
         "COMPRESSOR", "LO-FI"),
)
