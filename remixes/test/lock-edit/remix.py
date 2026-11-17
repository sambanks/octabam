"""Stock effects plus LOCK EDIT: [TRIG]+[BANK] in grid recording opens the audio editor on the step's sample and slice"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="lock-edit",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="tools/verify/verify_lock_edit.py"),),
    doc="stock effects with LOCK EDIT ([TRIG]+[BANK] in grid recording opens the audio editor on the step's sample and slice).",
    modules=("LOCK EDIT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
