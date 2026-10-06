"""waveload -- CF METER + CF METER IDLE + WAVE LOAD on stock: what K
4-voice wave engines cost in the frame interrupt, and how many fit,
read out over USB audio from track 8. DARK REV is off the chooser: its
words hold the readout insert."""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="waveload",
    family="probes", proof=Proof.HARDWARE, proof_note="image 92, Sam's MKII, 3 Oct 2026",
    doc="CF METER + WAVE LOAD on stock: T8's FX2 BURN = K 4-voice wave engines per frame interrupt, read over USB.",
    modules=("USB MIDI", "USB AUDIO OUT", "CF METER", "CF METER IDLE", "WAVE LOAD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS MAIN CUE")},
)
