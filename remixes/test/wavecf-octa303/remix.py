"""WAVE and OCTA303 in one image: two machines on the list, one limit of two machines a Part."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="wavecf-octa303",
    family="mods", proof=Proof.PORT,
    proof_note="built; the rows and the cross-kind limit under the port (verify_wavecf_ui.py); not flashed",
    doc="WAVE and OCTA303 in one image: HOOKS gives the track's machine list seven rows, OCTA-303 on row 5 and WAVE on row 6; a Part holds two machines of either kind.",
    modules=("OCTA303", "WAVE CF", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
