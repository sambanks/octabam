#!/usr/bin/env python3
"""Build the card image the C++ port reads (emu_card.stage_project).

    .venv/bin/python3 tools/emu/ot_emu/stage_card.py out/_testproj OCTABAM RIG \
        --tree out/_stage_card_tree --out out/card.img"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import emu_card  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("set_name", nargs="?", default="OCTABAM")
    ap.add_argument("name", nargs="?", default=None)
    ap.add_argument("--tree", default="out/_stage_card_tree",
                    help="scratch dir the card is staged in; it is WIPED at start, so "
                         "concurrent runs need one each")
    ap.add_argument("--image-mb", type=int, default=64)
    ap.add_argument("--out", default="out/card.img")
    ap.add_argument("--audio", action="append", default=[],
                    help="'<src wav>:<card path relative to the SET folder>' -- a sample to put on "
                         "the card as well (none are staged by default, so every sample slot is "
                         "empty and the DSP has nothing to play: O9); repeatable")
    ap.add_argument("--root-file", action="append", default=[],
                    help="'<src>:<card path relative to the card root>' -- a file outside the set "
                         "(the settings store's BRAIN/card.work); repeatable")
    a = ap.parse_args()
    img, staged = emu_card.stage_project(a.project, a.set_name, a.name,
                                         tree=a.tree, image_mb=a.image_mb, audio=a.audio,
                                         root_files=a.root_file)
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(img)
    print(f"{a.out}: {len(img)} bytes, SET {a.set_name} PROJECT {staged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
