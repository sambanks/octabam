"""usb-io-tracks-abcd -- the Octatrack as a USB interface: the sixteen track channels out, four channels into inputs A-D.

USB AUDIO OUT TRACKS (to the host), USB AUDIO IN ABCD (from the host; the jacks while its stream is
closed) and USB CROSSBAR (the controller served first on the crossbar,
without which IN loses packet tails under load), with USB MIDI, on the stock
effects minus SPATIALIZER, whose words on payload A hold the IN module's RX
inject: listed on neither chooser, so neither menu offers it.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb-io-tracks-abcd",
    image_name="IO-TRK-ABCD",
    family="mods", proof=Proof.PORT, proof_note="`make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form",
    doc="stock - SPATIALIZER + USB (TRACKS out, ABCD in).",
    modules=("USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "ABCD"},
)
