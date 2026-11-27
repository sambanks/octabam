"""OCTA303 alone: the OCTA-303 machine with the stock effects."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="octa303",
    family="mods", evidence=(Evidence(Level.EMULATOR,
        note="built and its UI gate run under the port, 19 Oct 2026; OCTA303 itself on the owner's MK1 in remix "
             "acidtrack (ACIDV70, BUILD 87)"),),
    doc="the OCTA-303 machine (a circuit-modelled TB-303 voice on the ColdFire) with the stock effects.",
    modules=("OCTA303", *stock.EFFECTS),
    fallback="NONE",
)
