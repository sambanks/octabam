"""base -- stock, whole, plus the switcher.

All fourteen stock FX2 effects, nothing given up, and MAIN MENU > OS. The
smallest change to 1.40C that adds OS SWITCH: the DSP park lives entirely
in stock's dead interrupt vectors (schema.DspSection.pins), so it costs the
effect region nothing and no effect has to be harvested to pay for it.

This is the starting point the other remixes are departures from: harvest
an effect when you want words for a module, not to afford the switcher.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="base",
    family="reference", proof=Proof.PORT,
    proof_note="verify_osswitch and verify_dspvectors; the same park ran on an MKII "
               "29 Sep 2026 in bottleservice-ret",
    doc="stock's fourteen effects, whole, plus MAIN MENU > OS: the smallest image that "
        "can boot another one.",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
