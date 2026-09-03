"""CFPROBE -- the rig plus the ColdFire headroom probe and its readout.

BamSep26 as it will be flashed, with two additions: HELLO WORLD, whose GAIN
knob is the probe's display, and CF PROBE, the cave that times the audio
interrupt's per-frame delay routine and burns on the crossfader. The point
of building it on the rig rather than on `hello` is the load: the sweep
must run against the ColdFire work a real set produces, and the DSP
selection is the one the set will use.

Eight FX2 rows, one past the in-place chooser list, so the panel scrolls.
Select HELLO WORLD on any track to read the probe; the DSP side of HELLO
WORLD is a gain, so keep that track's GAIN at 96..127 (the total-busy band,
and within 2 dB of unity) unless you are reading another band.

A diagnostic image, not a performance one. docs/FLASHPLAN.md prices the
flash and modules/cfprobe/README.md is the procedure.
"""

from remix.schema import Remix

REMIX = Remix(
    name="cfprobe",
    doc="The rig plus the ColdFire headroom probe, read out on HELLO WORLD.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "DELAY",
             "FILTER STATION", "CHARACTER STATION", "MODULATION STATION",
             "TEMPO SYNC", "MENU SHORTCUT", "HELLO WORLD", "CF PROBE"),
    fallback="SEND",
    fx1=("FILTER STATION", "CHARACTER STATION", "MODULATION STATION"),
)
