#!/usr/bin/env python3
"""The FAT16 reader returns what the builder wrote, byte for byte.

    python3 tools/verify/verify_card_reader.py

The reader is how every STEM REC port run gets its WAV back, so it is held
to the builder that made the image: a tree of files of awkward sizes (0, 1,
one cluster, one cluster + 1, many clusters), a long name and a nested
folder, built, read back and compared.
"""
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import emu_card as ec  # noqa: E402


def main():
    fails = 0
    with tempfile.TemporaryDirectory() as t:
        tree = pathlib.Path(t) / "tree"
        files = {
            "PRESETS/PROJ/project.work": b"",
            "PRESETS/AUDIO/a.wav": b"\x01",
            "PRESETS/AUDIO/Long Name Recording.wav": os.urandom(4096),
            "PRESETS/AUDIO/250910-1432/T1.wav": os.urandom(4097),
            "big.bin": os.urandom(300_000),
        }
        for rel, data in files.items():
            p = tree / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        img = pathlib.Path(t) / "card.img"
        img.write_bytes(ec.build_image(str(tree), 16))
        for rel, data in files.items():
            got = ec.read_file(img.read_bytes(), "/" + rel)
            ok = got == data
            fails += 0 if ok else 1
            print(f"  [{'PASS' if ok else 'FAIL'}] /{rel} ({len(data):,} B)")
        missing = ec.read_file(img.read_bytes(), "/PRESETS/AUDIO/none.wav")
        ok = missing is None
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] a missing file reads as None")
        names = sorted(ec.list_dir(img.read_bytes(), "/PRESETS/AUDIO") or [])
        want = sorted(["a.wav", "Long Name Recording.wav", "250910-1432"])
        ok = [n.lower() for n in names] == [n.lower() for n in want]
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] list_dir /PRESETS/AUDIO  {names}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
