"""Minimal image for VERBERATION's gate: the module alone, no stock effect listed."""
from remix.schema import Evidence, Level, Remix
REMIX = Remix(family="effects", evidence=(Evidence(Level.RENDER,
    note="`verify_verberation`; not flashed"),), name="verberation",
              doc="VERBERATION alone: the fixture of its render gate.",
              modules=("VERBERATION",), fallback="NONE")
