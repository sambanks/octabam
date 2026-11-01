"""Standard octabam with GRANULAR in place of the mutually exclusive OCTA303."""
from dataclasses import replace

from remix import registry
from remix.schema import Proof

BASE = registry.remix("octabam")
REMIX = replace(
    BASE,
    name="granular-octabam",
    family="test",
    modules=tuple(key for key in BASE.modules if key != "OCTA303") + ("GRANULAR",),
    proof=Proof.PORT,
    proof_note=(
        "14-case GRANULAR firmware subset, serialized initialization/boot, menus, USB "
        "enumeration/settings and counted DSP budget pass. MODULATION/SPECTRUM publication "
        "and isolated FX1 audio checked on both cores. No full-remix or hardware qualification."
    ),
    doc="Standard octabam's utilities, stock and demand-loaded effects, with GRANULAR replacing OCTA303.",
)
