"""ZOOM KEEP -- the audio editor keeps its zoom when a slice is auditioned.

In SLICES trig mode a trig picks and plays a slice in the audio editor, and
stock zooms the SLICE page out to fit the whole slice each time. With ZOOM
KEEP the zoom stays where it is and the slice start is scrolled into view, so
an edit zoomed in on a marker survives auditioning. zoomkeep.s has the detail.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

MODULE = Module(
    name="zoom-keep",
    key="ZOOM KEEP",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES, author="8thmyth", author_url="https://github.com/8thmyth",
    proof=Proof.HARDWARE,
    proof_note="8thmyth's MKI, image OCTABAMHC (remix test/octabam-lazy-chop), 14 Nov 2026; verify_zoom_keep under the port",
    doc="The audio editor keeps its zoom when a slice is auditioned (SLICES trig mode); the slice start scrolls into view.",
    linked=(Linked("zoomkeep", "modules/zoom-keep/zoomkeep.s", dram=True),),
    detours=(
        # The view fit call in stock's slice select 0x40071668 (jsr 0x40077138 at 0x40071712). Read from 1.40C.
        Detour(0x40071712, bytes.fromhex("4eb940077138"), "zoomkeep", "zk_fitkeep",
               "editor slice select (SLICES trig mode): the zoom kept, the slice start scrolled into view", kind="jsr"),
    ),
    gates=(Gate("tools/verify/verify_zoom_keep.py", venv=True, stage="image"),),
)
