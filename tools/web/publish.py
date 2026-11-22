#!/usr/bin/env python3
"""Build the web builder's patches from this tree and your own 1.40C.

    make webpatch BUILD=N [OUT=out/web]
    python3 tools/web/publish.py --build N --tree PATH      # build in another checkout, publish into this one

For each published remix (`tools/site/release.py`), and each community remix
(remixes/community/<name>/) that passes `make check REMIX=<name>` first, it runs `make image`, turns
`out/mainos_bus.bin` into an OBP1 patch against the stock MAIN OS
(`tools/web/obpatch.py` applies and leak-checks it), and writes

    <out>/patches/<remix>.obp
    <out>/manifest.json          release version, commit, date, and per remix: version, image name, patch,
                                 and `community` for a community remix

CI's runs leave the community remixes out (tools/verify/reach.py), so this
run checks each one before it builds a patch; a community remix that does not
pass, or does not build, is left out of the builder, named, and the run goes on.
`--no-community` skips them.
    <out>/ref/<remix>/           the files `make image` wrote, for tools/web/test_chain.mjs

`ref/` holds Elektron's OS and stays in <out> (out/ is not tracked).
`patches/` and `manifest.json` are copied to docs/site/builder/, which the
site serves; commit them in a PR of their own. The tree must be clean and at
the release tag (release.VERSION), so a published patch names a commit anyone
can check out; `--dev` builds into <out> only. `--tree` names that checkout (a
worktree at the tag); the patches and the manifest are published into the tree the
script is in, which is how a release is published from a branch that is ahead of it.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/web"))
sys.path.insert(0, str(ROOT / "tools/site"))
import obpatch  # noqa: E402
import release  # noqa: E402

SITE = ROOT / "docs/site/builder"
TREE = ROOT        # the checkout the images are built in; --tree changes it


def git(*a):
    return subprocess.run(["git", *a], cwd=TREE, capture_output=True, text=True, check=True).stdout.strip()


def remixes():
    return [r for r in release.REMIXES if (TREE / "remixes" / r / "remix.py").exists()]


def community():
    """The community remixes of the tree, by name."""
    return sorted(p.parent.name for p in (TREE / "remixes" / "community").glob("*/remix.py"))


def make_quiet(*args):
    """Run make in TREE with its output in a log under out/web; True when it passes."""
    log = TREE / "out" / "web" / ("-".join(a.replace("=", "_") for a in args) + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as f:
        ok = subprocess.run(["make", *args], cwd=TREE, stdout=f, stderr=subprocess.STDOUT).returncode == 0
    if not ok:
        print(f"   make {' '.join(args)} failed: {log}")
    return ok


def image_name(remix, build):
    """The Makefile's IMAGE_NAME (tools/remix/brain.py image_name)."""
    sys.path.insert(0, str(TREE / "tools"))
    from remix import brain
    return brain.image_name(remix, build)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", required=True, help="the BUILD tag stamped into the images (make image BUILD=; A0 is image 100)")
    ap.add_argument("--out", default="out/web")
    ap.add_argument("--tree", help="build in this checkout (default: the one this script is in)")
    ap.add_argument("--dev", action="store_true", help="allow a tree that is not clean at origin/main (manifest says so)")
    ap.add_argument("--no-community", action="store_true", help="build the release's remixes only")
    args = ap.parse_args()
    global TREE
    if args.tree:
        TREE = pathlib.Path(args.tree).resolve()

    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    tagged = subprocess.run(["git", "rev-list", "-n", "1", release.VERSION], cwd=TREE, capture_output=True, text=True)
    behind = tagged.returncode != 0 or tagged.stdout.strip() != commit
    if (dirty or behind) and not args.dev:
        sys.exit(f"webpatch: the tree must be clean and at the {release.VERSION} tag (git checkout --detach {release.VERSION}); "
                 "--dev builds a throwaway set")
    stock_path = TREE / "out/raw/section_3_MAIN_OS.bin"
    if not stock_path.exists():
        sys.exit(f"webpatch: {stock_path} missing -- make os && make recon")

    out = (ROOT / args.out)
    (out / "patches").mkdir(parents=True, exist_ok=True)
    version = f"OCTABAM{args.build}"
    stock = stock_path.read_bytes()
    rows, refused = [], []
    jobs = [(r, False) for r in remixes()] + ([] if args.no_community else [(r, True) for r in community()])
    for remix, contrib in jobs:
        print(f"== {remix}{' (community)' if contrib else ''}", flush=True)
        if contrib:
            # CI does not check a community remix; its patch is built only when its gates pass here
            if not (make_quiet("check", f"REMIX={remix}")
                    and make_quiet("image", f"REMIX={remix}", f"BUILD={args.build}")):
                refused.append(remix)
                continue
        else:
            subprocess.run(["make", "image", f"REMIX={remix}", f"BUILD={args.build}"], cwd=TREE, check=True)
        name = image_name(remix, args.build)
        ref = out / "ref" / remix
        ref.mkdir(parents=True, exist_ok=True)
        for src, dst in ((f"out/OCTATRACK_{version}.bin", "card.bin"),
                         (f"out/OCTATRACK_OS1.40C_{version}.syx", "midi.syx"),
                         (f"out/{name}.RMX", "image.rmx"),
                         ("out/mainos_bus.bin", "mainos_bus.bin")):
            shutil.copyfile(TREE / src, ref / dst)
        patch = obpatch.make(stock, (ref / "mainos_bus.bin").read_bytes())
        (out / "patches" / f"{remix}.obp").write_bytes(patch)
        row = {"name": remix, "title": remix, "version": version, "imageName": name,
               "patch": f"patches/{remix}.obp", "patchBytes": len(patch),
               "sha256": hashlib.sha256(patch).hexdigest()}
        if contrib:
            row["community"] = True
        rows.append(row)
        print(f"   patch {len(patch):,} bytes")
    if refused:
        print(f"left out of the builder (make check or make image failed): {', '.join(refused)}")

    manifest = {"version": release.VERSION, "commit": commit, "dev": dirty or behind, "build": args.build,
                "date": datetime.date.today().isoformat(), "remixes": rows}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"wrote {args.out}/manifest.json for {commit[:8]}")
    if manifest["dev"]:
        return
    shutil.rmtree(SITE / "patches", ignore_errors=True)
    shutil.copytree(out / "patches", SITE / "patches")
    shutil.copyfile(out / "manifest.json", SITE / "manifest.json")
    print(f"copied patches and manifest to {SITE.relative_to(ROOT)}/ -- commit them in a PR")


if __name__ == "__main__":
    main()
