"""midi-scenes -- MIDI SCENES alone, plus direct-jump for the swd gate.

ColdFire modules, no DSP, no menu rows: the reference minimal build of
the DRAM platform. This remix has not been flashed.
MIDISC 2.0 ran on bkkbrls-del's unit in the `ok-ms` image (14 Sep 2026).
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="midi-scenes",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_scenes",
        note="`verify_scenes` against MIDISC2.1 under the port; not flashed"),),
    doc="Reference minimal build: the MIDI SCENES ColdFire patch, plus direct-jump so `swd` runs.",
    modules=("STORE", "MIDI SCENES", "DIRECT JUMP",),
    fallback="NONE",
)
