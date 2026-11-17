"""Stock effects plus ZOOM KEEP: the audio editor keeps its zoom when a slice is auditioned"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="zoom-keep",
    family="mods", proof=Proof.CHECK, proof_note="verify_zoom_keep under the port; the module itself on 8thmyth's MKI in test/octabam-lazy-chop (OCTABAMHC, 14 Nov 2026)",
    doc="stock effects with ZOOM KEEP (the audio editor keeps its zoom when a slice is auditioned).",
    modules=("ZOOM KEEP",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
