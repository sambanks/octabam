#!/usr/bin/env python3
"""
Build a firmware image with our reverb replacing DARK REV.

    python3 tools/build_reverb.py [dsp/reverb4.asm]

DARK REV is the intended home: 1,067 words of code, and its descriptor's first
parameter is already TIME, which is exactly what our p0 drives. Replacing it
needs no new tables at all -- no descriptor clone, no id/position map -- because
we inherit effect id 0x16 and everything already points at it. Selecting
DARK REV on FX2 runs our reverb.

IMPORTANT: only the FRONT of DARK's module may be overwritten. PLATE REV calls a
helper that lives inside DARK's module, 974 words in (P:0x01a47 in payload A,
P:0x01807 in B). Clobbering it would break PLATE -- the same class of mistake as
vacating SPRING, which had inbound branches and hung the DSP. Our code is 357
words, so it fits in front of the helper with room to spare, and the builder
refuses to write past it.

The blob is position-dependent (`do` encodes an absolute loop-end address), so it
is assembled separately for each payload.
"""
import pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from dsp_modmap import BASE, IMG, PAYLOADS, modules  # noqa: E402

OUT = pathlib.Path("out/mainos_reverb.bin")
DIS = pathlib.Path("vendor/dsp56300/build/source/dsp_host/dsp_asm")
DARK_ID = 0x16

# per payload: (DARK module address, offset of the helper PLATE calls, X:0x215 module)
P = {"A": (0x01679, 974, 0x400e2345),
     "B": (0x01439, 974, 0x400f5a10)}


def assemble(asm, org):
    subprocess.run([str(DIS), "-in", asm, "-org", f"{org:x}",
                    "-out", "out/dsp/rv.bin", "-sym", "out/dsp/rv.sym"],
                   check=True, capture_output=True)
    blob = pathlib.Path("out/dsp/rv.bin").read_bytes()
    words = [blob[i] | (blob[i + 1] << 8) | (blob[i + 2] << 16)
             for i in range(0, len(blob), 3)]
    syms = dict((k, int(v, 16)) for k, v in
                (l.split() for l in
                 pathlib.Path("out/dsp/rv.sym").read_text().split("\n") if l))
    return words, syms["init"], syms["proc"]


def main():
    asm = sys.argv[1] if len(sys.argv) > 1 else "dsp/reverb4.asm"
    if not DIS.exists():
        sys.exit(f"missing {DIS} — run ./setup.sh")
    img = bytearray(IMG.read_bytes())

    def wrw(a, v):
        i = a - BASE
        img[i], img[i + 1], img[i + 2] = v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff

    print(f"source: {asm}\n")
    for tag, va, ln in PAYLOADS:
        dark, helper_off, xtab = P[tag]
        words, init_at, proc_at = assemble(asm, dark)
        mods, _ = modules(bytes(img), va, ln)
        rec = [m for m in mods if m[0] == 0 and m[1] == dark]
        if len(rec) != 1:
            sys.exit(f"payload {tag}: expected one P module at 0x{dark:05x}")
        _, _, cnt, data_off = rec[0]

        if len(words) > helper_off:
            sys.exit(f"payload {tag}: {len(words)} words would overwrite the helper "
                     f"PLATE calls at +{helper_off} — refusing")

        print(f"=== payload {tag} ===")
        print(f"  DARK module P:0x{dark:05x}, {cnt} words")
        for i, w in enumerate(words):
            wrw(va + data_off + i * 3, w)
        print(f"  wrote {len(words)} words at the front; "
              f"{helper_off - len(words)} words clear before PLATE's helper at "
              f"+{helper_off} (P:0x{dark + helper_off:05x})")
        print(f"  init P:0x{init_at:05x}   proc P:0x{proc_at:05x}")

        wrw(xtab + DARK_ID * 3, init_at)
        wrw(xtab + (32 + DARK_ID) * 3, proc_at)
        print(f"    X:0x215[0x{DARK_ID:02x}] = P:0x{init_at:05x}")
        print(f"    X:0x235[0x{DARK_ID:02x}] = P:0x{proc_at:05x}")

    OUT.write_bytes(bytes(img))
    d = sum(1 for x, y in zip(IMG.read_bytes(), img) if x != y)
    print(f"\n{OUT}: {len(img):,} bytes, {d} changed")
    print("\nNo ColdFire-side changes: we inherit DARK REV's id, descriptor and")
    print("chooser entry. Its first parameter is already TIME, which is what p0 drives.")
    print("\nTEST: FX2 -> DARK REV. TIME sweeps the decay (RT60 ~2.7s to ~6.8s).")
    print("      CHORUS and SPRING are untouched this time; PLATE should still work.")


if __name__ == "__main__":
    main()
