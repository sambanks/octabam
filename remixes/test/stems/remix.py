"""STEMS -- STEM REC on the stock effects.

Every track to the card while the sequencer plays, one file each; UP +
REC opens STEMS (docs/firmware/STEM_REC.md). No octabam DSP: the 14 stock
effects are listed so the FX2 chooser is stock's. STEMS1 listed STEM REC
alone and drew a one-row chooser with nothing in it (Yves's MKII, 30 Sep
2026); ok-ms lists them for the same reason. No MAIN MENU row so BRAIN
can own the root's fifth category.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="stems",
    family="mods", evidence=(Evidence(Level.UNIT, unit="MKII", who="Yves", date="2026-10-06",
        note="(STEMS3)"),),
    doc="STEM REC on the stock effects: multitrack recording to the card, each track, MAIN, CUE and the inputs as separate WAV files.",
    modules=("STEM REC",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
