#!/usr/bin/env python3
"""Flash 7 on the unit, automated: the one-aux bus's claims driven over MIDI
and measured through the interface, so the human does the flash, the cable
and the project load -- and nothing else.

    python3 tools/hw_flash7.py stage                 # out/projects/OCTABAM_F7TEST
    python3 tools/hw_flash7.py card                  # image + project -> the card, verify, eject
    python3 tools/hw_flash7.py check                 # MIDI ports, the interface, a 2 s level
    python3 tools/hw_flash7.py run [--only ii,iv]    # the test (~6 min), verdict per claim
    python3 tools/hw_flash7.py analyse               # re-read out/hw/flash7/*.wav, re-print

WHAT THE MANUAL ALLOWS (OT MKII 1.40C, Appendix C, read 9 Sep 2026): every
MAIN-page knob has a CC on the track's trig channel (FX1 slots 0-5 = CC 34-39,
FX2 = CC 40-45, level 46, mute 49, solo 50), program change selects the
pattern (PROG CH RECEIVE on; PC n = bank A pattern n+1, measured 24 Aug 2026),
and notes 24-31 play tracks 1-8. NOT reachable: an effect TYPE, a PART, any
page-2 knob. So the claims that need a different effect on a track live in
PARTS 2-4 of the test project's bank A, reached by program change -- and each
of those parts carries a SIGNATURE (T1's LEVEL: 108 / 64 / 84 / 48) so the
run can prove the pattern actually changed before it trusts a claim.

THE METHOD is tools/hw_bus_test.py's synchronous detection: toggle one CC
A/B/A/B on a fixed period while recording, compare adjacent segments (drift
cancels), |t| >= 3 = a real effect. Every A/B run drives a CONTROL known to
reach the DSP beside the TEST, so "no change" is a measurement, not a dead
cable. Absolute levels use the same recordings.

THE RIG: OT on the Midihub's port A (`--port`), the Rytm on its own USB port
as clock master (`--rytm`; START is sent there, never to the OT), the OT's
main outs on the interface (`--rec-device`, the MOTU MicroBook's line pair;
the loudest channel is analysed and named in the log). Drums into inputs
A/B: T1 (THRU, hosts the delay) is the sender under test.

THE HUMAN STEPS, in order: flash OCTABAM21 from the card (docs/FLASHING.md),
power-cycle, PROJECT -> LOAD `OCTABAM_F7TEST`, check PROJECT -> MIDI ->
CONTROL has AUDIO CC IN on and SYNC has PROG CH RECEIVE on, Rytm patched into
A/B, main outs into the interface, then `check` and `run`.
"""
import argparse
import array
import math
import os
import pathlib
import shutil
import subprocess
import sys
import time
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ot_midi                                  # noqa: E402
import ot_project as op                         # noqa: E402
from hw_bus_test import metric, paired, stats   # noqa: E402

OUT = ROOT / "out/hw/flash7"
REC = ROOT / "tools/rec"
BASE = ROOT / "out/projects/OCTABAM_ONEAUX"
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
def stage(src=BASE, dest=TEST):
    """OCTABAM_F7TEST = the one-aux rig with bank A's patterns 2-4 pointing at
    parts 2-4, each a copy of part 1 plus ONE variant and its LEVEL signature:
      part 2: SEND on T8's FX2, AUX 127          (claim v, the refusal)
      part 3: a BUS-mode Character on T4, RET 127 (claims vii / vii-b)
      part 4: NONE on T5 (no reverb)             (claim iii, the last live stage)
    Patterns 2-4 get pattern 1's trigs (T1's THRU trig), so the drums pass."""
    if not (src / "bank01.work").is_file():
        sys.exit(f"{src} missing -- build it: python3 tools/ot_project.py rigproj "
                 f"~/octa/backups/OCTABAM_RIG_20260906_cleared {src} bamsep27")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

    def mut(data):
        # patterns 2-4 := pattern 1, then their part byte
        p0 = op.PTRN0
        chunk = bytes(data[p0:p0 + op.PTRN_FSTRIDE])
        for k in (1, 2, 3):
            a = p0 + k * op.PTRN_FSTRIDE
            data[a:a + op.PTRN_FSTRIDE] = chunk
            data[a + op.PTRN_FSTRIDE - 5] = k
        # parts 2-4 (and their saved mirrors 6-8) := part 1 (mirror 5)
        for base in (0, 4):
            src_off = op.PART_BASE + base * op.PART_STRIDE
            rec = bytes(data[src_off:src_off + op.PART_STRIDE])
            for k in (1, 2, 3):
                off = op.PART_BASE + (base + k) * op.PART_STRIDE
                data[off:off + op.PART_STRIDE] = rec
                data[off + 0x1b + 2 * 0] = SIGNATURE[k]            # T1 LEVEL
                if k == 1:                                          # v: SEND on T8, AUX 127
                    data[off + op.FX2_OFF + 7] = ID_SEND
                    data[off + op.P1_OFF + 7 * op.TRACK_STRIDE + 6 + 0] = 127
                elif k == 2:                                        # vii: station on T4
                    data[off + op.FX1_OFF + 3] = ID_CHARACTER
                    for s, v in enumerate(STATION_P1):
                        data[off + op.P1_OFF + 3 * op.TRACK_STRIDE + s] = v
                    for s, v in enumerate(STATION_P2):
                        data[off + op.P2_OFF + 3 * op.P2_STRIDE + s] = v
                elif k == 3:                                        # iii: no reverb
                    data[off + op.FX2_OFF + 4] = ID_NONE

    op._bank_write(dest, 1, mut, guard=False)
    # read back
    pat_part, parts = op.bank_info(dest, 1)
    want = [0, 1, 2, 3] + [0] * 12
    if pat_part != want:
        sys.exit(f"pattern->part read-back {pat_part} != {want}")
    checks = [
        parts[1]["fx2"][7] == ID_SEND and parts[1]["levels"][0] == 64,
        parts[2]["fx1"][3] == ID_CHARACTER and parts[2]["levels"][0] == 84,
        parts[3]["fx2"][4] == ID_NONE and parts[3]["levels"][0] == 48,
        parts[0]["levels"][0] == 108,
    ]
    if not all(checks):
        sys.exit(f"part read-back failed: {checks} {parts}")
    masks = op.pattern_masks(dest, 1)
    for k in range(4):
        if (k, 0, 0) not in masks:
            sys.exit(f"pattern {k+1} has no T1 trig -- the THRU would pass nothing")
    for suffix in ("work", "strd"):          # .strd only if the source had one
        f = dest / f"bank01.{suffix}"
        if f.is_file():
            d = f.read_bytes()
            if int.from_bytes(d[-2:], "big") != (sum(d[0x10:-2]) & 0xFFFF):
                sys.exit(f"bank01.{suffix}: checksum wrong")
    print(f"staged {dest}: bank A patterns 1-4 -> parts 1-4; T1 LEVEL signatures "
          f"{[SIGNATURE[k] for k in range(4)]}; T1 trig on every pattern")
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
    def toggle(self, ch, cc, va, vb, tag):
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
        samples, sr, _ = self.record(secs, tag)
        skip = int(0.5 * sr)
        seg = samples[skip:]
        r = math.sqrt(sum(v * v for v in seg) / max(1, len(seg)))
        pk = max((abs(v) for v in seg), default=0)
        log(f"    {tag:22s} rms {db(r):.1f} dBFS peak {db(pk):.1f}")
        return db(r), db(pk)


# =========================================================================
# the run
# =========================================================================
def verdict(name, ok, why):
    log(f"  {'PASS' if ok else 'FAIL'}  {name}: {why}")
    return ok


def run(args):
    rig = Rig(args.port, None if args.no_rytm else args.rytm, args.rec_device, args.chan)
    only = set(args.only.split(",")) if args.only else None
    want = lambda k: only is None or k in only
    results = {}
    log(f"flash 7 run {time.strftime('%Y-%m-%d %H:%M')} port {args.port} rec {args.rec_device}")

    # ---- setup: pattern 1, transport, T8 soloed, knobs at the test values
    rig.pc(0)
    if rig.rytm:
        rig.rytm.send([0xFA]); log("  Rytm START sent")
    rig.cc(1, CC_LEVEL, LEVEL_HOME); rig.cc(1, AUX, 127); rig.cc(1, MIX, 127)
    rig.cc(5, MIX, 127); rig.cc(8, RET, 127)
    log(f"  pattern A01 requested, T1 AUX 127, both MIX 127, T8 RET 127; waiting {PATTERN_WAIT:.0f} s")
    time.sleep(PATTERN_WAIT)

    # ---- S0: is anything there at all
    rig.solo_only(8)
    ret0, _ = rig.level(4, "s0_t8_return")
    rig.solo_only(1)
    dry0, _ = rig.level(4, "s0_t1_dry")
    if dry0 < -55:
        log("  STOP: T1 (the drums, soloed) is silent -- no source, wrong input pair, "
            "or the interface is not on the OT's outs. Nothing below can be read.")
        return finish(results)
    results["s0"] = verdict("S0 return alive", ret0 > -55,
                            f"T8 soloed reads {ret0:.1f} dBFS with T1 dry at {dry0:.1f} "
                            f"(flash 6's shape was silence on T8)")

    # ---- ii: the chain -- the return follows T1's send, the hosts print nothing
    if want("ii"):
        log("claim ii -- the chain")
        rig.solo_only(8)
        c = rig.toggle(8, RET, 127, 0, "ii_ctrl_t8_ret")
        t = rig.toggle(1, AUX, 127, 0, "ii_test_t1_aux")
        results["ii-a"] = verdict("ii-a the return follows the send", c["t"] >= 3 and t["t"] >= 3,
                                  f"RET |t|={c['t']:.1f}, T1 AUX |t|={t['t']:.1f} (both must move T8)")
        rig.solo_only(1)
        c = rig.toggle(1, CC_LEVEL, LEVEL_HOME, 64, "ii_ctrl_t1_level")
        rig.cc(1, CC_LEVEL, LEVEL_HOME)
        t = rig.toggle(1, AUX, 127, 0, "ii_test_t1_aux_on_t1")
        results["ii-b"] = verdict("ii-b host T1 prints only its dry", c["t"] >= 3 and t["t"] < 3 and abs(t["rms"]) < 0.5,
                                  f"LEVEL |t|={c['t']:.1f} (the control), AUX |t|={t['t']:.1f} rms d={t['rms']:+.2f} dB "
                                  f"(a host printing its wet would move here -- flash 6's failure)")
        rig.solo_only(5)
        l5, _ = rig.level(4, "ii_t5_solo")
        results["ii-c"] = verdict("ii-c host T5 prints nothing", l5 < -60,
                                  f"T5 soloed reads {l5:.1f} dBFS (nothing plays on T5; a print would show)")
        rig.cc(1, AUX, 127)

    # ---- iv: both engines are in the chain
    if want("iv"):
        log("claim iv -- MIX on each engine")
        rig.solo_only(8)
        d = rig.toggle(1, MIX, 127, 0, "iv_delay_mix")
        rig.cc(1, MIX, 127)
        r = rig.toggle(5, MIX, 127, 0, "iv_reverb_mix")
        rig.cc(5, MIX, 127)
        results["iv"] = verdict("iv delay MIX and reverb MIX both shape the return", d["t"] >= 3 and r["t"] >= 3,
                                f"delay MIX |t|={d['t']:.1f}, reverb MIX |t|={r['t']:.1f}")

    # ---- the pattern-change signature, then the part-borne claims
    def goto(pattern):
        rig.pc(pattern)
        log(f"  program change {pattern} -> pattern A0{pattern+1}; waiting {PATTERN_WAIT:.0f} s")
        time.sleep(PATTERN_WAIT)
        rig.solo_only(1)
        lv, _ = rig.level(3, f"sig_p{pattern+1}_t1")
        got = lv - dry0
        ok = abs(got - SIG_DB[pattern]) < 2.5
        verdict(f"pattern A0{pattern+1} reached (T1 LEVEL {SIGNATURE[pattern]})", ok,
                f"T1 dry {got:+.1f} dB against pattern 1, expected {SIG_DB[pattern]:+.1f}"
                + ("" if ok else " -- PROG CH RECEIVE off, or the project is not OCTABAM_F7TEST"))
        return ok

    if want("v"):
        log("claim v -- the send refused on T8 (pattern 2: SEND on T8's FX2)")
        if goto(1):
            rig.solo_only(8)
            c = rig.toggle(8, RET, 127, 0, "v_ctrl_t8_ret")
            t = rig.toggle(8, AUX, 0, 127, "v_test_t8_aux")
            rig.cc(8, AUX, 0)
            results["v"] = verdict("v T8's AUX changes nothing", c["t"] >= 3 and t["t"] < 3,
                                   f"RET |t|={c['t']:.1f}, T8 AUX |t|={t['t']:.1f} "
                                   f"(T8 audible in its own return = the pin is wrong)")
        else:
            results["v"] = verdict("v", False, "pattern 2 not reached")

    if want("vii"):
        log("claim vii / vii-b -- a BUS station on T4 (pattern 3)")
        if goto(2):
            rig.solo_only(8)
            ret3, _ = rig.level(4, "vii_t8_return")
            rig.solo_only(4)
            l4, _ = rig.level(4, "vii_t4_solo")
            results["vii"] = verdict("vii T4 returns nothing", l4 < -60, f"T4 soloed reads {l4:.1f} dBFS")
            results["vii-b"] = verdict("vii-b T8 still returns beside it", ret3 > -55 and abs(ret3 - ret0) < 4,
                                       f"T8 reads {ret3:.1f} dBFS against {ret0:.1f} on pattern 1 "
                                       f"(silence = the stolen-stamp defect, fixed 9 Sep)")
        else:
            results["vii"] = verdict("vii", False, "pattern 3 not reached")

    if want("iii"):
        log("claim iii -- the last live stage (pattern 4: NONE on T5)")
        if goto(3):
            rig.solo_only(8)
            ret4, _ = rig.level(4, "iii_t8_return")
            d = rig.toggle(1, MIX, 127, 0, "iii_delay_mix")
            rig.cc(1, MIX, 127)
            r = rig.toggle(5, MIX, 127, 0, "iii_reverb_mix")
            rig.cc(5, MIX, 127)
            results["iii"] = verdict("iii repeats return without a reverb", ret4 > -55 and d["t"] >= 3 and r["t"] < 3,
                                     f"T8 {ret4:.1f} dBFS, delay MIX |t|={d['t']:.1f}, reverb MIX |t|={r['t']:.1f} "
                                     f"(silence = the fall-through; a live reverb MIX = the part did not change)")
        else:
            results["iii"] = verdict("iii", False, "pattern 4 not reached")

    # ---- viii: the return over minutes
    if want("viii"):
        log(f"claim viii -- {args.long:.0f} s of return, pattern 1")
        rig.pc(0); time.sleep(PATTERN_WAIT)
        rig.solo_only(8)
        samples, sr, _ = rig.record(args.long, "viii_long")
        win = int(2.0 * sr)
        lv = [db(math.sqrt(sum(v * v for v in samples[i:i + win]) / win)) for i in range(sr, len(samples) - win, win)]
        med = sorted(lv)[len(lv) // 2]
        drops = [i for i, v in enumerate(lv) if v < med - 12]
        results["viii"] = verdict("viii no dropout", not drops,
                                  f"{len(lv)} windows of 2 s: median {med:.1f} dBFS, min {min(lv):.1f}, max {max(lv):.1f}"
                                  + (f"; windows 12 dB under the median at {[2*i+1 for i in drops]} s" if drops else ""))

    # ---- restore
    rig.unsolo()
    rig.cc(1, CC_LEVEL, LEVEL_HOME); rig.cc(1, AUX, 30); rig.cc(1, MIX, 127); rig.cc(5, MIX, 127); rig.cc(8, RET, 127)
    rig.pc(0)
    log("  restored: nothing soloed, T1 AUX 30, MIX 127/127, RET 127, pattern A01")
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
        sys.exit(f"compile the recorder: swiftc -O tools/rec.swift -o {REC}")
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
