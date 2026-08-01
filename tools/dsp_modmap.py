#!/usr/bin/env python3
"""
Recover the DSP56300 module load map from the MAIN OS image.

Step 1 of the DSP project. Without knowing which bytes load to which DSP address
and in which memory space, any disassembly is at the wrong PC and is worthless.

The ColdFire boots the DSP twice (GPIO 0xfc0a400c selects 0 then 1 -- apparently
two DSPs or two banks), each time uploading a small bootstrap to P memory and
then a large self-describing payload:

    FUN_40001d4c(0x400e21e0, 0x96,  0x31000)   bootstrap A -> P:0x31000
    FUN_40001b18(0x400e2324)                   payload A   (self-describing)
    FUN_40001d4c(0x400e2276, 0xae,  0x32000)   bootstrap B -> P:0x32000
    FUN_40001b18(0x400f59ef)                   payload B   (self-describing)

FUN_40001b18 takes only a pointer, so the payload carries its own addresses.
Decompiled, it walks 24-bit LITTLE-endian words: an optional 3-header and an
optional 4-header (6 bytes each), then records whose leading word is the memory
space (0/1/2), terminated by a word > 3.

    python3 tools/dsp_modmap.py
"""
import pathlib, sys

BASE = 0x40000400
IMG = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
SPACE = {0: "P", 1: "X", 2: "Y", 3: "?"}

PAYLOADS = [("A", 0x400e2324, 0x136cb), ("B", 0x400f59ef, 0x12d05)]
BOOTSTRAPS = [("A", 0x400e21e0, 0x96, 0x31000), ("B", 0x400e2276, 0xae, 0x32000)]


def w24(b, i):
    """24-bit little-endian word, as FUN_40001b18 assembles it."""
    return b[i] | (b[i + 1] << 8) | (b[i + 2] << 16)


def parse(b, order):
    """Walk the records. `order` picks (count,addr) vs (addr,count) -- the
    decompilation did not make the field order unambiguous, so try both and
    keep whichever consumes the blob cleanly."""
    off = 0
    if b[0] == 3:
        off = 6
    if off < len(b) and b[off] == 4:
        off += 6
    mods, guard = [], 0
    while off + 9 <= len(b):
        guard += 1
        if guard > 5000:
            return None, "runaway"
        sp = w24(b, off)
        if sp > 3:
            return mods, f"terminator 0x{sp:06x} at +0x{off:x}"
        f1, f2 = w24(b, off + 3), w24(b, off + 6)
        cnt, addr = (f1, f2) if order == "ca" else (f2, f1)
        if cnt == 0 or cnt > 0x20000:
            return None, f"implausible count {cnt} at +0x{off:x}"
        data = off + 9
        end = data + cnt * 3
        if end > len(b):
            return None, f"record overruns blob at +0x{off:x} (count {cnt})"
        mods.append((sp, addr, cnt, data))
        off = end
    return mods, "ran off the end"


def modules(img, va, ln):
    """Best-effort parse of one payload -> list of (space, addr, count, data_off)."""
    b = img[va - BASE: va - BASE + ln]
    best = None
    for order in ("ca", "ac"):
        mods, _ = parse(b, order)
        if mods:
            consumed = mods[-1][3] + mods[-1][2] * 3
            if best is None or consumed > best[0]:
                best = (consumed, mods)
    return (best[1] if best else []), b


def extract(img, args):
    """--extract <A|B> <hex dsp addr> <out.bin>  : dump one module's raw words."""
    tag, addr_s, out = args
    addr = int(addr_s, 16)
    for t, va, ln in PAYLOADS:
        if t != tag.upper():
            continue
        mods, b = modules(img, va, ln)
        for sp, a, cnt, data in mods:
            if a == addr:
                blob = b[data: data + cnt * 3]
                pathlib.Path(out).write_bytes(blob)
                print(f"payload {t} {SPACE.get(sp,'?')}:0x{addr:05x}  {cnt:,} words "
                      f"({len(blob):,} B) -> {out}")
                print(f"  disassemble with:")
                print(f"    vendor/dsp56300/build/source/disassemble/dsp56kDisassemble \\")
                print(f"        -in {out} -pc {addr:x} -le")
                return
        sys.exit(f"no module at 0x{addr:05x} in payload {t}")
    sys.exit(f"unknown payload {tag}")


def main():
    if not IMG.exists():
        sys.exit(f"missing {IMG}")
    img = IMG.read_bytes()

    if len(sys.argv) > 1 and sys.argv[1] == "--extract":
        return extract(img, sys.argv[2:5])

    print("=== bootstraps (address given explicitly by the ColdFire) ===")
    for tag, va, ln, dsp in BOOTSTRAPS:
        print(f"  {tag}: 0x{va:08x} +0x{ln:<6x} -> P:0x{dsp:05x}  ({ln//3} words)")

    for tag, va, ln in PAYLOADS:
        b = img[va - BASE: va - BASE + ln]
        print(f"\n=== payload {tag} @0x{va:08x}  {ln:,} B  ({ln//3:,} words) ===")
        print(f"  first bytes: {b[:12].hex(' ',1)}")
        best = None
        for order in ("ca", "ac"):
            mods, why = parse(b, order)
            if mods:
                consumed = mods[-1][3] + mods[-1][2] * 3
                score = consumed / len(b)
                print(f"  order={order}: {len(mods)} records, consumed "
                      f"{consumed:,}/{len(b):,} ({score:.1%}) -- {why}")
                if best is None or score > best[0]:
                    best = (score, order, mods)
            else:
                print(f"  order={order}: rejected -- {why}")
        if not best:
            print("  !! neither field order parses; the record layout differs")
            continue
        _, order, mods = best
        print(f"\n  --- module map (field order {order}) ---")
        tot = 0
        for sp, addr, cnt, data in mods:
            tot += cnt
            print(f"    {SPACE.get(sp,'?')}:0x{addr:05x}  {cnt:6,} words  "
                  f"(image 0x{BASE+va-BASE+data:08x})")
        print(f"    total {tot:,} words across {len(mods)} modules")


if __name__ == "__main__":
    main()
