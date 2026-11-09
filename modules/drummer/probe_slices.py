#!/usr/bin/env python3
"""DRUMMER phase 2, unknown 1: which slice does the stock FLEX voice start for a STRT lock?

    .venv/bin/python3 modules/drummer/probe_slices.py --sample DIR/NAME.wav [--image out/mainos_bus.bin]
        [--project <empty project dir>] [--tempo 240] [--frames 3000]

The sample and its slices come from the user's own files (NAME.wav + NAME.ot, the .ot the unit's
audio editor writes with FILE > SAVE SAMPLE SETTINGS); they are staged on a scratch card under out/
and never committed. An empty project made by the image itself (tools/hw/ot_fresh.py) gets:

  FLEX slot 1 = the sample, its markers record = the .ot's trim and slices;
  T1 FLEX on slot 1 in every Part, SETUP LOOP off, SLIC on, TSTR off;
  pattern A01 T1: a trig on steps 1..16, step s with a STRT lock (lock byte 1) from STRT_LOCKS.

The port plays it and every write to T1's voice record +32..+47 (0x800049d8: +32 slice, +33 STRT,
+40 start, +44 end) is logged; each trig's (slice, start, end) is compared with what the code read
in phase 1 predicts: slice = min(STRT >> 1, count - 1), start/end = that slice's bounds
(modules/drummer/INVESTIGATION.md).
"""
import argparse, pathlib, re, shutil, struct, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
from hw import ot_project as otp  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/drummer/slices"
SAMPLE_REL = "AUDIO/DRUMMER_TEST.wav"
VOICE = 0x800049d8                       # T1's voice record
SETUP_OFF, VALUES_OFF = 0x1e3, 0x033     # part-relative, + t*30 + 6*machine + slot
FLEX = 1
STRT = 1                                 # lock byte of PLAYBACK STRT
# step -> STRT lock: an unordered walk of the slices, odd values (2n+1 -> n), past the count
# (clamped to the last slice) and one step with no lock (the Part's STRT, 0 -> slice 0).
STRT_LOCKS = [10, 0, 6, 31, 2, 28, 127, 14, 9, 22, 4, 30, 40, None, 18, 26]


def read_ot(path):
    d = path.read_bytes()
    if d[:4] != b"FORM" or d[8:16] != b"DPS1SMPA":
        sys.exit(f"{path}: not a .ot file")
    slices = [struct.unpack(">III", d[0x3a + 12 * i:0x46 + 12 * i]) for i in range(64)]
    count, = struct.unpack(">I", d[0x33a:0x33e])
    return slices, count


def build_project(src, dest, wav_frames, slices, count, tempo, track=0):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() in (".work", ".strd"):
            shutil.copy2(f, dest / f.name)
    for suffix in ("work", "strd"):
        pw = dest / f"project.{suffix}"
        if not pw.is_file():
            continue
        raw = pw.read_bytes()
        raw = re.sub(rb"\[SAMPLE\]\r\nTYPE=FLEX\r\nSLOT=001\r\n.*?\[/SAMPLE\]\r\n\r\n", b"", raw, flags=re.S)
        block = ("[SAMPLE]\r\nTYPE=FLEX\r\nSLOT=001\r\nPATH=../" + SAMPLE_REL + "\r\n"
                 "TRIM_BARSx100=200\r\nLOOP_BARSx100=200\r\nBPMx24=2232\r\n"
                 "TSMODE=0\r\nLOOPMODE=0\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n"
                 "[/SAMPLE]\r\n\r\n").encode()
        at = raw.find(b"[SAMPLE]")
        if at < 0:
            raw = raw.rstrip(b"\r\n") + b"\r\n\r\n"
            at = len(raw)
        raw = raw[:at] + block + raw[at:]
        for key, val in ((rb"BANK", b"0"), (rb"PATTERN", b"0"), (rb"TRACK", b"0")):
            raw = re.sub(rb"\r\n" + key + rb"=\d+\r\n", b"\r\n" + key + b"=" + val + b"\r\n", raw, count=1)
        raw = raw.replace(b"MASTER_TRACK=1", b"MASTER_TRACK=0")
        pw.write_bytes(raw)
    otp.set_tempo(dest, tempo)
    rec = struct.pack(">III", 0, wav_frames, 0xffffffff)
    rec += b"".join(struct.pack(">III", *s) for s in slices) + struct.pack(">I", count)
    assert len(rec) == 784
    for suffix in ("work", "strd"):
        pm = dest / f"markers.{suffix}"
        if not pm.is_file():
            continue
        data = bytearray(pm.read_bytes())
        data[0x16:0x16 + 784] = rec                     # FLEX slot 1
        data[-2:] = (sum(data[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        pm.write_bytes(bytes(data))

    def mut(data):
        for p in range(otp.NPARTS_ALL):
            base = otp.PART_BASE + p * otp.PART_STRIDE
            data[base + otp.MTYPE_OFF + track] = FLEX
            data[base + 0x2d3 + 5 * track + FLEX] = 0    # the track: FLEX slot 1
            setup = base + SETUP_OFF + 30 * track + 6 * FLEX
            data[setup + 0] = 0                          # LOOP off
            data[setup + 1] = 1                          # SLIC on
            data[setup + 4] = 0                          # TSTR off
            values = base + VALUES_OFF + 30 * track + 6 * FLEX
            data[values + 0] = 64                        # PTCH
            data[values + 1] = 0                         # STRT
            data[values + 3] = 127                       # RATE
        off = otp.trac_off(0, track)
        for step, v in enumerate(STRT_LOCKS):
            data[off + 7 - step // 8] |= 1 << (step % 8)
            if v is not None:
                data[off + 0x59 + step * 32 + STRT] = v
    otp._bank_write(dest, 1, mut, guard=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True, help="NAME.wav, with NAME.ot beside it")
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--project", default="", help="an empty project (default: tools/hw/ot_fresh.py on --image)")
    ap.add_argument("--tempo", type=int, default=240)
    ap.add_argument("--frames", type=int, default=3000)
    ap.add_argument("--dsp", action="store_true", help="run both DSP cores too (slower; audio out)")
    a = ap.parse_args()
    wav = pathlib.Path(a.sample).expanduser().resolve()
    slices, count = read_ot(wav.with_suffix(".ot"))
    import wave
    with wave.open(str(wav)) as w:
        frames = w.getnframes()
    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "image.bin"
    shutil.copy2(a.image, image)
    src = pathlib.Path(a.project) if a.project else None
    if src is None:
        fresh = OUT / "fresh"
        r = subprocess.run([str(PY), str(ROOT / "tools/hw/ot_fresh.py"), "--image", str(image), "--out", str(fresh)],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"ot_fresh failed:\n{(r.stdout + r.stderr)[-1500:]}")
        src = next(p.parent for p in fresh.rglob("project.work"))
    proj = OUT / "project"
    build_project(src, proj, frames, slices, count, a.tempo)
    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "RIG",
                        "--tree", str(OUT / "tree"), "--out", str(card), "--audio", f"{wav}:{SAMPLE_REL}"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"stage_card failed:\n{(r.stdout + r.stderr)[-1500:]}")
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM", "--project", "RIG",
           "--sequencer", "--internal-clock", "--frames", str(a.frames), "--load-ms", "90000",
           "--main-level", "64", "--watch-mem", f"{VOICE + 32:#x},16"]
    if a.dsp:
        cmd += ["--dsp", "--audio-out", str(OUT / "port")]
    log = OUT / "port.txt"
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text()
    print(f"port exit {r.returncode}; log {log}")
    # one voice start = writes at 0x4000f67c (+32 slice), f67e (+33 STRT), f790 (+44 end), f794 (+40 start)
    starts, cur = [], {}
    for m in re.finditer(r"\[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|0) \(\d\) at pc (0x[0-9a-f]+)", text):
        addr, val, pc = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)
        key = {0x4000f67c: "slice", 0x4000f67e: "strt", 0x4000f790: "end", 0x4000f794: "start"}.get(pc)
        if key == "slice":
            cur = {}
        if key:
            cur[key] = val
        if key == "start":
            starts.append(cur)
    print(f"{len(starts)} voice starts on T1")
    expect = [(v if v is not None else 0) for v in STRT_LOCKS]
    # find the pattern's first pass: the run of starts whose STRT bytes follow the lock list
    first = next((i for i in range(len(starts) - 15)
                  if [s.get("strt") for s in starts[i:i + 16]] == expect), None)
    if first is None:
        print("FAIL: no 16 consecutive starts carry the 16 locked STRT values in order")
        for s in starts[:40]:
            print("   ", s)
        return 1
    fails = 0
    print(" step  STRT  slice want  start..end            want")
    for step, s in enumerate(starts[first:first + 16]):
        want = min(expect[step] >> 1, count - 1)
        ws, we = slices[want][0], slices[want][1]
        ok = s["slice"] == want and s["start"] == ws and s["end"] == we
        fails += not ok
        print(f"  {step + 1:2d}  {s['strt']:4d}  {s['slice']:4d} {want:4d}   {s['start']:6d}..{s['end']:6d}   "
              f"{ws:6d}..{we:6d}  {'PASS' if ok else 'FAIL'}")
    print(f"{16 - fails}/16 steps play the predicted slice and bounds")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
