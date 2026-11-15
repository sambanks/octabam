"""STEM REC (UP+REC) with BRAIN on the root: coexistence proof.

STEM REC does not grow MAIN MENU; BRAIN grows the root's fifth category.
Stock effects keep the FX2 chooser filled. MEMORY is required by STEM
REC's DramRegions.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="stems-brain",
    family="probes", evidence=(Evidence(Level.EMULATOR, ref="verify_stems_menu",
        note="verify_stems_menu under ot_emu"),),
    doc="STEM REC (UP+REC) with BRAIN on the root: coexistence without two menu growers.",
    modules=("STEM REC", "BRAIN", "MEMORY",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
