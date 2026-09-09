"""MODS -- every community firmware mod in one image, no effects.

MIDI SCENES (bkkbrls-del), Octakit (Em), the LO-FI AMF fix (Bryan T) and
CC to page 2 (octabam), bridged by SCENES KITS so the two shared stock
sites carry all of them: apply_part runs his pack/after around her
engine load, and the CC dispatch runs our cave, then hers, then stock's.
Nothing of octabam's DSP is placed. ⚠️ Octakit migrates Parts into Kits
on load: back up projects first. ⚠️ The apply path is measured under the
port; his Part save/reload menu hooks against her Kit menus are not (see
modules/scenes-kits). Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="mods",
    doc="Every community firmware mod in one image: MIDI SCENES + Octakit + "
        "the LO-FI AMF fix + CC to page 2, bridged.",
    modules=("MIDI SCENES", "OCTAKIT", "LOFI AMF FIX", "CC PAGE 2", "SCENES KITS"),
    fallback="NONE",
)
