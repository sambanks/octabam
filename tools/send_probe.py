#!/usr/bin/env python3
"""
Render a REAL send path -- SEND client -> shared bus -> REVERB SERVER -- in the
emulator, and measure the metallic artifact numerically.

    python3 tools/send_probe.py                     # current working tree
    python3 tools/send_probe.py --wav out/send.wav  # ... and keep the audio

WHY THIS EXISTS. The obvious local repro -- `dsp_host -inst 2` with two reverbs
-- does not exercise the send path at all, for three independent reasons:

  * ChonVerb never WRITES the REVERB accumulator. It reads it (r7+$63) and
    writes the DELAY accumulator (r7+$68). Only dsp/send_client.asm writes the
    REVERB one, so with no SEND instance the reverb reads an all-zero buffer.
  * The server-role lock (dsp/reverb_server.asm, y:>$982) makes a second
    REVERB SERVER instance rts immediately as a dry passthrough.
  * dsp_host took ONE -init/-proc pair, so every instance ran the same effect.

The third is now fixed: -init/-proc take a list, one entry point per instance.
This script uses that to run instance 0 = REVERB SERVER (r7 0x6200, position 0,
the housekeeper) and instance 1 = SEND (r7 0x6400) -- the hardware layout from
XBUS.md, track 1 ChonVerb + track 2 Send.

-inmask 2 feeds the tone to the SEND only. The reverb's own dry input is
silent, so everything in its output arrived over the bus. That is what makes
the measurement unambiguous.

THE METRIC. A linear reverb fed a sine outputs a sine. Any significant energy
away from the fundamental is nonlinearity or a glitch -- exactly the
"robotic/metallic/formanty" artifact. So: drive a bin-centred sine through the
send, take a steady-state window of the reverb's output, and report the total
non-fundamental energy relative to the fundamental. MOD and SPEED are forced to
0 because delay-line modulation makes legitimate sidebands.

TRAPS THIS SCRIPT IS BUILT AROUND (both cost a wrong conclusion before):
  * the engine stays DRY for 256 CALLS -- the source starts after the warm-up
  * a silent render scores perfectly, so silence is checked FIRST and reported
    as a failure, never as a clean result
"""
import argparse, array, cmath, math, os, pathlib, struct, subprocess, sys, wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host"

SR = 44100
FRAMES = 15                # dsp_host caps a block at 15 frames
WARMUP_BLOCKS = 300        # the engine stays dry for 256 CALLS; pad well past it

REVERB_ID, SEND_ID = 0x07, 0x09
INIT_TAB, PROC_TAB = 0x215, 0x235

# analysis window: 16384 pts -> 2.6917 Hz bins. The tone is placed exactly on
# bin 163 so a clean render puts all its energy in one bin and the spur floor
# is not just spectral leakage.
NFFT = 16384
TONE_BIN = 163
TONE_HZ = TONE_BIN * SR / NFFT      # 438.75 Hz


def die(msg):
    sys.exit(f"send_probe: {msg}")


# ---- payload dump --------------------------------------------------------
def dump_mem(image, mem):
    sys.path.insert(0, str(ROOT / "tools"))
    import dsp_modmap
    mem.parent.mkdir(parents=True, exist_ok=True)
    dsp_modmap.dumpmem(pathlib.Path(image).read_bytes(), ["A", str(mem)])
    return mem


def entry_points(mem_path, fxid):
    """Read an effect's init/proc out of the dispatch tables in the dump, the
    same tables the hardware dispatches through -- a hardcoded entry point
    silently jumps into whatever moved into that address."""
    blob = pathlib.Path(mem_path).read_bytes()
    want = {INIT_TAB + fxid, PROC_TAB + fxid}
    found, pos = {}, 0
    while pos + 9 <= len(blob):
        sp, addr, cnt = struct.unpack_from("<BII", blob, pos)
        pos += 9
        if sp == 0xff:
            break
        if sp == 1:
            for a in want:
                if addr <= a < addr + cnt:
                    found[a] = struct.unpack_from("<I", blob, pos + (a - addr) * 4)[0]
        pos += cnt * 4
    init, proc = found.get(INIT_TAB + fxid), found.get(PROC_TAB + fxid)
    if init is None or proc is None:
        die(f"no dispatch entry for fx id 0x{fxid:02x} in {pathlib.Path(mem_path).name}")
    if not 0 < init < 0x20000 or proc != init + 1:
        die(f"implausible entry points for 0x{fxid:02x}: init 0x{init:05x} proc 0x{proc:05x}")
    return init, proc


# ---- the run -------------------------------------------------------------
def run(mem, dur, tail, rev_params, send_params, verbose=False, amp=0.5,
        direct=False, wave_src=None, split=0, layout='RS'):
    """-> instance 0 (the reverb) as a list of 24-bit ints, warm-up trimmed.

    direct=True is the CONTROL: no SEND instance at all, the tone goes into the
    reverb's own audio buffer. Same engine, same level, same full-wet MIX -- the
    only difference is whether the signal arrived over the bus. Without this,
    any distortion measured on the send path could just as well be the reverb
    overloading, which it would do on its own input too."""
    pad = WARMUP_BLOCKS * FRAMES
    n_tone = len(wave_src) if wave_src is not None else int(dur * SR)
    total = pad + n_tone + int(tail * SR)
    blocks = -(-total // FRAMES)
    n = blocks * FRAMES

    # PID-tagged: two probes running at once (a commit sweep in the background
    # while a render is made in the foreground) would otherwise overwrite each
    # other's raw files and silently cross-contaminate the results.
    src = ROOT / f"out/dsp/_send_in_{os.getpid()}.raw"
    out = ROOT / f"out/dsp/_send_out_{os.getpid()}.raw"
    src.parent.mkdir(parents=True, exist_ok=True)
    w = 2 * math.pi * TONE_HZ / SR
    with open(src, "wb") as f:
        for i in range(n):
            if wave_src is not None:
                j = i - pad
                v = amp * wave_src[j] if 0 <= j < len(wave_src) else 0.0
            else:
                v = amp * math.sin(w * (i - pad)) if pad <= i < pad + n_tone else 0.0
            f.write(struct.pack("<i", max(-8388608, min(8388607, int(v * 8388607)))))

    ri, rp = entry_points(mem, REVERB_ID)
    si, sp = entry_points(mem, SEND_ID)
    live = [(0, 'R')]
    if direct:
        cmd = [str(HOST), "-mem", str(mem),
               "-init", f"{ri:x}", "-proc", f"{rp:x}",
               "-inst", "1", "-r7", "2", "-alloc", "1",
               "-inmask", "1",                   # tone straight into the reverb
               "-blocks", str(blocks), "-in", str(src), "-out", str(out),
               *(["-split", str(split)] if str(split) not in ("0", "") else []),
               "-params", ",".join(map(str, rev_params))]
    else:
        # Nothing in send_client divides by the number of clients, so N sends put
        # N x the contribution into one accumulator word.
        # layout: one char per DISPATCH SLOT, in hardware order.
        #   R = REVERB SERVER, S = SEND, . = a track running neither (NONE or a
        #       stock effect -- our code never runs there, so the slot is simply
        #       skipped and nobody housekeeps from it)
        # Slot 0 is position 0 (r7 0x6200), the designated housekeeper. Putting
        # anything other than R there is what makes send_client's self-healing
        # election actually run, and that path never executed in any earlier test.
        slots = [c for c in layout.upper() if c in "RS."]
        live = [(k, c) for k, c in enumerate(slots) if c != "."]
        n = len(live)
        if not any(c == "R" for _, c in live):
            die(f"layout {layout!r} has no REVERB SERVER")
        r7s = ",".join(str(2 + 2 * k) for k, _ in live)
        als = ",".join(str(1 + 2 * k) for k, _ in live)
        inmask = sum(1 << i for i, (_, c) in enumerate(live) if c == "S")
        cmd = [str(HOST), "-mem", str(mem),
               "-init", ",".join(f"{ri:x}" if c == "R" else f"{si:x}" for _, c in live),
               "-proc", ",".join(f"{rp:x}" if c == "R" else f"{sp:x}" for _, c in live),
               "-inst", str(n), "-r7", r7s, "-alloc", als,
               "-inmask", str(inmask),                # tone to the SENDs only
               "-blocks", str(blocks), "-in", str(src), "-out", str(out),
               *(["-split", str(split)] if str(split) not in ("0", "") else [])]
        for _, c in live:
            cmd += ["-params", ",".join(map(str, rev_params if c == "R" else send_params))]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"dsp_host failed:\n{r.stdout[-3000:]}{r.stderr[-2000:]}")
    if verbose:
        print(r.stdout)

    # dsp_host writes instance 0 to `out` and instance k to `out.iK`. The reverb
    # is not necessarily instance 0 any more -- under a layout like "SR" a SEND
    # occupies position 0 -- so read back whichever stream the reverb produced.
    ridx = 0 if direct else next(i for i, (_, c) in enumerate(live) if c == "R")
    got = out if ridx == 0 else pathlib.Path(f"{out}.i{ridx}")
    a = array.array("i")
    a.frombytes(got.read_bytes())
    for f in [src, out] + [pathlib.Path(f"{out}.i{i}") for i in range(1, 8)]:
        f.unlink(missing_ok=True)
    return list(a[0::2])[pad:], list(a[1::2])[pad:]   # the REVERB's stream


# ---- analysis ------------------------------------------------------------
def fft(x):
    """Iterative radix-2 FFT; len(x) must be a power of two."""
    n = len(x)
    j = 0
    x = list(x)
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            x[i], x[j] = x[j], x[i]
    ln = 2
    while ln <= n:
        step = cmath.exp(-2j * math.pi / ln)
        for i in range(0, n, ln):
            wv = 1 + 0j
            for k in range(i, i + ln // 2):
                u = x[k]
                v = x[k + ln // 2] * wv
                x[k] = u + v
                x[k + ln // 2] = u - v
                wv *= step
        ln <<= 1
    return x


def analyse(sig, label):
    """Report the spur floor of a steady-state window. Returns (ratio_dB, rms)."""
    rms = math.sqrt(sum(v * v for v in sig) / max(len(sig), 1)) / 8388607
    # Take the window from the LAST part of the tone, so the tank is fully
    # built up and the measurement is steady state.
    if len(sig) < NFFT:
        die(f"{label}: only {len(sig)} samples, need {NFFT}")
    seg = sig[-NFFT:]
    pk = max(abs(v) for v in seg) / 8388607
    if pk < 1e-4:
        return None, rms, pk, []

    hann = [0.5 - 0.5 * math.cos(2 * math.pi * i / NFFT) for i in range(NFFT)]
    spec = fft([complex(seg[i] * hann[i] / 8388607, 0) for i in range(NFFT)])
    half = NFFT // 2
    mag = [abs(spec[i]) for i in range(half)]

    # Hann spreads a pure tone over ~3 bins; exclude a small guard band so the
    # window's own skirts are not counted as spurs.
    guard = 4
    fund = sum(m * m for m in mag[TONE_BIN - guard:TONE_BIN + guard + 1])

    # HARMONICS ONLY. The engine's LFO puts legitimate sidebands within a few Hz
    # of the fundamental, and how much depends on parameters whose slot meanings
    # MOVED across the commits being bisected (the v92 page-2 rejig) -- so a
    # broadband spur count is not comparable between versions. Energy at 2f, 3f,
    # 5f... is: modulation cannot make it, and it is what "metallic" sounds like.
    harm = []
    for h in range(2, 10):
        b = TONE_BIN * h
        if b + guard >= half:
            break
        e = sum(m * m for m in mag[b - guard:b + guard + 1])
        harm.append((h, b * SR / NFFT, 10 * math.log10(max(e, 1e-30) / max(fund, 1e-30))))
    thd = 10 * math.log10(
        max(sum(10 ** (d / 10) for _, _, d in harm), 1e-30))

    tops = sorted(((m, i) for i, m in enumerate(mag)
                   if abs(i - TONE_BIN) > guard and i > 2), reverse=True)[:4]
    peak = math.sqrt(max(fund, 1e-30))
    tops = [(i * SR / NFFT, 20 * math.log10(max(m, 1e-30) / peak)) for m, i in tops]
    return thd, rms, pk, (harm, tops)


def write_wav(path, L, R):
    b = bytearray()
    for l, r in zip(L, R):
        for s in (l, r):
            s = max(-8388608, min(8388607, int(s)))
            b += (s & 0xFFFFFF).to_bytes(3, "little")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(3); w.setframerate(SR)
        w.writeframes(bytes(b))


# reverb: MOD and SPEED forced to 0 (modulation makes legitimate sidebands and
# would swamp the metric), MIX full wet, LP wide open.
REV_PARAMS  = [64, 0, 127, 0, 127, 127, 0, 0, 64, 0]
# send: x:(r6+0) = ->DELAY level, x:(r6+1) = ->REVERB level
SEND_PARAMS = [0, 127, 0, 0, 0, 0, 0, 0, 0, 0]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default="out/mainos_bus.bin")
    ap.add_argument("--mem", help="skip the dump and use this .mem")
    ap.add_argument("--build", action="store_true", help="run build_bus.py first")
    ap.add_argument("--dur", type=float, default=1.5, help="tone seconds (default 1.5)")
    ap.add_argument("--tail", type=float, default=0.5)
    ap.add_argument("--wav", help="also write the reverb output here")
    ap.add_argument("--label", default="send->reverb")
    ap.add_argument("--amp", type=float, default=0.5, help="tone amplitude FS")
    ap.add_argument("--level", type=int, default=127, help="SEND ->REVERB level 0..127")
    ap.add_argument("--mix", type=int, default=127, help="reverb MIX 0..127")
    ap.add_argument("--time", type=int, default=64,
                    help="TIME/decay (slot 0). MODE scales this by its own decay\nconstant in r7+$1e -- BIG's is 1.000000, i.e. NO headroom.")
    ap.add_argument("--mod", type=int, default=0,
                    help="MOD depth (slot 1). Zeroed in the THD tests to keep LFO\nsidebands out of the metric -- which also suppressed any\ninterpolation artifact the modulation would have caused.")
    ap.add_argument("--shmr", type=int, default=0,
                    help="SHIMMER amount (param slot 6 -> r6+$b). v101 replaced\nSPEED with SHMR; render_reverb.py still calls this slot SPEED.\nBuilds before 41d252c default it to 48, not 0.")
    ap.add_argument("--in", dest="infile",
                    help="source .wav instead of the tone (THD is then not meaningful)")
    ap.add_argument("--split", default="0",
                    help="frames in the a=0 sub-block call. NONZERO IS THE POST-TRIG\nSTATE: proc() runs TWICE a block and the bus split bookkeeping\n(r7+$65/$66/$67) actually executes. Split 0 never touches it.")
    ap.add_argument("--layout", default="RS",
                    help="dispatch slots in hardware order: R=reverb, S=send, .=neither. "
                         "Slot 0 is position 0, the housekeeper. e.g. SR, .RS, SSR")
    ap.add_argument("--direct", action="store_true",
                    help="CONTROL: no SEND, tone into the reverb's own input")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    if a.build:
        r = subprocess.run([sys.executable, "tools/build_bus.py"], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:
            die(f"build_bus.py failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    if not HOST.exists():
        die(f"missing {HOST.relative_to(ROOT)} -- run ./setup.sh")

    mem = pathlib.Path(a.mem) if a.mem else dump_mem(ROOT / a.image,
                                                     ROOT / "out/dsp/_send_probe_A.mem")
    rev = list(REV_PARAMS); rev[5] = a.mix; rev[6] = a.shmr; rev[1] = a.mod
    rev[0] = a.time
    snd = list(SEND_PARAMS); snd[1] = a.level
    wsrc = None
    if a.infile:
        sys.path.insert(0, str(ROOT / 'tools'))
        import render_reverb
        wsrc, sr = render_reverb.read_wav(pathlib.Path(a.infile))
        if sr != SR:
            wsrc = render_reverb.resample(wsrc, sr, SR)
    L, R = run(mem, a.dur, a.tail, rev, snd, a.verbose, a.amp, a.direct, wsrc, a.split, a.layout)
    thd, rms, pk, extra = analyse(L, a.label) if not a.infile else (None, 0, 0, None)
    if a.infile:
        pk = max((abs(v) for v in L + R), default=0) / 8388607
        print(f'{a.label}: {a.infile} through '
              f"{'REVERB direct (CONTROL)' if a.direct else 'SEND -> bus -> REVERB'}"
              f'  amp {a.amp}  peak {pk:.3f} FS')
        if a.wav:
            write_wav(ROOT / a.wav if not os.path.isabs(a.wav) else a.wav, L, R)
            print(f'  -> {a.wav}')
        return 0

    path = "REVERB direct input (CONTROL)" if a.direct else "SEND -> bus -> REVERB"
    print(f"{a.label}:  tone {TONE_HZ:.2f} Hz through {path} "
          f"(amp {a.amp}, ->REVERB {a.level})")
    if thd is None:
        print(f"  !! SILENT (peak {pk:.2e}, rms {rms:.2e}) -- the bus carried nothing.")
        print("     A silent render is a FAILED measurement, not a clean one.")
    else:
        harm, tops = extra
        print(f"  peak {pk:5.3f} FS   rms {20*math.log10(max(rms,1e-9)):6.1f} dBFS")
        print(f"  THD (2f..9f) = {thd:6.2f} dB      <- the metric")
        print("  harmonics: " + "  ".join(f"{h}f {d:6.1f}" for h, _, d in harm))
        print("  loudest spurs: " + "  ".join(f"{f:.0f}Hz {d:.0f}dB" for f, d in tops))
    if a.wav:
        write_wav(ROOT / a.wav if not os.path.isabs(a.wav) else a.wav, L, R)
        print(f"  -> {a.wav}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
