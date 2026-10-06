"""usb-out-tracks-main-cue -- stock effects plus USB MIDI and USB AUDIO, nothing else.

For testing the USB stream (tracks 1-16, MAIN 17-18, CUE 19-20) on a unit
that runs stock projects: no rig stations, no chooser changes, no project
stamping. Local test remix (Bryan T, 25 Sep 2026).
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="usb-out-tracks-main-cue",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="stock + USB MIDI + USB AUDIO (20 ch: tracks, MAIN, CUE).",
    modules=("USB MIDI", "USB AUDIO OUT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS MAIN CUE")},
)
