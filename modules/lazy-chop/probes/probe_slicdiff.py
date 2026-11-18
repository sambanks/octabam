#!/usr/bin/env python3
"""The RAM address of T1's FLEX SLIC: the bank blob of the SLIC OFF card against the SLIC ON one."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
dumps = {}
for kind in ("sample", "slic"):
    w = V.OUT / "_probe" / f"slicdiff_{kind}"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
    card = w / "card.img"; shutil.copy(cards[kind], card)
    r = V.Run(f"slicdiff_{kind}", card, "OCTABAM", "LC")
    with r.p as p:
        p.settle()
        blob = p.long(0x46C82456)
        dumps[kind] = (blob, p.peek(blob + 0x8ED80, 4 * 0x18B2), p.peek(0x100A54D0, 0x8000), p.peek(0x80000800, 0x800))
b0, a, sa, la = dumps["sample"]; b1, b, sb, lb = dumps["slic"]
print("blob", hex(b0), hex(b1))
for name, x, y, base in (("bank parts", a, b, b0 + 0x8ED80), ("SRAM 0x100a54d0", sa, sb, 0x100A54D0), ("live 0x80000800", la, lb, 0x80000800)):
    d = [i for i in range(min(len(x), len(y))) if x[i] != y[i]]
    print(name, "differs at", [(hex(base + i), x[i], y[i]) for i in d[:12]], f"({len(d)} bytes)")
