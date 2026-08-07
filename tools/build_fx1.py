#!/usr/bin/env python3
"""
EXPERIMENT: offer DELAY and the three reverbs on the FX1 slot.

Stock firmware restricts FX1 to 10 effects; FX2 gets those plus DELAY, PLATE REV,
SPRING REV and DARK REV. The descriptors and the DSP algorithms for all four
already exist and are already used by FX2 — the only thing keeping them off FX1 is
which entries the two FX1 tables contain.

This is a de-risking experiment (in the spirit of tools/build_exp.py), built
STANDALONE from the stock image so exactly one thing changes. It answers: are the
FX1/FX2 slots symmetric on the DSP side, or does the slot restriction reflect a
real resource difference (delay-line memory, DSP cycles)?

  data only, no new code, no PERSONALIZE gate  -- it adds menu entries and changes
  nothing until you actually select one of the new effects.

Two tables need to agree (found by RE, see PARAM_PAGES.md):

  1. id-indexed lookup  0x400d5f58[id]  -> descriptor   (32 slots, gaps = NONE)
     Resolves a STORED effect id to its parameter page. Patched in place: the four
     ids we want are NONE today.

  2. chooser list       0x400d6060      -> descriptor   (NUL-terminated, UI order)
     What the encoder scrolls through. This one CANNOT grow in place: it ends at
     0x400d608c and the FX2 list starts at 0x400d6090. So it is rebuilt in the code
     cave and its three `lea` references are repointed.

    python3 tools/build_fx1.py        # -> out/mainos_fx1.bin
"""
import pathlib, sys

BASE = 0x40000400
STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
OUT = pathlib.Path("out/mainos_fx1.bin")

NONE = 0x400d4618            # the NONE descriptor every unused id points at
FX1_IDS = 0x400d5f58         # id-indexed lookup, FX1 slot
FX1_LIST = 0x400d6060        # chooser list, FX1 slot (11 entries + terminator)
NEW_LIST = 0x400d6b00        # relocation target in the free cave

# effect id -> descriptor pointer, taken from the FX2 tables (same descriptors)
ADD = [(0x08, 0x400d4ace, "DELAY"),
       (0x14, 0x400d55cc, "PLATE REV"),
       (0x15, 0x400d575e, "SPRING REV"),
       (0x16, 0x400d58f0, "DARK REV")]

# every `lea.l 0x400d6060, aN` that must follow the list to its new home
LIST_REFS = [0x40037990, 0x40052706, 0x40059bd2]


def off(a):
    return a - BASE


def main():
    if not STOCK.exists():
        sys.exit(f"missing {STOCK} — run 'make os && make recon' first")
    img = bytearray(STOCK.read_bytes())

    def rd(a):
        return int.from_bytes(img[off(a):off(a) + 4], "big")

    def wr(a, v):
        img[off(a):off(a) + 4] = v.to_bytes(4, "big")

    print("=== 1. id-indexed lookup (patched in place) ===")
    for fid, desc, nm in ADD:
        slot = FX1_IDS + fid * 4
        cur = rd(slot)
        if cur != NONE:
            sys.exit(f"FX1 id 0x{fid:02x} at 0x{slot:08x} is not NONE "
                     f"(0x{cur:08x}) — wrong firmware or already patched")
        wr(slot, desc)
        print(f"  id 0x{fid:02x} @0x{slot:08x}: NONE -> 0x{desc:08x}  {nm}")

    print("\n=== 2. chooser list (relocated: cannot grow in place) ===")
    old = []
    a = FX1_LIST
    while rd(a) != 0:
        old.append(rd(a))
        a += 4
        if len(old) > 32:
            sys.exit("FX1 chooser list has no terminator — assumption wrong")
    print(f"  stock list 0x{FX1_LIST:08x}: {len(old)} entries, terminator at 0x{a:08x}")
    if a + 4 > 0x400d6090:
        print(f"  confirmed: FX2 list starts 0x400d6090, no room to append")

    new = old + [d for _, d, _ in ADD] + [0]
    need = len(new) * 4
    if any(img[off(NEW_LIST):off(NEW_LIST) + need]):
        sys.exit(f"cave at 0x{NEW_LIST:08x} is not free")
    for i, v in enumerate(new):
        wr(NEW_LIST + i * 4, v)
    print(f"  rebuilt at 0x{NEW_LIST:08x}: {len(new) - 1} entries + terminator "
          f"({need} B), cave verified free")

    print("\n=== 3. repoint the references ===")
    for r in LIST_REFS:
        if rd(r) != FX1_LIST:
            sys.exit(f"ref at 0x{r:08x} is not 0x{FX1_LIST:08x}: 0x{rd(r):08x}")
        if bytes(img[off(r) - 2:off(r)]) not in (b"\x41\xf9", b"\x47\xf9", b"\x4b\xf9"):
            sys.exit(f"ref at 0x{r:08x} is not preceded by a lea.l opcode")
        wr(r, NEW_LIST)
        print(f"  0x{r:08x}  lea.l -> 0x{NEW_LIST:08x}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(bytes(img))
    stock = STOCK.read_bytes()
    d = [i for i, (x, y) in enumerate(zip(stock, img)) if x != y]
    print(f"\n{OUT}: {len(img):,} bytes, {len(d)} changed vs stock")
    runs, s, p = [], d[0], d[0]
    for i in d[1:]:
        if i > p + 8:
            runs.append((s, p))
            s = i
        p = i
    runs.append((s, p))
    for s, e in runs:
        print(f"  0x{BASE + s:08x}..0x{BASE + e:08x}  {e - s + 1:3d} B")


if __name__ == "__main__":
    main()
