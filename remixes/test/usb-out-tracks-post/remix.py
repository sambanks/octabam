"""usb-out-tracks-post -- stock effects plus USB MIDI and USB AUDIO OUT TRACKS POST, nothing else.

usb-out-tracks with each track's channels after that track's own MAIN gain
(LEVEL, mute, solo, XLV; MAIN_LEVEL left out). For testing the stems on a
unit that runs stock projects.
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="usb-out-tracks-post",
    family="mods", proof=Proof.HARDWARE,
    proof_note="allmyfriendsaresynths's MKII, P3, 5 Oct 2026 (smoke test: 16 channels, LEVEL/mute/solo/crossfader follow)",
    doc="stock + USB MIDI + USB AUDIO OUT TRACKS POST (16 ch: the tracks after their own MAIN gain).",
    modules=("USB MIDI", "USB AUDIO OUT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS POST")},
)
