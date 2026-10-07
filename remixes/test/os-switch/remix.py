"""Stock effects plus BRAIN and OS SWITCH: boot a raw OS image from the card without
writing the flash."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="os-switch",
    family="probes", proof=Proof.PORT, proof_note="the chainload under the port (verify_osswitch)",
    doc="stock effects with BRAIN and OS SWITCH: MAIN MENU > BRAIN boots a .OBI from /BRAIN/OS/, no flash write.",
    modules=("BRAIN", "OS SWITCH", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
