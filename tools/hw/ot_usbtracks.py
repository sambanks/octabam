#!/usr/bin/env python3
"""USB MIDI TRACKS on a unit: build the test images, write the test project, deploy, switch, run, compare.

    python3 tools/hw/ot_usbtracks.py build                   # NEW, OFF and OLD images + their PEEK addresses
    python3 tools/hw/ot_usbtracks.py project SRC             # the test project from a copy of SRC (SRC untouched)
    python3 tools/hw/ot_usbtracks.py deploy [--vol /Volumes/X]   # .RMX files + project to the card
    python3 tools/hw/ot_usbtracks.py switch NEW|OFF|OLD      # boot that image through REMIX SWITCH
    .venv/bin/python3 tools/hw/ot_usbtracks.py run LABEL --image NEW|OFF|OLD [--stress 60]
    python3 tools/hw/ot_usbtracks.py report LABEL [LABEL ...]

The images (`build`; out/hw/umt/):
  NEW  remixes/test/usb-midi-tracks-hw at this tree: USB MIDI TRACKS as reviewed on #1123, SEND pinned NOTES+CC
  OFF  remixes/test/usb-midi-tracks-hw-off: the same, SEND pinned OFF
  OLD  the same composition at OLD_REV (the PR's first push: channel = track, the encoder kicked in the
       frame interrupt), built in a detached worktree under out/hw/umt/old-tree
Each carries REMOTE (PEEK, disk mode, REMIX SWITCH boots over USB), BRAIN and LOAD METER, and no FRAME GUARD:
a late frame entry is what the stress looks for. Each build's runtime.elf gives the PEEK addresses
(utm_dbg, utm_state, usbmidi_tx_drops), kept in <name>.json beside the .RMX.

The project (`project`): a copy of SRC with every effect NONE, every sample slot on one generated sine
(set/AUDIO/utm_hw.wav), MIDI clock, transport and program change receive on, AUDIO CC OUT = INT (stock
sends no CC 16..21 of its own to muddle the count), and in bank A:
  TRIG CHANNELs 1, 2, 4, 3, 5..8: T3 and T4 swapped, so the channel shows which build read the setting
  pattern 1 (part 1)  T1..T4 FLEX, slots 1..4 (notes 0..3), a trig on every step;
                      T1 RTRG INF RTIM 4 and T2 RTRG INF RTIM 16 locked on every trig: the stress
  pattern 2 (part 2)  the same, but T1 is THRU: a part change that takes T1 off the hooked renderer
                      with a note pending, as the stuck-note fix is about
Every other trig and lock of patterns 1 and 2 is cleared. Written to out/hw/umt/card/UMTSET/UMT.

`deploy` copies the three .RMX files to /BRAIN/REMIXES/ and the set to the card root. With a REMOTE image
running, it enters and leaves USB DISK MODE itself (COMMAND 1 and 2); otherwise put the unit in disk mode
from the panel first and leave it after. The set is refused if a UMTSET without this tool's marker exists.

`switch` rescans and boots the image (COMMAND 4, then 3), waits for the unit to leave USB and come back, and
checks LOAD METER's DSP count advances. The first switch onto a REMOTE image is done by hand: MAIN MENU >
BRAIN > REMIXES > UMT-HW 1.

`run` needs the test project loaded (once, by hand: PROJECT > CHANGE > UMTSET/UMT). Phases:
  stress   START at 120 BPM (clock from this Mac over USB) on pattern 1 for --stress seconds; LOAD METER
           polled 4x a second: the frame interrupt's longest run and a DSP that stops (STALLED)
  part     program change to pattern 2 while playing; 8 s more: T1's pending note must close at the switch
  stop     STOP; 2 s later every note-on has its note-off
then PEEK of the module's counters and pending notes. Every USB MIDI byte from the unit is kept with its
arrival time. Results: out/hw/umt/LABEL.json and a summary; `report` compares labels.

What it judges, per run: STALLED or not; longest frame interrupt (us); per track (by its note) the channels
it came on, note-ons, note-offs, a note left open at the end; CCs per channel; for the part change, how long after the switch T1's last note-off
came; usbmidi_tx_drops; T3's note spacing (a plain trig every 16th: 125 ms) as jitter. OFF expects silence.
Measured on the unit, by this tool: nothing yet.
"""
import argparse
import json
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

OUT = ROOT / "out/hw/umt"
OLD_REV = "94c95f79"                    # PR #1123's head before the review fixes
IMAGES = {                              # key: (remix, image name, build number)
    "NEW": ("test/usb-midi-tracks-hw", "UMT-HW", 1),
    "OFF": ("test/usb-midi-tracks-hw-off", "UMT-OFF", 1),
    "OLD": ("test/usb-midi-tracks-hw", "UMT-OLD", 1),
}
SYMS = ("utm_dbg", "utm_state", "usbmidi_tx_drops")
SET, PROJ, WAV = "UMTSET", "UMT", "utm_hw.wav"
MARKER = "OT_USBTRACKS_FIXTURE.txt"
BPM = 120
STEP_S = 60.0 / BPM / 4                 # a 16th
FLEX, THRU = 1, 2
RTRG, RTIM, SLOTLOCK = 4, 5, 31         # lock bytes: playback page slots 4 and 5; the sample lock
# TRIG CHANNEL per track as the file and RAM hold it (0x8000003f + t, the channel nibble; -1 OFF). T3 and T4
# swapped: NEW sends T3 (note 2) on nibble 3 and T4 (note 3) on nibble 2, OLD (channel = track) the other way.
TRIGCH = (0, 1, 3, 2, 4, 5, 6, 7)
NOTE_OF = {1: 0, 2: 1, 3: 2, 4: 3}       # track -> its note: FLEX slot t, 0-based


def rmx_name(key):
    _, name, build = IMAGES[key]
    return f"{name} {build}.RMX"


def sh(cmd, cwd=ROOT, log=None):
    print("  $", " ".join(str(c) for c in cmd), f"(cwd {cwd})" if cwd != ROOT else "")
    with open(log, "w") if log else open("/dev/null", "w") as f:
        r = subprocess.run([str(c) for c in cmd], cwd=cwd, stdout=f if log else None, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"failed ({r.returncode}): {' '.join(str(c) for c in cmd)}" + (f"; log {log}" if log else ""))


def symbols(tree):
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    elf = tree / "out/platform/runtime/runtime.elf"
    got = {}
    for line in subprocess.run([nm, str(elf)], capture_output=True, text=True).stdout.splitlines():
        f = line.split()
        if len(f) == 3 and f[2] in SYMS:
            got[f[2]] = int(f[0], 16)
    missing = [s for s in SYMS if s not in got]
    if missing:
        sys.exit(f"{elf}: no {missing}")
    return got


# ---- build ---------------------------------------------------------------------------------------------
OLD_REMIX = '''from remix.schema import Evidence, Level, Pin, Remix

REMIX = Remix(
    name="usb-midi-tracks-hw", image_name="UMT-OLD",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="usb-midi-tracks-hw at the PR's first push (ot_usbtracks.py OLD).",
    modules=("USB", "USB MIDI TRACKS", "REMOTE", "LOAD METER", "BRAIN", "MEMORY", "STORE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS", "COMPRESSOR", "LO-FI", "DJ EQ", "COMB FILTER"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): Pin("OFF")},
)
'''


def build_one(key, tree):
    remix, name, build = IMAGES[key]
    log = OUT / f"build-{key}.log"
    sh(["make", "image", f"REMIX={remix}", f"BUILD={build}"], cwd=tree, log=log)
    src = tree / "out" / rmx_name(key)
    shutil.copy2(src, OUT / rmx_name(key))
    (OUT / f"{key}.json").write_text(json.dumps({"rmx": rmx_name(key), "remix": remix, "tree": str(tree),
                                                 "rev": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=tree,
                                                                       capture_output=True, text=True).stdout.strip(),
                                                 "syms": symbols(tree)}, indent=1))
    print(f"  {key}: {OUT / rmx_name(key)}")


def cmd_build(a):
    OUT.mkdir(parents=True, exist_ok=True)
    for key in ("NEW", "OFF"):
        if key in a.only:
            build_one(key, ROOT)
    if "OLD" in a.only:
        old = OUT / "old-tree"
        if not old.exists():
            sh(["git", "worktree", "add", "--detach", old, OLD_REV])
            for link in ("vendor", ".venv", "downloads"):
                src = ROOT / link
                (old / link).symlink_to(src.resolve() if src.is_symlink() else src)
            (old / "out/raw").mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "out/raw/section_3_MAIN_OS.bin", old / "out/raw/section_3_MAIN_OS.bin")
            sh(["git", "submodule", "update", "--init"], cwd=old)
        d = old / "remixes/test/usb-midi-tracks-hw"
        d.mkdir(parents=True, exist_ok=True)
        (d / "remix.py").write_text(OLD_REMIX)
        build_one("OLD", old)


# ---- the project ---------------------------------------------------------------------------------------
def cmd_project(a):
    import ot_bank as ob
    import ot_fresh
    import ot_project as otp
    import math
    import wave
    src = pathlib.Path(a.src).expanduser()
    setdir = OUT / "card" / SET
    dest = setdir / PROJ
    if setdir.exists():
        shutil.rmtree(setdir)
    setdir.mkdir(parents=True)
    otp.make_clean_project(src, dest)                  # a copy: SRC is only read
    # one sine behind every sample slot (a voice whose file is missing stops at once, retrigs and all)
    audio = setdir / "AUDIO"
    audio.mkdir()
    with wave.open(str(audio / WAV), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 220 * i / 44100)))
                               for i in range(44100 * 3)))
    # MIDI: receive clock, transport and program change (this Mac drives the run); send none of them, and
    # AUDIO CC OUT = INT, so the only USB MIDI from the unit is this module's
    stamp = dict(ot_fresh.STAMP, MIDI_AUDIO_TRK_CC_OUT=1, MIDI_CLOCK_SEND=0, MIDI_TRANSPORT_SEND=0,
                 MIDI_PROGRAM_CHANGE_SEND=0,
                 **{f"MIDI_TRIG_CH{t + 1}": c for t, c in enumerate(TRIGCH)})
    for pw in (dest / "project.work", dest / "project.strd"):   # the working state and its saved twin
        if not pw.is_file():
            continue
        data = pw.read_bytes()
        if not re.search(rb"PATH=", data):
            sys.exit(f"{src}: no sample slot (PATH=) to point at the sine; use a project with samples assigned")
        data = re.sub(rb"PATH=[^\r\n]+", b"PATH=../AUDIO/" + WAV.encode(), data)
        pw.write_bytes(ot_fresh.stamp_settings(data, stamp))

    def part_off(part):                                 # 1-based part; part + 4 is its saved copy
        return otp.PART_BASE + (part - 1) * otp.PART_STRIDE

    def mut(d):
        for part in (1, 2):
            for copy in (part, part + 4):
                for t in range(4):
                    d[part_off(copy) + otp.MTYPE_OFF + t] = THRU if (part == 2 and t == 0) else FLEX
                    d[part_off(copy) + 0x2d3 + t * 5 + otp.SLOT_KIND["flex"]] = t   # slot t + 1
        ptrns = [m.start() for m in re.finditer(rb"PTRN", d)] + [otp.PART_BASE]
        for pat in (0, 1):
            d[ptrns[pat + 1] - 5] = pat                 # pattern 1 -> part 1, pattern 2 -> part 2
            for t in range(8):
                for which in range(ob.NMASKS):
                    ob.set_mask(d, pat, t, 0, which)
                base = ob.trac(pat, t) + ob.LOCKS
                d[base:base + ob.NSTEPS * ob.LOCK_LEN] = bytes([ob.NOLOCK]) * (ob.NSTEPS * ob.LOCK_LEN)
            for t in range(4):
                if pat == 1 and t == 0:
                    continue                            # T1 is THRU in part 2
                ob.set_mask(d, pat, t, 0xffff)          # steps 1..16
                for st in range(16):
                    rec = ob.trac(pat, t) + ob.LOCKS + st * ob.LOCK_LEN
                    if t == 0:
                        d[rec + RTRG], d[rec + RTIM] = 127, 4
                    elif t == 1:
                        d[rec + RTRG], d[rec + RTIM] = 127, 16
    otp._bank_write(dest, 1, mut, guard=False)

    # read it back through the readers the gates use
    pat_part, _ = otp.bank_info(dest, 1)
    d = (dest / "bank01.work").read_bytes()
    ok = pat_part[:2] == [0, 1] and int.from_bytes(d[-2:], "big") == (sum(d[0x10:-2]) & 0xFFFF)
    ok &= all(ob.trigs(d, 0, t) == list(range(16)) for t in range(4)) and ob.trigs(d, 1, 0) == []
    ok &= ob.locks(d, 0, 0)[0] == {RTRG: 127, RTIM: 4} and ob.locks(d, 0, 2) == {}
    ok &= list(d[part_off(1) + otp.MTYPE_OFF:][:4]) == [FLEX] * 4
    ok &= list(d[part_off(2) + otp.MTYPE_OFF:][:4]) == [THRU] + [FLEX] * 3
    ok &= [d[part_off(1) + 0x2d3 + t * 5 + 1] for t in range(4)] == [0, 1, 2, 3]
    if not ok:
        sys.exit("the project did not read back as written -- do NOT use it")
    (setdir / MARKER).write_text(f"written by tools/hw/ot_usbtracks.py from {src.name}; safe to delete\n")
    print(f"project: {dest} (bank A: pattern 1 = stress on part 1, pattern 2 = T1 THRU on part 2)")


# ---- the unit ------------------------------------------------------------------------------------------
def device(wait=0.0):
    import load_meter as lm
    import usb.core
    t0 = time.time()
    while True:
        dev = usb.core.find(idVendor=0x1935, idProduct=0x0002, backend=lm.libusb_backend())
        if dev is not None or time.time() - t0 >= wait:
            return dev
        time.sleep(0.5)  # waits for: the unit to enumerate


def remote(dev):
    import ot_events as ev
    return ev.unit_command(dev), (lambda off, n: bytes(dev.ctrl_transfer(0xc0, 0x5a, off, 0, n, timeout=1000))), \
        ev.unit_peek(dev)


def card_volume(given):
    if given:
        return pathlib.Path(given)
    for v in pathlib.Path("/Volumes").iterdir():
        if (v / "BRAIN").is_dir() or v.name.upper().startswith("OCTATRACK"):
            return v
    return None


def cmd_deploy(a):
    import ot_events as ev
    files = [OUT / rmx_name(k) for k in IMAGES if (OUT / rmx_name(k)).is_file()]
    if not files:
        sys.exit("nothing built: run `build` first")
    if not (OUT / "card" / SET / PROJ / "project.work").is_file():
        sys.exit("no project: run `project SRC` first")
    vol, dev, entered = card_volume(a.vol), None, False
    if vol is None:
        dev = device()
        if dev is None:
            sys.exit("no card mounted and no unit on USB")
        cmd1, _, _ = remote(dev)
        try:
            entered = ev.command(cmd1, ev.CMD_DISK_ENTER)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"the image has no REMOTE ({type(e).__name__}): put the unit in USB DISK MODE from the panel")
        print("  disk mode entered; waiting for the card")
        t0 = time.time()
        while vol is None and time.time() - t0 < 60:
            time.sleep(1.0)  # waits for: macOS to mount the card
            vol = card_volume(a.vol)
        if vol is None:
            sys.exit("the card did not mount within 60 s")
    print(f"  card: {vol}")
    rdir = vol / "BRAIN" / "REMIXES"
    rdir.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, rdir / f.name)
        print(f"  {f.name} -> {rdir}")
    tgt = vol / SET
    if tgt.exists() and not (tgt / MARKER).is_file():
        sys.exit(f"{tgt} exists and is not this tool's: refusing to touch it")
    if tgt.exists():
        shutil.rmtree(tgt)
    shutil.copytree(OUT / "card" / SET, tgt)
    print(f"  {SET}/{PROJ} -> {vol}")
    subprocess.run(["sync"])
    if entered:
        subprocess.run(["diskutil", "unmount", str(vol)], check=True)
        cmd1, _, _ = remote(device(10))
        print("  leaving disk mode:", ev.command(cmd1, ev.CMD_DISK_LEAVE))
    else:
        print("  eject the card in Finder, then leave USB DISK MODE on the unit")


def wait_healthy(timeout=60):
    import load_meter as lm
    t0 = time.time()
    while time.time() - t0 < timeout:
        dev = device(2)
        if dev is not None:
            try:
                ok, why = lm.healthy(dev)
                if ok:
                    return dev
            except Exception:  # noqa: BLE001
                pass
        time.sleep(1.0)  # waits for: the unit booting and its DSP running
    return None


def cmd_switch(a):
    import ot_events as ev
    dev = device()
    if dev is None:
        sys.exit("no unit on USB")
    cmd1, ctrl, peek1 = remote(dev)
    ev.command(cmd1, ev.CMD_SCAN)
    time.sleep(2.0)  # waits for: the rescan in the UI task
    name = rmx_name(a.image)
    names = ev.remixes(ctrl, peek1)
    if name.encode() not in names:
        sys.exit(f"{name} is not in the unit's list {names}: run `deploy`")
    if not ev.boot(cmd1, ctrl, peek1, name):
        sys.exit("the unit refused the boot")
    print(f"  booting {name}")
    t0 = time.time()
    while device() is not None and time.time() - t0 < 20:
        time.sleep(0.5)  # waits for: the unit to leave USB at its reset
    if wait_healthy(90) is None:
        sys.exit("the unit did not come back healthy within 90 s")
    print("  up, DSP running")


# ---- the run -------------------------------------------------------------------------------------------
def midi_port(kind):
    import ot_midi
    names = [n for n, _ in ot_midi.endpoints(kind)]
    hit = [n for n in names if "octatrack" in n.lower()]
    if not hit:
        sys.exit(f"no Octatrack MIDI {kind} among {names}")
    return hit[0]


def peek_state(peek1, syms):
    import ot_events as ev
    dbg = struct.unpack(">5I", ev.peek(peek1, syms["utm_dbg"], 20))
    state = ev.peek(peek1, syms["utm_state"], 32)
    drops = struct.unpack(">I", ev.peek(peek1, syms["usbmidi_tx_drops"], 4))[0]
    return {"second_calls": dbg[0], "starts": dbg[1], "notes": dbg[3], "repeats": dbg[4],
            "pending": [t for t in range(8) if state[4 * t]], "drops": drops}


def cmd_run(a):
    import load_meter as lm
    import ot_midi
    meta = json.loads((OUT / f"{a.image}.json").read_text())
    dev = wait_healthy(10)
    if dev is None:
        sys.exit("no healthy unit on USB")
    _, _, peek1 = remote(dev)
    before = peek_state(peek1, meta["syms"])
    msgs, lock = [], threading.Lock()
    t0 = time.monotonic()

    def got(data):
        now = time.monotonic() - t0
        with lock:
            msgs.append((now, bytes(b for b in data if b not in (0xF8, 0xFE))))
    inp = ot_midi.In(midi_port("src"), got)            # held: its callback must outlive the run
    out = ot_midi.Out(midi_port("dst"))
    stop = threading.Event()
    marks = {}

    def clock():
        period = 60.0 / (BPM * 24)
        tc, n = time.monotonic(), 0
        while not stop.is_set():
            out.send([0xF8]); n += 1
            dt = tc + n * period - time.monotonic()
            if dt > 0:
                time.sleep(dt)  # waits for: MIDI clock pacing

    def play(seconds, phase):
        t1, still, last = time.monotonic(), 0, None
        longest = []
        while time.monotonic() - t1 < seconds:
            inp.pump(0.25)
            try:
                r = lm.read_fast(dev)
            except Exception as e:  # noqa: BLE001
                return longest, f"no answer in {phase} ({type(e).__name__})"
            longest.append(round(r["cf"]["longest_us"], 1))
            still = still + 1 if r["dsp"]["seq"] == last else 0
            last = r["dsp"]["seq"]
            if still >= 3:
                return longest, f"STALLED in {phase} at {time.monotonic() - t0:.2f} s"
        return longest, "ok"

    res = {"label": a.label, "image": a.image, "rmx": meta["rmx"], "rev": meta["rev"],
           "t": time.strftime("%Y-%m-%d %H:%M:%S"), "before": before}
    out.send([0xC0, 0])                                 # pattern 1 (program change, channel 1)
    time.sleep(1.0)  # waits for: the pattern change while stopped (4.5..5.9 ms measured; margin)
    th = threading.Thread(target=clock); th.start()
    time.sleep(0.5)  # waits for: the unit to lock to the clock before START
    marks["start"] = time.monotonic() - t0
    out.send([0xFA])
    res["stress_longest_us"], verdict = play(a.stress, "stress")
    if verdict == "ok":
        marks["pc"] = time.monotonic() - t0
        out.send([0xC0, 1])                             # pattern 2: part 2, T1 THRU, at pattern 1's end
        res["part_longest_us"], verdict = play(8.0, "part")
    marks["stop"] = time.monotonic() - t0
    out.send([0xFC])
    stop.set(); th.join()
    t1 = time.monotonic()
    while time.monotonic() - t1 < 2.0:
        inp.pump(0.25)
    res["verdict"] = verdict
    res["marks"] = marks
    try:
        res["after"] = peek_state(peek1, meta["syms"])
    except Exception as e:  # noqa: BLE001
        res["after"] = f"{type(e).__name__}: {e}"
    with lock:
        res["midi"] = [(round(t, 4), m.hex()) for t, m in msgs if m]
    res["judged"] = judge(res)
    (OUT / f"{a.label}.json").write_text(json.dumps(res, indent=1))
    show(res)
    print(f"  -> {OUT / (a.label + '.json')}")


def events(res):
    """[(t, status, d1, d2)]: the channel messages in the bytes the unit sent, running status resolved.
    Realtime bytes (F8..FF) were dropped on arrival; nothing here sends SysEx or system common."""
    evs, run, need, got = [], None, 0, []
    for t, h in res["midi"]:
        for x in bytes.fromhex(h):
            if x >= 0xF8:
                continue                                # realtime: may sit inside a message
            if x & 0x80:
                run, got = (x, []) if x < 0xF0 else (None, [])
                need = 1 if run is not None and run & 0xE0 == 0xC0 else 2
                continue
            if run is None:
                continue
            got.append(x)
            if len(got) == need:
                evs.append((t, run, got[0], got[1] if need == 2 else 0))
                got = []
    return evs


def judge(res):
    """Per track (by its note: T1..T4 play slots 1..4, notes 0..3): the channels it came on, note-ons,
    note-offs, notes left open; CCs per channel; the part change; T3's note spacing."""
    evs = events(res)
    tr = {t: {"ch": set(), "on": 0, "off": 0, "open": None, "ons": [], "last_off": None} for t in NOTE_OF}
    by_note = {n: t for t, n in NOTE_OF.items()}
    ccs, other = {}, 0
    for t, st, d1, d2 in evs:
        k, ch = st & 0xF0, st & 0x0F
        if k == 0xB0:
            ccs[ch + 1] = ccs.get(ch + 1, 0) + 1
            continue
        if k not in (0x80, 0x90) or d1 not in by_note:
            other += 1
            continue
        p = tr[by_note[d1]]
        p["ch"].add(ch + 1)
        if k == 0x90 and d2:
            p["on"] += 1; p["open"] = t; p["ons"].append(t)
        else:
            p["off"] += 1; p["open"] = None; p["last_off"] = t
    j = {"tracks": {f"T{t}": {"channels": sorted(p["ch"]), "on": p["on"], "off": p["off"],
                              "open_at_end": p["open"] is not None} for t, p in tr.items()},
         "cc_per_channel": ccs, "other_messages": other}
    pc = res["marks"].get("pc")
    if pc is not None:
        # pattern 2 starts at pattern 1's end: the first bar line after the PC, counted from START
        bar = 16 * STEP_S
        switch = res["marks"]["start"] + bar * (int((pc - res["marks"]["start"]) / bar) + 1)
        p = tr[1]
        j["part"] = {"switch_s": round(switch, 3),
                     "t1_note_ons_after_switch": len([x for x in p["ons"] if x > switch + 0.05]),
                     "t1_last_off_after_switch_ms": None if p["last_off"] is None
                     else round(1000 * (p["last_off"] - switch), 1),
                     "t1_open_at_end": p["open"] is not None}
    ons = tr[3]["ons"]
    d = [1000 * (y - x) for x, y in zip(ons, ons[1:]) if 0.06 < y - x < 0.2]
    if d:
        mean = sum(d) / len(d)
        j["t3_spacing_ms"] = {"n": len(d), "mean": round(mean, 2), "min": round(min(d), 2), "max": round(max(d), 2),
                              "sd": round((sum((x - mean) ** 2 for x in d) / len(d)) ** 0.5, 2)}
    return j


def show(res):
    j = res["judged"]
    lo = res.get("stress_longest_us") or [0]
    print(f"{res['label']} [{res['image']} {res['rev']}]: {res['verdict']}; longest frame interrupt "
          f"{max(lo):.1f} us (stress), {max(res.get('part_longest_us') or [0]):.1f} us (part change)")
    for t, c in j["tracks"].items():
        print(f"  {t}: channel(s) {c['channels']}, {c['on']} on, {c['off']} off, open at the end {c['open_at_end']}")
    print(f"  CCs per channel {j['cc_per_channel']}; other messages {j['other_messages']}")
    if "part" in j:
        print(f"  part change: {j['part']}")
    if "t3_spacing_ms" in j:
        print(f"  T3 note spacing (125 ms nominal): {j['t3_spacing_ms']}")
    a = res.get("after")
    if isinstance(a, dict):
        print(f"  unit: notes {a['notes']}, repeats {a['repeats']}, pending {a['pending']}, usbmidi_tx_drops {a['drops']}")
    if res["image"] == "OFF":
        n = sum(c["on"] for c in j["tracks"].values()) + sum(j["cc_per_channel"].values())
        print(f"  OFF: {'silent' if n == 0 else f'NOT silent: {n} note-ons and CCs'}")


def cmd_report(a):
    for label in a.labels:
        show(json.loads((OUT / f"{label}.json").read_text()))
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--only", default="NEW,OFF,OLD", type=lambda s: s.split(","))
    p = sub.add_parser("project"); p.add_argument("src")
    d = sub.add_parser("deploy"); d.add_argument("--vol")
    s = sub.add_parser("switch"); s.add_argument("image", choices=IMAGES)
    r = sub.add_parser("run"); r.add_argument("label"); r.add_argument("--image", choices=IMAGES, required=True)
    r.add_argument("--stress", type=float, default=60.0)
    rp = sub.add_parser("report"); rp.add_argument("labels", nargs="+")
    a = ap.parse_args()
    {"build": cmd_build, "project": cmd_project, "deploy": cmd_deploy, "switch": cmd_switch,
     "run": cmd_run, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
