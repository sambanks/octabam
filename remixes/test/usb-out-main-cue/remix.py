"""usb-out-main-cue -- stock effects plus USB MIDI and USB AUDIO OUT MAIN CUE, nothing else.

usb-out-tracks-main-cue with MAIN L/R + CUE L/R only, at the 250 us cadence (not
USB AUDIO OUT MASTER's 1 ms). For testing USB AUDIO OUT MAIN CUE on a unit that runs
stock projects. Local test remix (27 Sep 2026).
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="usb-out-main-cue",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="stock + USB MIDI + USB AUDIO OUT MAIN CUE (4 ch: MAIN + CUE).",
    modules=("USB MIDI", "USB AUDIO OUT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("MAIN CUE")},
)
