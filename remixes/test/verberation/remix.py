"""Minimal image for VERBERATION's gate: the module alone, no stock effect listed."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.RENDER, proof_note="`verify_verberation`; not flashed", name="verberation",
              doc="VERBERATION alone: the fixture of its render gate.",
              modules=("VERBERATION",), fallback="NONE")
