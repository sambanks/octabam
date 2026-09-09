"""KITS -- every firmware mod that composes with Octakit, no effects.

The "just the mods" image of the Octakit family: 256 Kits per Project
(Em) and the LO-FI AMF fix (Bryan T). Two mods cannot join: MIDI SCENES
hooks the same stock routine and addresses the Part window Octakit
replaces (its family is `scenes`), and CC PAGE 2 repoints the MIDI
control-parameter dispatch entry at 0x400d64a0 that her recipe rewrites
(seven `midi-control-parameter` writes -- her own CC handling). CC to
page 2 under Octakit would have to live inside her runtime; the ledger
refuses the pair until then. Nothing of octabam's DSP is placed.
⚠️ Octakit migrates a project's Parts into Kits on load; back up projects
first, and know that going back to stock may lose Kit data (her warning).
Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="kits",
    doc="All the firmware mods of the Octakit family, no effects: 256 Kits "
        "and the LO-FI AMF fix.",
    modules=("OCTAKIT", "LOFI AMF FIX"),
    fallback="NONE",
)
