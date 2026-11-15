"""persistent-buffers -- recorder buffers saved with the project.

STORE + PERSISTENT BUFFERS on the stock effects. Not flashed.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="persistent-buffers",
    family="mods",
    evidence=(Evidence(Level.EMULATOR, ref="verify_persistent_buffers",
        note="verify_persistent_buffers under the port"),),
    doc="Recorder buffers BUFFERS/REC1.wav..REC8.wav under the project on SAVE / LOAD.",
    modules=("STORE", "PERSISTENT BUFFERS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
