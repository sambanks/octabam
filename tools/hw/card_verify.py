#!/usr/bin/env python3
"""Verify files on the Octatrack's card with UNCACHED reads.

    python3 tools/hw/card_verify.py stable [-n 6] FILE...          # is the transport clean?
    python3 tools/hw/card_verify.py compare LOCAL CARD [-n 2]      # a file or a tree, local vs card

`cmp` straight after a copy reads macOS's page cache, not the card: on 30 Sep
2026 it passed every corrupt copy made through USB disk mode on RIGPF3BP,
which returned about one read in four wrong (docs/contributing/FAILURE_MODES.md).
Every read here sets F_NOCACHE, so each one goes to the card.

stable   reads each file N times; a file whose hash changes between reads
         means the transport is corrupting -- stop, and do card work from
         stock (OS SWITCH -> STOCK140) instead
compare  hashes each local file and reads its card copy N times; a copy is
         good only when every read equals the local hash. A tree compares
         every file (macOS `._*` files skipped) and lists files only on the
         card
Exit status 1 on any unstable or mismatched file.
"""
import argparse
import fcntl
import hashlib
import os
import sys

F_NOCACHE = 48          # <sys/fcntl.h>, macOS


def digest(path, nocache=True):
    fd = os.open(path, os.O_RDONLY)
    try:
        if nocache:
            fcntl.fcntl(fd, F_NOCACHE, 1)
        h = hashlib.sha256()
        while True:
            b = os.read(fd, 1 << 20)
            if not b:
                break
            h.update(b)
        return h.hexdigest()
    finally:
        os.close(fd)


def stable(files, n):
    bad = 0
    for f in files:
        hs = [digest(f) for _ in range(n)]
        ok = len(set(hs)) == 1
        bad += 0 if ok else 1
        print(f"{'STABLE ' if ok else 'CHANGES'} {' '.join(h[:10] for h in hs)}  {f}")
    return bad


def compare(local, card, n):
    if os.path.isdir(local):
        names = sorted(x for x in os.listdir(local) if not x.startswith("._"))
        pairs = [(os.path.join(local, x), os.path.join(card, x)) for x in names]
        extra = sorted(x for x in os.listdir(card) if not x.startswith("._") and x not in names)
    else:
        pairs, extra = [(local, card)], []
    bad = 0
    for src, dst in pairs:
        if os.path.isdir(src):
            bad += compare(src, dst, n)
            continue
        want = digest(src, nocache=False)
        got = {digest(dst) for _ in range(n)} if os.path.isfile(dst) else {"missing"}
        ok = got == {want}
        bad += 0 if ok else 1
        if not ok:
            print(f"MISMATCH {dst}  ({'missing' if 'missing' in got else f'{len(got)} distinct read(s)'})")
    print(f"{card}: {len(pairs)} file(s), {bad} bad" + (f"; only on the card: {extra}" if extra else ""))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stable")
    s.add_argument("-n", type=int, default=6)
    s.add_argument("files", nargs="+")
    c = sub.add_parser("compare")
    c.add_argument("-n", type=int, default=2)
    c.add_argument("local")
    c.add_argument("card")
    a = ap.parse_args()
    bad = stable(a.files, a.n) if a.cmd == "stable" else compare(a.local, a.card, a.n)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
