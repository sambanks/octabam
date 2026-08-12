#!/usr/bin/env python3
"""Prove an alternate BongDelay engine is BIT-IDENTICAL to the shipping one.

    python3 tools/verify_delay.py dsp/delay_server2.asm
    python3 tools/verify_delay.py dsp/delay_server2.asm --ref dsp/delay_server.asm

The verify_roll pattern applied to the delay (PLAN.md 3.1, stage 1 CLEAN:
refactor first, prove equivalence, THEN add modes). Both engines are built
into the DELAY HATCH -- DEV=1 XBUS=1, the `make render-delay` configuration,
delay at its shipping Y base 0x38000 and, since the 12 Aug placement change,
at P:0x04000 outside the donor region (build_bus.py's DEV_DELAY_P; the
record lives in the .mem dump) -- and rendered through the real send path
(--layout DS: a DELAY SERVER at position 0 plus a SEND feeding it over the
shared bus). NOT SPEC: a SPEC dump has no delay at all (id 0x06 -> SEND
alias), the 12 Aug mislabel send_probe now dies on.

THE CONTROLS ARE THE POINT (verify_roll's lesson, verbatim): a bit-identical
claim is worthless without a companion check proving the comparison can see
a difference at all.

  * sensitivity: the REFERENCE rendered at TONE=100 vs TONE=10 must DIFFER.
    If not, the harness is blind and every PASS below it means nothing.
  * nop: ONE nop inserted inside the reference's sample loop must move the
    module (+1 word, every following address and `do` loop-end literal with
    it) and STILL render identically -- equality is a claim about audio, not
    about bytes, and a candidate that happened to place identically could
    otherwise pass for the wrong reason.

Coverage: the knob corners that exercise the addressing this refactor
touches -- TIME extremes (TIME=0 keeps the read 64 samples behind the write,
so both wrap constantly; TIME=127 is the 16320 maximum), PING 0/64/127 (the
LineR-silent, mixed and full-swap crossfeed paths), FDBK+TONE high (long
recirculation through the one-pole), and a nonzero --split (the a=0/a=1
sub-block path, whose bus bookkeeping never runs at split 0). Unlike
verify_roll these are RUNTIME knob values, not per-build overrides, so one
build of each engine serves every case.

DMODE: if the candidate carries a `; DMODE_OVERRIDE` marker (the v2 mode
dispatch), it is additionally built with DMODE=3 -- an engine that does not
exist -- and must render identically to the reference: an unknown MODE
select must degrade to CLEAN, the trad delay, never to silence.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import send_probe

SCRATCH = ROOT / "out" / "delayverify"
SR = 44100

# TIME FDBK TONE PING MIX VRBW p6 p7 VRBD p9 -- send_probe.DELAY_PARAMS order
BASE = [40, 60, 100, 64, 90, 0, 0, 0, 0, 0]


def dp(**kw):
    p = list(BASE)
    for k, v in kw.items():
        p[{"TIME": 0, "FDBK": 1, "TONE": 2, "PING": 3, "MIX": 4}[k]] = v
    return p


def make_source():
    """0.35 s of broadband noise then silence to 1.2 s. Fixed seed -- the
    same LCG as verify_roll. Silence matters: it is where recirculating
    feedback (and nothing else) is the whole signal."""
    n = int(SR * 1.2)
    state = 0x1234567
    src = []
    for i in range(n):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        v = (((state >> 8) & 0xFFFF) - 0x8000) / 0x8000
        src.append(v if i < int(SR * 0.35) else 0.0)
    return src


def build(src, tag, dmode=None):
    """Build the delay hatch with DLSRC=src, keep its payload-A dump, return
    (mem, delay_words, hatch_free)."""
    env = dict(os.environ, DEV="1", XBUS="1", DLSRC=str(src))
    for k in ("SPEC", "BURN", "PROBE", "XPROBE", "DELAYPROBE", "MODE",
              "WIDTH", "DMODE", "NOSHIM"):
        env.pop(k, None)
    if dmode is not None:
        env["DMODE"] = str(dmode)
    r = subprocess.run([sys.executable, "tools/build_bus.py"], cwd=ROOT,
                       env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FAILED: build DLSRC={src}"
                 f"{' DMODE=' + str(dmode) if dmode is not None else ''}\n"
                 f"{r.stdout[-4000:]}\n{r.stderr[-4000:]}")
    words = free = None
    for line in r.stdout.splitlines():
        s = line.strip()
        if words is None and s.startswith("DELAY SERVER") and "words)" in s:
            words = int(line.split("(")[1].split("words")[0])
        elif words is not None and free is None and s.startswith("region"):
            free = int(line.split("FREE")[1].split()[0])
    if words is None:
        sys.exit(f"verify_delay: no DELAY SERVER placement line in the build "
                 f"output for {src} -- was the delay placed at all?")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    mem = SCRATCH / f"{tag}.mem"
    shutil.copyfile(ROOT / "out/dsp/mem_dev_A.mem", mem)
    return mem, words, free


NOP_MARKERS = ("; ---- one-pole damping in the feedback path",
               "; ---- ping-pong crossfeed matrix")


def nop_variant(ref):
    """A copy of `ref` with exactly one `nop` added inside the sample loop.
    Refuses rather than guessing if no marker is found -- a nop OUTSIDE the
    loop would still relocate the code but prove something much weaker."""
    lines = (ROOT / ref).read_text().splitlines(keepends=True)
    for marker in NOP_MARKERS:
        hit = [i for i, l in enumerate(lines) if l.startswith(marker)]
        if hit:
            lines.insert(hit[0], "        nop                     ; verify_delay control\n")
            break
    else:
        sys.exit(f"verify_delay: no known sample-loop marker in {ref}; "
                 f"add one to NOP_MARKERS rather than dropping the control")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    out = SCRATCH / "ref_nop.asm"
    out.write_text("".join(lines))
    return out.relative_to(ROOT)


def render(mem, params, split=0, source=[]):
    """One DS-layout render -> (L, R) sample lists of the DELAY's output."""
    snd = list(send_probe.SEND_PARAMS)
    snd[0] = 127                        # ->DELAY, x:(r6+0) -- NOT ->REVERB
    L, R = send_probe.run(mem, 0, 0.3, send_probe.REV_PARAMS, snd,
                          amp=0.5, wave_src=source, split=split,
                          layout="DS", delay_params=params, pick="D")
    return L, R


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidate", help="the engine under test, e.g. dsp/delay_server2.asm")
    ap.add_argument("--ref", default="dsp/delay_server.asm",
                    help="the engine it must match (default: the shipping one)")
    args = ap.parse_args()

    for p in (args.candidate, args.ref):
        if not (ROOT / p).exists():
            sys.exit(f"verify_delay: no such source {p}")

    source = make_source()
    ok = True

    def check(label, cond, detail=""):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}{detail}")
        ok = ok and cond

    print(f"reference {args.ref}\ncandidate {args.candidate}\n")

    # ---- the controls, first: can this comparison see anything? ----------
    ref_mem, ref_words, ref_free = build(args.ref, "ref")
    c_hi = render(ref_mem, dp(TONE=100), source=source)
    c_lo = render(ref_mem, dp(TONE=10), source=source)
    check("harness is sensitive (reference TONE=100 vs TONE=10 differ)",
          c_hi != c_lo,
          "" if c_hi != c_lo else
          "  <-- the comparison is BLIND; every result below is meaningless")

    nop_mem, nop_words, _ = build(nop_variant(args.ref), "ref_nop")
    check("nop control: one nop moved the code", nop_words == ref_words + 1,
          f"  ({ref_words} -> {nop_words} words)")
    n_hi = render(nop_mem, dp(TONE=100), source=source)
    check("nop control: relocated code still renders identically", n_hi == c_hi)

    # ---- then the equality cases ------------------------------------------
    cand_mem, cand_words, cand_free = build(args.candidate, "cand")
    CASES = [
        ("defaults", dp(), 0),
        ("PING=0 (LineR silent)", dp(PING=0), 0),
        ("PING=127 (full swap)", dp(PING=127), 0),
        ("TIME=0 (64-sample floor, wrap-heavy)", dp(TIME=0), 0),
        ("TIME=127 (16320 max)", dp(TIME=127), 0),
        ("FDBK=127 TONE=127 (long recirculation)", dp(FDBK=127, TONE=127), 0),
        ("defaults, split=7 (a=0/a=1 sub-block path)", dp(), 7),
    ]
    for label, params, split in CASES:
        a = render(ref_mem, params, split, source)
        b = render(cand_mem, params, split, source)
        detail = ""
        if a != b:
            fa, fb = a[0] + a[1], b[0] + b[1]
            n = sum(1 for x, y in zip(fa, fb) if x != y)
            first = next((i for i, (x, y) in enumerate(zip(fa, fb)) if x != y), -1)
            detail = f"  (first differing sample {first}, {n} of {len(fa)} differ)"
        check(f"bit-identical: {label}", a == b, detail)

    # ---- unknown MODE must fall back to CLEAN ------------------------------
    if "; DMODE_OVERRIDE" in (ROOT / args.candidate).read_text():
        dm_mem, _, _ = build(args.candidate, "cand_dmode3", dmode=3)
        d = render(dm_mem, dp(), source=source)
        r = render(ref_mem, dp(), source=source)
        check("DMODE=3 (nonexistent mode) degrades to CLEAN, bit-identical",
              d == r)
    else:
        print("  [ -- ] DMODE fallback case skipped: candidate has no "
              "; DMODE_OVERRIDE marker (a v1 source)")

    print(f"\n  DELAY SERVER {ref_words} -> {cand_words} words "
          f"({cand_words - ref_words:+d}); donor-region FREE {ref_free} -> "
          f"{cand_free} (the delay sits OUTSIDE it at DEV_DELAY_P since the "
          f"12 Aug placement change)")
    print("\nOK" if ok else "\nFAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
