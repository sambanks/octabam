"""Stock effects plus SRC3 KEY: [MIDI] in the audio editor records SRC3 on the MKI"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="src3-key",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="tools/verify/verify_src3_key.py"),),
    doc="stock effects with SRC3 KEY ([MIDI] in the audio editor records SRC3 on the MKI).",
    modules=("SRC3 KEY", "BUFFER SAVER", "ATA WRITE GUARD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
