"""Stock effects plus LAZY CHOP and BUFFER SAVER: chop a recorder take by tapping the trig keys, save it with its slices.

ATA WRITE GUARD rides along as in remixes/test/buffer-saver.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="lazy-chop",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="tools/verify/verify_lazy_chop.py"),),
    doc="stock effects with LAZY CHOP (tap TRIG 1..16 to slice a take) and BUFFER SAVER.",
    modules=("LAZY CHOP", "BUFFER SAVER", "ATA WRITE GUARD", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
