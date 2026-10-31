"""octabam's ColdFire core with SIDECHAIN_COMPRESSOR in its per-core form and no demand loader and no LOAD METER
(it shares SC's MON site, bridged only in the demand form): the split between the loader and the core modules for the KEY leak (sambanks/octabam#934)."""
import importlib.util, pathlib
from remix.schema import Pin, Proof, Remix

_spec = importlib.util.spec_from_file_location("_octabam_remix", pathlib.Path(__file__).resolve().parents[2] / "octabam" / "remix.py")
_o = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_o)

REMIX = Remix(
    name="sc-core",
    family="test", proof=Proof.CHECK, proof_note="",
    doc="octabam's ColdFire core with SIDECHAIN_COMPRESSOR per-core (SPRING REV's words), no demand loader, no LOAD METER",
    modules=tuple(k for k in _o.CORE if k != "LOAD METER") + ("LOFI AMF FIX", "MODE DEFAULTS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "SIDECHAIN_COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE",
    # as octabam, so the ColdFire side is octabam's; FORM stays PER_CORE (no loader here)
    settings={k: v for k, v in _o.REMIX.settings.items() if k != ("octabam.sidechain-compressor", "FORM")
              and not k[1] == "SLOTS"},
)
