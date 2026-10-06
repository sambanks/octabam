"""wave -- an experiment: WAVE (a 4-voice wavetable synth on FX2) with SCALE QUANTIZER for
the played notes, the page-2 tools (CC MAP, SCENES P2, PLOCKS P2) and USB
MIDI + USB AUDIO OUT TRACKS MAIN CUE to record it. DARK REV and SPRING REV
are off the chooser: WAVE runs in their words."""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="wave",
    family="effects", proof=Proof.HARDWARE, proof_note="Sam's MKII, image 93, 3 Oct 2026: plays, PTCH and the CHROMATIC keys move the pitch",
    doc="Experiment: a 4-voice wavetable synth on FX2, played by a sine on its track; SCALE QUANTIZER, page-2 tools, USB out; DARK and SPRING REV give up their words.",
    modules=("WAVE", "SCALE QUANTIZER", "CC MAP", "SCENES P2", "STORE", "PLOCKS P2",
             "USB MIDI", "USB AUDIO OUT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS MAIN CUE")},
)
