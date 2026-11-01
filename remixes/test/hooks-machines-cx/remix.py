"""OCTA303 and CX OSC in one image: HOOKS gives the track's machine list seven rows, OCTA-303 on row 5 and CX OSC on row 6, and the list scrolls."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="hooks-machines-cx",
    family="mods", proof=Proof.PORT,
    proof_note="verify_hooks: the bridged machine sites in this image; the two machines' UI gates under the port",
    doc="OCTA303 and CX OSC in one image: HOOKS gives the track's machine list seven rows, OCTA-303 on row 5 and CX OSC on row 6, and the list scrolls.",
    modules=("OCTA303", "CX OSC",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
