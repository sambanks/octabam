"""mods -- every ColdFire mod that can share one image, stock effects only.

MIDI SCENES (bkkbrls-del), KITS, the LO-FI AMF fix (Bryan T), CC MAP,
the five recorder fixes (recfix until 28 Sep 2026), REPITCH (repeat98),
DIRECT_JUMP_KYOTI (with BATCH_BUGFIXES, which it requires) and
RELOAD_FROM_PROJECT (Zac Kyoti; refused beside Octakit until 6 Oct 2026), USB MIDI and USB AUDIO OUT TRACKS MAIN CUE
(markandrus). No DSP module; the 14 stock effects are listed so the FX2
chooser is stock's. Tim Hastie's DIRECT JUMP declares a conflict with
DIRECT_JUMP_KYOTI, and SCALE QUANTIZER's 2,916 B ROM unit beside REPITCH's
576 B leaves CC MAP's 724 B cave no run in the free ROM (measured 28 Sep
2026): they live in octatrick. Booted under the ColdFire port; unflashed
as a whole.

KITS migrates the Parts into kits.work on the first load: back up projects
first.
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="mods",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="Every ColdFire mod in one image on the stock effects: MIDI SCENES, "
        "KITS, the recorder fixes, REPITCH, the KYOTI direct jump and reload, USB MIDI + AUDIO.",
    modules=("MIDI SCENES", "STORE", "KITS", "LOFI AMF FIX", "CC MAP",
             "RECORDER LOOP FIX", "RLEN PLEN",
             "REPITCH", "DIRECT_JUMP_KYOTI", "BATCH_BUGFIXES", "RELOAD_FROM_PROJECT",
             "USB MIDI", "USB AUDIO OUT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS MAIN CUE")},
)
