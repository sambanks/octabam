"""Stock effects plus LAZY CHOP and LAZY CHOP TEMPO: the tempo popup after a chop, under the port.

ATA WRITE GUARD rides along as in remixes/test/lazy-chop.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="chop-tempo",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="tools/verify/verify_chop_tempo.py"),),
    doc="stock effects with LAZY CHOP and LAZY CHOP TEMPO (BPM popup after YES).",
    modules=("LAZY CHOP", "LAZY CHOP TEMPO", "BUFFER SAVER", "ATA WRITE GUARD", "FILTER", "EQUALIZER", "DJ EQ",
             "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
