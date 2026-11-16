"""usb-midi-tracks -- stock effects plus USB and USB MIDI TRACKS.

The smallest image that carries the module: USB (the transmit queue it
calls) and USB MIDI TRACKS, on the stock effects. No SYNTH MACHINE: both
repoint the kind table's FLEX and STATIC renderer entries.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="usb-midi-tracks",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock + USB MIDI + audio-track trigs as USB MIDI (USB only).",
    modules=("USB", "USB MIDI TRACKS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("octabam.usb-midi-tracks", "SEND"): "NOTES+CC"},   # the gate checks CCs and notes
)
