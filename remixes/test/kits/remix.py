"""kits -- KITS on the stock effects.

255 Kits per project through the stock Part slots. No DSP module; the 14
stock effects keep the FX choosers stock's.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="kits",
    family="mods", proof=Proof.PORT, proof_note="verify_kits under the port",
    doc="KITS (255 Kits per project) on the stock effects.",
    modules=("STORE", "KITS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
