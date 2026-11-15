"""usb-io-stock14 -- the Octatrack as a USB interface with every stock effect kept: MAIN L/R and CUE L/R out, four channels into inputs A-D.

USB (MAIN CUE out, IN ABCD, USB MIDI) on all fourteen stock effects. Nothing
is harvested, so there is no donor region: USB's RX inject goes above
payload A's code, P:$1fdf, in a load record of its own that a pre-boot copy
of the payload carries (schema.DspSection.tail).
"""

from remix.schema import Evidence, Level, Remix

STOCK14 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")

REMIX = Remix(
    name="usb-io-stock14",
    family="mods", evidence=(Evidence(Level.UNIT, unit="MKII", who="Bryan T", image="OCTABAM4", date="2026-10-22",
        note="macOS: tools/hw/usb_in_tones.py, each input at unity on its own side, the rest within +-1.5 LSB, the"
             " same as the 29- and 39-word injects in their donor regions; `make check` (verify_usb, "
             "verify_usb_in) under the port"),),
    doc="stock (all 14) + USB (MAIN CUE out, ABCD in), the inject at payload A's tail.",
    modules=("USB",) + STOCK14,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "ABCD"},
)
