"""MIDI SCENES -- the minimal build: the ColdFire scene-lock patch, alone.

Adds no effect and touches no DSP, so the smallest image the module system
can produce with it is exactly one module: MIDI SCENES
(`modules/midi-scenes/manifest.py`), which ports bkkbrls-del/midisc's
MIDI-driven scene locks onto this project's own CavePatch convention. No
menu row, no FX2 id -- the fallback question doesn't apply here the way it
does for a DSP effect, so this mirrors `remixes/hello.py`'s shape
(NO_FALLBACK) rather than `remixes/tempo-sync`-style bundling into a rig.

Kept solo deliberately: MIDI SCENES pins two caves (SAFE_CAVE, CAVE2) into
the exact free-ROM run `busscreen` and `menushortcut` also use. Adding
either of those to this remix is a real address collision, not a bug in
the ledger -- see `modules/midi-scenes/manifest.py`'s docstring.
"""

from remix.schema import Remix

REMIX = Remix(
    name="midi-scenes",
    doc="Reference minimal build: the MIDI SCENES ColdFire patch, alone.",
    modules=("MIDI SCENES",),
    fallback="NONE",
)
