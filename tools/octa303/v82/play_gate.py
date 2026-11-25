#!/usr/bin/env python3
"""OCTA303 v8.2: the 'plays many steps' gate (10 Nov 2026, after the v8.1 images froze the sequencer on Marko's MK1).

    python3 tools/octa303/v82/play_gate.py IMAGE [--project DIR] [--frames N]

A copy of a project (OT_PROJECT, or ~/.octabam_project; the source is not modified) where, in every bank and every part,
T5 and T6 are OCTA-303 (FLEX signed T B 1) and, in every pattern, T1 plays steps 1 5 9 13 and T5/T6 play all 16 steps
with PLAYBACK locks CUT/RES/ENV/ACC 127, at 300 BPM.  The image boots under the port (out/emu/ot_emu), loads it, plays
N frames (default 3000 = 1.09 s = ~21 steps) and the sequencer's step word (0x800065b2) is watched.

PASS when: the load completed; the step word advanced at least (expected - 2) times, wrapped from 16 back to 0 at least
once, and no step took more than 1.5 x the 300 BPM step; no ILLEGAL in the port's log.  It prints the ColdFire
instructions per 16-sample frame, and the share of them inside OCTA303's code (o3_* / sy_*), for comparing images.

What it cannot see (TRAPS.md, trap-blind-instrument): the port counts instructions, not the chip's cycles (no cache, no
EMAC stalls), and it runs a frame when the work is done: a CPU overload on the unit does not show here.  The
instructions per frame are the comparison it offers; the unit's LOAD is the measurement.
Written by Claude (Anthropic).
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/harness")); sys.path.insert(0, str(ROOT / "tools/hw"))
from ab_fixture import prepare  # noqa: E402
import ot_project as otp  # noqa: E402

O3 = (4, 5)
BPM_X24 = 7200                      # 300 BPM
STEP_SAMPLES = 44100 * 60 / 300 / 4  # 2205 samples a 16th
FAILS = []


def check(what, ok, info=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {what}" + (f"  {info}" if info else ""), flush=True)
    if not ok:
        FAILS.append(what)


def fixture(src, out):
    d = prepare(src, out / "RIG")
    for path in sorted(d.glob("bank*.work")):
        def mutate(data):
            for part in range(8):
                base = otp.PART_BASE + part * otp.PART_STRIDE + 9
                for t in O3:
                    data[base + 0x22 + t] = 1
                    data[base + 60 + 30 * t:base + 63 + 30 * t] = b"TB\x01"
        otp._bank_write(d, int(path.stem[4:]), mutate, guard=False)
    locks = {str(s): {"S1": 127, "S2": 127, "S3": 127, "S5": 127} for s in range(1, 17)}
    spec = {"banks": "all", "patterns": {"all": {"tracks": {
        "1": {"trigs": [1, 5, 9, 13]},
        "5": {"trigs": list(range(1, 17)), "locks": {"playback": locks}},
        "6": {"trigs": list(range(1, 17)), "locks": {"playback": locks}}}}}}
    (out / "spec.json").write_text(json.dumps(spec))
    subprocess.run([sys.executable, str(ROOT / "tools/hw/ot_spec.py"), "apply", str(d), str(out / "spec.json")],
                   check=True, stdout=subprocess.DEVNULL)
    for p in d.glob("project.*"):
        raw = p.read_bytes()
        raw, n = re.subn(rb"(?m)^TEMPOx24=[^\r\n]*", b"TEMPOx24=" + str(BPM_X24).encode(), raw)
        assert n, f"{p.name}: no TEMPOx24"
        p.write_bytes(raw)
    card = out / "card.img"
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(d), "OCTABAM", "RIG",
                    "--tree", str(out / "tree"), "--out", str(card)], check=True, stdout=subprocess.DEVNULL)
    return card


def o3_range(elf):
    nm = shutil.which("m68k-elf-nm") or "m68k-elf-nm"
    syms = [l.split() for l in subprocess.check_output([nm, "-n", str(elf)], text=True).splitlines()]
    a = [int(s[0], 16) for s in syms if len(s) == 3 and s[1] in "tT" and (s[2].startswith("o3_") or s[2].startswith("sy_"))]
    return min(a), max(a)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("image")
    dot = pathlib.Path.home() / ".octabam_project"
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT") or (dot.read_text().strip() if dot.exists() else None))
    ap.add_argument("--frames", type=int, default=3000)
    ap.add_argument("--out", default=str(ROOT / "out/octa303/play-gate"))
    ap.add_argument("--elf", default=str(ROOT / "out/platform/runtime/runtime.elf"))
    a = ap.parse_args()
    if not a.project:
        print("[SKIP] play gate: no project (OT_PROJECT or ~/.octabam_project)"); return 0
    emu = ROOT / "out/emu/ot_emu"
    if not emu.exists():
        print(f"[SKIP] play gate: no port at {emu} (make emu-cf)"); return 0
    out = pathlib.Path(a.out); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    card = fixture(a.project, out)
    cmd = [str(emu), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "RIG", "--sequencer",
           "--internal-clock", "--frames", str(a.frames), "--load-ms", "90000", "--dsp", "--main-level", "64",
           "--watch-mem", "0x800065b0,4", "--coverage", str(out / "cov.txt")]
    with (out / "port.log").open("w") as log:
        r = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
    log = (out / "port.log").read_text()
    print(f"play gate: {a.image}, {a.frames} frames at 300 BPM, T5/T6 OCTA-303 every step, CUT/RES/ENV/ACC 127")
    check("the port ran to the end", r.returncode == 0 and "run ended REACHED" in log, f"exit {r.returncode}")
    check("the project loaded", "LOAD PROJECT handled" in log)
    check("no illegal instruction", "ILLEGAL" not in log)
    steps = [(float(m.group(1)), int(m.group(2), 0)) for m in
             re.finditer(r"\[\s*([0-9.]+)\] \[0x800065b2\] <- (0x[0-9a-f]+|\d+)", log)]
    adv = [s for s in steps if s[1] != 0]
    expect = int(a.frames * 16 / STEP_SAMPLES)
    check(f"the sequencer advanced (at least {expect - 2} steps)", len(adv) >= expect - 2, f"{len(adv)} steps")
    check("it wrapped from step 16 back to 1", any(p[1] == 16 and q[1] == 0 for p, q in zip(steps, steps[1:])))
    gaps = [q[0] - p[0] for p, q in zip(adv, adv[1:]) if q[1] == p[1] + 1]   # the watch's stamp is in samples
    worst = max(gaps) if gaps else 0
    check("no step later than 1.5 x the step", gaps and worst <= 1.5 * STEP_SAMPLES, f"worst {worst:.0f} samples (step {STEP_SAMPLES:.0f})")
    m = re.search(r"\((\d+) per frame of 16 samples\)", log)
    if m and pathlib.Path(a.elf).exists():
        lo, hi = o3_range(a.elf)
        tot = o3 = 0
        for line in (out / "cov.txt").read_text().splitlines():
            pc, n = line.split(); pc, n = int(pc, 16), int(n)
            tot += n; o3 += n if lo <= pc <= hi + 0x2000 else 0
        print(f"  ColdFire instructions per frame: {m.group(1)}; inside OCTA303 {100.0 * o3 / max(tot, 1):.1f} %"
              f" ({int(m.group(1)) * o3 // max(tot, 1)} a frame, two voices)")
    print("play gate: " + ("PASS" if not FAILS else f"{len(FAILS)} FAILED"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
