"""wave -- an experiment: WAVE (a 4-voice wavetable synth on FX2) with SCALE QUANTIZER for
the played notes, the page-2 tools (CC MAP, SCENES P2, PLOCKS P2) and USB at
TRACKS MAIN CUE to record it. DARK REV and SPRING REV
are off the chooser: WAVE runs in their words."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="wave",
    family="effects", proof=Proof.PORT, proof_note="Sam's MKII, image 93, 3 Oct 2026: plays, PTCH and the CHROMATIC keys move the pitch; EDIT EVENTS migration: software only, hardware pending; shared EVENTS migration is software-only, not hardware-tested",
    doc="Experiment: a 4-voice wavetable synth on FX2, played by a sine on its track; SCALE QUANTIZER, page-2 tools, USB out; DARK and SPRING REV give up their words.",
    modules=("WAVE", "SCALE QUANTIZER", "CC MAP", "SCENES P2", "STORE", "EVENTS", "PLOCKS P2",
             "USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
