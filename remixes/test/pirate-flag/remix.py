"""base plus PIRATE FLAG: the OS's boot animation as a waving Jolly Roger."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="pirate-flag",
    family="probes", proof=Proof.CHECK, proof_note="the flag under the port (verify_pirateflag)",
    doc="base + PIRATE FLAG: the boot animation becomes a waving Jolly Roger.",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV", "PIRATE FLAG"),
    fallback="NONE",
)
