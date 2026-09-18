#!/usr/bin/env python3
"""REPITCH gates: the hooks, the panel, and a loop that must follow the
project tempo by speed, live.

    python3 tools/verify/verify_repitch.py [REMIX] [--project <dir>] [--case NAME]
        [--tempo 120] [--to 90] [--at 2000] [--frames 5000] [--adhoc flex,4,2,64[,127]]
    make check REMIX=repitch        # from make verify; OT_PROJECT adds playback

1. hooks     out/emu/ot_repitch_stock_test on the stock and the built image
             (tools/harness/repitch_probe.cpp)
2. panel     tools/verify/verify_repitch_ui.py under the .venv
3. playback  with a project: a copy gets one sample on T1 (slot 1, a
             generated two-second 440 Hz stereo loop whose attributes say
             120 BPM, trim markers over the whole file), T1 on the case's
             machine with LOOP on, the case's SETUP TSTR and PTCH, the
             sample's TSMODE, a trig on A01 step 1 and the given tempo. The
             port boots the image, loads the card, plays, calls the
             firmware's own tempo setter (0x4009c7c4) at a frame, and writes
             both cores' output. Before and after the change it measures
             the loop's PITCH (interpolated rising zero crossings, median
             period) and its SPEED: how fast the renderer moves the track's
             sample position (voice +68, every write watched), in source
             frames per output sample. The pitch alone cannot tell REPITCH
             from a timestretch: image 80 played 330 Hz with the position
             still advancing at 1.0, skipping a quarter of every chunk
             (docs/remixer/FAILURE_MODES.md). The renderer's resolved TSTR
             (voice +24) must read OFF on a REPITCH track.

Playback cases (a live change 120 -> 90 BPM; R = 0.75):
                pitch x440   speed      resolved
  stock-off     1 -> 1       1 -> 1     0    FLEX, TSTR OFF
  stretch       1 -> 1       1 -> R     2    FLEX, TSTR NORM: the control, a real timestretch
  repitch       1 -> R       1 -> R     0    FLEX, TSTR REPITCH
  auto          1 -> R       1 -> R     0    FLEX, TSTR AUTO, the sample's TIMESTRETCH = REPITCH
  ptch          1 -> R       1 -> R     0    FLEX, TSTR REPITCH, PTCH +24 (ignored)
  static        1 -> R       1 -> R     0    STATIC, TSTR REPITCH
  reverse       1 -> R      -1 -> -R    0    FLEX, TSTR REPITCH, RATE full reverse

Each part SKIPs on what it lacks (the port, the .venv, a project). What it
cannot see: pixels, hardware timing, the audio editor drawn on screen.
"""
import argparse, math, os, pathlib, re, shutil, struct, subprocess, sys, wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import ot_project as otp  # noqa: E402
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PROBE = ROOT / "out/emu/ot_repitch_stock_test"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/repitch"
SR, LOOP_FRAMES, TONE = 44100, 88200, 440.0
SAMPLE_REL = "AUDIO/REPITCH_440_120.wav"
TEMPO_SETTER = 0x4009c7c4          # (whole BPM, tenths), the UI's own
MACHINES = {"static": (0, 136, 0), "flex": (1, 0, 1)}   # type, markers record, slot-byte index
SETUP_OFF, VALUES_OFF, STRIDE6 = 0x1e3, 0x033, 30   # part-relative, + t*30 + 6*machine + slot
LOOP_SLOT, TSTR_SLOT, PTCH_SLOT, RATE_SLOT = 0, 4, 0, 3
STATE, VOICE, LANE = 0x80004898, 0x800049d8, 0x80000510
POSITION = VOICE + 68              # T1's sample position, frames


def make_loop(path):
    """Four beats at 120 BPM: 880 whole periods, so the loop is seamless."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        frames = bytearray()
        for n in range(LOOP_FRAMES):
            v = int(round(16000 * math.sin(2 * math.pi * TONE * n / SR)))
            frames += struct.pack("<hh", v, v)
        w.writeframes(bytes(frames))


def build_project(src, dest, tstr, tsmode, bpm, ptch, rate, machine="flex"):
    mtype, mrec, sbyte = MACHINES[machine]
    kind = machine.upper().encode()
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
        raw = re.sub(rb"\[SAMPLE\]\r\nTYPE=" + kind + rb"\r\nSLOT=001\r\n.*?\[/SAMPLE\]\r\n\r\n", b"", raw, flags=re.S)
        block = ("[SAMPLE]\r\nTYPE=" + machine.upper() + "\r\nSLOT=001\r\nPATH=../" + SAMPLE_REL + "\r\n"
                 "TRIM_BARSx100=100\r\nLOOP_BARSx100=100\r\nBPMx24=2880\r\n"
                 f"TSMODE={tsmode}\r\nLOOPMODE=1\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n"
                 "[/SAMPLE]\r\n\r\n").encode()
        at = raw.find(b"[SAMPLE]")
        if at < 0:
            sys.exit(f"verify_repitch: {pw} has no [SAMPLE] section to insert before")
        raw = raw[:at] + block + raw[at:]
        for key, val in ((rb"BANK", b"0"), (rb"PATTERN", b"0"), (rb"TRACK", b"0")):
            raw = re.sub(rb"\r\n" + key + rb"=\d+\r\n", b"\r\n" + key + b"=" + val + b"\r\n", raw, count=1)
        raw = raw.replace(b"MASTER_TRACK=1", b"MASTER_TRACK=0")
        pw.write_bytes(raw)
    otp.set_tempo(dest, bpm)
    # markers: a 22-byte header, 136 FLEX then 128 STATIC slot records of 784
    # bytes (trim start, trim end, loop point, 64 x 12-byte slices, count),
    # the bank files' checksum. An all-zero record loads as a 64-sample loop.
    for suffix in ("work", "strd"):
        pm = dest / f"markers.{suffix}"
        if not pm.is_file():
            continue
        data = bytearray(pm.read_bytes())
        at = 0x16 + 784 * mrec
        data[at:at + 784] = struct.pack(">III", 0, LOOP_FRAMES, 0) + bytes(768) + bytes(4)
        data[-2:] = (sum(data[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        pm.write_bytes(bytes(data))

    def mut(data):
        for p in range(otp.NPARTS_ALL):
            base = otp.PART_BASE + p * otp.PART_STRIDE
            data[base + otp.MTYPE_OFF] = mtype
            data[base + 0x2d3 + sbyte] = 0                   # T1 slot 1
            setup = base + SETUP_OFF + 6 * mtype
            data[setup + LOOP_SLOT] = 1
            data[setup + TSTR_SLOT] = tstr
            values = base + VALUES_OFF + 6 * mtype
            data[values + PTCH_SLOT] = ptch
            data[values + RATE_SLOT] = rate
        off = otp.trac_off(0, 0) + 7                          # pattern A01, T1, step 1
        data[off] |= 1
    otp._bank_write(dest, 1, mut, guard=False)


def stage(project, card, wav):
    cmd = [str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(project), "OCTABAM", "RIG",
           "--tree", str(card.parent / "tree"), "--out", str(card), "--audio", f"{wav}:{SAMPLE_REL}"]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_repitch: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")


def read_wav24(path):
    with wave.open(str(path), "rb") as w:
        n, ch, raw = w.getnframes(), w.getnchannels(), w.readframes(w.getnframes())
    slots = [[] for _ in range(ch)]
    for i in range(n):
        for c in range(ch):
            b = raw[(i * ch + c) * 3:(i * ch + c) * 3 + 3]
            slots[c].append(int.from_bytes(b, "little", signed=True))
    return slots


def pitch(x):
    """Median period from interpolated rising zero crossings -> Hz."""
    xs = []
    for i in range(1, len(x)):
        a, b = x[i - 1], x[i]
        if a <= 0 < b:
            xs.append(i - 1 + (-a) / (b - a))
    periods = sorted(b - a for a, b in zip(xs, xs[1:]))
    if len(periods) < 20:
        return 0.0
    return SR / periods[len(periods) // 2]


def position_speed(text, lo, hi):
    """Source frames per output sample over [lo, hi) samples after the first
    position write (the step-1 trig), from the watched writes; a loop wrap
    (the loop is the whole file) is folded back."""
    pts = [(float(m.group(1)), int(m.group(2), 16)) for m in re.finditer(
        rf"^\s+\[\s*([\d.]+)\] \[{POSITION:#x}\] <- (0x[0-9a-f]+)", text, re.M)]
    if not pts:
        return None
    s0 = pts[0][0]
    seg = [(s, v) for s, v in pts if lo <= s - s0 < hi]
    if len(seg) < 2:
        return None
    total = 0
    for (_, u), (_, v) in zip(seg, seg[1:]):
        d = (v - u) & 0xFFFFFFFF
        d = d - (1 << 32) if d & 0x80000000 else d
        if d > LOOP_FRAMES // 2:
            d -= LOOP_FRAMES
        elif d < -LOOP_FRAMES // 2:
            d += LOOP_FRAMES
        total += d
    return total / (seg[-1][0] - seg[0][0])


def run_case(a, name, machine, tstr, tsmode, ptch, image, rate=127):
    work = OUT / name
    work.mkdir(parents=True, exist_ok=True)
    wav = OUT / "REPITCH_440_120.wav"
    if not wav.is_file():
        make_loop(wav)
    build_project(pathlib.Path(a.project).expanduser(), work / "project", tstr, tsmode, a.tempo, ptch, rate, machine)
    card = work / "card.img"
    stage(work / "project", card, wav)
    dumps = work / "state.bin", work / "voices.bin", work / "lanes.bin", work / "tempo.bin"
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM", "--project", "RIG",
           "--sequencer", "--internal-clock", "--frames", str(a.frames), "--load-ms", "20000",
           "--dsp", "--main-level", "64", "--audio-out", str(work / "port"),
           "--watch-mem", f"{POSITION:#x},4",
           "--mem-dump", f"{STATE:#x},320={dumps[0]};{VOICE:#x},1344={dumps[1]};"
                         f"{LANE:#x},384={dumps[2]};0x80001814,12={dumps[3]}"]
    if a.to:
        whole = int(a.to); tenths = round((a.to - whole) * 10)
        cmd += ["--call-at", str(a.at), "--call", f"{TEMPO_SETTER:#x},{whole},{tenths}"]
    log = work / "port.txt"
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text()
    if r.returncode or not re.search(r"run ended REACHED", text):
        return dict(error=f"port run failed (exit {r.returncode}) -- {log}")
    best = None
    for core in (0, 1):
        p = work / f"port_core{core}.wav"
        if not p.is_file():
            continue
        m = re.search(rf"port_core{core}\.wav, .*?transport start at frame (\d+)", text)
        if not m:
            continue
        start = int(m.group(1))
        for s, x in enumerate(read_wav24(p)):
            x = x[start:]
            energy = sum(v * v for v in x[:SR // 2])
            if best is None or energy > best[0]:
                best = (energy, core, s, x)
    if best is None or best[0] == 0:
        return dict(error=f"no audio on any slot -- {log}")
    _, core, s, x = best
    change = a.at * 16
    before = x[max(0, change - SR // 2):change] if a.to else x[SR // 4:SR // 4 + SR // 2]
    after = x[change + SR // 4:change + SR // 4 + SR // 2] if a.to else before
    state = dumps[0].read_bytes()
    lanes = dumps[2].read_bytes()
    voices = dumps[1].read_bytes()
    tempo = struct.unpack(">III", dumps[3].read_bytes())
    end = a.frames * 16
    if a.to:
        speed = (position_speed(text, SR // 8, change - SR // 8), position_speed(text, change + SR // 8, end - SR // 16))
    else:
        speed = (position_speed(text, SR // 8, end - SR // 16),) * 2
    return dict(core=core, slot=s, before=pitch(before), after=pitch(after), samples=len(x), speed=speed,
                inc=struct.unpack(">I", state[36:40])[0], lane_tstr=lanes[28], voice_tstr=voices[24],
                tempo=tempo, log=log)


R = None   # the tempo ratio (after / before)
CASES = {  # name: machine, SETUP TSTR, sample TSMODE, PTCH, RATE, pitch x440, speed, resolved TSTR
    "stock-off": ("flex", 0, 2, 64, 127, (1, 1), (1, 1), 0),
    "stretch": ("flex", 2, 2, 64, 127, (1, 1), (1, R), 2),
    "repitch": ("flex", 4, 2, 64, 127, (1, R), (1, R), 0),
    "auto": ("flex", 1, 4, 64, 127, (1, R), (1, R), 0),
    "ptch": ("flex", 4, 2, 88, 127, (1, R), (1, R), 0),
    "static": ("static", 4, 2, 64, 127, (1, R), (1, R), 0),
    "reverse": ("flex", 4, 2, 64, 0, (1, R), (-1, R), 0),
}


def main():
    global OUT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="repitch")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--image", default="", help="a built image instead of building the remix")
    ap.add_argument("--work", default="", help="scratch directory (default out/repitch)")
    ap.add_argument("--case", action="append", choices=sorted(CASES), help="default: all")
    ap.add_argument("--tempo", type=float, default=120.0)
    ap.add_argument("--to", type=float, default=90.0, help="live tempo change target (0 = none)")
    ap.add_argument("--at", type=int, default=2000, help="frames after the transport start")
    ap.add_argument("--frames", type=int, default=5000)
    ap.add_argument("--adhoc", default="", metavar="MACHINE,TSTR,TSMODE,PTCH[,RATE]",
                    help="one extra run with these values, reported without a verdict")
    a = ap.parse_args()
    if a.work:
        OUT = pathlib.Path(a.work).resolve()

    if "REPITCH" not in registry.remix(a.remix).modules:
        print(f"  [ -- ] verify_repitch: {a.remix} carries no REPITCH")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "image.bin"
    if a.image:
        shutil.copy2(a.image, image)
    else:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_repitch: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    fails = 0
    if not a.adhoc:
        # The hooks through the firmware's own code (tools/harness/repitch_probe.cpp).
        if PROBE.exists():
            for args in ([str(ROOT / "out/raw/section_3_MAIN_OS.bin")], ["--patched", str(image)]):
                r = subprocess.run([str(PROBE), *args], cwd=ROOT, capture_output=True, text=True)
                for line in r.stdout.splitlines():
                    if line.lstrip().startswith(("[PASS]", "[FAIL]", "SKIP:")) or "failure(s)" in line:
                        print("  " + line.strip())
                fails += r.returncode != 0
        else:
            print("  [SKIP] verify_repitch: hook contracts need the port's probe (make emu-cf)")
        # The page drawings (tools/verify/verify_repitch_ui.py, the .venv's unicorn).
        if PY.exists():
            r = subprocess.run([str(PY), str(ROOT / "tools/verify/verify_repitch_ui.py"), a.remix,
                                "--image", str(image)], cwd=ROOT)
            fails += r.returncode != 0
        else:
            print("  [SKIP] verify_repitch: page drawings need the .venv (make emu-setup)")

    if not a.project:
        print("  [SKIP] verify_repitch: playback needs a project (OT_PROJECT=<dir> or --project)")
        return 1 if fails else 0
    if not (pathlib.Path(a.project).expanduser() / "project.work").is_file():
        sys.exit(f"verify_repitch: {a.project} is not an Octatrack project directory")
    if not EMU.exists() or not PY.exists():
        print("  [SKIP] verify_repitch: playback needs the port (make emu-cf) and the .venv (make emu-setup)")
        return 1 if fails else 0

    if a.adhoc:
        machine, *rest = a.adhoc.split(",")
        tstr, tsmode, ptch, *rate = (int(v) for v in rest)
        print(f"  [adhoc] {run_case(a, 'adhoc', machine, tstr, tsmode, ptch, image, *rate)}")
        return 0
    ratio = (a.to or a.tempo) / a.tempo

    def want(pair):
        k0, k1 = pair
        return k0, (k1 if k1 is not None else ratio) * (-1 if k0 < 0 else 1)

    for name in a.case or list(CASES):
        machine, tstr, tsmode, ptch, rate, pk, sk, resolved = CASES[name]
        res = run_case(a, name, machine, tstr, tsmode, ptch, image, rate)
        if "error" in res:
            print(f"  [FAIL] playback {name}: {res['error']}", flush=True); fails += 1; continue
        p0, p1 = (TONE * k for k in want(pk))
        s0, s1 = want(sk)
        got0, got1 = res["speed"]
        ok = (abs(res["before"] - p0) < 2.0 and abs(res["after"] - p1) < 2.0
              and got0 is not None and got1 is not None
              and abs(got0 - s0) < 0.01 and abs(got1 - s1) < 0.01
              and res["voice_tstr"] == resolved)
        fails += not ok
        fmt = lambda v: "none" if v is None else f"{v:+.4f}"  # noqa: E731
        print(f"  [{'ok' if ok else 'FAIL'}] playback {name}: pitch {res['before']:.2f} -> {res['after']:.2f} Hz "
              f"(want {p0:.0f} -> {p1:.0f}), speed {fmt(got0)} -> {fmt(got1)} (want {s0:+.2f} -> {s1:+.2f}), "
              f"resolved TSTR {res['voice_tstr']} (want {resolved}); increment {res['inc']:#010x}, "
              f"SETUP TSTR {res['lane_tstr']}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
