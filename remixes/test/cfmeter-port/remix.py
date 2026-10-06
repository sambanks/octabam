"""cfmeter-port -- cfmeter without CF METER IDLE, for the port gate: the
port advances its clock only at main's stock `bras .`, which the idle loop
replaces. The idle slot reads 0."""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="cfmeter-port",
    family="probes", proof=Proof.PORT, proof_note="the readout chain under the port",
    doc="cfmeter without the idle loop: the port gate for the readout chain and the interrupt timing.",
    modules=("DIRECT JUMP", "SCALE QUANTIZER", "SYNTH MACHINE",
             "USB MIDI", "USB AUDIO OUT", "CF METER",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS MAIN CUE")},
)
