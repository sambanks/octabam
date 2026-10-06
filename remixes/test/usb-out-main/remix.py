"""usb-out-main -- USB AUDIO OUT MAIN on the stock effects.

The stock chooser plus USB MIDI and USB AUDIO OUT MAIN: MAIN L/R to the
host, two channels, every 250 us at high speed. For testing the MAIN-only
stream on a unit that runs stock projects; `usb-io-main-ab` adds the stereo
return.
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="usb-out-main",
    family="mods", proof=Proof.PORT, proof_note="`verify_usb` under the port, 28 Sep 2026",
    doc="stock + USB MIDI + USB AUDIO OUT MAIN (2 ch: MAIN L/R).",
    modules=("USB MIDI", "USB AUDIO OUT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("MAIN")},
)
