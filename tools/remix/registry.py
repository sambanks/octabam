"""Discovery of remix modules: the index.

Every directory under `modules/` holding a `manifest.py` that exports a
`MODULE` is a contribution. Nothing else registers a module -- there is no
central list to edit, so adding one is adding a directory, and two modules
cannot silently disagree about which of them is "the" delay because the
registry refuses duplicate keys and ids.

Directories whose name starts with `_` or `.` are skipped, which is what
keeps `modules/_template/` out of every build.

The STOCK FX2 effects (tools/remix/stock.py) are registered alongside, under
their own keys ("FILTER", "CHORUS", ...), so a remix keeps one in the chooser
by listing it exactly as it lists a module. They are Kind.STOCK: no code, no
clone, no words -- the build writes only their chooser row.
"""

from __future__ import annotations

import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from remix.schema import NO_FALLBACK, on_the_bus  # noqa: E402
MODULES_DIR = ROOT / "modules"

_cache: dict[str, object] | None = None


def _exec(path: pathlib.Path, modname: str):
    """Execute a manifest or remix file, ALWAYS from the source on disk.

    Deliberately not importlib's file loader. That one caches bytecode and
    validates the cache on the source's size and its mtime IN WHOLE SECONDS,
    so an edit that lands in the same second and does not change the file's
    length is ignored -- and "change one hex digit in a manifest" is exactly
    that edit. The build then silently uses the previous declaration.

    Found here by flipping an fx2 id to 0x06 to test the ledger, flipping it
    back, and watching the build keep refusing. On a manifest that is not a
    stale cache, it is a firmware image that does not match its own source.
    """
    ns = types.ModuleType(modname)
    ns.__file__ = str(path)
    exec(compile(path.read_text(), str(path), "exec"), ns.__dict__)
    return ns


def _load_one(manifest: pathlib.Path):
    # Manifests say `from remix.schema import ...`, so tools/ must be
    # importable no matter who called us -- the build script, a verify tool
    # run standalone, or `python3 -m`.
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    mod = _exec(manifest, f"remix_manifest_{manifest.parent.name}")
    if not hasattr(mod, "MODULE"):
        raise SystemExit(f"{manifest} defines no MODULE")
    return mod.MODULE


def modules() -> dict[str, object]:
    """Every discovered module, keyed by its build key (e.g. "REVERB SERVER")."""
    global _cache
    if _cache is not None:
        return _cache
    found: dict[str, object] = {}
    seen_dirs: dict[str, str] = {}
    seen_ids: dict[int, str] = {}
    for d in sorted(MODULES_DIR.iterdir()) if MODULES_DIR.is_dir() else []:
        if not d.is_dir() or d.name.startswith(("_", ".")):
            continue
        manifest = d / "manifest.py"
        if not manifest.exists():
            continue
        m = _load_one(manifest)
        if m.name != d.name:
            raise SystemExit(f"{manifest}: declares name {m.name!r} but lives "
                             f"in modules/{d.name}/")
        if m.key in found:
            raise SystemExit(f"two modules claim the key {m.key!r}: "
                             f"{seen_dirs[m.key]} and {d.name}")
        if m.menu is not None:
            if m.menu.fx2_id in seen_ids:
                raise SystemExit(
                    f"two modules claim FX2 id 0x{m.menu.fx2_id:02x}: "
                    f"{seen_ids[m.menu.fx2_id]} and {d.name}")
            seen_ids[m.menu.fx2_id] = d.name
        seen_dirs[m.key] = d.name
        found[m.key] = m
    from remix import stock
    for m in stock.MODULES:
        if m.key in found:
            raise SystemExit(f"module {seen_dirs[m.key]} claims the key "
                             f"{m.key!r}, which is a stock effect's")
        if m.menu.fx2_id in seen_ids:
            # A DECLARED replacement is allowed to share the id -- that is
            # what it declared. It must name THIS effect, though: replacing
            # LO-FI while sitting on PHASER's id is a typo that would
            # otherwise ship.
            other = found.get(seen_ids[m.menu.fx2_id]) or \
                next((x for x in found.values()
                      if x.menu is not None
                      and x.menu.fx2_id == m.menu.fx2_id), None)
            rep = other.menu.replaces if (other is not None
                                          and other.menu is not None) else None
            if rep != m.key:
                raise SystemExit(
                    f"module {seen_ids[m.menu.fx2_id]} claims FX2 id "
                    f"0x{m.menu.fx2_id:02x}, which is stock {m.key}'s -- the "
                    f"dispatch tables are shared with FX1, so it would hijack "
                    f"that effect on both menus"
                    + (f" (it declares replaces={rep!r}, not {m.key!r})"
                       if rep else ""))
            found[m.key] = m
            continue
        seen_ids[m.menu.fx2_id] = m.key
        found[m.key] = m
    _cache = found
    return found


def by_key(key: str):
    try:
        return modules()[key]
    except KeyError:
        raise SystemExit(f"no module with key {key!r} -- have "
                         f"{sorted(modules())}")


def by_name(name: str):
    for m in modules().values():
        if m.name == name:
            return m
    raise SystemExit(f"no module named {name!r}")


def asm(key_or_name: str) -> str:
    """A module's DSP source, repo-relative.

    Tools ask for this rather than spelling the path, so moving a module's
    source is a one-line change in its manifest instead of a sweep through
    every wrapper -- which is how those paths went stale before.
    """
    for m in modules().values():
        if key_or_name in (m.key, m.name):
            if m.dsp is None:
                raise SystemExit(f"module {key_or_name!r} has no DSP source")
            return m.dsp.asm
    raise SystemExit(f"no module {key_or_name!r}")


def asm_by_stem() -> dict[str, pathlib.Path]:
    """Source filename stem -> absolute path, for tools that key by filename."""
    return {pathlib.Path(m.dsp.asm).stem: ROOT / m.dsp.asm
            for m in modules().values() if m.dsp is not None}


def by_id(fx2_id: int):
    for m in modules().values():
        if m.menu is not None and m.menu.fx2_id == fx2_id:
            return m
    return None


REMIXES_DIR = ROOT / "remixes"
# The plain two-server image, the refhash gate's subject: what `tools/*.py`
# build when REMIX is unset. `make` passes REMIX=bamsep26, the rig.
DEFAULT_REMIX = "bus"


def remix(name: str = DEFAULT_REMIX):
    """Load remixes/<name>.py and return its REMIX."""
    f = REMIXES_DIR / f"{name}.py"
    if not f.exists():
        raise SystemExit(f"no remix {name!r} -- have {sorted(remix_names())}")
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    mod = _exec(f, f"remix_sel_{name}")
    if not hasattr(mod, "REMIX"):
        raise SystemExit(f"{f} defines no REMIX")
    r = mod.REMIX
    known = modules()
    for k in r.modules:
        if k not in known:
            raise SystemExit(f"remix {name!r} selects unknown module {k!r} -- "
                             f"have {sorted(known)}")
    # ⚠️ THE FIRMWARE'S OWN NONE IS ONLY SAFE WHEN THERE IS NO BUS. An
    # unassigned track then runs nothing at all -- including the housekeeping
    # block -- and a remix with a server on one core and no participant on
    # core 0 would leave the rotation frozen and the accumulators uncleared.
    # With neither a server nor a client in the image there is no bus to
    # keep, so the question does not arise. See schema.NO_FALLBACK for the
    # whole argument and for why it cannot be settled by a local test.
    if r.fallback == NO_FALLBACK:
        on_bus = [k for k in r.modules if on_the_bus(known[k])]
        if on_bus:
            raise SystemExit(
                f"remix {name!r}: fallback {NO_FALLBACK!r} is only for a remix "
                f"with no bus participant, and this one has "
                f"{', '.join(sorted(on_bus))} -- an unassigned track would run "
                f"nothing, so nobody would flip the rotation or clear the "
                f"accumulators. Use fallback=\"SEND\".")
    return r


def remix_names() -> list[str]:
    if not REMIXES_DIR.is_dir():
        return []
    return sorted(f.stem for f in REMIXES_DIR.glob("*.py")
                  if not f.name.startswith("_"))


def selected(r) -> list:
    """The remix's modules, in its declared order."""
    return [modules()[k] for k in r.modules]
