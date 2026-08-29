#!/usr/bin/env python3
"""Prove an alternate reverb engine is BIT-IDENTICAL to the shipping one.

    python3 tools/verify_roll.py dsp/reverb_rolled.asm
    python3 tools/verify_roll.py cand.asm --ref modules/chonverb/reverb_server.asm

PLAN.md step 1 rolled the tank into a loop and moved per-line state out of
the full `r7` block into absolute Y (landed; the shipping engine is the
8-line rolled tank). The gate remains for any future engine refactor: the
candidate build must render byte-for-byte identically to the reference, or
something moved that was not supposed to. Coverage: every MODE character
(ROOM/PLATE/BIG since the HALL cut) plus a TIME=127 SIZE=127 DIFF=127 wet
case, because MODE varies six levers and the extreme case is where an
off-by-one in a tap or a mask actually shows.

THE CONTROL IS THE POINT. `octamax-assembler-traps` records two instructions
this assembler silently mis-encodes, and the lesson from that session was that
a bit-identical claim is worthless without a companion check proving the
comparison can see a difference at all. So every run also renders the
REFERENCE engine twice -- once at HP=0, once at HP=64 -- and those must
DIFFER. If they do not, the harness is blind and every PASS below it means
nothing. `tools/verify_burn.py` uses the same pairing for the same reason.

Source material is synthesised deterministically: a broadband burst then
silence. Equality does not care about spectrum, but the control does -- HP is
a low cut inside the feedback path, so the source needs low content for the
difference to exist.
"""
import argparse
import os
import pathlib
import struct
import subprocess
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from remix import registry  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))

SCRATCH = ROOT / "out" / "rollverify"
SR = 44100
MODES = ["ROOM", "PLATE", "BIG"]  # HALL cut 9 Aug 2026; MODE=3 no longer exists


def run(cmd, **kw):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(str(c) for c in cmd)}\n"
                 f"{r.stdout[-4000:]}\n{r.stderr[-4000:]}")
    return r.stdout


def make_source(path):
    """1/3 s of broadband noise, then silence to 1.5 s. Fixed seed."""
    n = int(SR * 1.5)
    state = 0x1234567
    frames = bytearray()
    for i in range(n):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        v = ((state >> 8) & 0xFFFF) - 0x8000
        env = 1.0 if i < SR // 3 else 0.0
        frames += struct.pack("<h", int(v * 0.5 * env))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))


def build(src, mode, tag):
    """Build with RVSRC=src (and MODE if given), dump payload A, return the .mem.

    Everything lands under out/rollverify/ so no intermediate can be mistaken
    for the flashable out/mainos_bus.bin -- and the image is dumped straight
    after its own build, before the next one overwrites it.

    XBUS=1 SPEC=1 -- `make bus`, the shipping configuration -- is forced, and
    not only because it is what ships. The plain build packs BOTH servers into
    one 2,724-word region and NO LONGER FITS at all (DELAY SERVER overruns,
    2,794 > 2,724 -- the same overrun that makes verify_burn skip). Under
    specialization payload A carries the reverb by itself (FREE 32 as of
    11 Aug 2026; the build report is the live number), which is the space
    this refactor is measured against anyway.
    """
    env = dict(os.environ, RVSRC=str(src), XBUS="1", SPEC="1")
    env.pop("BURN", None)
    if mode is None:
        env.pop("MODE", None)
    else:
        env["MODE"] = str(mode)
    out = run([sys.executable, "tools/build_bus.py"], env=env)
    words = free = None
    for line in out.splitlines():
        if "REVERB SERVER P:0x" in line:
            words = int(line.split("(")[1].split("words")[0])
        elif words is not None and "FREE" in line and free is None:
            free = int(line.split("FREE")[1].split()[0])
    import dsp_modmap
    SCRATCH.mkdir(parents=True, exist_ok=True)
    mem = SCRATCH / f"{tag}.mem"
    dsp_modmap.dumpmem((ROOT / "out/mainos_bus.bin").read_bytes(), ["A", str(mem)])
    return mem, words, free


NOP_MARKERS = ("; ---- feedback and write back",
               "; ---- 4x4 Hadamard",
               "; ---- wet added to dry")


def nop_variant(ref):
    """A copy of `ref` with exactly one `nop` added inside the sample loop.

    The marker list is tried in order so this keeps working if the tank is
    restructured -- but it refuses rather than guessing if none is found,
    because a nop inserted OUTSIDE the sample loop would still relocate the
    code and would still pass, while proving something much weaker.
    """
    text = (ROOT / ref).read_text()
    lines = text.splitlines(keepends=True)
    for marker in NOP_MARKERS:
        hit = [i for i, l in enumerate(lines) if l.startswith(marker)]
        if hit:
            lines.insert(hit[0], "        nop                     ; verify_roll control\n")
            break
    else:
        sys.exit(f"verify_roll: no known sample-loop marker in {ref}; "
                 f"add one to NOP_MARKERS rather than dropping the control")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    out = SCRATCH / "ref_nop.asm"
    out.write_text("".join(lines))
    return out.relative_to(ROOT)


def render(mem, src, out, params=(), wet=False):
    cmd = [sys.executable, "tools/render_reverb.py", str(src),
           "--mem", str(mem), "-o", str(out)]
    for p in params:
        cmd += ["-p", p]
    if wet:
        cmd.append("--wet")
    run(cmd)
    return out.read_bytes()


# The cases docs/XBUS.md asks for: every MODE character, plus one extreme.
# (label, MODE for the build, render params, wet-only)
CASES = [(f"MODE={i} {name}", i, (), False) for i, name in enumerate(MODES)] + [
    ("TIME=127 SIZE=127 DIFF=127 wet", None,
     ("TIME=127", "SIZE=127", "DIFF=127"), True),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidate", help="the engine under test, e.g. dsp/reverb_rolled.asm")
    ap.add_argument("--ref", default=registry.asm("chonverb"),
                    help="the engine it must match (default: the shipping one)")
    args = ap.parse_args()

    for p in (args.candidate, args.ref):
        if not (ROOT / p).exists():
            sys.exit(f"verify_roll: no such source {p}")

    wav = SCRATCH / "src.wav"
    make_source(wav)

    ok = True

    def check(label, cond, detail=""):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}{detail}")
        ok = ok and cond

    print(f"reference {args.ref}\ncandidate {args.candidate}\n")

    # ---- the control, first: can this comparison see anything? -----------
    # Build the REFERENCE once with no MODE override and render it at two HP
    # settings. HP=0 is documented in modules/chonverb/reverb_server.asm as an exact bypass
    # of the in-loop low cut, so HP=0 vs HP=64 is a real change to the audio.
    ref_mem, ref_words, ref_free = build(args.ref, None, "ref_default")
    c0 = render(ref_mem, wav, SCRATCH / "ctl_hp0.wav", ("HP=0",))
    c64 = render(ref_mem, wav, SCRATCH / "ctl_hp64.wav", ("HP=64",))
    check("harness is sensitive (reference HP=0 vs HP=64 differ)", c0 != c64,
          "" if c0 != c64 else
          "  <-- the comparison is BLIND; every result below is meaningless")

    # ---- the second control: ONE nop, inside the sample loop -------------
    # The HP pair proves the render responds to a parameter. This proves it
    # responds to the CODE, and that equality is a claim about audio rather
    # than about bytes: a single nop makes the module one word longer, which
    # moves every address after it and the `do` loop-end literals with it, and
    # the render must come out unchanged anyway. Without this, a candidate
    # that happened to place identically could pass for the wrong reason.
    nop_src = nop_variant(args.ref)
    nop_mem, nop_words, _ = build(nop_src, None, "ref_nop")
    check("nop control: one nop moved the code", nop_words == (ref_words or 0) + 1,
          f"  ({ref_words} -> {nop_words} words)")
    n0 = render(nop_mem, wav, SCRATCH / "ctl_nop.wav", ("HP=0",))
    check("nop control: relocated code still renders identically", n0 == c0)

    # ---- then the equality cases ----------------------------------------
    for label, mode, params, wet in CASES:
        slug = label.split()[0].replace("=", "") if mode is not None else "extreme"
        a_mem, _, _ = build(args.ref, mode, f"ref_{slug}")
        a = render(a_mem, wav, SCRATCH / f"ref_{slug}.wav", params, wet)
        b_mem, cw, cf = build(args.candidate, mode, f"cand_{slug}")
        b = render(b_mem, wav, SCRATCH / f"cand_{slug}.wav", params, wet)
        detail = ""
        if a != b:
            if len(a) != len(b):
                detail = f"  ({len(a)} vs {len(b)} bytes)"
            else:
                first = next(i for i, (x, y) in enumerate(zip(a, b)) if x != y)
                n = sum(1 for x, y in zip(a, b) if x != y)
                detail = f"  (first differing byte {first}, {n} of {len(a)} differ)"
        check(f"bit-identical: {label}", a == b, detail)

    # Size is not a gate -- it is the number the refactor exists to move, so
    # report it rather than asserting on it.
    if cw is not None and ref_words is not None:
        print(f"\n  REVERB SERVER {ref_words} -> {cw} words "
              f"({cw - ref_words:+d}), payload A FREE {ref_free} -> {cf}")

    print("\nOK" if ok else "\nFAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
