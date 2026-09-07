#!/usr/bin/env python3
"""Gate for the two-core harness and for PAYLOAD B's placement.

Until 7 Sep 2026 payload B -- the shipping image's half that carries BusDelay
and serves tracks 1-4 -- had never run anywhere but on the unit. dsp_host now
boots both payloads with the shared window Y/X:0x30000-0x3FFFF really shared,
and this gate pins two things at once:

  1. THE HARNESS: a render with the servers on their REAL cores (SEND and
     BusDelay on payload B, BusVerb on payload A, the delay's wet crossing the
     core boundary) must be BIT-IDENTICAL to the same layout on one core
     through the DEV hatch. The bus arithmetic is core-agnostic under
     lock-step, so any difference is a harness defect (a window not shared, a
     context address wrong, a buffer misplaced).

  2. THE IMAGE: payload B's copy of the delay is assembled with its own base
     literal substituted ($30000 -> $38000, docs/BUS.md) and placed by the
     SPEC build. Identity with the DEV copy proves that substitution and
     that placement produce the same audio, which until now was checked
     statically only.

Plus the fuzz: the same two-core layouts under several -skew interleavings
must still match. That is NOT a proof of the cross-core race fix (the
interleave is a guess at the hardware's timing, and the four-buffer rotation
is designed to survive any single-block skew), but a mismatch there is a
real defect, and no local test could show one before.

    make verify-twocore          # ~1 min; part of `make check`

Both builds are of the `bus` remix: SPEC (the shipping shape) and DEV (the
hatch). The shipping artifact is snapshotted and restored, the way
verify_busscreen does, so `make check`'s remix is what is left on disk.
"""
import filecmp
import os
import pathlib
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import send_probe  # noqa: E402

OUT = ROOT / "out/dsp"
SCRATCH = OUT / "_twocore"
IMAGE = ROOT / "out/mainos_bus.bin"
DEV_MEM = OUT / "mem_dev_A.mem"
BLOCKS = 700
SKEWS = (1, 37, 333, -250)

R = [64, 30, 100, 0, 127, 0, 2, 0, 64, 0, 0, 1]          # manifest defaults
D = [40, 60, 100, 127, 127, 64, 0, 48, 64, 1, 0, 0]      # -VRB 127: wet on into the reverb
S_DEL = [127, 0] + [0] * 10
S_VRB = [0, 127] + [0] * 10

# layout: list of (letter, core, params); instance order is dispatch order
CASES = {
    "RS   send on B -> reverb on A":            [("R", 0, R), ("S", 1, S_VRB)],
    "DS   send on B -> delay on B":             [("R", 0, R), ("D", 1, D), ("S", 1, S_DEL)],
    "RDS  delay on B -> reverb on A (series)":  [("R", 0, R), ("D", 1, D), ("S", 1, S_DEL)],
    "SSSR two senders per core":                [("R", 0, R), ("S", 0, S_VRB), ("S", 1, S_VRB), ("S", 1, S_VRB)],
}
# which instance's stream each case compares (the server being measured)
PICK = {"RS": 0, "DS": 1, "RDS": 0, "SSSR": 0}


def build(env, log):
    r = subprocess.run([sys.executable, "tools/build_bus.py"], cwd=ROOT,
                       env={**os.environ, "REMIX": "bus", **env}, capture_output=True, text=True)
    log.write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        sys.exit(f"build failed ({env}): see {log}")


def impulse(path, blocks):
    pad = send_probe.WARMUP_BLOCKS * send_probe.FRAMES
    with open(path, "wb") as f:
        for i in range(blocks * send_probe.FRAMES):
            f.write(struct.pack("<i", 0x400000 if i == pad else 0))


def run(mems, layout, out, skew=None):
    """mems: {core: path}. Instances get per-core positions."""
    ep = {}
    for c, m in mems.items():
        ep[c] = {L: send_probe.entry_points(m, send_probe.SERVER_ID[L]) for L in "RDS"}
        if ep[c]["D"] == ep[c]["S"] and any(L == "D" and core == c for L, core, _ in layout):
            sys.exit(f"payload for core {c} ({m.name}) has no real delay -- wrong build")
    pos = {}
    cmd = [str(send_probe.HOST), "-mem", str(mems[0])]
    if 1 in mems:
        cmd += ["-memB", str(mems[1])]
    cores, allocs, r7s, inits, procs, inmask = [], [], [], [], [], 0
    for k, (L, c, _) in enumerate(layout):
        p = pos.get(c, 0); pos[c] = p + 1
        cores.append(str(c)); allocs.append(str(1 + 2 * p)); r7s.append(str(2 + 2 * p))
        inits.append(f"{ep[c][L][0]:x}"); procs.append(f"{ep[c][L][1]:x}")
        if L == "S":
            inmask |= 1 << k
    cmd += ["-init", ",".join(inits), "-proc", ",".join(procs), "-inst", str(len(layout)),
            "-core", ",".join(cores), "-alloc", ",".join(allocs), "-r7", ",".join(r7s),
            "-inmask", str(inmask), "-frames", str(send_probe.FRAMES), "-blocks", str(BLOCKS),
            "-in", str(SCRATCH / "imp.raw"), "-out", str(out)]
    for _, _, pv in layout:
        cmd += ["-params", ",".join(map(str, pv))]
    if skew is not None:
        cmd += ["-skew", str(skew)]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed:\n{r.stdout[-2000:]}{r.stderr[-1000:]}")
    return r.stdout


def stream(out, k):
    return out if k == 0 else pathlib.Path(f"{out}.i{k}")


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    snap = SCRATCH / "mainos_bus.snapshot.bin"
    had = IMAGE.is_file()
    if had:
        shutil.copy2(IMAGE, snap)
    try:
        build({"XBUS": "1", "SPEC": "1"}, SCRATCH / "build_spec.log")
        specA = send_probe.dump_mem(IMAGE, SCRATCH / "spec_A.mem", "A")
        specB = send_probe.dump_mem(IMAGE, SCRATCH / "spec_B.mem", "B")
        build({"XBUS": "1", "DEV": "1"}, SCRATCH / "build_dev.log")
        if not DEV_MEM.is_file():
            sys.exit(f"DEV build left no {DEV_MEM}")
    finally:
        if had:
            shutil.copy2(snap, IMAGE)
    impulse(SCRATCH / "imp.raw", BLOCKS)

    fails = 0
    print(f"two-core gate: {len(CASES)} layouts, SPEC two-core vs DEV one-core, then skews {SKEWS}")
    for name, layout in CASES.items():
        key = name.split()[0]
        k = PICK[key]
        two = run({0: specA, 1: specB}, layout, SCRATCH / f"{key}_two.raw")
        one = run({0: DEV_MEM}, [(L, 0, pv) for L, _, pv in layout], SCRATCH / f"{key}_one.raw")
        a, b = stream(SCRATCH / f"{key}_two.raw", k), stream(SCRATCH / f"{key}_one.raw", k)
        nz = [l for l in two.splitlines() if f"instance {k}:" in l and "non-zero" in l]
        silent = nz and nz[0].split()[2] == "0"
        same = filecmp.cmp(a, b, shallow=False)
        ok = same and not silent
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name:42s} "
              f"{'silent!' if silent else ('identical' if same else 'DIFFERS')}")
        if not same and not silent:
            continue
        for sk in SKEWS:
            run({0: specA, 1: specB}, layout, SCRATCH / f"{key}_sk.raw", skew=sk)
            s = filecmp.cmp(stream(SCRATCH / f"{key}_sk.raw", k), a, shallow=False)
            fails += not s
            print(f"       {'ok  ' if s else 'FAIL'} skew {sk:5d} {'identical' if s else 'DIFFERS'}")
    if fails:
        sys.exit(f"two-core gate: {fails} FAILURE(S)")
    print("two-core gate: every layout bit-identical across cores and under every skew.")
    print("  ⚠️  Identity under skew is not proof of the race fix -- the interleave is a")
    print("     guess at the hardware's timing. A mismatch here would be a real defect.")


if __name__ == "__main__":
    main()
