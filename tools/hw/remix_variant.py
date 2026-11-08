#!/usr/bin/env python3
"""A remix minus some modules, for a control or bisect image on a unit: written as a flat remix file
`remixes/_hw-<NAME>.py` (gitignored), so `make image REMIX=_hw-<NAME> BUILD=<n>` builds it.

    .venv/bin/python3 tools/hw/remix_variant.py octabam-verbs vrb-ncf --without SCREEN "CHORDS FACTORY" PAGES
    .venv/bin/python3 tools/hw/remix_variant.py octabam-verbs pr1066 --pr1067      # the remix as main had it before #1067
    .venv/bin/python3 tools/hw/remix_variant.py --list                             # the variants in this tree
    .venv/bin/python3 tools/hw/remix_variant.py --clean                            # remove them

`--pr1067` takes out what #1067 added to that remix (docs/contributing/HARDWARE_PLAN.md, "Images"): the control
image for the loader soak. A module named in --without leaves the remix's FX1 list too. The build still refuses what
it refuses for any remix (a module another one requires: CHORDS FACTORY requires PAGES, so take both out together).
"""
import argparse, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

# What #1067 added, per remix (CHANGELOG "New modules in the octabam remixes").
CF_1067 = ("CHORDS FACTORY", "PAGES", "SCREEN", "SLOW LFO", "BAR LED", "REC CS1 SKIP")
PR1067 = {
    "octabam": CF_1067,
    "octabam-bus": CF_1067 + ("SCALES", "VARISPEED"),
    "octabam-verbs": CF_1067 + ("SCALES", "VIBRATO", "TRANSIENT", "RESONATOR"),
}

TEMPLATE = '''"""{doc}"""
# Written by tools/hw/remix_variant.py; gitignored (/remixes/_hw-*.py). Not a remix to ship.
import dataclasses
from remix import registry

_BASE = registry.remix({base!r})
_OUT = {out!r}
REMIX = dataclasses.replace(
    _BASE, name={name!r}, doc={doc!r},
    modules=tuple(k for k in _BASE.modules if k not in _OUT),
    fx1=tuple(k for k in (_BASE.fx1 or ()) if k not in _OUT) or _BASE.fx1,
    hidden=tuple(k for k in (_BASE.hidden or ()) if k not in _OUT),
    locked=tuple(k for k in (_BASE.locked or ()) if k not in _OUT),
    settings={{k: v for k, v in _BASE.settings.items()
              if not any(k[0] == "octabam." + m.lower().replace(" ", "-") for m in _OUT)}})
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", nargs="?"); ap.add_argument("name", nargs="?")
    ap.add_argument("--without", nargs="+", default=[], metavar="MODULE")
    ap.add_argument("--pr1067", action="store_true", help="take out what #1067 added to BASE")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--clean", action="store_true")
    a = ap.parse_args()
    files = sorted((ROOT / "remixes").glob("_hw-*.py"))
    if a.list:
        for f in files:
            print(f.stem, "--", (re.search(r'"""(.*?)"""', f.read_text(), re.S) or [None, ""])[1])
        return 0
    if a.clean:
        for f in files:
            f.unlink(); print("removed", f.relative_to(ROOT))
        return 0
    if not (a.base and a.name):
        ap.error("BASE and NAME, or --list / --clean")
    from remix import registry
    base = registry.remix(a.base)
    out = list(a.without) + (list(PR1067.get(a.base, ())) if a.pr1067 else [])
    if a.pr1067 and a.base not in PR1067:
        sys.exit(f"--pr1067 knows {', '.join(PR1067)}, not {a.base}")
    missing = [m for m in out if m not in base.modules]
    if missing:
        sys.exit(f"{a.base} does not carry {', '.join(missing)}")
    name = f"_hw-{a.name}"
    # the image calls itself `<NAME> <BUILD>` in at most 15 characters (tools/remix/brain.py image_name): with
    # `_hw-` and a three-digit BUILD that leaves NAME 7
    if not re.fullmatch(r"_hw-[a-z0-9-]{1,7}", name):
        sys.exit("NAME: lower-case letters, digits and '-', up to 7 (the image name is 15 characters with BUILD)")
    doc = f"{a.base} without {', '.join(out)} (a control/bisect image for the unit)"
    path = ROOT / "remixes" / f"{name}.py"
    path.write_text(TEMPLATE.format(doc=doc, base=a.base, out=tuple(out), name=name))
    registry._cache = None if hasattr(registry, "_cache") else None
    r = registry.remix(name)
    print(f"wrote {path.relative_to(ROOT)}: {len(r.modules)} modules ({len(base.modules)} in {a.base})")
    print(f"build:  make image REMIX={name} BUILD=<n>     (or make rmx REMIX={name} BUILD=<n> for REMIX SWITCH)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
