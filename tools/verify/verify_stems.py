#!/usr/bin/env python3
"""STEM REC -- the row, the tap and the file, checked without hardware.

    python3 tools/verify/verify_stems.py [remix]      (default: stems)

Static, from the built image: CONTROL has seven rows, the six stock ones
byte for byte, the seventh labelled STEM REC with the module's action and
id 0; the frame site jumps to the hook; the ring and the stack sit at the
top of the platform reserve, above the runtime's stage. Then, when the
port is built and the fixture exists (tools/verify/stems_fixture.py), the
runs of Tasks 14 to 16.
"""
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, "tools/scratch")   # blockdump.py lives here (t1_frames, below)
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
RUNTIME_ELF = pathlib.Path("out/platform/runtime/runtime.elf")
LAYOUT_DIR = pathlib.Path("out/platform")      # platform_build.LAYOUT lives here, by name
CONTROL_DESC, CONTROL_ROWS, ROW_LEN, STOCK_N = 0x400cbd54, 0x400cc5a8, 24, 6
FRAME_SITE = 0x40004b12

# Task 11's interface (STEM_REC.md section 9.4): T1's slot in the read-back
# half, and the direction char blockdump.py's summary prints for that class.
READBACK_DIR = "<"
T1_OFFSET = 0x100

EMU = pathlib.Path("out/emu/ot_emu")
FIXTURE = pathlib.Path("out/stems_fixture.json")   # written by tools/verify/stems_fixture.py
KEY_STOP = 0x4000a1e0
STOP_GATE = 0x80000029     # the STOP handler returns early while this byte is 0 (STEM_REC.md 1.6)
PRE_ROLL = 40              # frames before the transport start; the dump includes them
ST_IDLE, ST_ARMED, ST_RECORDING, ST_FINISHING = 0, 1, 2, 3   # stems.s

fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def syms():
    out = subprocess.run(["m68k-elf-nm", str(RUNTIME_ELF)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def rd32(img, a):
    return int.from_bytes(img[a - BASE:a - BASE + 4], "big")


def static(img, stock, s):
    check("CONTROL count is 7", rd32(img, CONTROL_DESC) == 7, f"{rd32(img, CONTROL_DESC)}")
    rows = rd32(img, CONTROL_DESC + 0x18)
    check("CONTROL rows moved", rows != CONTROL_ROWS, f"0x{rows:08x}")
    a, b = rows - BASE, CONTROL_ROWS - BASE
    check("the six stock rows came across byte for byte",
          img[a:a + ROW_LEN * STOCK_N] == stock[b:b + ROW_LEN * STOCK_N])
    r7 = [rd32(img, rows + ROW_LEN * STOCK_N + 4 * k) for k in range(6)]
    check("row 7 label is stems_label", r7[0] == s["stems_label"], f"0x{r7[0]:08x}")
    check("row 7 action is stems_action", r7[2] == s["stems_action"], f"0x{r7[2]:08x}")
    check("row 7 window, pad, child and id are 0", r7[1] == r7[3] == r7[4] == r7[5] == 0, f"{r7}")
    want = b"\x4e\xb9" + s["stems_frame_hook"].to_bytes(4, "big") + b"\x4e\x71"
    got = img[FRAME_SITE - BASE:FRAME_SITE - BASE + 8]
    check("0x40004b12 is jsr stems_frame_hook; nop", got == want, got.hex())


def regions(s):
    from remix import platform_build
    lay = json.loads((LAYOUT_DIR / platform_build.LAYOUT).read_text())
    ring, stack = s["stems_ring"], s["stems_stack"]
    check("ring is 4 MiB ending at the reserve ceiling", ring + 0x400000 == lay["ceiling"],
          f"0x{ring:08x} + 4 MiB vs ceiling 0x{lay['ceiling']:08x}")
    check("stack sits just below the ring", stack + 0x2000 <= ring, f"0x{stack:08x}")
    check("the runtime's stage ends below the stack", lay["stage_end"] <= stack,
          f"stage end 0x{lay['stage_end']:08x}")


def t1_frames(dump_path):
    """T1's 16-bit stereo frames from a --block-dump, in frame order: the even
    words of T1's 64-word block in each read-back. One entry per frame, each
    32 signed samples, L R L R ..."""
    import blockdump
    out = []
    for d, frame, ch, core, ram, w in blockdump.read(dump_path):
        if ram in (0x80003190, 0x80003590) and d == READBACK_DIR:
            base = T1_OFFSET // 2
            out.append((frame, [x - 65536 if x >= 32768 else x for x in w[base:base + 64:2]]))
    return [s for _, s in sorted(out)]


def port(s, frames, stop_at=None, extra=(), tag="run", ring_bytes=0, calls=(), pokes=()):
    """One fixture run under the port: the module's action called before
    play (`--call-before-play`: the action arms, and the hook takes the
    ARMED-to-RECORDING edge on the first playing frame), STOP at `stop_at`
    (None = no STOP), any further `calls` as (frame, addr), any `pokes` as
    (addr, byte) applied after the load. A run that calls STOP also sets
    STOP_GATE to 1: the port starts the transport without the PLAY key, and
    on the fixture's project that leaves the STOP handler's gate shut, so
    the call would do nothing (Task 10). Dumps the six state words and, when
    `ring_bytes`, the start of the ring. Returns (log text, dump, card,
    state words, ring bytes).

    `--call-before-play` beside `--pre-roll` needs the port fixed on 13 Sep
    2026 (`main.cpp` runs to main's spin before the call; STEM_REC.md 10.1).
    An older port refuses the call, prints the refusal and records nothing,
    so `tap()` checks the call's own report line before anything else."""
    fx = json.loads(FIXTURE.read_text())
    work = pathlib.Path("out/stems_runs"); work.mkdir(parents=True, exist_ok=True)
    dump, card = work / f"{tag}.dump", work / f"{tag}.img"
    mem, ring = work / f"{tag}.mem", work / f"{tag}.ring"
    dumps = f"0x{s['stems_state']:x},24={mem}"
    if ring_bytes:
        dumps += f";0x{s['stems_ring']:x},{ring_bytes}={ring}"
    at = [f"{f}:0x{a:x}:0" for f, a in calls]
    pk = list(pokes)
    if stop_at is not None:
        at.append(f"{stop_at}:0x{KEY_STOP:x}:0")
        pk.append((STOP_GATE, 1))
    args = [str(EMU), "--image", str(IMAGE), "--card", fx["card"], "--set", fx["set"],
            "--project", fx["project"], "--sequencer", "--internal-clock",
            "--frames", str(frames), "--load-ms", "20000", "--dsp", "--main-level", "64",
            "--pre-roll", str(PRE_ROLL), "--poke-trig", "2", "--block-dump", str(dump),
            "--call-before-play", f"0x{s['stems_action']:x}:0",
            "--card-out", str(card), "--mem-dump", dumps, *extra]
    if at:
        args += ["--at", ",".join(at)]
    if pk:
        args += ["--poke", ";".join(f"0x{a:x}={b}" for a, b in pk)]
    r = subprocess.run(args, capture_output=True, text=True)
    m = mem.read_bytes() if mem.exists() else b"\0" * 24
    words = [int.from_bytes(m[i:i + 4], "big") for i in range(0, 24, 4)]
    return (r.stdout + r.stderr, dump, card, words,
            ring.read_bytes() if ring_bytes and ring.exists() else b"")


def tap(s):
    log, dump, _, words, raw = port(s, 400, stop_at=300, tag="tap", ring_bytes=64 * 400)
    st, status, _, wr, rd, nfr = words
    armed = [l for l in log.splitlines() if l.startswith("call") and "before play" in l]
    check("the action was called before play", any("-> returned" in l for l in armed),
          armed[0].strip() if armed else "no call line in the port's report")
    check("the hook recorded frames", nfr > 200, f"{nfr} frames, wr {wr}")
    # Every check below needs frames: with none, "equal at a fixed lag" and
    # "64 bytes per frame" are true of an empty ring, which is how the first
    # RED run of this task passed three of them.
    check("wr is 64 bytes per frame", nfr > 0 and wr == 64 * nfr, f"{wr} vs {64 * nfr}")
    check("the stop moved RECORDING on", nfr > 0 and st in (ST_IDLE, ST_FINISHING),
          f"state {st}, status {status}")
    got = [[int.from_bytes(raw[f * 64 + 2 * k:f * 64 + 2 * k + 2], "big", signed=True)
            for k in range(32)] for f in range(nfr)]
    want = t1_frames(dump)
    lag = next((L for L in range(len(want) - nfr + 1) if want[L:L + nfr] == got), None)
    check("every ring frame equals T1's read-back at one fixed lag", nfr > 0 and lag is not None,
          f"lag {lag} frames (pre-roll {PRE_ROLL})" if lag is not None
          else f"no lag 0..{len(want) - nfr} matches")
    loud = any(any(x) for x in got)
    check("the signal is not silence", loud,
          "non-zero samples present" if loud else f"all {nfr} ring frames are zero")


def main():
    from remix import registry
    name = sys.argv[1] if len(sys.argv) > 1 else "stems"
    if "STEM REC" not in registry.remix(name).modules:
        print(f"  [ -- ] {name} does not carry STEM REC -- nothing to check")
        return 0
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], capture_output=True, text=True, env=env)
    if r.returncode:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    img, stock, s = IMAGE.read_bytes(), STOCK.read_bytes(), syms()
    static(img, stock, s)
    regions(s)
    if EMU.exists() and FIXTURE.exists():
        tap(s)
    else:
        print("  [SKIP] port runs: build the port (make emu-cf) and the fixture "
              "(python3 tools/verify/stems_fixture.py)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
