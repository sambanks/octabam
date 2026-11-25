"""OCTA303 SEAM: the hybrid OCTA-303 (the voice after the VCO on the DSP) with dEVILish and the stock effects that
leave it room: DJ EQ out (its curve bank holds the tables), COMPRESSOR and LO-FI out (their P words hold the code),
PHASER out (dEVILish takes its id)."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="octa303-seam",
    family="mods", evidence=(Evidence(Level.EMULATOR, date="2026-11-25", ref="tools/octa303/v82/play_gate.py",
        note="built; OCTA303 SEAM's own checks (tools/octa303/seam) on the author's remix aCiDhYb, which runs on "
             "the author's MKI (ACIDV100); this remix is the module's gate carrier"),),
    doc="the hybrid OCTA-303 (OCTA303 SEAM: FM, filter, VCA, MUFF, DIST and output on the DSP) with dEVILish and the "
        "stock effects but DJ EQ, COMPRESSOR, LO-FI and PHASER.",
    modules=("OCTA303", "OCTA303 SEAM", "DEVILISH", "FILTER", "EQUALIZER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "DEVILISH"),
    fallback="NONE",
)
