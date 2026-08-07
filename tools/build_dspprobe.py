#!/usr/bin/env python3
"""
Build a firmware image carrying a custom DSP effect (dsp/probe.asm).

Currently an X-memory probe: stamp a mask at an address, read it back, apply it
to the audio. Heavy distortion means the address is real and held the value.

    python3 tools/gen_probe.py 4000 > dsp/probe.asm
    python3 tools/build_dspprobe.py

MAXIMALLY CONSERVATIVE variant. Three hardware attempts hung the DSP, and every
one of them relocated the donor module to P:0x2000 as well as replacing its
contents and using a new effect id. So this version removes the relocation: the
code is assembled at the donor's OWN address and overwrites it in place. Only
the contents and the dispatch change.

The donor is CHORUS -- the relocatability scan shows it clean (no absolute
internal jumps, nothing branches into it), unlike SPRING which has 5 and 3.
CHORUS becomes a silent passthrough.

Note the blob is POSITION-DEPENDENT even without branches: `do` encodes an
absolute loop-end address, so it is assembled separately for each payload.
"""
import pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from dsp_modmap import BASE, IMG, PAYLOADS, modules  # noqa: E402

OUT = pathlib.Path("out/mainos_dspprobe.bin")
ASM = pathlib.Path("dsp/probe.asm")
DIS = pathlib.Path("vendor/dsp56300/build/source/dsp_host/dsp_asm")
PROBE_ID = 0x06
DONOR_ID = 0x12                       # CHORUS

# per payload: (donor P address, null-stub init, null-stub proc, X:0x215 module)
P = {"A": (0x00eb7, 0x007c8, 0x007c9, 0x400e2345),
     "B": (0x00c77, 0x00588, 0x00589, 0x400f5a10)}

NONE_DESC = 0x400d4618
LOFI_ENTRY = 0x400d5d6e
CLONE_AT = 0x400d7000
CLONE_DESC = CLONE_AT + 0x38
DESC_LEN = 0x192
FX2_IDS = 0x400d5fdc
FX2_LIST = 0x400d6090
NEW_LIST = 0x400d6b00
LIST_REFS = [0x400375f4, 0x40052496, 0x40059a42]
ID2POS = 0x400d6150


def assemble(org):
    subprocess.run([str(DIS), "-in", str(ASM), "-org", f"{org:x}",
                    "-out", "out/dsp/probe.bin", "-sym", "out/dsp/probe.sym"],
                   check=True, capture_output=True)
    blob = pathlib.Path("out/dsp/probe.bin").read_bytes()
    words = [blob[i] | (blob[i + 1] << 8) | (blob[i + 2] << 16)
             for i in range(0, len(blob), 3)]
    syms = dict((k, int(v, 16)) for k, v in
                (l.split() for l in
                 pathlib.Path("out/dsp/probe.sym").read_text().split("\n") if l))
    return words, syms["init"], syms["proc"]


def main():
    if not DIS.exists():
        sys.exit(f"missing {DIS} — run 'make setup'")
    img = bytearray(IMG.read_bytes())

    def wrw(a, v):
        i = a - BASE
        img[i], img[i + 1], img[i + 2] = v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    for tag, va, ln in PAYLOADS:
        donor, nul_i, nul_p, xtab = P[tag]
        words, init_at, proc_at = assemble(donor)     # per payload: `do` is absolute
        mods, _ = modules(bytes(img), va, ln)
        rec = [m for m in mods if m[0] == 0 and m[1] == donor]
        if len(rec) != 1:
            sys.exit(f"payload {tag}: expected one P module at 0x{donor:05x}")
        _, _, cnt, data_off = rec[0]
        if cnt < len(words):
            sys.exit(f"payload {tag}: donor {cnt} words < probe {len(words)}")

        print(f"=== payload {tag} ===")
        print(f"  donor CHORUS module P:0x{donor:05x} ({cnt} words), NOT relocated")
        for i, w in enumerate(words):
            wrw(va + data_off + i * 3, w)
        print(f"  overwrote first {len(words)} words with the probe")
        print(f"  init P:0x{init_at:05x}  proc P:0x{proc_at:05x}  (from the symbol map)")

        for slot, val, what in ((PROBE_ID, init_at, "probe init"),
                                (32 + PROBE_ID, proc_at, "probe process"),
                                (DONOR_ID, nul_i, "CHORUS init -> null stub"),
                                (32 + DONOR_ID, nul_p, "CHORUS proc -> null stub")):
            wrw(xtab + slot * 3, val)
            print(f"    X:0x{0x215 if slot < 32 else 0x235:03x}[0x{slot % 32:02x}] "
                  f"= P:0x{val:05x}   {what}")

    print("\n=== ColdFire: five tables (see PARAM_PAGES.md) ===")
    if rd32(FX2_IDS + PROBE_ID * 4) != NONE_DESC:
        sys.exit(f"FX2 id 0x{PROBE_ID:02x} is not NONE")
    src, dst = LOFI_ENTRY - BASE, CLONE_AT - BASE
    if any(img[dst:dst + DESC_LEN]):
        sys.exit("cave not free for the descriptor")
    img[dst:dst + DESC_LEN] = img[src:src + DESC_LEN]
    img[dst + 0x3b] = PROBE_ID
    img[dst + 0x3c:dst + 0x41] = b"PRB\x00\x00"
    img[dst + 0x41:dst + 0x4e] = b"XPROBE\x00" + b"\x00" * 6
    print(f"  3+4. own descriptor @0x{CLONE_AT:08x}, id byte 0x{PROBE_ID:02x}")

    img[FX2_IDS + PROBE_ID * 4 - BASE: FX2_IDS + PROBE_ID * 4 - BASE + 4] = \
        CLONE_DESC.to_bytes(4, "big")
    print(f"  1. id lookup [0x{PROBE_ID:02x}] -> 0x{CLONE_DESC:08x}")

    old, a = [], FX2_LIST
    while rd32(a):
        old.append(rd32(a))
        a += 4
    new = old + [CLONE_DESC, 0]
    if any(img[NEW_LIST - BASE: NEW_LIST - BASE + len(new) * 4]):
        sys.exit("cave not free for the list")
    for i, v in enumerate(new):
        img[NEW_LIST - BASE + i * 4: NEW_LIST - BASE + i * 4 + 4] = v.to_bytes(4, "big")
    for r in LIST_REFS:
        if rd32(r) != FX2_LIST:
            sys.exit(f"ref at 0x{r:08x} unexpected")
        img[r - BASE:r - BASE + 4] = NEW_LIST.to_bytes(4, "big")
    print(f"  2. chooser list -> 0x{NEW_LIST:08x}, probe at position {len(old)}")

    img[ID2POS + PROBE_ID * 4 - BASE: ID2POS + PROBE_ID * 4 - BASE + 4] = \
        len(old).to_bytes(4, "big")
    print(f"  5. id->position [0x{PROBE_ID:02x}] = {len(old)}")

    OUT.write_bytes(bytes(img))
    d = sum(1 for x, y in zip(IMG.read_bytes(), img) if x != y)
    print(f"\n{OUT}: {len(img):,} bytes, {d} changed")
    print(f"\nTEST: FX2 list, last entry (XPROBE, position {len(old)}).")
    print("  heavy distortion -> the probed address is real; whole path works")
    print("  silence          -> read back zero")
    print("  clean            -> read back all-ones")
    print("  CHORUS is a silent passthrough (donor).")


if __name__ == "__main__":
    main()
