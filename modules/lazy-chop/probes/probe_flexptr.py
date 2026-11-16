#!/usr/bin/env python3
"""What in RAM points at FLEX slot 1's audio (0x414975e0, pool offset 0xa02000, block 1708)."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "flexptr"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("flexptr", card, "OCTABAM", "LC")
pats = {"addr": (0x414975E0).to_bytes(4, "big"), "off": (0xA02000).to_bytes(4, "big"), "blk32": (1708).to_bytes(4, "big"),
        "addr_u": (0x414975E0 | 0).to_bytes(4, "big")}
regions = [(0x40000400, 0x40A955E0 - 0x40000400), (0x46000000, 0x00D00000), (0x10000000, 0x00110000), (0x80000000, 0x00010000)]
with r.p as p:
    p.settle(); p.run(500)
    for base, n in regions:
        try:
            m = p.peek(base, n)
        except Exception as e:
            print("skip", hex(base), e); continue
        for name, pat in pats.items():
            i = m.find(pat); k = 0
            while i >= 0 and k < 8:
                if i % 2 == 0: print(f"{name} at {base + i:#x}")
                i = m.find(pat, i + 1); k += 1
    # halfword 1708 in the block array rows 0..1
    arr = p.peek(0x46C2E9C0, 2 * 14602 * 2)
    hw = [int.from_bytes(arr[j:j + 2], "big") for j in range(0, len(arr), 2)]
    print("row0/1 entries == 1708:", [j for j, v in enumerate(hw) if v == 1708][:10], " row1 head:", hw[14602:14602 + 12])
