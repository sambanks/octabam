#!/usr/bin/env python3
"""
Render real audio through ChonVerb in the emulator, so voicing can be judged by
ear without a flash.

    python3 tools/render_reverb.py loop.wav
    python3 tools/render_reverb.py loop.wav -p TIME=100 -p SIZE=127 -p MIX=80
    python3 tools/render_reverb.py loop.wav --sweep SIZE=0,64,127 --wet
    python3 tools/render_reverb.py loop.wav --build          # rebuild first

Why this is trustworthy: tools/dsp_host runs the REAL assembled instruction
stream, not a model of the reverb, and the DSP56300 arithmetic is emulated
exactly -- which REVERB.md already leans on ("for a pure optimization the
output should be bit-identical"). About 6x faster than real time.

What it CANNOT tell you, and still needs a flash (REVERB.md, BUS.md):
  * whether four instances fit the cycle budget -- 432 cycles/sample once
    froze the chip, and this harness will happily render something that
    cannot run
  * anything ColdFire-side: menu, descriptors, knob labels, parameter
    ranges. -params pokes r6 directly and bypasses all of it
  * payload B, which dsp_host cannot boot at all
  * multi-instance behaviour under a nonzero split, where there is a known
    unexplained one-vs-two-instance divergence

So: voice here, then spend flashes on the cycle budget and the UI surface.
"""
import argparse, array, math, os, pathlib, struct, subprocess, sys, wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host"
IMAGE = ROOT / "out/mainos_bus.bin"
MEM = ROOT / "out/dsp/mem_reverb_server_A.mem"

SR = 44100
FRAMES = 15              # dsp_host caps a block at 15 frames (the & 0xf in setup)
WARMUP_BLOCKS = 260      # the engine stays dry for 256 CALLS; pad past it and trim

# -params index -> r6 offset is NOT linear: 0..5 are page 1, then the harness
# maps 6..9 onto r6+$b..$e. Names come from REVERB.md's measured table.
PARAMS = [("TIME", 64), ("MOD", 40), ("SIZE", 127), ("HP", 0), ("LP", 100),
          ("MIX", 64), ("WIDTH", 64), ("_FREE", 0), ("DEL", 0), ("PRE", 0)]
NAMES = {n: i for i, (n, _) in enumerate(PARAMS)}
# $c (index 7) is a real page-2 slot but nothing on the host drives it
# (REVERB.md), so it is not offered as a knob.
KNOBS = ", ".join(n for n, _ in PARAMS if n != "_FREE")


def die(msg):
    sys.exit(f"render_reverb: {msg}")


# ---- WAV in --------------------------------------------------------------
def read_wav(path):
    """-> (mono float list in -1..1, samplerate). Stereo is summed to mono:
    the harness feeds one mono stream and the engine sums L+R itself."""
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 1:
        vals = [(b - 128) / 128.0 for b in raw]
    elif sw == 2:
        a = array.array("h"); a.frombytes(raw); vals = [v / 32768.0 for v in a]
    elif sw == 3:
        vals = []
        for i in range(0, len(raw), 3):
            v = raw[i] | (raw[i + 1] << 8) | (raw[i + 2] << 16)
            vals.append(((v - 0x1000000) if v & 0x800000 else v) / 8388608.0)
    elif sw == 4:
        a = array.array("i"); a.frombytes(raw); vals = [v / 2147483648.0 for v in a]
    else:
        die(f"unsupported sample width {sw*8}-bit in {path}")
    if ch > 1:
        vals = [sum(vals[i:i + ch]) / ch for i in range(0, len(vals) - ch + 1, ch)]
    return vals, sr


def resample(x, src, dst):
    """Naive linear resample. Good enough to audition a reverb; not a
    mastering-grade converter, so prefer 44.1 kHz sources."""
    if src == dst:
        return x
    ratio = dst / src
    out = []
    for i in range(int(len(x) * ratio)):
        p = i / ratio
        j = int(p)
        f = p - j
        a = x[j] if j < len(x) else 0.0
        b = x[j + 1] if j + 1 < len(x) else a
        out.append(a + (b - a) * f)
    return out


def write_wav(path, left, right):
    b = bytearray()
    for l, r in zip(left, right):
        for s in (l, r):
            s = max(-8388608, min(8388607, int(s)))
            b += (s & 0xFFFFFF).to_bytes(3, "little")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(3); w.setframerate(SR)
        w.writeframes(bytes(b))


# ---- the emulator --------------------------------------------------------
def ensure_mem(build):
    if build or not IMAGE.exists():
        print("building out/mainos_bus.bin ...")
        subprocess.run([sys.executable, "tools/build_bus.py"], cwd=ROOT,
                       check=True, capture_output=True)
    if not HOST.exists():
        die(f"missing {HOST.relative_to(ROOT)} -- run ./setup.sh")
    stale = not MEM.exists() or MEM.stat().st_mtime < IMAGE.stat().st_mtime
    if stale:
        sys.path.insert(0, str(ROOT / "tools"))
        import dsp_modmap
        MEM.parent.mkdir(parents=True, exist_ok=True)
        dsp_modmap.dumpmem(IMAGE.read_bytes(), ["A", str(MEM)])
    return MEM


def run(mem, src, values, tail_s, verbose):
    """src: mono floats at SR. -> (L, R) as 24-bit ints, warm-up trimmed."""
    pad = WARMUP_BLOCKS * FRAMES
    total = pad + len(src) + int(tail_s * SR)
    blocks = -(-total // FRAMES)
    n = blocks * FRAMES

    tmp = ROOT / "out/dsp/_render_in.raw"
    out = ROOT / "out/dsp/_render_out.raw"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "wb") as f:
        for i in range(n):
            v = src[i - pad] if pad <= i < pad + len(src) else 0.0
            f.write(struct.pack("<i", max(-8388608, min(8388607, int(v * 8388607)))))

    cmd = [str(HOST), "-mem", str(mem), "-init", "1252", "-proc", "1253",
           "-inst", "1", "-r7", "4", "-alloc", "3", "-blocks", str(blocks),
           "-in", str(tmp), "-out", str(out),
           "-params", ",".join(str(v) for v in values)]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"dsp_host failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    if verbose:
        print(r.stdout.strip().splitlines()[-1])

    a = array.array("i")
    a.frombytes(out.read_bytes())
    return list(a[0::2])[pad:], list(a[1::2])[pad:]


# ---- reporting -----------------------------------------------------------
def report(label, L, R, src_len):
    peak = max((abs(v) for v in L + R), default=0)
    clip = sum(1 for v in L + R if abs(v) >= 8388607)
    tail = L[src_len:] or L
    w = SR // 10
    env = [math.sqrt(sum(s * s for s in tail[i:i + w]) / w)
           for i in range(0, max(len(tail) - w, 1), w)]
    rt = 0.0
    if env and max(env) > 0:
        pk = max(env)
        above = [i for i, e in enumerate(env) if 20 * math.log10(max(e, 1e-9) / pk) > -60]
        if above:
            rt = (above[-1] + 1) * w / SR
    print(f"  {label:28s} peak {peak/8388607:5.2f} FS   tail to -60 dB {rt:5.2f} s"
          + (f"   *** {clip} CLIPPED SAMPLES ***" if clip else ""))


def main():
    ap = argparse.ArgumentParser(description="Render audio through ChonVerb in the emulator.")
    ap.add_argument("input", help="source .wav (mono or stereo; 44.1 kHz preferred)")
    ap.add_argument("-o", "--out", help="output .wav (default: alongside the source)")
    ap.add_argument("-p", "--param", action="append", default=[], metavar="NAME=VAL",
                    help="knob, 0..127: " + KNOBS)
    ap.add_argument("--sweep", metavar="NAME=a,b,c", help="one render per value")
    ap.add_argument("--wet", action="store_true",
                    help="wet only (out minus the dry path, exact -- not a MIX trick)")
    ap.add_argument("--tail", type=float, default=8.0, help="seconds of ring-out (default 8)")
    ap.add_argument("--gain", type=float, default=1.0, help="input gain, linear (default 1.0)")
    ap.add_argument("--build", action="store_true", help="run build_bus.py first")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    values = [d for _, d in PARAMS]
    for spec in a.param:
        if "=" not in spec:
            die(f"bad -p {spec!r}, want NAME=VALUE")
        k, v = spec.split("=", 1)
        if k.upper() not in NAMES or k.upper() == "_FREE":
            die(f"unknown knob {k!r}; known: {KNOBS}")
        values[NAMES[k.upper()]] = max(0, min(127, int(v)))

    sweep = []
    if a.sweep:
        k, vs = a.sweep.split("=", 1)
        if k.upper() not in NAMES or k.upper() == "_FREE":
            die(f"unknown knob {k!r}; known: {KNOBS}")
        sweep = [(k.upper(), int(v)) for v in vs.split(",")]

    src_path = pathlib.Path(a.input)
    if not src_path.exists():
        die(f"no such file: {src_path}")
    src, sr = read_wav(src_path)
    if sr != SR:
        print(f"note: {sr} Hz source, linearly resampled to {SR} -- prefer 44.1 kHz sources")
        src = resample(src, sr, SR)
    if a.gain != 1.0:
        src = [v * a.gain for v in src]

    mem = ensure_mem(a.build)
    out_base = pathlib.Path(a.out) if a.out else src_path.with_suffix("")
    print(f"{src_path.name}: {len(src)/SR:.1f} s + {a.tail:.0f} s tail"
          + (f"   [{'wet only' if a.wet else 'wet+dry'}]"))

    jobs = [(dict(zip(NAMES, values)), out_base, None)] if not sweep else []
    for k, v in sweep:
        vals = dict(zip(NAMES, values)); vals[k] = v
        jobs.append((vals, pathlib.Path(f"{out_base}_{k}{v}"), k))

    for vals, dest, swept in jobs:
        vlist = [vals[n] for n, _ in PARAMS]
        L, R = run(mem, src, vlist, a.tail, a.verbose)
        if a.wet:
            # output = dry + wet, and the dry path is the mono input duplicated,
            # so subtracting it recovers the wet exactly.
            dry = [int(v * 8388607) for v in src] + [0] * (len(L) - len(src))
            L = [l - d for l, d in zip(L, dry)]
            R = [r - d for r, d in zip(R, dry)]
        dest = dest.with_suffix(".wav")
        write_wav(dest, L, R)
        # name the knobs that differ from the defaults, and always the swept one
        # (a sweep can legitimately pass through a knob's own default value)
        label = " ".join(f"{n}={vals[n]}" for n, _ in PARAMS
                         if n != "_FREE" and (n == swept or vals[n] != dict(PARAMS)[n])) \
                or "defaults"
        report(label, L, R, len(src))
        print(f"  -> {dest}")


if __name__ == "__main__":
    main()
