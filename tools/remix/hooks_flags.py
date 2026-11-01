"""The HOOKS flags a participant's remix.inc carries (modules/hooks).

A module whose routine a HOOKS bridge calls (frame_tail, frame_entry, boot)
is built with that bridge's flag: 1 when the remix carries the bridge and
the module is in it -- the routine then returns instead of replaying the
stock instructions -- else 0, its own bytes unchanged. Called from a
participant's Linked.include at build time, not when manifests load.
"""
import functools
import pathlib
import runpy

ROOT = pathlib.Path(__file__).resolve().parents[2]


@functools.cache
def _hooks():
    return runpy.run_path(str(ROOT / "modules/hooks/manifest.py"))


def inc(key, modules) -> str:
    """remix.inc lines for module `key` in a selection of module keys."""
    return _hooks()["flags_inc"](key, modules)


def on(bridge, key, modules) -> bool:
    """Is module `key` in HOOKS's `bridge` for a selection of module keys?"""
    h = _hooks()
    return bridge in h["bridged"](modules) and any(p[0] == key for p in h["BRIDGES"][bridge])


def image_row(key, root=ROOT) -> int:
    """The machine list row of machine module `key` in the image last built
    (out/mainos_bus.bin, whose sidecar names its remix): 5, or its place after
    the machines before it (machine_rows)."""
    side = root / "out/mainos_bus.remix"
    if not side.exists():
        return 5
    from remix import registry
    keys = {m.key for m in registry.selected(registry.remix(side.read_text().split()[0]))}
    on = _hooks()["machines"](keys)
    return 5 + on.index(key) if key in on else 5
