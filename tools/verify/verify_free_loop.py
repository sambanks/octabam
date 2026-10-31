#!/usr/bin/env python3
"""Prove FREE LOOP (modules/free-loop) under the ColdFire port.

    python3 tools/verify/verify_free_loop.py [REMIX] [--only NAME] [--keep] [--jobs N]

Without --only, the scenarios run at once (--jobs, default every core), each
in its own port and directory under out/verify_free_loop/j/.

Each scenario is one boot of FREE LOOP's template (modules/free-loop/
make_template.py: T1-T4 FLEX on R1-R4, T1/T3 FREE, T2/T4 GRID, RLEN PLEN,
recorder trigs on step 1) with a --live-script: the transport stopped at
the start, CC 90 on a track's channel as its pedal, panel keys, the
input a steady tone (--audio-in tones).

  free     T1's REC (CC 90, channel 1) at 2.0 s and 10.0 s (8 s = 4 bars at 120): the
           mailbox gets the take's start word then 0x80; the tempo is
           FREE LOOP's for that take (fl_tempo, recomputed here from the
           take's LIMIT), close to 120; A1's length 64, scale 1X; the
           transport runs; R1's loop end is cut to L <= the take; the
           first step comes within a few frames of the stop
  overdub  the same, then T2's REC (channel 2): T2's recorder trig on
           the next step 1 fires (fl_takes, counted for FREE / GRID tracks only)
  mute     the same, then T1's PLAY/STOP (CC 91) tapped (MUTE NOW: at the
           press): T1 muted (0x80000008 bit 8, through stock's CC 49), again: heard
  playend  the same, then T1's PLAY/STOP held 1.5 s: muted at 12.5 s (the
           press's mute), heard again at 13.3 s with an END pending (fl_qpend);
           muted once its loop starts again (~18 s)
  mutedclear T1 muted (a tap), then its REC held 1.5 s: R1 empty at 13.3 s
  stopclear  the sequencer stopped (CC 83), then T1's REC held 1.5 s: R1 empty
  midistop   the same take, then MIDI mode (the MIDI key) and CC 83 on the PROG CH
           channel (AUTO, 11): the sequencer stops, as in audio mode
  slow     T1 BARS 2, MAX 100, a take of 2 bars at 90: the slot's tempo and
           LOOP_BARS are the loop's (FLEX's stretch 1), the voice moves 22,050
           samples in 500 ms
  end      the same, then T1's END (CC 93) at 12 s: T1 still heard at 15 s,
           muted once its loop starts again (~18 s), the mute written within a
           tick of T1's first trig of that pass (the step handler runs a step ahead)
  noclear  the same, T1's PLAY/STOP pressed and released after 0.3 s, then
           3 s: T1 muted, R1 kept
  recclear the same, then T1's REC held 1.5 s: armed at the press; T1 has an
           UNDO buffer, so at 1.3 s the arm is undone and R1 kept (nothing to undo yet)
  recundo  undo's two passes, then T1's REC held 1.5 s at 28 s: T1 back on R1, idle
  takeclear T1's REC at 2 s held 1.5 s: the free take dropped at 3 s (its
           recorder stopped, R1 empty, the transport still stopped, T1 idle);
           a new press at 5 s takes again
  undo     the same (a loop of 8 s, passes from ~10, 18, 26, 34 s), T1's REC at 11 s and
           19 s: the pass at 18 s is recorded by R5's recorder (T5's mailbox, T1's own
           does not start), T1 still plays R1 during it, its slot byte (Part and lane)
           R5 once it records; at 27 s T1 plays R5; UNDO (CC 92) at 28 s: back on R1,
           heard from the pass at 34 s
  undocut  T1's REC at 11 s, UNDO at 20 s while R5 records: T5's recorder stopped,
           T1 back on R1, overdub off
  poptake, poparmed, popover, popend  the template's POPUP ON for T1: during the
           take (5 s), armed (12.5 s), overdubbing (21 s), the cut pass finishing
           (21 s): T1's popup open with that state (fl_pop_key), the screen saved
           as out/verify_free_loop/j/<name>/<name>.png
  popclosed the cut pass over (28 s): the popup closed
  popundo  undo's two passes, CC 92 at 28 s: T1's popup shows UNDO (fl_pop_key), a PNG
  playentry A02's PLAY entry for T1 = MUTE, CC 85 at 12 s: T1 heard at 17 s, muted
           once A02 starts (19.5 s), fl_pat_t[0] = A02
  playstop A02's PLAY entry for T1 = STOP: T1 stopped (fl_stopm), not muted, and no
           trig of T1 dispatched once A02 plays
  fade     T1's PLAY/STOP tapped (MUTE MODE OT): at 20 ms its LEVEL 0 and not muted, at
           200 ms muted with its LEVEL back
  edge     POPUP OFF, T1 overdubbing: fl_odub bit 0, a PNG of the screen's edge mark
  entryarm A02's ENTRY for T2 = ARM, CC 85 at 12 s: T2's pass from A02's first step (by 19 s)
  replace  T2 armed stopped, PLAY at 2 s (A01 2-4 s, 16 steps; its pass 1 into R6), CC 85: A02 with
           T2's ENTRY ARM (the control) or REPLACE, a steady input (a WAV of known level):
           at 5 s the recorder's mixed sources (0x800062cc) are the input + T2 (ARM, ~2x)
           or the input alone (REPLACE: SRC3 dropped from its trig); T2 muted during
           the REPLACE pass, heard and idle after it, on R2
  undoto   T1 UNDO TO 1, the take and REC at 11 s: at 27 s R5's recorder overdubs R5 in
           place (the take stays in R1); UNDO at 28 s stops it, T1 back on R1, R5
           kept whole (the stop wrote its end at the cut); REDO at 30 s: back on R5
  undostep T1 UNDO TO 1, overdubs one at a time (REC, REC): 18-26 s into R5, 34-42 s R5
           in place; UNDO at 43 s: R1 heard from 50 s; REDO at 52 s: R5 whole, heard from 58 s
  slave    CLOCK RECEIVE on: T1's pedal starts nothing
  panel    TRACK 1 held + UP opens the window (fl_win), DOWN, RIGHT: T1's
           SIGN 4/4 -> 3/4 (fl_cfg); NO closes it
  load     the template's freeloop.work read at the load: roles 2 1 2 1
"""
import argparse
import concurrent.futures
import os
import re
import pathlib
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/verify_free_loop"
MAILBOX, LIMIT, REC_POS = 0x46C7E9FA, 0x46C7FE24, 0x46C802C8
TRANSPORT, TEMPO = 0x800065B8, 0x80001814
A1 = 0x400E21E0                                   # bank A, pattern 1
SLOT_END_R1 = 0x100B14F0 + 0x448 * 128 + 0x130
T1, UP, DOWN, RIGHT, NO, YES = 0x10, 0x33, 0x20, 0x21, 0x32, 0x31


def cc(ms, channel, value):
    return f"{ms} midi {0xB0 | channel:02x} 5a {value:02x}"


def cc91(ms, channel, value):
    return f"{ms} midi {0xB0 | channel:02x} 5b {value:02x}"


def cc92(ms, channel, value):
    return f"{ms} midi {0xB0 | channel:02x} 5c {value:02x}"


def cc93(ms, channel, value):
    return f"{ms} midi {0xB0 | channel:02x} 5d {value:02x}"


def key(ms, code, hold=60):
    return [f"{ms} key {code:#x} down", f"{ms + hold} key {code:#x} up"]


def loop_len(ticks, t24):
    q, r = divmod(2646000, t24)
    return ticks * q + (ticks * r + t24 // 2) // t24


def tempo_for(take, spb=16, lo=70, hi=160):
    """fl_tempo for BARS AUTO (freeloop.c), to check the firmware against."""
    for bars in (1, 2, 4, 8, 16):
        steps = spb * bars
        ticks = steps * 6
        if loop_len(ticks, 7200) > take:
            continue
        a, b = 720, 7200
        while b - a > 1:
            m = (a + b) // 2
            a, b = (a, m) if loop_len(ticks, m) <= take else (m, b)
        if b < lo * 24:
            continue
        return (b, bars, loop_len(ticks, b)) if b <= hi * 24 else None
    return None


def parallel(remix, jobs):
    """Every scenario at once: one child per scenario (--keep --only, its own
    directory under OUT, so cards and dumps never meet), printed in order."""
    src = pathlib.Path(__file__).read_text()
    names = re.findall(r'if run\("(\w+)"\)', src)
    names += [f"pop{n}" for n in re.findall(r'"(\w+)": \(FREE', src)]   # the POP table
    def one(n):
        d = OUT / "j" / n
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        r = subprocess.run([sys.executable, __file__, remix, "--keep", "--only", n, "--out", str(d)],
                           cwd=ROOT, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr
    with concurrent.futures.ThreadPoolExecutor(min(jobs, len(names))) as pool:
        results = list(pool.map(one, names))
    failed = [n for n, (rc, _) in zip(names, results) if rc]
    for n, (rc, out) in zip(names, results):
        print(f"  -- {n}"); print(out.rstrip())
    print(f"  verify_free_loop: {len(names)} scenarios, {jobs} at once: "
          f"{'PASS' if not failed else 'FAILED ' + ' '.join(failed)}")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX", "free-loop"))
    ap.add_argument("--only", default="")
    ap.add_argument("--keep", action="store_true", help="reuse out/mainos_bus.bin as built")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1,
                    help="scenarios run at once, each in its own port and directory (default: every core)")
    ap.add_argument("--out", default="", help=argparse.SUPPRESS)   # a scenario's own directory (--jobs)
    a = ap.parse_args()
    global OUT
    if a.out:
        OUT = pathlib.Path(a.out)
    remix = registry.remix(a.remix)
    if "FREE LOOP" not in remix.modules:
        print(f"  [ -- ] verify_free_loop: {a.remix} carries no FREE LOOP"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_free_loop: no port binary (make emu-cf)"); return 0
    OUT.mkdir(parents=True, exist_ok=True)
    if not a.keep:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_free_loop: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    if not a.only and a.jobs > 1:
        return parallel(a.remix, a.jobs)
    image = OUT / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                        capture_output=True, text=True).stdout
    sym = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    for s in ("fl_cfg", "fl_st", "fl_takes", "fl_win", "fl_trim", "fl_src", "fl_pop", "fl_qplay",
              "fl_odub", "fl_pat_t"):
        if s not in sym:
            sys.exit(f"verify_free_loop: no {s} in the runtime's symbols")

    r = subprocess.run([str(PY), str(ROOT / "modules/free-loop/make_template.py"), "--image", str(image),
                        "--out", str(OUT), "--name", "TPL"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_free_loop: make_template failed:\n{(r.stdout + r.stderr)[-1500:]}")
    cards = {}

    def card(slave=False):
        if slave in cards:
            return cards[slave]
        d = OUT / f"proj_{int(slave)}"
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(OUT / "TPL", d)
        if slave:
            p = d / "project.work"
            raw = p.read_bytes().replace(b"MIDI_CLOCK_RECEIVE=0", b"MIDI_CLOCK_RECEIVE=1")
            p.write_bytes(raw)
        c = OUT / f"card_{int(slave)}.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(d), "OCTABAM", "FL",
                            "--tree", str(OUT / f"tree_{int(slave)}"), "--out", str(c)],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_free_loop: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        cards[slave] = c
        return c

    def boot(tag, lines, quit_ms, dumps, watch="", slave=False, lcd=False, audio_in="tones"):
        script = OUT / f"{tag}.script"
        lines = [l for l in lines if int(l.split()[0]) <= quit_ms]   # the port reads the script in order: a
        script.write_text("\n".join(lines + [f"{quit_ms} quit"]) + "\n")   # later line would hold the quit back
        files = {k: OUT / f"{tag}_{k}.bin" for k in dumps}
        for p in files.values():
            p.unlink(missing_ok=True)
        cmd = [EMU, "--image", image, "--card", card(slave), "--set", "OCTABAM", "--project", "FL",
               "--load-ms", "90000", "--mkii", "--dsp", "--internal-clock", "--audio-in", audio_in,
               "--live-script", script,
               "--mem-dump", ";".join(f"{addr:#x},{n}={files[k]}" for k, (addr, n) in dumps.items())]
        if watch:
            cmd += ["--watch-mem", watch]
        if lcd:
            cmd += ["--lcd", OUT / f"{tag}.lcd"]
        with open(OUT / f"{tag}.txt", "w") as f:
            rc = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        if rc or not all(p.is_file() for p in files.values()):
            sys.exit(f"verify_free_loop: ot_emu exit {rc} -- {OUT / (tag + '.txt')}")
        log = (OUT / f"{tag}.txt").read_text(errors="replace")
        return {k: p.read_bytes() for k, p in files.items()}, log

    fails = 0

    def check(label, ok, detail):
        nonlocal fails
        fails += not ok
        print(f"  [{'ok' if ok else 'FAIL'}] {label}  {detail}")

    def u32(b, o=0):
        return struct.unpack_from(">I", b, o)[0]

    def writes(log, addr):
        import re
        return [(float(t), int(v, 0), pc) for t, v, pc in re.findall(
            rf"\[\s*([\d.]+)\] \[{addr:#x}\] <- (\S+) \(\d\) at pc (0x[0-9a-f]+)", log)]

    STATE = {"tempo": (TEMPO, 4), "transport": (TRANSPORT, 4), "a1": (A1 + 0x8e53, 2),
             "limit": (LIMIT, 16), "end1": (SLOT_END_R1, 4), "cfg": (sym["fl_cfg"], 1098),
             "st": (sym["fl_st"], 176), "takes": (sym["fl_takes"], 32), "win": (sym["fl_win"], 4),
             "trim": (sym["fl_trim"], 32), "mutes": (0x80000008, 4), "voice": (0x800049D8, 0xA8 * 8),
             "lane": (0x8000082F, 1), "flex1": (A1 + 0x8ed80 + 0x2cb, 1), "src": (sym["fl_src"], 8),
             "lim8": (LIMIT, 32), "pos8": (REC_POS, 32),
             "ends": (0x100B14F0 + 0x448 * 128, 0x448 * 8)}
    FREE = [cc(2000, 0, 127), cc(2100, 0, 0), cc(10000, 0, 127), cc(10100, 0, 0)]
    run = lambda n: not a.only or a.only == n

    if run("load"):
        d, _ = boot("load", [], 1500, STATE)
        check("load: freeloop.work read", list(d["cfg"][:4]) == [2, 1, 2, 1] and list(d["cfg"][570:574]) == [5, 6, 7, 8],
              f"roles {list(d['cfg'][:8])}, undo buffers {list(d['cfg'][570:578])}")

    if run("free"):
        d, log = boot("free", FREE, 13000, STATE,
                      watch=f"{MAILBOX:#x},16;{TRANSPORT:#x},4;0x800065b5,1;{SLOT_END_R1:#x},4")
        print("         R1 end writes", [(round(t), v, pc) for t, v, pc in writes(log, SLOT_END_R1)][-6:])
        mail = [v for _, v, _ in writes(log, MAILBOX) if v]
        check("free: the take's start then its stop", mail[:2] == [0x9010 | 0x4000, 0x80] or mail[:2] == [0x9010, 0x80],
              f"mailbox {[hex(v) for v in mail[:4]]}")
        take = u32(d["limit"])                      # the take and its fade-out (FOUT)
        t24 = u32(d["tempo"])
        L = loop_len(64 * 6, t24)
        check("free: the take ~8 s", 352000 < take < 354500, f"LIMIT[T1] {take}")
        check("free: 4 bars at 120 +- 0.1", 2878 <= t24 <= 2882 and t24 == tempo_for(L + 1)[0],
              f"tempo24 {t24} ({t24 / 24:.3f} BPM)")
        want = (t24, 4, L)
        check("free: A1 64 steps 1X", list(d["a1"]) == [64, 2], f"length/scale {list(d['a1'])}")
        check("free: the transport runs", u32(d["transport"]) == 1, f"{u32(d['transport'])}")
        end = u32(d["end1"])
        print("         fl_trim", [u32(d["trim"], 4 * t) for t in range(4)],
              "voice byte 1", [d["voice"][0xA8 * t + 1] for t in range(4)],
              "slot ends", [u32(d["ends"], 0x448 * r + 0x130) for r in range(8)])
        check("free: R1's loop end cut to L", end == L and end <= take,
              f"end {end}, L {want and want[2]}, take {take}")
        tw = writes(log, TRANSPORT)
        stop = [t for t, v, _ in writes(log, MAILBOX) if v == 0x80]
        run_at = [t for t, v, _ in tw if v == 1]
        steps = [t for t, v, _ in writes(log, 0x800065b5) if run_at and t >= run_at[0]]
        if stop and run_at:
            print(f"         stop posted at {stop[0]:.1f}, transport 1 at {run_at[0]:.1f} (port clock units)")

    if run("overdub"):
        lines = FREE + [cc(11000, 1, 127), cc(11100, 1, 0)]
        d, log = boot("overdub", lines, 21000, STATE)
        takes = [u32(d["takes"], 4 * t) for t in range(8)]
        check("overdub: T2's pass fires (its recorder, or R6's: its UNDO buffer), T1/T3/T4 none",
              takes[1] + takes[5] >= 1 and takes[0] == takes[2] == takes[3] == 0, f"fl_takes {takes}")
        check("overdub: T2 overdubbing", d["st"][1] == 3, f"st {list(d['st'][:4])}")

    if run("mute"):
        d1, _ = boot("mute1", FREE + [cc91(12000, 0, 127), cc91(12100, 0, 0)], 13000, STATE)
        check("mute: PLAY/STOP mutes T1", (u32(d1["mutes"]) >> 8) & 1 == 1, f"mutes {u32(d1['mutes']):#x}")
        d2, _ = boot("mute2", FREE + [cc91(12000, 0, 127), cc91(12100, 0, 0), cc91(13000, 0, 127), cc91(13100, 0, 0)],
                     14000, STATE)
        check("mute: again, heard", (u32(d2["mutes"]) >> 8) & 1 == 0, f"mutes {u32(d2['mutes']):#x}")

    QPEND = 40                                         # FlState qpend[8] (st has held undo started: 5 x 8)
    if run("playend"):
        lines = FREE + [cc91(12000, 0, 127), cc91(13500, 0, 0)]
        da, _ = boot("playend_a", lines, 12500, STATE)
        check("playend: held 0.5 s: T1 muted (MUTE NOW, at the press)",
              (u32(da["mutes"]) >> 8) & 1 == 1, f"mutes {u32(da['mutes']):#x}")
        db, _ = boot("playend_b", lines, 13300, STATE)
        check("playend: held 1 s: the press's mute undone, an END pending, R1 kept",
              db["st"][QPEND] == 1 and (u32(db["mutes"]) >> 8) & 1 == 0 and u32(db["end1"]) != 0,
              f"qpend {db['st'][QPEND]}, mutes {u32(db['mutes']):#x}, end {u32(db['end1'])}")
        dc, _ = boot("playend_c", lines, 19500, STATE)
        check("playend: muted once its loop starts again", (u32(dc["mutes"]) >> 8) & 1 == 1 and dc["st"][QPEND] == 0,
              f"mutes {u32(dc['mutes']):#x}, qpend {dc['st'][QPEND]}")

    if run("mutedclear"):
        lines = FREE + [cc91(11500, 0, 127), cc91(11600, 0, 0), cc(12000, 0, 127), cc(13500, 0, 0)]
        d, _ = boot("mutedclear", lines, 13300, STATE)
        check("mutedclear: T1 muted, REC held 1 s: R1 empty, T1 idle",
              (u32(d["mutes"]) >> 8) & 1 == 1 and u32(d["end1"]) == 0 and d["st"][0] == 0 and d["st"][8] == 0,
              f"mutes {u32(d['mutes']):#x}, end {u32(d['end1'])}, st {d['st'][0]}, has {d['st'][8]}")

    if run("stopclear"):
        stop = [f"12000 midi ba 53 7f"]                # CC 83 on the PROG CH channel (11): STOP
        lines = FREE + stop + [cc(13000, 0, 127), cc(14500, 0, 0)]
        d, _ = boot("stopclear", lines, 14300, STATE)
        check("stopclear: stopped, REC held 1 s: R1 empty",
              u32(d["transport"]) != 1 and u32(d["end1"]) == 0 and d["st"][8] == 0,
              f"transport {u32(d['transport'])}, end {u32(d['end1'])}, has {d['st'][8]}")

    if run("midistop"):
        lines = FREE + key(11500, 0x35) + [f"12000 midi ba 53 7f"]   # MIDI mode, then CC 83 on AUTO (11)
        d, _ = boot("midistop", lines, 13000, {**STATE, "midimode": (0x80000012, 4)})
        check("midistop: in MIDI mode, CC 83 on the AUTO channel stops the sequencer",
              u32(d["midimode"]) != 0 and u32(d["transport"]) != 1,
              f"MIDI mode {u32(d['midimode'])}, transport {u32(d['transport'])}")

    if run("end"):
        lines = FREE + [cc93(12000, 0, 127)]
        da, _ = boot("end_a", lines, 15000, STATE)
        check("end: T1 still heard before its loop's end", (u32(da["mutes"]) >> 8) & 1 == 0, f"mutes {u32(da['mutes']):#x}")
        db, log = boot("end_b", lines, 19500, STATE, watch="0x80000008,4;0x80004a04,4;0x80000c50,1")
        check("end: muted once the loop starts again", (u32(db["mutes"]) >> 8) & 1 == 1, f"mutes {u32(db['mutes']):#x}")
        mw = [t for t, v, _ in writes(log, 0x80000C50) if v == 0]              # the fade's start, LEVEL 0
        mb = [t for t, v, _ in writes(log, 0x80000008) if (v >> 8) & 1]
        if mw and mb:
            check("end: the mute itself after the fade (~50 ms)", 0 < mb[0] - mw[0] < 4000,
                  f"LEVEL 0 at {mw[0]:.1f}, mute at {mb[0]:.1f} (port clock)")
        trigs = [t for t, _, pc in writes(log, 0x80004A04) if pc == "0x4000f790"]   # T1's voice start, each pass
        if mw:
            after = [t for t in trigs if t >= mw[0]]
            before = [t for t in trigs if t < mw[0]]
            near = min((abs(t - mw[0]) for t in trigs), default=1e9)
            check("end: the fade starts at the pass's first trig (within one tick), not a step early",
                  near < 950 and len(trigs) >= 2 and mw[0] > trigs[0] + 300000,
                  f"mute at {mw[0]:.1f}, T1's trigs {[round(t) for t in trigs]} (port clock)")

    if run("noclear"):
        d, _ = boot("noclear", FREE + [cc91(12000, 0, 127), cc91(12300, 0, 0)], 15000, STATE)
        check("noclear: T1 muted, R1 kept", (u32(d["mutes"]) >> 8) & 1 == 1 and u32(d["end1"]) != 0,
              f"mutes {u32(d['mutes']):#x}, end {u32(d['end1'])}")

    if run("recclear"):
        lines = FREE + [cc(12000, 0, 127), cc(13500, 0, 0)]
        da, _ = boot("recclear_a", lines, 12500, STATE)
        check("recclear: REC armed at the press", da["st"][0] == 2 and u32(da["end1"]) != 0,
              f"st {da['st'][0]}, end {u32(da['end1'])}")
        db, _ = boot("recclear_b", lines, 13300, STATE)
        check("recclear: held 1 s, the pedal still down (T1 has R5: UNDO, nothing to undo): the arm undone, R1 kept",
              u32(db["end1"]) != 0 and db["st"][0] == 0 and db["st"][8] == 1 and u32(db["transport"]) == 1,
              f"end {u32(db['end1'])}, st {db['st'][0]}, has {db['st'][8]}, transport {u32(db['transport'])}")

    if run("takeclear"):
        lines = [cc(2000, 0, 127), cc(3500, 0, 0)]
        da, _ = boot("takeclear_a", lines, 3300, STATE)
        rec = da["voice"][1]
        check("takeclear: held 1 s: the take dropped, the pedal still down",
              da["st"][0] == 0 and rec == 0 and u32(da["end1"]) == 0 and u32(da["transport"]) != 1,
              f"st {da['st'][0]}, T1 recorder byte {rec}, end {u32(da['end1'])}, transport {u32(da['transport'])}")
        db, _ = boot("takeclear_b", lines + [cc(5000, 0, 127), cc(5100, 0, 0)], 5500, STATE)
        check("takeclear: the next press takes again", db["st"][0] == 1 and db["voice"][1] != 0,
              f"st {db['st'][0]}, T1 recorder byte {db['voice'][1]}")

    if run("slow"):
        cfg = sym["fl_cfg"]
        pokes = f"1000 poke {cfg + 16:#x}=2;{cfg + 42:#x}=0;{cfg + 43:#x}=100"     # T1 BARS 2, MAX 100
        lines = [pokes, cc(2000, 0, 127), cc(2100, 0, 0), cc(7333, 0, 127), cc(7433, 0, 0)]  # 2 bars at 90
        extra = dict(STATE, slot=(0x100B14F0 + 0x448 * 128, 0x448), v1=(0x800049D8, 0xA8))
        da, _ = boot("slow_a", lines, 9000, extra)
        db, _ = boot("slow_b", lines, 9500, extra)
        t24 = u32(da["tempo"])
        print(f"         tempo24 {t24} ({t24 / 24:.2f}), A1 {list(da['a1'])}, R1 end {u32(da['end1'])}")
        print("         slot +0x110..+0x138:", [hex(u32(da["slot"], o)) for o in range(0x110, 0x138, 4)])
        moved = [(o, u32(db["v1"], o) - u32(da["v1"], o)) for o in range(0, 0xA8, 4)
                 if u32(db["v1"], o) != u32(da["v1"], o)]
        print("         voice T1 longs moved in 500 ms (22,050 samples at rate 1):", [(hex(o), d) for o, d in moved])
        check("slow: the slot stamped with the loop's tempo and 2 bars",
              u32(da["slot"], 0x114) == t24 and u32(da["slot"], 0x11c) == 200 and u32(da["slot"], 0x120) == 200,
              f"slot tempo {u32(da['slot'], 0x114)}, bars x100 {u32(da['slot'], 0x11c)}/{u32(da['slot'], 0x120)}, project {t24}")
        rate = u32(db["v1"], 0x44) - u32(da["v1"], 0x44)
        check("slow: T1 plays at rate 1", 21800 < rate < 22300, f"voice +0x44 moved {rate} in 500 ms")

    CUR = 82                                           # FlState on the 5475 (u32 on 2 bytes): cur[8] .. inj[8] after down[8]
    def takes_of(d, t):                                # recorder trigs let through for track t (its own or injected)
        return u32(d["takes"], 4 * t) + u32(d["takes"], 4 * (fl_undo_r(d, t)))

    def fl_undo_r(d, t):
        return (d["cfg"][570 + t] or t + 1) - 1

    def st_field(d, k, t=0):                           # cur 0, rec 1, valid 2, swap 3, undone 4, inj 5
        return d["st"][CUR + 8 * k + t]

    def slot_of(d, t):
        return (u32(d["voice"], 0xA8 * t + 8) - 0x100B14F0) // 0x448

    if run("undo"):
        od = FREE + [cc(11000, 0, 127), cc(11100, 0, 0), cc(19000, 0, 127), cc(19100, 0, 0)]
        mb = f"{MAILBOX:#x},16"
        da, log = boot("undo_a", od, 21000, STATE, watch=mb)
        import re
        starts = [(round(float(t)), a) for t, a, v in re.findall(r"\[\s*([\d.]+)\] \[(0x46c7e9[0-9a-f]+|0x46c7ea0[0-9a-f])\] <- (\S+)", log)
                  if int(v, 0)]
        print("         mailbox writes (port clock, address)", starts[:8])
        check("undo: the pass recorded by R5's recorder, not T1's",
              da["voice"][0xA8 * 4 + 1] != 0 and da["voice"][1] == 0 and len(starts) == 2,
              f"recorders running T5 {da['voice'][0xA8 * 4 + 1]} T1 {da['voice'][1]}, mailbox words {len(starts)} (the take's)")
        check("undo: R5 records with T1's setup", da["src"][4] == 1 and da["voice"][0xA8 * 4 + 1] != 0,
              f"fl_src {list(da['src'])}, T5 recorder byte {da['voice'][0xA8 * 4 + 1]}")
        check("undo: T1 still plays R1 during the pass", slot_of(da, 0) == 128, f"slot {slot_of(da, 0)}")
        check("undo: T1's slot byte R5 once it records", da["lane"][0] == 0x84 and da["flex1"][0] == 0x84
              and st_field(da, 0) == 1, f"lane {da['lane'][0]:#x}, Part {da['flex1'][0]:#x}, cur {st_field(da, 0)}")
        db, _ = boot("undo_b", od + [cc92(28000, 0, 127), cc92(28100, 0, 0)], 29000, STATE)
        e5 = u32(db["ends"], 0x448 * 4 + 0x130)
        print("         LIMIT", [u32(db["lim8"], 4 * r) for r in range(8)], "write pos", [u32(db["pos8"], 4 * r) for r in range(8)])
        print("         R5 slot +0x110..+0x138:", [u32(db["ends"], 0x448 * 4 + o) for o in range(0x110, 0x138, 4)])
        check("undo: at 27 s T1 plays R5, a whole loop", slot_of(db, 0) == 132 and abs(e5 - u32(db["end1"])) < 400,
              f"slot {slot_of(db, 0)}, R5 end {e5}, R1 end {u32(db['end1'])}")
        check("undo: UNDO puts T1 back on R1", db["lane"][0] == 0x80 and st_field(db, 0) == 0 and st_field(db, 4) == 1,
              f"lane {db['lane'][0]:#x}, cur {st_field(db, 0)}, undone {st_field(db, 4)}")
        dc, _ = boot("undo_c", od + [cc92(28000, 0, 127), cc92(28100, 0, 0)], 35000, STATE)
        check("undo: heard from the next pass (R1)", slot_of(dc, 0) == 128, f"slot {slot_of(dc, 0)} at 35 s")

    if run("undoto"):                                  # T1 UNDO TO 1: passes from ~10 (none), 18, 26, 34 s
        poke = [f"1000 poke {sym['fl_cfg'] + 1090:#x}=1"]
        od = poke + FREE + [cc(11000, 0, 127), cc(11100, 0, 0)]
        IN = CUR + 8 * 8                                               # FlState inplace[8] (npass, anchor before it)
        da, _ = boot("undoto_a", od, 27000, STATE)
        check("undoto: at 27 s T1 on R5, R5's recorder overdubbing it in place, T1's own idle",
              da["lane"][0] == 0x84 and da["st"][IN] == 1 and da["voice"][0xA8 * 4 + 1] != 0 and da["voice"][1] == 0
              and da["st"][CUR + 48] == 2 and da["st"][CUR + 56] == 2,
              f"lane {da['lane'][0]:#x}, inplace {da['st'][IN]}, recorders T5 {da['voice'][0xA8 * 4 + 1]} T1 {da['voice'][1]}, "
              f"npass {da['st'][CUR + 48]}, anchor {da['st'][CUR + 56]}")
        db, _ = boot("undoto_b", od + [cc92(28000, 0, 127), cc92(28100, 0, 0)], 28500, STATE)
        check("undoto: UNDO during it: R5's recorder stopped, T1 back on R1 (the take), REDO next",
              db["lane"][0] == 0x80 and db["voice"][0xA8 * 4 + 1] == 0 and st_field(db, 0) == 0 and st_field(db, 4) == 1
              and db["st"][IN] == 0, f"lane {db['lane'][0]:#x}, T5 recorder {db['voice'][0xA8 * 4 + 1]}, "
              f"cur {st_field(db, 0)}, undone {st_field(db, 4)}")
        e27 = [u32(da["ends"], 0x448 * 4 + o) for o in (0x130, 0x11c)] + [u32(da["lim8"], 16)]
        e28 = [u32(db["ends"], 0x448 * 4 + o) for o in (0x130, 0x11c)] + [u32(db["lim8"], 16)]
        check("undoto: R5 kept whole through the cut (its end, bars, LIMIT as before it)",
              e28 == e27 and e27[0] > 350000 and e27[1] == 400, f"R5 end/bars/LIMIT at 27 s {e27}, after the UNDO {e28}")
        dr, _ = boot("undoto_r", od + [cc92(28000, 0, 127), cc92(28100, 0, 0), cc92(30000, 0, 127), cc92(30100, 0, 0)],
                     30500, STATE)
        er = [u32(dr["ends"], 0x448 * 4 + o) for o in (0x130, 0x11c)] + [u32(dr["lim8"], 16)]
        check("undoto: REDO: T1 back on R5, the whole loop", dr["lane"][0] == 0x84 and st_field(dr, 0) == 1
              and st_field(dr, 4) == 0 and er == e27, f"lane {dr['lane'][0]:#x}, cur {st_field(dr, 0)}, "
              f"undone {st_field(dr, 4)}, R5 end/bars/LIMIT {er}")
        do, _ = boot("undoto_o", od + [cc92(28000, 0, 127), cc92(28100, 0, 0), cc92(30000, 0, 127), cc92(30100, 0, 0),
                                       cc(31000, 0, 127), cc(31100, 0, 0)], 43000, STATE)
        eo = [u32(do["ends"], 0x448 * 4 + o) for o in (0x130, 0x11c)]
        check("undoto: then REC: R5 overdubbed in place again over a whole loop (34-42 s)",
              do["lane"][0] == 0x84 and do["st"][IN] == 1 and abs(eo[0] - e27[0]) < 400 and eo[1] == 400,
              f"lane {do['lane'][0]:#x}, inplace {do['st'][IN]}, R5 end/bars {eo}")

    if run("undostep"):                                # T1 UNDO TO 1, overdubs one at a time (REC, REC)
        poke = [f"1000 poke {sym['fl_cfg'] + 1090:#x}=1"]
        od = (poke + FREE + [cc(11000, 0, 127), cc(11100, 0, 0), cc(20000, 0, 127), cc(20100, 0, 0),   # 18-26 into R5
                             cc(27000, 0, 127), cc(27100, 0, 0), cc(36000, 0, 127), cc(36100, 0, 0)])  # 34-42 R5 in place
        IN = CUR + 8 * 8

        def r5(d):
            return [u32(d["ends"], 0x448 * 4 + o) for o in (0x130, 0x11c)] + [u32(d["lim8"], 16)]

        dp, _ = boot("undostep_p", od, 42500, STATE)
        print("         after the two passes: lane", hex(dp["lane"][0]), "cur", st_field(dp, 0), "rec", st_field(dp, 1),
              "valid", st_field(dp, 2), "undone", st_field(dp, 4), "npass", dp["st"][CUR + 48], "anchor", dp["st"][CUR + 56],
              "inplace", dp["st"][IN], "st", dp["st"][0], "R5", r5(dp), "R1 end", u32(dp["end1"]))
        check("undostep: two passes over: T1 on R5, valid, R5 a whole loop",
              dp["lane"][0] == 0x84 and st_field(dp, 2) == 1 and r5(dp)[1] == 400 and r5(dp)[0] > 350000,
              f"lane {dp['lane'][0]:#x}, valid {st_field(dp, 2)}, R5 {r5(dp)}")
        un = od + [cc92(43000, 0, 127), cc92(43100, 0, 0)]
        du, _ = boot("undostep_u", un, 51000, STATE)
        check("undostep: UNDO: T1 on R1, the take, heard from 50 s",
              du["lane"][0] == 0x80 and st_field(du, 4) == 1 and slot_of(du, 0) == 128,
              f"lane {du['lane'][0]:#x}, undone {st_field(du, 4)}, slot {slot_of(du, 0)}")
        dr, _ = boot("undostep_r", un + [cc92(52000, 0, 127), cc92(52100, 0, 0)], 59000, STATE)
        print("         after REDO: lane", hex(dr["lane"][0]), "cur", st_field(dr, 0), "valid", st_field(dr, 2),
              "undone", st_field(dr, 4), "slot", slot_of(dr, 0), "R5", r5(dr), "st", dr["st"][0])
        check("undostep: REDO: T1 back on R5, the whole loop, heard from 58 s",
              dr["lane"][0] == 0x84 and st_field(dr, 4) == 0 and slot_of(dr, 0) == 132 and r5(dr) == r5(dp),
              f"lane {dr['lane'][0]:#x}, undone {st_field(dr, 4)}, slot {slot_of(dr, 0)}, R5 {r5(dr)}")

    if run("recundo"):
        lines = FREE + [cc(11000, 0, 127), cc(11100, 0, 0), cc(19000, 0, 127), cc(19100, 0, 0),
                        cc(28000, 0, 127), cc(29500, 0, 0)]
        d, _ = boot("recundo", lines, 29300, STATE)
        check("recundo: REC held 1 s: UNDO, T1 back on R1, idle, the pedal still down",
              d["lane"][0] == 0x80 and st_field(d, 0) == 0 and st_field(d, 4) == 1 and d["st"][0] == 0,
              f"lane {d['lane'][0]:#x}, cur {st_field(d, 0)}, undone {st_field(d, 4)}, st {d['st'][0]}")

    if run("undocut"):
        lines = FREE + [cc(11000, 0, 127), cc(11100, 0, 0), cc92(20000, 0, 127), cc92(20100, 0, 0)]
        d0, _ = boot("undocut_0", lines[:-2], 20500, STATE)
        d, _ = boot("undocut", lines, 20500, STATE)
        check("undocut: R5's recorder stopped by UNDO", d0["voice"][0xA8 * 4 + 1] != 0 and d["voice"][0xA8 * 4 + 1] == 0,
              f"T5 recorder byte without UNDO {d0['voice'][0xA8 * 4 + 1]}, with {d['voice'][0xA8 * 4 + 1]}")
        check("undocut: T1 on R1, overdub off", d["lane"][0] == 0x80 and st_field(d, 0) == 0 and d["st"][0] == 0
              and st_field(d, 1) == 0, f"lane {d['lane'][0]:#x}, cur {st_field(d, 0)}, st {d['st'][0]}")

    def shot(tag):                                     # the screen at the quit, as a PNG beside the dumps
        subprocess.run([str(PY), str(ROOT / "tools/emu/lcd_view.py"), str(OUT / f"{tag}.lcd"),
                        "--png", str(OUT / f"{tag}.png")], cwd=ROOT, capture_output=True)
        print(f"         screen: {OUT / (tag + '.png')}")

    POP = {"take": (FREE[:2], 5000, 1), "armed": (FREE + [cc(11000, 0, 127), cc(11100, 0, 0)], 12500, 2),
           "over": (FREE + [cc(11000, 0, 127), cc(11100, 0, 0)], 21000, 3),
           "end": (FREE + [cc(11000, 0, 127), cc(11100, 0, 0), cc(19000, 0, 127), cc(19100, 0, 0)], 21000, 4)}
    for name, (lines, ms, want) in POP.items():
        if run(f"pop{name}"):
            d, _ = boot(f"pop{name}", lines, ms, dict(STATE, pop=(sym["fl_pop"], 8)), lcd=True)
            shot(f"pop{name}")
            check(f"pop{name}: T1's popup open, showing state {want}",
                  u32(d["pop"]) != 0 and d["pop"][7] & 7 == want and (d["pop"][7] >> 3) & 7 == 0,
                  f"fl_pop {u32(d['pop']):#x}, key {u32(d['pop'], 4):#x}")
    if run("popundo"):
        od = FREE + [cc(11000, 0, 127), cc(11100, 0, 0), cc(19000, 0, 127), cc(19100, 0, 0)]
        d, _ = boot("popundo", od + [cc92(28000, 0, 127), cc92(28100, 0, 0)], 28500,
                    dict(STATE, pop=(sym["fl_pop"], 8)), lcd=True)
        shot("popundo")
        pkey = u32(d["pop"], 4)
        check("popundo: UNDO shown big in T1's popup (no stock toast)", u32(d["pop"]) != 0 and pkey >> 31 == 1
              and (pkey >> 8) & 0xff == 16 and pkey & 0xff == 0, f"fl_pop {u32(d['pop']):#x}, key {pkey:#x}")

    if run("playentry"):
        cfg = sym["fl_cfg"]
        pokes = f"1000 poke {cfg + 581:#x}=1;{sym['fl_qplay']:#x}=1"        # A02: T1 PLAY MUTE
        nxt = "12000 midi ba 55 7f"                                          # CC 85: the next pattern, A02
        d1, _ = boot("playentry_a", [pokes] + FREE + [nxt], 17000, dict(STATE, pat=(sym["fl_pat_t"], 8)))
        check("playentry: T1 heard until A02 starts", (u32(d1["mutes"]) >> 8) & 1 == 0 and d1["pat"][0] == 0,
              f"mutes {u32(d1['mutes']):#x}, pattern seen {d1['pat'][0]}")
        d2, _ = boot("playentry_b", [pokes] + FREE + [nxt], 19500, dict(STATE, pat=(sym["fl_pat_t"], 8)))
        check("playentry: T1 enters A02 muted (PLAY MUTE)", (u32(d2["mutes"]) >> 8) & 1 == 1 and d2["pat"][0] == 1,
              f"mutes {u32(d2['mutes']):#x}, pattern seen {d2['pat'][0]}")

    if run("playstop"):
        cfg = sym["fl_cfg"]
        pokes = f"1000 poke {cfg + 581:#x}=2;{sym['fl_qplay']:#x}=1"        # A02: T1 PLAY STOP
        lines = [pokes] + FREE + ["12000 midi ba 55 7f"]
        d, log = boot("playstop", lines, 27500, dict(STATE, stopm=(sym["fl_stopm"], 1), pat=(sym["fl_pat_t"], 8)),
                      watch="0x80004a04,4")
        trigs = [t for t, _, pc in writes(log, 0x80004A04) if pc == "0x4000f790"]   # T1's voice start, each pass
        print(f"         T1's trigs (port clock): {[round(t) for t in trigs]}")
        check("playstop: T1 enters A02 STOPped, not muted", d["stopm"][0] & 1 == 1 and d["pat"][0] == 1
              and (u32(d["mutes"]) >> 8) & 1 == 0, f"fl_stopm {d['stopm'][0]:#x}, pattern {d['pat'][0]}, mutes {u32(d['mutes']):#x}")
        check("playstop: no T1 trig in A02, its first step neither (passes at ~18 and ~26 s)", len(trigs) == 1,
              f"{len(trigs)} trigs")

    if run("fade"):
        lines = FREE + [cc91(12000, 0, 127), cc91(12100, 0, 0)]
        lv = dict(STATE, level=(0x80000C50, 2))
        da, _ = boot("fade_a", lines, 12020, lv)
        check("fade: 20 ms after the press, T1's LEVEL 0, not muted yet (the fade)",
              da["level"][0] == 0 and (u32(da["mutes"]) >> 8) & 1 == 0, f"level {da['level'][0]}, mutes {u32(da['mutes']):#x}")
        db, _ = boot("fade_b", lines, 12200, lv)
        check("fade: 200 ms after, T1 muted, its LEVEL back",
              db["level"][0] != 0 and (u32(db["mutes"]) >> 8) & 1 == 1, f"level {db['level'][0]}, mutes {u32(db['mutes']):#x}")

    if run("edge"):
        cfg = sym["fl_cfg"]
        lines = [f"1000 poke {cfg + 24:#x}=0"] + FREE + [cc(11000, 0, 127), cc(11100, 0, 0)]   # POPUP OFF
        d, _ = boot("edge", lines, 21000, dict(STATE, odub=(sym["fl_odub"], 1)), lcd=True)
        shot("edge")
        check("edge: T1 overdubbing marked at its icon (fl_odub)", d["odub"][0] & 1 == 1, f"fl_odub {d['odub'][0]:#x}")

    if run("popclosed"):
        d, _ = boot("popclosed", FREE + [cc(11000, 0, 127), cc(11100, 0, 0), cc(19000, 0, 127), cc(19100, 0, 0)],
                    28000, dict(STATE, pop=(sym["fl_pop"], 8)))
        check("popclosed: the cut pass over (~26 s): the popup closed", u32(d["pop"]) == 0, f"fl_pop {u32(d['pop']):#x}")

    if run("entryarm"):
        cfg = sym["fl_cfg"]
        pokes = f"1000 poke {cfg + 61:#x}=4"                                # A02: T2 ENTRY ARM
        lines = [pokes] + FREE + ["12000 midi ba 55 7f"]
        d, _ = boot("entryarm", lines, 19000, dict(STATE, pat=(sym["fl_pat_t"], 8)))
        takes = [u32(d["takes"], 4 * t) for t in range(8)]
        check("entryarm: T2 armed by A02's ENTRY, its pass from A02's first step (~18 s)",
              takes[1] + takes[5] >= 1 and d["st"][1] == 3, f"fl_takes {takes}, st {list(d['st'][:4])}")

    def tone_wav(path, seconds):
        """4 channels (A B C D) of a 441 Hz square at -6 dB (+-16,384), 16-bit: an input of a known level.
        A square, not a sine: the mix dump is one frame (16 samples), and a sine's peak in it
        depends on the phase at the dump (15,377 for 16,384 on 28 Oct 2026)."""
        one = b"".join(struct.pack("<hhhh", *[16384 if i < 50 else -16384] * 4) for i in range(100))
        frames = one * int(441 * seconds)                                # 441 Hz: 100 samples a period
        head = b"RIFF" + struct.pack("<I", 36 + len(frames)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 4, 44100, 44100 * 8, 8, 16)
        path.write_bytes(head + b"data" + struct.pack("<I", len(frames)) + frames)

    MIX = 0x800062CC                                                  # the recorder's sources, mixed (RECORDER.md:
    if run("replace"):                                               # 0x40007680, the frame's 16 samples)
        cfg = sym["fl_cfg"]
        wav = OUT / "replace_in.wav"
        tone_wav(wav, 200)                                               # the port feeds it from its first DSP command
        lines = [cc(1500, 1, 127), cc(1600, 1, 0), cc91(2000, 1, 127), cc91(2100, 1, 0), "2500 midi ba 55 7f"]
        dumps = dict(STATE, mix=(MIX, 128))                              # A01 2.0-4.0 s (T2's pass 1, into R6), A02 4-6
        res = {}
        for name, mode in (("arm", 4), ("replace", 12)):                 # A02: T2 ENTRY ARM / REPLACE
            poke = [f"1000 poke {cfg + 61:#x}={mode}"]
            dm, _ = boot(f"replace_{name}_m", poke + lines, 5000, dumps, audio_in=str(wav))
            d, _ = boot(f"replace_{name}", poke + lines, 8800, STATE, audio_in=str(wav))
            peak = max(abs(v) for v in struct.unpack(">64h", dm["mix"]))
            res[name] = (d, dm, peak)
            print(f"         {name}: the recorder's mix at 5 s, peak {peak} (the input 16384); T2 st {dm['st'][1]} then "
                  f"{d['st'][1]}, mutes at 5 s {u32(dm['mutes']):#x}, at 8.8 s {u32(d['mutes']):#x}")
        da, dma, pa = res["arm"]
        dr, dmr, pr = res["replace"]
        check("replace: ENTRY ARM (the control): A02's pass records the input and T2 itself (SRC3, pass 1's loop)",
              pa > 1.6 * 16384 and dma["st"][1] == 3, f"peak {pa}, st {dma['st'][1]}")
        check("replace: ENTRY REPLACE: A02's pass records the input only (its trig without SRC3), not T2",
              abs(pr - 16384) < 1000 and takes_of(dmr, 1) >= 2, f"peak {pr}, T2's passes {takes_of(dmr, 1)}")
        RP = CUR + 8 * 10                                                # FlState rpass[8]
        check("replace: T2 muted during its pass, then idle and heard, on the new loop (R2)",
              (u32(dmr["mutes"]) >> 9) & 1 == 1 and dr["st"][1] == 0 and dr["st"][RP + 1] == 0
              and (u32(dr["mutes"]) >> 9) & 1 == 0 and st_field(dr, 0, 1) == 0,
              f"mutes at 5 s {u32(dmr['mutes']):#x}, then {u32(dr['mutes']):#x}; st {dr['st'][1]}, rpass {dr['st'][RP + 1]}, "
              f"cur {st_field(dr, 0, 1)}")

    if run("slave"):
        d, log = boot("slave", FREE[:2], 4000, STATE, watch=f"{MAILBOX:#x},16", slave=True)
        mail = [v for _, v, _ in writes(log, MAILBOX) if v]
        check("slave: no take", not mail and d["st"][0] == 0, f"mailbox {mail}, st {d['st'][0]}")

    if run("panel"):
        lines = [f"2000 key {T1:#x} down"] + key(2200, UP) + [f"2500 key {T1:#x} up"]
        d1, _ = boot("panel_open", lines, 3000, STATE)
        check("panel: TRACK 1 + UP opens the window", u32(d1["win"]) != 0, f"fl_win {u32(d1['win']):#x}")
        lines += key(3000, DOWN) + key(3300, RIGHT) + key(3600, NO)
        d2, _ = boot("panel", lines, 4200, STATE)
        check("panel: RIGHT on SIGN: 3/4", d2["cfg"][8] == 1, f"sig {list(d2['cfg'][8:12])}")
        check("panel: NO closes", u32(d2["win"]) == 0, f"fl_win {u32(d2['win']):#x}")

    print(f"  verify_free_loop: {'PASS' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
