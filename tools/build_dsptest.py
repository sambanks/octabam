#!/usr/bin/env python3
"""
TEST: does the DSP have more than 8K words of internal P memory?

Both payloads' P modules are perfectly contiguous, ending at P:0x01fdf (payload
A) -- 99.6% of 0x2000. That looks like an 8K internal P RAM that is essentially
full, which would mean a new effect cannot be appended and must instead replace
an existing one. But it is an inference from the packing, not a datasheet fact.

This settles it by ear. CHORUS is RELOCATED to P:0x02000:

  * its code is exactly one module (329 words in both payloads),
  * it contains no absolute jmp/jsr, so relative branches survive the move,
  * nothing outside it branches into it,

so moving it is three words per payload: the module's load-address field, and
its two dispatch-table entries (X:0x215[0x12] init, X:0x235[0x12] process).

    CHORUS still works  -> P:0x2000 is real RAM, effects can be APPENDED
    CHORUS is silent /
    passthrough / broken -> internal P RAM ends at 8K, effects must REPLACE

Contained either way: only CHORUS changes. Every other effect keeps its address
and its dispatch entries. If P:0x2000 does not exist, selecting CHORUS may glitch
or hang the DSP -- recoverable with a power cycle.

    python3 tools/build_dsptest.py        # -> out/mainos_dsptest.bin
"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from dsp_modmap import BASE, IMG, PAYLOADS, modules  # noqa: E402

OUT = pathlib.Path("out/mainos_dsptest.bin")
NEW_ADDR = 0x2000
CHORUS_ID = 0x12

# per payload: (chorus init addr, chorus process addr, X:0x215 module image addr)
CHORUS = {"A": (0x00eb7, 0x00ed7, 0x400e2345),
          "B": (0x00c77, 0x00c97, 0x400f5a10)}


def main():
    if not IMG.exists():
        sys.exit(f"missing {IMG}")
    img = bytearray(IMG.read_bytes())

    def rdw(a):
        i = a - BASE
        return img[i] | (img[i + 1] << 8) | (img[i + 2] << 16)

    def wrw(a, v):
        i = a - BASE
        img[i], img[i + 1], img[i + 2] = v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff

    for tag, va, ln in PAYLOADS:
        ini, pro, xtab = CHORUS[tag]
        mods, _ = modules(bytes(img), va, ln)

        rec = [m for m in mods if m[0] == 0 and m[1] == ini]
        if len(rec) != 1:
            sys.exit(f"payload {tag}: expected one P module at 0x{ini:05x}, got {len(rec)}")
        _, addr, cnt, data_off = rec[0]

        # record header is [space][addr][count] immediately before the data
        addr_field = va + data_off - 6
        if rdw(addr_field) != ini:
            sys.exit(f"payload {tag}: address field at 0x{addr_field:08x} is "
                     f"0x{rdw(addr_field):05x}, expected 0x{ini:05x}")

        print(f"=== payload {tag} ===")
        print(f"  CHORUS module: P:0x{ini:05x}, {cnt} words")
        wrw(addr_field, NEW_ADDR)
        print(f"  load address  @0x{addr_field:08x}: 0x{ini:05x} -> 0x{NEW_ADDR:05x}")

        # dispatch entries: init at X:0x215[id], process at X:0x235[id]
        for slot, old, tag2 in ((CHORUS_ID, ini, "init   X:0x215"),
                                (32 + CHORUS_ID, pro, "process X:0x235")):
            ea = xtab + slot * 3
            if rdw(ea) != old:
                sys.exit(f"payload {tag}: {tag2} entry is 0x{rdw(ea):05x}, "
                         f"expected 0x{old:05x}")
            new = NEW_ADDR + (old - ini)
            wrw(ea, new)
            print(f"  {tag2}[0x{CHORUS_ID:02x}] @0x{ea:08x}: 0x{old:05x} -> 0x{new:05x}")

    OUT.write_bytes(bytes(img))
    stock = IMG.read_bytes()
    d = [i for i, (x, y) in enumerate(zip(stock, img)) if x != y]
    print(f"\n{OUT}: {len(img):,} bytes, {len(d)} changed")
    print("\nTEST: select CHORUS on any track.")
    print("  works  -> P RAM extends past 8K; new effects can be APPENDED at 0x2000+")
    print("  broken -> internal P RAM ends at 8K; new effects must REPLACE an existing one")


if __name__ == "__main__":
    main()
