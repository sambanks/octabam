"""seamtest -- the bus image plus the recorder-seam cave, for route A.

Not for the unit yet: the cave is measured in the emulator only
(RTOS_FORK 10.17). Build with `REMIX=seamtest make bus` and run
`tools/emu_rtos.py --image out/mainos_seamtest.bin ...` against the
looping-recorder fixtures.
"""

from remix.schema import Remix

REMIX = Remix(
    name="seamtest",
    doc="bus + the recorder-seam ColdFire cave (emulator-only until flashed).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC", "RECORDER SEAM"),
    fallback="SEND",
)
