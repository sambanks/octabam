"""PERSISTENT BUFFERS -- recorder buffers survive project save / load.

On PROJECT SAVE (the project store), non-empty Flex recorder slots 128-135
are written to BUFFERS/REC1.wav..REC8.wav under the project (overwrite).
On PROJECT LOAD / RELOAD, those files are loaded back into the same slots.
Pickup and Flex both use these buffers; this module does not care which
machine is assigned.
"""

from remix.schema import Category, Gate, Kind, Linked, Module, Evidence, Level

MODULE = Module(
    name="persistent-buffers",
    key="PERSISTENT BUFFERS",
    kind=Kind.CF_PATCH,
    category=Category.SETTINGS,
    author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    evidence=(Evidence(Level.UNIT, unit="MKII", date="2026-10-17",
        note="verify_persistent_buffers port; author MKII R2–R6 (17 Oct 2026); R7 PBUF R7.RMX (22 Oct 2026): "
             "short/long save UI immediate, 8 slots, empty skip, load/reload, reopen+play, overwrite, save≡load "
             "play"),),
    doc="On project save, dump non-empty recorder buffers to BUFFERS/REC1.wav..REC8.wav "
        "(overwrite); on project load, restore them.",
    linked=(Linked("pbf", "modules/persistent-buffers/pbuf.s", dram=True),),
    requires=("STORE",),
    conflicts=(
        ("BUFFER SAVER",
         "both write the recorder buffers at SAVE PROJECT, so a save could write them twice"),
    ),
    gates=(Gate("tools/verify/verify_persistent_buffers.py", once=True),),
)
