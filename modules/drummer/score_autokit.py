#!/usr/bin/env python3
"""Score autokit.c on AUTO's references (autokit_refs.py): each named slice's zone, AUTO's against the user's.

    .venv/bin/python3 modules/drummer/score_autokit.py [--features] [--ref NAME]

Prints per reference the slices AUTO gets wrong and the score; --features adds every slice's features.
The samples stay on the user's disk; a reference not found is skipped (said so).
"""
import argparse, ctypes, pathlib, struct, sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import kitmaker as K  # noqa: E402
import verify_autokit as VA  # noqa: E402
from autokit_refs import REFS  # noqa: E402

NAMES = E.ZONES + ["COMBO"] + ["?"] * 5 + ["OUT"]


def load(ref):
    x = K.decode(ref["wav"])
    if ref["slices"] == "ot":
        ot = ref["wav"].with_suffix(".ot").read_bytes()
        n, = struct.unpack(">I", ot[0x33A:0x33E])
        sl = [struct.unpack(">II", ot[0x3A + 12 * i:0x42 + 12 * i]) for i in range(n)]
    else:
        sl = K.bounds(K.onsets_after_silence(x, -84.0, 50), len(x), from_zero=False)
    m = np.clip(np.round(x.mean(axis=1) * 32768), -32768, 32767).astype(np.int32)
    return m, sl


def score(name, ref, L, features):
    m, sl = load(ref)
    read = VA.READ(lambda ctx, frame: int(m[frame]) if frame < len(m) else 0)
    feats = (VA.Features * 64)()
    for i, (s, e) in enumerate(sl):
        L.ak_features(read, None, s, e, ctypes.byref(feats[i]))
    kit, align, link = E.Kit(), (ctypes.c_uint8 * 64)(), (ctypes.c_uint8 * 64)()
    L.dr_kit_init(ctypes.byref(kit), len(sl))
    L.ak_kit(feats, len(sl), ctypes.byref(kit), align, 0, 0, link)
    want = ref["zones"]
    if features:
        cols = [c for c, _ in VA.Features._fields_ if c not in ("band", "env")]
        print("  sl  want   auto   " + " ".join(f"{c[:7]:>7s}" for c in cols))
        for i in range(len(sl)):
            f = feats[i]
            print(f"  {i + 1:2d}  {want.get(i + 1, '-'):6s} {NAMES[kit.zone[i]]:6s} "
                  + " ".join(f"{getattr(f, c):7d}" for c in cols))
    bad = [(i, want[i], NAMES[kit.zone[i - 1]]) for i in sorted(want) if NAMES[kit.zone[i - 1]] != want[i]]
    ok = len(want) - len(bad)
    print(f"{name}: {ok}/{len(want)}" + ("" if not bad else "  wrong: " + ", ".join(f"{i} {w}->{g}" for i, w, g in bad)))
    return ok, len(want)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--features", action="store_true")
    ap.add_argument("--ref", action="append", choices=sorted(REFS))
    a = ap.parse_args()
    L = VA.lib()
    tot = [0, 0]
    for name in a.ref or REFS:
        ref = REFS[name]
        if not ref["wav"].is_file():
            print(f"{name}: [SKIP] {ref['wav']} not here")
            continue
        ok, n = score(name, ref, L, a.features)
        tot[0] += ok
        tot[1] += n
    print(f"total {tot[0]}/{tot[1]}")


if __name__ == "__main__":
    sys.exit(main())
