"""OCTA303 (the OCTA-303 machine) beside SCALE QUANTIZER: HOOKS gives a 303 track's CHROMATIC keys to OCTA303 and every other track's to SCALE QUANTIZER."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="hooks-chrom-303",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_hooks",
        note="verify_hooks: the bridged CHROMATIC sites in this image and the chains under Unicorn"),),
    doc="OCTA303 (the OCTA-303 machine) beside SCALE QUANTIZER: HOOKS gives a 303 track's CHROMATIC keys to OCTA303 and every other track's to SCALE QUANTIZER.",
    modules=("OCTA303", "SCALE QUANTIZER",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
