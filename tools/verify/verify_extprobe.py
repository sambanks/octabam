#!/usr/bin/env python3
"""EXTPROBE under dsp_host: it fills the slot's view with a pattern and counts what differs, and the decoder reads it.

    python3 tools/verify/verify_extprobe.py

SCAN over a region seeded with the pattern except six words: the highest offset, the total and the 1,024-word buckets
are exact. FILL over an empty (zero) region: after the fill pass the scan finds nothing, so the fill reached every
word (a failed fill leaves 15,779 words differing). OFF touches nothing. dsp_host does not alias Y onto X, so what
this proves is the instrument and its decoder, not a reverb's writes (that is the unit's job).
"""
import pathlib
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "modules/extprobe"))
import decode  # noqa: E402
import send_probe  # noqa: E402
from remix import registry  # noqa: E402

MOD = registry.by_name("extprobe")
MEM = "out/dsp/_audition_extprobe_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FRAMES, BLOCKS = 16, 520
TMP = pathlib.Path("out/_extprobe")
TMP.mkdir(parents=True, exist_ok=True)
BASE, N, PATTERN = 0x34000, 0x3DA3, 0xA5A5A5
fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


pathlib.Path(MEM).unlink(missing_ok=True)
subprocess.run([sys.executable, "tools/remix/audition.py", "extprobe", "out/dry/drums_110.wav"], capture_output=True)
if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM}: python3 tools/remix/audition.py extprobe out/dry/drums_110.wav")
init, proc = send_probe.entry_points(MEM, MOD.menu.fx2_id)
(TMP / "in.raw").write_bytes(b"\0" * (4 * 2 * FRAMES * BLOCKS))


def seeded(path, words):
    """The audition dump plus an X record at BASE: PATTERN everywhere in the region except `words` {offset: value}."""
    blob = pathlib.Path(MEM).read_bytes()
    end = blob.rindex(b"\xff")
    region = [words.get(i, PATTERN) for i in range(N)]
    rec = struct.pack("<BII", 1, BASE, N) + b"".join(struct.pack("<I", w) for w in region)
    pathlib.Path(path).write_bytes(blob[:end] + rec + blob[end:])


def run(mem, go, tag):
    out = TMP / f"{tag}.raw"
    r = subprocess.run([HOST, "-mem", str(mem), "-init", f"{init:x}", "-proc", f"{proc:x}", "-inst", "1", "-r7", "1",
                        "-alloc", "0", "-inmask", "1", "-frames", str(FRAMES), "-blocks", str(BLOCKS), "-in",
                        str(TMP / "in.raw"), "-out", str(out), "-params", f"{go}," + ",".join(["0"] * 11)],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"dsp_host failed ({tag}):\n{r.stdout[-600:]}\n{r.stderr[-600:]}")
    d = out.read_bytes()
    v = struct.unpack(f"<{len(d) // 4}i", d)
    ph, frames = decode.decode_frames(list(v[0::2]), list(v[1::2]))
    return decode.last_cycle(frames)


diffs = {5: 0, 100: 1, 0x7FF: 0x123456, 0x1000: 0, 0x37FF: 0x7FFFFF, 0x3DA2: 0x800001}
seeded(TMP / "seeded.mem", diffs)
c = run(TMP / "seeded.mem", 2, "scan")
check("SCAN: a complete cycle", c is not None)
if c:
    check("SCAN: state scanning, at least one full pass", c[1] == 2 and c[4] >= 1, f"state {c[1]}, passes {c[4]}")
    check("SCAN: the highest differing offset is 0x3da2", c[5] == 0x3DA2, f"{c[5]:#x}")
    check("SCAN: six words differ in a pass", c[6] == 6, f"{c[6]}")
    want = [0] * 16
    for off in diffs:
        want[off >> 10] += 1
    check("SCAN: the buckets", [c[7 + b] for b in range(16)] == want, f"{[c[7 + b] for b in range(16)]} want {want}")

pathlib.Path(TMP / "empty.mem").write_bytes(pathlib.Path(MEM).read_bytes())
c = run(TMP / "empty.mem", 1, "fill")
check("FILL: a complete cycle", c is not None)
if c:
    check("FILL: scanning after the fill, a pass done", c[1] == 2 and c[4] >= 1, f"state {c[1]}, passes {c[4]}")
    check("FILL: the scan finds nothing that differs", c[6] == 0 and c[5] == 0, f"total {c[6]}, highest {c[5]:#x}")

c = run(TMP / "seeded.mem", 0, "off")
check("OFF: state off, no pass, nothing counted", c is not None and c[1] == 0 and c[4] == 0 and c[6] == 0)
print("PASS" if not fails else f"{fails} FAIL")
sys.exit(1 if fails else 0)
