"""SCENES -- every firmware mod that composes with MIDI SCENES, no effects.

The "just the mods" image for someone who wants the unit's own effects and
the community's firmware changes: MIDI-driven scene locks (bkkbrls-del),
the LO-FI AMF fix (Bryan T) and MIDI CC reaching page-2 knobs (octabam).
Octakit is the one mod that cannot join -- it hooks the same stock routine
and replaces the Part window his code addresses -- so its family is
`kits`. Nothing of octabam's DSP is placed: every stock effect stays, the
chooser is stock's. Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="scenes",
    doc="All the firmware mods of the MIDI SCENES family, no effects: scenes "
        "over MIDI, the LO-FI AMF fix, CC to page 2.",
    modules=("MIDI SCENES", "LOFI AMF FIX", "CC PAGE 2"),
    fallback="NONE",
)
