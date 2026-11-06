"""Minimal image for STUDIO VERB's gate: the module alone, no stock effect listed."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.RENDER, proof_note="`verify_studioverb`; not flashed", name="studioverb",
              doc="STUDIO VERB alone: the fixture of its render gate.",
              modules=("STUDIO VERB",), fallback="NONE")
