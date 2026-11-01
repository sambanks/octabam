#!/usr/bin/env python3
"""REC THRESHOLD under the port: TRIG THR set through RECORDING SETUP, then
TRACK 1 + REC AB, in twelve scenarios.

Each scenario boots the built image (out/mainos_bus.bin) on a private empty
card, opens RECORDING SETUP 1 with FUNC + REC AB, turns encoder D three
steps (4 detents a step) so TRIG reads THR, closes it with NO, and presses
TRACK 1 + REC AB. "Started" means the recorder's arm wrote LIMIT
(0x46c7fe24[0]) at 0x400069d6, as it does after a stock press.

  tones   the port's tones on every input   armed, then started at once
  silent  a silent WAV from the DSP boot    armed, never started; track 1's
                                            status icon blinks (its drawn state
                                            alternates with 0x10 + state)
  late    silent 10 s, then numbered samples
                                            armed, started only after a wait; the
                                            take's first sample within one frame
                                            (16 samples) of the onset
  cancel  as late, a second press at once   armed, cancelled, never started;
                                            the icon ends on its own state
  untrig  as late, TRIG THR -> HOLD in      armed; the icon renderer drops
          RECORDING SETUP 1 while armed     the arm after the edit, before the
                                            input, the icon stops blinking, and
                                            the input starts nothing
  inpage  tones, RECORDING SETUP 1 left     TRIG ONE: started at once by stock;
          open, TRACK 1 + REC AB inside it  THR: armed, then started
  stock   silent, TRIG left at ONE          RECORDING SETUP 2 shows QREC and
                                            QPL and both edit (QREC back to
                                            OFF); started at once by stock

LEV (the QREC byte under THR, -40 dB when TRIG becomes THR, set through
RECORDING SETUP 2's encoder D, 4 detents a step of LEV_DB) against a steady
1 kHz sine after 10 s of silence:

  high    -20 dBFS, LEV -12 dB              armed, never started; encoder E
                                            (IN, QPL's cell) leaves QPL alone
  quiet   -46 dBFS, LEV -40 dB (default)    armed, never started
  low     -50 dBFS, LEV -60 dB              armed, started after the wait
  full    positive full scale (24-bit       armed, started: at or over LEV
          +0x7fffff), LEV 0 dB              fires, and nothing passes 0 dB

Never flashes or talks to hardware.
"""

from __future__ import annotations

import math
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
from remix import arena  # noqa: E402
EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
ELF = ROOT / "out/platform/runtime/runtime.elf"
STAGE_CARD = ROOT / "tools/emu/ot_emu/stage_card.py"
MAILBOX = 0x46C7E9FA
LIMIT = 0x46C7FE24
ICON = 0x400C0CB8                    # the status icons' drawn states, track 1 first
TRIG_PUBLISHED = 0x80000C97          # 0x80000c94 + slot 3
QREC_PUBLISHED = 0x80000C9D          # slot 9: LEV under THR
QPL_PUBLISHED = 0x80000C9E           # slot 10: IN under THR, not edited
LEV_DB = (-60, -56, -52, -48, -44, -40, -36, -32, -28, -24,   # thresh.s lev_db, raw -1 .. 16
          -20, -16, -12, -8, -6, -4, -2, 0)
ARM_PC = 0x400069D6
RUN_TIMEOUT_S = 900                  # per port run
ELAPSED = {}                         # job name -> wall seconds, None while running

# Panel key codes (tools/panel/key_map.json: row 0x20+r, bit b -> r*8+b).
NO, FUNC, REC_AB, REC_CD, T1 = 0x32, 0x2D, 0x2B, 0x2C, 0x10
OPEN1 = [f"500 key {NO:#x} down", f"560 key {NO:#x} up",
         f"800 key {FUNC:#x} down", f"860 key {REC_AB:#x} down",
         f"920 key {REC_AB:#x} up", f"960 key {FUNC:#x} up"]
SETUP = OPEN1 + ["1300 enc 3 12",                  # TRIG ONE -> THR
                 f"1600 key {NO:#x} down", f"1660 key {NO:#x} up"]


def trig_away():
    """While armed (2000): RECORDING SETUP 1 opened, TRIG THR -> HOLD, closed."""
    return [f"2500 key {FUNC:#x} down", f"2520 key {REC_AB:#x} down",
            f"2540 key {REC_AB:#x} up", f"2560 key {FUNC:#x} up",
            "2700 enc 3 -4", f"2900 key {NO:#x} down", f"2920 key {NO:#x} up"]


def page2_stock():
    """TRIG ONE: RECORDING SETUP 2 opened, QREC one step and back (OFF, so
    the press after stays unquantised), QPL one step, closed: 1700..1999."""
    return [f"1700 key {FUNC:#x} down", f"1720 key {REC_CD:#x} down",
            f"1740 key {REC_CD:#x} up", f"1760 key {FUNC:#x} up",
            "1800 enc 3 4", "1860 enc 3 -4", "1920 enc 4 4",
            f"1950 key {NO:#x} down", f"1970 key {NO:#x} up"]


def lev(db):
    """RECORDING SETUP 2 opened, LEV moved from -40 to db one LEV_DB step at a
    time (4 detents, 80 ms apart: closer or larger turns accelerate), IN
    turned, closed: 1700..3199 ms, before a press at 3200."""
    steps = LEV_DB.index(db) - LEV_DB.index(-40)
    return ([f"1700 key {FUNC:#x} down", f"1720 key {REC_CD:#x} down",
             f"1740 key {REC_CD:#x} up", f"1760 key {FUNC:#x} up"]
            + [f"{1900 + 80 * i} enc 3 {4 if steps > 0 else -4}" for i in range(abs(steps))]
            + ["3050 enc 4 8", f"3100 key {NO:#x} down", f"3120 key {NO:#x} up"])


def press(ms):
    return [f"{ms} key {T1:#x} down", f"{ms + 40} key {REC_AB:#x} down",
            f"{ms + 100} key {REC_AB:#x} up", f"{ms + 140} key {T1:#x} up"]


def fail(message, output=""):
    print(f"  [FAIL] verify_rec_threshold: {message}")
    if output:
        print(output[-4000:])
    return 1


def symbols():
    nm = shutil.which("m68k-elf-nm")
    if not nm:
        raise RuntimeError("m68k-elf-nm is missing")
    out = subprocess.run([nm, str(ELF)], capture_output=True, text=True, check=True).stdout
    sym = {p[2]: int(p[0], 16) for p in (line.split() for line in out.splitlines()) if len(p) == 3}
    if "armed" not in sym:
        raise RuntimeError("the linked runtime has no `armed` (REC THRESHOLD not in the image)")
    return sym


def arena_span():
    """(start, length) of the audio page arena the built image uses: its
    base is the operand the build writes at every arena.BASE_SITES site
    (the platform reserve below it is sized per remix)."""
    img = IMAGE.read_bytes()
    off = arena.BASE_SITES[0] + 2 - 0x40000400
    base = int.from_bytes(img[off:off + 4], "big")
    return base, arena.END - base


def write_wav(path, silent_s, loud_s, numbered=False, dbfs=-6.2):
    """Silence, then a 1 kHz sine, or numbered samples: sample n of the
    loud part is A = C = 4000 + (n & 0x3fff), B = D = 4000 + (n >> 14) * 16,
    so a recorded frame names the input sample it came from."""
    rate = 44100
    frames = bytearray(8 * int(rate * silent_s))
    for i in range(int(rate * loud_s)):
        if numbered:
            a, b = 4000 + (i & 0x3FFF), 4000 + ((i >> 14) << 4)
            frames += struct.pack("<4h", a, b, a, b)
        else:
            v = int(32767 * 10 ** (dbfs / 20) * math.sin(2 * math.pi * 1000 * i / rate))
            frames += struct.pack("<4h", v, v, v, v)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(4)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(bytes(frames))


def write_full_scale(path, silent_s, loud_s):
    """Silence, then +0x7fffff (24-bit positive full scale, held) on every
    input: on the input pages exactly 0x7fffff00, LEV 0 dB's level."""
    rate = 44100
    frames = bytearray(12 * int(rate * silent_s))
    frames += b"\xff\xff\x7f" * 4 * int(rate * loud_s)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(4)
        f.setsampwidth(3)
        f.setframerate(rate)
        f.writeframes(bytes(frames))


def first_numbered(dump):
    """The smallest input sample number in a 16-bit stereo take in the arena
    dump, through the recorder's fade-in (gain g < 1 scales A and B alike:
    B = 4000 g while n < 16384); confirmed by the next frame being n + 1."""
    data = dump.read_bytes()
    best = None
    for off in range(0, len(data) - 8, 4):
        b = int.from_bytes(data[off + 2:off + 4], "big", signed=True)
        if not 2000 < b <= 4003:
            continue
        a = int.from_bytes(data[off:off + 2], "big", signed=True)
        g = b / 4000
        n = round(a / g - 4000)
        if not 0 <= n < 16384 or (best is not None and n >= best):
            continue
        a2 = int.from_bytes(data[off + 4:off + 6], "big", signed=True)
        b2 = int.from_bytes(data[off + 6:off + 8], "big", signed=True)
        if 2000 < b2 <= 4003 and abs(round(a2 / (b2 / 4000) - 4000) - (n + 1)) <= 1:
            best = n
    return best


def run(work, card, armed, name, audio, script, quit_ms):
    path = work / f"{name}.script"
    path.write_text("\n".join(script + [f"{quit_ms} quit"]) + "\n")
    args = [str(EMU), "--image", str(IMAGE), "--card", str(card),
            "--set", "OCTABAM", "--project", "THRESHOLD", "--load-ms", "90000",
            "--mkii", "--dsp", "--main-level", "64",
            "--watch-mem", f"{MAILBOX:#x},32;{LIMIT:#x},32;{armed:#x},32;{TRIG_PUBLISHED:#x},1;"
                           f"{QREC_PUBLISHED:#x},2;{ICON:#x},4",
            "--live-script", str(path)]
    if name == "late":
        start, length = arena_span()
        args += ["--mem-dump", f"{start:#x},{length:#x}={work / 'late_arena.bin'}"]
    args += ["--audio-in", "tones"] if audio == "tones" else ["--audio-in", str(audio), "--audio-in-from-boot"]
    started = time.monotonic()
    try:
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=RUN_TIMEOUT_S)
        ELAPSED[name] = time.monotonic() - started
    except subprocess.TimeoutExpired as exc:
        ELAPSED[name] = time.monotonic() - started
        partial = (exc.stdout or b"") + (exc.stderr or b"")
        if isinstance(partial, bytes):
            partial = partial.decode(errors="replace")
        stamps = re.findall(r"^\s*\[\s*([\d.]+)\]", partial, re.M)
        return name, None, (f"{name}: no exit after {RUN_TIMEOUT_S} s; ended on quit: "
                            f"{'ended on quit' in partial}; M6a gate PASS: {'M6a gate   : PASS' in partial}; "
                            f"{len(partial)} bytes of output, last emulated ms stamp: {stamps[-1] if stamps else None}\n"
                            + partial)
    print(f"  {name}: {ELAPSED[name]:.0f} s", flush=True)
    return name, r.returncode, r.stdout + r.stderr


def job_summary(host, results):
    """Append the host line and each port run's wall time to the Actions job summary."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    rows = "".join(f"| {name} | {ELAPSED[name]:.0f} | {'timed out' if results[name][0] is None else results[name][0]} |\n"
                   for name in results if name in ELAPSED)
    with open(path, "a") as f:
        f.write(f"\n**verify_rec_threshold**: {host}\n\n| port run | wall s | exit |\n|---|---|---|\n{rows}")


def writes(output, addr):
    """(time, value, pc) for each watched write to addr, in order."""
    return [(float(t), int(v, 0), int(pc, 16)) for t, v, pc in re.findall(
        rf"\[\s*([\d.]+)\] \[{addr:#x}\] <- (\S+) \(\d\) at pc (0x[0-9a-f]+)", output)]


def main():
    if not EMU.is_file():
        return fail("the ColdFire port is not built (make emu-cf)")
    if not IMAGE.is_file() or not ELF.is_file():
        return fail("build the image first (make bus REMIX=<a remix with REC THRESHOLD>)")
    try:
        sym = symbols()
        armed = sym["armed"]
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        return fail(str(exc))

    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        project = work / "project"
        project.mkdir()
        (project / "project.work").write_text("[STATES]\nBANK=0\n\n")
        card = work / "card.img"
        staged = subprocess.run([sys.executable, str(STAGE_CARD), str(project), "OCTABAM", "THRESHOLD",
                                 "--tree", str(work / "tree"), "--out", str(card)],
                                cwd=ROOT, capture_output=True, text=True)
        if staged.returncode:
            return fail("could not stage the empty card", staged.stdout + staged.stderr)
        silent, late = work / "silent.wav", work / "late.wav"
        write_wav(silent, 30, 0)
        write_wav(late, 10, 20, numbered=True)

        jobs = [("tones", "tones", SETUP + press(2000), 5000),
                ("silent", silent, SETUP + press(2000), 5000),
                ("late", late, SETUP + press(2000), 14000),
                ("cancel", late, SETUP + press(2000) + press(3000), 14000),
                ("untrig", late, SETUP + press(2000) + trig_away(), 14000),
                ("stock", silent, SETUP[:2] + page2_stock() + press(2000), 5000),
                # REC keys with RECORDING SETUP open (GRID RECORDING off; with
                # it on, stock's REC keys do nothing there, 0x400836e4)
                ("inpage_one", "tones", OPEN1 + press(2000), 5000),
                ("inpage_thr", "tones", OPEN1 + ["1300 enc 3 12"] + press(2000), 5000)]
        tone20, tone46, tone50 = work / "tone20.wav", work / "tone46.wav", work / "tone50.wav"
        write_wav(tone20, 10, 20, dbfs=-20)
        write_wav(tone46, 10, 20, dbfs=-46)
        write_wav(tone50, 10, 20, dbfs=-50)
        jobs += [("high", tone20, SETUP + lev(-12) + press(3200), 14000),
                 ("quiet", tone46, SETUP + press(2000), 14000),
                 ("low", tone50, SETUP + lev(-60) + press(3200), 14000)]
        full = work / "full.wav"
        write_full_scale(full, 10, 6)
        jobs += [("full", full, SETUP + lev(0) + press(3200), 14000)]
        host = f"{os.cpu_count()} cpus, load average {os.getloadavg()[0]:.1f}, {len(jobs)} port runs at once"
        print(f"  host: {host}", flush=True)
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            results = {name: (rc, out) for name, rc, out in
                       pool.map(lambda j: run(work, card, armed, *j), jobs)}
        job_summary(host, results)
        first = first_numbered(work / "late_arena.bin") if (work / "late_arena.bin").is_file() else None

    for name, (rc, out) in results.items():
        if rc is None:
            timed_out = ", ".join(n for n, (r, _) in results.items() if r is None)
            return fail(f"{name}: the port run timed out after {RUN_TIMEOUT_S} s (timed out: {timed_out})", out)
        if rc or "M6a gate   : PASS" not in out or "ended on quit" not in out:
            return fail(f"{name}: the port run did not finish cleanly (exit {rc})", out)

    def facts(name):
        out = results[name][1]
        return (writes(out, TRIG_PUBLISHED), writes(out, armed),
                writes(out, MAILBOX), [w for w in writes(out, LIMIT) if w[2] == ARM_PC], out)

    for name in [n for n in ("tones", "silent", "late", "cancel", "high", "quiet", "low", "full") if n in results]:
        trig, arm, mail, starts, out = facts(name)
        if not trig or trig[-1][1] != 3:
            return fail(f"{name}: RECORDING SETUP did not set TRIG to THR (3): {trig}", out)
        if not arm or arm[0][1] != 0x9010:
            return fail(f"{name}: the press did not arm with stock's start word 0x9010: {arm}", out)
        if any(pc == 0x400051F4 for _, _, pc in mail):
            return fail(f"{name}: stock's own start path ran under THR", out)

    _, arm, mail, starts, out = facts("tones")
    if len(starts) != 1 or not any(v == 0x9010 for _, v, _ in mail):
        return fail(f"tones: wanted one start from the armed word, saw {len(starts)}", out)
    _, arm, mail, starts, out = facts("silent")
    if starts or len(arm) != 1:
        return fail(f"silent: wanted armed and no start, saw starts {starts}, armed {arm}", out)
    icon = [(t, v) for t, v, _ in writes(out, ICON) if t > arm[0][0]]
    blinks = sum(1 for _, v in icon if v & 0x10)
    if blinks < 3 or sum(1 for _, v in icon if not v & 0x10) < 3:
        return fail(f"silent: track 1's icon did not blink while armed: {icon[:12]}", out)
    _, arm, mail, starts, out = facts("late")
    if len(starts) != 1:
        return fail(f"late: wanted one start, saw {len(starts)}", out)
    wait = starts[0][0] - arm[0][0]
    t_tones = facts("tones")
    quick = t_tones[3][0][0] - t_tones[1][0][0]
    if wait <= 10 * quick:
        return fail(f"late: started {wait:.0f} after the press, no later than tones' {quick:.0f}", out)
    if first is None or first > 16:
        return fail(f"late: the take's first sample is input sample {first}; wanted within "
                    "the detection frame (<= 16): the detector reads a stale page", out)
    _, arm, mail, starts, out = facts("cancel")
    if starts or [v for _, v, _ in arm] != [0x9010, 0]:
        return fail(f"cancel: wanted armed then cleared and no start, saw armed {arm}, starts {starts}", out)
    icon = [v for t, v, _ in writes(out, ICON) if t > arm[1][0]]
    if icon and icon[-1] & 0x10:
        return fail(f"cancel: track 1's icon still blanked after the cancel: {icon[-4:]}", out)
    for name, want in (("high", 0), ("quiet", 0), ("low", 1)):
        _, arm, mail, starts, out = facts(name)
        if len(starts) != want:
            return fail(f"{name}: LEV wanted {want} start(s), saw {len(starts)}", out)
    out = results["quiet"][1]
    qrec = [v for _, v, _ in writes(out, QREC_PUBLISHED)]
    if qrec != [4]:
        return fail(f"quiet: TRIG -> THR did not set the unset LEV to -40 dB (QREC raw 4): {qrec}", out)
    out = results["low"][1]
    qrec = [v for _, v, _ in writes(out, QREC_PUBLISHED)]
    if not qrec or qrec[0] != 4 or qrec[-1] not in (0, 0xFF):
        return fail(f"low: RECORDING SETUP 2 did not lower LEV to -60 or -56 dB (QREC raw -1 or 0): {qrec}", out)
    _, arm, mail, starts, out = facts("full")
    qrec = [v for _, v, _ in writes(out, QREC_PUBLISHED)]
    if not qrec or qrec[-1] != 16 or len(starts) != 1:
        return fail(f"full: LEV 0 dB (QREC raw 16) and a positive full-scale input wanted one start; "
                    f"QREC {qrec}, starts {starts}", out)
    out = results["high"][1]
    qrec = [v for _, v, _ in writes(out, QREC_PUBLISHED)]
    if not qrec or qrec[0] != 4 or qrec[-1] < 11 or qrec != sorted(qrec):
        # The port's encoder accelerates now and then (a step of 2), so LEV
        # lands at -12 dB or above: still over the -20 dBFS tone.
        return fail(f"high: RECORDING SETUP 2 did not raise LEV to -12 dB or more (QREC raw >= 11): {qrec}", out)
    high_lev = LEV_DB[qrec[-1] + 1]
    if writes(out, QPL_PUBLISHED):
        return fail("high: turning IN (QPL's cell) on a THR track changed QPL", out)
    trig, arm, mail, starts, out = facts("untrig")
    if not trig or trig[-1][1] != 2:
        return fail(f"untrig: RECORDING SETUP did not move TRIG from THR to HOLD: {trig}", out)
    bg = (sym["blink_gate"], sym[".bg_out"])
    if (starts or [v for _, v, _ in arm] != [0x9010, 0] or arm[1][0] < trig[-1][0]
            or not bg[0] <= arm[1][2] < bg[1]):
        return fail(f"untrig: wanted the arm dropped by the icon renderer after the TRIG edit, "
                    f"no start; saw armed {arm}, TRIG {trig}, starts {starts}", out)
    icon = [v for t, v, _ in writes(out, ICON) if t > arm[1][0]]
    if icon and icon[-1] & 0x10:
        return fail(f"untrig: track 1's icon still blanked after TRIG left THR: {icon[-4:]}", out)
    _, arm, mail, starts, out = facts("stock")
    if arm or len(starts) != 1 or not any(v == 0x9010 and pc == 0x400051F4 for _, v, pc in mail):
        return fail("stock: TRIG ONE did not start at once through stock's path", out)
    qrec = [v for _, v, _ in writes(out, QREC_PUBLISHED)]
    if qrec != [0, 0xFF] or not writes(out, QPL_PUBLISHED):
        return fail(f"stock: RECORDING SETUP 2 on a TRIG ONE track did not edit QREC (0 then OFF) "
                    f"and QPL as stock: QREC {qrec}, QPL {writes(out, QPL_PUBLISHED)}", out)
    _, arm, mail, starts, out = facts("inpage_one")
    if arm or len(starts) != 1 or not any(v == 0x9010 and pc == 0x400051F4 for _, v, pc in mail):
        return fail("inpage_one: TRIG ONE, TRACK 1 + REC AB inside RECORDING SETUP 1 did not start "
                    "at once through stock's path", out)
    trig, arm, mail, starts, out = facts("inpage_thr")
    if not trig or trig[-1][1] != 3 or not arm or arm[0][1] != 0x9010 or len(starts) != 1:
        return fail(f"inpage_thr: TRIG THR, TRACK 1 + REC AB inside RECORDING SETUP 1 did not arm "
                    f"and start: TRIG {trig}, armed {arm}, starts {starts}", out)

    print("  [PASS] verify_rec_threshold: TRIG THR through RECORDING SETUP; TRACK 1 + REC AB "
          "arms with 0x9010; tones start at once, silence never, silence-then-loud only after "
          f"the wait ({wait:.0f} vs {quick:.0f}) with the take from input sample {first} of the onset, "
          "a second press cancels, TRIG moved off THR while armed drops the arm and the blink; TRIG ONE starts "
          "at once and RECORDING SETUP 2 edits QREC and QPL as stock; from inside RECORDING SETUP 1 "
          "TRIG ONE starts and THR arms and starts; an armed track's icon blinks; "
          "LEV through RECORDING SETUP 2: "
          f"THR sets LEV -40 dB; -20 dBFS stays under {high_lev} dB, -46 dBFS under -40 dB, -50 dBFS starts at -60 dB, positive full scale starts at 0 dB; IN leaves QPL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
