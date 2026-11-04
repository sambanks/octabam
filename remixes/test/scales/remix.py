from remix.schema import Proof, Remix

REMIX = Remix(
    name="scales",
    family="mods",
    proof=Proof.PORT,
    proof_note="verify_scales",
    doc="SCALES alone, on the 14 stock effects: ARP SETUP's KEY, the chooser, the snapped notes and the CHROMATIC keys.",
    modules=("SCALES", "STORE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
