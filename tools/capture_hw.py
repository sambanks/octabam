#!/usr/bin/env python3
"""
Record the Octatrack's output through an audio interface and ANALYSE it, so the
hardware artifact can be characterised numerically instead of described.

    python3 tools/capture_hw.py --list
    python3 tools/capture_hw.py -d 2 -t 8 -o out/hw/send_bad.wav
    python3 tools/capture_hw.py --analyse out/hw/send_bad.wav

WHY THIS EXISTS. `tools/send_probe.py` renders the SEND -> bus -> REVERB path in
the emulator and it comes out CLEAN under every configuration that can be built:
one send or four, matched or mismatched per-track splits, any housekeeping
layout, quiet or clipping, all 25 engine commits. Sam hears the whole signal
turn into a metallic staticky tone on the device. So the cause is something the
emulator does not model, and the only way forward is evidence from the hardware
itself.

WHAT THE ANALYSIS LOOKS FOR. The reported symptom -- the signal REPLACED by a
metallic tone rather than merely distorted -- has a small number of signatures
that are easy to tell apart in a spectrum:

  * BLOCK-RATE BUZZ. The bus accumulators are 16 words, one per frame, and a
    block is 15-16 frames at 44.1 kHz. If the server reads the accumulator at a
    wrong or frozen index, the output picks up a periodic discontinuity at the
    BLOCK rate and the spectrum grows a comb at multiples of ~2756 Hz. This is
    the signature of a per-block indexing fault -- the leading hypothesis, and
    the one the emulator cannot rule out because it does not model the real
    dispatcher.
  * BROADBAND HASH with no relation to the input: the server is reading memory
    that is not audio at all.
  * HARMONIC DISTORTION at 2f/3f/5f of a test tone with the fundamental still
    dominant: ordinary overload, which is a known and separate weakness (the
    reverb saturates above ~0.35 FS input) and is NOT this bug.

HOW TO USE IT. Play a steady tone or a simple loop into the send with ChonVerb
on the receiving track, capture ~8 s, then run --analyse. Capture the WORKING
case too if one exists (send level at zero, or the reverb on its own track):
the comparison is worth far more than either recording alone.
"""
import argparse, array, math, os, pathlib, subprocess, sys, wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

SR = 44100
FRAMES = 15                      # the dispatcher's frames per block
BLOCK_HZ = SR / 16.0             # 2756.25 Hz -- the 16-word accumulator's rate


def die(msg):
    sys.exit(f"capture_hw: {msg}")


def list_devices():
    r = subprocess.run(["ffmpeg", "-f", "avfoundation", "-list_devices", "true",
                        "-i", ""], capture_output=True, text=True)
    out = r.stderr
    started = False
    for line in out.splitlines():
        if "AVFoundation audio devices" in line:
            started = True
            print("audio input devices:")
            continue
        if started:
            if "] [" in line or "] [" in line:
                pass
            idx = line.find("] [")
            if idx >= 0:
                print("   ", line[idx + 2:])
            elif "AVFoundation" not in line:
                break
    print("\nrecord with:  python3 tools/capture_hw.py -d <N> -t 8 -o out/hw/x.wav")


def record(dev, secs, dest):
    dest = pathlib.Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "avfoundation", "-i", f":{dev}",
           "-t", str(secs), "-ar", str(SR), "-ac", "2",
           "-c:a", "pcm_s24le", str(dest)]
    print("  " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"ffmpeg failed:\n{r.stderr[-2500:]}")
    print(f"  -> {dest}")
    return dest


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        a = array.array("h"); a.frombytes(raw); v = [x / 32768.0 for x in a]
    elif sw == 3:
        v = []
        for i in range(0, len(raw), 3):
            x = raw[i] | (raw[i + 1] << 8) | (raw[i + 2] << 16)
            v.append(((x - 0x1000000) if x & 0x800000 else x) / 8388608.0)
    elif sw == 4:
        a = array.array("i"); a.frombytes(raw); v = [x / 2147483648.0 for x in a]
    else:
        die(f"unsupported sample width {sw*8}-bit")
    if ch > 1:
        v = [sum(v[i:i + ch]) / ch for i in range(0, len(v) - ch + 1, ch)]
    return v, sr


def analyse(path):
    from send_probe import fft
    sig, sr = read_wav(path)
    if not sig:
        die(f"{path} is empty")
    pk = max(abs(x) for x in sig)
    rms = math.sqrt(sum(x * x for x in sig) / len(sig))
    print(f"{pathlib.Path(path).name}: {len(sig)/sr:.2f} s @ {sr} Hz   "
          f"peak {pk:.3f} FS   rms {20*math.log10(max(rms,1e-9)):.1f} dBFS")
    if pk < 1e-4:
        die("recording is silent -- check routing and input gain")

    # loudest steady window, so a capture with silence at either end still lands
    # the analysis on the actual sound
    N = 16384
    if len(sig) < N:
        die(f"only {len(sig)} samples, need {N}")
    best, bi = -1.0, 0
    for i in range(0, len(sig) - N, N // 2):
        e = sum(x * x for x in sig[i:i + N])
        if e > best:
            best, bi = e, i
    seg = sig[bi:bi + N]

    hann = [0.5 - 0.5 * math.cos(2 * math.pi * i / N) for i in range(N)]
    spec = fft([complex(seg[i] * hann[i], 0) for i in range(N)])
    half = N // 2
    mag = [abs(spec[i]) for i in range(half)]
    total = sum(m * m for m in mag[1:])
    if total <= 0:
        die("no energy in the analysis window")

    peak_i = max(range(2, half), key=lambda i: mag[i])
    print(f"  strongest component: {peak_i*sr/N:8.1f} Hz")

    # 1) comb at multiples of the block rate = per-block indexing fault
    guard = 3
    comb, seen = 0.0, set()
    k = 1
    while k * BLOCK_HZ < sr / 2:
        b = int(round(k * BLOCK_HZ * N / sr))
        for j in range(b - guard, b + guard + 1):
            if 0 < j < half and j not in seen:
                seen.add(j); comb += mag[j] ** 2
        k += 1
    print(f"  energy at multiples of the {BLOCK_HZ:.1f} Hz BLOCK RATE : "
          f"{10*math.log10(max(comb,1e-30)/total):6.1f} dB of total")

    # 2) how concentrated is the spectrum? a metallic tone is a few strong lines
    order = sorted(range(1, half), key=lambda i: mag[i], reverse=True)
    for topn in (1, 8, 32):
        e = sum(mag[i] ** 2 for i in order[:topn])
        print(f"  top {topn:3d} bins hold {100*e/total:5.1f}% of the energy")

    print("  loudest lines:")
    shown, out = set(), 0
    for i in order:
        if any(abs(i - j) <= guard for j in shown):
            continue
        shown.add(i); out += 1
        f = i * sr / N
        near = round(f / BLOCK_HZ)
        tag = (f"   (~{near}x block rate)"
               if near >= 1 and abs(f - near * BLOCK_HZ) < 25 else "")
        print(f"     {f:8.1f} Hz  {20*math.log10(max(mag[i],1e-30)/mag[peak_i]):6.1f} dB{tag}")
        if out >= 10:
            break

    print("\n  READING IT: a strong comb at multiples of "
          f"{BLOCK_HZ:.0f} Hz => per-block indexing fault (the leading hypothesis).\n"
          "  Energy spread everywhere with no relation to the input => the server is\n"
          "  reading memory that is not audio. Fundamental still dominant with 3f/5f\n"
          "  below it => ordinary overload, which is a DIFFERENT known issue.")


def timeline(path, hop=0.5):
    """Track the artifact THROUGH a fade, which is what tells the two remaining
    hypotheses apart.

    Fading the send up from zero sweeps the level continuously, so the question
    "does the artifact scale with the signal, or switch on above a threshold?"
    is answered by whether the block-rate column stays FLAT as the rms column
    rises. Flat => structural: the bus is delivering something proportional to
    the signal, and it is broken at every level. Rising only near the top =>
    ordinary overload, which is a separate known weakness and not this bug."""
    from send_probe import fft
    sig, sr = read_wav(path)
    N = 16384
    step = max(int(hop * sr), 1)
    if len(sig) < N:
        die(f"only {len(sig)} samples, need {N}")
    hann = [0.5 - 0.5 * math.cos(2 * math.pi * i / N) for i in range(N)]
    guard = 3

    print(f"{pathlib.Path(path).name}: {len(sig)/sr:.2f} s, window "
          f"{N/sr:.2f} s every {hop:.2f} s")
    print("   time     rms      block-rate    top-1    strongest")
    print("    (s)   (dBFS)   comb (dB rel)   bin %       line")
    rows = []
    for start in range(0, len(sig) - N, step):
        seg = sig[start:start + N]
        rms = math.sqrt(sum(x * x for x in seg) / N)
        if rms < 1e-6:
            print(f"  {start/sr:5.1f}   {20*math.log10(max(rms,1e-9)):6.1f}"
                  f"        --           --      (silent)")
            continue
        spec = fft([complex(seg[i] * hann[i], 0) for i in range(N)])
        half = N // 2
        mag = [abs(spec[i]) for i in range(half)]
        total = sum(m * m for m in mag[1:]) or 1e-30

        comb, seen, k = 0.0, set(), 1
        while k * BLOCK_HZ < sr / 2:
            b = int(round(k * BLOCK_HZ * N / sr))
            for j in range(b - guard, b + guard + 1):
                if 0 < j < half and j not in seen:
                    seen.add(j); comb += mag[j] ** 2
            k += 1
        combdb = 10 * math.log10(max(comb, 1e-30) / total)
        pi = max(range(2, half), key=lambda i: mag[i])
        top1 = 100 * mag[pi] ** 2 / total
        f = pi * sr / N
        near = round(f / BLOCK_HZ)
        tag = "*" if near >= 1 and abs(f - near * BLOCK_HZ) < 25 else " "
        print(f"  {start/sr:5.1f}   {20*math.log10(rms):6.1f}      {combdb:6.1f}"
              f"       {top1:5.1f}    {f:8.1f} Hz{tag}")
        rows.append((20 * math.log10(rms), combdb))

    if len(rows) >= 4:
        lo = [c for r, c in rows if r < min(r for r, _ in rows) + 12]
        hi = [c for r, c in rows if r > max(r for r, _ in rows) - 12]
        if lo and hi:
            print(f"\n  quietest part of the fade: block-rate comb "
                  f"{sum(lo)/len(lo):6.1f} dB")
            print(f"  loudest  part of the fade: block-rate comb "
                  f"{sum(hi)/len(hi):6.1f} dB")
            d = sum(hi) / len(hi) - sum(lo) / len(lo)
            print(f"  change across the fade: {d:+.1f} dB")
            print("\n  READING IT: within a few dB => the artifact scales with the signal,\n"
                  "  i.e. STRUCTURAL and present at every send level. Strongly rising =>\n"
                  "  level-dependent overload, a different (known) issue.\n"
                  "  A clean emulator render measures about -47 dB on this column.")
    print("  (* = the strongest line sits on a multiple of the block rate)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list audio input devices")
    ap.add_argument("-d", "--device", help="avfoundation audio device index")
    ap.add_argument("-t", "--secs", type=float, default=8.0)
    ap.add_argument("-o", "--out", default="out/hw/capture.wav")
    ap.add_argument("--analyse", metavar="FILE", help="analyse an existing recording")
    ap.add_argument("--timeline", metavar="FILE",
                    help="track the artifact through a FADE, window by window")
    ap.add_argument("--hop", type=float, default=0.5, help="timeline step, seconds")
    a = ap.parse_args()

    if a.list:
        return list_devices() or 0
    if a.timeline:
        return timeline(a.timeline, a.hop) or 0
    if a.analyse:
        return analyse(a.analyse) or 0
    if a.device is None:
        die("give -d <device index> (see --list), or --analyse <file>")
    analyse(record(a.device, a.secs, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
