"""midi-scenes -- MIDI SCENES alone.

One ColdFire module, no DSP, no menu row: the reference minimal build of
the DRAM platform with a real mod on it. Not flashed (the 2.0 build of
the module ran on hardware inside ok-ms).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="midi-scenes",
    family="mods", proof=Proof.PORT, proof_note="`verify_scenes` against MIDISC2.1 under the port; not flashed",
    doc="Reference minimal build: the MIDI SCENES ColdFire patch, alone.",
    modules=("MIDI SCENES",),
    fallback="NONE",
)
