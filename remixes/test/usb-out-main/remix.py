"""usb-out-main -- USB AUDIO OUT MAIN on the stock effects.

The stock chooser plus USB MIDI and USB AUDIO OUT MAIN: MAIN L/R to the
host, two channels, every 250 us at high speed. For testing the MAIN-only
stream on a unit that runs stock projects; `usb-io-main-ab` adds the stereo
return.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="usb-out-main",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_usb",
        note="`verify_usb` under the port, 28 Sep 2026"),),
    doc="stock + USB (MAIN) (2 ch: MAIN L/R).",
    modules=("USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
