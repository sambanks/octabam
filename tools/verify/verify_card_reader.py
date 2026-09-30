#!/usr/bin/env python3
"""The card reader returns what the builder wrote, byte for byte.

    python3 tools/verify/verify_card_reader.py

`emu_card.extract_image` is how every STEM REC port run gets its WAV back,
so it is held to the builder that made the image: files of awkward sizes (0,
1, one cluster, one cluster + 1, many clusters), a long name and nested
folders, built, read back and compared. It also pins what the reader cannot
show: a folder with no file in it does not appear (it lists files), so a
take that made its folder and wrote nothing reads as no take at all. And it
pins the FAT16 image itself, by hash, so a change to the builder that moves
one byte of it is seen.
"""
import hashlib
import pathlib
import struct
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import emu_card as ec  # noqa: E402


def _bytes(n):
    """n bytes of a fixed pattern, so the image, and its hash, repeat."""
    return bytes(range(256)) * (n // 256) + bytes(range(n % 256))


FILES = {
    "PRESETS/PROJ/project.work": b"",
    "PRESETS/AUDIO/a.wav": b"\x01",
    "PRESETS/AUDIO/Long Name Recording.wav": _bytes(4096),
    "PRESETS/AUDIO/250910-1432/T1.wav": _bytes(4097),
    "big.bin": _bytes(300_000),
}
EMPTY = "PRESETS/AUDIO/250910-1433"
# A filler inside PRESETS that sorts first there, so the builder allocates it
# before the rest of PRESETS: 65,536 clusters of 512 bytes put everything
# after it above cluster 65,535, where a cluster number needs its high word.
# The unit's 64 GB card allocates up there; a 64 MB image never does. Inside
# PRESETS, not at the root, so PRESETS's own cluster is guessed below 65,536
# and allocated above it: the case where a '.' entry's high word goes stale.
FILLER = "PRESETS/A_FILLER.bin"
FILLER_BYTES = 65536 * 512
# The 16 MB image of build_tree(), from upstream's builder (27 Sep 2026, 68af650).
FAT16_SHA = "5c36bdd8bebdeaa519f2358f9e359f9144ced5d8ce161a1783d68da88919a853"


def build_tree(root):
    for rel, data in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    (root / EMPTY).mkdir(parents=True)


def main():
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    with tempfile.TemporaryDirectory() as t:
        tree = pathlib.Path(t) / "tree"
        build_tree(tree)
        img16 = ec.build_image(str(tree), 16)
        got = ec.extract_image(img16)
        for rel, data in FILES.items():
            check(f"/{rel} ({len(data):,} B)", got.get(rel) == data,
                  "" if rel in got else "missing")
        check("nothing read back that was not written", set(got) == set(FILES),
              f"{sorted(set(got) - set(FILES))}")
        check(f"an empty folder ({EMPTY}) does not appear",
              not any(p.startswith(EMPTY) for p in got))
        sha = hashlib.sha256(img16).hexdigest()
        check("FAT16: the image is what upstream's builder made", sha == FAT16_SHA, sha)
        img32 = ec.build_image(str(tree), 64, fat=32)
        check("FAT32: the partition type is 0x0c", img32[446 + 4] == 0x0C, f"0x{img32[446 + 4]:02x}")
        part = struct.unpack_from("<I", img32, 446 + 8)[0] * 512
        check("FAT32: the BPB says FAT32", img32[part + 82:part + 90] == b"FAT32   ",
              repr(img32[part + 82:part + 90]))
        got32 = ec.extract_image(img32)
        for rel, data in FILES.items():
            check(f"FAT32: /{rel} ({len(data):,} B)", got32.get(rel) == data,
                  "" if rel in got32 else "missing")
        check("FAT32: nothing read back that was not written", set(got32) == set(FILES),
              f"{sorted(set(got32) - set(FILES))}")
        tree_hi = pathlib.Path(t) / "tree_hi"
        build_tree(tree_hi)
        (tree_hi / FILLER).write_bytes(bytes(FILLER_BYTES))
        clusters = {}
        got_hi = ec.extract_image(ec.build_image(str(tree_hi), 128, fat=32), clusters=clusters)
        check("FAT32 high: every file reads back",
              all(got_hi.get(r) == d for r, d in FILES.items())
              and len(got_hi.get(FILLER, b"")) == FILLER_BYTES)
        low = min(clusters[r] for r, d in FILES.items() if d and r.startswith("PRESETS/"))
        check("FAT32 high: the files in PRESETS start above cluster 65,535", low > 0xFFFF,
              f"lowest first cluster {low}")
        fs = ec._Fat32(128 * 2048 - 2048, 1, 2048)       # build_image(..., 128, fat=32)'s volume
        log = []
        fs.build_dir(str(tree_hi), 0, True, log)
        dirs = [(n, c) for n, _, c, _ in log if n.endswith("/")]
        bad = []
        for n, c in dirs:
            dot = fs.data[(c - 2) * fs.cluster_bytes:(c - 2) * fs.cluster_bytes + 32]
            got = struct.unpack_from("<H", dot, 26)[0] | (struct.unpack_from("<H", dot, 20)[0] << 16)
            if dot[:11] != b".          " or got != c:
                bad.append((n, c, got))
        check("FAT32 high: every folder's '.' entry names its own cluster",
              bool(dirs) and not bad and min(c for _, c in dirs) > 0xFFFF,
              f"{len(dirs)} folders, lowest {min((c for _, c in dirs), default=None)}, wrong {bad}")
        try:
            ec.build_image(str(tree), 16, fat=32)
            check("FAT32: a 16 MB image is refused (too few clusters)", False)
        except ValueError as e:
            check("FAT32: a 16 MB image is refused (too few clusters)", "not FAT32" in str(e), str(e))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
