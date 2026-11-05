"""usb-out-tracks-main-cue -- stock effects plus USB MIDI and USB AUDIO, nothing else.

For testing the USB stream (tracks 1-16, MAIN 17-18, CUE 19-20) on a unit
that runs stock projects: no rig stations, no project stamping. PLATE REV
gives up its words: USB's DSP half must be placed, and an effect on neither
chooser is the only source of words (the placer refuses a remix that
harvests nothing in payload A). Local test remix (Bryan T, 25 Sep 2026).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb-out-tracks-main-cue",
    image_name="OUT-TRK-MC",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="stock + USB MIDI + USB AUDIO (20 ch: tracks, MAIN, CUE); PLATE REV harvested for USB's words.",
    modules=("USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
