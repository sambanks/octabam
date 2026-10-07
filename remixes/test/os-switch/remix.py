"""Stock effects plus OS SWITCH: boot a raw OS image from the card without
writing the flash."""

from remix.schema import Proof, Remix

# DARK REV is off the chooser: its words hold OS SWITCH's DSP loader.
REMIX = Remix(
    name="os-switch",
    family="probes", proof=Proof.PORT, proof_note="the chainload under the port (verify_osswitch)",
    doc="stock effects with CONTROL > OS SWITCH: boot a .OBI from the card root, no flash write.",
    modules=("OS SWITCH", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV"),
    fallback="NONE",
)
