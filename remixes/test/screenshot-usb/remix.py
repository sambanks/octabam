"""stock effects with USB MIDI and SCREENSHOT: the Elektron screenshot SysEx request answered over USB (or DIN)."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="screenshot-usb",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock + USB MIDI + SCREENSHOT.",
    modules=("USB", "SCREENSHOT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
