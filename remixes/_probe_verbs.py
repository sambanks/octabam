"""_probe_verbs -- scratch: the stock chooser plus a send, keeping the reverbs."""
from remix.schema import Remix
REMIX = Remix(
    name="_probe_verbs",
    doc="stock chooser plus SEND, keeping the reverbs the build never reached",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV", "SEND"),
    fallback="SEND",
)
