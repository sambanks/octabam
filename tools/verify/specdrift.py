"""The specs against the manifests they describe (docs/specs/).

STORE.md: the events table names exactly the manifest's EVENTS (plus `ctl`), the clients table matches CLIENTS (key,
prefix, events), and the register ABI table names the `store_part_*` entries the sources define.
EVENTS.md: the family/event table is FAMILIES. HOOKS.md: the bridge table is BRIDGES.
A name added to a manifest and not to its spec, or the other way round, fails.
Called by verify_docs.py; `python3 tools/verify/specdrift.py` runs it alone.
"""
import pathlib, re, runpy, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _manifest(mod):
    return runpy.run_path(str(ROOT / "modules" / mod / "manifest.py"))


def _section(text, heading):
    """The lines of `## heading` (or `### heading`) up to the next heading of the same or higher level."""
    lines = text.split("\n")
    for i, l in enumerate(lines):
        m = re.match(r"^(#{2,4}) " + re.escape(heading) + r"\s*$", l)
        if m:
            lvl = len(m.group(1))
            out = []
            for l2 in lines[i + 1:]:
                m2 = re.match(r"^(#{1,6}) ", l2)
                if m2 and len(m2.group(1)) <= lvl:
                    break
                out.append(l2)
            return out
    return None


def _rows(lines):
    """Table rows (cells stripped) of the first table in `lines`, header and rule skipped."""
    rows = []
    for l in lines:
        if l.startswith("|"):
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            rows.append(cells)
        elif rows:
            break
    return rows[1:]


def _expand(token):
    """`loadall_pre / post` and `loadall_pre/post` -> loadall_pre, loadall_post; a plain name -> itself."""
    out = []
    for part in re.split(r"\s*,\s*", token):
        names = [n.strip().strip("`") for n in re.split(r"\s*/\s*", part)]
        base = names[0]
        out.append(base)
        stem = base.rsplit("_", 1)[0]
        out += [stem + "_" + n if "_" not in n else n for n in names[1:]]
    return out


def check():
    fails = []
    spec = ROOT / "docs/specs"

    # STORE
    st = _manifest("store")
    text = (spec / "STORE.md").read_text()
    sec = _section(text, "Events")
    have = set()
    for cells in _rows(sec or []):
        if "not an event" in cells[0]:
            continue
        have.update(_expand(cells[0].replace("`", "")))
    for e in sorted(set(st["EVENTS"]) - have):
        fails.append(f"docs/specs/STORE.md: event {e} is in modules/store/manifest.py EVENTS and not in the events table")
    for e in sorted(have - set(st["EVENTS"])):
        fails.append(f"docs/specs/STORE.md: the events table names {e}, which EVENTS does not have")
    sec = _section(text, "Clients")
    want = {(k, p): set(ev) for k, p, ev in st["CLIENTS"]}
    got = {}
    for cells in _rows(sec or []):
        m = re.match(r"(.+?) \(`(\w+)`\)$", cells[0])
        if not m:
            fails.append(f"docs/specs/STORE.md: clients table row {cells[0]!r} is not `NAME (`prefix`)`")
            continue
        evs = set()
        for part in re.split(r",\s*", cells[1]):
            evs.update(_expand(part.strip()))
        got[(m.group(1), m.group(2))] = evs
    for k in sorted(set(want) - set(got)):
        fails.append(f"docs/specs/STORE.md: client {k[0]} ({k[1]}) is in CLIENTS and not in the clients table")
    for k in sorted(set(got) - set(want)):
        fails.append(f"docs/specs/STORE.md: the clients table has {k[0]} ({k[1]}), which CLIENTS does not")
    for k in sorted(set(want) & set(got)):
        if want[k] != got[k]:
            fails.append(f"docs/specs/STORE.md: {k[0]} handles {sorted(want[k] ^ got[k])} differently from CLIENTS")
    abi = set(re.findall(r"`(store_part_\w+)`", "\n".join(_section(text, "Register ABI") or [])))
    src = "".join(p.read_text() for p in (ROOT / "modules/store").glob("*.s"))
    for n in sorted(abi):
        if not re.search(r"^\s*(?:\.globl\s+|\.global\s+)?" + n + r":?", src, re.M):
            fails.append(f"docs/specs/STORE.md: register ABI entry {n} is not in modules/store/*.s")

    # EVENTS
    ev = _manifest("events")
    sec = _section((spec / "EVENTS.md").read_text(), "Register by contract")
    tbl = [l for l in (sec or []) if l.startswith("|")]
    have = {c[0].strip("`") for c in _rows(tbl)}
    want = {f"{fam}.{e}" for fam, evs in ev["FAMILIES"].items() for e in evs}
    for n in sorted(want - have):
        fails.append(f"docs/specs/EVENTS.md: {n} is in modules/events/manifest.py FAMILIES and not in the contract table")
    for n in sorted(have - want):
        fails.append(f"docs/specs/EVENTS.md: the contract table names {n}, which FAMILIES does not have")

    # HOOKS
    hk = _manifest("hooks")
    have = {c[0] for c in _rows(_section((spec / "HOOKS.md").read_text(), "Bridges") or [])}
    for n in sorted(set(hk["BRIDGES"]) - have):
        fails.append(f"docs/specs/HOOKS.md: bridge {n} is in modules/hooks/manifest.py BRIDGES and not in the bridge table")
    for n in sorted(have - set(hk["BRIDGES"])):
        fails.append(f"docs/specs/HOOKS.md: the bridge table names {n}, which BRIDGES does not have")
    return fails


if __name__ == "__main__":
    f = check()
    for x in f:
        print("  [FAIL]", x)
    print(f"specdrift: {len(f)} problem{'s' if len(f) != 1 else ''}")
    sys.exit(1 if f else 0)
