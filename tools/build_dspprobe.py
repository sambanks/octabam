#!/usr/bin/env python3
"""
Build a firmware image carrying the X-memory probe effect (dsp/probe.asm).

Answers: is X:0x08d98..0x0ffff (29,288 words / 664 ms) real memory? It is
unreferenced anywhere in the firmware, and if it exists a new reverb can have
several times the stock delay allocation.

    heavy crush (obviously nasty)  -> X:0xf000 works; X RAM reaches 64K
    mild crush  (clearly dirty)    -> X:0xa000 works, 0xf000 does not
    clean audio (unchanged)        -> neither; X RAM ends below 0xa000

This is also the first custom DSP code through the whole pipeline, which is the
point of doing it with ~40 instructions instead of a reverb.

Payload A cannot grow (payload B follows it immediately in the image), so rather
than insert a record we REPURPOSE one: SPRING's P module is re-pointed to
P:0x2000 and its first words overwritten with the probe. SPRING is the donor
because it is the least-liked of the three reverbs and is being replaced anyway.
Its dispatch entries are redirected to the null stub so selecting SPRING stays
safe (silent passthrough) rather than jumping into vacated memory.

    python3 tools/build_dspprobe.py        # -> out/mainos_dspprobe.bin
"""
import pathlib, subprocess, struct, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from dsp_modmap import BASE, IMG, PAYLOADS, modules, w24  # noqa: E402

OUT = pathlib.Path("out/mainos_dspprobe.bin")
ASM = pathlib.Path("dsp/probe.asm")
DIS = pathlib.Path("vendor/dsp56300/build/source/dsp_host/dsp_asm")
ORG = 0x2000
PROBE_ID = 0x06          # a free effect id: no descriptor, dispatch = null stub
SPRING_ID = 0x15

# per payload: (spring init addr, null-stub init, null-stub proc, X:0x215 module)
P = {"A": (0x01252, 0x007c8, 0x007c9, 0x400e2345),
     "B": (0x01012, 0x00588, 0x00589, 0x400f5a10)}

# ColdFire side
NONE_DESC = 0x400d4618
LOFI_DESC = 0x400d5da6      # stand-in descriptor so the probe has a param page
FX2_IDS = 0x400d5fdc
FX2_LIST = 0x400d6090
NEW_LIST = 0x400d6b00
LIST_REFS = [0x400375f4, 0x40052496, 0x40059a42]


def main():
    if not DIS.exists():
        sys.exit(f"missing {DIS} — run ./setup.sh")
    subprocess.run([str(DIS), "-in", str(ASM), "-org", f"{ORG:x}",
                    "-out", "out/dsp/probe.bin"], check=True)
    blob = pathlib.Path("out/dsp/probe.bin").read_bytes()
    words = [blob[i] | (blob[i + 1] << 8) | (blob[i + 2] << 16)
             for i in range(0, len(blob), 3)]
    print(f"probe: {len(words)} words, init P:0x{ORG:05x}, proc P:0x{ORG + 9:05x}\n")

    img = bytearray(IMG.read_bytes())

    def rdw(a):
        i = a - BASE
        return img[i] | (img[i + 1] << 8) | (img[i + 2] << 16)

    def wrw(a, v):
        i = a - BASE
        img[i], img[i + 1], img[i + 2] = v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff

    for tag, va, ln in PAYLOADS:
        spring, nul_i, nul_p, xtab = P[tag]
        mods, _ = modules(bytes(img), va, ln)
        rec = [m for m in mods if m[0] == 0 and m[1] == spring]
        if len(rec) != 1:
            sys.exit(f"payload {tag}: expected one P module at 0x{spring:05x}")
        _, addr, cnt, data_off = rec[0]
        if cnt < len(words):
            sys.exit(f"payload {tag}: donor module {cnt} words < probe {len(words)}")

        print(f"=== payload {tag} ===")
        af = va + data_off - 6
        if rdw(af) != spring:
            sys.exit(f"payload {tag}: address field is 0x{rdw(af):05x}, expected 0x{spring:05x}")
        wrw(af, ORG)
        print(f"  donor module P:0x{spring:05x} ({cnt} words) -> P:0x{ORG:05x}")

        for i, w in enumerate(words):
            wrw(va + data_off + i * 3, w)
        print(f"  wrote {len(words)} probe words (the module's remaining "
              f"{cnt - len(words)} words load as inert data)")

        for slot, val, what in ((PROBE_ID, ORG, "probe init"),
                                (32 + PROBE_ID, ORG + 9, "probe process"),
                                (SPRING_ID, nul_i, "SPRING init -> null stub"),
                                (32 + SPRING_ID, nul_p, "SPRING proc -> null stub")):
            wrw(xtab + slot * 3, val)
            print(f"  X:0x{0x215 if slot < 32 else 0x235:03x}[0x{slot % 32:02x}] = "
                  f"P:0x{val:05x}   {what}")

    print("\n=== ColdFire: make the probe selectable on FX2 ===")
    # ColdFire pointers are 32-bit BIG-endian; rdw() is the DSP's 24-bit
    # little-endian reader and must not be used on this side of the image.
    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")
    cur = rd32(FX2_IDS + PROBE_ID * 4)
    if cur != NONE_DESC:
        sys.exit(f"FX2 id 0x{PROBE_ID:02x} is not NONE (0x{cur:08x})")
    img[FX2_IDS + PROBE_ID * 4 - BASE: FX2_IDS + PROBE_ID * 4 - BASE + 4] = \
        LOFI_DESC.to_bytes(4, "big")
    print(f"  id 0x{PROBE_ID:02x} -> descriptor 0x{LOFI_DESC:08x} (shows as LO-FI)")

    old, a = [], FX2_LIST
    while int.from_bytes(img[a - BASE:a - BASE + 4], "big"):
        old.append(int.from_bytes(img[a - BASE:a - BASE + 4], "big"))
        a += 4
    new = old + [LOFI_DESC, 0]
    if any(img[NEW_LIST - BASE: NEW_LIST - BASE + len(new) * 4]):
        sys.exit("cave not free")
    for i, v in enumerate(new):
        img[NEW_LIST - BASE + i * 4: NEW_LIST - BASE + i * 4 + 4] = v.to_bytes(4, "big")
    for r in LIST_REFS:
        if int.from_bytes(img[r - BASE:r - BASE + 4], "big") != FX2_LIST:
            sys.exit(f"ref at 0x{r:08x} unexpected")
        img[r - BASE:r - BASE + 4] = NEW_LIST.to_bytes(4, "big")
    print(f"  chooser list -> 0x{NEW_LIST:08x}, {len(new) - 1} entries "
          f"(probe is the LAST one, position {len(old)})")

    OUT.write_bytes(bytes(img))
    stock = IMG.read_bytes()
    d = sum(1 for x, y in zip(stock, img) if x != y)
    print(f"\n{OUT}: {len(img):,} bytes, {d} changed")
    print(f"\nTEST: select the LAST entry on the FX2 effect list (position {len(old)}).")
    print("  heavy distortion -> X RAM reaches 0xf000 (64K): big delay lines available")
    print("  mild distortion  -> reaches 0xa000 but not 0xf000")
    print("  clean audio      -> neither; X RAM ends below 0xa000")
    print("  SPRING is now a silent passthrough by design.")


if __name__ == "__main__":
    main()
