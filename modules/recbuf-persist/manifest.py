"""RECBUF PERSIST -- recorder buffers survive project save / load.

On PROJECT SAVE (the project store), non-empty Flex recorder slots 128-135
are written to BUFFERS/REC1.wav..REC8.wav under the project (overwrite).
On PROJECT LOAD / RELOAD, those files are loaded back into the same slots.
Pickup and Flex both use these buffers; this module does not care which
machine is assigned.
"""

from remix.schema import Category, Gate, Kind, Linked, Module, Proof

MODULE = Module(
    name="recbuf-persist",
    key="RECBUF PERSIST",
    kind=Kind.CF_PATCH,
    category=Category.SETTINGS,
    author="iliamurzinov",
    author_url="https://github.com/iliamurzinov",
    proof=Proof.CHECK,
    proof_note="verify_recbuf: symbols + port save/load; author MKII R2–R6 (17 Oct 2026): BUFFERS/RECn.wav; !BUFFERS left UI unassigned",
    doc="On project save, dump non-empty recorder buffers to BUFFERS/REC1.wav..REC8.wav "
        "(overwrite); on project load, restore them.",
    linked=(Linked("rbp", "modules/recbuf-persist/recbuf.s", dram=True),),
    requires=("STORE",),
    gates=(Gate("tools/verify/verify_recbuf.py", once=True),),
)
