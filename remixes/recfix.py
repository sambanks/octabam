"""RECFIX -- the recorder loop click: the three fixes, and nothing else.

The build to hand somebody whose recorder loops click (the shareable one --
`docs/firmware/RECORDER_CLICK.md` is its write-up and reproduction steps, and
neither names the reporter). It carries the THREE
ColdFire caves that between them removed the fault on hardware, and no DSP
code of our own at all -- no effects, no bus, no FX2 id of ours, no menu
change:

  * `FLEX SEEK BIND`      -- a same-buffer re-bind is a SEEK for the DSP, not
                             a new note. Removes the voice-restart transient
                             (a chirp, then hash at 140 % of the signal over
                             300 samples). RTOS_FORK 10.50.
  * `FLEX SEEK BIND CTR`  -- and its per-bind counter is held, so the read
                             pointer is not reset onto the alternating grid.
                             Removes the +/-1.5-sample seam. 10.51.
  * `RECORDER SPACING`    -- each fixed-RLEN pass is exactly as long as the
                             gap to its next arm, derived from the current
                             arm. Removes the one-skipped-sample scuff on
                             alternate bars. 10.57/10.58.

Three different mechanisms -- a message path, a position store, a length --
each measured on its own symptom, which is why all three are here.

⚠️ THE STOCK FX2 LIST IS NOT OPTIONAL, AND IS NOT "SOMETHING ELSE". Every
octabam image replaces the FX2 chooser WHOLESALE with the remix's modules
(`tools/remix/stock.py`), so a remix carrying only ColdFire caves draws a
chooser of ONE row -- NONE. The eleven non-donor stock effects keep their
code, descriptor and dispatch either way, so saved projects still PLAY, but
nothing could be selected or changed from the menu. Listing the fourteen
costs NOTHING: no clone, no placement, no words, no cycles -- only their list
rows. It is what keeps the unit NORMAL, which is the whole point of this
build: somebody should be able to flash it and carry on using their own
projects.

⚠️ NOT THE BYTES THAT WERE MEASURED. The hardware result (10.58) is
OCTABAM83 = `seekE`, which is these three caves PLUS the bus (our DSP
effects). This remix drops the bus, so it is a DIFFERENT IMAGE and is
port-gated only. The recorder path is ColdFire and the bus is DSP, so they
are independent and this is expected to behave identically -- but "expected"
is not "measured", and the honest order is for Sam to re-take the self-loop
capture on this image before it goes out.

OPEN QUESTION this build does not answer: whether `RECORDER SPACING` alone
would have been enough. The three have only ever been tested stacked.
"""

from remix.schema import Remix

REMIX = Remix(
    name="recfix",
    doc="The recorder loop click: the three ColdFire fixes beside the stock FX2 "
        "chooser, no DSP code of our own.",
    modules=("FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING",
             # the stock chooser, in stock order -- no words, no placement (stock.py)
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
