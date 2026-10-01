"""usb-out-master -- stock effects plus USB MIDI and USB AUDIO OUT MASTER, nothing else.

usb-out-tracks-main-cue with track 8's two channels only (the master track, post-FX
pre-fader). For testing USB AUDIO OUT MASTER on a unit that runs stock
projects. Local test remix (27 Sep 2026).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb-out-master",
    # OS SWITCH needs DSP words for its park code (modules/os-switch/
    # dsp_park.asm), and this remix keeps every stock effect, so none are
    # free: it is left out. The image is still a valid switch TARGET (its
    # .OBI boots from any image that carries OS SWITCH).
    os_switch=False,
    family="mods", proof=Proof.PORT, proof_note="",
    doc="stock + USB MIDI + USB AUDIO OUT MASTER (2 ch: track 8).",
    modules=("USB MIDI", "USB AUDIO OUT MASTER",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
