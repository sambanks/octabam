"""usb-midi -- stock effects plus USB MIDI.

USB MIDI (markandrus/octemu's completion of the firmware's dormant USB-MIDI
half) on the DRAM platform: the unit appears to a host as a composite
mass-storage + MIDI class device, and the MIDI function mirrors the DIN
ports. The chooser is stock. remixes/test/usb-midi/README.md has the build
and use steps.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="usb-midi",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock + USB MIDI (class-compliant, mirrors DIN).",
    modules=("USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
