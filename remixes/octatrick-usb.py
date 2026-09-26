"""octatrick-usb -- octatrick plus USB MIDI and USB AUDIO.

Tim Hastie's SYNTH MACHINE, SCALE QUANTIZER and DIRECT JUMP (remixes/
octatrick.py) with markandrus's USB MIDI and USB AUDIO on the same DRAM
platform: the unit appears to a host as card storage + a class-compliant
MIDI port + a 20-channel 44.1 kHz 24-bit audio input (tracks 1-16, MAIN
17-18, CUE 19-20; at full speed the stereo sum). The stock effects, both
DSP payloads and their dispatch stay stock (fallback NONE, the usb-lean
pattern). The synth's voice engine and the USB units share the platform
reserve. Build with `make image REMIX=octatrick-usb BUILD=N`;
docs/remixes/usb.md has the use steps.
"""

from remix.schema import Remix

REMIX = Remix(
    name="octatrick-usb",
    doc="SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP + USB MIDI + USB AUDIO on the stock effects.",
    modules=("DIRECT JUMP", "SCALE QUANTIZER", "SYNTH MACHINE",
             "USB MIDI", "USB AUDIO",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
