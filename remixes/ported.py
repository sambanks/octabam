"""PORTED -- every ported OS mod that is known to coexist, combined.

The pick-and-choose proof: this remix exists to make the build's own ledger
(`tools/remix/ledger.py`) and `verify_menu.py` check every ported module
against every other one in a single image, not just alone. Grows as more
land. Currently: MIDI SCENES (bkkbrls-del/midisc) + LOFI AMF FIX
(bryantysinger/octa-bt-pt) -- no known collision between the two (MIDI
SCENES claims ColdFire free-ROM caves; LOFI AMF FIX claims two DSP-payload
words and no free space at all).
"""

from remix.schema import Remix

REMIX = Remix(
    name="ported",
    doc="Every ported OS mod known to coexist, combined -- the pick-and-"
        "choose proof.",
    modules=("MIDI SCENES", "LOFI AMF FIX"),
    fallback="NONE",
)
