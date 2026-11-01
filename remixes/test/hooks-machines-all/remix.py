"""ANALOG BD, OCTA303 and CX OSC in one image: HOOKS gives the track's machine list eight rows, ANALOG BD on row 5, OCTA-303 on row 6 and CX OSC on row 7, and the list scrolls."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="hooks-machines-all",
    family="mods", proof=Proof.PORT,
    proof_note="verify_hooks: the bridged machine sites in this image; the three machines' UI gates under the port",
    doc="ANALOG BD, OCTA303 and CX OSC in one image: HOOKS gives the track's machine list eight rows, ANALOG BD on row 5, OCTA-303 on row 6 and CX OSC on row 7, and the list scrolls.",
    modules=("ANALOG BD", "OCTA303", "CX OSC",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE",
)
