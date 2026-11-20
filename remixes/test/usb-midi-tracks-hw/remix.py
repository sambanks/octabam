"""usb-midi-tracks-hw -- USB MIDI TRACKS on a unit, driven from the Mac.

The test image for tools/hw/ot_usbtracks.py: USB MIDI TRACKS with USB MIDI,
REMOTE (PEEK of the module's counters, disk mode and REMIX SWITCH boots over
USB), BRAIN (REMIX SWITCH, the SEND setting) and LOAD METER (the frame
interrupt's longest run). No FRAME GUARD: a late frame entry is what the run
looks for. SPATIALIZER gives its DSP words to LOAD METER, as in fmenes.
SEND is pinned NOTES+CC; tools/hw/ot_usbtracks.py builds the OFF copy.
"""
from remix.schema import Evidence, Level, Pin, Remix

REMIX = Remix(
    name="usb-midi-tracks-hw", image_name="UMT-HW",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="USB MIDI TRACKS + USB + REMOTE + BRAIN + LOAD METER on 13 stock effects: the unit test image.",
    modules=("USB", "USB MIDI TRACKS", "REMOTE", "LOAD METER", "BRAIN", "MEMORY", "STORE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS", "COMPRESSOR", "LO-FI", "DJ EQ", "COMB FILTER"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): Pin("OFF"),
              ("octabam.usb-midi-tracks", "SEND"): Pin("NOTES+CC")},
)
