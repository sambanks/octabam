"""usb-out-tracks-main-cue -- stock effects plus USB MIDI and USB AUDIO, nothing else.

For testing the USB stream (tracks 1-16, MAIN 17-18, CUE 19-20) on a unit
that runs stock projects: no rig stations, no chooser changes, no project
stamping. Local test remix (Bryan T, 25 Sep 2026).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb-out-tracks-main-cue",
    # OS SWITCH needs DSP words for its park code (modules/os-switch/
    # dsp_park.asm), and this remix keeps every stock effect, so none are
    # free: it is left out. The image is still a valid switch TARGET (its
    # .OBI boots from any image that carries OS SWITCH).
    os_switch=False,
    family="mods", proof=Proof.PORT, proof_note="",
    doc="stock + USB MIDI + USB AUDIO (20 ch: tracks, MAIN, CUE).",
    modules=("USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
