#!/usr/bin/env python3
"""Watch a unit on USB, stop at a freeze, and keep what led up to it and what followed.

    python3 tools/hw/freeze_watch.py [watch] [--trigger LIST] [--when EXPR] [--pre S] [--post S] [--audio [NAME]]
    python3 tools/hw/freeze_watch.py probe        # the handshake: what this unit answers, which triggers it arms
    python3 tools/hw/freeze_watch.py selftest     # the rules on synthetic samples; no unit

macOS, like the other tools here that read MIDI: the input is ot_midi's CoreMIDI. USB needs pyusb and a libusb
(load_meter.py's note); without them it watches MIDI only.

THE HANDSHAKE. At connect and after every restart the watcher asks the unit what it can be watched with, all of it
read-only and none of it added to the image. A request the image does not carry STALLs, as stock does; only a
STALL marks it absent, and one that times out is asked again.
  usb   GET_STATUS, any device: the ColdFire's USB code is running.
  lm    LOAD METER, 0xc0/0x57 (load_meter.py), when the image carries it: the DSP's frame count (about 2,800 a
        second whenever the frame loop runs, playing or not) and the frame interrupt's rate, the audio engine's
        own heartbeat; per-slot DSP costs go in the freeze file.
  aud   USB audio's counters, 0xc0/0x55 (usb_counters.py), any image with USB audio out: `produced` advances
        44,100 a second, but only while a host has the stream open, so it is a heartbeat only with --audio.
  midi  the unit's MIDI source: clock (CLOCK SEND on) and START / STOP (TRANSPORT SEND on).
REMOTE's PEEK (issue #978) is not in an image yet; PROBES is where it goes.

TRIGGERS (--trigger, comma-separated; default: every one the handshake arms). Each fires once and re-arms when its
signal recovers.
  clock_stall  clock stopped for --clock-timeout with no STOP after it. Armed only once a START has been seen and
               two beats of clock after it: a unit that sends START sends STOP, so a missing STOP means something.
               Without a START (TRANSPORT SEND off) a STOP pressed on the unit cannot be told from a stall, and the
               stop is logged as `clock_stopped`, not triggered.
  usb_dead     --usb-fails ticks in a row with no request answered while the device is on the bus.
  frame_stall  the frame heartbeat (lm's count, or aud's with --audio) not advancing for --frame-timeout.
  irq_low      the frame interrupt under 90 % of its 2,756 a second on two ticks in a row (lm).
  when         --when EXPR, a Python expression over this tick's sample `s` and the last one `p` (the keys
               `probe` prints), e.g. --when "s['lm_core0'] > 0.97".
NOT FREEZES, logged and watched through: the unit leaving the bus and coming back (`left`, then `reboot`; a frame
count that goes back says `restart`), not coming back (`gone`), its MIDI source going away while USB still answers
(`midi_gone`: USB DISK MODE or a USB setting), a STOP, and the host sleeping (`host_sleep`: the wall clock moved
--pause seconds further than the monotonic one, which stops while the host sleeps; the detectors restart).

THE CAPTURE. Every --every seconds every signal is sampled into a ring of the last --pre seconds. At a trigger the
watcher keeps sampling --post seconds more, then writes OUT/freeze_<time>.json: the trigger; which part stopped, read
from what the signals did after it (the sequencer alone, the audio engine, the whole unit); the handshake; the
samples before and after; the MIDI messages of the window; a full LOAD METER read at the trigger while it still
answers; and with --audio OUT/freeze_<time>.wav, the unit's first two USB channels over the last --audio-keep
seconds. Every sample and event also goes to OUT/watch_<time>.jsonl. Exit 3 after a freeze; --keep-going re-arms.

THE COST TO THE UNIT. Each tick asks what the handshake found and nothing else: LOAD METER is 2 control transfers,
USB audio's counters 1, and GET_STATUS only when neither answered, so at most 3 a tick on EP0, which the ColdFire
answers in its USB interrupt; a unit that stops answering is asked one request a tick. Finding the device on the
host's bus sends nothing to it. --audio opens the stream, which runs USB audio's producer every frame (13-25 us of
the frame interrupt per frame, measured once with the producer running and no host; modules/usb/usbaudio.s
audio_frame_shim). Not measured: what the requests cost the unit's frame interrupt.

What it cannot see: inside the unit beyond these signals (what the processor was executing, the sequencer's
state), which needs PEEK; a freeze while stopped, unless USB or the frame heartbeat dies with it; a fault that leaves
every heartbeat running.
"""
import argparse, collections, ctypes, hashlib, json, pathlib, struct, sys, threading, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import load_meter, ot_midi, usb_counters  # noqa: E402
VID, PID = 0x1935, 0x0002                 # Elektron Octatrack
CLOCK, START, CONTINUE, STOP, SENSE = 0xF8, 0xFA, 0xFB, 0xFC, 0xFE
FRAME_IRQ = 2756                          # the frame interrupt's rate (load_meter.judge)
STALL = 32                                # pyusb's errno for a request the device refused (ot_fuzz reads it so)
TRIGGERS = ("clock_stall", "usb_dead", "frame_stall", "irq_low")
NEEDS = {"clock_stall": "midi", "usb_dead": "usb", "frame_stall": "lm", "irq_low": "lm"}
FREEZE = 3                                # exit status on a freeze
NAMES = ("octatrack", "elektron")         # a MIDI source whose name holds one of these


class Clock:
    """MIDI clock and transport, fed packet by packet from CoreMIDI's threads."""

    def __init__(self, timeout=1.0, min_clocks=48):
        self.timeout, self.min_clocks = timeout, min_clocks
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.last_clock = self.last_stop = None
            self.started = False          # a START or CONTINUE seen since the reset
            self.since_start = 0          # clocks since it (or since the reset)
            self.window, self.max_gap = [], 0.0

    def midi(self, t, data):
        """-> the packet without its real-time bytes (clock, start/stop, active sensing), for the log."""
        rest = bytearray()
        with self.lock:
            for b in data:
                if b == CLOCK:
                    if self.last_clock is not None:
                        self.max_gap = max(self.max_gap, t - self.last_clock)
                    self.last_clock = t
                    self.since_start += 1
                    self.window.append(t)
                elif b in (START, CONTINUE):
                    self.since_start, self.last_stop, self.started = 0, None, True
                elif b == STOP:
                    self.last_stop = t
                if b not in (CLOCK, SENSE):
                    rest.append(b)
        return bytes(rest)

    def take(self):
        """-> the clocks since the last take, their tempo and the longest gap."""
        with self.lock:
            w, self.window = self.window, []
            gap, self.max_gap = self.max_gap, 0.0
        bpm = 60 * (len(w) - 1) / (24 * (w[-1] - w[0])) if len(w) > 2 and w[-1] > w[0] else None
        return {"clocks": len(w), "bpm": round(bpm, 2) if bpm else None, "max_gap_ms": round(1000 * gap, 1)}

    def silent(self, t):
        """Clock ran two beats and has been silent for the timeout, with no STOP after it."""
        with self.lock:
            if self.last_clock is None or self.since_start < self.min_clocks:
                return False
            if self.last_stop is not None and self.last_stop >= self.last_clock:
                return False
            return t - self.last_clock > self.timeout


class Watch:
    """The rules. tick() takes one sample (a dict, the keys `probe` prints) and returns
    [(kind, name, why)], kind 'trigger' or 'event'. Pure: the selftest drives it with synthetic time."""

    def __init__(self, triggers=TRIGGERS, clock_timeout=1.0, usb_fails=3, frame_timeout=1.5, when=None,
                 pause=5.0, gone_after=60.0):
        self.triggers = set(triggers) | ({"when"} if when else set())
        self.clock = Clock(clock_timeout)
        self.usb_fails, self.frame_timeout, self.when = usb_fails, frame_timeout, when
        self.pause, self.gone_after = pause, gone_after
        self.prev, self.present, self.left, self.gone_said, self.midi_was = None, None, None, False, None
        self.reset()

    def reset(self):
        """After a restart or the host sleeping: nothing carried over from before."""
        self.clock.reset()
        self.fails, self.hb, self.hb_said, self.irq_low, self.clock_said, self.when_said = 0, None, False, 0, False, False

    def midi(self, t, data):
        return self.clock.midi(t, data)

    def tick(self, t, s):
        self.ev, p, self.prev = [], self.prev, s
        self._sleep(t, s, p)
        if self._presence(t, s):
            for check in (self._usb, self._heartbeat, self._irq, self._clock):
                check(t, s)
            self._when(s, p)
        return self.ev

    def _event(self, name, why):
        self.ev.append(("event", name, why))

    def _trigger(self, name, why):
        if name in self.triggers:
            self.ev.append(("trigger", name, why))

    def _sleep(self, t, s, p):
        if p is not None and "wall" in s and "wall" in p and (s["wall"] - p["wall"]) - (t - p["t"]) > self.pause:
            self._event("host_sleep", f"the host slept {s['wall'] - p['wall'] - (t - p['t']):.0f} s; detectors restarted")
            self.reset()

    def _presence(self, t, s):
        """Arrivals and departures -> whether the unit is there to be checked. Without USB the MIDI source
        stands for it."""
        present = s.get("present")
        if present is None:
            present = s.get("midi_src")
        if self.present and present is False:
            self.left, self.gone_said = t, False
            self._event("left", "the unit left the bus (a restart, power or the cable)")
        elif present and self.present is False and self.left is not None:
            self._event("reboot", f"the unit came back after {t - self.left:.1f} s: a restart, not a freeze")
            self.left = None
            self.reset()
        elif present is False and self.left is not None and not self.gone_said and t - self.left > self.gone_after:
            self.gone_said = True
            self._event("gone", f"the unit has been away {t - self.left:.0f} s (powered off or unplugged)")
        if present is not None:
            self.present = present
        if present and s.get("present") and s.get("midi_src") is False and self.midi_was:
            self._event("midi_gone", "the MIDI source went away while USB answers (USB DISK MODE, a USB setting)")
        if present:
            self.midi_was = s.get("midi_src")
        return bool(present)

    def _usb(self, t, s):
        if s.get("usb") == "fail":
            self.fails += 1
            if self.fails == self.usb_fails:
                self._trigger("usb_dead", f"{self.fails} ticks with no USB request answered: the main processor "
                                          f"stopped serving USB")
        elif s.get("usb") == "ok":
            self.fails = 0

    def _heartbeat(self, t, s):
        hb = s.get("lm_seq")
        if hb is None and s.get("audio_open"):
            hb = s.get("aud_produced")
        if hb is None:
            return
        if self.hb is not None and hb < self.hb[0]:
            self._event("restart", "the frame count went back: the unit restarted")
            self.reset()
        if self.hb is None or hb != self.hb[0]:
            self.hb, self.hb_said = (hb, t), False
        elif t - self.hb[1] > self.frame_timeout and not self.hb_said:
            self.hb_said = True
            self._trigger("frame_stall", f"the frame count has not moved for {t - self.hb[1]:.2f} s: the audio "
                                         f"engine stopped")

    def _irq(self, t, s):
        irq = s.get("lm_irq")
        if irq is None:
            return
        self.irq_low = self.irq_low + 1 if irq < 0.9 * FRAME_IRQ else 0
        if self.irq_low == 2:
            self._trigger("irq_low", f"the frame interrupt runs {irq:.0f} a second (nominal {FRAME_IRQ})")

    def _clock(self, t, s):
        c = self.clock
        if c.silent(t):
            if not self.clock_said:
                self.clock_said = True
                if c.started:
                    self._trigger("clock_stall", f"MIDI clock stopped for over {c.timeout} s with no STOP: the "
                                                 f"sequencer stalled")
                else:
                    self._event("clock_stopped", "clock stopped and no START was seen: a STOP with TRANSPORT SEND "
                                                 "off, or a stall; not told apart")
        elif c.last_clock is not None and t - c.last_clock <= c.timeout:
            self.clock_said = False

    def _when(self, s, p):
        if not self.when or self.when_said:
            return
        try:
            hit = bool(eval(self.when, {"__builtins__": {}}, {"s": s, "p": p or {}}))  # noqa: S307
        except Exception:  # noqa: BLE001 -- a key this tick lacks is not a trigger
            hit = False
        if hit:
            self.when_said = True
            self._trigger("when", f"--when {self.when}")


def heartbeat(x):
    return x.get("lm_seq") if x.get("lm_seq") is not None else x.get("aud_produced") if x.get("audio_open") else None


def classify(name, post):
    """What the signals did after the trigger -> one line: which part of the unit stopped."""
    there = [x for x in post if x.get("present") or (x.get("present") is None and x.get("midi_src") is not False)]
    if len(there) < len(post):
        return "the unit left the bus after the trigger (restarted by hand?)"
    usb = [x["usb"] for x in there if x.get("usb")]
    hb = [v for v in map(heartbeat, there) if v is not None]
    moving = len(set(hb)) > 1 if len(hb) > 1 else None
    if usb and "ok" not in usb:
        return "the whole unit: USB stopped answering"
    if moving is False:
        return "the audio engine: its frame heartbeat stopped, USB kept answering"
    engine = "; the frame heartbeat kept running" if moving else ""
    if name == "clock_stall":
        return "the sequencer: clock stopped" + (", USB kept answering" if usb else " (USB not watched)") + engine
    return f"{name}: USB {'kept answering' if usb else 'not watched'}" + engine


def _lm_keys(r):
    return {"lm_seq": r["dsp"]["seq"], "lm_irq": r["cf"]["irq_per_s"], "lm_cf_share": round(r["cf"]["share"], 4),
            "lm_cf_longest_us": round(r["cf"]["longest_us"], 1), "lm_bad": r["dsp"]["bad"],
            "lm_core0": round(load_meter.ratio(r["dsp"]["core0"]) or 0.0, 4),
            "lm_core1": round(load_meter.ratio(r["dsp"]["core1"]) or 0.0, 4)}


# name -> (read the request from a device, the sample keys from its reply). A request the image lacks raises STALL.
PROBES = {
    "lm": (load_meter.read_fast, _lm_keys),
    "aud": (usb_counters.read,
            lambda r: {"aud_produced": r["produced"], "aud_consumed": r["consumed"], "aud_underruns": r["underruns"]}),
}


class Unit:
    """The USB side: presence, liveness and the requests the handshake found. Inert without pyusb or libusb."""

    def __init__(self):
        try:
            import usb.core               # optional: without it the watcher has MIDI only
            self.core, self.backend = usb.core, load_meter.libusb_backend()
        except ImportError:
            self.core = self.backend = None
        self.dev, self.found = None, {}

    @property
    def available(self):
        return self.core is not None and self.backend is not None

    def find(self):
        return self.core.find(idVendor=VID, idProduct=PID, backend=self.backend) if self.available else None

    def handshake(self):
        """-> {probe: True, False or None}: False only for a STALL; None, asked again each sample, for a timeout."""
        self.dev = self.find()
        self.found = {"usb": self.dev is not None}
        for name, (read, _) in PROBES.items():
            try:
                read(self.dev)
                self.found[name] = True
            except Exception as e:  # noqa: BLE001
                self.found[name] = False if self.dev is None or getattr(e, "errno", None) == STALL else None
        return self.found

    def sample(self):
        """-> this tick's USB keys. The probes are asked first; any answer says USB is alive, and GET_STATUS is
        sent only when none did. The first request that times out ends the tick's asking."""
        if not self.available:
            return {"present": None}
        if self.find() is None:
            self.dev = None
            return {"present": False}
        if self.dev is None:
            self.dev = self.find()
        s = {"present": True, "usb": "fail", "usb_ms": None}
        for name, (read, keys) in PROBES.items():
            if self.found.get(name) is False:
                continue
            t = time.monotonic()
            try:
                r = read(self.dev)
            except Exception as e:  # noqa: BLE001
                if getattr(e, "errno", None) != STALL:
                    s[f"{name}_error"] = repr(e)
                    return s
                if not self.found.get(name):
                    self.found[name] = False
                continue
            s.update(keys(r), usb="ok", usb_ms=s["usb_ms"] or round(1000 * (time.monotonic() - t), 1))
            self.found[name] = True
        if s["usb"] != "ok":
            t = time.monotonic()
            try:
                self.dev.ctrl_transfer(0x80, 0x00, 0, 0, 2, timeout=500)
                s.update(usb="ok", usb_ms=round(1000 * (time.monotonic() - t), 1))
            except self.core.USBError:
                pass
        return s


class Audio:
    """The unit's USB audio in a ring (--audio): its first two channels and an rms a tick. Opening the stream
    starts the unit's producer, the heartbeat aud reads."""

    def __init__(self, name, keep):
        import numpy as np                # optional, with sounddevice: only --audio needs them
        import sounddevice as sd
        import ot_stimuli, usb_transport_probe
        self.np, self.keep, self.write_wav = np, keep, ot_stimuli.write_wav
        dev, nch = usb_transport_probe.find_input(name)
        self.blocks, self.sq, self.n = collections.deque(), 0.0, 0
        self.lock = threading.Lock()      # the callback runs on the audio thread

        def cb(indata, frames, t, status):
            x = indata[:, :2].copy()
            with self.lock:
                self.blocks.append((time.monotonic(), x))
                self.sq += float(np.sum(x.astype(np.float64) ** 2))
                self.n += x.size
                while self.blocks[-1][0] - self.blocks[0][0] > self.keep:
                    self.blocks.popleft()
        self.stream = sd.InputStream(device=dev, channels=nch, samplerate=44100, dtype="float32", callback=cb)
        self.stream.start()

    def rms_db(self):
        with self.lock:
            sq, n, self.sq, self.n = self.sq, self.n, 0.0, 0
        return round(float(20 * self.np.log10(max((sq / n) ** 0.5, 1e-12))), 1) if n else None

    def write(self, path):
        with self.lock:
            snap = [b for _, b in self.blocks]
        if snap:
            x = self.np.concatenate(snap)
            self.write_wav(path, (self.np.clip(x, -1, 1) * (2 ** 23 - 1)).astype(self.np.int32))
        return bool(snap)


def source_name(want):
    names = [n for n, _ in ot_midi.endpoints("src")]
    keys = (want.lower(),) if want else NAMES
    return next((n for n in names if any(k in n.lower() for k in keys)), None)


def armed(found, chosen, audio=False):
    """The triggers the handshake supports, of those asked for; aud is a heartbeat only with --audio."""
    on = [t for t in chosen if found.get(NEEDS[t], False)]
    if audio and found.get("aud") and "frame_stall" in chosen and "frame_stall" not in on:
        on.append("frame_stall")
    return on


class Session:
    """One watch: the log, the ring before a trigger, the MIDI connection, the capture after it."""

    def __init__(self, a):
        self.a = a
        self.out = pathlib.Path(a.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.path = self.out / f"watch_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
        self.log_f = self.path.open("a", buffering=1)
        self.chosen = [x for x in a.trigger.split(",") if x] if a.trigger else list(TRIGGERS)
        bad = [x for x in self.chosen if x not in TRIGGERS]
        if bad:
            sys.exit(f"unknown trigger(s) {bad}; have {', '.join(TRIGGERS)} (and --when)")
        self.unit = Unit()
        self.audio = Audio(a.audio, a.audio_keep) if a.audio else None
        self.image = None
        if a.image:
            p = pathlib.Path(a.image)
            self.image = {"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        self.watch = Watch(self.chosen, a.clock_timeout, a.usb_fails, a.frame_timeout, a.when, a.pause)
        self.ring = collections.deque(maxlen=max(1, int(a.pre / a.every)))
        self.msgs = collections.deque()
        self.inp, self.retired = None, []     # closed inputs stay referenced: CoreMIDI holds their callbacks
        self.t0, self.found = time.monotonic(), {}

    def log(self, rec):
        rec = {"s": round(time.monotonic() - self.t0, 2), **rec}
        self.log_f.write(json.dumps(rec) + "\n")
        return rec

    def say(self, line):
        print(f"{time.strftime('%H:%M:%S')}  {line}", flush=True)

    def on_bytes(self, data):
        rest = self.watch.midi(time.monotonic(), data)
        if rest:
            self.msgs.append((time.monotonic(), rest.hex(" ")))
            self.log({"event": "midi", "hex": rest.hex(" ")})

    def arm(self, found, why):
        self.found = found
        self.watch.triggers = set(armed(found, self.chosen, bool(self.audio))) | ({"when"} if self.a.when else set())
        self.log({"event": why, "found": found, "armed": sorted(self.watch.triggers)})
        self.say(f"{why}: {', '.join(k for k, v in found.items() if v) or 'nothing'}; "
                 f"armed: {', '.join(sorted(self.watch.triggers)) or 'nothing yet'}")

    def handshake(self):
        self.arm({**self.unit.handshake(), "midi": source_name(self.a.port) is not None}, "handshake")

    def connect(self):
        """The MIDI input follows the source; a unit found after the start gets its handshake. -> the source."""
        src = source_name(self.a.port)
        if self.inp is None and src:
            self.inp = ot_midi.In(src, self.on_bytes)
            self.log({"event": "midi_open", "port": src})
            if not self.found.get("midi"):
                self.handshake()
        elif self.inp is not None and not src:
            self.inp.close()
            self.retired.append(self.inp)
            self.inp = None
        if self.unit.available and not self.found.get("usb") and self.unit.find() is not None:
            self.handshake()
        return src

    def sample(self, src):
        t_end = time.monotonic() + self.a.every
        while time.monotonic() < t_end:
            ot_midi.In.pump(min(0.05, self.a.every))
        s = {"t": round(time.monotonic(), 3), "wall": round(time.time(), 3), **self.unit.sample(),
             "midi_src": src is not None, **self.watch.clock.take()}
        if self.audio:
            s.update(audio_open=True, rms_db=self.audio.rms_db())
        if any(self.unit.found.get(k) != self.found.get(k) for k in PROBES):
            self.arm({**self.found, **self.unit.found}, "rearm")
        return self.log({"event": "sample", **s})

    def events(self, s):
        """Log and print the tick's events -> its triggers."""
        trig = []
        for kind, name, why in self.watch.tick(s["t"], s):
            self.log({"event": kind, "name": name, "why": why})
            if kind == "trigger":
                trig.append((name, why))
                continue
            self.say(f"{name}: {why}")
            if name in ("reboot", "restart"):
                self.handshake()
        return trig

    def capture(self, name, why):
        """--post seconds more, then the freeze file."""
        print(f"\n*** {name}: {why}\n    sampling {self.a.post:g} s more ...", flush=True)
        lm_at = None
        if self.found.get("lm") and self.unit.dev is not None:
            try:
                lm_at = load_meter.read(self.unit.dev)
            except Exception as e:  # noqa: BLE001
                lm_at = {"error": repr(e)}
        post, t_end = [], time.monotonic() + self.a.post
        while time.monotonic() < t_end:
            post.append(self.sample(source_name(self.a.port)))
            self.events(post[-1])                 # a restart by hand during the window is logged
        kind = classify(name, post)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        dump, wav = self.out / f"freeze_{stamp}.json", self.out / f"freeze_{stamp}.wav"
        wav = str(wav) if self.audio and self.audio.write(wav) else None
        rec = self.log({"event": "FREEZE", "trigger": name, "why": why, "kind": kind})
        dump.write_text(json.dumps({
            "freeze": rec, "image": self.image, "handshake": self.found, "armed": sorted(self.watch.triggers),
            "settings": {k: v for k, v in vars(self.a).items() if k != "cmd"}, "lm_at_trigger": lm_at,
            "pre": list(self.ring), "post": post, "wav": wav,
            "midi": [{"t": round(t, 3), "hex": h} for t, h in self.msgs]}, indent=1, default=str))
        print(f"*** FREEZE ({name}): {kind}\n    {dump}" + (f"\n    {wav}" if wav else "")
              + f"\n    log: {self.path}\n    if the screen shows EXCEPTION, photograph it before touching the unit",
              flush=True)

    def run(self):
        self.log({"event": "watch_start", "image": self.image, "usb": self.unit.available, "audio": self.a.audio})
        print(f"logging to {self.path}" + ("" if self.unit.available else
              "\nUSB off: no pyusb or no libusb (.venv/bin/pip install pyusb libusb-package); MIDI only"), flush=True)
        self.handshake()
        last_line = 0.0
        while True:
            s = self.sample(self.connect())
            self.ring.append(s)
            while self.msgs and self.msgs[0][0] < time.monotonic() - self.a.pre - self.a.post:
                self.msgs.popleft()
            for name, why in self.events(s):
                self.capture(name, why)
                if not self.a.keep_going:
                    return FREEZE
                self.ring.clear()             # each trigger re-arms when its own signal recovers
            if s["t"] - last_line >= 10:
                last_line = s["t"]
                self.say(f"clocks {s['clocks']:3d}  bpm {s['bpm']}  usb {s.get('usb')} {s.get('usb_ms')} ms"
                         + (f"  dsp {s['lm_seq']}" if "lm_seq" in s else "")
                         + (f"  rms {s['rms_db']} dB" if self.audio else ""))

    def close(self):
        self.log_f.close()
        if self.audio:
            self.audio.stream.stop()


def cmd_watch(a):
    session = Session(a)
    try:
        return session.run()
    except KeyboardInterrupt:
        session.log({"event": "stopped_by_user"})
        print(f"\nstopped; log at {session.path}")
        return 0
    finally:
        session.close()


def cmd_probe(a):
    u = Unit()
    print("MIDI sources:", [n for n, _ in ot_midi.endpoints("src")] or "none")
    src = source_name(a.port)
    if not u.available:
        print("USB: no pyusb or no libusb (.venv/bin/pip install pyusb libusb-package): MIDI only")
    found = {**u.handshake(), "midi": src is not None}
    for name, what in (("usb", "GET_STATUS"), ("lm", "LOAD METER 0xc0/0x57"), ("aud", "USB audio counters 0xc0/0x55"),
                       ("midi", f"MIDI source {src!r}")):
        print(f"  {name:4s} {'yes' if found.get(name) else 'no ':3s}  {what}")
    print("triggers armed:", ", ".join(armed(found, TRIGGERS)) or "none",
          "(frame_stall from aud needs --audio)" if found.get("aud") and not found.get("lm") else "")
    if found.get("usb"):
        print("sample keys:", ", ".join(sorted({"t", "wall", "present", "usb", "usb_ms", "midi_src", "clocks", "bpm",
                                                 "max_gap_ms", "audio_open", "rms_db", *u.sample()})))
    return 0


def cmd_selftest(_a):
    fails = []

    def expect(what, got, want):
        ok = got == want
        print(f"  [{'ok' if ok else 'FAIL'}] {what}: {got!r}")
        if not ok:
            fails.append(what)

    def drive(events, until, step=0.25, s_at=lambda t: {}, **kw):
        """MIDI events (t, bytes) and a sample per tick -> [(t, kind, name)] from Watch."""
        wch, ev, t, got = Watch(**kw), sorted(events, key=lambda e: e[0]), 0.0, []
        while t <= until:
            while ev and ev[0][0] <= t:
                wch.midi(*ev.pop(0))
            s = {"t": t, "wall": t, "present": True, "usb": "ok", "midi_src": True, **s_at(t)}
            got += [(round(t, 2), k, n) for k, n, _ in wch.tick(t, s)]
            t = round(t + step, 6)
        return got

    def clocks(t0, seconds, bpm=120):
        return [(t0 + i * 60 / (bpm * 24), bytes([CLOCK])) for i in range(int(seconds * bpm * 24 / 60))]

    def names(got, kind=None):
        return [n for _, k, n in got if kind is None or k == kind]

    play = [(0.0, bytes([START]))] + clocks(0.01, 3.0)
    got = drive(play, 10)
    expect("START, clock, silence: one clock_stall about the timeout after the last clock",
           [(t, n) for t, k, n in got], [(4.0, "clock_stall")])
    expect("START, clock, STOP: nothing", drive(play + [(3.02, bytes([STOP]))], 10), [])
    expect("under two beats of clock, then nothing: nothing", drive([(0.0, bytes([START]))] + clocks(0.01, 0.4), 10), [])
    expect("a minute of clock: nothing", drive([(0.0, bytes([START]))] + clocks(0.01, 60.0), 60), [])
    expect("clock with no START seen, then silence: an event, not a trigger",
           [(k, n) for _, k, n in drive(clocks(0.0, 3.0), 10)], [("event", "clock_stopped")])
    expect("STOP, START, clock, silence: a stall",
           names(drive(play + [(3.02, bytes([STOP])), (4.0, bytes([START]))] + clocks(4.01, 3.0), 12), "trigger"),
           ["clock_stall"])
    expect("a stall, the clock back, a second stall: two triggers",
           names(drive(play + clocks(6.0, 3.0), 14), "trigger"), ["clock_stall", "clock_stall"])
    expect("clock_stall not chosen: nothing", drive(play, 10, triggers=("usb_dead",)), [])

    expect("three unanswered USB requests: one usb_dead",
           names(drive([], 5, s_at=lambda t: {"usb": "fail" if 1 <= t < 3 else "ok"}), "trigger"), ["usb_dead"])
    expect("USB unanswered for 8 s: one usb_dead, not one a tick (--keep-going)",
           names(drive([], 10, s_at=lambda t: {"usb": "fail" if t >= 1 else "ok"}), "trigger"), ["usb_dead"])
    expect("unanswered, answering again, unanswered: two",
           names(drive([], 10, s_at=lambda t: {"usb": "fail" if 1 <= t < 3 or t >= 6 else "ok"}), "trigger"),
           ["usb_dead", "usb_dead"])
    expect("the frame count still for 8 s: one frame_stall",
           names(drive([], 10, s_at=lambda t: {"lm_seq": int(2800 * min(t, 1.0))}), "trigger"), ["frame_stall"])
    expect("two unanswered, an answer, two more: nothing",
           drive([], 5, s_at=lambda t: {"usb": "fail" if t in (1.0, 1.25, 2.0, 2.25) else "ok"}), [])
    expect("the frame count still: one frame_stall after the timeout",
           [(t, n) for t, k, n in drive([], 5, s_at=lambda t: {"lm_seq": int(2800 * min(t, 2.0))})], [(3.75, "frame_stall")])
    expect("the frame count moving: nothing", drive([], 5, s_at=lambda t: {"lm_seq": int(2800 * t)}), [])
    expect("aud's count stopped, stream not opened by the watcher: not a heartbeat",
           drive([], 5, s_at=lambda t: {"aud_produced": 1000}), [])
    expect("aud's count stopped with --audio: frame_stall",
           names(drive([], 5, s_at=lambda t: {"aud_produced": int(44100 * min(t, 1.0)), "audio_open": True})),
           ["frame_stall"])
    expect("the frame count going back: a restart, not a stall",
           names(drive([], 5, s_at=lambda t: {"lm_seq": int(2800 * (t if t < 2 else t - 2))})), ["restart"])
    expect("the interrupt low on two ticks: irq_low",
           names(drive([], 3, s_at=lambda t: {"lm_seq": int(2800 * t), "lm_irq": 1200 if t >= 2 else 2756})),
           ["irq_low"])
    expect("the interrupt low on one tick: nothing",
           drive([], 3, s_at=lambda t: {"lm_seq": int(2800 * t), "lm_irq": 1200 if t == 2.0 else 2756}), [])

    expect("off the bus 8 s and back: left, then reboot; no trigger, even with clock cut off",
           [(k, n) for _, k, n in drive(play, 14, s_at=lambda t: {"present": not 3.5 <= t < 11.5})],
           [("event", "left"), ("event", "reboot")])
    expect("off the bus for good: left, then gone",
           names(drive([], 70, s_at=lambda t: {"present": t < 2})), ["left", "gone"])
    expect("no USB library: the MIDI source leaving and coming back is the reboot",
           names(drive([], 12, s_at=lambda t: {"present": None, "midi_src": not 2 <= t < 8})), ["left", "reboot"])
    expect("the MIDI source gone while USB answers: midi_gone, no trigger",
           [(k, n) for _, k, n in drive([], 4, s_at=lambda t: {"midi_src": t < 2})], [("event", "midi_gone")])
    wch = Watch()
    wch.midi(0.0, bytes([START]))
    for t, b in clocks(0.01, 3.0):
        wch.midi(t, b)
    wch.tick(2.9, {"t": 2.9, "wall": 2.9, "present": True, "usb": "ok"})
    expect("the wall clock 20 s ahead of the monotonic one (the host slept): host_sleep, no stall",
           [(k, n) for k, n, _ in wch.tick(3.0, {"t": 3.0, "wall": 23.0, "present": True, "usb": "ok"})],
           [("event", "host_sleep")])
    wch = Watch(usb_fails=3)
    for t in (1.0, 4.0, 7.0):                    # USB requests timing out make each tick late, not the host
        got = wch.tick(t, {"t": t, "wall": t, "present": True, "usb": "fail"})
    expect("ticks 3 s apart because requests time out: still usb_dead, not host_sleep", got,
           [("trigger", "usb_dead", "3 ticks with no USB request answered: the main processor stopped serving USB")])
    expect("--when on a sample key: one trigger",
           [(t, n) for t, k, n in drive([], 4, s_at=lambda t: {"lm_core0": 0.99 if t >= 2 else 0.5},
                                        when="s['lm_core0'] > 0.97")], [(2.0, "when")])
    expect("--when naming a key a sample lacks: nothing", drive([], 2, when="s['nope'] > 1"), [])

    ok = {"present": True, "usb": "ok"}
    expect("classify: USB dead after", classify("clock_stall", [{**ok, "usb": "fail"}] * 3),
           "the whole unit: USB stopped answering")
    expect("classify: USB alive, frame count still", classify("clock_stall", [{**ok, "lm_seq": 5}] * 3),
           "the audio engine: its frame heartbeat stopped, USB kept answering")
    expect("classify: USB alive, frame count moving",
           classify("clock_stall", [{**ok, "lm_seq": i} for i in range(3)]),
           "the sequencer: clock stopped, USB kept answering; the frame heartbeat kept running")
    expect("classify: MIDI only", classify("clock_stall", [{"present": None}] * 3),
           "the sequencer: clock stopped (USB not watched)")
    expect("classify: the unit left during the post window", classify("usb_dead", [ok, {"present": False}]),
           "the unit left the bus after the trigger (restarted by hand?)")


    class Err(Exception):
        def __init__(self, errno):
            super().__init__(errno)
            self.errno = errno                   # pyusb's USBError carries it: 32 a STALL, 60 a timeout

    class Dev:                                       # an image with USB audio and no LOAD METER
        answers, asked = True, 0

        def ctrl_transfer(self, bm, req, wv, wi, n, timeout=None):
            self.asked += 1
            if not self.answers:
                raise Err(60)
            if bm == 0x80:
                return bytes(2)
            if (bm, req) == (0xc0, 0x55):
                return struct.pack(">15i", *range(100, 115))
            raise Err(32)

    class Core:
        USBError = Err

        def __init__(self):
            self.dev = Dev()

        def find(self, **_):
            return self.dev
    u = Unit()
    u.core, u.backend = Core(), object()
    expect("handshake on an image without LOAD METER: usb and aud, not lm", u.handshake(),
           {"usb": True, "lm": False, "aud": True})
    u.core.dev.asked = 0
    s = u.sample()
    expect("its sample: aud read through usb_counters, which says USB answers; lm not asked, no GET_STATUS",
           (s["present"], s["usb"], s["aud_produced"], s["aud_underruns"], u.core.dev.asked), (True, "ok", 114, 103, 1))
    u.core.dev.answers, u.core.dev.asked = False, 0
    s = u.sample()
    expect("the device on the bus, not answering: a USB fail after one request",
           (s["present"], s["usb"], u.core.dev.asked), (True, "fail", 1))
    expect("a handshake while the unit is busy: lm and aud unknown, not absent", u.handshake(),
           {"usb": True, "lm": None, "aud": None})
    u.core.dev.answers = True
    u.sample()
    expect("... and the next sample finds aud, and lm's STALL says it is absent", u.found,
           {"usb": True, "lm": False, "aud": True})

    msgs = [bytes([START]), bytes([0xB0, 0x10, 0x40]), bytes([0xB0, 0x11, 0x00]), bytes([CLOCK]),
            bytes([0xF0, 0x00, 0x20]), bytes([0x3C, 0xF7]), bytes([0x90, 0x24, 0x64])]

    def pktlist(aligned):
        """A MIDIPacketList at a 4-byte-aligned address, its packets aligned or not."""
        raw = bytearray(struct.pack("<I", len(msgs)))
        for m in msgs:
            raw += struct.pack("<QH", 0x1122334455667788, len(m)) + m
            if aligned:
                raw += bytes(-len(raw) % 4)
        buf = ctypes.create_string_buffer(bytes(raw) + bytes(16))
        return buf, ctypes.addressof(buf)
    for aligned in (True, False):
        buf, addr = pktlist(aligned)
        got = list(ot_midi.packets(addr)) if ot_midi.PACKETS_ALIGNED or not aligned else msgs
        expect(f"a packet list {'aligned' if aligned else 'unaligned'} (a SysEx across two packets) reads whole",
               got, msgs)
    c = Clock()
    expect("real-time bytes dropped from the logged packet, the rest kept",
           c.midi(0.0, bytes([CLOCK, 0x90, 0x24, 0x64, CLOCK, SENSE])).hex(" "), "90 24 64")
    c = Clock()
    for i in range(48):
        c.midi(i / 48, bytes([CLOCK]))
    s = c.take()
    expect("120 BPM from a second of clock", (s["clocks"], round(s["bpm"])), (48, 120))
    print(f"selftest: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="watch", choices=("watch", "probe", "selftest"))
    ap.add_argument("--port", help="part of the MIDI source's name (default: one naming Octatrack or Elektron)")
    ap.add_argument("--trigger", help=f"comma-separated, of {', '.join(TRIGGERS)} (default: all the handshake arms)")
    ap.add_argument("--when", help="a Python expression over the sample s (and the last one, p) that triggers")
    ap.add_argument("--pre", type=float, default=120, help="seconds of samples kept before a trigger")
    ap.add_argument("--post", type=float, default=20, help="seconds sampled after a trigger")
    ap.add_argument("--every", type=float, default=1.0, help="seconds between samples (each asks the unit 1-3 requests)")
    ap.add_argument("--audio", nargs="?", const="Octatrack",
                    help="record the unit's USB audio (a CoreAudio device name; default Octatrack)")
    ap.add_argument("--audio-keep", type=float, default=30, help="seconds of audio kept for the freeze file")
    ap.add_argument("--image", help="the image on the unit: its sha256 goes in the log")
    ap.add_argument("--out", default=str(ROOT / "out/hw/freeze"), help="where the logs go (default out/hw/freeze)")
    ap.add_argument("--clock-timeout", type=float, default=1.0, help="seconds of missing clock that count as a stall")
    ap.add_argument("--usb-fails", type=int, default=3, help="unanswered USB requests in a row that count as a hang")
    ap.add_argument("--frame-timeout", type=float, default=1.5, help="seconds the frame count may stand still")
    ap.add_argument("--pause", type=float, default=5.0, help="seconds the wall clock may run ahead before it is the host sleeping")
    ap.add_argument("--keep-going", action="store_true", help="re-arm after a freeze instead of exiting")
    a = ap.parse_args()
    return {"watch": cmd_watch, "probe": cmd_probe, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
