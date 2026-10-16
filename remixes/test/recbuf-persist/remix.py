"""recbuf-persist -- recorder buffers saved with the project.

STORE + RECBUF PERSIST on the stock effects. Not flashed.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="recbuf-persist",
    family="mods",
    proof=Proof.CHECK,
    proof_note="verify_recbuf under the port",
    doc="Recorder buffers BUFFERS/REC1.wav..REC8.wav under the project on SAVE / LOAD.",
    modules=("STORE", "RECBUF PERSIST",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
