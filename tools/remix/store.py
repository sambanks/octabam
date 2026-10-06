"""Settings resolved for a remix, the refusals, and the lock file.

docs/proposals/STORE.md sections 2 and 4 are the rules. Layers 1 and 2
(the manifest's default and the remix's value or Pin) are resolved here, at
build. Layers 3 and 4 (card and project) exist only when the remix carries
the CORE module.

    python3 tools/remix/store.py resolve <remix>      the value of every setting and its layer
    python3 tools/remix/store.py check                every module's lock, every remix's settings
    python3 tools/remix/store.py lock <module> [--retire KEY ...] [--retire-param KEY ...]
"""
from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from remix.schema import (CORE_KEY, Apply, Binary, Blob, Number, Option, Pin,  # noqa: E402
                          Trigger)

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCK = "store.lock"

# CS1 (battery SRAM) that stock references nothing in: its whole-CS1
# initialise writes it, nothing reads it (docs/firmware/STEP_LOCKS.md
# section 6). The early block takes the largest run left after every
# selected module's Claims.sram.
CS1_FREE = (0x100F859C, 0x100FFF00)
EARLY_HEADER = 4                 # magic, version, 16-bit sum (STORE.md section 6.4)


# ---- resolution -----------------------------------------------------------

@dataclass(frozen=True)
class Resolved:
    store_id: str
    module: str                  # module key
    key: int
    name: str
    value: object                # an Option is its index
    layer: str                   # "manifest", "remix" or "pin"
    runtime: bool                # card and project layers apply on the unit

    def shown(self, setting) -> str:
        k = setting.kind
        if isinstance(k, Option):
            return k.labels[self.value]
        if isinstance(k, Blob):
            return f"{len(self.value)} bytes"
        if isinstance(k, Number) and k.unit:
            return f"{self.value} {k.unit}"
        return str(self.value)


def has_core(remix) -> bool:
    return CORE_KEY in remix.modules


def _selected(remix, mods):
    return [mods[k] for k in remix.modules if k in mods]


def _owners(remix, mods) -> dict[str, object]:
    return {m.store.id: m for m in _selected(remix, mods) if m.store is not None}


def resolve(remix, mods) -> list[tuple[Resolved, object]]:
    """(Resolved, Setting) for every setting of every selected module, in
    remix order then key order. Assumes check_remix found nothing."""
    core = has_core(remix)
    out = []
    for m in _selected(remix, mods):
        for s in sorted(m.settings, key=lambda s: s.key):
            given = remix.settings.get((m.store.id, s.name), _ABSENT)
            if given is _ABSENT:
                value, layer = s.default, "manifest"
            elif isinstance(given, Pin):
                value, layer = given.value, "pin"
            else:
                value, layer = given, "remix"
            if isinstance(s.kind, Option):
                value = s.kind.index(value)
            runtime = (core and layer != "pin" and s.apply is not Apply.BUILD
                       and not isinstance(s.kind, Trigger))
            out.append((Resolved(m.store.id, m.key, s.key, s.name, value, layer, runtime), s))
    return out


_ABSENT = object()


# ---- refusals -------------------------------------------------------------

def check_modules(mods) -> list[str]:
    """Registry-wide: two modules with one store id."""
    seen, bad = {}, []
    for m in mods.values():
        st = getattr(m, "store", None)
        if st is None:
            continue
        if st.id in seen:
            bad.append(f"store id {st.id!r}: {seen[st.id]} and {m.name}")
        seen[st.id] = m.name
    return bad


def early_budget(remix, mods) -> int:
    """Bytes of early values the remix's CS1 block can hold: the largest free
    run of CS1_FREE after every selected module's Claims.sram, less the
    block header."""
    lo, hi = CS1_FREE
    taken = sorted((b, b + n) for m in _selected(remix, mods) if m.claims
                   for b, n, _w in m.claims.sram if b < hi and b + n > lo)
    best, at = 0, lo
    for b, e in taken:
        best = max(best, b - at)
        at = max(at, e)
    best = max(best, hi - at)
    return max(0, best - EARLY_HEADER)


def early_settings(remix, mods) -> list[tuple[object, object]]:
    """(module, Setting) of every early setting the CS1 block carries: the
    remix has the core, and the value is neither pinned nor build-time."""
    if not has_core(remix):
        return []
    return [(m, s) for r, s in resolve(remix, mods) for m in [mods[r.module]]
            if s.early and r.runtime]


def check_remix(remix, mods) -> list[str]:
    """Every refusal of STORE.md section 4.3 that needs the remix."""
    bad = []
    sel = _selected(remix, mods)
    if not has_core(remix):
        for m in sel:
            if m.requires_core:
                bad.append(f"{m.name}: its function is stored state and the remix "
                           f"does not carry {CORE_KEY}")
    owners = _owners(remix, mods)
    for entry, given in remix.settings.items():
        if not (isinstance(entry, tuple) and len(entry) == 2):
            bad.append(f"settings entry {entry!r}: (store id, setting name)")
            continue
        sid, name = entry
        m = owners.get(sid)
        if m is None:
            bad.append(f"settings {entry!r}: no selected module files settings under {sid!r}")
            continue
        s = next((s for s in m.settings if s.name == name), None)
        if s is None:
            bad.append(f"settings {entry!r}: {m.name} has no setting {name!r} "
                       f"(has {', '.join(x.name for x in m.settings) or 'none'})")
            continue
        value = given.value if isinstance(given, Pin) else given
        if isinstance(s.kind, Trigger):
            bad.append(f"settings {entry!r}: a Trigger holds no value")
            continue
        why = s.kind.check(value)
        if why:
            bad.append(f"settings {entry!r}: {why}")
    if has_core(remix) and not bad:
        need = sum(s.size for _m, s in early_settings(remix, mods))
        room = early_budget(remix, mods)
        if need > room:
            bad.append(f"early settings take {need} bytes; the free CS1 run of this "
                       f"remix holds {room} after the {EARLY_HEADER}-byte header")
    return bad


# ---- the lock file (STORE.md section 4.4) ---------------------------------

def needs_lock(m) -> bool:
    return m.store is not None or any(p.key is not None for p in m.params)


def _kind_lock(k) -> dict:
    if isinstance(k, Binary):
        return {"type": "binary"}
    if isinstance(k, Option):
        return {"type": "option", "labels": list(k.labels)}
    if isinstance(k, Number):
        return {"type": "number", "min": k.min, "max": k.max, "step": k.step}
    if isinstance(k, Trigger):
        return {"type": "trigger"}
    return {"type": "blob", "max_bytes": k.max_bytes}


def lock_of(m, retired=None) -> dict:
    """The lock file's content for a module as declared now."""
    retired = retired or {"settings": [], "params": []}
    return {
        "store": None if m.store is None else {"id": m.store.id, "major": m.store.major},
        "settings": {str(s.key): {"name": s.name, **_kind_lock(s.kind)}
                     for s in sorted(m.settings, key=lambda s: s.key)},
        "params": {str(p.key): {"slot": i, "count": p.count}
                   for i, p in enumerate(m.params) if p.key is not None},
        "retired": {"settings": sorted(retired["settings"]),
                    "params": sorted(retired["params"])},
    }


def lock_path(m) -> pathlib.Path:
    return ROOT / "modules" / m.name / LOCK


def read_lock(m) -> dict | None:
    p = lock_path(m)
    return json.loads(p.read_text()) if p.exists() else None


def breaks(old: dict, new: dict) -> list[str]:
    """What `new` does to released keys that the lock refuses."""
    bad = []
    major_up = (new["store"] or {}).get("major", 1) > (old["store"] or {}).get("major", 1)
    if old["store"] and new["store"] and old["store"]["id"] != new["store"]["id"]:
        bad.append(f"store id {old['store']['id']!r} became {new['store']['id']!r}")
    for part in ("settings", "params"):
        retired = set(old["retired"][part])
        kept_retired = set(new["retired"][part])
        for k in retired - kept_retired:
            bad.append(f"{part} key {k} was retired and is no longer listed as retired")
        for k in sorted({int(x) for x in new[part]} & (retired | kept_retired)):
            bad.append(f"{part} key {k} was retired and is in use again")
        for k, was in old[part].items():
            now = new[part].get(k)
            if now is None:
                if int(k) not in kept_retired:
                    bad.append(f"{part} key {k} ({was.get('name', 'slot ' + str(was.get('slot')))}) "
                               f"was removed: retire it (store.py lock <module> "
                               f"--retire{'' if part == 'settings' else '-param'} {k})")
                continue
            if part == "params":
                continue
            if now["type"] != was["type"] and not major_up:
                bad.append(f"setting {k} {was['name']!r} changed type {was['type']} -> "
                           f"{now['type']}: a new key, or a new store major")
            if was["type"] == "option" and now["type"] == "option":
                old_l, new_l = was["labels"], now["labels"]
                if new_l[:len(old_l)] != old_l:
                    bad.append(f"setting {k} {was['name']!r}: labels {old_l} became "
                               f"{new_l}; append only")
    return bad


def check_lock(m) -> list[str]:
    """A module that needs a lock has one, it matches the manifest, and the
    manifest breaks nothing it released."""
    if not needs_lock(m):
        return [f"{m.name}: {LOCK} without a store or a keyed param"] \
            if lock_path(m).exists() else []
    old = read_lock(m)
    if old is None:
        return [f"{m.name}: no {LOCK}: python3 tools/remix/store.py lock {m.name}"]
    new = lock_of(m, old["retired"])
    bad = [f"{m.name}: {b}" for b in breaks(old, new)]
    if not bad and new != old:
        bad.append(f"{m.name}: {LOCK} is stale: python3 tools/remix/store.py lock {m.name}")
    return bad


def write_lock(m, retire=(), retire_param=()) -> list[str]:
    old = read_lock(m) or {"store": None, "settings": {}, "params": {},
                           "retired": {"settings": [], "params": []}}
    retired = {"settings": sorted(set(old["retired"]["settings"]) | set(retire)),
               "params": sorted(set(old["retired"]["params"]) | set(retire_param))}
    new = lock_of(m, retired)
    bad = breaks(old, new)
    if bad:
        return bad
    lock_path(m).write_text(json.dumps(new, indent=1, sort_keys=True) + "\n")
    return []


# ---- CLI ------------------------------------------------------------------

def main(argv):
    from remix import registry
    if len(argv) < 2 or argv[1] not in ("resolve", "check", "lock"):
        print(__doc__.strip())
        return 2
    mods = registry.modules()
    if argv[1] == "resolve":
        r = registry.remix(argv[2] if len(argv) > 2 else None)
        bad = check_remix(r, mods)
        if bad:
            print("\n".join(bad))
            return 1
        rows = resolve(r, mods)
        print(f"{r.name}: {len(rows)} settings, core {'in' if has_core(r) else 'absent'}")
        for res, s in rows:
            where = "run time" if res.runtime else "build"
            print(f"  {res.store_id:28s} {res.key:5d} {res.name:16s} "
                  f"{res.shown(s):12s} {res.layer:8s} {where}")
        return 0
    if argv[1] == "check":
        bad = check_modules(mods)
        for m in mods.values():
            bad += check_lock(m)
        for name in registry.remix_names():
            bad += [f"remix {name}: {b}" for b in check_remix(registry.remix(name), mods)]
        print("\n".join(bad) if bad else
              f"store: {sum(needs_lock(m) for m in mods.values())} locked modules, "
              f"{len(registry.remix_names())} remixes, 0 problems")
        return 1 if bad else 0
    # lock
    args = argv[2:]
    if not args:
        print("store.py lock <module> [--retire KEY ...] [--retire-param KEY ...]")
        return 2
    m = registry.by_name(args[0])
    retire, retire_param, cur = [], [], None
    for a in args[1:]:
        if a in ("--retire", "--retire-param"):
            cur = retire if a == "--retire" else retire_param
        elif cur is not None:
            cur.append(int(a))
        else:
            print(f"unexpected argument {a!r}")
            return 2
    if not needs_lock(m):
        print(f"{m.name}: no store and no keyed param, so no lock")
        return 1
    bad = write_lock(m, retire, retire_param)
    print("\n".join(f"{m.name}: {b}" for b in bad) if bad else f"wrote {lock_path(m).relative_to(ROOT)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
