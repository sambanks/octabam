"""BLACKPYRAMIDS_303 beside SCALE QUANTIZER: HOOKS gives a BLACKPYRAMIDS track's CHROMATIC octave keys, key index and keyboard picture to it and every other track's to SCALE QUANTIZER; SPRING REV given up."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="hooks-chrom-bp",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_hooks",
        note="verify_hooks: the bridged CHROMATIC sites in this image and the chains under Unicorn"),),
    doc="BLACKPYRAMIDS_303 beside SCALE QUANTIZER: HOOKS gives a BLACKPYRAMIDS track's CHROMATIC octave keys, key index and keyboard picture to it and every other track's to SCALE QUANTIZER; SPRING REV given up.",
    modules=("BLACKPYRAMIDS_303", "SCALE QUANTIZER",
             *stock.effects("SPRING REV")),
    fallback="NONE",
)
