#!/usr/bin/env python3
"""Which published web-builder patches are older than the code on HEAD.

    python3 tools/web/stale.py [--manifest docs/site/builder/manifest.json]
                               [--head HEAD] [--strict] [--check]

Reads the commit the manifest was built from, lists the paths changed since,
and prints for each official remix the paths that can move its image. No
firmware is needed. A path is placed by prefix, so the answer errs towards
stale: a manifest-only edit to a module still lists that module's remixes.

  docs/, *.md, .github/, tools/{verify,harness,emu,site,web,...}   ignored
  modules/<name>/        the official remixes selecting that module
  remixes/<official>/    that remix
  anything else          every official remix (the build, the DSP sources,
                         the Makefile, the vendored patches)

`--check` verifies the committed manifest against the files, with no firmware:
every patch exists, matches its recorded sha256, parses as OBP1, and all
patches name the same stock MAIN OS. It exits 1 on any mismatch.

A manifest that names a `version` is locked to that release (tools/site/release.py): the
paths changed since are listed and nothing warns. `--strict` exits 1 when any remix is stale. Under GitHub Actions each stale
remix is also printed as a ::warning::.
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

IGNORED_PREFIXES = (
    "docs/", ".github/", "CHANGELOG.md", "tools/verify/", "tools/harness/",
    "tools/emu/", "tools/site/", "tools/web/", "tools/ghidra/", "tools/hw/",
    "tools/panel/", "tools/rec/", "tools/tone/", "tools/scratch/", "downloads/",
)


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def changed_since(commit, head):
    return [p for p in git("diff", "--name-only", f"{commit}", head).splitlines() if p]


def ignored(path):
    return path.endswith(".md") or path.startswith(IGNORED_PREFIXES)


def registry_names():
    from remix import registry
    return registry.remix_names()


def selections(names):
    """{official remix: {module directory name}} from the registry."""
    from remix import registry
    have = set(registry.remix_names())
    return {n: ({m.name for m in registry.selected(registry.remix(n))} if n in have else set()) for n in names}


def stale(paths, sel):
    out = {n: [] for n in sel}
    for p in paths:
        if ignored(p):
            continue
        parts = p.split("/")
        if parts[0] == "modules" and len(parts) > 2:
            hit = [n for n, mods in sel.items() if parts[1] in mods]
        elif parts[0] == "remixes" and len(parts) > 2:
            hit = [n for n in sel if parts[1] == n]
        else:
            hit = list(sel)
        for n in hit:
            out[n].append(p)
    return out


def check(manifest, site):
    sys.path.insert(0, str(ROOT / "tools/web"))
    import obpatch
    bad, stock_shas = [], set()
    for r in manifest["remixes"]:
        f = site / r["patch"]
        if not f.exists():
            bad.append(f"{r['name']}: {r['patch']} missing")
            continue
        data = f.read_bytes()
        if hashlib.sha256(data).hexdigest() != r["sha256"]:
            bad.append(f"{r['name']}: {r['patch']} does not match its recorded sha256")
        try:
            stock_shas.add(obpatch.header(data)[0])
        except Exception as e:
            bad.append(f"{r['name']}: {r['patch']} is not an OBP1 patch ({e})")
    if len(stock_shas) > 1:
        bad.append("patches name different stock MAIN OS hashes")
    for b in bad:
        print("check:", b)
    return not bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="docs/site/builder/manifest.json")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    mpath = ROOT / args.manifest
    m = json.loads(mpath.read_text())
    if args.check:
        ok = check(m, mpath.parent)
        print("manifest ok" if ok else "manifest NOT ok")
        sys.exit(0 if ok else 1)
    names = [r["name"] for r in m["remixes"]]
    res = stale(changed_since(m["commit"], args.head), selections(names))
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    any_stale = False
    for n in names:
        paths = res[n]
        if n not in set(registry_names()):
            print(f"{n}: RETIRED (no remixes/{n}); the published patch stays until it is republished")
            continue
        if m.get("version"):
            # a patch locked to a release: later changes are expected, so nothing warns
            print(f"{n}: locked to {m['version']} (built from {m['commit'][:8]}); {len(paths)} path(s) changed since")
            continue
        if not paths:
            print(f"{n}: current (built from {m['commit'][:8]})")
            continue
        any_stale = True
        shown = ", ".join(paths[:5]) + (f" and {len(paths) - 5} more" if len(paths) > 5 else "")
        print(f"{n}: STALE, {len(paths)} path(s) changed since {m['commit'][:8]}: {shown}")
        if gha:
            print(f"::warning title=web builder patch stale::{n}: {len(paths)} path(s) changed since {m['commit'][:8]}")
    sys.exit(1 if (args.strict and any_stale) else 0)


if __name__ == "__main__":
    main()
