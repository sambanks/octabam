#!/usr/bin/env python3
"""CHORDS FACTORY under the ColdFire port: the atelier page.

    python3 tools/verify/verify_chords.py <remix>

A fresh project made by the image gets midi_fixture's MIDI tracks (track 1
on channel 1). Each run is a timed panel script from a fresh boot (MIDI,
then the keys below); ch_bank, the pages' windows and the MIDI OUT are read
back at the end.

- src1 / src2 / src3: SRC pressed again once, twice, three times on MIDI
  NOTE (PAGES): CHORDS' page, then none, then CHORDS' again. With TURING
  MACHINE in the remix (a PAGES client registered before CHORDS) its page
  comes first: TURING's, CHORDS', none; the other runs then open CHORDS
  with two SRC taps instead of one.
- build: on CHORDS, B +4, A +2: slot 1 is Dm7 built close at octave 4
  (50 53 57 60); trig 2, A +7, B +2: slot 2 is G7 voiced from it (LEAD,
  the smoothest: 50 53 55 59); F +1: the second answer (47 53 55 62). Then
  trig 2 held 1.5 s: G7's four notes on on channel 1 while held, off when
  let go; every note-on matched by its note-off.
- voix: slot 1 Dm7 built, F +1 on it (no chord before: nothing, a toast);
  trig 2, A +7, B +2 (G7, LEAD), C +1 (INV: built again), F +1: LEAD again
  from the smoothest answer, F +1: the second (47 53 55 62, LEAD 2/n) --
  F turns whatever made the chord, when the slot before holds one.
- keys: FUNC held, trigs 1, 5, 8: slot 1 is 48 52 55 (C, EDIT); FUNC + A
  -1: its bass a semitone down (47); FUNC + E: the bass ROOT flag.
- trigs: in GRID RECORDING (REC), the bank's RAM after trigs 1-16 tapped
  on the page is the RAM of the page opened alone: the trig keys edit no
  step under the page; control: the same taps with no page do change it
  (the measurement sees a trig edit).
- mode: Dm7 and G7 built in slots 1 and 2, the page closed, CHORDS chosen
  in FUNC + DOWN's list (DOWN three times): the trig mode is 2; trig 1
  tapped sends Dm7's four notes on channel 1 and their four note-offs
  (stock's CHROMATIC note, once a voice); trig 2 held to the end sends G7's
  and leaves them on; the trig LEDs: slot 1 green, slot 2 yellow, the rest
  dark.
- collide: slot 2 holds D#m7 as 42 49 58 63 (F#3 and A#4, 16 apart:
  stock's CHROMATIC note keeps both in one cell, note % 16), CHORDS, trig 2
  tapped: four note-ons and four note-offs, 42's included (image 36 left
  F#3 on).
- leave: trig 1 held (Dm7) while FUNC + DOWN's list moves to CHROMATIC:
  the chord's four note-offs are sent (the release no longer reaches
  CHORDS).
- live: Dm7 in slot 1 (poked), CHORDS, live recording (REC held, PLAY),
  trig 1 played on bar 1: the pattern's next passes play D F A C at that
  step on their own; the step's locks are NOTE 50, NOT2-4 64 + 3 / 7 / 10
  (stock's recorder fed one event per voice, from a record of its own).
- pick: Dm7 and G7 in slots 1 and 2 (poked), GRID RECORDING, trig 3 held,
  UP: the chooser opens (its window and layer); DOWN, YES: step 3's locks
  are G7's (NOTE 50, NOT2-4 67 69 73), in the bank's RAM and in its
  battery-backed copy; VEL and LEN as placing the trig left them (stock
  locks VEL 90, LEN none); the chooser closed, both layers popped once the
  trig is let go. Then trig 3 held and UP again: the window opens with G7
  marked (the step's chord), and NO leaves the locks as they were.
- arp: Dm7 in slot 1, CHORDS, ARP MODE turned on (encoder C on the ARP
  page), trig 1 held 3 s with the sequencer stopped: the arpeggiator plays
  the chord's notes one at a time (at least eight note-ons, only D F A C,
  not four at once): stock's arpeggiator takes the chord as keys held.
- hold: B +1 alone: the chord sounds for HOLD_TICKS of the display loop;
  its length in frames is printed beside a sequencer step's (120 BPM: 125
  ms) to calibrate HOLD_TICKS to about a second.

chords.work (STORE client 8), MKII: slot 1 of bank 1 built on the page,
then SAVE PROJECT: chords.work and chords.strd hold 'CHRD' version 1, 3584
bytes, their CRC-32 and that slot; the saved card booted again has it back.
The same edits with no save write no file.

The engine's arithmetic is modules/chords/verify.py's (host tests).
"""
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/verify"))
sys.path.insert(0, str(ROOT / "tools/emu"))
sys.path.insert(0, str(ROOT / "tools/panel"))
from remix import registry  # noqa: E402
import emu_card  # noqa: E402
import midi_fixture  # noqa: E402
import page_port as vt  # noqa: E402
from panel_link import PanelLink  # noqa: E402

FUNC, SRC, REC = 0x2d, 0x22, 0x29
PROJECT = "CHORDS"                         # the card's project
SLOT = 14                                   # sizeof(ChSlot): n, notes[4], root type inv spread oct lead mode degree flags
SLOTS = 16
BANK_RAM, BANK_SIZE = 0x400e21e0, 0x9b340   # bank 1's RAM (MIDI_TRACKS.md: B)
MODE_BUILT, MODE_LEAD, MODE_EDIT = range(3)
HOLD_FRAMES_WANT = (0.7, 1.5)               # seconds an edit sounds: the calibration's window


def tap(t, code):
    return vt.tap(t, code)


def enc(t, n, d):
    return [(t, f"enc {n} {d & 0xff}")]


def chords(t0=2200, src=2):
    out = []
    for i in range(src):
        out += tap(t0 + 500 * i, SRC)
    return out


RUNS = {
    "src1": chords(src=1),
    "src2": chords(src=2),
    "src3": chords(src=3),
    "build": chords() + enc(3400, 1, 4) + enc(3700, 0, 2) + tap(4200, 0x01) + enc(4600, 0, 7)
    + enc(4900, 1, 2) + enc(5300, 5, 1) + [(7000, "key 0x01 down"), (8500, "key 0x01 up")],
    "voix": chords() + enc(3400, 1, 4) + enc(3700, 0, 2) + enc(4000, 5, 1) + tap(4300, 0x01) + enc(4600, 0, 7)
    + enc(4900, 1, 2) + enc(5200, 2, 1) + enc(5600, 5, 1) + enc(6000, 5, 1),
    "keys": chords() + [(3400, f"key {FUNC:#x} down")] + tap(3600, 0x00) + tap(3900, 0x04) + tap(4200, 0x07)
    + enc(4600, 0, -1) + enc(4900, 4, 1) + [(5300, f"key {FUNC:#x} up")],
    "open": tap(2100, REC) + chords(),
    "trigs": tap(2100, REC) + chords() + [x for k in range(16) for x in tap(3400 + 200 * k, k)],
    "control": tap(2100, REC) + [x for k in range(16) for x in tap(3400 + 200 * k, k)],
    "hold": chords() + enc(3400, 1, 1) + [(8000, "wait")],
    "mode": chords() + enc(3400, 1, 4) + enc(3700, 0, 2) + tap(4200, 0x01) + enc(4600, 0, 7) + enc(4900, 1, 2)
    + tap(5600, SRC) + [(6400, f"key {FUNC:#x} down")] + tap(6600, 0x20) + tap(6900, 0x20) + tap(7200, 0x20)
    + [(7600, f"key {FUNC:#x} up")] + tap(8600, 0x00) + [(9600, "key 0x01 down"), (11000, "wait")],
}
RUNS["arp"] = (chords() + enc(3400, 1, 4) + enc(3700, 0, 2) + tap(4200, SRC) + [(5000, f"key {FUNC:#x} down")]
               + tap(5200, 0x20) + tap(5500, 0x20) + tap(5800, 0x20) + [(6200, f"key {FUNC:#x} up")]
               + tap(6800, 0x23) + enc(7200, 2, 8) + enc(7500, 2, 8)
               + [(9000, "key 0x00 down"), (12000, "key 0x00 up")])
RUNS["collide"] = ([(2600, f"key {FUNC:#x} down")] + tap(2800, 0x20) + tap(3100, 0x20) + tap(3400, 0x20)
                   + [(3800, f"key {FUNC:#x} up"), (5000, "key 0x01 down"), (6000, "key 0x01 up")])
COLLIDE = [42, 49, 58, 63]
# trig 1 held while FUNC + UP leaves CHORDS for CHROMATIC: Dm7's notes end there, not at the release
RUNS["leave"] = (chords() + enc(3400, 1, 4) + enc(3700, 0, 2) + tap(4200, SRC) + [(5000, f"key {FUNC:#x} down")]
                 + tap(5200, 0x20) + tap(5500, 0x20) + tap(5800, 0x20) + [(6200, f"key {FUNC:#x} up")]
                 + [(7000, "key 0x00 down"), (7600, f"key {FUNC:#x} down")] + tap(7800, 0x20) + tap(8100, 0x33)
                 + [(8500, f"key {FUNC:#x} up"), (9500, "key 0x00 up")])
RUNS["live"] = ([(2600, f"key {FUNC:#x} down")] + tap(2800, 0x20) + tap(3100, 0x20) + tap(3400, 0x20)
                + [(3800, f"key {FUNC:#x} up"), (4500, "key 0x29 down")] + tap(4700, 0x28)
                + [(5000, "key 0x29 up"), (5600, "key 0x00 down"), (5900, "key 0x00 up"), (16000, "wait")])
MIDI_TRACK1 = BANK_RAM + 0x48d0                    # pattern 1's MIDI track 1 (STEP_LOCKS.md)
CS1_TRACK1 = 0x1001614e + 0x48d0                   # its battery-backed copy
RUNS["pick"] = (tap(2600, 0x29) + [(3200, "key 0x02 down")] + tap(3600, 0x33) + tap(4200, 0x20) + tap(4600, 0x31)
                + [(5200, "key 0x02 up"), (6000, "key 0x02 down")] + tap(6400, 0x33) + tap(6900, 0x32)
                + [(7400, "key 0x02 up")])
EXTRA = {"mode": ("--serial-out", "mode-panel")}
TRIG_MODE = 0x460d16f0


def run(out, image, sym, name, script_lines, card=None, extra=()):
    script = out / f"{name}.script"
    lines = [x for x in script_lines if x[1] != "wait"] + [x for x in script_lines if x[1] == "wait"][:0]
    last = max(t for t, _x in script_lines)
    lines.append((last, "key 0x32 up"))     # a harmless line at the end time (the script quits 1.5 s after)
    vt.page_script(script, sorted(lines))
    dumps = [f"{sym['ch_bank']:#x},{SLOT * SLOTS * 16}={out}/{name}.bank",
             f"{sym['ch_win']:#x},4={out}/{name}.chwin"]
    if "tm_win" in sym:
        dumps.append(f"{sym['tm_win']:#x},4={out}/{name}.tmwin")
    if name == "mode":
        dumps.append(f"{TRIG_MODE:#x},4={out}/{name}.trigmode")
    if name == "pick":
        b = sym["ch_bank"]
        pk = [f"{b:#x}=4"] + [f"{b + 1 + i:#x}={n}" for i, n in enumerate((50, 53, 57, 60))] + [f"{b + 11:#x}={MODE_EDIT}"]
        pk += [f"{b + SLOT:#x}=4"] + [f"{b + SLOT + 1 + i:#x}={n}" for i, n in enumerate((50, 53, 55, 59))]
        pk += [f"{b + SLOT + 11:#x}={MODE_EDIT}"]
        extra = ("--poke", ";".join(pk))
        dumps.append(f"{MIDI_TRACK1:#x},{0x30 + 64 * 32}={out}/{name}.trk")
        dumps.append(f"{CS1_TRACK1:#x},{0x30 + 64 * 32}={out}/{name}.cs1")
        for k in ("ch_pk_win", "ch_up_pushed", "ch_pk_pushed"):
            dumps.append(f"{sym[k]:#x},1={out}/{name}.{k}")
    if name in ("live",):
        b = sym["ch_bank"]                          # slot 1 of bank 1: Dm7, EDIT
        extra = ("--poke", ";".join([f"{b:#x}=4"] + [f"{b + 1 + i:#x}={n}" for i, n in enumerate((50, 53, 57, 60))]
                                    + [f"{b + 11:#x}={MODE_EDIT}"]))
        dumps.append(f"{MIDI_TRACK1:#x},{0x30 + 64 * 32}={out}/{name}.trk")
    if name == "collide":
        b = sym["ch_bank"] + SLOT                   # slot 2 of bank 1: n, the notes, mode EDIT
        extra = ("--poke", ";".join([f"{b:#x}=4"] + [f"{b + 1 + i:#x}={n}" for i, n in enumerate(COLLIDE)]
                                    + [f"{b + 11:#x}={MODE_EDIT}"]))
    if name in ("open", "trigs", "control"):
        dumps.append(f"{BANK_RAM:#x},{BANK_SIZE}={out}/{name}.ram")
    cmd = [str(ROOT / "out/emu/ot_emu"), "--image", str(image), "--card", str(card or out / "card.img"),
           "--set", "OCTABAM", "--project", PROJECT, "--load-ms", "90000", "--mkii",
           "--live-script", str(script), "--mem-dump", ";".join(dumps), "--midi-out", str(out / f"{name}.midi"),
           *[str(out / x) if x.endswith("-panel") else x for x in EXTRA.get(name, extra)]]
    with (out / f"{name}.log").open("w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    return rc


def slot(bank, i, b=0):
    s = bank[(b * SLOTS + i) * SLOT:(b * SLOTS + i + 1) * SLOT]
    return {"notes": list(s[1:1 + s[0]]), "root": s[5], "type": s[6], "inv": s[7], "spread": s[8], "oct": s[9],
            "lead": s[10], "mode": s[11], "degree": s[12], "flags": s[13]}


def frames(path):
    """[(frame, byte)] from ot_emu's .frames file."""
    out = []
    for line in path.read_text().split("\n"):
        if line.strip():
            f, b = line.split()
            out.append((int(f), int(b, 16)))
    return out


def timed_notes(path):
    """[(frame, kind, ch, note)] from the bytes and their frames (no running status from stock's sender
    in a 3-byte send; status bytes restart a message)."""
    out, status, data, at = [], None, [], 0
    for f, b in frames(path):
        if b >= 0xf8:
            continue
        if b & 0x80:
            status, data, at = b, [], f
            continue
        if status is None:
            continue
        data.append(b)
        if len(data) == 2:
            if status & 0xf0 in (0x80, 0x90):
                out.append((at, "on" if status & 0xf0 == 0x90 and data[1] else "off", (status & 15) + 1, data[0]))
            data = []
    return out


def step_frames(out, image, sym):
    """Frames per sequencer step at 120 BPM: a plain run (page_port.play), track 1's trigs on
    steps 2 and 4."""
    vt.play(out, image, "clock", "", PROJECT)
    ons = [f for f, kind, ch, _n in timed_notes(out / "clock.midi.frames") if kind == "on" and ch == 1]
    firsts = []
    for f in ons:                           # a trig's voices go out together: keep each trig's first
        if not firsts or f - firsts[-1] > 50:
            firsts.append(f)
    return (firsts[1] - firsts[0]) / 2 if len(firsts) >= 2 else None


def persist(out, image, sym):
    d = out / "persist"
    d.mkdir()
    edits = chords(src=2 if "tm_win" in sym else 1) + enc(3400, 1, 4) + enc(3700, 0, 2)   # CHORDS: SRC's 2nd page beside TURING
    save, t = [], 4600
    for key, gap in ((0x1c, 1000), (0x21, 700), (0x20, 500), (0x31, 1100), (0x31, 30000)):
        save += tap(t, key)
        t += 40 + gap
    save += tap(t, 0x32)
    want = {"notes": [50, 53, 57, 60], "root": 2, "type": 4, "mode": MODE_BUILT}

    def boot(tag, card, lines, keep):
        script = d / f"{tag}.script"
        vt.page_script(script, lines)
        cmd = [ROOT / "out/emu/ot_emu", "--image", image, "--card", card, "--set", "OCTABAM", "--project", PROJECT,
               "--load-ms", "90000", "--mkii", "--live-script", script,
               "--mem-dump", f"{sym['ch_bank']:#x},{SLOT * SLOTS * 16}={d / (tag + '.bank')}"]
        if keep:
            cmd += ["--card-out", d / f"{tag}.img"]
        with open(d / f"{tag}.log", "w") as f:
            return subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode

    bad = []
    with ThreadPoolExecutor(2) as pool:
        rc = list(pool.map(lambda a: boot(*a), (("saved", out / "card.img", edits + save, True),
                                                ("unsaved", out / "card.img", edits, True))))
    if rc != [0, 0]:
        bad.append(f"the save and the unsaved run exited {rc}")
    files = emu_card.extract_image((d / "saved.img").read_bytes())
    for ext in ("work", "strd"):
        f = next((v for k, v in files.items() if k.lower().endswith(f"/{PROJECT.lower()}/chords.{ext}")), b"")
        pay = f[16:]
        ok = (len(f) == 16 + 3584 and f[:12] == b"CHRD\0\0\0\1\0\0\x0e\0"
              and struct.unpack(">I", f[12:16])[0] == zlib.crc32(pay)
              and list(pay[0:5]) == [4, 50, 53, 57, 60] and pay[5] == 2 and pay[6] == 4)
        if not ok:
            bad.append(f"chords.{ext}: {len(f)} B {f[:16].hex()} slot 1 {list(pay[:SLOT])}")
    uf = emu_card.extract_image((d / "unsaved.img").read_bytes())
    if any(k.lower().endswith(f"/{PROJECT.lower()}/chords.work") for k in uf):
        bad.append("the unsaved run wrote chords.work")
    rc = boot("reboot", d / "saved.img", [(2200, "key 0x32 down"), (2240, "key 0x32 up")], False)
    s = slot((d / "reboot.bank").read_bytes(), 0)
    if rc or any(s[k] != v for k, v in want.items()):
        bad.append(f"reboot: exited {rc}, slot 1 {s}")
    print(f"  [{'FAIL' if bad else 'PASS'}] verify_chords: chords.work (SAVE PROJECT writes .work and .strd; "
          f"the saved card boots it back; no save, no file)")
    for line in bad:
        print(f"      {line}")
    return bool(bad)


def main():
    remix = sys.argv[1]
    mods = registry.remix(remix).modules
    if "CHORDS FACTORY" not in mods:
        return 0
    turing = "TURING MACHINE" in mods
    if not turing:          # CHORDS is SRC's first page: chords()'s second SRC tap (2700) would close it
        second = set(tap(2700, SRC))
        RUNS.update({k: [x for x in v if x not in second] for k, v in RUNS.items() if k not in ("src2", "src3")})
    out = ROOT / "out/chords"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, env=env,
                   stdout=subprocess.DEVNULL, check=True)
    image = out / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    nm = subprocess.check_output(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")], text=True)
    sym = {n: int(a, 16) for a, n in re.findall(r"^([0-9a-f]+) [A-Za-z] ((?:ch|tm)_\w+)$", nm, re.M)}
    midi_fixture.fixture(vt.fresh(out, image), out / "project")
    card, _ = emu_card.stage_project(out / "project", "OCTABAM", PROJECT, tree=out / "tree")
    (out / "card.img").write_bytes(card)

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        rcs = dict(zip(RUNS, pool.map(lambda kv: run(out, image, sym, *kv), RUNS.items())))
        clock = pool.submit(step_frames, out, image, sym)
        step = clock.result()

    fails = 0
    for name in RUNS:
        bad = [] if rcs[name] == 0 and "ended on quit" in (out / f"{name}.log").read_text() else [
            f"the run exited {rcs[name]} or the script did not end"]
        bank = (out / f"{name}.bank").read_bytes()
        chwin = int.from_bytes((out / f"{name}.chwin").read_bytes(), "big")
        tmwin = int.from_bytes((out / f"{name}.tmwin").read_bytes(), "big") if turing else 0
        notes = timed_notes(out / f"{name}.midi.frames") if (out / f"{name}.midi.frames").exists() else []
        if name.startswith("src"):
            n = int(name[3])
            want = {1: (1, 0), 2: (0, 1), 3: (0, 0)}[n] if turing else {1: (0, 1), 2: (0, 0), 3: (0, 1)}[n]
            if ((tmwin != 0), (chwin != 0)) != (bool(want[0]), bool(want[1])):
                bad.append(f"TURING {tmwin:#x}, CHORDS {chwin:#x}; want open {want}")
        if name == "voix":
            s1, s2 = slot(bank, 0), slot(bank, 1)
            if s1["notes"] != [50, 53, 57, 60] or s1["mode"] != MODE_BUILT:
                bad.append(f"slot 1 {s1}; want Dm7 50 53 57 60 BUILT, F leaving it")
            if s2["notes"] != [47, 53, 55, 62] or s2["mode"] != MODE_LEAD or s2["lead"] != 1:
                bad.append(f"slot 2 {s2}; want G7 LEAD again from INV's built chord, second answer 47 53 55 62")
        if name == "build":
            s1, s2 = slot(bank, 0), slot(bank, 1)
            if s1["notes"] != [50, 53, 57, 60] or s1["mode"] != MODE_BUILT or (s1["root"], s1["type"]) != (2, 4):
                bad.append(f"slot 1 {s1}; want Dm7 50 53 57 60 BUILT")
            if s2["notes"] != [47, 53, 55, 62] or s2["mode"] != MODE_LEAD or s2["lead"] != 1:
                bad.append(f"slot 2 {s2}; want G7's second answer 47 53 55 62, LEAD")
            held = [x for x in notes if x[0] >= 0]
            # the last four note-ons are the held trig's, on channel 1, and each is let go after
            ons = [x for x in held if x[1] == "on"]
            last = ons[-4:]
            if sorted(n for _f, _k, _c, n in last) != [47, 53, 55, 62] or any(c != 1 for _f, _k, c, _n in last):
                bad.append(f"the held trig sent {last}; want 47 53 55 62 on ch 1")
            open_ = {}
            for f, kind, ch, n in held:
                if kind == "on":
                    if (ch, n) in open_:
                        bad.append(f"ch {ch} note {n} on twice")
                    open_[ch, n] = f
                elif open_.pop((ch, n), None) is None:
                    bad.append(f"ch {ch} note-off {n} with no note-on")
            if open_:
                bad.append(f"notes left on: {sorted(open_)}")
            if last and step:
                offs = [f for f, k, c, n in held if k == "off" and n == last[0][3] and f > last[0][0]]
                if offs:
                    secs = (offs[0] - last[0][0]) / step * 0.125
                    if not 1.2 <= secs <= 1.8:
                        bad.append(f"the trig held 1.5 s sounded {secs:.2f} s")
        if name == "keys":
            s1 = slot(bank, 0)
            if s1["notes"] != [47, 52, 55] or s1["mode"] != MODE_EDIT or s1["flags"] != 1:
                bad.append(f"slot 1 {s1}; want 47 52 55, EDIT, BASS ROOT")
        if name == "trigs":
            a, b = (out / "open.ram").read_bytes(), (out / "trigs.ram").read_bytes()
            diff = [i for i in range(len(a)) if a[i] != b[i]]
            if diff:
                bad.append(f"{len(diff)} bank bytes differ after the trig keys, first at {BANK_RAM + diff[0]:#x}")
        if name == "control":
            a, b = (out / "open.ram").read_bytes(), (out / "control.ram").read_bytes()
            if a == b:
                bad.append("the trig keys tapped in GRID RECORDING with no page changed no bank byte")
        if name == "hold":
            ons = [x for x in notes if x[1] == "on"]
            offs = [x for x in notes if x[1] == "off"]
            if len(ons) != 3 or len(offs) != 3 or not step:
                bad.append(f"the edit sent {notes}; want a triad on, then off")
            else:
                secs = (offs[0][0] - ons[0][0]) / step * 0.125
                print(f"      hold: {offs[0][0] - ons[0][0]} frames, a step {step:.0f}: {secs:.2f} s")
                if not HOLD_FRAMES_WANT[0] <= secs <= HOLD_FRAMES_WANT[1]:
                    bad.append(f"an edit sounds {secs:.2f} s; want {HOLD_FRAMES_WANT}")
        if name == "mode":
            mode = int.from_bytes((out / "mode.trigmode").read_bytes(), "big")
            if mode != 2:
                bad.append(f"the trig mode is {mode}, want 2 (CHORDS)")
            tail = [(k, c, n) for _f, k, c, n in notes][-12:]
            dm7, g7 = [50, 53, 57, 60], [50, 53, 55, 59]
            want = ([("on", 1, n) for n in dm7], [("off", 1, n) for n in dm7], [("on", 1, n) for n in g7])
            got = (sorted(tail[0:4]), sorted(tail[4:8]), sorted(tail[8:12]))
            if got != want:
                bad.append(f"the trig keys sent {tail}; want Dm7 on, off, then G7 on")
            link = PanelLink()
            stream = out / "mode-panel.a"
            if stream.exists():
                link.feed(stream.read_bytes())
            colours = {(15, 15): "Y", (15, 0): "R", (0, 0): ".", (0, 15): "G"}
            leds = "".join(colours.get((link.leds.get(2 * k, 0), link.leds.get(2 * k + 1, 0)), "?")
                           for k in range(16))
            if leds != "GY" + "." * 14:
                bad.append(f"the trig LEDs {leds}; want GY then dark")
        if name == "pick":
            for tag in ("trk", "cs1"):
                trk = (out / f"pick.{tag}").read_bytes()
                lk = list(trk[0x30 + 32 * 2:0x30 + 32 * 2 + 6])
                if lk[0] != 50 or lk[3:6] != [67, 69, 73] or lk[1:3] != [90, 0xff]:
                    bad.append(f"step 3's locks ({tag}) {lk}; want NOTE 50, NOT2-4 67 69 73 (G7)")
            heard = sorted(n for _f, k, c, n in notes if k == "on" and c == 1)
            if heard != [50, 53, 55, 59]:
                bad.append(f"DOWN in the chooser sounded {heard}; want G7 (50 53 55 59) once")
            left = {k: (out / f"pick.{k}").read_bytes()[0] for k in ("ch_pk_win", "ch_up_pushed", "ch_pk_pushed")}
            if any(left.values()):
                bad.append(f"after the trig was let go: {left}; want the chooser closed and both layers popped")
        if name == "live":
            trk = (out / "live.trk").read_bytes()
            steps = [s for s in range(64) if trk[0x30 + 32 * s] == 50]
            locks = [list(trk[0x30 + 32 * s:0x30 + 32 * s + 6]) for s in steps]
            bars = {}
            for f, k, c, n in notes:
                if k == "on" and c == 1 and n in (50, 53, 57):
                    bars.setdefault(f, set()).add(n)
            replays = [f for f, ns in bars.items() if ns == {50, 53, 57}]
            if len(steps) != 1 or locks[0][3:6] != [67, 71, 74]:
                bad.append(f"the recorded steps {steps}, locks {locks}; want one step NOTE 50, NOT2-4 67 71 74")
            if len(replays) < 2:
                bad.append(f"D F A heard together {len(replays)} time(s); want the played one and a replay")
        if name == "collide":
            ons = sorted(n for _f, k, c, n in notes if k == "on" and c == 1)
            offs = sorted(n for _f, k, c, n in notes if k == "off" and c == 1)
            if ons != COLLIDE or offs != COLLIDE:
                bad.append(f"trig 2 sent on {ons}, off {offs}; want {COLLIDE} both")
        if name == "leave":
            tail = [(k, n) for _f, k, c, n in notes if c == 1][-8:]
            if sorted(tail[:4]) != [("on", n) for n in (50, 53, 57, 60)] or \
                    sorted(tail[4:]) != [("off", n) for n in (50, 53, 57, 60)]:
                bad.append(f"the held chord as the mode changed: {tail}; want Dm7 on then off")
        if name == "arp":
            ons = [n for _f, k, _c, n in notes if k == "on"]
            tail = ons[-16:]
            moves = {(b > a) - (b < a) for a, b in zip(tail, tail[1:])}
            if len(ons) < 12 or set(tail) != {50, 53, 57, 60} or moves != {1, -1}:
                bad.append(f"the held chord under ARP sent {ons[-16:]}; want D F A C one at a time")
        if name == "control" and chwin:
            bad.append("a page opened with no SRC")
        if name == "open" and not chwin:
            bad.append("the page did not open")
        print(f"  [{'FAIL' if bad else 'PASS'}] verify_chords {remix}: {name}")
        for line in bad[:8]:
            print(f"      {line}")
        fails += bool(bad)
    fails += persist(out, image, sym)
    return int(bool(fails))


if __name__ == "__main__":
    sys.exit(main())
