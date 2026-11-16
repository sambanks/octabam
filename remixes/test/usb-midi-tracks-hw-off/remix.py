"""usb-midi-tracks-hw-off -- usb-midi-tracks-hw with SEND pinned OFF.

tools/hw/ot_usbtracks.py's silence check: the same project played on this
image must put no note and no CC on USB.
"""
from remix.schema import Evidence, Level, Pin, Remix

REMIX = Remix(
    name="usb-midi-tracks-hw-off", image_name="UMT-OFF",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="usb-midi-tracks-hw with USB MIDI TRACKS' SEND pinned OFF.",
    modules=("USB", "USB MIDI TRACKS", "REMOTE", "LOAD METER", "BRAIN", "MEMORY", "STORE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS", "COMPRESSOR", "LO-FI", "DJ EQ", "COMB FILTER"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): Pin("OFF"),
              ("octabam.usb-midi-tracks", "SEND"): Pin("OFF")},
)
