"""waveload-port -- waveload without CF METER IDLE, for the port gate: the
port advances its clock only at main's stock `bras .`."""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="waveload-port",
    family="probes", proof=Proof.PORT, proof_note="the load path under the port",
    doc="waveload without the idle loop: the port gate for the wave engines in the frame interrupt.",
    modules=("USB MIDI", "USB AUDIO OUT", "CF METER", "WAVE LOAD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS MAIN CUE")},
)
