#!/usr/bin/env python3
"""
Build a firmware image with our reverb replacing SPRING REV *and* DARK REV.

    python3 tools/build_reverb.py [dsp/reverb4.asm]

DARK REV is the home we inherit: its descriptor's first parameter is already
TIME, which is what p0 drives, so selecting DARK REV on FX2 runs our reverb with
no descriptor clone and no id/position map.

WE NOW ALSO TAKE SPRING REV'S MODULE, for the code space. The three reverb
modules are CONTIGUOUS in both payloads:

    PLATE   P:0x1000 (B 0x0dc0)   594 words
    SPRING  P:0x1252 (B 0x1012)  1063 words   <- taken
    DARK    P:0x1679 (B 0x1439)  1067 words   <- taken (front 974 only)

so the blob is assembled at SPRING's address and runs straight through into
DARK's, giving **2037 usable words** instead of 974.

Two limits still bind, and the builder enforces both:

* PLATE REV `jsr`s a helper inside DARK's module 974 words in (P:0x01a47 in A,
  P:0x01807 in B). That helper must survive, so the DARK half is capped at 974.
* The modules are separate RECORDS in the image, each with its own load address,
  so the blob is split: the first 1063 words go into SPRING's record and the
  remainder into DARK's.

Why taking SPRING is safe now, when an earlier attempt hung the DSP: the inbound
scan shows SPRING's module has exactly three callers, all of them `jsr 0x1586`
from *stock DARK*. That earlier attempt vacated SPRING while stock DARK was
still live, so its jsr landed in the new code. We replace DARK outright and
never call 0x1586, so nothing reaches into SPRING any more. (PLATE has no
inbound branches at all, which is the next 594 words if they are ever wanted.)

SPRING's own dispatch entries are repointed at our init/proc, so selecting
SPRING REV simply runs the reverb rather than jumping into the middle of it.

The blob is position-dependent (`do` encodes an absolute loop-end address), so it
is assembled separately for each payload.
"""
import pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from dsp_modmap import BASE, IMG, PAYLOADS, modules  # noqa: E402

OUT = pathlib.Path("out/mainos_reverb.bin")
DIS = pathlib.Path("vendor/dsp56300/build/source/dsp_host/dsp_asm")
DARK_ID = 0x16
SPRING_ID = 0x15

# per payload: (SPRING module addr, SPRING words, DARK module addr,
#               offset of the helper PLATE calls, X:0x215 module)
P = {"A": (0x01252, 1063, 0x01679, 974, 0x400e2345),
     "B": (0x01012, 1063, 0x01439, 974, 0x400f5a10)}


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
        spring, spring_len, dark, helper_off, xtab = P[tag]
        if spring + spring_len != dark:
            sys.exit(f"payload {tag}: SPRING 0x{spring:05x}+{spring_len} does not "
                     f"abut DARK 0x{dark:05x} — the layout assumption is broken")
        budget = spring_len + helper_off
        words, init_at, proc_at = assemble(asm, spring)
        mods, _ = modules(bytes(img), va, ln)

        def record(addr):
            rec = [m for m in mods if m[0] == 0 and m[1] == addr]
            if len(rec) != 1:
                sys.exit(f"payload {tag}: expected one P module at 0x{addr:05x}")
            return rec[0]

        _, _, s_cnt, s_off = record(spring)
        _, _, d_cnt, d_off = record(dark)
        if s_cnt != spring_len:
            sys.exit(f"payload {tag}: SPRING module is {s_cnt} words, expected {spring_len}")

        if len(words) > budget:
            sys.exit(f"payload {tag}: {len(words)} words exceeds the {budget}-word "
                     f"budget (SPRING {spring_len} + DARK front {helper_off}) — "
                     f"the helper PLATE calls at +{helper_off} must survive. Refusing.")

        print(f"=== payload {tag} ===")
        print(f"  SPRING module P:0x{spring:05x}, {s_cnt} words   (taken)")
        print(f"  DARK   module P:0x{dark:05x}, {d_cnt} words   (front {helper_off} taken)")

        # The two modules are contiguous in P but separate records in the image.
        head, tail = words[:spring_len], words[spring_len:]
        for i, w in enumerate(head):
            wrw(va + s_off + i * 3, w)
        for i, w in enumerate(tail):
            wrw(va + d_off + i * 3, w)

        print(f"  wrote {len(words)} words at P:0x{spring:05x}: "
              f"{len(head)} into SPRING, {len(tail)} into DARK's front")
        print(f"  {budget - len(words)} words clear before PLATE's helper at "
              f"+{helper_off} (P:0x{dark + helper_off:05x})")
        print(f"  init P:0x{init_at:05x}   proc P:0x{proc_at:05x}")
        # per payload, so the emulator harness never has to guess. Both payloads
        # write out/dsp/rv.sym, and the second one wins -- passing those
        # addresses against payload A's memory image silently runs garbage.
        pathlib.Path(f"out/dsp/rv_{tag}.sym").write_text(
            f"init {init_at:x}\nproc {proc_at:x}\n")

        # DARK is the id we ship on. SPRING's entries must move too: its module
        # now holds our code, so its old init/proc addresses point into the
        # middle of us. Aiming them at our own entry points makes selecting
        # SPRING REV simply run the reverb instead of hanging the DSP.
        for eid, who in ((DARK_ID, "DARK"), (SPRING_ID, "SPRING")):
            wrw(xtab + eid * 3, init_at)
            wrw(xtab + (32 + eid) * 3, proc_at)
            print(f"    X:0x215[0x{eid:02x}] = P:0x{init_at:05x}   "
                  f"X:0x235[0x{eid:02x}] = P:0x{proc_at:05x}   ({who})")

    OUT.write_bytes(bytes(img))
    d = sum(1 for x, y in zip(IMG.read_bytes(), img) if x != y)
    print(f"\n{OUT}: {len(img):,} bytes, {d} changed")
    print("\nNo ColdFire-side changes: we inherit DARK REV's id, descriptor and")
    print("chooser entry. Its first parameter is already TIME, which is what p0 drives.")
    print("\nTEST: FX2 -> DARK REV. TIME sweeps the decay (RT60 ~2.7s to ~6.8s).")
    print("      SPRING REV is GONE — its module is now ours, and its id runs the")
    print("      reverb too. PLATE and CHORUS must still work: check them.")


if __name__ == "__main__":
    main()
