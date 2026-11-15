"""usb-io-tracks-cd -- the Octatrack as a USB interface: the sixteen track channels out, a stereo pair into inputs C/D (A/B stay on the jacks).

USB AUDIO OUT TRACKS (to the host), USB AUDIO IN CD (from the host; the jacks while its stream is
closed) and USB CROSSBAR (the controller served first on the crossbar,
without which IN loses packet tails under load), with USB MIDI, on the stock
effects minus SPATIALIZER, whose words on payload A hold the IN module's RX
inject: listed on neither chooser, so neither menu offers it.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="usb-io-tracks-cd",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_usb",
        note="`make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form"),),
    doc="stock - SPATIALIZER + USB (TRACKS out, CD in).",
    modules=("USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "CD"},
)
