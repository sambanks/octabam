"""mods -- every ColdFire mod that can share one image, stock effects only.

MIDI SCENES (bkkbrls-del), Octakit (Em), the LO-FI AMF fix (Bryan T),
CC MAP, SCENES KITS and KITS RELOAD (the bridges), the five recorder
fixes (recfix until 28 Sep 2026), REPITCH (repeat98), USB MIDI and USB
AUDIO OUT TRACKS MAIN CUE (markandrus). No DSP module; the 14 stock effects
are listed so the FX2 chooser is stock's. SCENES P2 is out: the ledger
refuses it beside KITS RELOAD and MIDI SCENES. octatrick's three are out
(measured 28 Sep 2026): DIRECT JUMP's hook at 0x400a06d6 is a site
Octakit's recipe writes, and SCALE QUANTIZER's 2,916 B ROM unit beside
REPITCH's 576 B leaves CC MAP's 724 B cave no run in the free ROM; they
live in octatrick. Booted under the ColdFire port; unflashed as a
whole (ok-ms, its subset, has run on hardware).

Octakit migrates Parts into Kits on load: back up projects first. midisc's
Part save/reload menu hooks against Octakit's Kit menus are unmeasured.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="mods",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="Every ColdFire mod in one image on the stock effects: MIDI SCENES, "
        "Octakit, the recorder fixes, REPITCH, USB MIDI + AUDIO (octatrick's three cannot join it).",
    modules=("MIDI SCENES", "OCTAKIT", "LOFI AMF FIX", "CC MAP", "SCENES KITS", "KITS RELOAD",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING", "RECORDER HOLD", "RLEN PLEN",
             "REPITCH",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
