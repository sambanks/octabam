#!/usr/bin/env python3
"""Hear one effect live: a WAV on loop through the real code, knobs in a browser.

    make fxlive [REMIX=miniverb] [MODULE=MINIVERB] [WAV=loop.wav]
    .venv/bin/python3 tools/harness/fxlive.py [--remix R] [--module KEY] [--wav loop.wav]

Then open http://127.0.0.1:8573. It starts stopped with nothing selected:
choose a remix (its modules list from the manifests, nothing builds), then
a module (the remix builds), then Play. REMIX and MODULE pre-select the
same. A page has a slider for every knob the module draws, a wet/dry
monitor mix, bypass, the loop, and the meters.

WHAT RUNS. The remix is built to a private image (BUS_OUT=out/fxlive/...,
never out/mainos_bus.bin), payload A is dumped, and `dsp_host -stream` runs
the module's init/proc from the dispatch table exactly as `send_probe
--direct` does: one FX2 instance, r0 = 0 as the dispatcher passes it, 16
frames a block. The loop is fed block by block over a pipe with the knobs in
the same packet, so what you hear is the module's real instruction stream.
`dsp_host -stream`'s output is bit-identical to a file render of the same
input and knobs.

COLDFIRE EFFECTS. A module whose sound is made on the ColdFire (CF_AUDIO
below: TAPE ECHO, and the stock DELAY of stock.NO_DSP) gets a second stage
after the DSP: `out/emu/ot_cf_host`, the stock delay routine 0x400031a0 on
T5 from the same image and a copy of this build's DRAM runtime
(cf_host.cpp beside this file; `make emu-cf` builds it). Its output equals
Tape Echo's native oracle bit for bit (`make fxlive-check`). It does
not add the frame of latency the read-back adds on the unit, and it runs
the routine, not the firmware around it.

HOT SWAP. Every file under the module's directory (and the remix's
remix.py) is watched. When one changes the remix is rebuilt (~2 s), a new
`dsp_host` is booted and warmed on silence, and the loop crossfades onto it
without stopping. A build that fails keeps the old engine playing and puts
the build's output on the page. The new engine starts from init: a reverb's
tail restarts. The same rebuild is POST /api/reload, and every control is
JSON (GET /api/state, POST /api/knob {"slot": 0, "value": 64}, POST
/api/transport {"playing": false}), so a Claude
session editing the module can drive and read the page too.

WHAT IT IS NOT (tools/harness/README.md "blind spots"): the knob words are
clean (an LFO leaves bits 8-15 set; dsp_host -pword shows that), RAM starts
zeroed (verify_dirtystate), the dispatcher is modelled, not run, and AMP
VOL / LEVEL are not applied. WET/DRY is a monitor control here, not
anything the module does. Bus servers and clients need both cores and the
rotation and are refused: render those with rig_render.py. For a ColdFire
effect the instruction count is a floor, not the CPU budget (no cache, bus
or DMA stalls, and none of the rest of the frame). A sound you like
here is a starting point for a render and `make check`, never a result.

dsp_host: a branch that changes tools/harness/dsp_host/dsp_host.cpp must
point DSP_HOST at its own build (AGENTS.md); a shared dsp_host without
-stream exits at once and the page says so.
"""
import argparse
import json
import os
import pathlib
import struct
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); import toolpath  # noqa: E402,F401
import send_probe                      # noqa: E402  (dump_mem, entry_points, HOST)
from remix import registry             # noqa: E402
from remix.schema import BusRole, Kind, render_slot  # noqa: E402
from remix.stock import NO_DSP         # noqa: E402  (stock DELAY runs on the ColdFire)

# Effects whose sound is made in the ColdFire's delay routine 0x400031a0,
# their DSP dispatch a passthrough (docs/firmware/COLDFIRE_DELAY.md section
# 3). Kept here rather than in the module schema, which is for its owners to
# change. A ColdFire effect missing from this list plays dry, and the page
# says so (passes_through).
CF_AUDIO = frozenset({"TAPE ECHO"}) | NO_DSP    # modules/tapeecho/README.md

SR = 44100
FRAMES = 16                    # the firmware's block (rig_render's default)
NPARAM = 12
CHUNK_BLOCKS = 16              # blocks per pipe round trip: 256 frames, 5.8 ms
CHUNK = CHUNK_BLOCKS * FRAMES
TARGET_FILL = 2048             # frames rendered ahead of the audio device (~46 ms)
WARMUP_BLOCKS = send_probe.WARMUP_BLOCKS
XFADE_CHUNKS = 8               # hot-swap crossfade, ~46 ms
OUTDIR = ROOT / "out/fxlive"
FS = 8388608.0


# ---- audio files -------------------------------------------------------------
def read_wav(path):
    """Any PCM (8/16/24/32-bit) or float WAV -> float32 [n, 2] at SR."""
    b = pathlib.Path(path).read_bytes()
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError(f"{path}: not a RIFF/WAVE file")
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(b):
        cid, size = b[pos:pos + 4], struct.unpack_from("<I", b, pos + 4)[0]
        body = b[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", body)
            if fmt[0] == 0xFFFE and len(body) >= 26:          # WAVE_FORMAT_EXTENSIBLE
                fmt = (struct.unpack_from("<H", body, 24)[0],) + fmt[1:]
        elif cid == b"data":
            data = body
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise ValueError(f"{path}: no fmt or data chunk")
    tag, ch, rate, _, _, bits = fmt
    w = bits // 8
    n = len(data) // (w * ch)
    data = data[:n * w * ch]
    if tag == 3 and bits == 32:
        x = np.frombuffer(data, "<f4").astype(np.float32)
    elif tag == 3 and bits == 64:
        x = np.frombuffer(data, "<f8").astype(np.float32)
    elif tag == 1 and bits == 8:
        x = (np.frombuffer(data, np.uint8).astype(np.float32) - 128) / 128
    elif tag == 1 and bits == 16:
        x = np.frombuffer(data, "<i2").astype(np.float32) / 32768
    elif tag == 1 and bits == 24:
        u = np.frombuffer(data, np.uint8).reshape(-1, 3).astype(np.int32)
        v = u[:, 0] | (u[:, 1] << 8) | (u[:, 2] << 16)
        x = (np.where(v & 0x800000, v - 0x1000000, v)).astype(np.float32) / FS
    elif tag == 1 and bits == 32:
        x = np.frombuffer(data, "<i4").astype(np.float32) / 2147483648
    else:
        raise ValueError(f"{path}: unsupported WAV format {tag}/{bits}-bit")
    x = x.reshape(-1, ch)
    x = np.repeat(x, 2, axis=1) if ch == 1 else x[:, :2]
    if rate != SR and len(x) > 1:
        t = np.arange(int(len(x) * SR / rate)) * (rate / SR)
        x = np.stack([np.interp(t, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)
    if len(x) < CHUNK:
        x = np.tile(x, (CHUNK // max(len(x), 1) + 1, 1))
    return np.ascontiguousarray(x, np.float32), rate


def demo_loop():
    """Two bars at 120 BPM made here, so the page plays before a file is given:
    a kick, a hat and a saw chord stab, about -12 dBFS."""
    rng = np.random.default_rng(7)
    beat = SR // 2
    n = beat * 8
    x = np.zeros(n, np.float32)
    t = np.arange(beat) / SR
    kick = np.sin(2 * np.pi * (50 * t + 60 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 8)
    hat = rng.standard_normal(beat) * np.exp(-t * 60) * 0.25
    for k in range(8):
        x[k * beat:(k + 1) * beat] += 0.6 * kick.astype(np.float32)
        h = k * beat + beat // 2
        x[h:h + beat // 2] += np.diff(hat[:beat // 2 + 1]).astype(np.float32)
    tc = np.arange(beat * 2) / SR
    chord = sum(((f * tc) % 1.0) * 2 - 1 for f in (220.0, 261.6, 329.6)) / 3
    env = np.exp(-tc * 4)
    for k in (0, 4):
        s = k * beat + beat // 4
        x[s:s + len(tc)] += (0.3 * chord * env).astype(np.float32)[:n - s]
    x *= 0.25 / max(1e-9, float(np.abs(x).max()))
    return np.stack([x, x], 1)


# ---- what can be played --------------------------------------------------------
def support(m):
    """(how fxlive plays the module, why not). "dsp": an insert on its own
    track's frames. "cpu": the sound is made in the ColdFire's delay routine
    (CF_AUDIO), run by cf_host after the DSP. None:
    not here (a bus server or client, or no chooser row)."""
    if m.menu is None or m.kind not in (Kind.DSP_EFFECT, Kind.DSP_CLIENT, Kind.HYBRID, Kind.STOCK):
        return None, "no FX chooser row"
    if m.key in CF_AUDIO:
        return "cpu", ""
    if m.is_stock or (m.dsp is not None and m.dsp.bus_role is BusRole.NONE):
        return "dsp", ""
    return None, (f"a bus {m.dsp.bus_role.value}: it needs both cores and the rotation "
                  f"(rig_render.py)")


def playable(m):
    return support(m)[0] is not None


def module_index():
    """Every module with a chooser row: how it plays, the group it lists
    under (dsp, cpu, stock, not), why not, and the remixes that carry it,
    smallest first -- the first is the host fxlive builds unless told
    otherwise. A module sounds the same in any carrier (the build moves its
    address, not its code: MODULATION at P:0x01984 and P:0x01a11 rendered
    bit-identical, 9 Oct 2026), so the smallest is chosen because it builds
    fastest and drags in the fewest neighbours."""
    registry._cache = None
    mods = registry.modules()
    carriers = {}
    for name in registry.remix_names():
        try:
            r = registry.remix(name)
        except SystemExit:
            continue
        for k in r.modules:
            carriers.setdefault(k, []).append((len(r.modules), 0 if registry.is_test(name) else 1, name))
    out = []
    for k, m in sorted(mods.items()):
        if m.menu is None:
            continue
        how, why = support(m)
        hosts = [n for _, _, n in sorted(carriers.get(k, []))]
        if how and not hosts:
            how, why = None, "no remix carries it: add remixes/test/<name>/"
        out.append(dict(key=k, support=how, why=why, hosts=hosts,
                        group="stock" if m.is_stock else (how or "not")))
    return out


def catalog_of(remix):
    """Every module with a chooser row in the remix: key, how it plays, why
    not. From the manifests alone, so a remix lists before anything builds."""
    registry._cache = None                       # a manifest edit renames knobs
    mods = registry.modules()
    out = []
    for k in registry.remix(remix).modules:
        if k in mods and mods[k].menu is not None:
            how, why = support(mods[k])
            out.append(dict(key=k, support=how, why=why))
    return out


def module_dir(m):
    d = ROOT / "modules" / m.name
    return d if d.is_dir() else None


def describe(m):
    """The knobs the unit draws. A field a clone leaves None is the donor's
    (schema.Param): a MenuEntry(stock_dsp=True) clone such as
    SIDECHAIN_COMPRESSOR draws all of COMPRESSOR's page 1 without naming it."""
    donor = None
    if m.menu is not None and m.menu.replaces:
        donor = registry.modules().get(m.menu.replaces)
    dparams = list(donor.params) if donor is not None else []
    out = []
    for i, p in enumerate(list(m.params)[:NPARAM]):
        d = dparams[i] if i < len(dparams) else None
        pick = (lambda f: getattr(p, f) if getattr(p, f) is not None or d is None
                else getattr(d, f))
        nm = pick("name")
        name = nm.decode(errors="replace").strip() if nm else ""
        active = p.active
        if active is None and d is not None and (m.menu.stock_dsp or m.is_stock):
            active = d.active
        drawn = bool(active) or (active is None and m.is_stock and bool(name))
        if not drawn:
            continue
        count = pick("count") or 128
        labels = pick("labels")
        out.append(dict(slot=i, name=name or f"P{i + 1}", count=count,
                        default=min((pick("default") or 0) & 0x7f, count - 1),
                        labels=list(labels) if labels else None,
                        doc=pick("doc") or ""))
    return out


# ---- one process per stage, one chain per build -------------------------------------
CF_HOST = ROOT / "out/emu/ot_cf_host"
CF_TRACK = 4                   # T5: payload A's position 0, where the DSP stage runs


def dsp_cmd(host, mem, init, proc, r7, alloc, extra=()):
    return [str(host), "-mem", str(mem), "-init", f"{init:x}", "-proc", f"{proc:x}",
            "-inst", "1", "-r7", str(r7), "-alloc", str(alloc), "-audio", "0",
            "-frames", str(FRAMES), "-stream", *extra]


def cf_cmd(image, fxid, runtime=None, tempo=120):
    cmd = [str(CF_HOST), str(image), "--fxid", f"{fxid:x}", "--track", str(CF_TRACK),
           "--tempo", str(tempo), "--stream"]
    if runtime is not None:
        cmd[2:2] = ["--runtime", str(runtime[0]), f"{runtime[1]:x}"]
    return cmd


class Engine:
    """One `-stream` process: dsp_host, or cf_host for the ColdFire routine
    (the same packets). render() is a synchronous round trip of whole
    blocks: write every packet, then read every reply. 16 blocks are ~5 KB
    each way, well inside a pipe's buffer, so it cannot deadlock."""

    def __init__(self, cmd, name="dsp_host"):
        self.name = name
        self.log = OUTDIR / f"{name}_{os.getpid()}_{id(self):x}.log"
        self.logf = open(self.log, "w")
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.logf, bufsize=0)
        self.blocks = 0

    def render(self, x, params):
        """x: int32 [nb*FRAMES, 2] -> (int32 [nb*FRAMES, 2], instructions [nb])."""
        if len(x) > CHUNK:                       # keep each round trip inside the pipes
            parts = [self.render(x[i:i + CHUNK], params) for i in range(0, len(x), CHUNK)]
            return np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])
        nb = len(x) // FRAMES
        pk = np.empty((nb, NPARAM + 2 * FRAMES), np.int32)
        pk[:, :NPARAM] = params
        pk[:, NPARAM:] = x.reshape(nb, 2 * FRAMES)
        try:
            self.p.stdin.write(pk.tobytes())
            want = nb * (2 * FRAMES + 1) * 4
            buf = bytearray()
            while len(buf) < want:
                got = self.p.stdout.read(want - len(buf))
                if not got:
                    raise BrokenPipeError
                buf += got
        except (BrokenPipeError, OSError):
            raise RuntimeError(f"{self.name} stopped: " + self.tail())
        o = np.frombuffer(bytes(buf), np.int32).reshape(nb, 2 * FRAMES + 1)
        self.blocks += nb
        return o[:, :2 * FRAMES].reshape(-1, 2), o[:, -1]

    def tail(self, n=1500):
        try:
            self.logf.flush()
            t = self.log.read_text()
        except OSError:
            t = ""
        if "unknown option -stream" in t:
            return ("this dsp_host predates -stream: rebuild it with scripts/setup.sh, or "
                    "point DSP_HOST at a build of tools/harness/dsp_host/dsp_host.cpp")
        return t[-n:] or f"exit {self.p.poll()}"

    def close(self):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            self.p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.p.kill()
        self.logf.close()
        self.log.unlink(missing_ok=True)


class Chain:
    """The stages a track's audio crosses, in order: the DSP's FX2, then (for
    a "cpu" module) the ColdFire routine. On the unit the routine sees the
    read-back one frame later; the chain does not add that frame."""

    def __init__(self, stages):
        self.stages = stages

    def render(self, x, params):
        ins = []
        for st in self.stages:
            x, n = st.render(x, params)
            ins.append(n)
        return x, ins

    def close(self):
        for st in self.stages:
            st.close()


def passes_through(make_chain, meta):
    """True when the chain returned its input bit for bit at defaults, every
    knob at minimum, at the middle and at maximum: a module that makes its
    sound somewhere fxlive does not run, or that ignores its knobs."""
    rng = np.random.default_rng(3)
    x = np.round(rng.standard_normal((64 * FRAMES, 2)) * 0.1 * FS).astype(np.int32)
    settings = [{p["slot"]: p["default"] for p in meta}]
    for f in (lambda c: 0, lambda c: c // 2, lambda c: c - 1):
        settings.append({p["slot"]: f(p["count"]) for p in meta})
    for st in settings:
        v = np.zeros(NPARAM, np.int32)
        for k, val in st.items():
            v[k] = val
        e = make_chain()
        try:
            e.render(np.zeros((WARMUP_BLOCKS * FRAMES, 2), np.int32), v)
            y, _ = e.render(x, v)
        finally:
            e.close()
        if not np.array_equal(y, x):
            return False
    return True


# ---- the session -------------------------------------------------------------------
class Session:
    def __init__(self, a):
        self.a = a
        self.lock = threading.RLock()
        self.remix = None           # set by select(): the command line pre-selects
        self.module_key = None
        self.built_key = None       # the module the playing engine runs
        self.built_remix = None     # ... and the remix it was built from
        self.index = module_index()  # every chooser module: support, group, hosts
        self.how = None             # "dsp" or "cpu": the stages the playing module runs
        self.cf_ipb = 0.0
        self.params_meta = []
        self.values = [0] * NPARAM
        self.module_doc = ""
        self.wet = 1.0
        self.bypass = False
        self.gain_db = 0.0
        self.src = demo_loop()
        self.src_name = "(built-in demo loop)"
        self.pos = 0
        self.engine = None
        self.pending = None         # a warmed engine waiting to be crossfaded in
        self.xfade_old = None
        self.xfade_k = 0
        self.version = 0            # bumped on every successful swap
        self.status = "starting"
        self.error = ""
        self.build_log = ""
        self.building = False
        self.rebuild_req = threading.Event()
        self.ring = np.zeros((1 << 15, 2), np.float32)
        self.r_rd = self.r_wr = 0
        self.cv = threading.Condition()
        self.underruns = 0
        self.rt = 0.0
        self.ips = 0.0
        self.peak_in = self.peak_out = -120.0
        self.clips = 0
        self.passthrough = ""        # why this module cannot be heard here, if measured so
        self.same_run = 0           # chunks in a row whose output equals the input, bit for bit
        self.wet_now = 1.0
        self.playing = False        # launch stopped: Play starts the loop
        self.fade = 0               # +1: fade the next chunk in, -1: out (then stop)
        self.grace = 0.0            # no underrun is counted before this (a restart)
        self.running = True
        self.watch_files = {}
        if a.wav:
            self.load_wav(a.wav)
        # MODULE (and REMIX, a host override) pre-select what the page would
        if a.module:
            self.select(a.module, a.remix)
        self.status = self.idle_status()

    # -- state -----------------------------------------------------------------
    def load_wav(self, path):
        x, rate = read_wav(pathlib.Path(path).expanduser())
        with self.lock:
            self.src, self.pos = x, 0
            self.src_name = f"{pathlib.Path(path).name} ({len(x) / SR:.2f} s"\
                            + (f", resampled from {rate} Hz)" if rate != SR else ")")

    def select(self, module, remix=None):
        """Choose a module, built in `remix` or else the smallest remix that
        carries it. Whatever is playing keeps playing until it is ready."""
        with self.lock:
            e = next((e for e in self.index if e["key"] == module), None)
            if e is None:
                raise ValueError(f"no module {module!r} with an FX chooser row")
            if not e["support"]:
                raise ValueError(f"{module}: {e['why']}")
            if remix and remix not in e["hosts"]:
                raise ValueError(f"{module} is not in remix {remix}; it is in {', '.join(e['hosts'])}")
            self.module_key, self.remix = module, remix or e["hosts"][0]
        self.rebuild_req.set()

    def idle_status(self):
        """What the pill says when nothing is building (held under the lock)."""
        if self.engine is not None:                 # what is sounding comes first
            return "playing" if self.playing else "stopped"
        if self.module_key is None:
            return "choose a module"
        return "no engine"

    def set_knob(self, slot, value):
        with self.lock:
            meta = next((p for p in self.params_meta if p["slot"] == slot), None)
            hi = (meta["count"] - 1) if meta else 127
            self.values[slot] = max(0, min(hi, int(value)))

    def state(self):
        with self.lock:
            return dict(
                remix=self.remix, index=self.index,
                built=self.built_key or "", built_remix=self.built_remix or "",
                module=self.module_key,
                how=self.how, cpu_instr_per_block=round(self.cf_ipb), doc=self.module_doc,
                params=[dict(p, value=self.values[p["slot"]]) for p in self.params_meta],
                values=list(self.values), wet=self.wet, bypass=self.bypass, playing=self.playing,
                gain_db=self.gain_db, wav=self.src_name, status=self.status,
                error=self.error, build_log=self.build_log, building=self.building,
                version=self.version, underruns=self.underruns,
                realtime=round(self.rt, 2), instr_per_sample=round(self.ips, 1),
                peak_in=round(self.peak_in, 1), peak_out=round(self.peak_out, 1),
                clips=self.clips, passthrough=self.passthrough, dry=self.same_run * CHUNK >= SR // 2, watching=sorted(str(p.relative_to(ROOT)) for p in self.watch_files),
                dsp_params=",".join(map(str, self.values)))

    # -- build + swap ------------------------------------------------------------------
    def build_engine(self, remix, key):
        """Build, dump, find the entry points, boot and warm. Returns
        (engine, meta, doc, modules, watch) or raises with the reason."""
        catalog = catalog_of(remix)
        mods = registry.modules()
        r = registry.remix(remix)
        c = next((c for c in catalog if c["key"] == key), None)
        if c is None:
            raise RuntimeError(f"{key} is not in remix {remix}")
        if not c["support"]:
            raise RuntimeError(f"{key}: {c['why']}")
        m = mods[key]
        if not pathlib.Path(self.a.host).is_file():
            raise RuntimeError(f"no dsp_host at {self.a.host}: run scripts/setup.sh, or point "
                               f"DSP_HOST at a build with -stream (a branch that changes "
                               f"dsp_host.cpp builds its own, AGENTS.md)")
        how = support(m)[0]
        if how == "cpu" and not CF_HOST.is_file():
            raise RuntimeError(f"{key} is made on the ColdFire and {CF_HOST.relative_to(ROOT)} "
                               f"is not built: make emu-cf")
        OUTDIR.mkdir(parents=True, exist_ok=True)
        image = OUTDIR / f"{remix}.bin"
        env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1", BUS_OUT=str(image))
        t0 = time.time()
        b = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, env=env,
                           capture_output=True, text=True)
        log = (b.stdout + b.stderr).strip()
        if b.returncode != 0:
            raise RuntimeError("build failed:\n" + log[-4000:])
        # The DRAM runtime lands at a fixed out/platform/ (any DRAM build
        # rewrites it, a ROM-only one leaves it alone): take a copy now, and
        # only when THIS build printed that it linked one.
        runtime = None
        if how == "cpu" and "platform runtime:" in log:
            raw = OUTDIR / f"{remix}.runtime.raw"
            raw.write_bytes((ROOT / "out/platform/runtime.raw").read_bytes())
            base = json.loads((ROOT / "out/platform/layout.json").read_text())["base"]
            raw.with_suffix(".base").write_text(f"{base:x}\n")   # the pair, for a cf_host run by hand
            runtime = (raw, base)
        mem = send_probe.dump_mem(image, OUTDIR / f"{remix}_A.mem", "A")
        try:
            init, proc = send_probe.entry_points(mem, m.menu.fx2_id)
            send = mods.get("SEND")
            if send is not None and key != "SEND" and "SEND" in r.modules \
                    and (init, proc) == send_probe.entry_points(mem, send.menu.fx2_id):
                raise RuntimeError(f"{key}'s dispatch entry in payload A is the SEND alias: "
                                   f"the module is not in this payload, and a render would be "
                                   f"a dry passthrough")
        except SystemExit as e:
            raise RuntimeError(str(e))
        r7, alloc = render_slot(m)
        meta = describe(m)

        def make_chain():
            stages = [Engine(dsp_cmd(self.a.host, mem, init, proc, r7, alloc), "dsp_host")]
            if how == "cpu":
                stages.append(Engine(cf_cmd(image, m.menu.fx2_id, runtime), "cf_host"))
            return Chain(stages)
        passthrough = passes_through(make_chain, meta)
        eng = make_chain()
        with self.lock:
            vals = list(self.values) if key == self.built_key else None
        if vals is None:
            vals = [0] * NPARAM
            for p in meta:
                vals[p["slot"]] = p["default"]
        silence = np.zeros((WARMUP_BLOCKS * FRAMES, 2), np.int32)
        eng.render(silence, np.array(vals, np.int32))
        watch = {}
        d = module_dir(m)
        paths = [registry.remix_path(remix)]
        if d is not None:
            paths += [p for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        for p in paths:
            try:
                watch[p] = p.stat().st_mtime_ns
            except OSError:
                pass
        took = time.time() - t0
        summary = "\n".join(line for line in log.splitlines()[-3:])
        if passthrough:
            where = ("the DSP and the ColdFire's delay routine" if how == "cpu" else "the DSP")
            self.passthrough = (f"{key} returned its input unchanged, bit for bit, at its "
                                f"defaults and with every knob at minimum, middle and maximum. "
                                f"fxlive runs {where}; if the module makes its sound anywhere "
                                f"else, it cannot be heard here. If it is a ColdFire effect "
                                f"in the stock delay routine, add it to CF_AUDIO in "
                                f"tools/harness/fxlive/fxlive.py.")
        else:
            self.passthrough = ""
        self.how = how
        stage = (f"; ColdFire routine 0x400031a0 as id 0x{m.menu.fx2_id:02x} on T{CF_TRACK + 1}"
                 + (f", runtime at 0x{runtime[1]:08x}" if runtime else "") if how == "cpu" else "")
        return eng, meta, m.doc, catalog, watch, key, vals, \
            f"built {remix} in {took:.1f} s; {key} init P:0x{init:05x} proc P:0x{proc:05x} " \
            f"r7 {r7} alloc {alloc}{stage}\n{summary}"

    def builder(self):
        while self.running:
            self.rebuild_req.wait(0.4)
            if not self.rebuild_req.is_set():
                if self.changed():
                    time.sleep(0.3)                   # let an editor finish writing
                    self.rebuild_req.set()
                continue
            self.rebuild_req.clear()
            with self.lock:
                remix, key = self.remix, self.module_key
                if remix is None or key is None:
                    continue
                self.building = True
                self.status = f"building {remix} ..."
            try:
                eng, meta, doc, keys, watch, key, vals, msg = self.build_engine(remix, key)
                with self.lock:
                    if self.pending is not None:
                        self.pending.close()
                    self.pending = eng
                    self.params_meta, self.module_doc = meta, doc
                    self.index = module_index()   # a manifest or remix edit shows up
                    self.module_key, self.values, self.built_key = key, vals, key
                    self.built_remix = remix
                    self.watch_files = watch
                    self.error = ""
                    self.build_log = msg
                    self.status = "swapping"
            except Exception as e:                    # keep the old engine playing
                with self.lock:
                    self.error = str(e) if isinstance(e, RuntimeError) else traceback.format_exc()
                    self.status = f"{key} failed -- {self.built_key} keeps playing" \
                        if self.engine else f"{key} failed -- playing dry"
                    try:                              # still watch, so the fix rebuilds
                        m = registry.modules().get(key)
                        d = module_dir(m) if m else None
                        if d is not None:
                            self.watch_files = {p: p.stat().st_mtime_ns for p in d.rglob("*")
                                                if p.is_file() and "__pycache__" not in p.parts}
                    except Exception:
                        pass
            finally:
                with self.lock:
                    self.building = False

    def changed(self):
        with self.lock:
            files = dict(self.watch_files)
        for p, t in files.items():
            try:
                if p.stat().st_mtime_ns != t:
                    return True
            except OSError:
                return True
        return False

    # -- audio ---------------------------------------------------------------------------
    def fill(self):
        with self.cv:
            return (self.r_wr - self.r_rd) % len(self.ring)

    def transport(self, playing):
        """Stop fades the next chunk out and pauses the engines; play starts
        the loop from the top with a fade in. A rebuild while stopped still
        swaps (without a crossfade: nothing is sounding)."""
        with self.lock:
            if playing and not self.playing:
                self.playing, self.fade, self.pos = True, +1, 0
                self.grace = time.monotonic() + 0.25   # the device asks before the first chunk
                self.status = "playing" if self.engine else self.status
            elif not playing and self.playing:
                self.playing, self.fade = False, -1

    def idle(self):
        with self.lock:
            if self.pending is not None:
                for e in (self.engine, self.xfade_old):
                    if e is not None:
                        e.close()
                self.engine, self.pending, self.xfade_old = self.pending, None, None
                self.version += 1
            if not self.building and not self.error:
                self.status = self.idle_status()
            self.peak_in = self.peak_out = -120.0
        time.sleep(0.02)

    def renderer(self):
        while self.running:
            with self.lock:
                stopped = not self.playing and self.fade == 0
            if stopped:
                self.idle()
                continue
            if self.fill() >= TARGET_FILL:
                with self.cv:
                    self.cv.wait(0.01)
                continue
            with self.lock:
                if self.pending is not None:
                    self.xfade_old, self.engine = self.engine, self.pending
                    self.pending = None
                    self.xfade_k = 0 if self.xfade_old else XFADE_CHUNKS
                    if self.xfade_old is None:
                        self.underruns = 0        # the device ran ahead of the first build
                    self.version += 1
                    self.status = "playing"
                eng, old = self.engine, self.xfade_old
                src, pos = self.src, self.pos
                idx = (pos + np.arange(CHUNK)) % len(src)
                self.pos = (pos + CHUNK) % len(src)
                params = np.array(self.values, np.int32)
                wet_t = 0.0 if self.bypass else self.wet
                g = 10 ** (self.gain_db / 20)
                fade, self.fade = self.fade, 0
            dry = src[idx] * g
            x = np.clip(np.round(dry * FS), -FS, FS - 1).astype(np.int32)
            t0 = time.perf_counter()
            try:
                if eng is None:
                    y, ins = x, [np.zeros(CHUNK_BLOCKS)]
                else:
                    y, ins = eng.render(x, params)
                    if old is not None:
                        yo, _ = old.render(x, params)
                        k = self.xfade_k
                        ramp = ((k * CHUNK + np.arange(CHUNK)) / (XFADE_CHUNKS * CHUNK))[:, None]
                        y = np.round(yo * (1 - ramp) + y * ramp).astype(np.int32)
                        self.xfade_k += 1
                        if self.xfade_k >= XFADE_CHUNKS:
                            old.close()
                            self.xfade_old = None
            except RuntimeError as e:
                with self.lock:
                    self.error = str(e)
                    self.status = "engine stopped -- rebuild (or fix and save) to restart"
                    if self.engine is eng:
                        self.engine = None
                    if self.xfade_old is not None:
                        self.xfade_old = None
                continue
            dt = time.perf_counter() - t0
            if eng is not None and dt > 0:
                self.rt = 0.9 * self.rt + 0.1 * ((CHUNK / SR) / dt) if self.rt else (CHUNK / SR) / dt
                self.ips = float(np.mean(ins[0])) / FRAMES
                self.cf_ipb = float(np.mean(ins[1])) if len(ins) > 1 else 0.0
            wet = y.astype(np.float32) / FS
            w = self.wet_now + (wet_t - self.wet_now) * (np.arange(1, CHUNK + 1) / CHUNK)[:, None]
            self.wet_now = wet_t
            out = dry * (1 - w) + wet * w
            if fade:
                ramp = (np.arange(CHUNK) + 1) / CHUNK
                out = out * (ramp if fade > 0 else 1 - ramp)[:, None]
            pin, pout = float(np.abs(dry).max()), float(np.abs(out).max())
            self.peak_in = max(20 * np.log10(max(pin, 1e-6)), self.peak_in - 1.5)
            self.peak_out = max(20 * np.log10(max(pout, 1e-6)), self.peak_out - 1.5)
            self.clips += int(np.count_nonzero(np.abs(y) >= 8388607))
            self.same_run = self.same_run + 1 if eng is not None and np.array_equal(y, x) else 0
            with self.cv:
                n = len(self.ring)
                i = self.r_wr % n
                j = min(CHUNK, n - i)
                self.ring[i:i + j] = out[:j]
                self.ring[:CHUNK - j] = out[j:]
                self.r_wr = (self.r_wr + CHUNK) % n

    def pull(self, frames):
        with self.cv:
            n = len(self.ring)
            have = (self.r_wr - self.r_rd) % n
            out = np.zeros((frames, 2), np.float32)
            k = min(frames, have)
            i = self.r_rd
            j = min(k, n - i)
            out[:j] = self.ring[i:i + j]
            out[j:k] = self.ring[:k - j]
            self.r_rd = (self.r_rd + k) % n
            if k < frames and self.engine is not None and self.playing \
                    and time.monotonic() > self.grace:
                self.underruns += 1
            self.cv.notify()
        return out

    def run_audio(self):
        if self.a.no_audio:                       # headless: a clock that drains the ring
            def clock():
                t = time.perf_counter()
                while self.running:
                    t += 512 / SR
                    self.pull(512)
                    time.sleep(max(0.0, t - time.perf_counter()))
            threading.Thread(target=clock, daemon=True).start()
            return None
        import sounddevice as sd

        def cb(outdata, frames, _t, _status):
            outdata[:] = self.pull(frames)
        st = sd.OutputStream(samplerate=SR, channels=2, dtype="float32", blocksize=512,
                             latency="low", callback=cb, device=self.a.device)
        st.start()
        return st


# ---- http ------------------------------------------------------------------------------
def make_handler(s):
    page = (pathlib.Path(__file__).with_name("fxlive.html")).read_bytes()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, code, body, ctype="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send(200, page, "text/html; charset=utf-8")
            elif self.path.startswith("/api/state"):
                self.send(200, s.state())
            else:
                self.send(404, {"error": "not found"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            try:
                if self.path.startswith("/api/upload"):
                    name = os.path.basename(self.headers.get("X-Filename") or "upload.wav")
                    d = OUTDIR / "uploads"
                    d.mkdir(parents=True, exist_ok=True)
                    p = d / name
                    p.write_bytes(raw)
                    s.load_wav(p)
                    return self.send(200, s.state())
                body = json.loads(raw or b"{}")
                if self.path == "/api/knob":
                    if "slot" in body:
                        s.set_knob(int(body["slot"]), body["value"])
                    for k, v in (body.get("values") or {}).items():
                        s.set_knob(int(k), v)
                elif self.path == "/api/mix":
                    with s.lock:
                        if "wet" in body:
                            s.wet = max(0.0, min(1.0, float(body["wet"])))
                        if "bypass" in body:
                            s.bypass = bool(body["bypass"])
                        if "gain_db" in body:
                            s.gain_db = max(-48.0, min(12.0, float(body["gain_db"])))
                elif self.path == "/api/load":
                    if body.get("wav"):
                        s.load_wav(body["wav"])
                    if body.get("module"):
                        s.select(body["module"], body.get("remix"))
                    elif body.get("remix"):
                        raise ValueError("a remix only chooses where a module is built: "
                                         "give {\"module\": ..., \"remix\": ...}")
                elif self.path == "/api/transport":
                    s.transport(bool(body.get("playing", not s.playing)))
                elif self.path == "/api/defaults":
                    with s.lock:
                        for p in s.params_meta:
                            s.values[p["slot"]] = p["default"]
                elif self.path == "/api/reload":
                    s.rebuild_req.set()
                else:
                    return self.send(404, {"error": "not found"})
                self.send(200, s.state())
            except Exception as e:
                self.send(400, {"error": str(e)})
    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--module", default=os.environ.get("MODULE") or None,
                    help="pre-select a module KEY, which builds it at once (default: none)")
    ap.add_argument("--remix", default=os.environ.get("REMIX") or None,
                    help="with --module: the remix to build it in (default: the smallest that carries it)")
    ap.add_argument("--wav", default=os.environ.get("WAV") or None, help="loop (default: a built-in demo)")
    ap.add_argument("--port", type=int, default=8573)
    ap.add_argument("--host", default=str(send_probe.HOST), help="dsp_host with -stream (DSP_HOST)")
    ap.add_argument("--device", default=None, help="sounddevice output device")
    ap.add_argument("--no-audio", action="store_true", help="no sound device; render on a clock")
    a = ap.parse_args()
    if a.remix and not a.module:
        ap.error("--remix only chooses where --module is built; give --module")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    try:
        s = Session(a)
    except ValueError as e:
        ap.error(str(e))
    threading.Thread(target=s.builder, daemon=True).start()
    threading.Thread(target=s.renderer, daemon=True).start()
    stream = s.run_audio()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(s))
    what = (f"{s.module_key} in {s.remix}" if s.module_key else "nothing selected")
    print(f"fxlive: http://127.0.0.1:{a.port}  ({what}; stopped, press Play; Ctrl-C quits)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        s.running = False
        if stream is not None:
            stream.stop()
        for e in (s.engine, s.pending, s.xfade_old):
            if e is not None:
                e.close()


if __name__ == "__main__":
    main()
