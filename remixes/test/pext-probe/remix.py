"""PEXT PROBE on FX1 beside the stock effects: PLATE REV and SPRING REV give up their words, and EQUALIZER's id is the probe's.

A measurement instrument for one hardware run (modules/pextprobe/README.md): it tests how far P
memory reaches above P:0x2000 on each DSP core and reports it in the audio of the track it sits on; USB
carries the tracks (16 channels, PRE) to the host, which is where the report is read."""
from remix.schema import Evidence, Level, Remix
REMIX = Remix(family="effects", evidence=(Evidence(Level.EMULATOR),),
              name="pext-probe", doc="PEXT PROBE on FX1 and USB audio out (TRACKS) beside the stock effects (all but EQUALIZER, whose id it takes, and PLATE REV and SPRING REV, whose words it takes).",
              modules=("USB", "PEXT PROBE",
                       "FILTER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "DARK REV"),
              fx1=("PEXT PROBE",
                   "FILTER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
                   "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
              fallback="NONE",
              settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 0,
                        ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
                        ("octabam.usb", "IN"): "OFF"})
