"""Discovery of remix modules: the index.

Every directory under `modules/` holding a `manifest.py` that exports a
`MODULE` is a contribution. Nothing else registers a module -- there is no
central list to edit, so adding one is adding a directory, and two modules
cannot silently disagree about which of them is "the" delay because the
registry refuses duplicate keys and ids.

Directories whose name starts with `_` or `.` are skipped, which is what
keeps `modules/_template/` out of every build.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULES_DIR = ROOT / "modules"

_cache: dict[str, object] | None = None


def _load_one(manifest: pathlib.Path):
    # Manifests say `from remix.schema import ...`, so tools/ must be
    # importable no matter who called us -- the build script, a verify tool
    # run standalone, or `python3 -m`.
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    spec = importlib.util.spec_from_file_location(
        f"remix_manifest_{manifest.parent.name}", manifest)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
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


def by_id(fx2_id: int):
    for m in modules().values():
        if m.menu is not None and m.menu.fx2_id == fx2_id:
            return m
    return None
