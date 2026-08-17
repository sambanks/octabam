#!/usr/bin/env python3
"""
Render a REAL send path -- SEND client -> shared bus -> a SERVER -- in the
emulator, and measure the metallic artifact numerically.

    python3 tools/send_probe.py                     # current working tree
    python3 tools/send_probe.py --wav out/send.wav  # ... and keep the audio

DRIVING THE DELAY. --layout takes D as well as R, so the DELAY SERVER can be
run and heard locally:

    DEV=1 XBUS=1 python3 tools/build_bus.py   # -> out/dsp/mem_dev_A.mem
    python3 tools/send_probe.py --mem out/dsp/mem_dev_A.mem --layout DS

(NOSHIM=1 was load-bearing for a few hours on 12 Aug 2026 -- R16-R18 grew
ChonVerb past what the donor region could hold with all three servers packed
in. The same evening's DEV placement change moved the delay OUT of the region
to P:0x04000, appended to the .mem dump -- see build_bus.py's DEV_DELAY_P --
so the full-shimmer reverb fits again and NOSHIM is back to optional.)

This needs a DEV=1 image and there is no way around it: XBUS=1 stubs the DELAY
SERVER out, and the specialized build that follows puts BongDelay in payload B
only -- which dsp_host cannot boot (REVERB.md). Against either, `--layout DS`
renders digital silence from a 10-word stub -- or, on a SPEC dump, a dry
passthrough from the DELAY->SEND id alias, which entry() now refuses to run.
The silence check below reports silence as a FAILED measurement rather than a
clean one.

The two buses have SEPARATE send knobs -- x:(r6+0) is ->DELAY, x:(r6+1) is
->REVERB -- so --level follows whichever server is being measured and --dlevel
overrides it. Driving the reverb's knob while measuring the delay renders
silence, which cost a confusing first run.

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
XBUS.md. (Instance numbering only -- on hardware ChonVerb serves
TRACKS 5-8, payload B's BongDelay serves 1-4; the old 'track 1 ChonVerb'
label predates the 10 Aug track<->core inversion measurement.)

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

REVERB_ID, SEND_ID, DELAY_ID = 0x07, 0x09, 0x06
INIT_TAB, PROC_TAB = 0x215, 0x235
SERVER_ID = {"R": REVERB_ID, "S": SEND_ID, "D": DELAY_ID}

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
        direct=False, wave_src=None, split=0, layout='RS', delay_params=None,
        inall=False,
        pick=None):
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

    # Resolved lazily, per character actually used: a build that stubbed an
    # effect out still has a dispatch entry, but a build that never placed it
    # would die here -- and dying with "no dispatch entry for 0x06" is the
    # right failure for `--layout DS` against a non-DEV image.
    ep = {}

    def entry(c):
        if c not in ep:
            ep[c] = entry_points(mem, SERVER_ID[c])
            # A SPEC build has NO delay in payload A -- build_bus.py aliases id
            # 0x06 to the SEND client so a wrong chooser pick becomes a send.
            # Locally that alias resolves to a perfectly plausible entry point
            # and renders a dry passthrough: silence over the bus, dry in a
            # --direct control. That cost a session on 12 Aug 2026 ("BongDelay
            # outputs nothing in any config" -- it was never instantiated).
            # The dispatch table cannot distinguish the alias from real code,
            # but DELAY == SEND can never be legitimate: die, don't measure.
            if c == "D" and ep["D"] == entry_points(mem, SERVER_ID["S"]):
                die("this dump's DELAY entry is the SEND alias -- a SPEC build "
                    "(payload A carries no delay). Build the delay hatch:\n"
                    "  DEV=1 XBUS=1 python3 tools/build_bus.py\n"
                    "then rerun against out/dsp/mem_dev_A.mem")
        return ep[c]

    # --direct is the CONTROL for whichever server is being measured, so it has
    # to instantiate THAT server. Running a reverb and labelling it a delay
    # control is precisely the class of mislabel this project has lost sessions
    # to, and here it would silently compare two different effects.
    dpar = delay_params if delay_params is not None else DELAY_PARAMS
    tgt = pick or ("R" if "R" in layout.upper() else "D")
    live = [(0, tgt)]
    if direct:
        ri, rp = entry(tgt)
        cmd = [str(HOST), "-mem", str(mem),
               "-init", f"{ri:x}", "-proc", f"{rp:x}",
               "-inst", "1", "-r7", "2", "-alloc", "1",
               "-inmask", "1",                   # tone straight into the server
               "-blocks", str(blocks), "-in", str(src), "-out", str(out),
               *(["-split", str(split)] if str(split) not in ("0", "") else []),
               "-params", ",".join(map(str, rev_params if tgt == "R" else dpar))]
    else:
        # Nothing in send_client divides by the number of clients, so N sends put
        # N x the contribution into one accumulator word.
        # layout: one char per DISPATCH SLOT, in hardware order.
        #   R = REVERB SERVER, D = DELAY SERVER, S = SEND, . = a track running
        #       neither (NONE or a stock effect -- our code never runs there, so
        #       the slot is simply skipped and nobody housekeeps from it)
        # Slot 0 is position 0 (r7 0x6200), the designated housekeeper. Putting
        # anything other than R there is what makes send_client's self-healing
        # election actually run, and that path never executed in any earlier test.
        #
        # D needs a DEV=1 image (tools/build_bus.py): XBUS=1 stubs the DELAY
        # SERVER out, and the specialized build puts it in payload B, which
        # dsp_host cannot boot. Against either of those `--layout DS` renders
        # silence from a 10-word stub rather than failing, which is why the
        # silence check below is a FAILED measurement and not a clean one.
        slots = [c for c in layout.upper() if c in "RDS."]
        live = [(k, c) for k, c in enumerate(slots) if c != "."]
        n = len(live)
        if not any(c in "RD" for _, c in live):
            die(f"layout {layout!r} has no server -- needs an R or a D")
        r7s = ",".join(str(2 + 2 * k) for k, _ in live)
        als = ",".join(str(1 + 2 * k) for k, _ in live)
        # The tone normally reaches the SENDs only, so a SERVER's own track
        # is SILENT and its dry path is never exercised -- MIX=0 renders
        # digital silence. That is fine for measuring an engine and useless
        # for measuring a DRY/WET BLEND, which is a hardware-only behaviour
        # every local render was blind to until 12 Aug 2026. --inall feeds
        # every live slot, so the delay's own dry is real and MIX can be
        # measured for what it does on the unit.
        inmask = sum(1 << i for i, (_, c) in enumerate(live)
                     if c == "S" or inall)
        par = {"R": rev_params, "S": send_params, "D": dpar}
        cmd = [str(HOST), "-mem", str(mem),
               "-init", ",".join(f"{entry(c)[0]:x}" for _, c in live),
               "-proc", ",".join(f"{entry(c)[1]:x}" for _, c in live),
               "-inst", str(n), "-r7", r7s, "-alloc", als,
               "-inmask", str(inmask),                # tone to the SENDs only
               "-blocks", str(blocks), "-in", str(src), "-out", str(out),
               *(["-split", str(split)] if str(split) not in ("0", "") else [])]
        for _, c in live:
            cmd += ["-params", ",".join(map(str, par[c]))]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"dsp_host failed:\n{r.stdout[-3000:]}{r.stderr[-2000:]}")
    if verbose:
        print(r.stdout)

    # dsp_host writes instance 0 to `out` and instance k to `out.iK`. The server
    # is not necessarily instance 0 any more -- under a layout like "SR" a SEND
    # occupies position 0 -- so read back whichever stream the server produced.
    # `pick` chooses which when a layout runs both servers (e.g. "RDS", where
    # the delay's wet feeds the reverb): default to R if present, else D.
    ridx = 0 if direct else next(i for i, (_, c) in enumerate(live) if c == tgt)
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
# delay: build_bus.py's DEFAULTS for DELAY SERVER, which are the knob positions
# a fresh part boots with -- TIME FDBK TONE PING MIX, then VRBW, then index 8 =
# VRBD ($d's knob field). MIX 90 so a render is audibly wet without argument.
# TIME FDBK TONE PING IN ... -- slot 4 is IN, this track's own send level into
# the delay, NOT the old MIX crossfade (v3 stage 1). It defaults to 0 here for
# the same reason it defaults to 0 in build_bus.py: IN>0 registers the host as
# a bus client and the 1/N auto-gain then gives it a share it does not use,
# quietly halving every real sender. The old 90 sitting here would have done
# exactly that to every measurement taken from now on -- the SHMR/SPEED=0
# lesson, which polluted every render until Round 12 caught it.
DELAY_PARAMS = [40, 60, 100, 64, 0, 0, 0, 0, 0, 0]


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
    ap.add_argument("--dlevel", type=int, default=None,
                    help="SEND ->DELAY level 0..127 (x:(r6+0)). Defaults to\n"
                         "--level when the target is the DELAY, else 0 -- the\n"
                         "two buses have SEPARATE send knobs, and driving the\n"
                         "reverb's while measuring the delay renders silence.")
    ap.add_argument("--mix", type=int, default=127, help="reverb MIX 0..127")
    ap.add_argument("--time", type=int, default=64,
                    help="TIME/decay (slot 0). MODE scales this by its own decay\nconstant in r7+$1e -- BIG's is 1.000000, i.e. NO headroom.")
    ap.add_argument("--mod", type=int, default=0,
                    help="MOD depth (slot 1). Zeroed in the THD tests to keep LFO\nsidebands out of the metric -- which also suppressed any\ninterpolation artifact the modulation would have caused.")
    ap.add_argument("--shmr", type=int, default=0,
                    help="SHIMMER amount (param slot 6 -> r6+$b). v101 replaced\nSPEED with SHMR; render_reverb.py still calls this slot SPEED.\nBuilds before 41d252c default it to 48, not 0.")
    ap.add_argument("--dtime", type=int, default=None,
                    help="DELAY TIME 0..127 (delay slot 0, default 40 -- the\nboot default). PITCH mode caps the lag at 14335 samples,\ni.e. TIME ~111.")
    ap.add_argument("--dfdbk", type=int, default=None,
                    help="DELAY FDBK 0..127 (delay slot 1, default 60)")
    ap.add_argument("--dwow", type=int, default=None,
                    help="DELAY WOW depth 0..127 (delay slot 6, default 0).\n"
                         "TAPE's wow/flutter depth; ignored by the other modes.")
    ap.add_argument("--dmix", "--din", type=int, default=None, dest="dmix",
                    help="DELAY IN 0..127 (delay slot 4, default 0) -- this\n"
                         "track's OWN send level into the delay. Was MIX, a\n"
                         "dry/wet crossfade, until v3 stage 1 made the host\n"
                         "track a return whose output is the wet alone.\n"
                         "--din is the name that matches the panel; --dmix\n"
                         "still works so older command lines do not break,\n"
                         "but they now mean something different.")
    ap.add_argument("--dtone", type=int, default=None,
                    help="DELAY TONE 0..127 (delay slot 2, default 100)")
    ap.add_argument("--dping", type=int, default=None,
                    help="DELAY PING 0..127 (delay slot 3, default 64)")
    ap.add_argument("--inall", action="store_true",
                    help="feed the source to EVERY live slot, not just the\n"
                         "SENDs. Without it a server's own track is silent and\n"
                         "its DRY path -- and therefore MIX -- cannot be\n"
                         "measured locally at all.")
    ap.add_argument("--dspray", type=int, default=None,
                    help="DELAY SPRAY 0..127 (delay slot 10, default 0).\n"
                         "GRAIN's scatter depth: 0 puts all four grains on one\n"
                         "read position, 127 spreads them over 1015 samples.\n"
                         "Only read in GRAIN (DMODE=3); inert elsewhere.")
    ap.add_argument("--dvrbw", type=int, default=None,
                    help="DELAY ->VERB WET 0..127 (delay slot 5, default 0).\n"
                         "The delay's own cross-send into the REVERB bus --\n"
                         "the delay->reverb topology (PLAN 3). Needs a layout\n"
                         "carrying both servers, e.g. --layout RDS --pick R.")
    ap.add_argument("--in", dest="infile",
                    help="source .wav instead of the tone (THD is then not meaningful)")
    ap.add_argument("--split", default="0",
                    help="frames in the a=0 sub-block call. NONZERO IS THE POST-TRIG\nSTATE: proc() runs TWICE a block and the bus split bookkeeping\n(r7+$65/$66/$67) actually executes. Split 0 never touches it.")
    ap.add_argument("--layout", default="RS",
                    help="dispatch slots in hardware order: R=reverb, D=delay, "
                         "S=send, .=neither. Slot 0 is position 0, the "
                         "housekeeper. e.g. SR, .RS, SSR, DS. D needs a DEV=1 "
                         "image (see build_bus.py)")
    ap.add_argument("--pick", choices=["R", "D"],
                    help="which server's output to analyse when the layout runs "
                         "both (default: R if present, else D)")
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
        die(f"missing {HOST.relative_to(ROOT)} -- run 'make setup'")

    mem = pathlib.Path(a.mem) if a.mem else dump_mem(ROOT / a.image,
                                                     ROOT / "out/dsp/_send_probe_A.mem")
    rev = list(REV_PARAMS); rev[5] = a.mix; rev[6] = a.shmr; rev[1] = a.mod
    rev[0] = a.time
    # Which server is being measured decides which SEND knob has to be up.
    _tgt = "D" if (a.pick == "D" or "R" not in a.layout.upper()) else "R"
    snd = list(SEND_PARAMS)
    snd[1] = a.level                                    # ->REVERB, x:(r6+1)
    snd[0] = a.dlevel if a.dlevel is not None else (a.level if _tgt == "D" else 0)
    wsrc = None
    if a.infile:
        sys.path.insert(0, str(ROOT / 'tools'))
        import render_reverb
        wsrc, sr = render_reverb.read_wav(pathlib.Path(a.infile))
        if sr != SR:
            wsrc = render_reverb.resample(wsrc, sr, SR)
    dpar = None
    if any(v is not None for v in (a.dtime, a.dfdbk, a.dmix, a.dvrbw, a.dwow,
                                   a.dtone, a.dping, a.dspray)):
        dpar = list(DELAY_PARAMS)
        for idx, val in ((0, a.dtime), (1, a.dfdbk), (2, a.dtone), (3, a.dping),
                         (4, a.dmix), (5, a.dvrbw), (6, a.dwow), (9, a.dspray)):
            if val is not None:
                dpar[idx] = val
    L, R = run(mem, a.dur, a.tail, rev, snd, a.verbose, a.amp, a.direct, wsrc,
               a.split, a.layout, delay_params=dpar, pick=a.pick,
               inall=a.inall)
    thd, rms, pk, extra = analyse(L, a.label) if not a.infile else (None, 0, 0, None)
    if a.infile:
        pk = max((abs(v) for v in L + R), default=0) / 8388607
        _srv = "DELAY" if (a.pick == "D" or "R" not in a.layout.upper()) else "REVERB"
        print(f'{a.label}: {a.infile} through '
              f"{_srv + ' direct (CONTROL)' if a.direct else 'SEND -> bus -> ' + _srv}"
              f'  amp {a.amp}  peak {pk:.3f} FS')
        if a.wav:
            write_wav(ROOT / a.wav if not os.path.isabs(a.wav) else a.wav, L, R)
            print(f'  -> {a.wav}')
        return 0

    _srv = "DELAY" if (a.pick == "D" or "R" not in a.layout.upper()) else "REVERB"
    path = (f"{_srv} direct input (CONTROL)" if a.direct
            else f"SEND -> bus -> {_srv}")
    print(f"{a.label}:  tone {TONE_HZ:.2f} Hz through {path} "
          f"(amp {a.amp}, ->REVERB {snd[1]}, ->DELAY {snd[0]})")
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
