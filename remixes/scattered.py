"""scattered -- two modules in two runs that are NOT next to each other.

The worked example for non-contiguous harvesting, and the reason the placer
stopped being a single bump cursor on 3 Sep 2026.

The thirteen DSP effects are laid out contiguously, but the ones you want to
give up need not be adjacent. This remix keeps six stock effects on FX1 and
puts Streamz and WarpFold on FX2, which leaves SPATIALIZER on no menu at all
-- and SPATIALIZER sits between FILTER and EQUALIZER, nowhere near the
reverbs. So what it gives up is THREE separate runs:

    run 1     261 w   SPATIALIZER
    run 2   3,342 w   FLANGER/CHORUS/PLATE REV/SPRING REV/DARK REV
    run 3     277 w   COMB FILTER

⚠️ ALL THREE ARE PLACEABLE, AND THAT IS THE POINT. Until 3 Sep the build
wrote one contiguous stream, so `stock.region_of` handed it the largest run
alone and runs 1 and 3 were given up and then left empty -- 538 words
surrendered for nothing, with the budget showing no change when you dropped
them. The placer now first-fits each module into a run it fits: Streamz's
255 words go into SPATIALIZER's 261-word opening, WarpFold's 322 into run 2.

⚠️ A GAP IS STILL A WALL. A module is ONE code stream, so it must fit inside
a SINGLE run -- 3,880 words across three runs will not take a 3,500-word
module, and the remixer says the largest opening beside the total for that
reason. Harvesting an effect that sits BETWEEN two runs joins them into one.

⚠️ WHY WARPFOLD IS IN RUN 2 AND NOT RUN 1: it is 322 words and run 1 holds
261. First-fit walks the runs in address order and takes the first that
fits, so the order modules appear in `modules` does not decide where they
land -- their sizes do.

Measured, not assumed: both modules render BIT-IDENTICAL audio here and in a
control remix whose harvest is a single run (`tools/remix/selftest.py`).

⚠️ UNFLASHED, and a demonstration rather than a voicing: Streamz and
WarpFold are both inserts, so this image has no bus at all.
"""

from remix.schema import Remix

REMIX = Remix(
    name="scattered",
    doc="Two modules placed into two non-adjacent runs of harvested code.",
    modules=("STREAMZ", "WARPFOLD"),
    fallback="NONE",
    # Six of stock's ten. Dropping SPATIALIZER and COMB FILTER from FX1 is
    # what makes the harvest non-contiguous -- put either back and its run
    # merges away.
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "COMPRESSOR", "LO-FI"),
)
