"""ok-ms -- Octakit + MIDI SCENES on the stock effects.

No octabam DSP, no CC MAP, no LO-FI fix. The 14 stock effects are listed
so the FX2 chooser is stock's (a remix with no FX2 modules otherwise draws
a one-row chooser). Built 14 Sep 2026 as OKMS1 (VERSION=OKMS1); confirmed
working on hardware by midisc's author the same day: the first image from
this pipeline to run on a unit -- and its first Part Reload trapped (VEC:04
in Octakit's caller check; modules/kits-reload). KITS RELOAD bridges it;
OKMS2 = this remix with the bridge, unflashed.

Octakit migrates Parts into Kits on load: back up projects first.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="ok-ms",
    family="mods", proof=Proof.HARDWARE, proof_note="midisc's author's unit, 14 Sep 2026 (OKMS2)",
    doc="Octakit + MIDI SCENES on the stock effects: the two mods alone.",
    modules=("MIDI SCENES", "OCTAKIT", "KITS RELOAD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
