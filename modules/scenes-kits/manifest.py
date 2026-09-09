"""SCENES KITS -- the bridge: MIDI SCENES, Octakit and CC PAGE 2 in one image.

Three mods, two shared sites, and until 10 Sep 2026 the ledger refused
every pair (Sam: "rather than make them exclusive can we be brutal and
make them all work?"). This module carries the stubs that let them share:

  * apply_part entry (0x40009094): his wrapper and her engine-load both
    rewrite it. `chains.s` does his pre-work (save the caller into
    apply_ret, return through `after`, `jsr pack`) and jumps into her
    entry, which replays the displaced prologue and runs stock's body
    through her trampoline. His hooks keep their meaning under Kits
    because her active path still applies the STOCK Part window (the
    structure his pack/unpack address through 0x46c82456); she wraps it,
    she does not replace it. While her lifecycle state is not active (boot)
    the site is hers alone -- she inspects the stock caller's return
    address there, and his swap would trip her fatal.
  * the MIDI CC dispatch entry (0x400d64a0): her recipe installs her
    handler, CC PAGE 2 repoints it to its cave. The cave keeps the entry;
    its fall-through (CC_NEXT) becomes her handler instead of stock's, and
    hers falls through to stock as before. CCs 62-67 are ours, then hers,
    then stock's.

Both are declared as Overrides (schema.Override): the build skips his
detour and her two recipe writes at those sites, writes the bridge's own
detour at apply_part, and defines CHAIN_APPLY_NEXT / CC_NEXT as the targets
her writes carried. The ledger owns the sites to this module; a remix
carrying both MIDI SCENES and OCTAKIT without it is still refused.

MEASURED (port): see docs/remixer/PLACEMENT.md and this README. NOT
measured: hardware. Kits semantics beyond the apply path -- his Part
save/reload menu hooks against her LOAD/SAVE KIT menus -- are the open
question this bridge does not answer; it makes the image buildable and
the apply path coherent, no more.
"""

from remix.schema import Detour, Kind, Linked, Module, Override

H = bytes.fromhex

MODULE = Module(
    name="scenes-kits",
    key="SCENES KITS",
    kind=Kind.CF_PATCH,
    doc="The bridge that lets MIDI SCENES, Octakit and CC PAGE 2 share one "
        "image (apply_part and the CC dispatch chained).",
    linked=(Linked("chains", "modules/scenes-kits/chains.s", dram=True),),
    detours=(
        Detour(0x40009094, H("4fefff9848d77cfc"), "chains", "chain_apply_part",
               "apply_part: his pack + after, then her engine load", pad_to=8),
    ),
    overrides=(
        Override(0x40009094, "MIDI SCENES"),
        Override(0x40009094, "OCTAKIT", write="engine-part-load",
                 defsym="CHAIN_APPLY_NEXT"),
        Override(0x400D64A0, "OCTAKIT",
                 write="midi-control-parameter-000-at-400d64a0", defsym="CC_NEXT"),
    ),
)
