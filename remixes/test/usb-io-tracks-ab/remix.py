"""usb-io-tracks-ab -- the Octatrack as a USB interface: the sixteen track channels out, a stereo pair into inputs A/B (C/D stay on the jacks).

USB AUDIO OUT TRACKS (to the host), USB AUDIO IN AB (from the host; the jacks while its stream is
closed) and USB CROSSBAR (the controller served first on the crossbar,
without which IN loses packet tails under load), with USB MIDI, on the stock
effects minus SPATIALIZER, whose words on payload A hold the IN module's RX
inject: listed on neither chooser, so neither menu offers it.
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="usb-io-tracks-ab",
    family="mods", proof=Proof.PORT, proof_note="`make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form",
    doc="stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN AB.",
    modules=("USB MIDI", "USB AUDIO OUT", "USB CROSSBAR", "USB AUDIO IN",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS"),
              ("octabam.usb-audio-in", "INPUTS"): Pin("AB")},
)
