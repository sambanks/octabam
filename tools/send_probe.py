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
BusVerb past what the donor region could hold with all three servers packed
in. The same evening's DEV placement change moved the delay OUT of the region
to P:0x04000, appended to the .mem dump -- see build_bus.py's DEV_DELAY_P --
so the full-shimmer reverb fits again and NOSHIM is back to optional.)

This needs a DEV=1 image and there is no way around it: XBUS=1 stubs the DELAY
SERVER out, and the specialized build that follows puts BusDelay in payload B
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

  * BusVerb never WRITES the REVERB accumulator. It reads it (r7+$63) and
    writes the DELAY accumulator (r7+$68). Only modules/send/send_client.asm writes the
    REVERB one, so with no SEND instance the reverb reads an all-zero buffer.
  * The server-role lock (modules/busverb/reverb_server.asm, y:>$982) makes a second
    REVERB SERVER instance rts immediately as a dry passthrough.
  * dsp_host took ONE -init/-proc pair, so every instance ran the same effect.

The third is now fixed: -init/-proc take a list, one entry point per instance.
This script uses that to run instance 0 = REVERB SERVER (r7 0x6200, position 0,
the housekeeper) and instance 1 = SEND (r7 0x6400) -- the hardware layout from
XBUS.md. (Instance numbering only -- on hardware BusVerb serves
TRACKS 5-8, payload B's BusDelay serves 1-4; the old 'track 1 BusVerb'
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

INIT_TAB, PROC_TAB = 0x215, 0x235

# Ids and the layout alphabet come from the module manifests. A layout string
# is one letter per dispatch slot, and each letter is whichever module claims
# it -- so a new server becomes selectable here by declaring a layout_char,
# not by editing this file.
sys.path.insert(0, str(ROOT / "tools"))
from remix import registry  # noqa: E402

SERVER_ID = {m.harness.layout_char: m.menu.fx2_id
             for m in registry.modules().values()
             if m.harness is not None and m.harness.layout_char
             and m.menu is not None}
# The layout ALPHABET, derived. It used to be the literal "RDS." in two
# places, so a module could declare a layout_char, have it resolved into
# SERVER_ID above, and still be silently dropped from every layout string --
# which is what happened to all six inserts: they had to be driven through
# dsp_host by hand. `.` means a track running neither (NONE, or a stock
# effect): our code never runs there, so the slot is simply skipped.
LAYOUT_CHARS = set(SERVER_ID) | {"."}
# Which of them own a bus accumulator and can therefore be MEASURED as the
# target of a send. An insert has no bus role, so a layout of nothing but
# inserts has nothing to analyse -- that is what the check below is for.
SERVER_CHARS = {m.harness.layout_char for m in registry.modules().values()
                if m.harness is not None and m.harness.layout_char
                and m.harness.is_server}
# Every module's own declared defaults, as a -params list. A module the CLI
# has no flags for still needs SOMETHING sensible on its knobs, and the
# manifest is where that is already written down.
MODULE_DEFAULTS = {m.harness.layout_char: [(p.default or 0) for p in m.params]
                   for m in registry.modules().values()
                   if m.harness is not None and m.harness.layout_char
                   and m.params}
REVERB_ID = SERVER_ID.get("R")
SEND_ID = SERVER_ID.get("S")
DELAY_ID = SERVER_ID.get("D")

# CLI flag -> the module's own knob NAME, and the SLOT then comes from the
# manifest. The flag names are historical and several no longer match the
# panel -- --dwow drives DPTH, --dmix drives IN, --dspray drives the host's
# -DEL send (slot 10, DRV until 5 Sep 2026),
# --width drives SHFT -- so they are kept as aliases for existing invocations
# and docs while the index they resolve to stays honest.
#
# This indirection is the point. The slot numbers used to be written out here
# by hand, and twice they were wrong: SPRAY sat on slot 9 until it was found
# to be retuning the pitch select, and --din drove -VRB for five days after
# the IN/-VRB swap, which made a delay makeup test measure +0.0 dB. Both were
# a wrapper that had not been audited after a slot moved. There is now
# nothing to audit.
REV_FLAGS = {"time": "TIME", "mod": "MOD", "mix": "IN", "shmr": "SHMR",
             "rmode": "MODE", "width": "SHFT", "gate": "GATE", "rrate": "RATE",
             # v8 (5 Sep 2026): TONE and -DEL replaced HP/LP on slots 3/4.
             "rtone": "TONE", "rdel": "-DEL"}
DELAY_FLAGS = {"dtime": "TIME", "dfdbk": "FDBK", "dtone": "TONE",
               "dping": "PING", "dvrbw": "-VRB", "dmix": "PTCH", "dwow": "MDEP",
               "dmode": "MODE", "drate": "MRAT", "dptch": "SIZE",
               "dspray": "-DEL", "dfrz": "FRZE"}


def _slots(key, flags):
    """flag name -> slot index, resolved through the module's knob map."""
    kmap = registry.by_key(key).knob_map()
    missing = [n for n in flags.values() if n not in kmap]
    if missing:
        die(f"{key} has no knob named {missing} -- send_probe's flag table "
            f"and the manifest disagree")
    return {f: kmap[n] for f, n in flags.items()}

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
    # ⚠️ THIS BOUND HAS BEEN WRONG TWICE, BOTH TIMES BY BEING FITTED TO THE
    # EFFECTS THAT HAPPENED TO HAVE BEEN RENDERED. `proc == init + 1` was the
    # first test, an accident of every init being a bare `rts`; it broke on
    # 17 Aug 2026 when the bus clients gained a rotation seed. `init + 64`
    # was the second, and it broke on 2 Sep 2026 the moment the three stock
    # reverbs became renderable -- they seed a tank, so their init is real
    # code. Both failed as "implausible entry points", which reads like a
    # stale dispatch table rather than a tool assumption.
    #
    # MEASURED, every effect in the pristine image (payload A) plus ours:
    #   ours, and stock DELAY        1
    #   the other ten stock effects  5..32   (max CHORUS 32)
    #   PLATE / SPRING / DARK REV    85 / 108 / 162
    # So 256: comfortably past the real maximum, and still tight enough that
    # a wrong table -- which gives a wild address or proc before init -- is
    # caught. The invariant itself is unchanged: proc follows init, and init
    # seeds per-instance state rather than processing audio.
    _MAX_INIT = 256
    if not 0 < init < 0x20000 or not init < proc <= init + _MAX_INIT:
        die(f"implausible entry points for 0x{fxid:02x}: init 0x{init:05x} "
            f"proc 0x{proc:05x} (want init < proc <= init+{_MAX_INIT})")
    return init, proc


# ---- the run -------------------------------------------------------------
def run(mem, dur, tail, rev_params, send_params, verbose=False, amp=0.5,
        direct=False, wave_src=None, split=0, layout='RS', delay_params=None,
        inall=False,
        pick=None, tempo=None, insert_params=None, feed=None):
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
            # --direct control. That cost a session on 12 Aug 2026 ("BusDelay
            # outputs nothing in any config" -- it was never instantiated).
            # The dispatch table cannot distinguish the alias from real code,
            # but DELAY == SEND can never be legitimate: die, don't measure.
            if c == "D" and ep["D"] == entry_points(mem, SERVER_ID["S"]):
                die("this dump's DELAY entry is the SEND alias -- a SPEC build "
                    "(payload A carries no delay). Build the delay hatch:\n"
                    "  DEV=1 XBUS=1 python3 tools/build_bus.py\n"
                    "then rerun against out/dsp/mem_dev_A.mem")
            # The same trap generalizes to every module: an id absent from
            # the image dispatches to the fallback (SPEC aliases it to SEND),
            # which renders a PLAUSIBLE DRY PASSTHROUGH -- peak == amp, THD at
            # the noise floor, no error anywhere. Reproduced 31 Aug 2026 with
            # --pick B against a `bus` image (no BodeShift in it). Check
            # which code the entry actually points at before running it.
            if c != "S" and ep[c] == entry_points(mem, SERVER_ID["S"]):
                _m = registry.by_id(SERVER_ID[c])
                die(f"this dump's {_m.name} entry is the SEND alias -- the "
                    f"module is not in this image, so the render would be a "
                    f"dry passthrough. Build a remix that includes it.")
        return ep[c]

    # --direct is the CONTROL for whichever server is being measured, so it has
    # to instantiate THAT server. Running a reverb and labelling it a delay
    # control is precisely the class of mislabel this project has lost sessions
    # to, and here it would silently compare two different effects.
    dpar = delay_params if delay_params is not None else DELAY_PARAMS
    _present = [c for c in layout.upper() if c in SERVER_CHARS]
    tgt = pick or ("R" if "R" in layout.upper() else
                   "D" if "D" in layout.upper() else
                   (_present[0] if _present else None))
    # ⚠️ NO SILENT FALLBACK TO "R". It used to default to the reverb when it
    # could not work out a target, which meant `--direct` on an insert
    # rendered BusVerb and said so in the wrong words. If we cannot tell what
    # to run, say so.
    if tgt is None or tgt not in SERVER_ID:
        die(f"cannot tell which module to render from layout {layout!r}. "
            f"Pass --pick <letter> -- one of {''.join(sorted(SERVER_ID))} "
            f"(see --layout help).")
    live = [(0, tgt)]
    if direct:
        ri, rp = entry(tgt)
        # Params for whichever module is being rendered: the two servers keep
        # their CLI-driven sets, anything else uses its own manifest defaults
        # unless --set built an override list.
        _par = (rev_params if tgt == "R" else dpar if tgt == "D"
                else insert_params if insert_params is not None
                else MODULE_DEFAULTS.get(tgt, [0] * 12))
        # THE AUDIO BLOCK IS AT X:0 ON HARDWARE (the dispatcher's `move #$0,r0`,
        # P:0x42e) and the STOCK effects use the X memory right after it as
        # scratch -- the flanger writes X:0x20-0xff every block. dsp_host's
        # default puts the audio at X:0x80, inside that scratch, which turned
        # the flanger's output into a Nyquist-rate alternation (+0.94/-0.02)
        # and cost a false "not credible" verdict (2 Sep 2026). None of our
        # own modules touch low X, so the default never mattered for them;
        # a stock render gets the hardware address.
        _tm = registry.by_id(SERVER_ID[tgt])
        # An FX1-ONLY module (Claims.fx1_only) passes dry on an FX2 slot,
        # so its render is an FX1 instance: state block 0x6100 and the
        # allocator's first FX1 entry (Y:0x1000). Everything else renders
        # as FX2 instance 1 (0x6200 / Y:0x4000), as it always has.
        _fx1o = (_tm is not None and getattr(_tm, "claims", None) is not None
                 and _tm.claims.fx1_only)
        cmd = [str(HOST), "-mem", str(mem),
               "-init", f"{ri:x}", "-proc", f"{rp:x}",
               "-inst", "1", "-r7", "1" if _fx1o else "2",
               "-alloc", "0" if _fx1o else "1",
               "-inmask", "1",                   # tone straight into the module
               *(["-audio", "0"] if _tm is not None and _tm.is_stock else []),
               "-blocks", str(blocks), "-in", str(src), "-out", str(out),
               *(["-split", str(split)] if str(split) not in ("0", "") else []),
               "-params", ",".join(map(str, _par))]
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
        slots = [c for c in layout.upper() if c in LAYOUT_CHARS]
        live = [(k, c) for k, c in enumerate(slots) if c != "."]
        n = len(live)
        if not any(c in SERVER_CHARS for _, c in live):
            die(f"layout {layout!r} has no bus server to measure -- needs one "
                f"of {''.join(sorted(SERVER_CHARS))}. The others "
                f"({''.join(sorted(set(SERVER_ID) - SERVER_CHARS))}) either "
                f"feed a bus (SEND) or are inserts that process their own "
                f"track's frames, so there is no accumulator to analyse; "
                f"render an insert with --direct instead")
        r7s = ",".join(str(2 + 2 * k) for k, _ in live)
        als = ",".join(str(1 + 2 * k) for k, _ in live)
        # The tone normally reaches the SENDs only, so a SERVER's own track
        # is SILENT and its dry path is never exercised -- MIX=0 renders
        # digital silence. That is fine for measuring an engine and useless
        # for measuring a DRY/WET BLEND, which is a hardware-only behaviour
        # every local render was blind to until 12 Aug 2026. --inall feeds
        # every live slot, so the delay's own dry is real and MIX can be
        # measured for what it does on the unit.
        # `feed` names the letters whose tracks receive the tone (3 Sep
        # 2026: a station sends from its OWN track, so the tone has to reach
        # it and NOT the server, whose own dry would swamp the measurement).
        inmask = sum(1 << i for i, (_, c) in enumerate(live)
                     if c == "S" or inall or (feed and c in feed))
        # The three the CLI has flags for keep their flag-driven values;
        # anything else falls back to what its own manifest declares.
        par = dict(MODULE_DEFAULTS)
        par.update({"R": rev_params, "S": send_params, "D": dpar})
        if isinstance(insert_params, dict):     # per-letter overrides
            par.update(insert_params)
        cmd = [str(HOST), "-mem", str(mem),
               "-init", ",".join(f"{entry(c)[0]:x}" for _, c in live),
               "-proc", ",".join(f"{entry(c)[1]:x}" for _, c in live),
               "-inst", str(n), "-r7", r7s, "-alloc", als,
               "-inmask", str(inmask),                # tone to the SENDs only
               "-blocks", str(blocks), "-in", str(src), "-out", str(out),
               *(["-split", str(split)] if str(split) not in ("0", "") else [])]
        for _, c in live:
            cmd += ["-params", ",".join(map(str, par[c]))]
    if tempo:
        # what the ColdFire tempo cave publishes (r6+$6/$7); 24 Aug 2026
        cmd += ["-tempo", str(tempo)]
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


def analyse(sig, label, tone_end=None):
    """Report the spur floor of a steady-state window. Returns (ratio_dB, rms).

    ⚠️ THE DEFAULT WINDOW IS THE LAST NFFT SAMPLES OF THE BUFFER, which is
    the `--tail` SILENCE APPENDED AFTER THE TONE, not "the last part of the
    tone" this comment used to claim. A reverb hides that: its tail is a loud
    decaying one, so the window is full of signal. A MEMORYLESS module has
    nothing there, so the window is digital silence and the tool announced
    `SILENT -- the bus carried nothing` about a perfectly good render. That is
    what made every insert look broken (found 30 Aug 2026).

    The fix is deliberately ADDITIVE, not a correction of the window: every
    THD in `docs/VOICING.md` was measured against the tail, and moving the
    window silently would invalidate the lot (the reverb reads -36.5 dB on the
    tail and -21.7 dB on the tone -- they are different measurements, not a
    better and a worse one). So the tail stays the default, and `tone_end` is
    used only when the tail turns out to be silent. Anything comparing against
    a logged number keeps comparing against the same thing.
    """
    rms = math.sqrt(sum(v * v for v in sig) / max(len(sig), 1)) / 8388607
    if len(sig) < NFFT:
        die(f"{label}: only {len(sig)} samples, need {NFFT}")
    seg = sig[-NFFT:]
    pk = max(abs(v) for v in seg) / 8388607
    if pk < 1e-4 and tone_end is not None and tone_end >= NFFT:
        # No tail to measure -- a module with no memory. Fall back to the end
        # of the tone and SAY SO, because it is not the same measurement.
        seg = sig[tone_end - NFFT:tone_end]
        pk = max(abs(v) for v in seg) / 8388607
        if pk >= 1e-4:
            print("  (no tail: measured over the end of the TONE, so this THD "
                  "is not comparable with a server's tail figure)")
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
# 12 entries: page 1 (0..5), then the REAL page-2 slot map (6..11) --
# docs/PARAM_PAGES.md, settled 17 Aug 2026. Slots 7/9/11 are COMPANION fields
# (written to bits 8-15 of the same word as the preceding knob), drivable
# locally since dsp_host learned the map the same day; before that, no
# companion select was ever exercisable in the emulator and DMODE=/DINT=/DFRZ=
# build overrides were the only way in. Those overrides remain valid and are
# proven equivalent (param-driven MODE renders bit-identical to a MODE= build).
# idx5 is IN since the v4 RETURN (was MIX): 0, or every render registers a
# silent host client and dilutes the senders by 1/sqrt(N+1) -- exactly the
# phantom-client defect the DSP side just spent a day removing.
# idx11 is the RATE select (0.5/1/2/4x MOD speed) since 18 Aug 2026 -- 1 = 1x,
# the hardware boot default. 0 halved the MOD speed of every render between
# RATE's birth and this default catching up (both 18 Aug 2026).
# Slots 3/4 are TONE (64 = the old HP 0 / LP 127) and -DEL (0) since v8,
# 5 Sep 2026. The old `0, 127` here read as TONE 0 / -DEL 127 for one build:
# every verify-bus case went dark and the reverb host sent full-tilt into the
# delay bus -- the harness-knob-drift trap, again.
REV_PARAMS  = [64, 0, 127, 64, 0, 0, 0, 0, 64, 0, 0, 1]
# send: x:(r6+0) = ->DELAY level, x:(r6+1) = ->REVERB level
SEND_PARAMS = [0, 127, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
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
# idx8 = RATE, and 64 IS LOAD-BEARING (build_bus.py's own words): exactly 1x
# LFO speed, the pre-knob law. The 0 that sat here from RATE's birth (18 Aug
# 2026) until later the same day froze both drift LFOs, so every DPTH
# render between was wobble-free.
DELAY_PARAMS = [40, 60, 100, 64, 0, 0, 0, 0, 64, 0, 0, 0]


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
                    help="SHIMMER amount (param slot 7 since v7, 4 Sep 2026 -> the COMPANION field of r6+$c; slot 6's knob field before, NOT $b -- the $b\nreading is why the delay's WOW worked locally and never on hardware; see\nPARAM_PAGES.md). v101 replaced\nSPEED with SHMR; render_reverb.py still calls this slot SPEED.\nBuilds before 41d252c default it to 48, not 0.")
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
                         "track a return (wet alone v3..v4; since v5 the\n"
                         "host's dry rides under the wet at unity).\n"
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
                         "neither its IN feed nor (since v5) its unity dry\n"
                         "passthrough can be measured locally at all.")
    ap.add_argument("--drate", type=int, default=None,
                    help="DELAY RATE 0..127 (slot 8 KNOB, born 18 Aug 2026):\n"
                         "scales both drift LFO increments by val/64, so 64 is\n"
                         "exactly 1x and 0 freezes the wobble entirely.")
    ap.add_argument("--dspray", type=int, default=None,
                    help="DELAY SPRAY 0..127 (delay slot 10, default 0).\n"
                         "GRAIN's scatter depth: 0 puts all four grains on one\n"
                         "read position, 127 spreads them over 1015 samples.\n"
                         "Only read in GRAIN (DMODE=3); inert elsewhere.")
    ap.add_argument("--dvrbw", type=int, default=None,
                    help="delay -VRB 0..127 (p5) -- the delay's send into the\n"
                         "reverb, A KNOB AGAIN from 18 Aug 2026 (hardwired at\n"
                         "max v3..R29). Default 0: the wash is opt-in, and\n"
                         "registration follows the knob.")
    ap.add_argument("--dmode", type=int, default=None,
                    help="delay MODE 0..4 via the slot-7 COMPANION field --\n"
                         "runtime equivalent of the DMODE= build override\n"
                         "(proven bit-identical). 0=CLEAN 1=PITCH 2=TAPE\n"
                         "3=GRAIN 4=REVERSE.")
    ap.add_argument("--dptch", type=int, default=None,
                    help="delay PTCH select 0..3 (slot-9 companion; DINT=\n"
                         "equivalent). Interval in PITCH, interval SET in\n"
                         "GRAIN, segment SIZE in REVERSE.")
    ap.add_argument("--dfrz", type=int, default=None,
                    help="delay FREEZE 0/1 (slot-11 companion; DFRZ=\n"
                         "equivalent). Frozen from block 0 in a fixed-param\n"
                         "render, so the line holds silence -- see PLAN.")
    ap.add_argument("--rmode", type=int, default=None,
                    help="reverb MODE 0..2 via the slot-7 COMPANION field\n"
                         "(0=ROOM 1=PLATE 2=BIG) -- the --dmode twin. Default\n"
                         "ROOM: REV_PARAMS[7] stays 0, which was the ONLY\n"
                         "reachable mode here until 18 Aug 2026 (the panel\n"
                         "boots BIG; renders wanting it must say so).")
    ap.add_argument("--rrate", type=int, default=None,
                    help="reverb RATE select 0..3 = 0.5/1/2/4x MOD speed\n"
                         "(slot-11 companion, born 18 Aug 2026; default 1x).")
    ap.add_argument("--shft", "--width", type=int, default=None, dest="width",
                    help="reverb SHFT 0..3 (slot-9 companion): shimmer\n"
                         "interval +12/+19/+7/-12. Was WIDTH until v6\n"
                         "(23 Aug 2026; width is pinned wide now); --width\n"
                         "still parses so older command lines do not break,\n"
                         "but it selects the interval, not the image.")
    ap.add_argument("--gate", type=int, default=None,
                    help="reverb GATE 0..127 (slot-10 KNOB).")
    ap.add_argument("--rdel", type=int, default=None,
                    help="reverb -DEL 0..127 (page-1 slot 4, default 0): the\n"
                         "host's own dry send into the DELAY bus, back on\n"
                         "5 Sep 2026 (v8; retired 18 Aug 2026 -- the flag\n"
                         "was a no-op in between). Registration follows the\n"
                         "knob, so 0 takes no auto-gain share.")
    ap.add_argument("--rtone", type=int, default=None,
                    help="reverb TONE 0..127 (page-1 slot 3, default 64): the\n"
                         "old HP+LP pair on one knob -- below 64 darkens\n"
                         "(LP), above 64 thins (HP), 64 = HP 0 / LP 127.")
    ap.add_argument("--in", dest="infile",
                    help="source .wav instead of the tone (THD is then not meaningful)")
    ap.add_argument("--split", default="0",
                    help="frames in the a=0 sub-block call. NONZERO IS THE POST-TRIG\nSTATE: proc() runs TWICE a block and the bus split bookkeeping\n(r7+$65/$66/$67) actually executes. Split 0 never touches it.")
    _alpha = ", ".join(f"{c}={registry.by_id(SERVER_ID[c]).name}"
                       for c in sorted(SERVER_ID))
    ap.add_argument("--layout", default="RS",
                    help=f"dispatch slots in hardware order: {_alpha}, "
                         ".=neither. Slot 0 is position 0, the housekeeper. "
                         "e.g. SR, .RS, SSR, DS. D needs a DEV=1 image. "
                         "Only R/D own a bus accumulator and can be ANALYSED; "
                         "render an insert with --direct --pick <letter>.")
    # ⚠️ NOT hard-coded to R/D. This was choices=["R","D"] until 30 Aug 2026,
    # which made the documented insert-render command
    # (`--direct --pick W`) die in argparse -- and dropping --pick was worse:
    # the target fell back to "R", so it instantiated BusVerb and LABELLED
    # the output "DELAY". Six documents described that command as the way to
    # render an insert. Derive the choices, like everything else here.
    ap.add_argument("--pick",
                    help="which module's output to analyse: its layout letter "
                         f"({''.join(sorted(SERVER_ID))}), or its module key/"
                         "name (e.g. FILTER, chorus). Defaults to the "
                         "layout's server (R, else D). REQUIRED with --direct "
                         "for an insert or a stock effect, which has no bus "
                         "and so no default")
    ap.add_argument("--direct", action="store_true",
                    help="CONTROL / the insert path: no SEND, tone straight "
                         "into the picked module's own track input")
    ap.add_argument("--feed", default="", metavar="LETTERS",
                    help="also feed the tone to these layout letters' tracks "
                         "(a client insert sends from its own track); SENDs "
                         "are always fed, --inall feeds everything")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VAL",
                    help="drive any knob of the RENDERED module by its "
                         "manifest name (repeatable). Resolved through the "
                         "module's own knob map, so it works for every "
                         "effect -- servers and inserts alike -- without a "
                         "per-effect flag; an unknown name dies instead of "
                         "driving the wrong slot.")
    ap.add_argument("--return", dest="ret", action="store_true",
                    help="append a CHARACTER in SAT=BUS with both "
                         "return levels at 127 to the layout and measure "
                         "ITS output: the engines' wet as the master hears "
                         "it, two blocks late (docs/BUS.md 'The returns'). "
                         "The servers' own streams then carry dry only.")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    if a.ret:
        _rl = next((m.harness.layout_char for m in registry.modules().values()
                    if m.name == "character" and m.harness is not None), None)
        if _rl is None:
            die("--return needs the Character station in the registry")
        if _rl in a.layout.upper():
            die(f"--return: the layout already has a {_rl!r}; set its knobs "
                f"with --set {_rl}:SAT=3 etc. instead")
        a.layout = a.layout + _rl
        a.pick = _rl
        a.set = [f"{_rl}:SAT=3", f"{_rl}:CRSH=127", f"{_rl}:RING=127"] + a.set
    if a.pick is not None and a.pick not in SERVER_ID:
        # A module key or name, resolved to its letter -- the letters are
        # derived and nobody should have to know them.
        _pm = next((m for m in registry.modules().values()
                    if a.pick in (m.key, m.name, m.key.lower())
                    and m.harness is not None and m.harness.layout_char), None)
        if _pm is None:
            die(f"--pick {a.pick!r}: not a layout letter "
                f"({''.join(sorted(SERVER_ID))}) or a module key/name")
        a.pick = _pm.harness.layout_char

    if a.build:
        r = subprocess.run([sys.executable, "tools/build_bus.py"], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:
            die(f"build_bus.py failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    if not HOST.exists():
        die(f"missing {HOST.relative_to(ROOT)} -- run 'make setup'")

    mem = pathlib.Path(a.mem) if a.mem else dump_mem(ROOT / a.image,
                                                     ROOT / "out/dsp/_send_probe_A.mem")
    _rs = _slots("REVERB SERVER", REV_FLAGS)
    rev = list(REV_PARAMS)
    for _f, _v in (("mix", a.mix), ("shmr", a.shmr), ("mod", a.mod),
                   ("time", a.time)):
        rev[_rs[_f]] = _v                      # --mix drives IN (post-v4)
    for _f, val in (("rmode", a.rmode), ("width", a.width),
                    ("gate", a.gate), ("rrate", a.rrate),
                    ("rtone", a.rtone), ("rdel", a.rdel)):
        if val is not None:
            rev[_rs[_f]] = val
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
                                   a.dtone, a.dping, a.dspray, a.dmode,
                                   a.drate, a.dptch, a.dfrz)):
        dpar = list(DELAY_PARAMS)
        # ⚠️ SPRAY is slot 10 ($e KNOB). It sat at index 9 until 17 Aug 2026,
        # which under the OLD dsp_host map happened to hit $e's knob field --
        # right answer, wrong reasoning. Under the real map index 9 is PTCH's
        # companion, so leaving it would have silently retuned the pitch
        # select instead of the scatter depth.
        # ⚠️ IN is slot 5 and -VRB is slot 4 since the 18 Aug 2026 swap.
        # This table carried the PRE-swap mapping until 23 Aug -- --din was
        # silently driving -VRB (caught when a delay IN-makeup test measured
        # +0.0 dB lift; verify_bus.py had the swap right all along). The
        # harness-knob-drift rule again: audit EVERY wrapper on a slot swap.
        _ds = _slots("DELAY SERVER", DELAY_FLAGS)
        for _f, val in (("dtime", a.dtime), ("dfdbk", a.dfdbk),
                        ("dtone", a.dtone), ("dping", a.dping),
                        ("dmix", a.dmix), ("dvrbw", a.dvrbw),
                        ("dwow", a.dwow), ("dmode", a.dmode),
                        ("drate", a.drate), ("dptch", a.dptch),
                        ("dspray", a.dspray), ("dfrz", a.dfrz)):
            if val is not None:
                dpar[_ds[_f]] = val
    ins = None
    if a.set:
        # The target is the module that will actually RUN (same choice run()
        # makes): --pick, else the layout's reverb, else its delay. --set on
        # anything else would silently drive a module that never renders.
        _st = a.pick or ("R" if "R" in a.layout.upper() else
                         "D" if "D" in a.layout.upper() else None)
        if _st not in SERVER_ID:
            die(f"--set needs a render target -- pass --pick <letter> "
                f"(one of {''.join(sorted(SERVER_ID))})")
        _mod = registry.by_id(SERVER_ID[_st])
        kmap = _mod.knob_map_all()
        if _st == "R":
            base = rev
        elif _st == "D":
            base = dpar = list(dpar) if dpar is not None else list(DELAY_PARAMS)
        else:
            base = ins = list(MODULE_DEFAULTS.get(_st, [0] * 12))
        # A `LETTER:NAME=VAL` spec drives ANOTHER live slot of a bus layout
        # (3 Sep 2026, for the stations: a client insert's send level has to
        # be set on the instance that sends, not on the server being
        # measured). Per-letter lists ride `insert_params` as a dict.
        others = {}
        for spec in a.set:
            tgt_mod, tgt_base = _mod, base
            if ":" in spec.split("=", 1)[0]:
                letter, _, spec = spec.partition(":")
                letter = letter.strip().upper()
                if letter not in SERVER_ID:
                    die(f"--set {letter}: is not a layout letter")
                tgt_mod = registry.by_id(SERVER_ID[letter])
                tgt_base = others.setdefault(
                    letter, list(MODULE_DEFAULTS.get(letter, [0] * 12)))
            kmap2 = tgt_mod.knob_map_all()
            name, _, val = spec.partition("=")
            name = name.strip().upper()
            if name not in kmap2:
                die(f"{tgt_mod.name} has no knob named {name!r} -- it has: "
                    f"{' '.join(sorted(kmap2))}")
            slot = kmap2[name]
            v = int(val)
            count = tgt_mod.params[slot].count
            hi = (count - 1) if count is not None else 127
            if not 0 <= v <= hi:
                die(f"{tgt_mod.name} {name}={v} is out of range 0..{hi} -- a "
                    f"stepped select uses the value as an INDEX")
            tgt_base[slot] = v
        # In a bus layout every per-letter list rides the dict, the render
        # target's own included -- run() ignores a bare list there. And a
        # `2:NAME=VAL` spec for the TARGET letter lands in `others`, so the
        # target's list is the merge of both, never the defaults over the
        # prefixed values (3 Sep 2026: `--pick 2 --set 2:SAT=3` rendered a
        # station at its defaults and reported the bus silent).
        if not a.direct and ins is not None:
            if _st in others:
                for _k, _v in enumerate(others[_st]):
                    if _v != MODULE_DEFAULTS.get(_st, [0] * 12)[_k]:
                        ins[_k] = _v
            others[_st] = ins
        if others and not a.direct:
            ins = others
    L, R = run(mem, a.dur, a.tail, rev, snd, a.verbose, a.amp, a.direct, wsrc,
               a.split, a.layout, delay_params=dpar, pick=a.pick,
               inall=a.inall, insert_params=ins, feed=a.feed)
    # Where the tone stops, so the analysis window is the end of the TONE
    # rather than the silence after it -- see analyse().
    _tone_end = len(wsrc) if wsrc is not None else int(a.dur * SR)
    thd, rms, pk, extra = (analyse(L, a.label, _tone_end) if not a.infile
                           else (None, 0, 0, None))
    if a.infile:
        pk = max((abs(v) for v in L + R), default=0) / 8388607
        _t = a.pick or ("R" if "R" in a.layout.upper() else
                        "D" if "D" in a.layout.upper() else None)
        _mm = registry.by_id(SERVER_ID[_t]) if _t in SERVER_ID else None
        _srv = _mm.menu.fullname.decode("latin1").strip() if _mm else "?"
        print(f'{a.label}: {a.infile} through '
              f"{_srv + ' (--direct)' if a.direct else 'SEND -> bus -> ' + _srv}"
              f'  amp {a.amp}  peak {pk:.3f} FS')
        if a.wav:
            write_wav(ROOT / a.wav if not os.path.isabs(a.wav) else a.wav, L, R)
            print(f'  -> {a.wav}')
        return 0

    # Name the module that ACTUALLY ran. This used to be a two-way guess
    # between REVERB and DELAY, so an insert render was labelled "DELAY" while
    # executing the reverb -- a mislabel of exactly the kind this project has
    # lost sessions to.
    _tgt = a.pick or ("R" if "R" in a.layout.upper() else
                      "D" if "D" in a.layout.upper() else None)
    _m = registry.by_id(SERVER_ID[_tgt]) if _tgt in SERVER_ID else None
    _srv = _m.menu.fullname.decode("latin1").strip() if _m else "?"
    path = (f"{_srv} on its own track (--direct)" if a.direct
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
