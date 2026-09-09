"""softretrig -- the bus image plus the FLEX soft-retrigger cave, for the port.

Not for the unit yet: the cave is scored in the C++ port only (RTOS_FORK
10.47). Build with `REMIX=softretrig make bus` and render the click fixtures
with `tools/emu/ot_emu --image out/mainos_softretrig.bin --pre-roll 200 ...`
(modules/flex-softretrig/README.md has the exact invocation).
"""

from remix.schema import Remix

REMIX = Remix(
    name="softretrig",
    doc="bus + the FLEX soft-retrigger ColdFire cave (port-scored until flashed).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC", "FLEX SOFT RETRIG"),
    fallback="SEND",
)
