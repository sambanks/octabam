"""Standard octabam-bus plus the GRANULAR FLEX source engine."""
from dataclasses import replace

from remix import registry
from remix.schema import Proof

BASE = registry.remix("octabam-bus")
REMIX = replace(
    BASE,
    name="granular-bus",
    family="test",
    modules=BASE.modules + ("GRANULAR",),
    proof=Proof.PORT,
    proof_note=(
        "14-case GRANULAR firmware subset, serialized initialization/boot, menus, USB "
        "enumeration/settings and counted DSP budget pass. Isolated bus sends and "
        "CHARACTER audio checked on both cores. No full-remix or hardware qualification."
    ),
    doc="Standard octabam-bus's utilities, delay/reverb hosts, SEND and FX1 effects, plus GRANULAR.",
)
