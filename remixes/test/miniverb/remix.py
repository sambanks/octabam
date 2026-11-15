"""Minimal eight-instance reverb development image; unflashed."""
from remix.schema import Evidence, Level, Remix
REMIX = Remix(family="effects", evidence=(Evidence(Level.RENDER,
    note="`make verify-miniverb`"),), name="miniverb", doc="Minimal allocator-owned FDN reverb.",
              modules=("MINIVERB",), fallback="NONE")
