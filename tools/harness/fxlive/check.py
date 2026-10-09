#!/usr/bin/env python3
"""fxlive's self-check: cf_host (its ColdFire stage) against Tape Echo's native oracle.

    make fxlive-check

tools/harness/fxlive/cf_host.cpp runs the stock delay routine 0x400031a0 one frame
per block from a built image and its DRAM runtime, staging the knobs through
stock's own producer copy and the tempo words as the frame code sets them.
This check streams 3,000 blocks with every Tape Echo control moving through
it, on T1 and on T5 (the track fxlive uses), and requires every output
sample to equal modules/tapeecho/cpu.c's, block for block -- the same
oracle verify_tapeecho_cpu.py holds the ColdFire kernels to. Then it checks
the stock DELAY's tempo sync in cf_host: a repeat at 60 BPM lands twice as
late as at 120.

It builds its own image of the `tapeecho` remix to out/fxlive/ (BUS_OUT,
so out/mainos_bus.bin is left alone) and copies that build's DRAM runtime
out of out/platform/ at once. It borrows State, Params and RING from
tools/verify/verify_tapeecho_cpu.py, Tape Echo's own verifier, so a change
to that struct shows up here as a failure.
"""
import ctypes as C
import json
import os
import pathlib
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
import verify_tapeecho_cpu as V  # noqa: E402  (State, Params, RING)

OUT = ROOT / "out/fxlive/check"
HOST = ROOT / "out/emu/ot_cf_host"
FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    FAILS += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""), flush=True)


def run(args, data=None):
    r = subprocess.run([str(a) for a in args], cwd=ROOT, input=data, capture_output=True)
    if r.returncode:
        raise SystemExit(f"{args[0]} exit {r.returncode}\n{r.stderr.decode(errors='replace')[-2000:]}")
    return r.stdout


def stream(image, runtime, fxid, track, knobs, x24, tempo=120):
    nb = len(knobs)
    pk = np.zeros((nb, 44), np.int32)
    pk[:, :12] = knobs
    pk[:, 12:] = x24.reshape(nb, 32)
    out = run([HOST, image, "--runtime", runtime[0], f"{runtime[1]:x}", "--fxid", fxid,
               "--track", track, "--tempo", tempo, "--stream"], pk.tobytes())
    return np.frombuffer(out, np.int32).reshape(nb, 33)[:, :32]


def tape_identity(lib, image, runtime, track):
    nb = 3000
    rng = np.random.default_rng(5)
    x24 = np.round(np.sin(np.arange(nb * 16) * 0.05)[:, None] * [0.3, 0.25] * 8388607).astype(np.int32)
    x24 += rng.integers(-2000, 2000, x24.shape, dtype=np.int32)
    knobs = np.zeros((nb, 12), np.int32)
    for b in range(nb):           # TIME FDBK WOW AGE SYNC MIX, all moving
        knobs[b, :6] = [(b // 8) % 128, (b // 7) % 128 if b > 1000 else 64, (b // 11) % 128,
                        (b // 9) % 128, (b // 400) % 2, (b // 13) % 128]
    cf = stream(image, runtime, "15", track, knobs, x24)
    st, p = V.State(), V.Params()
    ring = (C.c_int32 * (V.RING * 2))()
    audio, rec = (C.c_int32 * 32)(), (C.c_int32 * 32)()
    write, bad, first = 0, 0, None
    blocks = x24.reshape(nb, 32)
    for b in range(nb):
        t, fb, wow, age, sync, mix = (int(v) for v in knobs[b, :6])
        p.time, p.feedback, p.wow, p.sync, p.mix, p.age = t, fb, wow, sync, mix, age
        p.tempo, p.lane = 2880, track
        for i in range(32):
            audio[i] = int(blocks[b, i]) << 8
        lib.te_process(C.byref(st), C.byref(p), ring, write, audio, rec)
        for i in range(32):
            ring[2 * write + i] = rec[i]
        write = (write + 16) % V.RING
        if not np.array_equal(np.array(audio[:], np.int64) >> 8, cf[b]):
            bad += 1
            first = b if first is None else first
    check(f"TAPE ECHO on T{track + 1}: cf_host equals the native oracle", bad == 0,
          f"{nb} blocks, every control moving" + (f"; {bad} differ, first at block {first}" if bad else ""))


def delay_sync(image, runtime):
    # TAPE off: with it on, TIME glides from where the head starts and a
    # repeat soon after reset lands part way along the glide.
    nb, hit = 3200, 400 * 16
    x24 = np.zeros((nb * 16, 2), np.int32)
    x24[hit] = 0x400000
    knobs = np.tile(np.array([47, 0, 127, 0, 127, 127, 0, 0, 127, 1, 0, 0], np.int32), (nb, 1))
    at = {}
    for bpm in (120, 60):
        y = stream(image, runtime, "08", 4, knobs, x24, bpm).reshape(-1, 2)
        late = np.flatnonzero(np.abs(y[hit + 64:, 0]) > 0x100000)
        at[bpm] = int(late[0]) + 64 if len(late) else None
    ok = at[120] is not None and at[60] is not None and abs(at[60] - 2 * at[120]) <= 64
    check("stock DELAY, SYNC on: the 60 BPM repeat lands twice as late as the 120 BPM one",
          ok, f"{at[120]} and {at[60]} samples")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not (ROOT / "out/emu/CMakeCache.txt").is_file():
        raise SystemExit("fxlive check: the port is not configured here: make emu-cf")
    run(["cmake", "--build", "out/emu", "--target", "ot_cf_host", "-j8"])
    image = OUT / "tapeecho.bin"
    b = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT,
                       env=dict(os.environ, REMIX="tapeecho", XBUS="1", SPEC="1", BUS_OUT=str(image)),
                       capture_output=True, text=True)
    if b.returncode or "platform runtime:" not in b.stdout:
        raise SystemExit(f"fxlive check: the tapeecho build failed\n{(b.stdout + b.stderr)[-2000:]}")
    raw = OUT / "tapeecho.runtime.raw"
    raw.write_bytes((ROOT / "out/platform/runtime.raw").read_bytes())
    runtime = (raw, json.loads((ROOT / "out/platform/layout.json").read_text())["base"])
    lib_path = OUT / "te_native.so"
    run(["cc", "-shared", "-fPIC", "-O2", "-fwrapv", "-DTE_HOST=1", "modules/tapeecho/cpu.c",
         "-o", lib_path])
    lib = C.CDLL(str(lib_path))
    lib.te_process.argtypes = [C.POINTER(V.State), C.POINTER(V.Params), C.POINTER(C.c_int32),
                               C.c_uint32, C.POINTER(C.c_int32), C.POINTER(C.c_int32)]
    for track in (0, 4):
        tape_identity(lib, image, runtime, track)
    delay_sync(image, runtime)
    print(f"\n{FAILS} failure(s)" if FAILS else "\nOK: fxlive's cf_host runs the ColdFire routine as the oracle does")
    return int(bool(FAILS))


if __name__ == "__main__":
    sys.exit(main())
