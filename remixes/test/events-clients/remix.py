"""Focused shared EVENTS client fixture with USB audio and hardware load readings."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="events-clients",
    family="probes", evidence=(Evidence(Level.EMULATOR,
        note="Tested on radiohagen's MKII (25 Oct 2026): controlled trig undo, CONTINUE and 600-second audio "
             "capture."),),
    doc="EVENTS with EUCLID in both FX slots, PLOCKS P2, USB MAIN/CUE and LOAD METER.",
    modules=("BRAIN", "STORE", "EVENTS", "EUCLID", "SCENES P2", "PLOCKS P2",
             "USB", "LOAD METER", "ATA WRITE GUARD", "FILTER", "COMPRESSOR", "PLATE REV"),
    fx1=("EUCLID", "FILTER", "COMPRESSOR"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
