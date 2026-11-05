"""usb-out-tracks-post -- stock effects plus USB MIDI and USB AUDIO OUT TRACKS POST, nothing else.

usb-out-tracks with each track's channels after that track's own MAIN gain
(LEVEL, mute, solo, XLV; MAIN_LEVEL left out). For testing the stems on a
unit that runs stock projects.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb-out-tracks-post",
    image_name="OUT-TRK-POST",
    family="mods", proof=Proof.HARDWARE,
    proof_note="allmyfriendsaresynths's MKII, P3, 5 Oct 2026 (smoke test: 16 channels, LEVEL/mute/solo/crossfader follow)",
    doc="stock + USB (TRACKS POST) (16 ch: the tracks after their own MAIN gain).",
    modules=("USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "POST", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
