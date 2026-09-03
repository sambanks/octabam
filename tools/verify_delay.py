#!/usr/bin/env python3
"""Prove an alternate BongDelay engine is BIT-IDENTICAL to the shipping one.

    python3 tools/verify_delay.py modules/bongdelay/delay_server2.asm
    python3 tools/verify_delay.py cand.asm --ref modules/bongdelay/delay_server.asm

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

MODE COVERAGE (added 12 Aug 2026, before GRAIN). Until then this gate proved
CLEAN only, which was enough while each new mode was a leaf hung off the
dispatch -- but GRAIN rolls machinery the other modes share (the PRNG, the
window, the shifted-output substitution), so PITCH and TAPE have to be
bit-compared too or a refactor can break them invisibly. Each mode case
builds BOTH engines with the same DMODE/DINT overrides and compares:

  * DMODE=1 PITCH, DINT=0 (+12) and DINT=3 (detune -- the one select where
    the two lines' steps differ, so it is the case that catches an L/R mixup)
  * DMODE=2 TAPE at WOW=100, and at WOW=127 FDBK=127 (deep wobble through
    the loop saturation, the two stage-4 mechanisms at once)
  * DMODE=3 GRAIN at SPRAY=0 (every grain reads the same place -- the
    degenerate, most easily-broken case) and SPRAY=127 (full scatter)
  * DMODE=4 REVERSE at its longest segment and at its shortest with TIME
    maxed (the case where the lag floor is clamped, i.e. the bound that
    keeps LAG0 + 2S inside the line)

and each is guarded by its OWN sensitivity control: the reference in that
mode must DIFFER from the reference in CLEAN. Without it a mode case passes
vacuously whenever the override silently fails to reach the engine, which is
exactly what the DMODE machinery exists to prevent (`$30000` census trap).

UNKNOWN MODE: the candidate is additionally built with DMODE=7 -- above every
implemented engine -- and must render identically to the reference: an unknown
MODE select must degrade to CLEAN, the trad delay, never to silence. (This was
DMODE=3 until GRAIN took mode 3, then 5 until REVERSE took 4; a fallback case
aimed at a mode that EXISTS proves nothing, so it moves up with the engines.)
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from remix import registry  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
import send_probe

SCRATCH = ROOT / "out" / "delayverify"
SR = 44100

# send_probe.DELAY_PARAMS order, which since the 18 Aug 2026 swap is:
#   0 TIME  1 FDBK  2 TONE  3 PING  4 -VRB  5 IN  6 DPTH  7 MODE  8 RATE
#   9 PTCH  10 DRV  11 FRZE
# ⚠️ Slot 6 is the KNOB field of r6+$c, NOT $b -- the old "$b/$c/$d/$e"
# reading is the exact error PARAM_PAGES.md names as why the delay's WOW
# worked locally and never on hardware. Odd slots (7/9/11) are companion
# fields; dsp_host drives them via -params too since 17 Aug 2026.
#
# ⚠️ The 90 was on index 4 until 30 Aug 2026, described as "MIX 90 so a render
# is audibly wet". After the swap index 4 is -VRB, so every run pinned the
# REVERB SEND to 90 and left the delay's own IN at 0. Harmless for the
# bit-compare (both sides got the same wrong knob) and wrong as a description
# of what was exercised -- the same shape as the SLOT fix below, which landed
# on 23 Aug and did not reach this line.
# v5.1: slot 5 is PTCH (IN retired). 0 here so a pre-v5 REFERENCE gets
# IN=0 and stays comparable; the GRAIN cases set PTCH explicitly.
BASE = [40, 60, 100, 64, 0, 0, 0, 0, 0, 0, 0, 0]

SLOT = {"TIME": 0, "FDBK": 1, "TONE": 2, "PING": 3, "VRB": 4, "PTCH": 5,
        "MDEP": 6, "MRAT": 8, "DRV": 10}
# v5.1 (3 Sep 2026): slot 5 is PTCH (IN retired), MDEP = wow depth / GRAIN
# scatter, MRAT = wow rate / GRAIN density, DRV = drive in every mode.
# ⚠️ MIX (= IN since v3) moved to slot 5 in the 18 Aug 2026 IN/-VRB swap;
# this map said 4 until 23 Aug, so the "MIX=0" case was actually pinning
# -VRB -- harmless for its bit-compare purpose (both sides got the same
# wrong knob), but wrong as documentation of what it exercised.


def dp(**kw):
    p = list(BASE)
    for k, v in kw.items():
        p[SLOT[k]] = v
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


def build(src, tag, dmode=None, dint=None):
    """Build the delay hatch with DLSRC=src, keep its payload-A dump, return
    (mem, delay_words, hatch_free). DFRZ/DINT are popped as well as DMODE:
    an override leaking in from the caller's environment would silently move
    BOTH sides of the comparison off the case this run means to prove."""
    env = dict(os.environ, DEV="1", XBUS="1", DLSRC=str(src))
    for k in ("SPEC", "BURN", "PROBE", "XPROBE", "DELAYPROBE", "MODE",
              "WIDTH", "DMODE", "DINT", "DFRZ", "NOSHIM"):
        env.pop(k, None)
    if dmode is not None:
        env["DMODE"] = str(dmode)
    if dint is not None:
        env["DINT"] = str(dint)
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


def mode_count(src):
    """How many engine SELECT POSITIONS a delay source carries, read from the
    mode fork's own markers. Counted from the alternative NUMBERS, not the
    marker count: TAPE's retirement (18 Aug 2026) left the alternatives
    numbered 1/3/4, and `1 + count` said 4 -- so REVERSE (DMODE=4) was
    SILENTLY SKIPPED by every run since, the harness-drift family again
    (caught 23 Aug when the v6 roll touched REVERSE and its cases skipped).
    A mode only ONE side carries cannot be bit-compared at all, so the
    caller still skips it loudly rather than failing a candidate for adding
    an engine."""
    ns = [int(n) for n in re.findall(r"; MODEFORK_MID -- alternative (\d+)", src)]
    return (max(ns) + 1) if ns else 1


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
    ap.add_argument("candidate", help="the engine under test, e.g. modules/bongdelay/delay_server2.asm")
    ap.add_argument("--ref", default=registry.asm("bongdelay"),
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
        # MIX=0 is the DRY PATH, and stage 5c turned MIX from an add into a
        # crossfade. At 0 the two are identical by construction, so this case
        # is what proves the change touched only the blend and nothing else
        # -- the cases above it are EXPECTED to differ across that commit.
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

    # ---- the OTHER ENGINES, each with its own sensitivity control ----------
    # CLEAN equality above says nothing about PITCH/TAPE/GRAIN, and every
    # stage from here on touches machinery they share. Both engines are built
    # with the SAME override so the comparison is of code, not of mode.
    cand_src = (ROOT / args.candidate).read_text()
    ref_src = (ROOT / args.ref).read_text()
    shared_modes = min(mode_count(cand_src), mode_count(ref_src))
    if "; DMODE_OVERRIDE" in cand_src:
        clean_ref = render(ref_mem, dp(), source=source)
        MODES = [
            # v5 numbering (3 Sep 2026): 1 = GRAIN, 2 = REVERSE; PITCH mode is
            # retired and its harmoniser lives in GRAIN's continuous pitch.
            # DINT drives the SIZE select (the PTCH slot until v5).
            ("GRAIN unison SPRAY=0 (every grain on the same read)", 1, 1, dp(MDEP=0, PTCH=64)),
            ("GRAIN unison SPRAY=127 (full scatter)", 1, 1, dp(MDEP=127, PTCH=64)),
            ("GRAIN +12 on PTCH, 23 ms grains", 1, 2, dp(MDEP=60, PTCH=96)),
            ("GRAIN -12 on PTCH, 186 ms grains (the distance clamp)", 1, 3,
             dp(MDEP=90, PTCH=32)),
            ("GRAIN sparse (MRAT 0) at 93 ms", 1, 1, dp(MDEP=64, MRAT=0, PTCH=64)),
            ("REVERSE size 4096 (93 ms, the line's ceiling)", 2, 1, dp()),
            ("REVERSE size 512 (stutter) at TIME=127", 2, 3, dp(TIME=127)),
        ]
        for label, dmode, dint, params in MODES:
            if dmode > shared_modes - 1:
                print(f"  [ -- ] {label}: DMODE={dmode} is not an engine BOTH "
                      f"sources carry -- nothing to bit-compare, case skipped")
                continue
            rm, _, _ = build(args.ref, f"ref_m{dmode}_{dint}", dmode, dint)
            cm, _, _ = build(args.candidate, f"cand_m{dmode}_{dint}", dmode, dint)
            a = render(rm, params, source=source)
            check(f"mode is LIVE: {label} differs from CLEAN",
                  a != clean_ref,
                  "" if a != clean_ref else
                  "  <-- the override never reached the engine; the case below "
                  "is VACUOUS")
            b = render(cm, params, source=source)
            detail = ""
            if a != b:
                fa, fb = a[0] + a[1], b[0] + b[1]
                n = sum(1 for x, y in zip(fa, fb) if x != y)
                first = next((i for i, (x, y) in enumerate(zip(fa, fb))
                              if x != y), -1)
                detail = f"  (first differing sample {first}, {n} of {len(fa)} differ)"
            check(f"bit-identical: {label}", a == b, detail)

        # ---- unknown MODE must fall back to CLEAN --------------------------
        # DMODE=5, not 3: 3 is GRAIN now, and a fallback case aimed at a mode
        # that EXISTS proves nothing. Keep this above the highest engine.
        dm_mem, _, _ = build(args.candidate, "cand_dmode5", dmode=5)
        d = render(dm_mem, dp(), source=source)
        check("DMODE=5 (nonexistent mode) degrades to CLEAN, bit-identical",
              d == clean_ref)
    else:
        print("  [ -- ] mode cases skipped: candidate has no "
              "; DMODE_OVERRIDE marker (a v1 source)")

    print(f"\n  DELAY SERVER {ref_words} -> {cand_words} words "
          f"({cand_words - ref_words:+d}); donor-region FREE {ref_free} -> "
          f"{cand_free} (the delay sits OUTSIDE it at DEV_DELAY_P since the "
          f"12 Aug placement change)")
    print("\nOK" if ok else "\nFAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
