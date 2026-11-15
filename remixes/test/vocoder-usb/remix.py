"""vocoder-usb -- the vocoder remix plus USB (TRACKS PRE, MAIN, CUE; IN OFF), so a VOCODER
performance records cleanly over USB: each track post-FX pre-fader on channels 1-16, MAIN (after
the crossfader and scenes) on 17-18, CUE on 19-20, and USB MIDI. USB is ColdFire code in DRAM and
takes no DSP words or cycles; VOCODER's DSP side is the vocoder remix's, byte for byte."""
from remix.schema import Evidence, Level, Remix
REMIX = Remix(family="effects", evidence=(Evidence(Level.EMULATOR,
    note="make check under the ColdFire port, 10 Oct 2026; not flashed"),),
              name="vocoder-usb", doc="The vocoder remix plus USB MIDI and USB audio out, TRACKS MAIN CUE (20 channels over USB: the tracks, MAIN, CUE).",
              modules=("VOCODER",
                       "FILTER", "EQUALIZER", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "SPRING REV", "DARK REV",
                       "USB"),
              fallback="NONE",
              fx1=("FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
                   "COMB FILTER", "COMPRESSOR", "LO-FI"),
              settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
                        ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
                        ("octabam.usb", "IN"): "OFF"})
