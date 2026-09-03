"""_floatcave -- scratch: FOUR descriptor clones plus tempo sync.

Until 3 Sep 2026 this could not build: the clones end at 0x400d7000 with
three of them, exactly where the tempo cave was pinned, and a fourth ran
into it. The caves float now; this remix is the proof, and selftest builds
it. FLANGER/CHORUS are off both choosers so WarpFold has words to land on.
"""
from remix.schema import Remix
REMIX = Remix(
    name="_floatcave",
    doc="scratch: four clones + tempo sync (the caves must float)",
    modules=("REVERB SERVER", "SEND", "WARPFOLD", "HELLO WORLD", "TEMPO SYNC"),
    fallback="SEND",
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "COMPRESSOR", "LO-FI"),
)
