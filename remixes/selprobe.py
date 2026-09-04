"""SELPROBE -- the rig plus the select-array readout.

`bamsep27` with HELLO WORLD and SELECT PROBE added, and nothing else
changed. It exists for one measurement, on hardware: does the byte our
formula addresses follow a page-2 select when you turn one?

Select HELLO WORLD on any track, open its FX2 page, and read GAIN. Then
open that same track's page 2 and turn a select. The number should follow.
See `modules/selprobe/manifest.py` for how to read it and what a wrong
answer looks like.

⚠️ Not `cfprobe`: both probes register on HELLO WORLD's GAIN, so an image
carries one or the other.
"""

from remix.schema import Remix

REMIX = Remix(
    name="selprobe",
    doc="The rig plus the page-2 select readout, for one hardware measurement.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "HELLO WORLD",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "MENU SHORTCUT", "SELECT PROBE"),
    hidden=("REVERB SERVER", "DELAY SERVER", "SEND",
            "SPECTRUM", "CHARACTER", "MODULATION"),
    grains=2,
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
