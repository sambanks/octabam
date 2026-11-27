"""persistent-buffers -- recorder buffers saved with the project.

STORE + PERSISTENT BUFFERS on the stock effects. Not flashed.
"""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="persistent-buffers",
    family="mods",
    evidence=(Evidence(Level.EMULATOR, ref="verify_persistent_buffers",
        note="verify_persistent_buffers under the port"),),
    doc="Recorder buffers BUFFERS/REC1.wav..REC8.wav under the project on SAVE / LOAD.",
    modules=("STORE", "PERSISTENT BUFFERS",
             *stock.EFFECTS),
    fallback="NONE",
)
