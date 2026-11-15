"""Stock effects plus BRAIN and REMIX SWITCH: boot a raw OS image from the card without
writing the flash."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="remix-switch",
    family="probes", evidence=(Evidence(Level.EMULATOR, ref="verify_remix_switch",
        note="the chainload under the port (verify_remix_switch)"),),
    doc="stock effects with BRAIN and REMIX SWITCH: MAIN MENU > BRAIN boots a .RMX from /BRAIN/REMIXES/, no flash write.",
    modules=("BRAIN", "REMIX SWITCH", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
