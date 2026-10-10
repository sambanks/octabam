"""ok-ms -- KITS + MIDI SCENES on the stock effects.

No octabam DSP, no CC MAP, no LO-FI fix. The 14 stock effects are listed
so the FX2 chooser is stock's (a remix with no FX2 modules otherwise draws
a one-row chooser). Built 14 Sep 2026 as OKMS1 with Em's Octakit and
confirmed working on hardware by midisc's author the same day; its first
Part Reload trapped in Octakit's caller check, and OKMS2 carried the KITS
RELOAD bridge (README.md). Since 6 Oct 2026 KITS replaces Octakit: the
stock Part Reload runs as on stock, so no bridge.

KITS migrates the Parts (or imports Octakit's kits3a/b.work) into
kits.work on the first load: back up projects first.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="ok-ms",
    family="mods", proof=Proof.PORT, proof_note="with Octakit on midisc's author's unit, 14 Sep 2026 (OKMS2); with KITS under the port",
    doc="KITS + MIDI SCENES on the stock effects: the two mods alone.",
    modules=("MIDI SCENES", "STORE", "KITS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
