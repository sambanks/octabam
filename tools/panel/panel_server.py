#!/usr/bin/env python3
"""The virtual front panel: the emulated unit with a clickable UI.

Serves a browser page that shows the firmware's REAL screen -- the LCD
framebuffer the draw primitives paint at FB (found 10 Sep 2026 by hooking
memory writes from the draw-primitive region during a menu draw: 16
bytes/row, MSB left, 128x64) -- and injects key presses as matrix reports
over the panel link.

The emulator is the C++ ColdFire port, `out/emu/ot_emu --interactive`,
over pipes (PortProc/PortRt below; protocol in the PortProc docstring):
boot + the fixture project in 21 s wall, 350 emulated ms per wall s while
playing (measured 12 Sep 2026), and it loads the project itself during its
boot. A missing binary is built here. Route A (emu_rtos, Unicorn), the
second backend until 26 Sep 2026, was retired; it is in git history.

    .venv/bin/python3 tools/panel/panel_server.py                  # built image, empty card
    .venv/bin/python3 tools/panel/panel_server.py --image out/raw/section_3_MAIN_OS.bin
    .venv/bin/python3 tools/panel/panel_server.py --project <dir> [--set S] [--name N]
    .venv/bin/python3 tools/panel/panel_server.py --project <dir> --audio ~/samples   # seed the pool

Samples (12 Sep 2026): the card's AUDIO folder is a per-port pool
(SamplePool, out/_panel_pool_<port>/) -- /samples/add, /samples/upload
and /samples/remove change it, /samples/commit rebuilds the card and
reboots the unit on it (there is no hot-plug: Panel.commit_card).

Sound (12 Sep 2026): with `--sound on` (the default) the port child runs
--dsp and the server drains core 0's main L/R over the pipe (O14k) into
AudioRing (the last 180 s, absolute frame numbers) and, from PLAY to STOP,
into out/_panel_takes_<port>/take-NNN.wav -- /audio/status, /audio/pcm,
/audio.wav, /audio/enable (README "Hearing the unit"). Playing costs ~3x
the wall time of a child without the cores.

The card (13 Sep 2026, O19): `--card <file.img>` boots an EXISTING image
as it is, with the child's write-back on (`--card-rw`: every sector the
firmware writes lands in the file), so the unit's own SAVE PROJECT and the
samples put on the card survive a quit -- the file is the card. A missing
file is created once from --project (the per-port build below) with a
sidecar `<file.img>.json` (set / project names, pending removals); later
boots read the sidecar. The pool is then `<file.img>.pool/` (pending
additions, never wiped); /samples/commit copies it onto the card through
an hdiutil mount while the child is stopped (no rebuild); /card/eject
mounts the card on the Mac for Finder and /card/insert boots it again.
Without --card nothing changes: a fresh per-port image every start.

    .venv/bin/python3 tools/panel/panel_server.py --card out/cards/OTLIVE-PROJECT.img \
        --project out/_projects/otlive/OTLIVE/PROJECT --set OTLIVE --name PROJECT

Then open http://localhost:8563/. Unmapped keys: the MAP drawer lists every
table entry; click one, watch the screen, name it. The mapping lives in the
browser (localStorage) and exports as JSON -- send a completed map back as
a PR to key_map.json.

The output device (13 Sep 2026): /audio/devices lists the Mac's audio
devices (PortAudio via the sounddevice package), /audio/output?device=
<index|name|off> streams the unit's outputs to one of them in real time
(main L/R on channels 1-2, cue L/R on 3-4, and -- O23, per-track outputs
the hardware does not have -- tracks 1-8 as stereo stems on 5-20, then
the other four ESAI words on 21-24; a device with fewer channels gets the
first pairs, a 2-channel one main L/R) -- BlackHole into a DAW, or the
speakers -- and /audio/status "output" says how it is going (README
"Recording into a DAW"). With a device on, the child streams the eight
ESAI words plus the eight stems (`audio start tracks`, 24 words a frame;
`all` on an older child) and the drain de-interleaves main L/R for the
ring, the takes and /audio/pcm, which see exactly what they saw.
"""
import argparse
import collections
import datetime
import filecmp
import io
import json
import os
import pathlib
import platform
import plistlib
import queue
import re
import shutil
import signal
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 23 Sep 2026: the app compares this with the file (an orphaned server from an
# earlier session kept every later server-side fix out of the app for a week)
SCRIPT_MTIME = os.path.getmtime(os.path.abspath(__file__))

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401

import emu_card as ec  # noqa: E402

SAMPLE_HZ = 44100.0
FRAME_PERIOD = 16.0                # samples per DSP-frame interrupt
CUR_PATTERN = 0x80000004
PATTERN_STRIDE = 0x8ed8            # 36568; sixteen records fill blob+0..0x8ed80
FW_MIDI_SETTINGS = 0x80000028      # project MIDI byte: bit 0 = CLOCK RECEIVE

FB = 0x460d1f80          # LCD framebuffer, COLUMN-major: 128 columns x 8 bytes,
                         # bit 7 of a page byte is the LOWEST of its 8 rows --
                         # pixel(x,y) = buf[x*8 + (63-y)//8] bit (7 - (63-y)%8)
                         # (verified: renders the SET DATE/TIME dialog legibly)
                         # -- a FALLBACK only: it is not a copy of what the panel
                         # shows (no page rotation, row/column or bit order maps
                         # it onto the decoded stream; best 669/1024 bytes wrong
                         # on AMP SETUP, 12 Sep 2026, KEYMAP.md)
UI_WINDOW = 0x460d175c      # the UI's popup slot. NOT "a SETUP window or 0" (the first
                            # version annotated /knob on nonzero and so on every page
                            # after a YES/NO, verifier 12 Sep 2026): it is POPUP while
                            # ANY popup is drawn from that record -- the SET DATE/TIME
                            # dialog, MIXER, TEMPO, PATTERN SETTINGS, the PROJECT menu,
                            # ARM ALL / DISARM ALL and the page SETUP windows -- and
                            # 0x46c7d384 (the record after it, flags closed) on the
                            # main screen and page 1 after YES closed the dialog; 0
                            # after a popup closes (fix_lab.log, fix_lab2.log).
POPUP = 0x46c7d34c          # the popup record: +0x08 x0, +0x0c y0, +0x18 x1, +0x20 flags
                            # (0x21 open, 0x01 closed), +0x28 rows. What tells the page
                            # SETUP windows apart is their geometry: every one of them
                            # (PLAYBACK/AMP/LFO/FX1/FX2, the second press of the page
                            # key) is x 7..0xf4, y 0, 0x40 rows, and nothing else is
                            # (MIXER 10/0/0xec/0x40, PROJECT menu 5/0/0xf6/0x40, TEMPO
                            # 0x1c/8/0xca/0x30, PATTERN SETTINGS 8/3/0xf2/0x3a, ARM ALL
                            # 0x25/0x17/0xb8/0x12, DISARM ALL 0x1e/0x17/0xc6/0x12, the
                            # clock dialog 0xf/7/0xe6/0x32; measured 12 Sep 2026,
                            # KEYMAP.md). The record keeps its last geometry after a
                            # close, hence the slot check as well.
SETUP_GEOMETRY = (7, 0, 0xf4, 0x40)
CLOCK_GEOMETRY = (0xf, 7, 0xe6, 0x32)     # the boot SET DATE/TIME dialog (KEYMAP.md)


def popup_geometry(uc):
    """(x0, y0, x1, rows) of the popup on screen, or None when the popup
    slot is empty or the record's flags say closed."""
    if int.from_bytes(uc.mem_read(UI_WINDOW, 4), "big") != POPUP:
        return None
    rec = bytes(uc.mem_read(POPUP, 0x2c))
    word = lambda off: int.from_bytes(rec[off:off + 4], "big")  # noqa: E731
    if not (word(0x20) & 0x20):
        return None
    return (word(0x08), word(0x0c), word(0x18), word(0x28))


def setup_window_open(uc):
    """True while a page's SETUP window is the popup on screen (see POPUP)."""
    if int.from_bytes(uc.mem_read(UI_WINDOW, 4), "big") != POPUP:
        return False
    rec = bytes(uc.mem_read(POPUP, 0x2c))
    word = lambda off: int.from_bytes(rec[off:off + 4], "big")  # noqa: E731
    return ((word(0x08), word(0x0c), word(0x18), word(0x28)) == SETUP_GEOMETRY
            and bool(word(0x20) & 0x20))


# -- 13 Sep 2026: the page encoders' parameters and the crossfader ------------
# ARM ALL / DISARM ALL (YES / NO on the bare main screen) never time out under
# the emulator (KEYMAP.md); the page-1 encoders still edit the page under them,
# so a reset goes ahead with either on screen. Any other popup (a SETUP
# window, the MIXER, TEMPO, a menu) means the encoders edit something else.
ARM_ALL_GEOMETRY = (0x25, 0x17, 0xb8, 0x12)
DISARM_ALL_GEOMETRY = (0x1e, 0x17, 0xc6, 0x12)
XFADER = 0x460d16c8         # the crossfader position the morph reads, long 0..127: 127 = scene A
                            # (leftmost), 0 = scene B (docs/firmware/MIDI.md appendix C; measured
                            # 13 Sep 2026: the weight table 0x80003c60 reads 0x8000_0000 at 127)
XFADER_ROW = 0x40           # the panel's fader report: `0x40 <adc 0..255>` on the panel UART; the RX
                            # parser (0x4009228c, class 0x40 with row nibble 0) scales the byte by the
                            # calibration record at 0x1ffffe (magic 0x1234; none under emulation ->
                            # value >> 1) and posts sys message kind 4 (0x40092fac -> 0x40092f2c ->
                            # handler 0x40061e0a, which stores it, rebuilds the weights and redraws
                            # the fader icon at LCD x 104-108 / y 59-61). docs/firmware/PANEL.md §9.
SCENE_A_OFF, SCENE_B_OFF = 0x8ed90, 0x8ed91   # the Part's assigned scenes (0-based), base-relative
PARAM_MAP_FILE = pathlib.Path(__file__).parent / "param_map.json"

_SKIN_JS = None


def skin_js():
    """window.SKIN / window.SKIN_SVG from tools/panel/skin/gen_svg.py, built
    into out/panel_skin/ on first use (per server)."""
    global _SKIN_JS
    if _SKIN_JS is None:
        out = ROOT / "out/panel_skin"
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(pathlib.Path(__file__).parent / "skin/gen_svg.py"), str(out)],
                       check=True, capture_output=True)
        # the drawing's own screen rect is id="screen", which is the page's LCD
        # image's id: the page would move the rect instead of the image
        svg = (out / "octatrack.svg").read_text().replace('id="screen"', 'id="skin-screen"')
        geo = (out / "octatrack-elements.json").read_text()
        _SKIN_JS = (f"window.SKIN = {geo};\nwindow.SKIN_SVG = {json.dumps(svg)};\n").encode()
    return _SKIN_JS


def load_param_map(path=PARAM_MAP_FILE):
    """tools/panel/param_map.json with its hex strings turned into ints
    (the "_notes" and evidence strings left alone); {} when missing."""
    try:
        raw = json.loads(pathlib.Path(path).read_text())
    except (OSError, ValueError):
        return {}
    def conv(v):
        if isinstance(v, str) and re.fullmatch(r"0x[0-9a-fA-F]+", v):
            return int(v, 16)
        if isinstance(v, dict):
            return {k: (v2 if k.startswith("_") else conv(v2)) for k, v2 in v.items()}
        return v
    return conv(raw)


KEY_TABLE = 0x400d2954   # per-key jump table: 66 longword handlers
KEY_COUNT = 66
IDX_REC, IDX_PLAY, IDX_STOP = 27, 28, 29   # measured: 0x4000a274/0x4000a200/0x4000a1e0


LCD_ON, LCD_OFF = bytes((0xf2, 0xf2, 0xf2)), bytes((0x06, 0x06, 0x07))   # lit / unlit pixel, RGB: the MKII display, white on black


def _png_rgb(w, h, rows):
    """Minimal 8-bit RGB PNG (stdlib only): rows of w*3 bytes."""
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + r for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _png_gray(w, h, rows):
    """Minimal 8-bit grayscale PNG (stdlib only)."""
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + r for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# -- the port backend: out/emu/ot_emu --interactive over pipes -----------------

PORT_BIN = ROOT / "out/emu/ot_emu"
PORT_SRC = ROOT / "tools/emu/ot_emu"
PORT_BUILD = ROOT / "out/emu"


class PortDied(Exception):
    """The port process is gone or silent: the loop kills it and respawns."""


class PortError(Exception):
    """The port answered `err <message>` (bad address, bad command)."""


# macOS scheduling classes and the child (O15f, 12 Sep 2026). Measured with
# bench.py on one binary, nothing else running: nice 5 (what zsh gives a job
# started with `&`: BG_NICE is on by default -- the "backgrounded runs 1.5x
# slower" of the speed-mem report) costs nothing on an idle machine (1357 vs
# 1341-1423 emulated ms per wall s) and only shows under contention; the
# DARWIN BACKGROUND class (`taskpolicy -b`, what a napped or background-QoS
# app and its children get: efficiency cores, throttled I/O) is 3.7x slower
# without the DSP cores (385 vs 1423; boot 21.4 vs 5.8 s) and 3.5x with them
# (43 vs 150; boot 91 s). A process may leave that class itself:
# setpriority(PRIO_DARWIN_PROCESS, 0, PRIO_DARWIN_NORMAL) in the child before
# exec put the same run back at 1469 (boot 5.5 s). Niceness cannot be lowered
# without privilege, so it is only reported (/status "nice").
PRIO_DARWIN_PROCESS, PRIO_DARWIN_NORMAL = 4, 0


def _child_foreground():
    """preexec_fn for the port child: leave the darwin background class if
    the server inherited it (a no-op otherwise; never raises)."""
    if sys.platform == "darwin":
        try:
            os.setpriority(PRIO_DARWIN_PROCESS, 0, PRIO_DARWIN_NORMAL)
        except OSError:
            pass


def host_nice():
    """The server's own niceness (the child inherits it)."""
    try:
        return os.getpriority(os.PRIO_PROCESS, 0)
    except OSError:
        return None


class PortProc:
    """One `ot_emu --interactive` child: a line out, a line back, flushed.

    The protocol (agreed 12 Sep 2026 with the port's side, built against the
    same text): the child boots exactly as the CLI does (project load
    included when --mount/--set/--project are given), prints its usual
    report, then one line `ready sample=<double> frames=<u64>` and serves
    stdin, one command per line, exactly one line per command:

        run <ms>            ok sample=<double> frames=<u64> stop=<word>
        key <row> <mask>    ok        (two bytes into UART A's receive queue)
        knob <row> <delta>  ok        (signed delta; pushes row, delta&0xff)
        tx                  tx <hex>  (UART A bytes since the previous tx)
        peek <addr> <len>   peek <hex> (len <= 4096; unmapped -> err)
        poke <addr> <hex>   ok
        frame on|off        ok        (Rtos::setFrame)
        status              status sample= ms= frames= frame= idle= wall=
        quit                ok, exit 0
        (failure)           err <message>, keeps serving
      and with --dsp (O14k, 12 Sep 2026; `err audio needs --dsp` without it):
        audio start [main|cue|all|tracks]   ok   (core 0's ESAI frames into a 60 s ring; tracks = + the eight stems, O23)
        audio read [<maxframes>]     audio <frames> <hex>   (LE int16 stereo, released on read, never blocks)
        audio status                 audio status on= mode= captured= pending= rate=44100 dropped= cap=
        audio stop                   ok
      and the pacing extensions (O15f, 12 Sep 2026; opt-in, the rest unchanged):
        pace on [rate]               ok        (free-running: emulated time tracks the child's wall
                                               clock x rate in 10 ms slices while stdin is empty)
        pace off                     ok
        pacestatus                   pacestatus on= rate= ratio= lag= slices= reanchors= slept= busy= stop= ms=
        run <ms> wall <seconds>      ok sample= frames= stop=wall|time|...   (also ends when the wall budget is spent)

    A reader thread queues stdout lines so a wait can time out; lines that
    are not the expected reply (the port's own report before `ready`, any
    printf noise) go to `log` (last 200) instead of being mistaken for one.
    stderr goes to `log_path`."""

    BACKSTOP = 120.0        # wall seconds a reply may take before the command is given up
                            # (the watchdog kills a hung child long before: Panel.ACTION_LIMIT)

    def __init__(self, argv, log_path=None):
        self.argv = [str(a) for a in argv]
        self.log = collections.deque(maxlen=200)
        self.lines = queue.Queue()
        self.lock = threading.Lock()
        self.ready = None               # (sample, frames) from the ready line
        self.commands = 0
        self.started = time.perf_counter()
        err = open(log_path, "ab") if log_path else subprocess.DEVNULL
        self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=err, bufsize=0, cwd=str(ROOT), preexec_fn=_child_foreground)
        if log_path:
            err.close()
        threading.Thread(target=self._reader, daemon=True, name="port-stdout").start()

    def _reader(self):
        # A buffered view of the pipe for the line reads: the raw FileIO a
        # bufsize=0 Popen hands out reads ONE BYTE PER SYSCALL in readline(),
        # which cost an 8.9 KB `audio read` reply (a 25 ms pump's frames)
        # 2.2 ms wall and a 350 KB one 90 ms (measured 12 Sep 2026); the
        # short `tx`/`ok` replies never showed it. Only this thread reads
        # stdout, so the buffer hides nothing, and a line is delivered as
        # soon as its newline arrives (BufferedReader.readline returns on
        # the read() that carries it, it does not wait to fill the buffer).
        f = io.BufferedReader(self.proc.stdout, buffer_size=1 << 16)
        for raw in iter(f.readline, b""):
            self.lines.put(raw.decode("ascii", "replace").rstrip("\r\n"))
        self.lines.put(None)            # EOF: the child exited

    def tail(self, n=6):
        return " | ".join(list(self.log)[-n:])

    def alive(self):
        return self.proc.poll() is None

    def wait_ready(self, timeout):
        """Consume the boot report until the ready line; PortDied on exit or silence."""
        deadline = time.perf_counter() + timeout
        rt_refused = None       # the child's own `dsp-rt : cannot start ...` line (O17), if it printed one
        while True:
            try:
                line = self.lines.get(timeout=max(0.0, deadline - time.perf_counter()))
            except queue.Empty:
                self.kill()
                raise PortDied(f"no ready line within {timeout:.0f} s; last: {self.tail()}")
            if line is None:
                if rt_refused:
                    raise PortDied(rt_refused)
                raise PortDied(f"exited (rc {self.proc.poll()}) before ready; last: {self.tail()}")
            if line.startswith("dsp-rt") and "cannot start" in line:
                rt_refused = line.strip()
            if line.startswith("ready "):
                f = dict(kv.split("=", 1) for kv in line.split()[1:] if "=" in kv)
                self.ready = (float(f.get("sample", 0)), int(f.get("frames", 0)))
                return self.ready
            self.log.append(line)

    def command(self, line, expect, timeout=None):
        """Send one line, return the reply that starts with `expect`.
        `err ...` raises PortError; a dead or silent child raises PortDied."""
        timeout = self.BACKSTOP if timeout is None else timeout
        with self.lock:
            try:
                self.proc.stdin.write(line.encode("ascii") + b"\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                raise PortDied(f"write failed on {line!r}: {e}")
            self.commands += 1
            deadline = time.perf_counter() + timeout
            while True:
                try:
                    reply = self.lines.get(timeout=max(0.0, deadline - time.perf_counter()))
                except queue.Empty:
                    self.kill()
                    raise PortDied(f"no reply to {line!r} within {timeout:.0f} s")
                if reply is None:
                    raise PortDied(f"exited (rc {self.proc.poll()}) on {line!r}; last: {self.tail()}")
                head = reply.split(" ", 1)[0]
                if head == expect:
                    return reply
                if head == "err":
                    raise PortError(reply[4:])
                self.log.append(reply)      # noise, not a reply: keep waiting

    def quit(self):
        try:
            if self.alive():
                self.command("quit", "ok", timeout=2.0)
        except (PortDied, PortError):
            pass
        self.kill()

    def kill(self):
        if self.alive():
            try:
                self.proc.kill()
            except OSError:
                pass
        try:
            self.proc.wait(timeout=2.0)
        except Exception:
            pass


class SpeedMeter:
    """Emulated ms per wall second, averaged over the last WINDOW wall
    seconds of run() calls (idle runs return at once, so idle reads high)."""
    WINDOW = 5.0

    def __init__(self):
        self.samples = collections.deque()      # (t_end, ms, wall)
        self.lock = threading.Lock()

    def add(self, ms, wall):
        now = time.perf_counter()
        with self.lock:
            self.samples.append((now, ms, wall))
            while self.samples and self.samples[0][0] < now - self.WINDOW:
                self.samples.popleft()

    @property
    def value(self):
        with self.lock:
            ms = sum(s[1] for s in self.samples)
            wall = sum(s[2] for s in self.samples)
        return round(ms / wall, 1) if wall > 1e-3 else None


class RtMeter:
    """x real time, honestly: emulated ms per WALL second over the last
    ~second of the paced loop's `pacestatus` readings (sleeps, commands
    and actions included) / 1000. 1.0 = the unit's own clock. None until
    a window is there; reset on a fresh child (its clock starts over)."""
    WINDOW = 1.0

    def __init__(self):
        self.samples = collections.deque()      # (t, emulated ms)
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.samples.clear()

    def add(self, ms):
        now = time.perf_counter()
        with self.lock:
            self.samples.append((now, ms))
            # keep one sample older than the window so a value always spans it
            while len(self.samples) > 2 and self.samples[1][0] < now - self.WINDOW:
                self.samples.popleft()

    @property
    def value(self):
        with self.lock:
            if len(self.samples) < 2:
                return None
            (t0, m0), (t1, m1) = self.samples[0], self.samples[-1]
        return round((m1 - m0) / ((t1 - t0) * 1000.0), 3) if t1 - t0 >= 0.5 else None


# -- the DSP main output: the child's audio ring drained into the server ------
#
# With sound on the port child runs --dsp and streams core 0's main L/R over
# the pipe (O14k: `audio start main`, `audio read`, 16-bit, 44100 Hz, a 60 s
# ring in the child that overwrites its oldest frames when nobody reads).
# Panel._drain_audio pulls everything pending into AudioRing (the last
# AUDIO_RING_S seconds, absolute frame numbers) on every pump, after every
# action and between run_ms slices, and into a take file while frame mode
# is on: PLAY opens take-NNN.wav, STOP closes it -- what the unit played
# between the two keys, as it would come out of MAIN OUT. 12 Sep 2026.

AUDIO_RATE = 44100
AUDIO_RING_S = 180           # the server-side ring: 180 s x 44100 x 4 B = 31.8 MB, allocated on the first frame
AUDIO_READ_MAX = 441000      # frames per `audio read` (10 s = 3.5 MB of hex on one line); looped while full
SOUND_ON_RT_NOTE = "sound on -- the DSP cores run in real time (--dsp-rt: the JIT workers on the lockstep schedule, O17; /status rt says the rate)"
SOUND_ON_NOTE = "sound on -- the lockstep --dsp child: while it plays the unit runs ~0.2x real time (/status rt says how much)"
SOUND_OFF_NOTE = "sound off: the port child runs without the DSP cores"


def wav_header(frames, channels=2, rate=AUDIO_RATE, width=2):
    """The 44-byte RIFF/WAVE header for `frames` frames of PCM."""
    data = frames * channels * width
    return (b"RIFF" + struct.pack("<I", 36 + data) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * channels * width,
                                    channels * width, width * 8)
            + b"data" + struct.pack("<I", data))


def pcm_peak(data):
    """(peak L, peak R), 0..32767, of little-endian 16-bit stereo bytes.
    memoryview.cast iterates in C (this Mac is little-endian, as is every
    host the port builds on); no per-sample Python loop."""
    n = len(data) // 4 * 4
    if not n:
        return (0, 0)
    mv = memoryview(data)[:n].cast("h")
    l, r = mv[0::2], mv[1::2]
    return (min(32767, max(max(l), -min(l))), min(32767, max(max(r), -min(r))))


class AudioRing:
    """The last AUDIO_RING_S seconds of the main output, 16-bit stereo,
    addressed by ABSOLUTE frame number since the server's capture started:
    `end` counts every frame ever appended (across child respawns: the
    child's own ring restarts, this one does not), `first` is the oldest
    frame still held. A circular bytearray (4 bytes a frame) allocated on
    the first append; read() copies at most two slices under the lock and
    nothing per sample -- /audio/pcm serves from it on an HTTP thread
    without touching the emu thread."""

    def __init__(self, seconds=AUDIO_RING_S):
        self.cap = int(seconds * AUDIO_RATE)
        self.buf = None
        self.end = 0
        self.lock = threading.Lock()

    @property
    def first(self):
        return max(0, self.end - self.cap)

    def append(self, data):
        total = len(data) // 4
        if total <= 0:
            return
        with self.lock:
            if self.buf is None:
                self.buf = bytearray(self.cap * 4)
            skip = max(0, total - self.cap)         # more than the ring holds: keep the newest
            n = total - skip
            pos = ((self.end + skip) % self.cap) * 4
            room = self.cap * 4 - pos
            k = n * 4
            if k <= room:
                self.buf[pos:pos + k] = data[skip * 4:skip * 4 + k]
            else:
                self.buf[pos:] = data[skip * 4:skip * 4 + room]
                self.buf[:k - room] = data[skip * 4 + room:skip * 4 + k]
            self.end += total

    def read(self, start, max_frames):
        """(from, bytes, end): up to max_frames frames from max(start, first);
        empty bytes when start >= end."""
        with self.lock:
            end = self.end
            start = max(int(start), self.first)
            n = min(int(max_frames), end - start)
            if n <= 0 or self.buf is None:
                return start, b"", end
            pos = (start % self.cap) * 4
            room = self.cap * 4 - pos
            k = n * 4
            if k <= room:
                out = bytes(self.buf[pos:pos + k])
            else:
                out = bytes(self.buf[pos:]) + bytes(self.buf[:k - room])
            return start, out, end


class TakeWriter:
    """One take file, out/_panel_takes_<port>/take-NNN.wav: 16-bit stereo
    44.1 kHz, the RIFF/data sizes re-patched after every append so the file
    is a valid WAV at every moment (a reader that lands mid-take gets what
    is there so far)."""

    def __init__(self, path, n, start):
        self.path, self.n, self.start = pathlib.Path(path), n, start    # start: the ring frame it opened at
        self.frames = 0
        self.f = open(self.path, "wb")
        self.f.write(wav_header(0))
        self.f.flush()

    def _patch(self):
        self.f.seek(4); self.f.write(struct.pack("<I", 36 + self.frames * 4))
        self.f.seek(40); self.f.write(struct.pack("<I", self.frames * 4))
        self.f.flush()

    def append(self, data):
        if not data:
            return
        self.f.seek(0, 2)
        self.f.write(data)
        self.frames += len(data) // 4
        self._patch()

    def close(self):
        try:
            self._patch()
        finally:
            self.f.close()

    def info(self, recording=False):
        return {"n": self.n, "file": str(self.path), "frames": self.frames,
                "seconds": round(self.frames / AUDIO_RATE, 3), "recording": recording,
                "start": self.start}


# -- the output stage: the unit's outputs on a Mac audio device (13 Sep 2026) --
#
# An output stream (the `sounddevice` package: PortAudio over CoreAudio; the
# `emu` extra of pyproject.toml carries it -- `uv sync --extra emu`, or into
# an existing venv `uv pip install --python .venv/bin/python3 sounddevice`)
# on the device the user picks, fed from the same drain as the ring and the
# takes. With a device on, the child's capture runs `audio start tracks`
# (O23, 13 Sep 2026): the EIGHT ESAI words per frame (O14k: words 2/3 = main
# L/R, 4/5 = cue L/R, 0/1 and 6/7 whatever the DSP puts there, zero on the
# fixture) followed by the EIGHT PER-TRACK STEMS (T1 L, T1 R, ... T8 L,
# T8 R: each track's own term of the DSP's main mix, tapped inside the
# emulator's mixdown -- git show 666b6154:docs/firmware/COLDFIRE_PORT.md O23), 24 words a frame; an older
# child without `tracks` gets `all` (8 words). The drain de-interleaves main
# L/R for the ring, the takes and /audio/pcm -- byte for byte what `audio
# start main` gives -- and hands the whole frame to the output, which lays
# it out on the device as main L/R -> channels 1-2, cue L/R -> 3-4, tracks
# 1-8 -> 5-20 (T1 on 5-6 ... T8 on 19-20), words 0/1 -> 21-22, words 6/7 ->
# 23-24, as many of those pairs as the device has channels for (a 2-channel
# device gets main L/R, an 8-channel one main, cue and tracks 1-2, BlackHole
# 16ch main, cue and tracks 1-6). The stream is opened with exactly that
# many channels, so anything further on the device is silent. The PortAudio callback (its own thread) pulls from a
# deque of chunks: it plays nothing until OUTPUT_PRIME_S is queued, puts out
# zeros and counts an underrun when the queue runs dry (then primes again),
# and the push drops the OLDEST frames beyond OUTPUT_CAP_S queued so the
# latency stays bounded -- counted as `dropped` while the stream plays (an
# audible skip) and as `trimmed` while it is re-priming after a gap (the
# fresh child's boot burst after a reboot: nothing was due, nothing heard). Two clocks -- the child's pacer (44,100
# frames per wall second) and the device's own -- so a long session drifts
# by their difference and shows it as an underrun or a drop now and then.
# Nothing here touches the emu thread: sounddevice is imported on first use,
# every PortAudio call is caught, a device that goes away stops the stream
# with a note.

OUTPUT_BLOCK = 512           # frames per PortAudio callback (11.6 ms)
OUTPUT_PRIME_S = 0.10        # queued before the stream plays (the drain runs every PACE_POLL_S = 20 ms)
OUTPUT_CAP_S = 0.25          # queued beyond this: the oldest frames are dropped, and counted
OUTPUT_STALL_S = 3.0         # no callback for this long while frames arrive: the device is gone, the stream stops
# The child's word pairs (pair k = words 2k/2k+1 of a frame) onto device channel
# pairs, per capture mode: main (2/3) -> 1-2, cue (4/5) -> 3-4, then (O23) the
# eight stems (pairs 4-11) -> 5-20, then ESAI words 0/1 and 6/7.
OUTPUT_ORDER = {2: (0,), 8: (1, 2, 0, 3), 24: (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 0, 3)}
OUTPUT_PAIR_NAMES = {2: ("main L/R",), 8: ("main L/R", "cue L/R", "ESAI words 0/1", "ESAI words 6/7"),
                     24: ("main L/R", "cue L/R") + tuple(f"track {k + 1} L/R" for k in range(8)) + ("ESAI words 0/1", "ESAI words 6/7")}
OUTPUT_MAX_CHANNELS = 24
CAPTURE_WORDS = {"main": 2, "all": 8, "tracks": 24}   # words a frame per `audio start <mode>`
OUTPUT_CAPTURE = "tracks"                              # the capture a device is fed from (falls back to all, then main)

_sd_lock = threading.Lock()
_sd_state = {}


def sounddevice():
    """The `sounddevice` module, imported on first use (its import
    initialises PortAudio, which enumerates every CoreAudio device: not at
    server start, and never fatal). (module | None, note)."""
    with _sd_lock:
        if "mod" not in _sd_state:
            try:
                import sounddevice as sd
                _sd_state["mod"], _sd_state["note"] = sd, None
            except Exception as e:  # ImportError, or PortAudio failing to load
                _sd_state["mod"] = None
                _sd_state["note"] = (f"the sounddevice package is not available ({type(e).__name__}: {e}); "
                                     "`uv sync --extra emu` (or `uv pip install --python .venv/bin/python3 sounddevice`) installs it")
        return _sd_state["mod"], _sd_state["note"]


def audio_devices(refresh=True):
    """Every output-capable device PortAudio sees, as [{index, name,
    channels, rate, default, hostapi}]. `refresh` re-initialises PortAudio
    first, so a device plugged in since the last call appears -- only with
    no stream open (the caller knows). (list | None, note)."""
    sd, note = sounddevice()
    if sd is None:
        return None, note
    if refresh:
        try:
            sd._terminate()
            sd._initialize()
        except Exception as e:
            note = f"device rescan failed ({type(e).__name__}: {e}); the list may be stale"
    try:
        devs = sd.query_devices()
        default = int(sd.default.device[1])
    except Exception as e:
        return None, f"PortAudio: {type(e).__name__}: {e}"
    out = []
    for i, d in enumerate(devs):
        if int(d.get("max_output_channels", 0)) > 0:
            try:
                api = sd.query_hostapis(d["hostapi"])["name"]
            except Exception:
                api = None
            out.append({"index": i, "name": d["name"], "channels": int(d["max_output_channels"]),
                        "rate": float(d["default_samplerate"]), "default": i == default, "hostapi": api})
    return out, note


def resolve_device(spec, devices):
    """An index, or a name (exact, then case-insensitive, then a unique
    case-insensitive substring) -> the device dict; LookupError otherwise."""
    s = str(spec).strip()
    if s.isdigit():
        for d in devices:
            if d["index"] == int(s):
                return d
        raise LookupError(f"no output device with index {s}")
    for d in devices:
        if d["name"] == s:
            return d
    low = s.lower()
    hits = [d for d in devices if d["name"].lower() == low] or [d for d in devices if low in d["name"].lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise LookupError(f"no output device named {s!r}")
    raise LookupError(f"{s!r} matches {len(hits)} devices: " + ", ".join(d["name"] for d in hits))


class AudioOutput:
    """One PortAudio output stream on one device: Panel._drain_audio pushes
    the child's frames (2 or 8 words each) laid out for the device, the
    callback plays them on PortAudio's thread. Counters for /audio/status."""

    def __init__(self, sd, device):
        self.device = device                         # the dict audio_devices() gave
        self.index, self.name = device["index"], device["name"]
        n = int(device["channels"])
        if n < 2:
            raise ValueError(f"{self.name} has {n} output channel(s); the unit's outputs need at least 2")
        self.channels = min(OUTPUT_MAX_CHANNELS, n - n % 2)   # 2..24, even: the pairs the device has room for
        self.units = self.channels // 2              # stereo pairs per device frame
        self.bpf = self.channels * 2                 # bytes per device frame (int16)
        self.q = collections.deque()                 # chunks in device frame layout
        self.off = 0                                 # bytes of q[0] already played
        self.qbytes = 0
        self.lock = threading.Lock()
        self.prime_bytes = int(OUTPUT_PRIME_S * AUDIO_RATE) * self.bpf
        self.cap_bytes = int(OUTPUT_CAP_S * AUDIO_RATE) * self.bpf
        self.primed = False
        self.underruns = 0      # callbacks the queue could not fill: zeros went out, then a re-prime
        self.dropped = 0        # frames dropped at the push, oldest first, beyond OUTPUT_CAP_S queued WHILE PLAYING (audible)
        self.trimmed = 0        # ... the same while re-priming after a gap (a reboot's boot burst, a pause): nothing was due
        self.pushed = 0         # frames the drain handed over
        self.played = 0         # frames the callback took from the queue
        self.callbacks = 0
        self.pa_underflows = 0  # PortAudio's own output-underflow flag on a callback
        self.words = 2          # words per frame of the last push: 2 = main only, 8 = all, 24 = tracks
        self.started = time.time()
        self.started_mono = time.monotonic()
        self.last_cb = None
        self.note = None
        self.closing = False
        self.running = False
        self.stream = sd.RawOutputStream(samplerate=AUDIO_RATE, device=self.index, channels=self.channels,
                                         dtype="int16", blocksize=OUTPUT_BLOCK, latency="low",
                                         callback=self._callback, finished_callback=self._finished)
        self.stream.start()
        self.running = True

    def channel_map(self):
        """The device's channel pairs by name, for the words the child streams
        now (the capture mode): what the stream carries, then what stays silent."""
        names = OUTPUT_PAIR_NAMES.get(self.words, OUTPUT_PAIR_NAMES[2])
        k = min(self.units, len(names))
        m = [f"{names[i]} -> {2 * i + 1}-{2 * i + 2}" for i in range(k)]
        if self.units > k:
            m.append(f"{self.channels - 2 * k} further channels silent (the capture is {'main only' if self.words == 2 else 'main, cue and the ESAI words'})")
        return m

    def layout(self, data, words):
        """The child's frames (`words` int16 each) as device frames: the
        pairs in OUTPUT_ORDER[words], as many as the device has channels for
        -- memoryview strides, nothing per sample. 2-word frames (the `main`
        capture) fill the first pair only."""
        n = len(data) // (words * 2)
        src = memoryview(data)[:n * words * 2].cast("i")     # one int32 per L/R pair
        su = words // 2
        order = OUTPUT_ORDER.get(words, (0,))
        if self.units == 1 and su == 1:
            return bytes(src)
        out = bytearray(n * self.bpf)
        om = memoryview(out).cast("i")
        for k in range(min(self.units, len(order))):
            om[k::self.units] = src[order[k]::su]
        return out

    def push(self, data, words):
        """From the drain (the emu thread): queue, then drop the oldest
        beyond the cap. A device that stopped calling back stops the stream."""
        if not self.running or self.closing:
            return
        last = self.last_cb if self.last_cb is not None else self.started_mono
        if time.monotonic() - last > OUTPUT_STALL_S:
            self.stop(f"stopped: no callback from {self.name} for {OUTPUT_STALL_S:.0f} s (unplugged, or taken by another app?)")
            return
        out = self.layout(data, words)
        self.words = words
        with self.lock:
            self.q.append(out)
            self.qbytes += len(out)
            self.pushed += len(out) // self.bpf
            excess = self.qbytes - self.cap_bytes
            while excess > 0 and self.q:
                c = self.q[0]
                k = min(len(c) - self.off, excess)
                self.off += k
                self.qbytes -= k
                excess -= k
                if self.primed:
                    self.dropped += k // self.bpf
                else:
                    self.trimmed += k // self.bpf
                if self.off >= len(c):
                    self.q.popleft()
                    self.off = 0

    def _callback(self, outdata, frames, t, status):
        self.callbacks += 1
        self.last_cb = time.monotonic()
        if status and status.output_underflow:
            self.pa_underflows += 1
        need = frames * self.bpf
        with self.lock:
            if not self.primed:
                if self.qbytes < self.prime_bytes:
                    outdata[:need] = bytes(need)
                    return
                self.primed = True
            got = 0
            while got < need and self.q:
                c = self.q[0]
                take = min(len(c) - self.off, need - got)
                outdata[got:got + take] = bytes(c[self.off:self.off + take])
                got += take
                self.off += take
                self.qbytes -= take
                if self.off >= len(c):
                    self.q.popleft()
                    self.off = 0
            self.played += got // self.bpf
            if got < need:
                outdata[got:need] = bytes(need - got)
                self.underruns += 1
                self.primed = False

    def _finished(self):
        self.running = False
        if not self.closing and not self.note:
            self.note = f"the stream on {self.name} ended by itself (device unplugged?)"

    def stop(self, note=None):
        self.closing = True
        self.running = False
        if note:
            self.note = note
        try:
            self.stream.abort(ignore_errors=True)     # not stop(): that waits for a device that may be gone
            self.stream.close(ignore_errors=True)
        except Exception as e:
            self.note = (self.note + "; " if self.note else "") + f"close: {type(e).__name__}: {e}"

    def status(self):
        with self.lock:
            qb = self.qbytes
        try:
            lat = round(float(self.stream.latency) * 1000.0, 1)
        except Exception:
            lat = None
        return {"device": self.name, "index": self.index, "channels": self.channels,
                "device_channels": int(self.device["channels"]), "running": self.running,
                "underruns": self.underruns, "dropped": self.dropped, "trimmed": self.trimmed, "latency_ms": lat,
                "buffered_ms": round(qb / self.bpf / AUDIO_RATE * 1000.0, 1), "primed": self.primed,
                "pushed": self.pushed, "played": self.played, "callbacks": self.callbacks,
                "pa_underflows": self.pa_underflows, "words": self.words, "map": self.channel_map(),
                "layout": list(OUTPUT_PAIR_NAMES.get(self.words, OUTPUT_PAIR_NAMES[2])[:self.units]),
                "since": self.started, "note": self.note}


class PortRx:
    """`rt.uart64.rx` for the port: extend([row, byte]) sends key/knob."""

    def __init__(self, rt):
        self.rt = rt

    def extend(self, seq):
        seq = list(seq)
        for i in range(0, len(seq) - 1, 2):
            row, val = int(seq[i]) & 0xff, int(seq[i + 1]) & 0xff
            if 0x30 <= row < 0x40:
                delta = val - 256 if val > 127 else val
                self.rt.proc.command(f"knob {row:#04x} {delta}", "ok")
            else:
                self.rt.proc.command(f"key {row:#04x} {val:#04x}", "ok")

    def append(self, b):
        raise TypeError("send whole [row, byte] reports with extend()")


class PortUart:
    def __init__(self, rt):
        self.name = "UART@fc064000 (port)"
        self.rx = PortRx(rt)
        self.tx = bytearray()           # grows as PortRt.poll_tx() drains the child


class PortMem:
    """`rt.uc` for the port: mem_read/mem_write over peek/poke (4 KB chunks)."""
    CHUNK = 4096

    def __init__(self, rt):
        self.rt = rt

    def mem_read(self, addr, n):
        out = bytearray()
        while n > 0:
            k = min(n, self.CHUNK)
            rep = self.rt.proc.command(f"peek {addr:#x} {k}", "peek")
            data = bytes.fromhex(rep[5:].strip())
            if len(data) != k:
                raise PortError(f"peek {addr:#x} {k}: {len(data)} bytes back")
            out += data
            addr += k; n -= k
        return out

    def mem_write(self, addr, data):
        data = bytes(data)
        for i in range(0, len(data), self.CHUNK):
            self.rt.proc.command(f"poke {addr + i:#x} {data[i:i + self.CHUNK].hex()}", "ok")


class PortRt:
    """The Panel's handle on the port child, over the interactive protocol:
    run(ms=), uart64.rx/tx, uc.mem_read/mem_write, sample, frame,
    pattern_base(), poke_trig(), internal_clock() -- the shape of the
    retired route A's emu_rtos.Rtos."""

    SLICE_MS = 20.0         # run_ms() slice: a round trip each, ~0.1 s wall while playing

    def __init__(self, proc, meter=None):
        self.proc = proc
        self.sample, self.frames = proc.ready
        self.stop_reason = None
        self.meter = meter
        self._frame = False
        self.next_frame = None          # set by Panel._before_play; the port keeps its own
        self.uart64 = PortUart(self)
        self.uc = PortMem(self)

    def run(self, ms=None, until=None, max_bursts=None, wall=None):
        """`run <ms>`, or with `wall` (seconds) `run <ms> wall <s>` (O15f):
        the child also stops when that much wall time is spent, stop_reason
        "wall" -- so a slice is bounded in wall time whatever the core's
        rate. Where it stops moves no firmware event."""
        if ms is None or until is not None or max_bursts is not None:
            raise TypeError("the port backend runs by ms only")
        t0 = time.perf_counter()
        line = f"run {float(ms):g}" + (f" wall {float(wall):g}" if wall is not None else "")
        rep = self.proc.command(line, "ok")
        wall_s = time.perf_counter() - t0
        f = dict(kv.split("=", 1) for kv in rep.split()[1:] if "=" in kv)
        s0 = self.sample
        self.sample = float(f.get("sample", self.sample))
        self.frames = int(f.get("frames", self.frames))
        self.stop_reason = f.get("stop", "?")
        if self.meter is not None:
            # what really ran (a wall-ended run advanced less than ms)
            self.meter.add((self.sample - s0) / SAMPLE_HZ * 1000.0 if wall is not None else float(ms), wall_s)
        return self.stop_reason

    # -- O15f: the child paces itself (see Panel._loop_paced) -------------
    paced = False           # `pace on` accepted by this child

    def pace(self, on, rate=1.0):
        self.proc.command(f"pace on {float(rate):g}" if on else "pace off", "ok")
        self.paced = bool(on)

    def pacestatus(self):
        """The child's own pacer figures as a dict (strings); updates
        sample from its `ms`."""
        rep = self.proc.command("pacestatus", "pacestatus")
        f = dict(kv.split("=", 1) for kv in rep.split()[1:] if "=" in kv)
        if "ms" in f:
            self.sample = float(f["ms"]) * SAMPLE_HZ / 1000.0
        return f

    def poll_tx(self):
        """Drain UART A's transmit bytes into uart64.tx; returns how many."""
        rep = self.proc.command("tx", "tx")
        data = bytes.fromhex(rep[3:].strip())
        self.uart64.tx += data
        return len(data)

    @property
    def frame(self):
        return self._frame

    @frame.setter
    def frame(self, on):
        self.proc.command(f"frame {'on' if on else 'off'}", "ok")
        self._frame = bool(on)

    def status(self):
        rep = self.proc.command("status", "status")
        return dict(kv.split("=", 1) for kv in rep.split()[1:] if "=" in kv)

    def pattern_base(self):
        """emu_rtos.Rtos.pattern_base, via peek: PART_PTR's blob + pattern * stride."""
        blob = int.from_bytes(self.uc.mem_read(ec.PART_PTR, 4), "big")
        return blob + self.uc.mem_read(CUR_PATTERN, 1)[0] * PATTERN_STRIDE

    def poke_trig(self, step):
        """emu_rtos.Rtos.poke_trig, via peek/poke (track 1, step 1-64)."""
        blob = int.from_bytes(self.uc.mem_read(ec.PART_PTR, 4), "big")
        at = blob + 7 - (step - 1) // 8
        v = self.uc.mem_read(at, 1)[0] | (1 << ((step - 1) % 8))
        self.uc.mem_write(at, bytes([v]))
        return v

    def internal_clock(self):
        """emu_rtos.Rtos.internal_clock: clear CLOCK RECEIVE (0x80000028 bit 0)."""
        midi = self.uc.mem_read(FW_MIDI_SETTINGS, 1)[0]
        self.uc.mem_write(FW_MIDI_SETTINGS, bytes([midi & ~1]))
        return midi


def port_available(port_bin=PORT_BIN, build=True, log=print):
    """(usable, note): the port binary exists and carries --interactive;
    built here when missing (cmake --fresh + build, ~1-2 min). The note says
    what happened; it lands in /status backend_note on a fallback."""
    port_bin = pathlib.Path(port_bin)
    note = ""
    if not port_bin.exists():
        if not build:
            return False, f"{port_bin} missing"
        log(f"port: {port_bin} missing, building (cmake --fresh -B {PORT_BUILD} -S {PORT_SRC}) ...")
        env = dict(os.environ, PATH="/opt/homebrew/bin:" + os.environ.get("PATH", ""))
        try:
            # The host's own architecture, as `make emu-cf` passes it: an
            # Intel-Homebrew cmake configures x86_64 and the port then runs
            # under Rosetta (Makefile emu-cf).
            for cmd in (["cmake", "--fresh", "-B", str(PORT_BUILD), "-S", str(PORT_SRC),
                         f"-DCMAKE_OSX_ARCHITECTURES={platform.machine()}"],
                        ["cmake", "--build", str(PORT_BUILD), "-j8"]):
                r = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=900)
                if r.returncode:
                    tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
                    return False, f"port build failed ({' '.join(cmd[:2])} rc {r.returncode}): {' | '.join(tail)}"
        except Exception as e:
            return False, f"port build failed: {type(e).__name__}: {e}"
        note = "port built here; "
        if not port_bin.exists():
            return False, note + f"{port_bin} still missing after the build"
    if port_bin.suffix != ".py" and b"--interactive" not in port_bin.read_bytes():
        return False, note + f"{port_bin} has no --interactive (built before the protocol landed)"
    return True, note.rstrip("; ")


# -- the sample pool: the set's AUDIO folder, one per server port --------------
#
# On the unit samples live on the CF card in the set's AUDIO folder; the
# user copies files there (USB disk mode) and loads them into slots from the
# firmware's own file browser. Here the card is a FAT image built from a
# staged tree at boot and there is no hot-plug, so the pool below is the
# AUDIO folder the card is built FROM: /samples/add and /upload put files in
# it, /samples/commit rebuilds the image with every file in it and reboots
# the child on the new image -- re-inserting the card. One pool per server
# port (out/_panel_pool_<port>/), wiped and re-seeded at start from the
# project's sibling AUDIO and --audio, so nothing a running server adds
# lands in the fixture folder. 12 Sep 2026.

AFCONVERT = "/usr/bin/afconvert"
SAMPLE_EXTS = (".wav", ".aif", ".aiff")
_NAME_BAD = re.compile(r"[^A-Za-z0-9._ -]")      # the card is VFAT with long names: keep the
                                                 # name, replace what is outside this set


def _ext80(b):
    """The 80-bit extended float an AIFF COMM chunk keeps its sample rate in."""
    se = int.from_bytes(b[:2], "big")
    mant = int.from_bytes(b[2:10], "big")
    if (se & 0x7fff) == 0 and mant == 0:
        return 0.0
    val = mant * 2.0 ** ((se & 0x7fff) - 16383 - 63)
    return -val if se & 0x8000 else val


def sample_header(path):
    """What the file's own header says (`path`, or the file's first bytes as
    a bytes object -- the card reader hands those over), stdlib only: {"kind": "WAV" | "AIFF" |
    "AIFC", "channels", "rate", "bits", "pcm", "tag"} from the RIFF/WAVE fmt
    chunk or the FORM/AIFF COMM chunk; None for anything else (mp3, flac,
    aac, a truncated file). "pcm": integer PCM (WAV format tag 1, or 0xfffe
    with a PCM SubFormat; AIFF, or AIFC with NONE/twos); "tag": the WAV format
    tag as written (0xfffe = WAVE_FORMAT_EXTENSIBLE, which the unit reads
    when its SubFormat is PCM -- measured 12 Sep 2026: a 16-bit 44.1 kHz
    stereo extensible WAV listed with footer `44.1k 16b 2Ch` and loaded
    into STATIC 6; afconvert keeps such a header anyway, so converting it
    changed nothing), the AIFC compression code for an AIFC, None for AIFF."""
    try:
        with (io.BytesIO(path) if isinstance(path, (bytes, bytearray)) else open(path, "rb")) as f:
            head = f.read(12)
            if len(head) < 12:
                return None
            if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
                while True:
                    ch = f.read(8)
                    if len(ch) < 8:
                        return None
                    tag, size = ch[:4], struct.unpack("<I", ch[4:])[0]
                    if tag == b"fmt ":
                        fmt = f.read(min(size, 40))
                        if len(fmt) < 16:
                            return None
                        code, chans, rate, _, _, bits = struct.unpack("<HHIIHH", fmt[:16])
                        tag = code
                        if code == 0xfffe and len(fmt) >= 26:
                            code = struct.unpack("<H", fmt[24:26])[0]   # SubFormat GUID, leading word
                        return {"kind": "WAV", "channels": chans, "rate": rate, "bits": bits,
                                "pcm": code == 1, "tag": tag}
                    f.seek(size + (size & 1), 1)
            if head[:4] == b"FORM" and head[8:12] in (b"AIFF", b"AIFC"):
                kind = head[8:12].decode()
                while True:
                    ch = f.read(8)
                    if len(ch) < 8:
                        return None
                    tag, size = ch[:4], struct.unpack(">I", ch[4:])[0]
                    if tag == b"COMM":
                        comm = f.read(min(size, 22))
                        if len(comm) < 18:
                            return None
                        chans, _, bits = struct.unpack(">hIh", comm[:8])
                        comp = comm[18:22] if kind == "AIFC" else b"NONE"
                        # "twos" is what afconvert -f AIFC -d BEI16 writes: big-endian
                        # integer PCM, the same bytes as NONE (12 Sep 2026)
                        return {"kind": kind, "channels": chans, "rate": int(round(_ext80(comm[8:18]))),
                                "bits": bits, "pcm": comp in (b"NONE", b"twos"),
                                "tag": comp.decode("latin-1") if kind == "AIFC" else None}
                    f.seek(size + (size & 1), 1)
    except OSError:
        return None
    return None


def sample_format(info, path=None):
    """'16-bit 44.1 kHz stereo WAV' from sample_header's dict (or the suffix
    of an unparsed file: 'MP3 (not WAV/AIFF)')."""
    if not info:
        ext = pathlib.Path(path).suffix.lstrip(".").upper() if path else ""
        return f"{ext or '?'} (not WAV/AIFF)"
    chans = {1: "mono", 2: "stereo"}.get(info["channels"], f"{info['channels']}-channel")
    kind = info["kind"]
    if info["kind"] == "WAV" and info["tag"] == 0xfffe:
        kind += " (extensible)"                     # only a 0xfffe tag, whatever its SubFormat
    if not info["pcm"]:
        kind += " (not integer PCM)"
    return f"{info['bits']}-bit {info['rate'] / 1000:g} kHz {chans} {kind}"


def sample_ok_as_is(info):
    """The unit's own rule: WAV or AIFF, integer PCM, 16 or 24 bit, 44.1 kHz,
    mono or stereo. An extensible WAV with a PCM SubFormat passes (the unit
    reads it, sample_header); AIFC does not (afconvert makes a WAV of it)."""
    return bool(info) and info["kind"] in ("WAV", "AIFF") and info["pcm"] \
        and info["bits"] in (16, 24) and info["rate"] == 44100 and info["channels"] in (1, 2)


class SamplePool:
    """out/_panel_pool_<port>/: the files the card's AUDIO folder is built from.

    add() is the one path for /samples/add, /samples/upload and --audio:
    read the header, convert with afconvert when the unit would not read
    the file as it is (`afconvert -f WAVE -d LEI16@44100 in out`, channels
    kept; the exact command goes into the reply note), write into the
    folder under the original basename with the extension normalised and
    characters outside [A-Za-z0-9._ -] replaced. A name already in the pool
    (case-insensitively) is refused unless the bytes are identical."""

    def __init__(self, path, wipe=True):
        self.path = pathlib.Path(path)
        if wipe and self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def names(self):
        return sorted((p.name for p in self.path.iterdir() if p.is_file() and not p.name.startswith(".")),
                      key=str.lower)

    def find(self, name):
        """The pool file called `name`, case-insensitively, or None."""
        low = name.lower()
        for n in self.names():
            if n.lower() == low:
                return self.path / n
        return None

    def files(self):
        out = []
        for n in self.names():
            p = self.path / n
            out.append({"name": n, "bytes": p.stat().st_size, "format": sample_format(sample_header(p), p)})
        return out

    def manifest(self):
        """{name: (size, mtime_ns)}: what the card was (or would be) built from."""
        return {n: (st.st_size, st.st_mtime_ns) for n in self.names() for st in (os.stat(self.path / n),)}

    def total_bytes(self):
        return sum(os.stat(self.path / n).st_size for n in self.names())

    def audio_specs(self):
        """stage_project's audio list: every pool file as AUDIO/<name>."""
        return [f"{self.path / n}:AUDIO/{n}" for n in self.names()]

    def seed(self, src_dir, convert=True, log=print):
        """Every WAV/AIFF in src_dir through add() (convert=False copies the
        project's own pool as it was saved). Returns the names added."""
        src_dir = pathlib.Path(src_dir).expanduser()
        added = []
        if not src_dir.is_dir():
            log(f"samples: {src_dir}: not a directory, nothing seeded")
            return added
        for p in sorted(src_dir.iterdir(), key=lambda q: q.name.lower()):
            if p.is_file() and p.suffix.lower() in SAMPLE_EXTS and not p.name.startswith("."):
                r = self.add(p) if convert else self._copy_verbatim(p)
                if r["ok"]:
                    added.append(r["name"])
                else:
                    log(f"samples: {p.name}: {r['error']}")
        return added

    def _copy_verbatim(self, src):
        dst = self.path / src.name
        if dst.exists() and not filecmp.cmp(src, dst, shallow=False):
            return {"ok": False, "error": f"{src.name}: a different file of that name is in the pool"}
        shutil.copyfile(src, dst)
        return {"ok": True, "name": src.name, "converted": False, "note": "the project's own pool, copied as is"}

    @staticmethod
    def card_name(raw, info, convert):
        """The name on the card: basename, extension normalised (.wav for a
        WAV or anything converted, .aif/.aiff kept for an AIFF), the rest
        VFAT-safe ASCII."""
        raw = pathlib.Path(raw).name.strip().lstrip(".")
        stem, dot, ext = raw.rpartition(".")
        if not dot:
            stem, ext = raw, ""
        ext = "." + ext.lower() if ext else ""
        if convert or (info and info["kind"] == "WAV"):
            ext = ".wav"
        elif info and info["kind"] == "AIFF" and ext not in (".aif", ".aiff"):
            ext = ".aif"
        stem = _NAME_BAD.sub("_", stem).strip() or "sample"
        return stem + ext

    def add(self, src, name=None, timeout=600, shown=None):
        """Validate -> convert if needed -> write into the pool. Returns the
        /samples/add reply dict. The note names the source as the caller
        knows it (`shown`: an upload's own name, not the dot-temporary its
        bytes landed in) and the pool file it became; "cmd" is afconvert's
        argv exactly as run, temporaries included."""
        src = pathlib.Path(src).expanduser()
        shown = shown or str(src)
        if not src.is_file():
            return {"ok": False, "error": f"{shown}: not a file"}
        if src.stat().st_size == 0:
            return {"ok": False, "error": f"{pathlib.Path(shown).name}: empty file"}
        info = sample_header(src)
        convert = not sample_ok_as_is(info)
        name = self.card_name(name or src.name, info, convert)
        was = sample_format(info, src)
        cmd = None
        with self.lock:
            tmp = self.path / f".incoming-{os.getpid()}-{name}"
            try:
                if convert:
                    cmd = [AFCONVERT, "-f", "WAVE", "-d", "LEI16@44100"]
                    if info and info["channels"] > 2:
                        cmd += ["-c", "2"]              # the unit reads mono or stereo only
                    said = " ".join(cmd + [shown, str(self.path / name)])
                    cmd += [str(src), str(tmp)]
                    try:
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                    except (OSError, subprocess.TimeoutExpired) as e:
                        return {"ok": False, "error": f"afconvert: {type(e).__name__}: {e}", "cmd": " ".join(cmd)}
                    if r.returncode or not tmp.exists():
                        tail = " | ".join((r.stderr or r.stdout).strip().splitlines()[-4:]) or "(no output)"
                        return {"ok": False, "error": f"afconvert failed (rc {r.returncode}): {tail}",
                                "cmd": " ".join(cmd), "was": was}
                    note = f"converted from {was}: {said}"
                else:
                    shutil.copyfile(src, tmp)
                    note = f"{was}, copied as is"
                have = self.find(name)
                if have is not None:
                    if filecmp.cmp(have, tmp, shallow=False):
                        return self._added(have, convert, note + f"; already in the pool as {have.name}"
                                           " (identical bytes)", cmd)
                    return {"ok": False, "error": f"{have.name} is already in the pool with different"
                                                  " content: remove it first, or rename the file",
                            "was": was}
                tmp.replace(self.path / name)
            finally:
                if tmp.exists():
                    tmp.unlink()
        return self._added(self.path / name, convert, note, cmd)

    @staticmethod
    def _added(out, convert, note, cmd):
        r = {"ok": True, "name": out.name, "converted": convert, "note": note,
             "bytes": out.stat().st_size, "format": sample_format(sample_header(out), out)}
        if cmd:
            r["cmd"] = " ".join(cmd)
        return r

    def remove(self, name):
        have = self.find(name)
        if have is None:
            return {"ok": False, "error": f"{name}: not in the pool"}
        have.unlink()
        return {"ok": True, "name": have.name}


# -- the persistent card (O19, 13 Sep 2026) ------------------------------------
#
# With --card the image file IS the card: the child boots it with --card-rw
# (AtaCard::setWriteBack: every sector the firmware writes is pwrite()n to
# the file as the WRITE completes), so SAVE PROJECT on the unit lands in it
# and the next boot on the same file finds it. What the server needs of the
# card without a mount -- the AUDIO folder's listing, the sets and projects
# for the sidecar -- comes from Fat16Image below, a read-only walk of the
# FAT16 volume the builder writes (emu_card._Fat16: MBR + one partition at
# LBA 2048, 512-byte sectors, LFN entries). Changing the card goes through
# an hdiutil mount (card_attach / card_detach), ONLY while the child is
# stopped: a re-insert copies the pool's pending files into <SET>/AUDIO
# and deletes the marked ones; an eject leaves it mounted for Finder.

CARD_DROPPINGS = (".fseventsd", ".Spotlight-V100", ".Trashes", ".TemporaryItems",
                  ".metadata_never_index", ".DS_Store", ".VolumeIcon.icns")


class Fat16Image:
    """A read-only walk of the card image's first partition (FAT16, as
    emu_card.build_image lays it out; macOS writes the same). Stdlib only,
    no mount: safe beside a running child (which writes whole sectors
    through, O19). listdir(cluster) parses 8.3 + VFAT long names."""

    def __init__(self, path):
        self.f = open(path, "rb")
        try:
            mbr = self._sectors(0, 1)
            if len(mbr) < 512 or mbr[510:512] != b"\x55\xaa":
                raise ValueError("no MBR signature")
            self.part = struct.unpack_from("<I", mbr, 446 + 8)[0]
            bpb = self._sectors(self.part, 1)
            bps, spc, reserved, nfats, root_entries, total16, _media, spf = struct.unpack_from("<HBHBHHBH", bpb, 11)
            total32 = struct.unpack_from("<I", bpb, 32)[0]
            if bps != 512 or not spc or not spf:
                raise ValueError(f"unexpected BPB (bytes/sector {bps}, spc {spc}, spf {spf})")
            self.spc = spc
            self.total = total16 or total32
            self.fat_start = self.part + reserved
            self.root_start = self.fat_start + nfats * spf
            self.root_sectors = root_entries * 32 // 512
            self.data_start = self.root_start + self.root_sectors
            self.label = bpb[43:54].decode("ascii", "replace").strip()
            fat = self._sectors(self.fat_start, spf)
            self.fat = struct.unpack(f"<{len(fat) // 2}H", fat)
        except Exception:
            self.f.close()
            raise

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _sectors(self, lba, n):
        self.f.seek(lba * 512)
        return self.f.read(n * 512)

    def chain(self, c):
        out, seen = [], set()
        while 2 <= c < 0xfff8 and c < len(self.fat) and c not in seen:
            out.append(c); seen.add(c)
            c = self.fat[c]
        return out

    def _cluster(self, c):
        return self._sectors(self.data_start + (c - 2) * self.spc, self.spc)

    def read(self, entry, limit=None):
        """The file's bytes (the first `limit` of them)."""
        want = entry["size"] if limit is None else min(entry["size"], limit)
        out = bytearray()
        for c in self.chain(entry["cluster"]):
            if len(out) >= want:
                break
            out += self._cluster(c)
        return bytes(out[:want])

    def listdir(self, cluster=0):
        """The entries of a directory (0 = the root): name (long, else 8.3),
        short, dir, hidden, cluster, size. `.` and `..` are left out."""
        if cluster == 0:
            raw = self._sectors(self.root_start, self.root_sectors)
        else:
            raw = b"".join(self._cluster(c) for c in self.chain(cluster))
        entries, lfn = [], {}
        for i in range(0, len(raw), 32):
            e = raw[i:i + 32]
            if len(e) < 32 or e[0] == 0:
                break
            if e[0] == 0xe5:
                lfn = {}
                continue
            attr = e[11]
            if attr == 0x0f:
                lfn[e[0] & 0x1f] = e[1:11] + e[14:26] + e[28:32]
                continue
            if attr & 0x08:
                lfn = {}
                continue                    # the volume label
            stem = e[:8].decode("latin-1").rstrip()
            ext = e[8:11].decode("latin-1").rstrip()
            short = stem + ("." + ext if ext else "")
            if e[0] == 0x05:
                short = "\xe5" + short[1:]
            name = None
            if lfn:
                u = b"".join(lfn[k] for k in sorted(lfn))
                name = u.decode("utf-16-le", "replace").split("\x00")[0].rstrip("\uffff")
            lfn = {}
            if short in (".", ".."):
                continue
            entries.append({"name": name or short, "short": short, "dir": bool(attr & 0x10),
                            "hidden": bool(attr & 0x02),
                            "cluster": struct.unpack_from("<H", e, 26)[0],
                            "size": struct.unpack_from("<I", e, 28)[0]})
        return entries

    def find(self, *parts):
        """The entry at the path `parts` (case-insensitive on long and short
        names), or None."""
        cluster, entry = 0, None
        for part in parts:
            low = part.lower()
            entry = next((e for e in self.listdir(cluster) if e["name"].lower() == low or e["short"].lower() == low), None)
            if entry is None:
                return None
            cluster = entry["cluster"]
        return entry

    def sets(self):
        """{set: [project, ...]}: every root folder with its sub-folders
        that hold a project.work or bank01.work (AUDIO and dot folders
        left out)."""
        out = {}
        for e in self.listdir(0):
            if not e["dir"] or e["name"].startswith("."):
                continue
            projects = []
            for sub in self.listdir(e["cluster"]):
                if not sub["dir"] or sub["name"].startswith(".") or sub["name"].upper() == "AUDIO":
                    continue
                names = {x["name"].lower() for x in self.listdir(sub["cluster"])}
                if names & {"project.work", "project.strd", "bank01.work", "bank01.strd"}:
                    projects.append(sub["name"])
            out[e["name"]] = projects
        return out


def card_audio_listing(image, set_name, header_bytes=16384):
    """What is in <SET>/AUDIO on the card image: {name: {"bytes", "format"}}
    (the format from the file's own header, sample_header on its first
    bytes); dot files and folders are left out. {} when the folder is not
    there."""
    out = {}
    try:
        with Fat16Image(image) as img:
            audio = img.find(set_name, "AUDIO")
            if audio is None or not audio["dir"]:
                return out
            for e in img.listdir(audio["cluster"]):
                if e["dir"] or e["name"].startswith(".") or e["hidden"]:
                    continue
                info = sample_header(img.read(e, header_bytes)) if e["size"] else None
                out[e["name"]] = {"bytes": e["size"], "format": sample_format(info, e["name"])}
    except (OSError, ValueError, struct.error) as e:
        print(f"panel: card listing failed: {type(e).__name__}: {e}")
    return out


def card_attach(image, readonly=False, browse=False, timeout=120):
    """hdiutil attach of a raw card image; (device, mount point). Verified
    13 Sep 2026: `-imagekey diskimage-class=CRawDiskImage` mounts the
    builder's image as FDisk + DOS_FAT_16 at /Volumes/<label> (`-mountpoint`
    answers "no mountable file systems" for this image, so the default
    mount point is taken from the plist). Never while the child runs on it."""
    cmd = ["hdiutil", "attach", "-imagekey", "diskimage-class=CRawDiskImage", "-plist"]
    if readonly:
        cmd.append("-readonly")
    if not browse:
        cmd.append("-nobrowse")
    cmd.append(str(image))
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"hdiutil attach rc {r.returncode}: {r.stderr.decode(errors='replace').strip()}")
    d = plistlib.loads(r.stdout)
    dev = mnt = None
    for e in d.get("system-entities", []):
        if e.get("mount-point"):
            mnt = e["mount-point"]
        if e.get("content-hint") == "FDisk_partition_scheme":
            dev = e.get("dev-entry")
    if not mnt:
        for e in d.get("system-entities", []):
            if e.get("dev-entry"):
                subprocess.run(["hdiutil", "detach", e["dev-entry"]], capture_output=True)
                break
        raise RuntimeError("hdiutil attached the image but mounted no volume")
    return dev or mnt, mnt


def card_mounted_at(image, timeout=60):
    """(device, mount point) if macOS has this image attached (an eject the
    last server left behind), else None -- from `hdiutil info -plist`."""
    try:
        r = subprocess.run(["hdiutil", "info", "-plist"], capture_output=True, timeout=timeout)
        d = plistlib.loads(r.stdout) if r.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    want = str(pathlib.Path(image).resolve())
    for img in d.get("images", []):
        if str(img.get("image-path", "")) != want:
            continue
        dev = mnt = None
        for e in img.get("system-entities", []):
            if e.get("mount-point"):
                mnt = e["mount-point"]
            if e.get("content-hint") == "FDisk_partition_scheme":
                dev = e.get("dev-entry")
        return (dev or mnt, mnt)
    return None


def card_detach(what, timeout=120):
    """hdiutil detach (the device or the mount point); a second try with
    -force when a Finder window or a Quick Look still holds a file."""
    r = subprocess.run(["hdiutil", "detach", str(what)], capture_output=True, timeout=timeout)
    if r.returncode == 0:
        return "detached"
    err = r.stderr.decode(errors="replace").strip()
    r = subprocess.run(["hdiutil", "detach", "-force", str(what)], capture_output=True, timeout=timeout)
    if r.returncode == 0:
        return f"detached with -force ({err})"
    raise RuntimeError(f"hdiutil detach rc {r.returncode}: {r.stderr.decode(errors='replace').strip() or err}")


def card_clean(mnt):
    """Remove what macOS drops on a mounted FAT volume (.fseventsd,
    .Spotlight-V100, .Trashes, .DS_Store, ._AppleDouble files) before the
    unit sees the card again: its file browser lists every entry, and a
    root folder would show up as a set. Returns the paths removed."""
    gone = []
    root = pathlib.Path(mnt)
    for name in CARD_DROPPINGS:
        p = root / name
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p, ignore_errors=True); gone.append(str(p))
        elif p.exists() or p.is_symlink():
            try:
                p.unlink(); gone.append(str(p))
            except OSError:
                pass
    for p in root.rglob("._*"):
        if p.is_file():
            try:
                p.unlink(); gone.append(str(p))
            except OSError:
                pass
    for p in root.rglob(".DS_Store"):
        try:
            p.unlink(); gone.append(str(p))
        except OSError:
            pass
    return gone


def card_no_droppings(mnt):
    """Ask macOS not to index or log the mounted card: .metadata_never_index
    and .fseventsd/no_log at its root (both removed again by card_clean)."""
    root = pathlib.Path(mnt)
    try:
        (root / ".metadata_never_index").touch()
        (root / ".fseventsd").mkdir(exist_ok=True)
        (root / ".fseventsd" / "no_log").touch()
    except OSError:
        pass


def sidecar_path(card):
    return pathlib.Path(str(card) + ".json")


def sidecar_load(card):
    try:
        return json.loads(sidecar_path(card).read_text())
    except (OSError, ValueError):
        return {}


def sidecar_save(card, meta):
    p = sidecar_path(card)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(meta, indent=2) + "\n")
    tmp.replace(p)


def build_card(project, set_name, name, tree, pool):
    """The card image: the project dir (when given) plus EVERY pool file as
    AUDIO/<name>, staged under `tree` (wiped and remade) and sized to fit.
    Returns (image bytes, staged project name or None, staged AUDIO dir).
    Measured 12 Sep 2026: the OTLIVE fixture with its 37 files, 64 MB image,
    in about a second."""
    tree = pathlib.Path(tree)
    audio = pool.audio_specs()
    size_mb = max(64, 16 + pool.total_bytes() // 2**20)
    if project:
        card, staged = ec.stage_project(project, set_name, name, audio=audio, tree=str(tree), image_mb=size_mb)
    else:
        if tree.exists():
            shutil.rmtree(tree)
        (tree / set_name / "AUDIO").mkdir(parents=True)
        for spec in audio:
            f, rel = spec.split(":", 1)
            shutil.copy2(f, tree / set_name / rel)
        card, staged = ec.build_image(str(tree), size_mb=size_mb), None
    return card, staged, tree / set_name / "AUDIO"


class Panel:
    """Owns the emulator thread; everything Unicorn happens on it."""

    def __init__(self, image, card, pump_ms=25.0, project=None, internal_clock=True,
                 play_pump_ms=10.0, backend="port", port_bin=PORT_BIN, port_args=(),
                 card_file=None, backend_note="", pool=None, card_builder=None,
                 staged_audio=None, sound=False, takes_dir=None, card_persistent=False,
                 card_rw=False, card_meta=None):
        self.image = image
        # The persistent card (O19, 13 Sep 2026): card_file is the user's
        # own image, booted as it is with --card-rw (card_rw: the binary
        # knows the flag); card_meta is its sidecar (set, project,
        # removals), card_files the AUDIO listing read from the image
        # (refreshed while the child is stopped), card_removals the on-card
        # files marked for deletion at the next re-insert, card_ejected /
        # card_mount the eject state (mounted on the Mac, no child).
        self.card_persistent = bool(card_persistent)
        self.card_rw = bool(card_rw)
        self.card_meta = dict(card_meta or {})
        self.card_files = {}
        self.card_removals = set(self.card_meta.get("removals", []))
        self.card_ejected = False
        self.card_mount = None
        self.card_dev = None
        self.card_flushed_at = 0.0
        self.card_flush_note = None
        if self.card_persistent and card_file is not None:
            self.card_files = card_audio_listing(card_file, (project or ("", ""))[0])
        # Sound (12 Sep 2026): with `sound` the port child is spawned with
        # --dsp and its main output is drained here (see AudioRing above,
        # _audio_start, _drain_audio). sound_wanted is what the NEXT child
        # boots with (/audio/enable flips it and reboots); sound is what the
        # current one delivers; audio_on says its capture is running.
        self.sound_wanted = bool(sound)
        self.sound = False
        # O17 (12 Sep 2026): with sound on the child runs --dsp-rt (the DSP
        # cores under the JIT on worker threads, real time). rt_wanted is
        # what the NEXT sound-on child boots with; an rt child that cannot
        # start (the binary's `dsp-rt : cannot start` line, or an exit
        # before `ready`) turns it off and the child is respawned with the
        # lockstep --dsp (~0.2x while playing). sound_rt says what the
        # current child runs.
        self.rt_wanted = True
        self.sound_rt = False
        # 23 Sep 2026: manual [TRIG] trigs were silent while the sequencer
        # was stopped because frame mode only ran from PLAY to STOP. The
        # DSP frame interrupt runs the firmware's frame builder
        # (0x4000b2ee..), the ONLY consumer of the trig mailbox 0x46c80354
        # that a [TRIG] key posts (0x40005030 -> 0x4000515c); with frame
        # mode off the press's 0x1d sat in the mailbox until the release
        # overwrote it with the note-off 0x40, and no voice ever started
        # (measured through /peek: mailbox[4] = 0x40, voice struct idle,
        # exact digital silence; the same key with `frame on` from boot:
        # -11.9 dBFS). On the unit the interrupt is never off (main unmasks
        # INTC0 source 1 at boot), so with the cores (sound on) the port
        # keeps it on from boot: frame_always. `playing` is what PLAY..STOP
        # now means for the pump rate and the take. Without the cores
        # nothing is audible and frame mode stays the PLAY..STOP affair it
        # was.
        self.frame_always = False
        self.playing = False
        self.sound_note = SOUND_ON_NOTE if sound else SOUND_OFF_NOTE
        self.sound_busy = False           # an /audio/enable reboot is in progress
        self.audio_on = False             # the current child accepted `audio start main`
        self.audio_note = None            # what went wrong with the capture, if anything
        self.ring = AudioRing()
        self.audio_captured = 0           # frames drained from every child so far
        self.audio_dropped = 0            # frames the children overwrote unread (their counters, summed)
        self._dropped_base = 0            # audio_dropped when the current child started
        self._dropped_at = 0.0            # wall time of the last `audio status` poll (one per second)
        self.audio_peak = (0, 0)          # |peak| L/R of the last non-empty read
        self.drain = {"reads": 0, "frames": 0, "wall_ms": 0.0, "max_ms": 0.0}   # the drain's own cost
        self.takes_dir = pathlib.Path(takes_dir) if takes_dir else None
        self.take = None                  # TakeWriter while a take is open (PLAY .. STOP)
        self.takes = []                   # closed takes, oldest first, as /audio/status lists them
        self.take_lock = threading.Lock()
        self.take_seq = self._scan_takes()
        # The output device (13 Sep 2026, AudioOutput above): the stream the
        # drain feeds, if one is on; the capture mode the child runs (main =
        # 2 words a frame, all = 8, tracks = 24) and the words per frame the drain parses.
        self.output = None
        self.output_lock = threading.Lock()
        self.output_note = None           # why there is none / what the last attempt said
        self.audio_mode = "main"
        self.audio_words = 2
        self.audio_peak_cue = (0, 0)      # |peak| of the cue pair in the last 8-word read
        self.card = card                  # the FAT16 card image, bytes
        self.card_file = card_file        # ... and the port reads it from this file
        self.pool = pool                  # SamplePool the card's AUDIO was built from
        self.card_builder = card_builder  # () -> (card bytes, staged name, staged AUDIO dir): commit_card
        self.staged_audio = staged_audio  # the AUDIO dir inside the staging tree (what is on the card)
        self.card_manifest = pool.manifest() if pool is not None else {}   # the pool as the card has it
        self.card_busy = False            # a re-insert (rebuild + reboot) is in progress
        self.reinserts = 0
        self.pump_ms = pump_ms
        self.play_pump_ms = play_pump_ms   # the pump while frame mode is on (see _loop)
        self.project = project            # (set_name, project_name) to load at boot
        self.internal_clock = internal_clock
        self.backend = backend            # "port"
        self.backend_note = backend_note  # why the backend is what it is, when it is not the default
        self.port_bin = str(port_bin)
        self.port_args = list(port_args)  # extra flags for the child (e.g. --dsp)
        self.proc = None                  # PortProc while the port backend runs
        self.restarts = 0                 # port respawns (watchdog kills, crashes)
        self.meter = SpeedMeter()         # emulated ms per wall s, both backends
        self.rtmeter = RtMeter()          # x real time by the wall clock (the port, paced): /status "rt"
        self.pace = None                  # the child's last `pacestatus` (dict of strings), port only
        self.loaded = None                # load_project_live's tuple once done
        self.phase = "booting"            # booting -> loading project -> ready
        self.actions = queue.Queue()
        self.lock = threading.Lock()
        self.frame = b""          # latest PNG
        self.screen_txt = ""      # the same frame as 64 lines of '#'/'.' (/screen.txt)
        self.seq = 0
        self.fault = None
        self.ran_ms = 0.0
        self.booted = False
        self.led_bits = bytearray(64)
        self.led_ids = {}
        self.handlers = self._read_table(image)
        self.param_map = load_param_map()       # what the page encoders edit (param_map.json)
        self._new_link()
        threading.Thread(target=self._loop, daemon=True, name="emu").start()

    def _new_link(self):
        """A fresh decoder and stream positions: at start and after a port respawn."""
        try:
            from panel_link import PanelLink     # tools/panel/panel_link.py, when present
            self.link = PanelLink()
        except Exception:
            self.link = None
        self._link_pos = 0
        self._led_pos = 0
        self.row_state = None
        self.clock_note = None       # what _dismiss_clock found (in /status)
        # After a track key is released the idle pump slows down for a
        # moment so a second press from the page lands inside the
        # firmware's double-tap window (the sample slot list): see _loop.
        self.slow_until = 0.0

    @staticmethod
    def _read_table(image):
        data = pathlib.Path(image).read_bytes()
        off = KEY_TABLE - 0x40000000
        return [struct.unpack(">I", data[off + i * 4:][:4])[0] for i in range(KEY_COUNT)]

    link = None          # PanelLink: the decoded CPU->panel UART stream, when available
    _link_pos = 0

    def _lcd_rows(self, uc):
        """64 rows x 128 bools, top row first -- what the LCD shows.

        Preferred source: the panel UART stream decoded by
        tools/panel/panel_link.py (the firmware sends the LCD its data
        over UART@fc064000 in 0x10 <chunk> <8 bytes> blocks and scrolls
        with its own commands, so the stream is the ground truth). Fallback:
        the RAM framebuffer at FB, whose page ORDER on screen is not fixed
        (renders come out with lines rotated when the firmware scrolls --
        the 11 Sep 2026 "sample list wrapped" report)."""
        if self._feed_link():
            try:
                return self.link.lcd_rows()
            except Exception as e:      # a decoder fault must not blank the panel
                self.fault = f"panel_link: {type(e).__name__}: {e}"
        buf = bytes(uc.mem_read(FB, 1024))
        rows = []
        for y in range(64):
            yy = 63 - y
            page, bit = yy >> 3, 7 - (yy & 7)
            rows.append([(buf[x * 8 + page] >> bit) & 1 for x in range(128)])
        return rows

    def _feed_link(self):
        """Hand the decoder the panel UART bytes sent since the last call.
        False when there is no decoder (the RAM framebuffer is the source)."""
        if self.link is None or not hasattr(self, "rt"):
            return False
        tx = self.rt.uart64.tx
        if len(tx) > self._link_pos:
            self.link.feed(bytes(tx[self._link_pos:]))
            self._link_pos = len(tx)
        return True

    def _snapshot(self, uc):
        # Render only when an LCD block landed since the last render
        # (PanelLink.dirty): the pump calls this every 25 ms of firmware and
        # a render is 0.7 ms (lcd_rows 0.30 + PNG 0.40, measured 12 Sep
        # 2026) -- at idle it was the loop's only work. The RAM fallback
        # has no such flag and renders every call, as before.
        if self._feed_link() and self.frame and not self.link.dirty:
            return
        # the MKII display: white pixels on black (the MKI's
        # LCD, dark on pale, was 0x1a on 0xc9 in grey)
        on, off = LCD_ON, LCD_OFF
        lcd = self._lcd_rows(uc)
        rows = [b"".join(on if px else off for px in row) for row in lcd]
        png = _png_rgb(128, 64, rows)
        if self.link is not None:
            self.link.dirty = False
        with self.lock:
            if png != self.frame:
                self.frame = png
                self.screen_txt = "\n".join("".join("#" if px else "." for px in row) for row in lcd) + "\n"
                self.seq += 1

    BOOT_TIMEOUT = 900.0     # wall seconds the port may take to print `ready` (boot + load)

    def _uc(self):
        """The memory the RAM-framebuffer fallback reads: the port's peek."""
        return self.rt.uc

    def _dismiss_clock(self, rt):
        # Every boot opens SET DATE/TIME (the "last set" record lives in
        # RAM at 0x80000080 and is zero on a fresh boot). YES (matrix
        # 0x26 bit 1) stores the clock and closes it (measured 11 Sep
        # 2026); on the bare main screen YES would instead open the
        # ARM ALL popup, so press it exactly once, here, while the
        # dialog is certainly up. Same under the port (its DSPI has no
        # RTC model: the dialog shows 2000-00-00, and YES still closes it).
        self.phase = "closing the clock dialog"
        # Wait for the dialog itself: on an empty card (no --project) it
        # came up later than 400 ms after `ready` and a blind YES landed
        # on the main screen instead (ARM ALL, then the dialog on top of
        # it; 12 Sep 2026). Bounded: a firmware that never shows it must
        # not be sent a stray YES.
        uc = self._uc()
        for _ in range(60):                      # up to 6 s of firmware
            if popup_geometry(uc) == CLOCK_GEOMETRY:
                break
            rt.run(ms=100)
        else:
            self.clock_note = "clock dialog never appeared (no YES sent)"
            self._poll(rt)
            self._snapshot(uc)
            return
        rt.uart64.rx.extend([0x26, 0x02]); rt.run(ms=60)
        rt.uart64.rx.extend([0x26, 0x00]); rt.run(ms=300)
        for _ in range(10):                      # it closes within a few frames
            if popup_geometry(uc) != CLOCK_GEOMETRY:
                break
            rt.run(ms=100)
        g = popup_geometry(uc)
        self.clock_note = ("clock dialog closed" if g is None
                           else f"popup still open after YES: {tuple(hex(v) for v in g)}")
        self._poll(rt)
        self._snapshot(uc)

    def _port_argv(self):
        argv = [self.port_bin]
        if self.port_bin.endswith(".py"):
            argv = [sys.executable, self.port_bin]        # the fake, or any Python stand-in
        argv += ["--image", str(self.image), "--card", str(self.card_file), "--interactive"]
        if self.card_rw:
            argv.append("--card-rw")        # O19: the file is the card (write-back)
        if self.project:
            set_name, name = self.project
            # The port loads the project in its own boot (--mount posts the
            # card mount, loadProjectLive does the LOAD PROJECT; O7), so no
            # load_project_live here. --internal-clock is the CLI's own flag
            # for the CLOCK RECEIVE clear; internal_clock() below does the
            # same byte through poke in case the child only applies it with
            # --sequencer (main.cpp, 12 Sep 2026).
            argv += ["--mount", "--set", set_name, "--project", name]
            if self.internal_clock:
                argv.append("--internal-clock")
        argv += self.port_args
        if self.sound_wanted and "--dsp" not in argv and "--dsp-rt" not in argv:
            # the DSP cores: --dsp-rt = real time (O17); --dsp = the lockstep
            # interpreter, ~0.2x while playing (the fallback, and what an
            # explicit --port-arg=--dsp asks for)
            argv.append("--dsp-rt" if self.rt_wanted else "--dsp")
        return argv

    def _boot_port(self, phase=None):
        """Spawn the child, wait for `ready`, close the clock dialog. `phase`
        overrides the boot text (the card re-insert keeps its own)."""
        self.phase = phase or ("booting the port" + (" (boot + project load, ~1 min)" if self.project else ""))
        log = pathlib.Path(str(self.card_file)).with_suffix(".port.log") if self.card_file else None
        proc = PortProc(self._port_argv(), log_path=log)
        self.proc = proc
        try:
            try:
                proc.wait_ready(self.BOOT_TIMEOUT)
            except PortDied as e:
                if not (self.sound_wanted and self.rt_wanted and "--dsp-rt" in proc.argv):
                    raise
                # O17: the real-time child did not come up (a binary without
                # --dsp-rt, a host whose DSP memory is not MMU-backed, a boot
                # that faults): once more with the lockstep cores -- sound at
                # ~0.2x -- and /status says why (sound_note, backend_note).
                self.rt_wanted = False
                self.sound_rt = False
                self.backend_note = ((self.backend_note + "; ") if self.backend_note else "") + \
                    f"the --dsp-rt child did not boot ({e}); respawned with the lockstep --dsp"
                print(f"panel: {self.backend_note}")
                proc.kill()
                proc = PortProc(self._port_argv(), log_path=log)
                self.proc = proc
                proc.wait_ready(self.BOOT_TIMEOUT)
            self.sound_rt = "--dsp-rt" in proc.argv
            rt = PortRt(proc, meter=self.meter)
            self.rt = rt
            self.booted = True
            self._audio_start(rt)       # the ring lives in the child: start it on every fresh one
            if self.project:
                rep = "\n".join(proc.log)
                posted = re.search(r"LOAD PROJECT posted: (\w+)", rep)
                banks = re.search(r"saved_bank: (-?\d+), final bank: (\d+)", rep)
                ready = re.search(r"card ready: (0x[0-9a-f]+)", rep)
                self.loaded = {"mounted": ready.group(1) if ready else None,
                               "posted": (posted.group(1) == "yes") if posted else None,
                               "saved_bank": int(banks.group(1)) if banks else None,
                               "final_bank": int(banks.group(2)) if banks else None,
                               "elapsed_ms": rt.sample / SAMPLE_HZ * 1000.0,
                               "port_report": list(proc.log)[-12:]}
                if self.internal_clock:
                    rt.internal_clock()
            self._poll(rt)
            self._snapshot(rt.uc)
            self._dismiss_clock(rt)
            rt.run(ms=300)
            # A fresh child is stopped. With the cores, frame mode from here
            # on (see frame_always in __init__): the unit's frame interrupt
            # is always live, and it is what turns a manual [TRIG] into a
            # voice while the sequencer is stopped.
            self.playing = False
            self.frame_always = bool(self.sound_wanted)
            if self.frame_always and not rt.frame:
                rt.frame = True
                rt.next_frame = rt.sample + FRAME_PERIOD
            self._poll(rt)
            self._snapshot(rt.uc)
        except BaseException:
            proc.kill()
            raise

    def _boot(self):
        try:
            self._boot_port()
        except PortDied as e:
            if self.booted:
                raise
            if self.sound_wanted:
                # The --dsp child did not come up (a binary built without
                # the cores, a DSP boot that faults): once more without
                # them -- the panel works, the sound does not, and
                # /status says why (backend_note, sound_note).
                self.sound_wanted = False
                self.audio_note = self.sound_note = f"sound off: the --dsp child did not boot ({e})"
                self.backend_note = ((self.backend_note + "; ") if self.backend_note else "") + \
                    f"the --dsp child did not boot ({e}); booted without the DSP cores (no sound)"
                print(f"panel: {self.backend_note}")
                self._boot_port()
            else:
                raise
        self.phase = "ready"

    def _respawn(self, why):
        """The port child is gone (watchdog kill, crash, silence): boot a
        fresh one. Emulated state starts over -- boot, project load, the
        clock dialog -- and the decoder with it; clicks queued meanwhile
        run against the new child once it is ready."""
        self.restarts += 1
        self.fault = f"port: {why}; respawned ({self.restarts})"
        return self._reboot_port(f"restarting the port ({why})")

    def _reboot_port(self, phase):
        """Kill the child and boot a fresh one on self.card_file (the
        respawn above and the card re-insert share this): a new decoder,
        blank LEDs and screen, three boot attempts, `phase` shown until the
        clock dialog is closed; /status "booted" is false meanwhile (it
        read true through a re-insert with the screen blank, 12 Sep 2026).
        True when the port is up again."""
        self._stop_child()
        for attempt in range(3):
            try:
                self._boot_port(phase)
                self.phase = "ready"
                return True
            except PortDied as e:
                self.fault = f"port: respawn {attempt + 1} failed: {e}"
                time.sleep(2.0)
        self.phase = "failed"
        return False

    REINSERT_PHASE = "re-inserting the card (reboot, ~40 s)"
    EJECT_PHASE = "ejecting the card (flush, stop)"
    INSERT_PHASE = "inserting the card (boot, ~40 s)"
    CARD_FLUSH_S = 3.0          # O19: `card flush` (fsync) at least this often while idle, and after every action batch

    def _stop_child(self):
        """The child gone and the panel blank, before a boot on the same
        card or a mount of it: with write-back on, `card flush` then
        `quit` (the child fsyncs before its `ok`), else the kill the
        respawn always did. Every caller re-boots or mounts afterwards."""
        self._close_take(None)          # a take open across a reboot ends here (the child's ring is gone)
        self.audio_on = False
        proc, self.proc = self.proc, None
        if proc is not None:
            if self.card_rw and proc.alive():
                try:
                    proc.command("card flush", "card", timeout=10.0)
                except (PortDied, PortError):
                    pass
                proc.quit()             # `quit` -> ok (flushed), then the kill
            else:
                proc.kill()
        self.booted = False
        self._new_link()
        self.led_bits = bytearray(64); self.led_ids = {}
        with self.lock:
            self.frame = b""; self.screen_txt = ""

    def _card_flush(self, rt, force=False):
        """O19: `card flush` on the child (an fsync of the image file; every
        written sector is already in the file) after an action batch and
        every CARD_FLUSH_S idle -- and the firmware's own SET / PROJECT
        names (0x100f8480 / 0x100f8378) into the sidecar when they changed
        (PROJECT > CHANGE on the unit), so the next boot loads what the
        user was in. Nothing without --card-rw."""
        if not self.card_rw or rt is None or self.card_ejected:
            return
        now = time.perf_counter()
        if not force and now - self.card_flushed_at < self.CARD_FLUSH_S:
            return
        self.card_flushed_at = now
        try:
            rep = rt.proc.command("card flush", "card", timeout=10.0)
            self.card_flush_note = rep[5:].strip() or None
            if self.card_persistent and self.booted:
                names = []
                for addr in (ec.FW_SET_NAME, ec.FW_PROJECT_NAME):
                    raw = bytes(rt.uc.mem_read(addr, 0x40))
                    # the set is kept as an absolute path ("/OTLIVE", emu_card.set_names)
                    names.append(raw.split(b"\0", 1)[0].decode("ascii", "replace").lstrip("/"))
                if all(names) and tuple(names) != tuple(self.project or ("", "")):
                    print(f"panel: the unit is in {names[0]}/{names[1]} now (was {self.project}); sidecar updated")
                    self.project = (names[0], names[1])
                    self.card_files = {}       # another set: re-listed at the next stop
                    self._save_sidecar()
        except PortError as e:
            self.card_flush_note = f"card flush refused: {e}"
        # PortDied propagates: the loop respawns

    def _save_sidecar(self):
        if not self.card_persistent or self.card_file is None:
            return
        meta = dict(self.card_meta)
        if self.project:
            meta["set"], meta["project"] = self.project
        meta["removals"] = sorted(self.card_removals)
        meta["pool"] = str(self.pool.path) if self.pool is not None else None
        meta["saved"] = datetime.datetime.now().isoformat(timespec="seconds")
        self.card_meta = meta
        try:
            sidecar_save(self.card_file, meta)
        except OSError as e:
            print(f"panel: sidecar not written: {e}")

    def refresh_card_files(self):
        """Re-read the card's AUDIO listing from the image (the child stopped
        or idle; the reader never mounts)."""
        if self.card_persistent and self.card_file is not None and self.project:
            self.card_files = card_audio_listing(self.card_file, self.project[0])
        return self.card_files

    def card_name_on(self, name):
        """The on-card file called `name`, case-insensitively, or None."""
        low = name.lower()
        return next((n for n in self.card_files if n.lower() == low), None)

    def pending(self):
        """(added, removed): pool files not on the card as they are, and card
        files no longer in the pool -- what the next commit changes. On the
        persistent card the pool IS the pending list (a file moves onto the
        card at the re-insert) and the removals are the marked names."""
        if self.pool is None:
            return [], []
        if self.card_persistent:
            return self.pool.names(), sorted(self.card_removals)
        now = self.pool.manifest()
        added = [n for n, st in now.items() if self.card_manifest.get(n) != st]
        removed = [n for n in self.card_manifest if n not in now]
        return added, removed

    def samples_files(self):
        """/samples "files": on the persistent card the image's AUDIO listing
        (on_card true; a name the pool also holds is shown from the pool,
        which replaces it at the re-insert) plus the pool's pending files;
        otherwise the pool as before."""
        if not self.card_persistent:
            return self.pool.files()
        pool = self.pool.files()
        low = {f["name"].lower() for f in pool}
        out = [{"name": n, "bytes": f["bytes"], "format": f["format"], "on_card": True,
                "removing": n in self.card_removals}
               for n, f in sorted(self.card_files.items(), key=lambda kv: kv[0].lower()) if n.lower() not in low]
        for f in pool:
            out.append({**f, "on_card": False, "removing": False})
        return out

    def remove_sample(self, name):
        """/samples/remove: a pool file is taken out; on the persistent card
        an on-card file is MARKED for deletion at the next re-insert (and a
        marked one un-marked by a second call)."""
        if self.pool.find(name) is not None:
            return self.pool.remove(name)
        if self.card_persistent:
            on = self.card_name_on(name)
            if on is not None:
                if on in self.card_removals:
                    self.card_removals.discard(on)
                    self._save_sidecar()
                    return {"ok": True, "name": on, "note": "kept: the removal mark is off again"}
                self.card_removals.add(on)
                self._save_sidecar()
                return {"ok": True, "name": on, "note": "on the card: removed at the next re-insert "
                                                        "(/samples/remove of the same name un-marks it)"}
        return {"ok": False, "error": f"{name}: not in the pool" + (" or on the card" if self.card_persistent else "")}

    def _commit_persistent(self):
        """The re-insert on the persistent card (on the emu thread): flush
        and stop the child, mount the image (nobrowse), copy the pool into
        <SET>/AUDIO, delete the marked files, clean macOS's droppings,
        detach, re-list, boot the child on the same file. A mount that
        fails leaves the card as it was (the pool keeps its files) and the
        unit is still rebooted."""
        added, removed = self.pending()
        set_name = self.project[0] if self.project else "OCTABAM"
        self._stop_child()
        note = None
        if added or removed:
            dev, mnt = card_attach(self.card_file, readonly=False, browse=False)
            copied, deleted = [], []
            try:
                card_no_droppings(mnt)
                audio = pathlib.Path(mnt) / set_name / "AUDIO"
                audio.mkdir(parents=True, exist_ok=True)
                have = {q.name.lower(): q for q in audio.iterdir()}
                for n in removed:
                    q = have.get(n.lower())
                    if q is not None and q.is_file():
                        q.unlink(); deleted.append(n)
                for n in added:
                    q = have.get(n.lower())
                    if q is not None and q.name != n and q.is_file():
                        q.unlink()          # the same name in another case: one entry on the card
                    shutil.copyfile(self.pool.path / n, audio / n)
                    copied.append(n)
                card_clean(mnt)
            finally:
                card_detach(dev)
            for n in copied:
                try:
                    (self.pool.path / n).unlink()   # on the card now
                except OSError:
                    pass
            self.card_removals.clear()
            note = f"{len(copied)} copied, {len(deleted)} deleted"
        self.refresh_card_files()
        self._save_sidecar()
        self.reinserts += 1
        return note

    def commit_card(self):
        """Re-insert the card: rebuild the image from the pool (every file)
        and reboot the unit on it -- the emulator has no hot-plug, and the
        firmware scans AUDIO/ at mount. Answers at once (ok, phase); the
        work runs as one action on the emu thread, /status "phase" shows
        REINSERT_PHASE, then the clock dialog, then ready. Under the port
        it is the watchdog's respawn path on the new image (_reboot_port).
        Adds, removes and a second commit are refused meanwhile
        (card_busy)."""
        if self.pool is None or (self.card_builder is None and not self.card_persistent):
            return False, "no sample pool"
        if self.card_busy:
            return False, "a re-insert is already in progress"
        if self.sound_busy:
            return False, "a sound switch (reboot) is in progress"
        if self.card_ejected:
            return False, "the card is ejected (mounted on the Mac): insert it first"
        if not self.booted:
            return False, f"the unit is still booting ({self.phase})"
        self.card_busy = True
        self.phase = self.REINSERT_PHASE

        def act():
            # Not an action the watchdog may time: the fresh child boots
            # for ~40 s and ACTION_LIMIT is 20 (it would kill it mid-boot).
            self.busy_since = None
            t0 = time.perf_counter()
            if self.card_persistent:
                # O19: no rebuild -- the pool's files are copied onto the
                # user's card through a mount while the child is stopped
                try:
                    note = self._commit_persistent()
                    self._reboot_port(self.REINSERT_PHASE)
                    self.fault = None
                    print(f"panel: card re-inserted ({note or 'no change'}; {len(self.card_files)} files in AUDIO)"
                          f" in {time.perf_counter() - t0:.1f} s")
                except Exception as e:
                    self.fault = f"card re-insert: {type(e).__name__}: {e}"
                    print(f"panel: {self.fault}")
                    if self.proc is None or not self.proc.alive():
                        self._reboot_port(self.REINSERT_PHASE)   # the card as it was
                finally:
                    self.card_busy = False
                return
            try:
                card, staged, audio_dir = self.card_builder()
                self.card, self.staged_audio = card, audio_dir
                if staged is not None and self.project:
                    self.project = (self.project[0], staged)
                self.card_manifest = self.pool.manifest()
                self.reinserts += 1
                self.card_file.write_bytes(card)
                self._reboot_port(self.REINSERT_PHASE)
                self.fault = None
                print(f"panel: card re-inserted with {len(self.card_manifest)} files in"
                      f" {time.perf_counter() - t0:.1f} s")
            except Exception as e:
                # a build that failed leaves the old child running; a boot
                # that failed has said "failed" itself (_reboot_port)
                self.fault = f"card re-insert: {type(e).__name__}: {e}"
                alive = self.proc is not None and self.proc.alive()
                self.phase = "ready" if alive else "failed"
            finally:
                self.card_busy = False
        self.actions.put(act)
        return True, self.REINSERT_PHASE

    def eject_card(self, open_finder=True):
        """/card/eject (O19): flush + stop the child, mount the image on the
        Mac (browsable, so Finder shows it; `open` it too unless told not
        to) and stay that way -- no child, every action refused -- until
        /card/insert. The user copies samples, projects or whole sets in
        and out as with a CF card in a reader. Persistent card only."""
        if not self.card_persistent:
            return False, "no persistent card (--card) to eject"
        if self.card_ejected:
            return False, f"the card is already ejected (mounted at {self.card_mount})"
        if self.card_busy or self.sound_busy:
            return False, f"the unit is busy ({self.phase})"
        if not self.booted:
            return False, f"the unit is still booting ({self.phase})"
        self.card_busy = True
        self.phase = self.EJECT_PHASE

        def act():
            self.busy_since = None
            try:
                self._stop_child()
                dev, mnt = card_attach(self.card_file, readonly=False, browse=True)
                card_no_droppings(mnt)
                self.card_ejected, self.card_mount, self.card_dev = True, mnt, dev
                self.phase = f"card ejected: mounted at {mnt} -- INSERT CARD to boot"
                self.fault = None
                print(f"panel: card ejected, mounted at {mnt} ({dev})")
                if open_finder:
                    subprocess.Popen(["open", mnt])
            except Exception as e:
                self.fault = f"card eject: {type(e).__name__}: {e}"
                print(f"panel: {self.fault}")
                self.card_ejected, self.card_mount, self.card_dev = False, None, None
                self._reboot_port("booting again (the eject failed)")
            finally:
                self.card_busy = False
        self.actions.put(act)
        return True, self.EJECT_PHASE

    def insert_card(self):
        """/card/insert (O19): clean the volume, detach it, re-list the
        card and boot the child on it. A detach that fails (a file open
        in Finder) leaves the card ejected and says why in /status fault."""
        if not self.card_ejected:
            return False, "the card is not ejected"
        if self.card_busy:
            return False, f"the unit is busy ({self.phase})"
        self.card_busy = True
        self.phase = self.INSERT_PHASE

        def act():
            self.busy_since = None
            t0 = time.perf_counter()
            try:
                gone = card_clean(self.card_mount)
                how = card_detach(self.card_dev or self.card_mount)
                self.card_ejected, self.card_mount, self.card_dev = False, None, None
                self.refresh_card_files()
                self._save_sidecar()
                print(f"panel: card inserted ({how}; {len(gone)} macOS files removed; {len(self.card_files)} files in AUDIO)")
                self._reboot_port(self.INSERT_PHASE)
                self.fault = None
                print(f"panel: booted on the inserted card in {time.perf_counter() - t0:.1f} s")
            except Exception as e:
                self.fault = f"card insert: {type(e).__name__}: {e}"
                print(f"panel: {self.fault}")
                if self.card_ejected:
                    self.phase = f"card ejected: mounted at {self.card_mount} -- INSERT CARD to boot ({e})"
            finally:
                self.card_busy = False
        self.actions.put(act)
        return True, self.INSERT_PHASE

    def _poll(self, rt):
        """Drain the child's UART A bytes into rt.uart64.tx (one round trip)."""
        rt.poll_tx()

    PACE_POLL_S = 0.02       # the paced loop's cadence (tx, audio drain, pacestatus, render) when no action is queued
    PACE_RATE = 1.0          # `pace on <rate>`: 1.0 = the unit's own clock

    def _loop(self):
        try:
            self._boot()
        except Exception as e:  # boot is all-or-nothing
            self.fault = f"boot: {type(e).__name__}: {e}"
            self.phase = "failed"
            return
        threading.Thread(target=self._watchdog, daemon=True, name="watchdog").start()
        try:
            self.rt.pace(True, self.PACE_RATE)
        except PortError as e:
            # an older child (--port-bin) without `pace`: the pump below, as before
            self.backend_note = ((self.backend_note + "; ") if self.backend_note else "") + \
                f"the child has no pacer ({e}); pumping 25 ms runs instead"
            print(f"panel: {self.backend_note}")
        else:
            return self._loop_paced()
        # A child without `pace`: the pump below (O15f).
        while True:
            try:
                while True:
                    try:
                        act = self.actions.get_nowait()
                    except queue.Empty:
                        break
                    self.busy_since = time.perf_counter()
                    try:
                        act()
                        self._drain_audio(self.rt)   # what the action's own runs rendered
                    finally:
                        self.busy_since = None
                rt = self.rt        # after the actions: a card re-insert replaces it
                t = time.perf_counter()
                self.busy_since = t
                # Shorter pumps while the sequencer runs: in frame mode 25 ms
                # of firmware is ~0.46 s wall (54 emulated ms per wall s,
                # measured 12 Sep 2026) and a click first waits for the pump
                # in progress, then runs its own 50 ms. 10 ms pumps cut the
                # wait to ~0.18 s; the per-pump work (snapshot 0.7 ms, LED
                # parse) stays under 1 %, and where run() stops does not
                # move any firmware event, so the emulated timing is the
                # same. The emulation itself is the cost: one emulated
                # second is 1.9M emu_start bursts, 2.9M Intc.pending calls,
                # 515k EMAC + 564k ISA-C shims (cProfile, 12 Sep 2026) --
                # all in tools/emu, nothing of it in this file. Under the
                # port the pump stays 25 ms (its own play_pump_ms).
                # The double-tap window: a track key pressed twice opens its
                # sample slot list, and the firmware measures the gap in ITS
                # time. Two page clicks are two actions with idle pumps
                # between them (25 ms each, ~30 ms wall), so a double-click
                # 0.3 s of wall apart reached the firmware ~350 emulated ms
                # press to press and missed the window (200 ms lands, 375
                # does not; measured 12 Sep 2026). For SLOW_WALL_S after a
                # track key goes up the pump is SLOW_PUMP_MS: the same
                # double-click is then ~170 emulated ms press to press.
                # Nothing else changes -- the firmware still runs, just less
                # of it per wall second, and only for that moment.
                # (frame_always: the frame interrupt runs while stopped too,
                # so PLAY..STOP is `playing`, not `rt.frame`.)
                if self.playing or (rt.frame and not self.frame_always):
                    pump = min(self.pump_ms, self.play_pump_ms)
                elif t < self.slow_until:
                    pump = min(self.pump_ms, self.SLOW_PUMP_MS)
                else:
                    pump = self.pump_ms
                rt.run(ms=pump)
                self._poll(rt)
                burst = time.perf_counter() - t    # the run + tx alone decide the idle sleep below,
                self._drain_audio(rt)              # so the drain (one more round trip, /audio/status
                self.busy_since = None             # "drain" measures it) changes no pump cadence
                self.ran_ms = rt.sample / SAMPLE_HZ * 1000.0
                if isinstance(rt, PortRt) and rt.stop_reason not in ("time", "gate", None, "?") \
                        and not (self.fault or "").startswith("port: run stopped"):
                    self.fault = f"port: run stopped: {rt.stop_reason}"
                self._snapshot(self._uc())
                self._parse_leds(rt)
                # idle bursts return instantly; don't spin the host
                if burst < 0.01:
                    time.sleep(0.03)
            except PortDied as e:
                self.busy_since = None
                if not self._respawn(str(e)):
                    return
            except Exception as e:
                self.busy_since = None
                self.fault = f"{type(e).__name__}: {e}"
                time.sleep(0.5)

    def _loop_paced(self):
        """The port backend since O15f (12 Sep 2026): the CHILD paces
        itself. `pace on` makes it free-running -- while its stdin is
        empty it advances emulated time in 10 ms slices so that it tracks
        its own wall clock (sleeping inside poll() on stdin when ahead, so
        a command wakes it at once; flat out when the core is slower than
        real time; re-anchoring past 250 ms of lag) -- and this thread
        only serves the actions and, every PACE_POLL_S when none is
        queued, drains tx and audio, reads `pacestatus` and renders. No
        `run` from the loop at all. What that replaces: the 25 ms pump +
        30 ms sleep ran idle at 0.69x without the cores and 1.02x in
        bursts of 0.85-2.0x with them (the firmware's clocks neither at
        hardware rate nor steady), and the SLOW_PUMP hack that compressed
        0.45 s of wall into 191 emulated ms after a track key so a page
        double-click could land. Now the double-tap window is a wall-time
        property: two page clicks 0.15 s apart open the slot list, 0.30 s
        apart miss (doubletap.py, 12 Sep 2026), as on the unit. Actions
        still run their own `run`s (a key's 50 ms); those advance on top
        of the pacer, which then waits for the wall clock, so the
        emulated timing around a click is the same as before and the wall
        timing is the unit's. Measured: idle 1.000x +- 0.01 with and
        without --dsp at ~8 % / ~40 % of a core (the DSP cores do not
        idle-skip); playing flat out until the core is >= 1.0x (no --dsp:
        1.00x on this Mac since O15a-e; --dsp: ~0.15x)."""
        armed = None            # the PortRt whose pacer is on
        prev = None             # (ms, busy) of the previous pacestatus, for the speed meter
        while True:
            try:
                # Actions first: a blocking get, so a queued click is served
                # the moment it arrives (idle key round trip ~1 ms) instead of
                # after a sleep; the timeout is the render/drain cadence.
                try:
                    act = self.actions.get(timeout=self.PACE_POLL_S)
                except queue.Empty:
                    act = None
                ran = False
                while act is not None:
                    self.busy_since = time.perf_counter()
                    try:
                        act()
                        ran = True
                        if self.rt is not None and not self.card_ejected:
                            self._drain_audio(self.rt)   # what the action's own runs rendered
                    finally:
                        self.busy_since = None
                    try:
                        act = self.actions.get_nowait()
                    except queue.Empty:
                        act = None
                if self.card_ejected or self.rt is None:
                    continue            # O19: the card is on the Mac; no child to serve
                rt = self.rt        # after the actions: a respawn / re-insert / sound switch replaces it
                if ran:
                    self._card_flush(rt, force=True)    # O19: the batch's writes on disk
                if rt is not armed:
                    if not rt.paced:
                        rt.pace(True, self.PACE_RATE)   # a fresh child: arm its pacer
                    armed = rt
                    prev = None
                    self.rtmeter.reset()
                t = time.perf_counter()
                self.busy_since = t
                self._poll(rt)
                self._drain_audio(rt)
                st = rt.pacestatus()
                self.busy_since = None
                self.pace = st
                self.ran_ms = rt.sample / SAMPLE_HZ * 1000.0
                self.rtmeter.add(self.ran_ms)
                busy = float(st.get("busy", 0.0))
                if prev is not None and busy > prev[1]:
                    # `speed` keeps its meaning (emulated ms per wall s INSIDE
                    # the emulation: idle slices are instant, so it reads high
                    # idle); `rt` is the wall-clock figure
                    self.meter.add(self.ran_ms - prev[0], busy - prev[1])
                prev = (self.ran_ms, busy)
                if st.get("on") != "1" and st.get("stop") not in ("time", "gate") \
                        and not (self.fault or "").startswith("port: run stopped"):
                    # the machine stopped inside a slice (fault/illegal): the
                    # pacer ended itself; say so once, as the pump did
                    self.fault = f"port: run stopped: {st.get('stop')}"
                self._snapshot(self._uc())
                self._parse_leds(rt)
                self._card_flush(rt)
            except PortDied as e:
                self.busy_since = None
                if self.card_ejected:
                    continue            # a stale action hit the stopped child: nothing to respawn on
                if not self._respawn(str(e)):
                    return
            except Exception as e:
                self.busy_since = None
                self.fault = f"{type(e).__name__}: {e}"
                time.sleep(0.5)

    def knob(self, row, delta):
        """An encoder turn: matrix rows 0x30-0x36 are the seven encoders and
        the second byte is a SIGNED detent delta (measured 10 Sep 2026: row
        0x30 with +2 moved the MIXER's MAIN field +2, with +16 clamped at
        +15). No release event -- a turn is an event, not a state."""
        if not (0x30 <= row < 0x37):
            return False, "encoder rows are 0x30-0x36"
        delta = max(-127, min(127, int(delta)))
        def act(rt):
            on_setup = row < 0x36 and setup_window_open(rt.uc)
            if on_setup and abs(delta) > 7:
                # The SETUP-page enum editor accumulates and, past about +-9
                # per report, steps the wrong way (PMTR 15 -> 6 on +12,
                # measured 12 Sep 2026); a big coalesced wheel turn from the
                # page would otherwise scramble the field. Deliver it as
                # +-7 reports instead.
                left = delta
                while left:
                    part = max(-7, min(7, left))
                    rt.uart64.rx.extend([row, part & 0xff])
                    rt.run(ms=30)
                    left -= part
            else:
                rt.uart64.rx.extend([row, delta & 0xff])
                rt.run(ms=30)
            note = ""
            if on_setup:
                # A-F on a SETUP page (AMP/LFO/PLAYBACK/FX SETUP, the second
                # press of a page key): the Part byte changes and the box is
                # drawn into RAM, but the firmware sends no LCD block for the
                # edit under the emulator (none within 3 s idle; a LEVEL +1
                # or a held FUNC flushed the box once each after a long run
                # of edits, never reliably) -- the page redraws when it is
                # closed (page key) and reopened (page key twice: the press
                # after a close only re-selects the page). KEYMAP.md, 12 Sep
                # 2026. Single detents only accumulate there (3 per step
                # clockwise, 4 back); +2..+7 is about one step. Page 1
                # flushes every report and gets no note -- also under the
                # ARM/DISARM ALL popup a YES/NO leaves on it (that popup is
                # drawn from the same record with its own geometry).
                note = (" (SETUP page: the value changed; the box redraws after the page key"
                        " closes the page and, pressed twice more, reopens it)")
            return f"row {row:#04x} delta {delta:+d}{note}"
        return self.do(act, timeout=120)

    # -- 13 Sep 2026: what an encoder edits on the current page, and the reset --
    def page_param(self, rt, row):
        """Resolve encoder `row` (0x30-0x36) against the firmware's state:
        the current track, the page kind, the machine / effect of the
        track, the page descriptor (param_map.json, measured 13 Sep 2026)
        -> (info dict, None) or (None, why not). Nothing is sent."""
        pm = self.param_map
        if not pm:
            return None, "param_map.json missing"
        uc = rt.uc
        rd = lambda a, n: bytes(uc.mem_read(a, n))                       # noqa: E731
        u8 = lambda a: rd(a, 1)[0]                                       # noqa: E731
        u32 = lambda a: int.from_bytes(rd(a, 4), "big")                  # noqa: E731
        s32 = lambda a: int.from_bytes(rd(a, 4), "big", signed=True)     # noqa: E731
        ram, lay = pm["ram"], pm["layout"]
        if u32(ram["midi_mode"]):
            return None, "MIDI mode: the MIDI-track pages are not mapped"
        g = popup_geometry(uc)
        if g is not None and g not in (ARM_ALL_GEOMETRY, DISARM_ALL_GEOMETRY):
            what = "a SETUP page" if g == SETUP_GEOMETRY else f"a window ({', '.join(hex(v) for v in g)})"
            return None, f"{what} is open: the encoders edit its boxes, not a page parameter -- nothing sent"
        track = u8(ram["cur_track_ui"])
        base = u32(ram["part_ptr"]) + u8(ram["part_index"]) * lay["part_stride"]
        if row == 0x36:
            lv = pm["level"]
            addr = lv["addr"] + lv["track_stride"] * track
            return {"row": row, "knob": "LEVEL", "name": "LEV", "page": "LEVEL", "track": track + 1,
                    "addr": addr, "min": lv["min"], "count": lv["count"], "default": lv["default"],
                    "cur": u8(addr)}, None
        kind = u32(ram["page_kind"])
        names = {0: "PLAYBACK", 1: "LFO", 2: "AMP", 3: "FX1", 4: "FX2"}
        if kind not in names:
            return None, f"page kind {kind} is not one of the five parameter pages"
        if track == 7 and u8(ram["master_track"]):
            return None, "the master track's page is not mapped"
        slot = row - 0x30
        if kind == 0:
            mt = u8(base + lay["machine_type"] + track)
            desc = u32(lay["pb_descriptors"] + 4 * mt)
            addr = base + lay["pb_base"] + track * lay["pb_track_stride"] + mt * lay["pb_machine_stride"] + slot
            page = f"PLAYBACK ({['STATIC', 'FLEX', 'THRU', 'NEIGHBOR', 'PICKUP'][mt] if mt < 5 else mt})"
        else:
            if kind == 3:
                desc = u32(lay["fx1_descriptors"] + 4 * u8(base + lay["fx1_id"] + track))
            elif kind == 4:
                desc = u32(lay["fx2_descriptors"] + 4 * u8(base + lay["fx2_id"] + track))
            else:
                desc = lay["lfo_descriptor"] if kind == 1 else lay["amp_descriptor"]
            addr = base + lay["page_base"] + track * lay["page_track_stride"] + (kind - 1) * lay["page_stride"] + slot
            page = names[kind]
        if not desc:
            return None, f"no descriptor for {page}"
        E = desc - 0x38
        name = rd(E + 0x4e + 6 * slot, 6).split(b"\0")[0].decode("ascii", "replace")
        # the enable nibbles are addressed from the descriptor POINTER (E+0x38):
        # `a3@(398)` in 0x40055008, shifted by 4*slot through 0x400a6994
        live = (u32(desc + 0x18e) >> (4 * slot)) & 1
        mn, cnt = s32(E + 0xa2 + 4 * slot), s32(E + 0xd2 + 4 * slot)
        if not live or name in ("", "---") or cnt < 2:
            return None, f"encoder {chr(65 + slot)} edits nothing on {page} ({name or '---'} is not live) -- nothing sent"
        cur = u8(addr)
        if mn < 0 and cur > 127:
            cur -= 256
        return {"row": row, "knob": chr(65 + slot), "name": name, "page": page, "track": track + 1,
                "addr": addr, "min": mn, "count": cnt, "default": u8(E + 0x96 + slot), "cur": cur}, None

    def knob_reset(self, row):
        """Put the parameter encoder `row` edits on the CURRENT page back to
        its init value THROUGH THE FIRMWARE: read the value, send the
        difference as detent reports (at most +-64 each, 30 ms of firmware
        between them), re-read, repeat -- up to six rounds, so a hook that
        does not step one unit per detent still lands. The LCD and the
        sound follow because the firmware did the edit. Nothing is sent
        where the page is not mapped (SETUP windows, menus, MIXER, MIDI
        mode); the dict says what happened either way."""
        if not (0x30 <= row < 0x37):
            return False, {"note": "encoder rows are 0x30-0x36"}
        chunk = int(self.param_map.get("report_chunk", 64) or 64) if self.param_map else 64
        def act(rt):
            info, why = self.page_param(rt, row)
            if info is None:
                return {"ok": False, "note": why}
            addr, target, mn = info["addr"], info["default"], info["min"]
            def read():
                v = rt.uc.mem_read(addr, 1)[0]
                return v - 256 if mn < 0 and v > 127 else v
            before, sent, rounds = info["cur"], [], 0
            cur = before
            while cur != target and rounds < 6:
                step = max(-chunk, min(chunk, target - cur))
                rt.uart64.rx.extend([row, step & 0xff])
                rt.run(ms=30)
                sent.append(step)
                rounds += 1
                nxt = read()
                if nxt == cur:      # the firmware did not move it: stop rather than pile up reports
                    break
                cur = nxt
            after = read()
            note = ("already at init" if before == target else
                    "reset" if after == target else
                    f"stopped at {after} (the encoder did not move the value further)")
            return {"ok": after == target, "note": note, "knob": info["knob"], "name": info["name"],
                    "page": info["page"], "track": info["track"], "addr": f"{addr:#x}", "before": before,
                    "after": after, "init": target, "range": [mn, mn + info["count"] - 1], "sent": sent}
        ok, res = self.do(act, timeout=120)
        if not ok:
            return False, {"note": str(res)}
        return bool(res.get("ok")), res

    KNOB_PUSH_ROW = 0x27    # the encoders' push switches: key-matrix row 0x27, bit = encoder index

    def knob_press(self, row, hold=60.0):
        """The encoder's PUSH switch. The panel scanner reports it as a key
        in matrix row 0x27, bit = the encoder's index (A-F = bits 0-5, LEVEL
        = bit 6; the descriptor table at [0x46c901dc] carries key codes
        0x38-0x3f for that row): found 13 Sep 2026, KEYMAP.md "The encoder
        push". Down, `hold` ms of firmware, up -- through _key_act, so a
        TRIG key held on rows 0x20/0x21 (a page chord or /key) stays held
        around it. With a trig held in GRID RECORDING the push TOGGLES that
        step's lock on the parameter this encoder edits: removes it, or
        sets one at the current value when there is none (measured on the
        OTLIVE fixture: PTCH lock 0x45 -> 0xff on the push, 0xff -> 0x40 on
        the next), as the unit's [TRIG] + knob press does (manual 12.5); with
        a SCENE key held it removes that parameter's scene lock (manual
        10.3.1). Bare, it only nudges a redraw."""
        if not (0x30 <= row < 0x37):
            return False, {"note": "encoder rows are 0x30-0x36"}
        bit = row - 0x30
        hold = max(10.0, min(float(hold), 2000.0))
        def act(rt):
            st = self.row_state or {}
            held = [f"{r:#04x}={m:#04x}" for r, m in sorted(st.items()) if m and r != self.KNOB_PUSH_ROW]
            trig = any(st.get(r, 0) for r in (0x20, 0x21))
            scene = bool(st.get(0x23, 0) & 0x06)
            a = self._key_act(rt, self.KNOB_PUSH_ROW, bit, True, run_ms=hold)
            b = self._key_act(rt, self.KNOB_PUSH_ROW, bit, False, run_ms=50.0)
            note = ("with a TRIG key held: the step's lock on this parameter is toggled (removed; set at the current value if there was none)" if trig
                    else "with a SCENE key held: the parameter's scene lock is removed" if scene
                    else "no TRIG or SCENE key held: nothing is locked or unlocked (the firmware only redraws)")
            return {"row": f"{row:#04x}", "bit": bit, "cell": f"{self.KNOB_PUSH_ROW:#04x}.{bit}", "hold_ms": hold,
                    "sent": [a, b], "held": held, "trig_held": trig, "scene_held": scene, "note": note}
        ok, res = self.do(act, timeout=120)
        if not ok:
            return False, {"note": str(res)}
        return True, res

    def xfader(self, pos=None):
        """The crossfader. `pos` 0..127 (0 = leftmost = scene A, 127 =
        rightmost = scene B, the same scale as MIDI CC 48) is sent the way
        the panel board reports the pot: `0x40 <byte>` on the panel UART,
        byte = 2*(127-pos)+1, which the firmware scales to its own 0..127
        (127 = A). None = just read. Answers the firmware's value either
        way: {pos, xf, cc48, scene_a, scene_b}."""
        def act(rt):
            uc = rt.uc
            byte = None
            if pos is not None:
                p = max(0, min(127, int(pos)))
                byte = 2 * (127 - p) + 1
                rt.uart64.rx.extend([XFADER_ROW, byte])
                rt.run(ms=30)
            xf = int.from_bytes(uc.mem_read(XFADER, 4), "big", signed=True)
            out = {"pos": 127 - xf, "xf": xf, "cc48": 127 - xf, "byte": byte}
            try:
                pm = self.param_map
                base = (int.from_bytes(uc.mem_read(pm["ram"]["part_ptr"], 4), "big")
                        + uc.mem_read(pm["ram"]["part_index"], 1)[0] * pm["layout"]["part_stride"])
                out["scene_a"] = uc.mem_read(base + SCENE_A_OFF, 1)[0] + 1
                out["scene_b"] = uc.mem_read(base + SCENE_B_OFF, 1)[0] + 1
            except Exception:
                pass
            return out
        ok, res = self.do(act, timeout=120)
        return (True, res) if ok else (False, {"note": str(res)})

    # PLAY and STOP as the panel scanner reports them (key_map.json, measured
    # 11 Sep 2026): row 0x25 bit 0 and row 0x24 bit 7. FUNC is 0x25 bit 5.
    PLAY_KEY = (0x25, 0)
    STOP_KEY = (0x24, 7)
    FUNC_KEY = (0x25, 5)

    def _before_play(self, rt):
        """What every PLAY needs BEFORE the key lands, whichever path
        delivers it (key(), transport()). The DSP frame interrupt is what
        steps the sequencer, so frame mode goes on (off again in
        _after_stop -- unless frame_always, the port with the cores, where
        it has been on since the boot). Without this the
        matrix PLAY only flipped the transport word and lit the PLAY LED:
        the position bar never moved (12 Sep 2026).

        Nothing is written into the pattern any more: the per-track byte
        activate_tracks used to set is PLAYS FREE, and FW_TRANSPORT(0)
        skips every track whose byte is set -- setting all eight was what
        kept the running light and the fired-trig LEDs off (KEYMAP.md
        "the trig-row running light", 12 Sep 2026). The fixture's bytes are
        clear and it plays as saved."""
        if not rt.frame:
            rt.frame = True
            rt.next_frame = rt.sample + FRAME_PERIOD
        if not self.playing:
            self.playing = True
            self._open_take(rt)         # sound on: a take file from this PLAY to the next STOP
        return [rt.uc.mem_read(rt.pattern_base() + 84 + 2330 * t, 1)[0] for t in range(8)]

    def _after_stop(self, rt):
        if not self.frame_always:
            rt.frame = False
        self.playing = False
        self._close_take(rt)

    # -- sound: the child's audio ring, the server's ring, the takes ----------

    def _scan_takes(self):
        """Takes already in takes_dir (an earlier server on this port): list
        them and number on from the highest."""
        top = 0
        if self.takes_dir is not None and self.takes_dir.is_dir():
            for f in sorted(self.takes_dir.glob("take-*.wav")):
                m = re.fullmatch(r"take-(\d+)\.wav", f.name)
                if not m:
                    continue
                n = int(m.group(1))
                frames = max(0, f.stat().st_size - 44) // 4
                self.takes.append({"n": n, "file": str(f), "frames": frames,
                                   "seconds": round(frames / AUDIO_RATE, 3), "recording": False})
                top = max(top, n)
        return top + 1

    def _audio_start(self, rt):
        """`audio start main` on a fresh child -- at the first boot and after
        every respawn, card re-insert and sound switch (the child's ring
        restarts from zero; the server's AudioRing keeps counting, so the
        absolute frame numbers keep increasing across it). Sets sound /
        audio_on / sound_note; a child that refuses (no --dsp) leaves the
        panel working without sound and says so."""
        self.audio_on = False
        self._dropped_base = self.audio_dropped
        self._dropped_at = 0.0
        if not isinstance(rt, PortRt) or not self.sound_wanted:
            self.sound = False
            self.sound_note = self.audio_note or SOUND_OFF_NOTE
            return
        mode = OUTPUT_CAPTURE if self._output_live() else "main"
        try:
            mode = self._capture_start(rt, mode)
        except PortError as e:
            self.sound = False
            self.audio_note = self.sound_note = f"sound off: the child refused `audio start main` ({e})"
            return
        self.audio_mode, self.audio_words = mode, CAPTURE_WORDS[mode]
        self.audio_on = True
        self.sound = True
        self.audio_note = None
        self.sound_note = SOUND_ON_RT_NOTE if self.sound_rt else SOUND_ON_NOTE
        if not self.sound_rt and self.backend_note and "--dsp-rt child did not boot" in self.backend_note:
            self.sound_note += " -- the --dsp-rt child did not boot (backend_note says why)"

    def _capture_start(self, rt, mode):
        """`audio start <mode>` on the child, falling back down the list
        (tracks -> all -> main) when the child does not know the mode (an
        older --port-bin); the note says what the output gets. Returns the
        mode started; raises PortError when even `main` is refused."""
        chain = ["tracks", "all", "main"]
        for m in chain[chain.index(mode):]:
            try:
                rt.proc.command(f"audio start {m}", "ok")
            except PortError as e:
                if m == "main":
                    raise
                self.output_note = (f"the child refused `audio start {m}` ({e}): the output gets "
                                    + ("main, cue and the ESAI words, no per-track stems" if m == "tracks" else "main L/R only"))
                print(f"panel: {self.output_note}")
                continue
            return m
        raise PortError("no capture mode")

    def _drain_audio(self, rt):
        """Everything the child captured since the previous drain, into the
        ring and the open take. `audio read` answers what is there and
        never blocks (O14k: 0.2 ms wall for a 100 ms slice, 8.8 KB of hex
        for a 25 ms pump); read in AUDIO_READ_MAX pieces while a piece
        comes back full. The child's `dropped` counter (frames it overwrote
        before a read) is polled once a wall second, not per pump. Always
        on the emu thread, like every pipe command. Returns frames drained."""
        if not self.audio_on or not isinstance(rt, PortRt):
            return 0
        got = 0
        t0 = time.perf_counter()
        while True:
            rep = rt.proc.command(f"audio read {AUDIO_READ_MAX}", "audio")
            head, _, hexs = rep[6:].partition(" ")          # "audio <frames> <hex>"
            n = int(head)
            if n:
                data = bytes.fromhex(hexs.strip())
                bpf = self.audio_words * 2
                if len(data) != n * bpf:
                    raise PortError(f"audio read: {n} frames announced, {len(data)} bytes of PCM ({self.audio_mode})")
                out = self.output
                if self.audio_words > 2:
                    # eight words a frame (O14k `all`) or 24 (O23 `tracks`): the
                    # whole frame to the device; main L/R (words 2/3) on to the
                    # ring, the take and /audio/pcm -- byte for byte what `main`
                    # gives; cue's peak beside
                    pairs = memoryview(data).cast("i")         # one int32 per L/R pair
                    su = self.audio_words // 2
                    if out is not None and out.running:
                        out.push(data, self.audio_words)
                    self.audio_peak_cue = pcm_peak(pairs[2::su].tobytes())
                    data = pairs[1::su].tobytes()
                elif out is not None and out.running:
                    out.push(data, 2)
                self.ring.append(data)
                self.audio_captured += n
                self.audio_peak = pcm_peak(data)
                if self.take is not None:
                    with self.take_lock:
                        self.take.append(data)
                got += n
            if n < AUDIO_READ_MAX:
                break
        if t0 - self._dropped_at > 1.0:
            st = rt.proc.command("audio status", "audio")
            f = dict(kv.split("=", 1) for kv in st.split()[2:] if "=" in kv)
            self.audio_dropped = self._dropped_base + int(f.get("dropped", 0))
            self._dropped_at = t0
        dt = (time.perf_counter() - t0) * 1000.0
        d = self.drain
        d["reads"] += 1; d["frames"] += got; d["wall_ms"] += dt
        if dt > d["max_ms"]:
            d["max_ms"] = dt
        return got

    # -- the output device (13 Sep 2026): AudioOutput above, fed by _drain_audio --

    def _output_live(self):
        o = self.output
        return o is not None and o.running

    def _audio_switch(self, rt, mode):
        """On the emu thread: the child's capture to `mode` (main | all |
        tracks; a mode the child lacks falls back, _capture_start). What is
        pending is drained first; the frames the child renders between that
        read and the restart (at most a pacer slice, ~10 ms) do not reach
        the ring or an open take. No-op when already so, or with the
        capture off. Returns the mode now."""
        if not self.audio_on or not isinstance(rt, PortRt) or mode == self.audio_mode:
            return self.audio_mode
        self._drain_audio(rt)
        mode = self._capture_start(rt, mode)
        self.audio_mode, self.audio_words = mode, CAPTURE_WORDS[mode]
        self._dropped_base = self.audio_dropped     # the child's counter restarts with its ring
        self._dropped_at = 0.0
        return mode

    def _queue_capture(self, mode):
        """The child's capture to `mode`, as an action, when there is a
        child to ask; a child that boots later (respawn, re-insert, sound
        switch) picks the mode itself in _audio_start."""
        if not self.booted or self.card_ejected or self.card_busy or self.sound_busy:
            return

        def act():
            try:
                self._audio_switch(self.rt, mode)
            except PortError as e:
                self.output_note = f"capture `{mode}`: {e}"
                print(f"panel: audio capture: {self.output_note}")
        self.actions.put(act)

    def audio_device_list(self):
        """/audio/devices: the output-capable devices PortAudio sees (rescanned
        while no stream is open), the output's state, the capture mode."""
        with self.output_lock:
            devices, note = audio_devices(refresh=not self._output_live())
        if devices is None:
            return {"ok": False, "available": sounddevice()[0] is not None, "error": note, "devices": [],
                    "output": self.output_status(), "capture": self.audio_mode}
        return {"ok": True, "available": True, "devices": devices, "note": note,
                "output": self.output_status(), "capture": self.audio_mode}

    def set_output(self, spec):
        """/audio/output?device=<index|name|off>: the output stream onto that
        device (a running stream on the same device is left as it is: the
        app re-sends its choice at every ready), or off. The child's capture
        follows -- the eight ESAI words plus the eight stems (`tracks`) with
        a device on, main L/R without -- through an emu-thread action. (ok, reply)."""
        spec = (spec or "").strip()
        with self.output_lock:
            cur = self.output
            if spec.lower() in ("", "off", "none"):
                if cur is not None:
                    cur.stop("stopped: /audio/output?device=off")
                    self.output = None
                    print(f"panel: audio output off (was {cur.name})")
                self.output_note = None
                self._queue_capture("main")
                return True, {"ok": True, "output": self.output_status(), "capture": self.audio_mode,
                              "note": "output off" + (f" (was {cur.name})" if cur is not None else "")}
            sd, why = sounddevice()
            if sd is None:
                self.output_note = why
                return False, {"ok": False, "error": why, "output": self.output_status()}
            if cur is not None and cur.running:
                devices, _ = audio_devices(refresh=False)
                try:
                    dev = resolve_device(spec, devices or [])
                except LookupError:
                    dev = None
                if dev is not None and dev["index"] == cur.index and dev["name"] == cur.name:
                    return True, {"ok": True, "output": cur.status(), "capture": self.audio_mode,
                                  "note": f"already on {cur.name}"}
            if cur is not None:
                cur.stop("stopped: another device chosen")
                self.output = None
            devices, note = audio_devices(refresh=True)
            if devices is None:
                self.output_note = note
                self._queue_capture("main")
                return False, {"ok": False, "error": note, "output": self.output_status()}
            try:
                dev = resolve_device(spec, devices)
            except LookupError as e:
                self._queue_capture("main")
                return False, {"ok": False, "error": str(e), "devices": [d["name"] for d in devices],
                               "output": self.output_status()}
            try:
                out = AudioOutput(sd, dev)
            except Exception as e:
                self.output_note = f"{dev['name']}: {type(e).__name__}: {e}"
                print(f"panel: audio output: {self.output_note}")
                self._queue_capture("main")
                return False, {"ok": False, "error": self.output_note, "output": self.output_status()}
            self.output = out
            self.output_note = None
            print(f"panel: audio output -> {out.name} ({out.channels} of {dev['channels']} channels: "
                  f"{'; '.join(out.channel_map())}; latency {out.status()['latency_ms']} ms)")
        self._queue_capture(OUTPUT_CAPTURE)
        return True, {"ok": True, "output": self.output_status(), "capture": self.audio_mode,
                      "note": f"output on {out.name}: " + "; ".join(out.channel_map())}

    def output_status(self):
        o = self.output
        if o is None:
            return {"device": None, "index": None, "channels": 0, "running": False, "underruns": 0,
                    "dropped": 0, "latency_ms": None, "buffered_ms": 0.0, "map": [], "note": self.output_note}
        st = o.status()
        if self.output_note and not st.get("note"):
            st["note"] = self.output_note
        return st

    def _open_take(self, rt):
        """PLAY: a new take-NNN.wav gets every frame drained from here on.
        What the child holds now was rendered BEFORE the key: drained into
        the ring first, so the file starts at the PLAY press."""
        if self.takes_dir is None or not self.audio_on or self.take is not None:
            return
        self._drain_audio(rt)
        self.takes_dir.mkdir(parents=True, exist_ok=True)
        n, self.take_seq = self.take_seq, self.take_seq + 1
        with self.take_lock:
            self.take = TakeWriter(self.takes_dir / f"take-{n:03d}.wav", n, self.ring.end)

    def _close_take(self, rt):
        """STOP (rt given: the frames up to the key are drained into it
        first) or a reboot (rt None: the child is gone). The take joins the
        list; None when no take was open."""
        if self.take is None:
            return None
        try:
            if rt is not None:
                self._drain_audio(rt)
        finally:
            with self.take_lock:
                t, self.take = self.take, None
                t.close()
                info = t.info()
                self.takes.append(info)
        return info

    def take_file(self, n):
        """(info, path) of take n -- the open one included -- or (None, None)."""
        with self.take_lock:
            if self.take is not None and self.take.n == n:
                return self.take.info(recording=True), self.take.path
            for t in self.takes:
                if t["n"] == n:
                    return dict(t), pathlib.Path(t["file"])
        return None, None

    def audio_status(self):
        with self.take_lock:
            take = self.take.info(recording=True) if self.take is not None else None
        takes = list(self.takes) + ([take] if take else [])
        return {"sound": self.sound, "on": self.audio_on, "rate": AUDIO_RATE,
                "captured": self.audio_captured, "end": self.ring.end, "first": self.ring.first,
                "cap": self.ring.cap, "dropped": self.audio_dropped, "peak": list(self.audio_peak),
                "take": take, "takes": takes, "note": self.audio_note or self.sound_note,
                # additions beyond the contract: the reboot state the page disables its controls on,
                # where the files land, and what the drain itself costs the pump
                "busy": self.sound_busy or self.card_busy, "phase": self.phase,
                "takes_dir": str(self.takes_dir) if self.takes_dir else None,
                "drain": dict(self.drain),
                # the output device (13 Sep 2026): the child's capture mode (main = 2
                # words a frame; tracks = 24 -- the ESAI words and the eight stems, O23
                # -- while a device is on, all = 8 on an older child), the cue pair's
                # peak of the last multi-word read, and the stream itself
                "capture": self.audio_mode, "words": self.audio_words,
                "peak_cue": list(self.audio_peak_cue),
                "output": self.output_status()}

    SOUND_ON_PHASE = "switching sound on (reboot, ~1 min)"
    SOUND_OFF_PHASE = "switching sound off (reboot, ~40 s)"

    def set_sound(self, on):
        """/audio/enable: reboot the port child with (on) or without --dsp,
        the card re-insert's own mechanics (_reboot_port: a fresh child on
        the same card image, the clock dialog closed, phase shown, booted
        false meanwhile). Takes and the ring survive; the child's ring
        restarts and the server keeps numbering on. Refused while a
        re-insert or another switch runs, while booting, when already in
        that state."""
        on = bool(on)
        if self.card_busy:
            return False, "the card is being re-inserted (reboot in progress)"
        if self.sound_busy:
            return False, "a sound switch is already in progress"
        if not self.booted:
            return False, f"the unit is still booting ({self.phase})"
        if on == self.sound_wanted:
            return False, f"sound is already {'on' if on else 'off'}"
        self.sound_busy = True
        phase = self.SOUND_ON_PHASE if on else self.SOUND_OFF_PHASE
        self.phase = phase

        def act():
            self.busy_since = None          # a boot, not an action the watchdog may time
            t0 = time.perf_counter()
            self.sound_wanted = on
            self.audio_note = None
            try:
                ok = self._reboot_port(phase)
                if not ok and on:
                    # the --dsp child did not come up three times: back without the cores
                    why = self.fault
                    self.sound_wanted = False
                    self.audio_note = f"sound off: the --dsp child did not boot ({why})"
                    ok = self._reboot_port(self.SOUND_OFF_PHASE)
                if ok:
                    self.fault = None
                    print(f"panel: sound {'on' if self.sound else 'off'} after a reboot of"
                          f" {time.perf_counter() - t0:.1f} s ({self.sound_note})")
            except Exception as e:
                self.fault = f"sound switch: {type(e).__name__}: {e}"
                alive = self.proc is not None and self.proc.alive()
                self.phase = "ready" if alive else "failed"
            finally:
                self.sound_busy = False
        self.actions.put(act)
        return True, phase

    def transport(self, what):
        """PLAY / REC / STOP for scripting: the key through the matrix
        (PLAY 0x25.0, REC 0x25.1, STOP 0x24.7), down then up, with the
        helpers key() wraps around PLAY/STOP."""
        if what not in ("play", "rec", "stop"):
            return False, "play|rec|stop"
        row, bit = {"play": self.PLAY_KEY, "rec": (0x25, 1), "stop": self.STOP_KEY}[what]
        def tap(rt):
            # one action, down then up: the down edge keeps its 50 ms of
            # firmware (the paced child would otherwise see both edges
            # in the same slice)
            down = self._key_act(rt, row, bit, True, run_ms=50.0)
            up = self._key_act(rt, row, bit, False, run_ms=50.0)
            return f"matrix tap: {down}; {up}"
        return self.do(tap, timeout=120)

    def activate_tracks(self, rt, tracks=range(8)):
        """Set the per-track PLAYS FREE byte in the current pattern record
        (+84 + 2330*t). No longer called by PLAY or poke_trig (12 Sep 2026):
        the 10 Sep reading of it as an "active" flag was wrong -- the two
        firmware consumers say the opposite. FW_TRANSPORT(0) (0x4009b964,
        the PLAY key's path) sets up a track only if the byte is ZERO
        (0x4009bc76), and FW_START_TRACK (0x4009b5c8, the trig-key start)
        acts only if it is SET (0x4009b630); with the byte set, PLAY calls no
        step handler for that track, so it fires nothing. Kept for scripts
        that want a plays-free track on purpose."""
        pb = rt.pattern_base()
        for t in tracks:
            rt.uc.mem_write(pb + 84 + 2330 * t, b"\x01")
        return [rt.uc.mem_read(pb + 84 + 2330 * t, 1)[0] for t in range(8)]

    def poke_trig(self, step, track=0):
        def act(rt):
            pb = rt.pattern_base()
            flags = [rt.uc.mem_read(pb + 84 + 2330 * t, 1)[0] for t in range(8)]
            return f"mask {rt.poke_trig(int(step)):#04x}, plays-free bytes {flags}"
        return self.do(act, timeout=60)

    _led_pos = 0

    def led_payload(self):
        """The LED state the page renders: {"bits": <17 row bytes hex>, "ids": {id: level}}."""
        with self.lock:
            ids = dict(self.led_ids)
            bits = bytes(self.led_bits)
            if self.link is not None:
                try:
                    rows = self.link.led_rows
                    bits = bytes(rows.get(i, 0) for i in range(17))
                    ids = dict(self.link.leds)
                except Exception:
                    pass
        return {"bits": bits.hex(), "ids": {f"{k:#04x}": v for k, v in ids.items()}}

    def _parse_leds(self, rt):
        """Parse the firmware->panel stream for LED state. Frames seen in a
        real boot: a bare 0x43 hello; `<id> <value>` pairs (brightness init,
        value 0x3f); `0x10 <offset> <8 bytes>` bitmap blocks. The bitmap is
        what the trig/track LEDs live in; ids carry per-entity values."""
        tx = rt.uart64.tx
        i = self._led_pos
        n = len(tx)
        while i < n:
            b = tx[i]
            if b == 0x43:
                i += 1
            elif b == 0x10:
                if i + 10 > n:
                    break
                off = tx[i + 1]
                if off + 8 <= len(self.led_bits):
                    self.led_bits[off:off + 8] = tx[i + 2:i + 10]
                i += 10
            else:
                if i + 2 > n:
                    break
                self.led_ids[b] = tx[i + 1]
                i += 2
        with self.lock:
            self._led_pos = i

    busy_since = None
    ACTION_LIMIT = 20.0      # wall seconds an action may hold the emulator
    RUN_SLICE_MS = 5.0       # emulated ms per slice of run_ms() (5 ms wall idle, ~0.1 s playing)
    SLOW_PUMP_MS = 6.0       # the idle pump for SLOW_WALL_S after a track key is released
    SLOW_WALL_S = 0.5        # (the double-tap window, see _loop)
    TRACK_ROW = 0x22         # the track keys T1-T8 (KEYMAP.md)

    def _watchdog(self):
        """Flag an action that holds the emulator too long (self.abort);
        run_ms() checks the flag between its slices and gives up.

        It cannot stop the action itself: Unicorn's emu_stop() from another
        thread ends one BURST, and Rtos.run() then simply starts the next
        (it loops step() until its ms elapse or its until() holds) -- the
        first version called emu_stop() here and /run?ms=5000 while frame
        mode was on still held the emulator for 356 s wall (verifier,
        12 Sep 2026). An early-ended burst is also charged its whole
        quantum (Rtos.step: instrs += n), a timing glitch for nothing, so
        emu_stop() is gone."""
        while True:
            time.sleep(1.0)
            t0 = self.busy_since
            if t0 is not None and time.perf_counter() - t0 > self.ACTION_LIMIT:
                self.aborted = (self.aborted or 0) + 1
                self.abort = True
                self.busy_since = time.perf_counter()   # re-arm; flag once per limit
                # The port CAN be stopped: a child that has not answered in
                # ACTION_LIMIT is killed here; the command blocked on it
                # raises PortDied and the loop respawns (_respawn).
                if self.proc is not None and self.proc.alive():
                    self.fault = f"watchdog: the port answered nothing for {self.ACTION_LIMIT:.0f} s; killed"
                    self.proc.kill()

    aborted = 0
    abort = False

    def run_ms(self, rt, ms, wall=None):
        """rt.run(ms=ms) in RUN_SLICE_MS slices, stopping early after `wall`
        seconds (one under ACTION_LIMIT by default, so the budget and not
        the watchdog is what ends it) or on the watchdog's flag; /status
        ran_ms follows the slices. Where a slice ends moves no firmware
        event (timers, frames and the panel UART advance by sample count),
        so the emulated timing is the plain run's. Needed because a long
        rt.run() is uninterruptible (see _watchdog) and in frame mode 5000
        ms of firmware is minutes of wall time: the page's RUN 1s / RUN 5s
        buttons froze it for the whole of that. Measured 12 Sep 2026
        (fix_srv.log): while playing /run?ms=1000 returned in 17.0 s at 59
        emulated ms per wall s (the pump's rate) and /run?ms=5000 stopped
        at 1202 ms after 20.1 s; idle, 1000 ms is instant (idle time is
        skipped to the next timer). Returns a one-line report."""
        wall = self.ACTION_LIMIT - 1.0 if wall is None else wall
        t0 = time.perf_counter()
        s0 = rt.sample
        end = s0 + ms * SAMPLE_HZ / 1000.0
        self.abort = False
        why = "done"
        slice_ms = getattr(rt, "SLICE_MS", self.RUN_SLICE_MS)   # the port: a round trip per slice
        while rt.sample < end:
            left = (end - rt.sample) / SAMPLE_HZ * 1000.0
            # O15f: the child ends the slice itself when the budget is
            # spent (`run <ms> wall <s>`), so the slice, not just the
            # loop, is bounded in wall time
            rt.run(ms=min(left, slice_ms), wall=max(0.01, wall - (time.perf_counter() - t0)))
            self.ran_ms = rt.sample / SAMPLE_HZ * 1000.0
            self._drain_audio(rt)       # the ring and the take keep up slice by slice
            if self.abort:
                why = "watchdog"; break
            if time.perf_counter() - t0 > wall or getattr(rt, "stop_reason", None) == "wall":
                why = f"{wall:.0f} s wall budget"; break
        ran = (rt.sample - s0) / SAMPLE_HZ * 1000.0
        dt = time.perf_counter() - t0
        rate = f" ({ran / dt:.0f} emulated ms per wall s{', frame mode on' if rt.frame else ''})" if dt > 0.2 else ""
        if why == "done":
            return f"ran {ran:.0f} ms in {dt:.1f} s{rate}"
        return f"ran {ran:.0f} of {ms:.0f} ms in {dt:.1f} s: {why}{rate}"

    def do(self, fn, timeout=30.0):
        """Run fn(rt) on the emu thread, return (ok, result-or-error)."""
        if self.card_ejected:
            return False, f"the card is ejected (mounted at {self.card_mount}): insert it first"
        done = threading.Event()
        box = {}
        def act():
            try:
                box["r"] = fn(self.rt)
                box["ok"] = True
            except PortDied as e:
                # the child is gone: answer this caller, then let the loop respawn
                box["r"] = f"port: {e}"
                box["ok"] = False
                raise
            except Exception as e:
                box["r"] = f"{type(e).__name__}: {e}"
                box["ok"] = False
            finally:
                done.set()
        self.actions.put(act)
        if not done.wait(timeout):
            return False, "timeout (emulator busy)"
        return box["ok"], box["r"]

    row_state = None   # per-row pressed-bit bytes, lazily created

    def key(self, row, bit, down):
        """A key through the real input path: the panel scanner's UART.

        The front panel talks to the CPU over UART@fc064000 (found 10 Sep
        2026: the firmware sends its LED traffic out on it and its receive
        interrupt is armed). Key events are TWO-byte matrix reports:
        `<row> <column-bitmask>` -- a bit set is a key held down, cleared is
        released (verified: row 0x25 bit 6 alone opens PATTERN SETTINGS
        over the SET DATE/TIME dialog). Per-row state is kept here so
        FUNC-style holds across rows work exactly as fingers do.
        """
        if not (0x20 <= row < 0x30 and 0 <= bit < 8):
            return False, "bad row/bit"
        return self.do(lambda rt: self._key_act(rt, row, bit, down), timeout=120)

    def tap(self, row, bit, n=1, hold=50, gap=150):
        """`n` presses of one key as ONE action: `hold` ms down, `gap` ms
        up between presses. Needed for the firmware's double-tap chords --
        a track key pressed twice opens the sample slot list (found 12 Sep
        2026 by a PC watch on the list's window store 0x4007920c under a
        pumpless ot_emu: every T1-T8 double-tapped, nothing else in 47
        keys x {alone, held 1.2 s, under 20 modifiers}). Two /key taps
        may or may not qualify: the firmware's window is short in ITS
        time, and the idle pump runs between separate actions -- four
        back-to-back curl /key edges (225 emulated ms over the two
        presses) opened it, the same two taps 0.2 s of wall apart (375
        emulated ms press to press) or 0.5/1/2 s apart did not (measured
        12 Sep 2026, port, OTLIVE). Inside one action the gap is exactly
        `gap` (200 ms press to press by default), so this is the reliable
        way; page clicks are separate actions and may not land."""
        if not (0x20 <= row < 0x30 and 0 <= bit < 8):
            return False, "bad row/bit"
        n = max(1, min(int(n), 8))
        hold = max(10.0, min(float(hold), 2000.0))
        gap = max(10.0, min(float(gap), 2000.0))
        def act(rt):
            out = []
            for i in range(n):
                out.append(self._key_act(rt, row, bit, True, run_ms=hold))
                out.append(self._key_act(rt, row, bit, False, run_ms=gap if i < n - 1 else 50.0))
            return f"{n} x ({hold:g} ms down, {gap:g} ms up): " + "; ".join(out)
        return self.do(act, timeout=120)

    def _key_act(self, rt, row, bit, down, run_ms=None):
        """One key edge on the emu thread (key() queues it; transport() on
        the port taps down+up through it; tap() chains them), then
        `run_ms` of firmware. `run_ms` None = the default: 50 ms, or under
        the paced child (O15f) NO run of its own for an ordinary key -- the
        pacer's next 10 ms slice delivers it within a slice of emulated
        time anyway, and the 50 ms run cost the click 50 emulated ms of
        wall at the core's rate (40 ms playing without the cores, ~330 with
        them; measured 12 Sep 2026) -- except PLAY down and STOP down,
        which keep it so the frame-mode switch and the take open/close sit
        around a processed key, as they always did."""
        if self.row_state is None:
            self.row_state = {}
        if down:
            self.row_state[row] = self.row_state.get(row, 0) | (1 << bit)
        else:
            self.row_state[row] = self.row_state.get(row, 0) & ~(1 << bit)
        state = self.row_state[row]
        # PLAY going down (not under FUNC: FUNC+PLAY is CLEAR PATTERN) gets
        # the same preparation the /transport path always had; STOP going
        # down takes frame mode off again after the key. The page has sent
        # PLAY as its matrix cell since the map was measured, and a bare
        # matrix PLAY started the transport but never stepped it (12 Sep
        # 2026 report: play icon and the first bar, no LEDs, no progress).
        func_held = bool(self.row_state.get(self.FUNC_KEY[0], 0) & (1 << self.FUNC_KEY[1]))
        play = down and (row, bit) == self.PLAY_KEY and not func_held
        stop = down and (row, bit) == self.STOP_KEY
        if run_ms is None:
            run_ms = 0.0 if getattr(rt, "paced", False) and not (play or stop) else 50.0
        note = ""
        if play:
            note = f" (play: active={self._before_play(rt)}, frame mode on)"
        rt.uart64.rx.extend([row, state])
        if run_ms > 0:
            rt.run(ms=run_ms)
        if stop:
            self._after_stop(rt)
            note = " (stop: frame mode off)"
        if not down and row == self.TRACK_ROW:
            self.slow_until = time.perf_counter() + self.SLOW_WALL_S
        return f"row {row:#04x} = {state:#04x}{note}"


def _pace_json(st):
    """The child's last `pacestatus` for /status: numbers, not strings."""
    if not st:
        return None
    f = lambda k, c=float: c(st[k]) if k in st else None   # noqa: E731
    return {"on": st.get("on") == "1", "rate": f("rate"), "ratio": f("ratio"), "lag_ms": f("lag"),
            "slices": f("slices", int), "reanchors": f("reanchors", int), "slept_s": f("slept"),
            "busy_s": f("busy"), "stop": st.get("stop")}


class Handler(BaseHTTPRequestHandler):
    panel: Panel = None
    html: bytes = b""
    model: str = "mki"

    last_request = time.monotonic()     # --idle-timeout's clock: any request resets it

    def log_message(self, *a):  # quiet
        pass

    def parse_request(self):
        Handler.last_request = time.monotonic()
        return super().parse_request()

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode())

    # The sample pool (SamplePool, Panel.commit_card): the set's AUDIO folder
    # the card is built from. Query values are URL-encoded (a Mac path with
    # spaces arrives as %20 or +). Adds and removes change the pool only;
    # the unit sees them after /samples/commit re-inserts the card (~40 s,
    # /status "phase"); while that runs every one of these answers ok:false.
    def _samples(self, path, args, body=None):
        p = self.panel
        arg = lambda k: urllib.parse.unquote_plus(args.get(k, ""))  # noqa: E731
        if p.pool is None:
            self._json({"ok": False, "error": "no sample pool"}, 500)
            return
        if path == "/samples":
            if p.card_persistent and not p.card_ejected and not p.card_busy:
                p.refresh_card_files()          # O19: the image as it is now (no mount)
            added, removed = p.pending()
            self._json({"pool": str(p.pool.path), "staged": str(p.staged_audio) if p.staged_audio else None,
                        "files": p.samples_files(), "pending": added, "removed": removed,
                        "busy": p.card_busy, "phase": p.phase,
                        # O19: the card itself
                        "card": str(p.card_file) if p.card_file else None,
                        "card_mode": "persistent" if p.card_persistent else "fresh",
                        "card_rw": p.card_rw, "card_ejected": p.card_ejected})
            return
        if p.card_busy:
            self._json({"ok": False, "error": "the card is being re-inserted (reboot in progress)",
                        "note": f"try again when /status phase is ready (now: {p.phase})"})
            return
        if path == "/samples/add":
            src = arg("path")
            if not src.startswith("/") and not src.startswith("~"):
                self._json({"ok": False, "error": "path must be absolute"})
                return
            r = p.pool.add(src)
        elif path == "/samples/upload":
            name = arg("name")
            if not name:
                self._json({"ok": False, "error": "name= is required"})
                return
            if not body:
                self._json({"ok": False, "error": "empty body (POST the raw file bytes)"})
                return
            # afconvert and the header parse want a file: the body lands in
            # the pool folder under a dot name and goes through add() as
            # /samples/add would (the reply names the upload, not the
            # temporary), then the temporary is removed.
            tmp = p.pool.path / f".upload-{os.getpid()}-{threading.get_ident()}-{SamplePool.card_name(name, None, False)}"
            try:
                tmp.write_bytes(body)
                r = p.pool.add(tmp, name=name, shown=name)
            finally:
                if tmp.exists():
                    tmp.unlink()
        elif path == "/samples/remove":
            r = p.remove_sample(arg("name"))
        elif path == "/samples/commit":
            ok, res = p.commit_card()
            self._json({"ok": ok, "phase": res} if ok else {"ok": False, "error": res, "phase": p.phase})
            return
        else:
            self._send(404, b"?", "text/plain")
            return
        if r.get("ok"):
            r["pending"] = p.pending()[0]
        self._json(r)

    # The main output (AudioRing, the takes; sound on = the child runs --dsp).
    # /audio/status and /audio/pcm read the ring on this thread under its own
    # lock -- no emu-thread action, so they answer while the pump runs;
    # /audio/enable queues the reboot. Every answer here is JSON or audio:
    # bad numbers are 400, a missing take 404, never a traceback.
    def _audio(self, path, args):
        p = self.panel

        def num(k, default):
            v = args.get(k)
            if v in (None, ""):
                return int(default)
            return int(v, 0) if v.lower().startswith(("0x", "0o", "0b")) else int(v)

        def send_wav(data, name, extra=()):
            body = wav_header(len(data) // 4) + data
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            for k, v in extra:
                self.send_header(k, str(v))
            self.end_headers()
            self.wfile.write(body)

        try:
            if path == "/audio/status":
                self._json(p.audio_status())
            elif path == "/audio/pcm":
                # raw LE int16 stereo frames from the ring: from=<absolute frame>
                # (clamped up to the oldest still held; X-Audio-From says where the
                # body really starts), max= frames (default 2 s, at most 10 s)
                start = max(0, num("from", 0))
                mx = max(1, min(num("max", 88200), 441000))
                frm, data, end = p.ring.read(start, mx)
                if not data:
                    self.send_response(204)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Audio-End", str(end))
                    self.send_header("X-Audio-Rate", str(AUDIO_RATE))
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Audio-From", str(frm))
                self.send_header("X-Audio-Frames", str(len(data) // 4))
                self.send_header("X-Audio-End", str(end))
                self.send_header("X-Audio-Rate", str(AUDIO_RATE))
                self.end_headers()
                self.wfile.write(data)
            elif path == "/audio.wav":
                if args.get("take") not in (None, ""):
                    n = num("take", 0)
                    info, file = p.take_file(n)
                    if info is None:
                        self._json({"ok": False, "error": f"no take {n}", "takes": [t["n"] for t in p.takes]}, 404)
                        return
                    with p.take_lock:               # not mid-append of the open take
                        raw = file.read_bytes() if file.exists() else b""
                    if len(raw) < 44 or raw[:4] != b"RIFF":
                        self._json({"ok": False, "error": f"take {n}: {file} is not a WAV"}, 404)
                        return
                    data = raw[44:len(raw) // 4 * 4]  # the header is rebuilt from what is there now
                    send_wav(data, f"octatrack-take-{n:03d}.wav",
                             [("X-Audio-Take", n), ("X-Audio-Frames", len(data) // 4),
                              ("X-Audio-Recording", int(bool(info.get("recording"))))])
                else:
                    # the ring: from=..&to=.. absolute frames, default everything held
                    first, end = p.ring.first, p.ring.end
                    frm = max(num("from", first), first)
                    to = min(num("to", end), end)
                    if to <= frm:
                        self._json({"ok": False, "error": "nothing captured in that range",
                                    "first": first, "end": end, "sound": p.sound}, 404)
                        return
                    frm, data, end = p.ring.read(frm, to - frm)
                    send_wav(data, "octatrack-main-out.wav",
                             [("X-Audio-From", frm), ("X-Audio-Frames", len(data) // 4), ("X-Audio-End", end)])
            elif path == "/audio/devices":
                # the output device (13 Sep 2026): what PortAudio sees, + the output's state
                self._json(p.audio_device_list())
            elif path == "/audio/output":
                # ?device=<index|name|off> starts / stops the stream; without it, the state
                if "device" not in args:
                    self._json({"ok": True, "output": p.output_status(), "capture": p.audio_mode})
                else:
                    ok, rep = p.set_output(urllib.parse.unquote_plus(args.get("device", "")))
                    self._json(rep, 200 if ok else (404 if "devices" in rep else 500))
            elif path == "/audio/enable":
                v = args.get("on", "1").lower()
                if v not in ("1", "0", "on", "off", "true", "false"):
                    self._json({"ok": False, "error": f"on={v!r}: want 1|0"}, 400)
                    return
                ok, res = p.set_sound(v in ("1", "on", "true"))
                if ok:
                    self._json({"ok": True, "phase": res, "sound": p.sound})
                else:
                    self._json({"ok": False, "note": res, "phase": p.phase, "sound": p.sound,
                                "busy": p.sound_busy or p.card_busy})
            else:
                self._json({"ok": False, "error": "no such audio endpoint",
                            "endpoints": ["/audio/status", "/audio/pcm", "/audio.wav", "/audio/enable",
                                          "/audio/devices", "/audio/output"]}, 404)
        except ValueError as e:
            self._json({"ok": False, "error": f"bad number: {e}"}, 400)

    def do_POST(self):
        path, _, q = self.path.partition("?")
        args = dict(kv.split("=", 1) for kv in q.split("&") if "=" in kv)
        if path == "/samples/upload":
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n > 0 else b""
            self._samples(path, args, body)
        else:
            self._send(404, b"?", "text/plain")

    def do_GET(self):
        p = self.panel
        path, _, q = self.path.partition("?")
        args = dict(kv.split("=", 1) for kv in q.split("&") if "=" in kv)
        if path == "/":
            # read per request: a page fix must not need a server (or app) restart
            page = pathlib.Path(__file__).parent / "panel.html"
            self._send(200, page.read_bytes() if page.exists() else self.html, "text/html; charset=utf-8")
        elif path == "/skin.js":
            # The panel's face: octemu's generated MKII skin (tools/panel/skin/
            # gen_svg.py, Mark Roberts, MIT) in octabam's dark palette, as one
            # script the page loads before it builds (window.SKIN = the element
            # geometry, window.SKIN_SVG = the drawing). Generated once per
            # server into out/panel_skin/.
            self._send(200, skin_js(), "application/javascript; charset=utf-8")
        elif path == "/screen.png":
            with p.lock:
                self._send(200, p.frame or _png_rgb(128, 64, [LCD_OFF * 128] * 64), "image/png")
        elif path == "/screen.txt":
            # the frame as 64 lines of '#' (dark) / '.' -- for agents that grep, not view
            with p.lock:
                txt = p.screen_txt or ("." * 128 + "\n") * 64
            self._send(200, txt.encode(), "text/plain; charset=utf-8")
        elif path == "/status":
            with p.lock:
                self._json({"booted": p.booted, "seq": p.seq, "ran_ms": p.ran_ms,
                            "fault": p.fault, "image": str(p.image), "phase": p.phase,
                            "backend": p.backend, "backend_note": p.backend_note or None,
                            # emulated ms per wall s over the last 5 s of run() calls;
                            # idle runs skip to the next timer, so idle reads high
                            "speed": p.meter.value,
                            # O15f: x real time by the WALL clock (emulated ms per
                            # wall s over the last second / 1000): 1.0 = the unit's
                            # clock; None before the pacer is up
                            "rt": p.rtmeter.value,
                            "pace": _pace_json(p.pace),
                            "nice": host_nice(),            # > 0: started as a zsh background job (BG_NICE); slower under load
                            "restarts": p.restarts,
                            "card_busy": p.card_busy,       # a /samples/commit re-insert in progress
                            "clock": p.clock_note,          # what the boot-time YES found
                            "sound": p.sound,               # the child runs the DSP cores and its main out is captured
                            "sound_rt": p.sound_rt,         # O17: ... under --dsp-rt (real time); False = the lockstep --dsp (~0.2x) or no cores
                            "sound_note": p.sound_note,
                            "frame_always": p.frame_always, # 23 Sep 2026: frame mode on from boot (manual [TRIG] trigs sound while stopped)
                            "pid": os.getpid(),             # 23 Sep 2026: so the app can retire a stale server it finds on the port
                            "script_mtime": SCRIPT_MTIME,   # this file's mtime when the server started: older than the file = stale
                            "playing": p.playing,           # PLAY pressed, STOP not yet
                            # O19: the card
                            "card": str(p.card_file) if p.card_file else None,
                            "card_mode": "persistent" if p.card_persistent else "fresh",
                            "card_rw": p.card_rw,             # the child writes through to the file
                            "card_ejected": p.card_ejected,
                            "card_mount": p.card_mount,
                            "project": {"set": p.project[0], "name": p.project[1]} if p.project else None})
        elif path.startswith("/samples"):
            self._samples(path, args)
        elif path == "/card":
            # O19: the card as a whole: file, sidecar, names, write-back, the
            # eject state, the AUDIO listing and the sets on it (the image
            # read directly, no mount)
            sets = {}
            if p.card_file and not p.card_ejected:
                try:
                    with Fat16Image(p.card_file) as img:
                        sets = img.sets()
                except (OSError, ValueError, struct.error) as e:
                    sets = {"error": f"{type(e).__name__}: {e}"}
            self._json({"card": str(p.card_file) if p.card_file else None,
                        "mode": "persistent" if p.card_persistent else "fresh",
                        "sidecar": str(sidecar_path(p.card_file)) if p.card_persistent and p.card_file else None,
                        "meta": p.card_meta, "project": p.project, "rw": p.card_rw,
                        "flush": p.card_flush_note, "ejected": p.card_ejected, "mount": p.card_mount,
                        "pool": str(p.pool.path) if p.pool else None,
                        "audio": p.card_files, "removals": sorted(p.card_removals), "sets": sets,
                        "busy": p.card_busy, "phase": p.phase})
        elif path == "/card/eject":
            ok, res = p.eject_card(open_finder=args.get("open", "1") != "0")
            self._json({"ok": ok, "phase": res, "mount": p.card_mount} if ok
                       else {"ok": False, "error": res, "phase": p.phase, "mount": p.card_mount})
        elif path == "/card/insert":
            ok, res = p.insert_card()
            self._json({"ok": ok, "phase": res} if ok else {"ok": False, "error": res, "phase": p.phase})
        elif path.startswith("/audio"):
            self._audio(path, args)
        elif path == "/peek":
            # read-only memory, either backend (Unicorn / the port's peek): what a
            # record holds right now, e.g. the popup slot 0x460d175c
            addr, n = int(args.get("addr", "0"), 0), min(int(args.get("len", "4"), 0), 4096)
            ok, res = p.do(lambda rt: bytes(rt.uc.mem_read(addr, n)).hex(), timeout=30)
            self._json({"ok": ok, "addr": f"{addr:#x}", "hex": res if ok else None, "result": None if ok else res})
        elif path == "/rtstatus":
            # O17: the port child's `rtstatus` line (the DSP workers' MIPS, waits, edges, faults)
            if p.proc is None:
                self._json({"ok": False, "result": "no port child"})
            else:
                ok, st = p.do(lambda rt: rt.proc.command("rtstatus", "rtstatus"), timeout=30)
                self._json({"ok": ok, "rtstatus": st if ok else None, "result": None if ok else st, "sound_rt": p.sound_rt})
        elif path == "/port":
            # the port child itself: argv, pid, its own status line, the tail of its report
            if p.proc is None:
                self._json({"ok": False, "result": "no port child"})
            else:
                ok, st = p.do(lambda rt: rt.status(), timeout=30)
                self._json({"ok": ok, "status": st if ok else None, "result": None if ok else st,
                            "pid": p.proc.proc.pid, "alive": p.proc.alive(), "argv": p.proc.argv,
                            "commands": p.proc.commands, "restarts": p.restarts,
                            "log_tail": list(p.proc.log)[-12:]})
        elif path == "/keys":
            self._json({"table": f"0x{KEY_TABLE:08x}",
                        "handlers": [f"0x{h:08x}" for h in p.handlers],
                        "rec": IDX_REC, "play": IDX_PLAY, "stop": IDX_STOP})
        elif path == "/key":
            ok, res = p.key(int(args.get("row", "-1"), 0), int(args.get("bit", "-1")),
                            args.get("down", "1") == "1")
            self._json({"ok": ok, "result": str(res)})
        elif path == "/knob":
            ok, res = p.knob(int(args.get("row", "-1"), 0), int(args.get("delta", "0")))
            self._json({"ok": ok, "result": str(res)})
        elif path == "/knob/reset":
            # the parameter this encoder edits on the CURRENT page back to its
            # init value, through the firmware (detent reports): the page's
            # double-click. ok:false + note where the page is not mapped.
            ok, res = p.knob_reset(int(args.get("row", "-1"), 0))
            self._json({"ok": ok, **res})
        elif path == "/knob/press":
            # the encoder's push switch (matrix row 0x27, bit = encoder index):
            # down, ?hold= ms (60), up. With a TRIG key held (/key or the page's
            # latched chord) in GRID RECORDING it toggles that step's lock on
            # the parameter the encoder edits -- the unit's [TRIG] + knob press.
            ok, res = p.knob_press(int(args.get("row", "-1"), 0), hold=float(args.get("hold", "60")))
            self._json({"ok": ok, **res})
        elif path == "/xfader":
            # the crossfader: ?pos=0..127 (0 = scene A / left, 127 = scene B /
            # right, = MIDI CC 48) sends the panel's fader report; without
            # pos it only reads the firmware's value
            pos = args.get("pos")
            ok, res = p.xfader(None if pos is None else int(pos))
            self._json({"ok": ok, **res})
        elif path == "/midi":
            # MIDI bytes into the unit's MIDI IN (UART0): ?hex=b04464 (port backend)
            hx = args.get("hex", "")
            if p.proc is None or not hx or len(hx) % 2:
                self._json({"ok": False, "result": "needs the port backend and ?hex=<even-length hex>"})
            else:
                line = "midi " + " ".join(hx[i:i + 2] for i in range(0, len(hx), 2))
                ok, res = p.do(lambda rt: rt.proc.command(line, "ok"), timeout=30)
                self._json({"ok": ok, "result": str(res)})
        elif path == "/tap":
            # n presses of one key inside one action (the double-tap chords:
            # /tap?row=0x22&bit=0&n=2 opens track 1's sample slot list)
            ok, res = p.tap(int(args.get("row", "-1"), 0), int(args.get("bit", "-1")),
                            n=int(args.get("n", "1")), hold=float(args.get("hold", "50")),
                            gap=float(args.get("gap", "150")))
            self._json({"ok": ok, "result": str(res)})
        elif path == "/map":
            # the identified panel map (keys, knobs, leds): tools/panel/key_map.json
            # plus "model": "mkii" | "mki", the model the child runs as
            mp = pathlib.Path(__file__).parent / "key_map.json"
            m = json.loads(mp.read_bytes()) if mp.exists() else {}
            m["model"] = Handler.model
            self._send(200, json.dumps(m).encode(), "application/json")
        elif path == "/transport":
            ok, res = p.transport(args.get("k", ""))
            self._json({"ok": ok, "result": str(res)})
        elif path == "/poke_trig":
            ok, res = p.poke_trig(args.get("step", "1"))
            self._json({"ok": ok, "result": str(res)})
        elif path == "/project":
            self._json({"project": p.project, "loaded": p.loaded})
        elif path == "/stack":
            # where is the emulator thread right now? (a hung action shows here)
            import traceback
            frames = sys._current_frames()
            dump = {}
            for th in threading.enumerate():
                f = frames.get(th.ident)
                if f is not None and th is not threading.current_thread():
                    dump[th.name] = "".join(traceback.format_stack(f)[-12:])
            self._send(200, "\n\n".join(f"== {k}\n{v}" for k, v in dump.items()).encode(), "text/plain")
        elif path == "/leds":
            # "bits": one byte per LED bitmap row (rows 0..16 of the 0x2r /
            # 0xa0+r messages, decoded by panel_link) -- key_map.json's leds
            # are [row, bit] into exactly this. "ids": the 0x3n <id> level
            # nibbles. Without panel_link the old naive parser's bytes remain.
            self._json(p.led_payload())
        elif path == "/leds/stream":
            # Server-sent events: one `data:` line per LED CHANGE, checked
            # every 20 ms. The page used to fetch /leds behind its 350 ms
            # status poll and missed two of every three 125 ms steps of the
            # running light (13 Sep 2026); pushed changes show every step.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last, quiet = None, 0.0
            try:
                while True:
                    cur = json.dumps(p.led_payload(), separators=(",", ":"))
                    if cur != last:
                        self.wfile.write(f"data: {cur}\n\n".encode()); self.wfile.flush()
                        last, quiet = cur, 0.0
                    else:
                        quiet += 0.02
                        if quiet >= 5.0:                 # keepalive: a comment line
                            self.wfile.write(b": ping\n\n"); self.wfile.flush(); quiet = 0.0
                    time.sleep(0.02)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
        elif path == "/run":
            # sliced, wall-bounded (run_ms): a plain rt.run(ms=5000) in frame
            # mode held the emulator for minutes (12 Sep 2026)
            ms = float(args.get("ms", 100))
            ok, res = p.do(lambda rt: p.run_ms(rt, min(ms, 5000)), timeout=600)
            self._json({"ok": ok, "result": str(res)})
        else:
            self._send(404, b"?", "text/plain")


def watchdog(srv, parent_pid, idle_s):
    """Nothing left running unseen: stop the server (its finally quits the
    child) when the process that started it is gone (--parent-pid), or when
    nobody has asked it anything for idle_s seconds (--idle-timeout). An open
    page polls /status, so a panel someone is looking at never times out."""
    ppid = os.getppid()
    while True:
        time.sleep(min(1.0, idle_s / 4) if idle_s else 1.0)
        why = None
        if parent_pid:
            if parent_pid == ppid:
                gone = os.getppid() != ppid      # re-parented: no pid-reuse doubt
            else:
                try:
                    os.kill(parent_pid, 0)
                    gone = False
                except ProcessLookupError:
                    gone = True
                except PermissionError:
                    gone = False
            if gone:
                why = f"parent pid {parent_pid} is gone"
        idle = time.monotonic() - Handler.last_request
        if why is None and idle_s and idle > idle_s:
            why = f"no HTTP request for {idle:.0f} s (--idle-timeout {idle_s / 60:g} min)"
        if why:
            print(f"panel: exiting: {why}", flush=True)
            srv.shutdown()
            return


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--image", default=None,
                    help="MAIN OS image (default: out/mainos_bus.bin if built, else the raw stock image)")
    ap.add_argument("--project", default=None, help="project dir to stage onto the card")
    ap.add_argument("--set", default="OCTABAM")
    ap.add_argument("--name", default=None)
    ap.add_argument("--card", default=None, metavar="IMG",
                    help="a PERSISTENT card image (O19): booted as it is with write-back, so SAVE PROJECT on the "
                         "unit and the samples put on it survive a quit; created once from --project when missing "
                         "(a sidecar IMG.json keeps the set/project names; the pool of pending samples is IMG.pool/). "
                         "Without it: a fresh per-port image every start, as before")
    ap.add_argument("--port", type=int, default=8563)
    ap.add_argument("--midi-clock", action="store_true",
                    help="keep the project's CLOCK RECEIVE setting (default: clear it so the "
                         "sequencer runs on its own clock -- no MIDI clock ever arrives here)")
    ap.add_argument("--port-bin", default=str(PORT_BIN),
                    help="the port binary (a .py stand-in runs under this Python)")
    ap.add_argument("--port-arg", action="append", default=[],
                    help="an extra flag for the port child, repeatable (e.g. --port-arg=--dsp)")
    ap.add_argument("--audio", action="append", default=[], metavar="DIR",
                    help="seed the sample pool with every WAV/AIFF in DIR (converted when the unit "
                         "would not read it), in addition to the project's sibling AUDIO; repeatable")
    ap.add_argument("--sound", choices=("on", "off"), default="on",
                    help="on (default): the port child runs --dsp-rt (the DSP cores in real time, O17) and its main output is captured "
                         "(/audio/status, /audio/pcm, /audio.wav, takes on PLAY..STOP); an rt child that cannot start is respawned "
                         "with the lockstep --dsp (~0.2x real time while it plays; /status sound_note says so); off: no DSP cores, no sound. "
                         "--port-arg=--dsp asks for the lockstep cores explicitly; --sound off wins over it")
    ap.add_argument("--mki", action="store_true",
                    help="run the port as an MKI (no --mkii): the MKI keymap, no PROJ/PART/AED/ARR/REC3 keys. "
                         "Default: the port child runs --mkii (docs/firmware/PANEL.md)")
    ap.add_argument("--parent-pid", type=int, default=0, metavar="PID",
                    help="exit (and stop the port child) when this process is gone: a bench or app passes its own pid")
    ap.add_argument("--idle-timeout", type=float, default=60.0, metavar="MIN",
                    help="exit after this many minutes with no HTTP request (default 60; 0 = never). "
                         "An open page polls, so it only fires when nobody is looking")
    a = ap.parse_args()

    # Default to the STOCK image: out/mainos_bus.bin is whatever the last
    # build or gate left there (verify_burn leaves a probe build that never
    # reaches the UI -- a blank screen, 11 Sep 2026). Pass --image to test
    # a built remix deliberately.
    image = a.image or str(ROOT / "out/raw/section_3_MAIN_OS.bin")

    # Bind FIRST, before anything below touches the port's files: the pool
    # wipe, the staging tree and the card image are all keyed by port, and a
    # second `panel_server.py --port <busy>` (the app on 8563 up while the
    # README's default CLI is run, a relaunch over a lingering server) used
    # to wipe the running server's pool back to the fixture, rebuild its
    # staging tree and overwrite its card image, THEN exit on the bind --
    # the next respawn booted without the user's samples (verifier, 12 Sep
    # 2026: 50 pool files -> 37). Nothing is served until serve_forever.
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    except OSError as e:
        sys.exit(f"panel: port {a.port}: {e}")

    # The sample pool (SamplePool): the set's AUDIO folder the card is built
    # from, one per server port. The project's own samples seed it as they
    # were saved: project.work references them as ../AUDIO/<file>, so the
    # sibling AUDIO/ next to the project dir is the set's pool, and without
    # them every sample slot stays invalid (RTOS_FORK section 10.12) -- the
    # UI still works, the audio does not. --audio dirs go through add()
    # (converted when the unit would not read them).
    project_dir = pathlib.Path(a.project).resolve() if a.project else None
    card_path = pathlib.Path(a.card).expanduser().resolve() if a.card else None
    card_meta = {}
    if card_path is None:
        pool = SamplePool(ROOT / "out" / f"_panel_pool_{a.port}")
        if project_dir is not None:
            pool.seed(project_dir.parent / "AUDIO", convert=False)
        for d in a.audio:
            pool.seed(d, convert=True)
        # One staging tree per server port: stage_project wipes and remakes its
        # tree, and two panels started together on the shared default raced on
        # it (FileExistsError in mkdir, 12 Sep 2026). The same builder rebuilds
        # the card for /samples/commit.
        tree = ROOT / "out" / f"_panel_stage_{a.port}"
        builder = lambda: build_card(a.project, a.set, a.name, tree, pool)  # noqa: E731
        card, staged, staged_audio = builder()
        project = (a.set, staged) if a.project else None
        if a.project:
            print(f"staged {project_dir.name} as {a.set}/{staged} with {len(pool.names())} samples (pool {pool.path})")
        else:
            print(f"empty project card with {len(pool.names())} samples (pool {pool.path})")
    else:
        # O19: the persistent card. Its pool (pending additions) lives beside
        # it and is never wiped; a missing image is built once, exactly as
        # the per-port card is, from --project + its sibling AUDIO + --audio,
        # and the sidecar records the names the child boots with.
        pool = SamplePool(card_path.with_name(card_path.name + ".pool"), wipe=False)
        builder, staged_audio = None, None
        if not card_path.exists():
            seed = SamplePool(ROOT / "out" / f"_panel_pool_{a.port}")
            if project_dir is not None:
                seed.seed(project_dir.parent / "AUDIO", convert=False)
            for d in a.audio:
                seed.seed(d, convert=True)
            tree = ROOT / "out" / f"_panel_stage_{a.port}"
            card, staged, _ = build_card(a.project, a.set, a.name, tree, seed)
            card_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = card_path.with_name(card_path.name + ".tmp")
            tmp.write_bytes(card)
            tmp.replace(card_path)
            card_meta = {"set": a.set, "project": staged, "created": datetime.datetime.now().isoformat(timespec="seconds"),
                         "from_project": str(project_dir) if project_dir else None,
                         "image_bytes": len(card), "removals": [], "pool": str(pool.path)}
            sidecar_save(card_path, card_meta)
            print(f"card: created {card_path} ({len(card) >> 20} MB) from "
                  f"{project_dir.name + ' as ' if project_dir else 'an empty '}{a.set}/{staged or '-'} "
                  f"with {len(seed.names())} samples; sidecar {sidecar_path(card_path)}")
            project = (a.set, staged) if a.project else None
        else:
            # a card the previous server left ejected (mounted on the Mac):
            # never boot the child on a volume macOS is writing -- clean and
            # detach it first, as /card/insert would
            was = card_mounted_at(card_path)
            if was is not None:
                dev, mnt = was
                try:
                    gone = card_clean(mnt) if mnt else []
                    how = card_detach(dev)
                    print(f"card: {card_path} was still mounted at {mnt}: {how} ({len(gone)} macOS files removed)")
                except Exception as e:
                    sys.exit(f"panel: {card_path} is mounted at {mnt} and could not be detached ({e}); "
                             f"eject it in Finder (or `hdiutil detach {dev}`) and start again")
            card_meta = sidecar_load(card_path)
            set_name, name = card_meta.get("set"), card_meta.get("project")
            if not (set_name and name):
                set_name, name = (a.set if a.set != "OCTABAM" else None) or set_name, a.name or name
            if not (set_name and name):
                try:
                    with Fat16Image(card_path) as img:
                        sets = img.sets()
                    set_name, projects = next(((k, v) for k, v in sets.items() if v), (None, []))
                    name = projects[0] if projects else None
                    print(f"card: no sidecar; the image holds {sets}")
                except (OSError, ValueError, struct.error) as e:
                    print(f"card: {card_path} is not a readable card image ({e})")
            project = (set_name, name) if set_name and name else None
            card_meta.update({"set": set_name, "project": name, "pool": str(pool.path)})
            card_meta.setdefault("removals", [])
            sidecar_save(card_path, card_meta)
            added = []
            for d in a.audio:
                added += pool.seed(d, convert=True)
            print(f"card: booting {card_path} as it is ({project[0] + '/' + project[1] if project else 'no project'}; "
                  f"{len(pool.names())} pending in {pool.path}{', ' + str(len(added)) + ' from --audio' if added else ''})")
        card = None

    # The port: its binary must exist and know --interactive
    # (port_available builds it when missing).
    backend, card_file = "port", None
    ok, note = port_available(a.port_bin, build=True)
    if not ok:
        sys.exit(f"panel: {note}")
    note = ""
    card_rw = False
    if card_path is not None:
        # O19: the user's own image, booted as it is; write-back when the
        # binary knows the flag (an older out/emu/ot_emu boots it read-only
        # and /status card_rw says so)
        card_file = card_path
        pb = pathlib.Path(a.port_bin)
        card_rw = pb.suffix == ".py" or b"--card-rw" in pb.read_bytes()
        if not card_rw:
            note = ((note + "; ") if note else "") + \
                f"{pb} has no --card-rw (built before O19): the card is booted read-only, SAVE on the unit stays in RAM"
            print(f"panel: {note}")
    else:
        # The port reads the card from a file, one per server port so two
        # panels do not share it.
        card_file = ROOT / "out" / f"_panel_card_{a.port}.img"
        card_file.write_bytes(card)
    # Sound: --dsp is --sound's flag now. A script's --port-arg=--dsp still
    # boots the cores (and gets the capture with them); an explicit --sound
    # off drops it, and says so.
    sound = a.sound == "on"
    port_args = [x for x in a.port_arg if x != "--dsp"]
    if len(port_args) != len(a.port_arg) and not sound:
        print("panel: --sound off: --port-arg=--dsp dropped (the child runs without the DSP cores)")
    # The model: the port boots as an MKII unless --mki (the GPIO loopback,
    # the panel loader handshake and the 0x7r report: ot_emu --mkii); a
    # .py stand-in and a port binary without the flag stay MKI. /map
    # says which.
    model = "mki"
    pb = pathlib.Path(a.port_bin)
    if not a.mki and pb.suffix != ".py":
        if b"--mkii" in pb.read_bytes():
            if "--mkii" not in port_args:
                port_args.append("--mkii")
            model = "mkii"
        else:
            print(f"panel: {pb} has no --mkii (built before it landed): running as an MKI")
    Handler.model = model
    takes_dir = ROOT / "out" / f"_panel_takes_{a.port}"
    Handler.panel = Panel(image, card, project=project, internal_clock=not a.midi_clock,
                          backend=backend, port_bin=a.port_bin, port_args=port_args,
                          card_file=card_file, backend_note=note,
                          play_pump_ms=25.0,
                          pool=pool, card_builder=builder, staged_audio=staged_audio,
                          sound=sound, takes_dir=takes_dir, card_persistent=card_path is not None,
                          card_rw=card_rw, card_meta=card_meta)
    Handler.html = (pathlib.Path(__file__).parent / "panel.html").read_bytes()
    print(f"panel: http://localhost:{a.port}/   image={image}   backend={backend}   model={model}"
          f"   sound={'on' if Handler.panel.sound_wanted else 'off'} (takes in {takes_dir})"
          f"   card={card_file} ({'persistent, write-back ' + ('on' if card_rw else 'OFF') if card_path else 'fresh per port'})")

    # O19: SIGTERM (the app's quit, a kill) ends serve_forever through the
    # finally below instead of killing the interpreter outright, so the
    # child gets `card flush` + `quit` (it fsyncs before its ok) and the
    # sidecar is written. Python's default action for SIGTERM is to die at
    # once -- the app's README said so, and it was true.
    def _term(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, _term)
    if (host_nice() or 0) > 0:
        print(f"panel: running at nice {host_nice()} (a zsh `&` job: BG_NICE) -- the unit will be slower "
              f"whenever anything else wants the CPU; start the server in the foreground, or `unsetopt BG_NICE`")
    if a.parent_pid or a.idle_timeout > 0:
        threading.Thread(target=watchdog, args=(srv, a.parent_pid, a.idle_timeout * 60.0),
                         daemon=True, name="watchdog").start()
    try:
        srv.serve_forever()
    finally:
        pn = Handler.panel
        pn._close_take(None)     # a take open at exit stays a valid WAV
        if pn.output is not None:
            pn.output.stop("server exit")
        if pn.card_ejected and pn.card_mount:
            # the card stays mounted on the Mac (the user may be copying):
            # say so; the next start on it needs it detached first
            print(f"panel: exiting with the card still mounted at {pn.card_mount} -- `hdiutil detach` it before the next start")
        if pn.proc is not None:
            if pn.card_rw:
                try:
                    pn.proc.command("card flush", "card", timeout=10.0)
                except (PortDied, PortError):
                    pass
            pn.proc.quit()
        pn._save_sidecar()


if __name__ == "__main__":
    main()
