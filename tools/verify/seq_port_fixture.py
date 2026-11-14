"""A firmware-generated project for SEQ's image-stage panel gates."""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def stage_project(image: pathlib.Path, card: pathlib.Path, tree: pathlib.Path):
    from remix import registry

    # Image-stage gates consume the preceding build. Refuse another remix's
    # image or an untracked replacement rather than testing stale out/ bytes.
    sidecar = image.with_suffix(".remix")
    fields = sidecar.read_text().split() if sidecar.exists() else []
    if len(fields) != 2 or fields[1] != hashlib.sha256(image.read_bytes()).hexdigest():
        raise SystemExit("SEQ: rebuild the selected remix; image provenance is missing or stale")
    selected = registry.remix(sys.argv[1] if len(sys.argv) > 1 else fields[0])
    if fields[0] != selected.name or "SEQ" not in selected.modules:
        raise SystemExit(f"SEQ: image is for {fields[0]}, expected {selected.name} with SEQ")

    # CI's image jobs have no template_project or OT_PROJECT. Let this image
    # make its own empty project; ot_fresh caches by image, port and script.
    fresh = ROOT / "out/seq-fixture"
    subprocess.run(
        [sys.executable, str(ROOT / "tools/hw/ot_fresh.py"),
         "--image", str(image), "--out", str(fresh)], cwd=ROOT, check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"),
         str(fresh / "image/NOPROJ"), "OCTABAM", "A",
         "--tree", str(tree), "--out", str(card)], cwd=ROOT, check=True,
    )
    return selected
