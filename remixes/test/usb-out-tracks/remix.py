"""usb-out-tracks -- stock effects plus USB MIDI and USB AUDIO OUT TRACKS, nothing else.

usb-out-tracks-main-cue with the sixteen track channels only (no MAIN/CUE): the layout
image 69 ran. For testing USB AUDIO OUT TRACKS on a unit that runs stock
projects. Local test remix (27 Sep 2026).
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="usb-out-tracks",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="stock + USB MIDI + USB AUDIO OUT TRACKS (16 ch: the tracks).",
    modules=("USB MIDI", "USB AUDIO OUT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS")},
)
