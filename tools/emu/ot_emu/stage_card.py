#!/usr/bin/env python3
"""Build the card image the C++ port reads, with ROUTE A'S OWN STAGING.

    .venv/bin/python3 tools/emu/ot_emu/stage_card.py out/_testproj OCTABAM RIG \
        --tree out/_o6_tree_port --out out/o6_card.img

⚠️ THE POINT IS THAT BOTH EMULATORS LOOK AT IDENTICAL MEDIA. `emu_rtos.
stage_project` is the function route A calls, so the tree it copies and the
FAT16 image it builds are the same bytes either way -- the FAT16 builder is
deliberately NOT ported to C++ for exactly this reason (COLDFIRE_PORT.md O7).
Building the image any other way (`emu_card.py --image-only` has its own skip
list) would make a difference between the two emulators that is the harness's
and not the firmware's, which is the class of defect standing rule 7 exists
for.
"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import emu_rtos  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("set_name", nargs="?", default="OCTABAM")
    ap.add_argument("name", nargs="?", default=None)
    ap.add_argument("--tree", default="out/_o6_tree_port",
                    help="scratch dir the card is staged in; it is WIPED at start, so a "
                         "run concurrent with route A's needs its own")
    ap.add_argument("--image-mb", type=int, default=64)
    ap.add_argument("--out", default="out/o6_card.img")
    ap.add_argument("--audio", action="append", default=[],
                    help="'<src wav>:<card path relative to the SET folder>' -- a sample to put on "
                         "the card as well (route A stages none by default, which is why every "
                         "sample slot is empty and the DSP has nothing to play: O9); repeatable")
    a = ap.parse_args()
    img, staged = emu_rtos.stage_project(a.project, a.set_name, a.name,
                                         tree=a.tree, image_mb=a.image_mb, audio=a.audio)
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(img)
    print(f"{a.out}: {len(img)} bytes, SET {a.set_name} PROJECT {staged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
