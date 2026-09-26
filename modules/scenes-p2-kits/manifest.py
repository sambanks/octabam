"""SCENES P2 KITS -- the bridge that lets SCENES P2 and Octakit share the
two page-2 editor entries (FX2 0x4003a9dc, FX1 0x4003abe4).

Her recipe replaces each entry with a jump to her wrapper, which prepares a
kit-write token, calls the stock body and validates at her marker inside
it that the body stored what she expects; a body that is skipped trips her
check (fatal). SCENES P2 detours the same entries: a turn with a scene held
must not reach the body at all. With the bridge her two writes are
overridden and the build defines P2_NEXT2 / P2_NEXT1 as the wrappers they
carried, so SCENES P2's stubs sit at the entries, take a held-scene turn
themselves (a lock in the pool, none of her state touched) and otherwise
jump on to her wrapper with the entry state untouched: her protocol runs
whole for every Part edit. `Kind.CF_PATCH`, nothing of its own to use.

Requires both SCENES P2 and OCTAKIT in the remix: with the overrides and no
SCENES P2 stub at the entries her wrappers would be unreachable.
"""

from remix.schema import Kind, Module, Override

MODULE = Module(
    name="scenes-p2-kits",
    key="SCENES P2 KITS",
    kind=Kind.CF_PATCH,
    doc="The bridge that lets SCENES P2 and Octakit share the page-2 editor entries.",
    overrides=(
        Override(0x4003A9DC, "OCTAKIT",
                 write="track-setup-byte-editors-003-at-4003a9dc", defsym="P2_NEXT2"),
        Override(0x4003ABE4, "OCTAKIT",
                 write="track-setup-byte-editors-006-at-4003abe4", defsym="P2_NEXT1"),
    ),
    requires=("SCENES P2", "OCTAKIT"),
)
