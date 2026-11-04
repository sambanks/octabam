#!/usr/bin/env python3
"""Build the web builder's patches from this tree and your own 1.40C.

    make webpatch BUILD=N [OUT=out/web]
    python3 tools/web/publish.py --build N --tree PATH      # build in another checkout, publish into this one

For each published remix (`tools/site/release.py`) it runs `make image`, turns
`out/mainos_bus.bin` into an OBP1 patch against the stock MAIN OS
(`tools/web/obpatch.py` applies and leak-checks it), and writes

    <out>/patches/<remix>.obp
    <out>/manifest.json          release version, commit, date, and per remix: version, image name, patch
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


def image_name(remix, build):
    """The Makefile's IMAGE_NAME: upper-case, 15 characters, trailing spaces cut."""
    return f"{remix} {build}".upper()[:15].rstrip(" ")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", required=True, help="the BUILD tag stamped into the images (make image BUILD=; A0 is image 100)")
    ap.add_argument("--out", default="out/web")
    ap.add_argument("--tree", help="build in this checkout (default: the one this script is in)")
    ap.add_argument("--dev", action="store_true", help="allow a tree that is not clean at origin/main (manifest says so)")
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
    rows = []
    for remix in remixes():
        print(f"== {remix}", flush=True)
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
        rows.append({"name": remix, "title": remix, "version": version, "imageName": name,
                     "patch": f"patches/{remix}.obp", "patchBytes": len(patch),
                     "sha256": hashlib.sha256(patch).hexdigest()})
        print(f"   patch {len(patch):,} bytes")

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
