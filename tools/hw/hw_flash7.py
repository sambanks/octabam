#!/usr/bin/env python3
"""Flash 7 on the unit, automated: the one-aux bus's claims driven over MIDI
and measured through the interface, so the human does the flash, the cable
and the project load -- and nothing else.

    python3 tools/hw/hw_flash7.py stage                 # out/projects/OCTABAM_F7TEST
    python3 tools/hw/hw_flash7.py card                  # image + project -> the card, verify, eject
    python3 tools/hw/hw_flash7.py check                 # MIDI ports, the interface, a 2 s level
    python3 tools/hw/hw_flash7.py run [--only ii,iv]    # the test (~6 min), verdict per claim
    python3 tools/hw/hw_flash7.py analyse               # re-read out/hw/flash7/*.wav, re-print

WHAT THE MANUAL ALLOWS (OT MKII 1.40C, Appendix C, read 9 Sep 2026): every
MAIN-page knob has a CC on the track's trig channel (FX1 slots 0-5 = CC 34-39,
FX2 = CC 40-45, level 46, mute 49, solo 50), program change selects the
pattern (PROG CH RECEIVE on; PC n = bank A pattern n+1, measured 24 Aug 2026),
and notes 24-31 play tracks 1-8. NOT reachable: an effect TYPE, a PART, any
page-2 knob. So the claims that need a different effect on a track live in
PARTS 2-4 of the test project's bank A, reached by program change -- and each
of those parts carries a SIGNATURE (T1's LEVEL: 108 / 64 / 84 / 48) so the
run can prove the pattern actually changed before it trusts a claim.

THE METHOD is tools/hw/hw_bus_test.py's synchronous detection: toggle one CC
A/B/A/B on a fixed period while recording, compare adjacent segments (drift
cancels), |t| >= 3 = a real effect. Every A/B run drives a CONTROL known to
reach the DSP beside the TEST, so "no change" is a measurement, not a dead
cable. Absolute levels use the same recordings.

THE RIG: OT on the Midihub's port A (`--port`), the Rytm on its own USB port
as clock master (`--rytm`; START is sent there, never to the OT), the OT's
main outs on the interface (`--rec-device`, the MOTU MicroBook's line pair;
the loudest channel is analysed and named in the log). Drums into inputs
A/B: T1 (THRU, hosts the delay) is the sender under test.

THE HUMAN STEPS, in order: flash OCTABAM21 from the card (docs/remixer/FLASHING.md),
power-cycle, PROJECT -> LOAD `OCTABAM_F7TEST`, check PROJECT -> MIDI ->
CONTROL has AUDIO CC IN on and SYNC has PROG CH RECEIVE on, Rytm patched into
A/B, main outs into the interface, then `check` and `run`.
"""
import argparse
import array
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import ot_midi                                  # noqa: E402
import ot_project as op                         # noqa: E402
from hw_bus_test import metric, paired, stats   # noqa: E402

OUT = ROOT / "out/hw/flash7"
REC = ROOT / "tools/hw/rec"
TEST = ROOT / "out/projects/OCTABAM_F7TEST"
IMAGE = ROOT / "out/OCTATRACK_OCTABAM21.bin"

# --- the CC map (manual Appendix C; slot maps from the module manifests) ---
CC_FX1 = 34          # + slot
CC_FX2 = 40          # + slot
CC_LEVEL = 46
CC_MUTE = 49
CC_SOLO = 50
AUX = CC_FX2 + 0     # every track's one send (SEND / both hosts: slot 0)
MIX = CC_FX2 + 5     # both engines: slot 5
RET = CC_FX1 + 2     # Character BUS: the CRSH knob is RET
LEVEL_HOME = 108
# T1 LEVEL per part: the pattern-change signature (OT LEVEL taper, measured
# on T8 24 Aug 2026: 108 = 0 dB, 84 = -3.6, 64 = -8.3, 48 = -13.3)
SIGNATURE = {0: 108, 1: 64, 2: 84, 3: 48}
SIG_DB = {0: 0.0, 1: -8.3, 2: -3.6, 3: -13.3}

ID_SEND, ID_CHARACTER, ID_NONE = 0x09, 0x1c, 0x00
STATION_P1 = (0, 0, 127, 40, 0, 0)          # DRV FOLD RET COMP - -   (RET 127)
STATION_P2 = (127, 3, 0, 1, 64, 0)          # MIX SAT=BUS RING CMOD WDTH SRR

PERIOD, CYCLES, GUARD = 1.5, 8, 0.6
PATTERN_WAIT = 9.5    # a 64-step pattern at 121 BPM is 7.9 s; PC lands at the boundary
LOG = []


def log(s=""):
    print(s, flush=True)
    LOG.append(s)


def db(x):
    return -120.0 if x <= 0 else 20 * math.log10(x)


# =========================================================================
# stage: the test project
# =========================================================================
BASE = ROOT / "out/projects/F7CLEAN_BASE"   # a project the UNIT created on THIS build


def stage(src=BASE, dest=TEST):
    """Build the bus test onto a UNIT-CREATED project (F7CLEAN), not a
    synthesized one. The synthesized project would not take a program change
    on the unit (9 Sep 2026): it was saved under an earlier build
    (OS_VERSION OCTABAM18) and carried the RIG backup's arrangement, MIDI
    mute mask and MIDI_MODE; a project the unit wrote on THIS build takes PC
    at once. So: copy F7CLEAN, stamp the RIG bus layout into every part
    (rigproj), make T1 a THRU, point bank A patterns 2-4 at parts 2-4, and
    give each variant part its ONE change and its T1 LEVEL signature:
      part 2: SEND on T8's FX2, AUX 127          (claim v, the refusal)
      part 3: a BUS-mode Character on T4, RET 127 (claims vii / vii-b)
      part 4: NONE on T5 (no reverb)             (claim iii, the last live stage)
    F7CLEAN's own pattern tails (16 steps, 1X), MIDI settings and structure
    are left as the unit wrote them."""
    if not (src / "project.work").is_file():
        sys.exit(f"{src} missing -- copy the unit's clean project there first:\n"
                 f"  cp -R /Volumes/OCTATRACK/PRESETS/F7CLEAN {src}")
    if "OCTABAM21" not in (src / "project.work").read_text(encoding="latin1"):
        sys.exit(f"{src} was not saved under this build (OCTABAM21) -- re-save F7CLEAN on the unit")
    if dest.exists():
        shutil.rmtree(dest)
    op.make_rig_project(str(src), str(dest), "bamsep27")     # RIG FX layout in every part, verified

    op.thru_track(dest, 1, guard=False)                      # T1 = THRU (type 2) + page + trig in pattern 1

    def variants(data):
        for k in (1, 2, 3):                                  # bank A patterns 2-4 -> parts 2-4
            data[op.PTRN0 + k * op.PTRN_FSTRIDE + op.PTRN_FSTRIDE - 5] = k
            base = op.trac_off(k, 0) + 7                      # T1 trig at step 1 of patterns 2-4
            data[base] |= 1
        for pbase in (0, 4):                                 # parts 2-4 and their saved mirrors := part 1
            src_off = op.PART_BASE + pbase * op.PART_STRIDE
            rec = bytes(data[src_off:src_off + op.PART_STRIDE])
            for k in (1, 2, 3):
                off = op.PART_BASE + (pbase + k) * op.PART_STRIDE
                data[off:off + op.PART_STRIDE] = rec
                data[off + 0x1b + 2 * 0] = SIGNATURE[k]                  # T1 LEVEL
                if k == 1:
                    data[off + op.FX2_OFF + 7] = ID_SEND
                    data[off + op.P1_OFF + 7 * op.TRACK_STRIDE + 6 + 0] = 127
                elif k == 2:
                    data[off + op.FX1_OFF + 3] = ID_CHARACTER
                    for si, v in enumerate(STATION_P1):
                        data[off + op.P1_OFF + 3 * op.TRACK_STRIDE + si] = v
                    for si, v in enumerate(STATION_P2):
                        data[off + op.P2_OFF + 3 * op.P2_STRIDE + si] = v
                elif k == 3:
                    data[off + op.FX2_OFF + 4] = ID_NONE

    op._bank_write(dest, 1, variants, guard=False)

    # project.work / .strd: play from A01 part 1, T8 the master track (the rig).
    # BYTES, not text: the file is CRLF and text mode strips every \r, which
    # the unit rejects with "SOME ERRORS OCCURED / PARSE ERROR" (9 Sep 2026).
    for suffix in ("work", "strd"):
        f = dest / f"project.{suffix}"
        if not f.is_file():
            continue
        data = f.read_bytes()
        for key, val in ((b"BANK", b"0"), (b"PATTERN", b"0"), (b"PART", b"0"), (b"MASTER_TRACK", b"1")):
            data = re.sub(rb"(?m)^" + key + rb"=[^\r\n]*", key + b"=" + val, data)
        if b"\n" in data and b"\r\n" not in data:
            sys.exit("project." + suffix + ": lost CRLF")
        f.write_bytes(data)
    if not (dest / "project.strd").is_file():
        shutil.copyfile(dest / "project.work", dest / "project.strd")

    # read back
    pat_part, parts = op.bank_info(dest, 1)
    if pat_part[:4] != [0, 1, 2, 3]:
        sys.exit(f"pattern->part {pat_part[:4]} != [0,1,2,3]")
    checks = [
        parts[1]["fx2"][7] == ID_SEND and parts[1]["levels"][0] == 64,
        parts[2]["fx1"][3] == ID_CHARACTER and parts[2]["levels"][0] == 84,
        parts[3]["fx2"][4] == ID_NONE and parts[3]["levels"][0] == 48,
        parts[0]["levels"][0] == 108,
        parts[0]["fx1"][0] == ID_CHARACTER and parts[0]["fx2"][0] == 0x06,   # T1 CHARACTER + BusDelay
        parts[0]["fx2"][4] == 0x07,                                          # T5 BusVerb
    ]
    if not all(checks):
        sys.exit(f"part read-back failed: {checks}")
    m = op.pattern_masks(dest, 1)
    for k in range(4):
        if (k, 0, 0) not in m:
            sys.exit(f"pattern {k+1} has no T1 trig")
        if any(key[1] != 0 for key in m if key[0] == k):
            sys.exit(f"pattern {k+1} has trigs off T1")
    d = (dest / "bank01.work").read_bytes()
    if d[op.PART_BASE + 0x2b] != 2:
        sys.exit("T1 is not a THRU")
    tb = (dest / "project.work").read_bytes()
    if b"OCTABAM21" not in tb or b"\r\nBANK=0\r\n" not in tb:
        sys.exit("project.work not the clean build / wrong saved position")
    if b"\n" in tb and b"\r\n" not in tb:
        sys.exit("project.work lost CRLF")
    print(f"staged {dest} from the unit's F7CLEAN: RIG layout in every part, T1 = THRU, "
          f"bank A patterns 1-4 -> parts 1-4, T1 LEVEL signatures {[SIGNATURE[k] for k in range(4)]}, "
          f"T8 master, play from A01")
    for k, what in ((1, "T8 FX2 = SEND, AUX 127"), (2, "T4 FX1 = Character BUS, RET 127"),
                    (3, "T5 FX2 = NONE")):
        print(f"  pattern {k+1} / part {k+1}: {what}")


# =========================================================================
# card: image + project onto the mounted card
# =========================================================================
def card(image=IMAGE, project=TEST, vol="/Volumes/OCTATRACK", set_name="PRESETS"):
    vol = pathlib.Path(vol)
    if not vol.is_dir():
        sys.exit(f"{vol} is not mounted: put the unit in USB DISK MODE (PROJECT menu) "
                 f"and re-run; `ls /Volumes` shows it")
    if not image.is_file():
        sys.exit(f"{image} missing -- REMIX=bamsep27 BUILD=21 make image")
    setdir = vol / set_name
    if not setdir.is_dir():
        sets = [p.name for p in vol.iterdir() if p.is_dir() and (p / "AUDIO").is_dir()]
        sys.exit(f"set {set_name!r} not on the card; sets with an AUDIO folder: {sets} (--set)")
    # the image: one firmware at the root
    dst = vol / image.name
    shutil.copyfile(image, dst)
    if dst.read_bytes() != image.read_bytes():
        sys.exit("image copy does not compare")
    for p in vol.iterdir():
        # only OUR previous builds go; the stock `OCTATRACK_OS1.40B.bin.bak`
        # that has sat at the root since 2023 is Sam's and stays
        if p.is_file() and p.name != image.name and p.name.startswith("OCTATRACK_OCTABAM") \
                and p.suffix.lower() == ".bin":
            print(f"  removing our previous build at the root: {p.name} ({p.stat().st_size} bytes)")
            p.unlink()
    # the project
    pdst = setdir / project.name
    if pdst.exists():
        shutil.rmtree(pdst)
    shutil.copytree(project, pdst)
    for f in sorted(project.iterdir()):
        if f.is_file() and (pdst / f.name).read_bytes() != f.read_bytes():
            sys.exit(f"{f.name} does not compare on the card")
    # sidecars
    killed = 0
    for p in list(vol.glob("._*")) + list(pdst.glob("._*")):
        p.unlink(); killed += 1
    subprocess.run(["sync"])
    roots = [p.name for p in vol.iterdir() if p.is_file() and p.stat().st_size > 300_000]
    print(f"card: {dst.name} at the root (firmware-sized files there: {roots}); "
          f"{pdst.relative_to(vol)} verified file by file; {killed} sidecar(s) removed")
    for _ in range(4):
        r = subprocess.run(["diskutil", "eject", str(vol)], capture_output=True, text=True)
        if r.returncode == 0:
            print("  ejected. If it re-mounts by itself, eject from the Finder.")
            return
        time.sleep(3)
    print(f"  eject failed ({r.stderr.strip()}): eject from the Finder.")


# =========================================================================
# capture + metrics
# =========================================================================
class Rig:
    def __init__(self, port, rytm, rec_device, chan=None):
        self.out = ot_midi.Out(port)
        self.rytm = None
        if rytm:
            try:
                self.rytm = ot_midi.Out(rytm)
            except SystemExit:
                log(f"  (no Rytm port {rytm!r}: transport assumed running)")
        self.rec_device = rec_device
        self.chan = chan
        OUT.mkdir(parents=True, exist_ok=True)

    def cc(self, ch, cc, val, settle=0.05):
        self.out.send([0xB0 | (ch - 1), cc, val]); time.sleep(settle)

    def pc(self, n, settle=0.05):
        self.out.send([0xC0, n]); time.sleep(settle)

    def solo_only(self, track):
        for t in range(1, 9):
            self.cc(t, CC_SOLO, 127 if t == track else 0, 0.02)
        time.sleep(1.0)

    def unsolo(self):
        for t in range(1, 9):
            self.cc(t, CC_SOLO, 0, 0.02)

    def record(self, secs, tag, during=None):
        """rec for `secs`; `during(t0)` runs once the tap is live. Returns
        (samples of the analysed channel, sr, channel index)."""
        wav = OUT / f"{tag}.wav"
        proc = subprocess.Popen([str(REC), f"{secs:.1f}", str(wav), self.rec_device],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        t0 = None
        for line in proc.stdout:
            if line.startswith("START"):
                t0 = float(line.split()[1]); break
        if t0 is None:
            err = proc.stderr.read()
            raise RuntimeError(f"recorder never reported START: {err.strip()}")
        if during:
            during(t0)
        proc.wait()
        return self.load(wav)

    def load(self, wav):
        w = wave.open(str(wav))
        n, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        a = array.array('i' if sw == 4 else 'h')
        a.frombytes(w.readframes(w.getnframes()))
        full = 2 ** 31 if sw == 4 else 2 ** 15
        chans = [[v / full for v in a[c::n]] for c in range(n)]
        if self.chan is None:
            rms = [math.sqrt(sum(v * v for v in c) / max(1, len(c))) for c in chans]
            self.chan = max(range(n), key=lambda i: rms[i])
            log(f"  interface channels (dBFS rms): " + " ".join(f"{i+1}:{db(r):.0f}" for i, r in enumerate(rms))
                + f" -> analysing channel {self.chan+1}")
        return chans[self.chan], sr, self.chan

    # -- the paired A/B toggle ------------------------------------------
    def toggle(self, ch, cc, va, vb, tag, home=None):
        """A/B/A/B on `cc`; afterwards the knob goes back to `home` (default
        the A value) -- a toggle that left its last value ran the next test
        with the return at 0 (9 Sep 2026)."""
        total = PERIOD * CYCLES * 2 + 1.0
        schedule = []

        def drive(t0):
            for k in range(CYCLES * 2):
                val = va if k % 2 == 0 else vb
                rel = k * PERIOD
                while time.time() - t0 < rel:
                    time.sleep(0.002)
                self.out.send([0xB0 | (ch - 1), cc, val])
                schedule.append((rel, val))

        samples, sr, _ = self.record(total, tag, drive)
        self.out.send([0xB0 | (ch - 1), cc, va if home is None else home]); time.sleep(0.3)
        segs = []
        for rel, val in schedule:
            s0, s1 = int((rel + GUARD) * sr), int((rel + PERIOD) * sr)
            if s1 <= len(samples) and s1 > s0:
                r, t, gf = metric(samples[s0:s1], sr)
                segs.append((val, r, t, gf))
        dr, dt, dg = paired(segs, va, vb)
        mr, _, tr = stats(dr); mt, _, tt = stats(dt); mg, _, tg = stats(dg)
        tmax = max(abs(tg), abs(tr), abs(tt))
        a_segs = [s[1] for s in segs if s[0] == va]
        lvl_a = sum(a_segs) / len(a_segs) if a_segs else -120.0
        log(f"    {tag:22s} ch{ch} CC{cc} {va}<->{vb}: gapfloor {mg:+.2f} dB (t {tg:+.1f}) "
            f"rms {mr:+.2f} (t {tr:+.1f}) tilt {mt:+.2f} (t {tt:+.1f}) n={len(dg)} level(A) {lvl_a:.1f} dBFS")
        return dict(t=tmax, rms=mr, gap=mg, tilt=mt, level=lvl_a, n=len(dg))

    def level(self, secs, tag):
        """Returns (median 40 ms window level, peak) in dBFS. The median, not
        the rms: a full-scale click in the capture (see the run log) would
        drag an rms by 10 dB and it moves a median by nothing."""
        samples, sr, _ = self.record(secs, tag)
        skip = int(0.5 * sr)
        seg = samples[skip:]
        win = max(1, int(0.04 * sr))
        w = sorted(math.sqrt(sum(v * v for v in seg[i:i + win]) / win) for i in range(0, len(seg) - win, win))
        med = w[len(w) // 2] if w else 0.0
        r = math.sqrt(sum(v * v for v in seg) / max(1, len(seg)))
        pk = max((abs(v) for v in seg), default=0)
        log(f"    {tag:22s} median {db(med):.1f} dBFS (rms {db(r):.1f}, peak {db(pk):.1f})")
        return db(med), db(pk)


# =========================================================================
# the run
# =========================================================================
def verdict(name, ok, why):
    log(f"  {'PASS' if ok else 'FAIL'}  {name}: {why}")
    return ok


TONE = ROOT / "tools/hw/tone"


class Clock:
    """The Mac as clock master: MIDI clock (24 per beat) on a thread, Start
    on begin, Stop on close. With no Rytm in the room the OT keeps CLOCK
    RECEIVE on and follows this, exactly as it follows the Rytm."""
    def __init__(self, out, bpm):
        import threading
        self.out, self.bpm, self.stop_flag = out, bpm, False
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        period = 60.0 / (self.bpm * 24.0)
        nxt = time.perf_counter()
        while not self.stop_flag:
            self.out.send([0xF8])
            nxt += period
            d = nxt - time.perf_counter()
            if d > 0:
                time.sleep(d)
            else:
                nxt = time.perf_counter()

    def start(self):
        self.thread.start()
        time.sleep(0.2)
        self.out.send([0xFA])          # Start

    def close(self):
        self.out.send([0xFC])          # Stop
        self.stop_flag = True


def start_source(args, secs):
    """The Mac as the drum machine: a gated 1 kHz burst train out of the
    interface (patched into inputs A/B) for the whole run. Returns the
    process, or None when --source is off."""
    if not args.source:
        return None
    if not TONE.is_file():
        sys.exit(f"compile the tone player: swiftc -O tools/hw/tone.swift -o {TONE}")
    cmd = [str(TONE), str(args.source_freq), f"{secs:.0f}", args.rec_device, str(args.source_amp)]
    if args.source == "burst":
        cmd += ["80", "610"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = p.stdout.readline().strip()
    log(f"  source: {line or 'tone player gave no banner'}")
    time.sleep(0.5)
    return p


def run(args):
    rig = Rig(args.port, None if args.no_rytm else args.rytm, args.rec_device, args.chan)
    source = start_source(args, 900)
    clock = None
    if args.clock:
        clock = Clock(rig.out, args.clock)
        clock.start()
        log(f"  MIDI clock at {args.clock} BPM + Start sent to the OT (the Mac is clock master)")
    try:
        return run_claims(args, rig)
    finally:
        if clock:
            clock.close()
        if source:
            source.terminate()


def run_claims(args, rig):
    """T8 is the MASTER track in the rig (measured 9 Sep 2026): soloing it
    mutes nothing, and every other solo still leaves through it -- so the
    return is in every capture and no track can be isolated by solo. Each
    claim is therefore a DIFFERENCE under MUTE and knob toggles in the full
    mix, with a control beside it, and the sends are pre-mute (muting T1
    leaves the return running), which is what makes the mute tests work."""
    only = set(args.only.split(",")) if args.only else None
    want = lambda k: only is None or k in only
    results = {}
    log(f"flash 7 run {time.strftime('%Y-%m-%d %H:%M')} port {args.port} rec {args.rec_device}")

    def home():
        rig.unsolo()
        for t in range(1, 9):
            rig.cc(t, CC_MUTE, 0, 0.02)
        rig.cc(1, 16, 1); rig.cc(1, 17, 127)             # T1 THRU input: INAB = A+B, VOL 127 (reverts on a part change)
        rig.cc(1, 22, 0); rig.cc(1, 23, 127); rig.cc(1, 24, 127)   # AMP ATK 0, HOLD INF, REL max: the dry stays open
        rig.cc(1, 25, 100)                                # AMP VOL: the dry audible beside the return (Sam runs +12)
        rig.cc(1, CC_LEVEL, LEVEL_HOME); rig.cc(1, AUX, 127); rig.cc(1, MIX, 127)
        rig.cc(5, MIX, 127); rig.cc(8, RET, 127); rig.cc(8, AUX, 0)
        time.sleep(1.0)

    rig.pc(0)
    if rig.rytm:
        rig.rytm.send([0xFA]); log("  Rytm START sent")
    home()
    log(f"  pattern A01 requested, nothing muted, T1 AUX 127, both MIX 127, T8 RET 127; waiting {PATTERN_WAIT:.0f} s")
    time.sleep(PATTERN_WAIT)

    mix0, _ = rig.level(4, "s0_mix")
    if mix0 < -55:
        log("  STOP: the mix is silent -- no source into A/B, the transport is not running, "
            "or the interface is not on the OT's outs.")
        return finish(results)
    results["s0"] = verdict("S0 the mix is alive", True, f"{mix0:.1f} dBFS rms")

    if want("ii"):
        log("claim ii -- the chain: the return on T8, the hosts quiet while it is live")
        c = rig.toggle(8, RET, 127, 0, "ii_ret")
        t = rig.toggle(1, AUX, 127, 0, "ii_t1_aux")
        rig.cc(1, AUX, 127)
        results["ii-a"] = verdict("ii-a the return follows T1's send", c["t"] >= 3 and t["t"] >= 3,
                                  f"RET |t|={c['t']:.1f}, T1 AUX |t|={t['t']:.1f} (both must move the gaps)")
        m1 = rig.toggle(5, CC_MUTE, 0, 127, "ii_t5mute_ret127")
        rig.cc(8, RET, 0); time.sleep(1.0)
        m0 = rig.toggle(5, CC_MUTE, 0, 127, "ii_t5mute_ret0")
        rig.cc(5, CC_MUTE, 0); rig.cc(8, RET, 127); time.sleep(1.0)
        results["ii-b"] = verdict("ii-b the wet sits on T8, not on the reverb host", abs(m1["gap"]) < 2 and m0["t"] >= 3,
                                  f"RET 127: muting T5 moves the gaps {m1['gap']:+.1f} dB (t {m1['t']:.1f}); "
                                  f"RET 0: {m0['gap']:+.1f} dB (t {m0['t']:.1f}) = T5 prints only when no return is live "
                                  f"(flash 6: the hosts printed with the return up)")
        m = rig.toggle(1, CC_MUTE, 0, 127, "ii_t1mute")
        rig.cc(1, CC_MUTE, 0)
        results["ii-c"] = verdict("ii-c the send is pre-mute (muting T1 leaves the return)", abs(m["gap"]) < 3,
                                  f"gaps {m['gap']:+.1f} dB with T1 muted (t {m['t']:.1f})")

    if want("iv"):
        log("claim iv -- MIX on each engine")
        rig.cc(1, MIX, 0); time.sleep(0.5)                    # no repeats: the reverb of the dry sends
        r = rig.toggle(5, MIX, 127, 0, "iv_reverb_mix_nodelay")
        rig.cc(1, MIX, 127); rig.cc(5, MIX, 0); time.sleep(0.5)   # no reverb: the repeats alone
        d = rig.toggle(1, MIX, 127, 0, "iv_delay_mix_noverb")
        rig.cc(1, MIX, 127); rig.cc(5, MIX, 127)
        results["iv"] = verdict("iv reverb MIX and delay MIX both shape the return", r["t"] >= 3 and d["t"] >= 3,
                                f"reverb MIX with the delay at 0 |t|={r['t']:.1f}; delay MIX with the reverb at 0 |t|={d['t']:.1f}")

    def arm_t1():
        # a part change reverts T1's THRU input and AMP envelope to the part's
        # stored (silent) values, so re-arm them over CC after every PC
        rig.cc(1, 16, 1); rig.cc(1, 17, 127)            # INAB = A+B, VOL 127
        rig.cc(1, 22, 0); rig.cc(1, 23, 127); rig.cc(1, 24, 127)   # AMP ATK 0, HOLD inf, REL max
        rig.cc(1, 25, 100)                               # AMP VOL

    def goto(pattern):
        # the signature is T1's LEVEL, which the return (post-FX, pre-LEVEL)
        # cannot show: read it with the return off and T5 muted, T1's dry alone
        arm_t1(); rig.cc(1, CC_LEVEL, LEVEL_HOME)
        rig.cc(1, CC_MUTE, 0); rig.cc(5, CC_MUTE, 127); rig.cc(8, RET, 0); time.sleep(1.0)
        ref, _ = rig.level(3, f"sig_p{pattern+1}_before")
        rig.pc(pattern)
        log(f"  program change {pattern} -> pattern A0{pattern+1}; waiting {PATTERN_WAIT:.0f} s")
        time.sleep(PATTERN_WAIT)
        arm_t1(); time.sleep(0.5)   # re-arm the INPUT after the part change, but NOT the level:
        lv, _ = rig.level(3, f"sig_p{pattern+1}_after")   # the part's stored T1 LEVEL is the signature
        rig.cc(5, CC_MUTE, 0); rig.cc(8, RET, 127)
        got = lv - ref
        ok = abs(got - SIG_DB[pattern]) < 3.0
        verdict(f"pattern A0{pattern+1} reached (T1 LEVEL {SIGNATURE[pattern]})", ok,
                f"T1 {got:+.1f} dB across the change, expected {SIG_DB[pattern]:+.1f}"
                + ("" if ok else " -- PROG CH RECEIVE off / wrong channel, or the project is not OCTABAM_F7TEST"))
        return ok

    if want("v"):
        log("claim v -- the send refused on T8 (pattern 2: SEND on T8's FX2)")
        if goto(1):
            home()
            c = rig.toggle(8, RET, 127, 0, "v_ret")
            t = rig.toggle(8, AUX, 0, 127, "v_t8_aux")
            rig.cc(8, AUX, 0)
            results["v"] = verdict("v T8's AUX changes nothing", c["t"] >= 3 and t["t"] < 3,
                                   f"RET |t|={c['t']:.1f}, T8 AUX |t|={t['t']:.1f} "
                                   f"(T8 feeding its own return = the pin is wrong)")
        else:
            results["v"] = verdict("v", False, "pattern 2 not reached")

    if want("vii"):
        log("claim vii / vii-b -- a BUS station on T4 (pattern 3)")
        if goto(2):
            home()
            rig.cc(4, RET, 127)
            m = rig.toggle(4, CC_MUTE, 0, 127, "vii_t4mute")
            rig.cc(4, CC_MUTE, 0)
            c = rig.toggle(8, RET, 127, 0, "vii_t8_ret")
            results["vii"] = verdict("vii T4 returns nothing (muting it changes nothing)", abs(m["gap"]) < 2,
                                     f"gaps {m['gap']:+.1f} dB with T4 muted (t {m['t']:.1f})")
            results["vii-b"] = verdict("vii-b T8 still returns beside the T4 station", c["t"] >= 3,
                                       f"RET |t|={c['t']:.1f}, {c['gap']:+.1f} dB (silence = the stolen stamps, fixed 9 Sep)")
        else:
            results["vii"] = verdict("vii", False, "pattern 3 not reached")

    if want("iii"):
        log("claim iii -- the last live stage (pattern 4: NONE on T5)")
        if goto(3):
            home()
            r = rig.toggle(5, MIX, 127, 0, "iii_reverb_mix")
            d = rig.toggle(1, MIX, 127, 0, "iii_delay_mix")
            rig.cc(1, MIX, 127); rig.cc(5, MIX, 127)
            results["iii"] = verdict("iii the repeats return without a reverb", d["t"] >= 3 and r["t"] < 3,
                                     f"delay MIX |t|={d['t']:.1f}, reverb MIX |t|={r['t']:.1f} "
                                     f"(a live reverb MIX = the part did not change; no repeats = the fall-through)")
        else:
            results["iii"] = verdict("iii", False, "pattern 4 not reached")

    if want("viii"):
        log(f"claim viii -- {args.long:.0f} s of return, pattern 1")
        rig.pc(0); time.sleep(PATTERN_WAIT); home()
        samples, sr, _ = rig.record(args.long, "viii_long")
        win = int(2.0 * sr)
        lv = [db(math.sqrt(sum(v * v for v in samples[i:i + win]) / win)) for i in range(sr, len(samples) - win, win)]
        med = sorted(lv)[len(lv) // 2]
        drops = [i for i, v in enumerate(lv) if v < med - 12]
        results["viii"] = verdict("viii no dropout", not drops,
                                  f"{len(lv)} windows of 2 s: median {med:.1f} dBFS, min {min(lv):.1f}, max {max(lv):.1f}"
                                  + (f"; windows 12 dB under the median at {[2*i+1 for i in drops]} s" if drops else ""))

    home(); rig.cc(1, AUX, 30); rig.pc(0)
    log("  restored: nothing muted or soloed, T1 AUX 30, MIX 127/127, RET 127, pattern A01")
    return finish(results)


def finish(results):
    log("")
    log("SUMMARY " + "  ".join(f"{k}:{'PASS' if v else 'FAIL'}" for k, v in results.items()))
    (OUT / f"run_{time.strftime('%Y%m%d_%H%M')}.log").write_text("\n".join(LOG) + "\n")
    log(f"  log + wavs in {OUT}")
    return all(results.values()) if results else False


def check(args):
    print("MIDI sources:     ", [n for n, _ in ot_midi.endpoints("src")])
    print("MIDI destinations:", [n for n, _ in ot_midi.endpoints("dst")])
    dst = [n for n, _ in ot_midi.endpoints("dst")]
    print(f"  OT port {args.port!r}: {'ok' if args.port in dst else 'MISSING'};"
          f" Rytm {args.rytm!r}: {'ok' if args.rytm in dst else 'missing (transport by hand)'}")
    if not REC.is_file():
        sys.exit(f"compile the recorder: swiftc -O tools/hw/rec.swift -o {REC}")
    rig = Rig.__new__(Rig); rig.rec_device = args.rec_device; rig.chan = args.chan
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        samples, sr, ch = rig.record(2.0, "check")
    except RuntimeError as e:
        sys.exit(f"  interface {args.rec_device!r}: {e}")
    r = math.sqrt(sum(v * v for v in samples) / max(1, len(samples)))
    print(f"  interface {args.rec_device!r} at {sr} Hz, channel {ch+1}: {db(r):.1f} dBFS rms over 2 s"
          + ("  (silent -- is the OT playing into it?)" if db(r) < -60 else ""))


def analyse(args):
    """Re-print the numbers from the saved recordings (no rig)."""
    rig = Rig.__new__(Rig); rig.chan = args.chan
    for wav in sorted(OUT.glob("*.wav")):
        samples, sr, ch = rig.load(wav)
        seg = samples[int(0.5 * sr):]
        r = math.sqrt(sum(v * v for v in seg) / max(1, len(seg)))
        print(f"{wav.name:28s} {len(samples)/sr:6.1f} s  rms {db(r):6.1f} dBFS  (ch {ch+1})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["stage", "card", "check", "run", "analyse"])
    ap.add_argument("--port", default="A", help="the OT's MIDI destination (Midihub port)")
    ap.add_argument("--rytm", default="Elektron Analog Rytm MKII")
    ap.add_argument("--no-rytm", action="store_true", help="do not send START anywhere")
    ap.add_argument("--rec-device", default="MicroBook", help="CoreAudio name substring")
    ap.add_argument("--chan", type=int, default=None, help="interface channel (1-based); default = loudest")
    ap.add_argument("--only", help="claims to run: ii,iv,v,vii,iii,viii")
    ap.add_argument("--long", type=float, default=90.0, help="claim viii capture length, s")
    ap.add_argument("--clock", type=float, default=121.0,
                    help="send MIDI clock at this BPM and Start/Stop to the OT (0 = the Rytm or a hand)")
    ap.add_argument("--source", choices=["burst", "tone"], default=None,
                    help="play the source from the Mac through the interface's outputs (patched into A/B)")
    ap.add_argument("--source-freq", type=float, default=1000.0)
    ap.add_argument("--source-amp", type=float, default=0.1)
    ap.add_argument("--image", default=str(IMAGE))
    ap.add_argument("--set", default="PRESETS", help="the set folder on the card that holds the project")
    ap.add_argument("--vol", default="/Volumes/OCTATRACK")
    args = ap.parse_args()
    if args.chan is not None:
        args.chan -= 1
    if args.cmd == "stage":
        stage()
    elif args.cmd == "card":
        card(pathlib.Path(args.image), TEST, args.vol, args.set)
    elif args.cmd == "check":
        check(args)
    elif args.cmd == "run":
        sys.exit(0 if run(args) else 1)
    elif args.cmd == "analyse":
        analyse(args)


if __name__ == "__main__":
    main()
