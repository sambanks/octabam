"""REMOTE's event records on the stock effects, with the USB module that answers the read."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="remote", family="mods", proof=Proof.PORT,
    proof_note="verify_remote under the port; not run on a unit",
    doc="Stock effects with REMOTE's event ring, read over USB.",
    modules=("REMOTE", "STORE", "USB", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
