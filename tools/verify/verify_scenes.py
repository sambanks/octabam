#!/usr/bin/env python3
"""MIDI SCENES under the port: the same panel scripts on an octabam image
and on bkkbrls-del's MIDISC2.1 image (the oracle), MIDI OUT recorded with
the frame of each byte, and the state each scenario leaves compared.

    python3 tools/verify/verify_scenes.py REMIX [--oracle MAIN21.raw] [--project DIR] [--persist]
        [--only b1,b7] [--tolerance FRAMES] [--reuse his,stock] [--out DIR]
    python3 tools/verify/verify_scenes.py --image NAME=PATH [...]   # record only

Without --oracle (or OT_MSC21_IMAGE) only the predicted values are checked.
The oracle image is stock 1.40C plus MIDISC2.1's `release21.json`; it is
not in the repository. SKIPs without a project (OT_PROJECT or
~/.octabam_project), the port binary, or a REMIX that carries no
MIDI SCENES.

The project is staged once; every scenario forks from one load (`ot_emu
--scenario`). The fixture: every Part of every bank has MIDI track 1 on
channel 11 (Part +0x4e2 = 11), its CC1..CC10 enabled (+0x3e2 + 30/31 =
0x3c/0x3f), scene A = scene 1, scene B = scene 9 (Part +0x10/+0x11 = 0/8).
Knob D on CTRL1 is flat 21; T1's setup CC 2 is CC 1, so the wire message
is `ba 01 vv`. Frames are 16 samples at 44.1 kHz since the script start.

Scenarios (all start: NO for the date prompt, MIDI, T1, FX1 = CTRL1):

  b1       SCENE A held + knob D +40, SCENE B held + knob D +100.
  b2       b1, then SCENE A held and left held (B2 readout, B4 lock LEDs,
           B5 pad indicator).
  b7       b1, then the fader 255 / 128 / 1 / 255.
  b7play   b1, PLAY, then the fader 255 / 128 / 1 / 255.
  b3       b7, then SCENE A held + push knob D, then the fader 1 / 255.
  b29copy  b1, SCENE A held + REC (copy), SCENE B held + STOP (paste),
           then the fader 1 / 255.
  b29clear b1, SCENE A held + PLAY (clear), then the fader 1 / 255.

Per scenario, against the oracle (PASS needs all of them):

  midi     the MIDI OUT messages equal, each in the same frame (within
           --tolerance frames; default 0)
  msc      the 4,096-byte lock table equal
  clip     the 256-byte scene clipboard equal
  trk      the MIDI track records 0x46c76dc0..+0x220 equal
  mask     the lock-mask longs 0x8000664e..+0x20 equal
  screen   the panel link's end-of-scenario LCD plane, LED rows and LED
           levels equal (skipped on a remix with KITS: its status line
           names the Kit where the oracle names the Part)
  nopart   the four Part windows of the image equal the stock image's (the
           module writes no Part byte; needs the stock image run)

and against values computed by hand, with no oracle: b1's table holds 40
at 0x015 and 100 at 0x815 and 0xff elsewhere, the track record holds 100 at
+21, and the CC 1 messages on the wire are the ones the lock values and the
lerp give (b7: 100, then 40, 69 = (40*64 + 100*63) / 127, 100, 40).

Not covered: B5 and the LED half of B4 (the LED rows and levels the panel
link carries are identical on stock, the oracle and this image in every
scenario, so the compare cannot tell a lock LED from none; B4's grey cells
are covered only as far as b2's LCD plane draws them), B6 beyond what b1/b2
draw, B8 with the XF off an end, B9
(stock's own sequence), B30 beyond the overlay in the end-of-scenario LCD,
any sound, the hardware.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/scenesverify"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
HIS_MSC = 0x40a955e0                              # the oracle's msc21_ram

BANK0, BANK_STRIDE, PART_WINDOW, PART_STRIDE = 0x400e21e0, 0x9b340, 0x8ed80, 0x18b2
# Part window = bank base + 0x8ed80 + part * 0x18b2; bank file Part p at
# 0x8eed6 + p * 0x18bb, RAM offset + 9 (the chunk header).
FILE_PART, FILE_PSTRIDE, NPARTS_FILE = 0x8eed6, 0x18bb, 8
MIDI_SETUP, MIDI_PARAMS = 0x4e2, 0x3e2            # Part offsets: setup 36 B per track (byte 0 = channel + 1), params 32 B per track
SCENE_B = 0x11                                    # Part offset: scene B's index (scene A at +0x10)
K = dict(no=0x32, midi=0x35, t1=0x10, t2=0x11, fx1=0x25, fx2=0x26, amp=0x23, play=0x28, stop=0x27,
         func=0x2d, scene_a=0x19, scene_b=0x1a, push_d=0x3b, rec=0x29, yes=0x31, down=0x20, right=0x21, part=0x1d, up=0x33)
MSC_LEN, CLIP_LEN = 0x1000, 0x100

DUMPS = {                                         # name: (address, length)
    "trk": (0x46c76dc0, 0x44 * 8),                # MIDI track records
    "mask": (0x8000664e, 0x20),                   # lock-mask long per track
    "mode": (0x80000012, 4),
    "xf": (0x460d16c8, 4),
    "ui": (0x100b14cc, 4),                        # track, ?, ?, part
    "page": (0x460d1684, 4),
}


class Script:
    """A --live-script at emulated milliseconds."""

    def __init__(self):
        self.t, self.lines = 1500.0, []

    def send(self, x, gap=60):
        self.lines.append(f"{self.t:.0f} {x}"); self.t += gap

    def tap(self, k, gap=250):
        c = K[k] if isinstance(k, str) else k
        self.send(f"key {c:#x} down", 40); self.send(f"key {c:#x} up", gap)

    def turn(self, hold, enc, ticks):
        self.send(f"key {K[hold]:#x} down", 60)
        self.send(f"enc {enc} {ticks}", 200)
        self.send(f"key {K[hold]:#x} up", 300)

    def chord(self, hold, k):
        self.send(f"key {K[hold]:#x} down", 60); self.tap(k, 150); self.send(f"key {K[hold]:#x} up", 300)

    def pot(self, v, gap=500):
        self.send(f"pot {v}", gap)

    def text(self):
        return "\n".join(self.lines + [f"{self.t:.0f} quit"]) + "\n"


def start(s):
    s.tap("no", 400); s.tap("midi", 300); s.tap("t1", 300); s.tap("fx1", 400)


def b1(s):
    start(s); s.turn("scene_a", 3, 40); s.turn("scene_b", 3, 100)


def b2(s):
    b1(s); s.send(f"key {K['scene_a']:#x} down", 1500)


def sweep(s, vals=(255, 128, 1, 255)):
    for v in vals:
        s.pot(v)


def b7(s):
    b1(s); sweep(s)


def b7play(s):
    b1(s); s.tap("play", 1000); sweep(s)


def b3(s):
    b7(s); s.chord("scene_a", "push_d"); sweep(s, (1, 255))


def b29copy(s):
    b1(s); s.chord("scene_a", "rec"); s.chord("scene_b", "stop"); sweep(s, (1, 255))


def b29clear(s):
    b1(s); s.chord("scene_a", "play"); sweep(s, (1, 255))


SCENARIOS = dict(b1=b1, b2=b2, b7=b7, b7play=b7play, b3=b3, b29copy=b29copy, b29clear=b29clear)

# What each scenario must put on the wire, from the lock values and the
# lerp: the CC 1 messages (`ba 01 vv`), in order. 69 = (40*64 + 100*63) / 127.
WIRE_CC1 = dict(b1=[100], b2=[100], b7=[100, 40, 69, 100, 40], b7play=[100, 40, 69, 100, 40],
                b3=[100, 40, 69, 100, 40, 0, 100, 0], b29copy=[100, 40], b29clear=[100, 0])


def fixture(src, dst):
    """Copy the project's .work files; in every Part of every bank: MIDI track 1
    on channel 11, its CC1..CC10 enabled, scene B = scene 9."""
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, dst / f.name)
    for b in range(1, 17):
        p = dst / f"bank{b:02d}.work"
        d = bytearray(p.read_bytes())
        for part in range(NPARTS_FILE):
            o = FILE_PART + part * FILE_PSTRIDE + 9
            d[o + MIDI_SETUP] = 11
            d[o + MIDI_PARAMS + 30], d[o + MIDI_PARAMS + 31] = 0x3c, 0x3f
            d[o + SCENE_B] = 8
        d[-2:] = (sum(d[0x10:-2]) & 0xffff).to_bytes(2, "big")
        p.write_bytes(bytes(d))


def blob(entries):
    """A 2.x sparse blob ('MS', count, pad, entries of a 16-bit index and a value)."""
    b = bytearray([0x4d, 0x53, len(entries), 0])
    for idx, v in entries:
        b += bytes([idx >> 8, idx & 255, v])
    return bytes(b)


# Phase 3 scenarios use a project whose Parts 0 and 1 hold locks (as 2.x sparse blobs, which
# the oracle unpacks at load and this module converts): T1's CC 1 knob (flat 21) is locked in
# scene A (index 0) and scene B (index 8) of each.
SEQ_PARTS = {0: [(0x0015, 30), (0x0815, 90)], 1: [(0x0015, 50), (0x0815, 110)]}


def seq_fixture(src, dst, bank):
    fixture(src, dst)
    bf = dst / f"bank{bank + 1:02d}.work"
    dat = bytearray(bf.read_bytes())
    for part, ents in SEQ_PARTS.items():
        o = FILE_PART + part * FILE_PSTRIDE + 9 + 0x17a2
        dat[o:o + len(blob(ents))] = blob(ents)
    dat[-2:] = (sum(dat[0x10:-2]) & 0xffff).to_bytes(2, "big")
    bf.write_bytes(bytes(dat))


def sw(s):
    """XF at the middle on Part 1, play, PTN + TRIG 2: pattern 2 (Part 2) starts when the pattern ends."""
    s.tap("no", 400); s.pot(128, 800); s.tap("play", 1500)
    s.send("key 0x2e down", 100); s.tap(1, 100); s.send("key 0x2e up", 20000)


SEQ = dict(sw=sw)
# CC 1 on the wire: the mix of Part 1 at XF 128 ((30 * 64 + 90 * 63) / 127 = 59), then of Part 2
# ((50 * 64 + 110 * 63) / 127 = 79) when the pattern switch lands.
SEQ_WIRE = dict(sw=[59, 79])


def decode(raw, st=0):
    """MIDI bytes -> (messages, running status). The firmware's drainer uses running status."""
    out, i = [], 0
    while i < len(raw):
        if raw[i] & 0x80:
            st = raw[i]; i += 1
        if st >= 0xf8 or st == 0:
            out.append(f"{st:02x}"); continue
        n = 2 if st & 0xf0 in (0x80, 0x90, 0xa0, 0xb0, 0xe0) else 1 if st & 0xf0 in (0xc0, 0xd0) else 0
        out.append(" ".join(f"{b:02x}" for b in (st, *raw[i:i + n]))); i += n
    return out, st


def midi_out(path):
    """[(frame, message)] from <tag>.midi.frames (`frame hex..` per drain; one frame can span
    lines), running status carried across frames."""
    if not path.is_file():
        return None
    rows = {}
    for line in path.read_text().split("\n"):
        if line.strip():
            frame, *hx = line.split()
            rows.setdefault(int(frame), []).extend(int(h, 16) for h in hx)
    st, out = 0, []
    for frame, raw in rows.items():
        msgs, st = decode(bytes(raw), st)
        out += [(frame, m) for m in msgs]
    return out


def panel(path):
    """The panel link's decoded end state: (LCD plane bytes, LED rows, LED levels)."""
    sys.path.insert(0, str(ROOT / "tools/panel"))
    from panel_link import PanelLink
    link = PanelLink()
    for suffix in ("a", "b"):
        f = pathlib.Path(f"{path}.{suffix}")
        if f.is_file() and f.stat().st_size:
            cand = PanelLink(); cand.feed(f.read_bytes())
            if cand.stats["lcd_blocks"] > link.stats["lcd_blocks"]:
                link = cand
    return bytes(link.frame), dict(link.led_rows), dict(link.leds)


def build(remix):
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_scenes: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                        capture_output=True, text=True).stdout
    sym = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    return sym["scn_lib"], sym["scn_clip"], sym.get("KIMG"), sym


def run_image(name, path, msc, out, card, tags, jobs, bank, table=None):
    """One ot_emu: the load, then one child per scenario."""
    d = out / name; d.mkdir(exist_ok=True)
    dumps = dict(DUMPS, parts=(BANK0 + bank * BANK_STRIDE + PART_WINDOW, 4 * PART_STRIDE))
    if msc is not None:
        if name == "ours":                        # the library: bank * 4 Parts, Part 0 displayed
            msc = (msc[0] + bank * 4 * MSC_LEN, msc[1])
        dumps["msc"] = (msc[0], MSC_LEN)
        dumps["clip"] = (msc[1], CLIP_LEN)
    scen = []
    for tag in tags:
        s = Script(); (table or SCENARIOS)[tag](s)
        sp = d / f"{tag}.script"; sp.write_text(s.text())
        dump = ";".join(f"{ad:#x},{ln:#x}={d / f'{tag}_{k}.bin'}" for k, (ad, ln) in dumps.items())
        scen += ["--scenario", f"{d / (tag + '.txt')} --live-script {sp} --midi-out {d / (tag + '.midi')} "
                               f"--serial-out {d / (tag + '.serial')} --mem-dump {dump}"]
    cmd = [EMU, "--image", path, "--card", card, "--set", "OCTABAM", "--project", "SCN", "--load-ms", "90000",
           "--scenario-jobs", jobs] + scen
    with open(d / "port.txt", "w") as f:
        f.write(" ".join(map(str, cmd)) + "\n"); f.flush()
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    print(f"== {name} (ot_emu exit {r.returncode})")
    return d


def collect(d, tag):
    r = {"midi": midi_out(d / f"{tag}.midi.frames")}
    for k in ("trk", "mask", "parts", "msc", "clip"):
        f = d / f"{tag}_{k}.bin"
        r[k] = f.read_bytes() if f.is_file() else None
    r["screen"] = panel(d / f"{tag}.serial") if (d / f"{tag}.serial.a").is_file() else None
    return r


CS1, CS1_LEN = 0x10000000, 0x100000
CS1_SCN = 0x100fbdf0                              # 'SCS1', bank, sum, 0, then the current bank's four tables


def persist(card, out, bank, lib, check, kimg=None, syms=None):
    """Storage under the port, our image only: the b1 locks kept by SAVE PROJECT
    (scenes.work and its .strd), a second boot, a power cycle (CS1 in, nothing
    posted) after a save and after none, and the same unsaved card without CS1."""
    import struct
    import zlib
    from concurrent.futures import ThreadPoolExecutor
    sys.path.insert(0, str(ROOT / "tools/emu"))
    import emu_card
    d = out / "persist"; d.mkdir(exist_ok=True)
    slot = lib + bank * 4 * MSC_LEN
    want = {0x015: 40, 0x815: 100}

    def scr(tag, save):
        s = Script(); b1(s)
        if save:                                 # PROJ: SAVE PROJECT
            s.tap(0x1c, 1000); s.tap("right", 700); s.tap("down", 500); s.tap("yes", 1100); s.tap("yes", 30000)
        else:
            s.t += 2000
        (d / f"{tag}.script").write_text(s.text())

    def boot(tag, card_, script, cs1=None, card_out=False):
        cmd = [EMU, "--image", d / "ours.bin", "--card", card_, "--set", "OCTABAM",
               "--project", "SCN", "--load-ms", "90000", "--mkii", "--live-script", script,
               "--mem-dump", f"{slot:#x},{MSC_LEN:#x}={d / (tag + '_msc.bin')};{CS1:#x},{CS1_LEN:#x}={d / (tag + '_cs1.bin')}"]
        if card_out:
            cmd += ["--card-out", d / f"{tag}.img"]
        if cs1 is not None:
            cmd += ["--cs1-in", cs1, "--no-post"]
        with open(d / f"{tag}.txt", "w") as f:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        return r.returncode

    shutil.copy2(OUT / "mainos_ours.bin", d / "ours.bin")
    scr("saved", True); scr("unsaved", False)
    idle = Script(); idle.tap("no", 400); (d / "idle.script").write_text(idle.text())
    with ThreadPoolExecutor(2) as ex:
        rc = list(ex.map(lambda j: boot(*j), [("saved", card, d / "saved.script", None, True),
                                              ("unsaved", card, d / "unsaved.script", None, True)]))
    check(f"persist: the save and the unsaved run exited {rc}", rc == [0, 0])

    def msc(tag):
        f = d / f"{tag}_msc.bin"
        return f.read_bytes() if f.is_file() else b""

    def held(b):
        return {i: v for i, v in enumerate(b) if v != 0xff}

    check(f"persist: saved run holds {held(msc('saved'))} (predicted {want})", held(msc("saved")) == want)
    files = emu_card.extract_image((d / "saved.img").read_bytes())
    for ext in ("work", "strd"):
        f = next((v for k, v in files.items() if k.lower().endswith(f"/scn/scenes.{ext}")), b"")
        ok = len(f) == 16 + 64 * MSC_LEN and f[:8] == b"MSCW\0\0\0\1" and \
            struct.unpack(">I", f[12:16])[0] == zlib.crc32(f[16:]) and \
            held(f[16 + bank * 4 * MSC_LEN:16 + (bank * 4 + 1) * MSC_LEN]) == want
        check(f"persist: scenes.{ext} on the card ({len(f)} B), header, CRC-32 and the locks in bank {bank} Part 0", ok)
    uf = emu_card.extract_image((d / "unsaved.img").read_bytes())
    check("persist: the unsaved run wrote no scenes.work",
          not any(k.lower().endswith("/scn/scenes.work") for k in uf))

    cs1 = (d / "saved_cs1.bin").read_bytes()[CS1_SCN - CS1:CS1_SCN - CS1 + 16 + 4 * MSC_LEN]
    ssum = (bank + sum(struct.unpack(">%dI" % (len(cs1[16:]) // 4), cs1[16:]))) & 0xffffffff
    check(f"persist: CS1 copy: magic {cs1[:4]!r}, bank {struct.unpack('>I', cs1[4:8])[0]}, sum "
          f"{'holds' if struct.unpack('>I', cs1[8:12])[0] == ssum else 'WRONG'}, Part 0 holds {held(cs1[16:16 + MSC_LEN])}",
          cs1[:4] == b"SCS1" and struct.unpack(">I", cs1[4:8])[0] == bank
          and struct.unpack(">I", cs1[8:12])[0] == ssum and held(cs1[16:16 + MSC_LEN]) == want)

    jobs = [("reboot", d / "saved.img", None), ("power", d / "saved.img", d / "saved_cs1.bin"),
            ("powerun", d / "unsaved.img", d / "unsaved_cs1.bin"), ("nocs1", d / "unsaved.img", None)]
    with ThreadPoolExecutor(3) as ex:
        rc = list(ex.map(lambda j: boot(j[0], j[1], d / "idle.script", j[2]), jobs))
    check(f"persist: the four boots exited {rc}", rc == [0, 0, 0, 0])
    check(f"persist: reboot (the saved card, posted load): {held(msc('reboot'))}", held(msc("reboot")) == want)
    check(f"persist: power (saved card, CS1 in, nothing posted): {held(msc('power'))}", held(msc("power")) == want)
    check(f"persist: powerun (unsaved card, CS1 in, nothing posted): {held(msc('powerun'))}", held(msc("powerun")) == want)
    check(f"persist: nocs1 (the unsaved card, posted load): {held(msc('nocs1'))} (none)", held(msc("nocs1")) == {})

    # A scenes.work that is refused (a payload byte flipped: the CRC fails) is not
    # written over; STORE lists it; OVERWRITE and BACKUP (store_answer_cb(choice, 0))
    # then let the next save write it, BACKUP after copying it to scenes.bak.
    files_saved = emu_card.extract_image((d / "saved.img").read_bytes())
    wk = next(v for k, v in files_saved.items() if k.lower().endswith("/scn/scenes.work"))
    bad = bytearray(wk); bad[16 + 5000] ^= 0x55; bad = bytes(bad)
    proj = d / "proj_bad"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(out / "project", proj)
    (proj / "scenes.work").write_bytes(bad)
    card_bad = d / "card_bad.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "SCN",
                        "--tree", str(d / "tree_bad"), "--out", str(card_bad)], cwd=ROOT, capture_output=True, text=True)
    check("persist: the card with a refused scenes.work staged", r.returncode == 0)
    ans = syms["store_answer_cb"]

    def rboot(tag, choice):
        scr(tag, True)
        cmd = [EMU, "--image", d / "ours.bin", "--card", card_bad, "--set", "OCTABAM", "--project", "SCN",
               "--load-ms", "90000", "--mkii", "--live-script", d / f"{tag}.script", "--card-out", d / f"{tag}.img",
               "--mem-dump", f"{slot:#x},{MSC_LEN:#x}={d / (tag + '_msc.bin')};{syms['store_npend']:#x},4={d / (tag + '_np.bin')};{syms['store_pend']:#x},32={d / (tag + '_pend.bin')}"]
        if choice is not None:
            cmd += ["--step", f"-:call:{ans:#x},{choice},0"]
        with open(d / f"{tag}.txt", "w") as f:
            return subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode

    with ThreadPoolExecutor(3) as ex:
        rc = list(ex.map(lambda a: rboot(*a), [("ignore", None), ("overwrite", 1), ("backup", 2)]))
    check(f"persist: the refused-file runs exited {rc}", rc == [0, 0, 0])

    def card_files(tag):
        return emu_card.extract_image((d / f"{tag}.img").read_bytes())

    def find(fs, name):
        return next((v for k, v in fs.items() if k.lower().endswith(f"/scn/{name}")), None)

    npend = struct.unpack(">I", (d / "ignore_np.bin").read_bytes())[0]
    pend = (d / "ignore_pend.bin").read_bytes()
    check(f"persist: ignore: STORE lists the file ({npend} entry, client {pend[0]}, arg {pend[1]})",
          npend == 1 and pend[0] == 2)
    fi = card_files("ignore")
    check("persist: ignore: the refused scenes.work is byte for byte what it was, no scenes.bak",
          find(fi, "scenes.work") == bad and find(fi, "scenes.bak") is None)
    fo = card_files("overwrite")
    wo = find(fo, "scenes.work")
    ok = wo is not None and len(wo) == 16 + 64 * MSC_LEN and wo[:8] == b"MSCW\0\0\0\1" and \
        struct.unpack(">I", wo[12:16])[0] == zlib.crc32(wo[16:]) and \
        held(wo[16 + bank * 4 * MSC_LEN:16 + (bank * 4 + 1) * MSC_LEN]) == want
    check("persist: overwrite: the next save wrote a good scenes.work holding the locks; no scenes.bak",
          ok and find(fo, "scenes.bak") is None)
    fb = card_files("backup")
    wb = find(fb, "scenes.work")
    check("persist: backup: scenes.bak is the refused file, scenes.work a good one",
          find(fb, "scenes.bak") == bad and wb is not None and struct.unpack(">I", wb[12:16])[0] == zlib.crc32(wb[16:]))

    # A project saved under MIDISC 2.x: Part 0 of bank 3 keeps three locks in its sparse
    # blob ('MS', 3, entries of index and value at Part +0x17a2), Part 1 a blob whose value
    # is out of range. With no scenes.work the first becomes Part 0's table, the second nothing.
    proj = d / "proj_conv"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(out / "project", proj)
    bf = proj / f"bank{bank + 1:02d}.work"
    dat = bytearray(bf.read_bytes())

    def put(part, blob):
        o = FILE_PART + part * FILE_PSTRIDE + 9 + 0x17a2
        dat[o:o + len(blob)] = blob
    put(0, bytes([0x4d, 0x53, 3, 0, 0x00, 0x15, 33, 0x08, 0x15, 77, 0x02, 0xa3, 5]))
    put(1, bytes([0x4d, 0x53, 1, 0, 0x00, 0x20, 200]))
    dat[-2:] = (sum(dat[0x10:-2]) & 0xffff).to_bytes(2, "big")
    bf.write_bytes(bytes(dat))
    card_conv = d / "card_conv.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "SCN",
                        "--tree", str(d / "tree_conv"), "--out", str(card_conv)], cwd=ROOT, capture_output=True, text=True)
    check("persist: the card with a 2.x project staged", r.returncode == 0)
    pbase = 0x400e21e0 + bank * 0x9b340
    cmd = [EMU, "--image", d / "ours.bin", "--card", card_conv, "--set", "OCTABAM", "--project", "SCN", "--load-ms", "90000",
           "--mkii", "--live-script", d / "idle.script",
           "--mem-dump", f"{slot:#x},{MSC_LEN:#x}={d / 'conv_p0.bin'};{slot + MSC_LEN:#x},{MSC_LEN:#x}={d / 'conv_p1.bin'};"
           f"{pbase + 0x8ed80 + 0x1712:#x},0x120={d / 'conv_w.bin'};{pbase + 0x9504a + 0x1712:#x},0x120={d / 'conv_s.bin'}"]
    with open(d / "conv.txt", "w") as f:
        rc = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    p0 = held((d / "conv_p0.bin").read_bytes()) if (d / "conv_p0.bin").is_file() else None
    p1 = held((d / "conv_p1.bin").read_bytes()) if (d / "conv_p1.bin").is_file() else None
    check(f"persist: 2.x project: Part 0's blob became its table {p0} (predicted {{21: 33, 2069: 77, 675: 5}}); "
          f"Part 1's out-of-range blob became nothing {p1} (run exit {rc})",
          p0 == {21: 33, 2069: 77, 675: 5} and p1 == {})
    cleared = bytes(0x110) + b"\xff" * 16
    wk = (d / "conv_w.bin").read_bytes() if (d / "conv_w.bin").is_file() else b""
    sv = (d / "conv_s.bin").read_bytes() if (d / "conv_s.bin").is_file() else b""
    check("persist: 2.x project: the blob's Part copy holds what stock Part Clear leaves (zeros, last 16 bytes 0xff)",
          cleared in (wk, sv))

    if kimg is None:
        return
    # A Kit carries its Part's locks (KITS, kits.work version 2): SAVE KIT stores the
    # slot's table in the Kit; LOAD KIT of it, after the locks were cleared, puts it back.
    O_RESID, O_LIB, REC1 = 352, 416, 6338
    REC = REC1 + 4096
    FK = dict(func=0x2d, part=0x1d, up=0x33)

    def savekit(s):
        s.send(f"key {FK['func']:#x} down", 800); s.tap(FK["part"], 800); s.send(f"key {FK['func']:#x} up", 300)
        s.tap("down", 200); s.tap("down", 200); s.tap("yes", 1200); s.tap("yes", 1500)

    def kscript(tag, clear):
        s = Script(); b1(s); savekit(s)
        if clear:
            s.chord("scene_a", "play"); s.chord("scene_b", "play")
            s.tap("part", 800); s.tap("yes", 1500)               # LOAD KIT: the list opens on the current Kit
        s.t += 2000
        (d / f"{tag}.script").write_text(s.text())

    def kboot(tag, clear):
        kscript(tag, clear)
        cmd = [EMU, "--image", d / "ours.bin", "--card", card, "--set", "OCTABAM", "--project", "SCN",
               "--load-ms", "90000", "--mkii", "--live-script", d / f"{tag}.script",
               "--mem-dump", f"{slot:#x},{MSC_LEN:#x}={d / (tag + '_msc.bin')};{kimg:#x},{O_LIB + 256 * REC}={d / (tag + '_kimg.bin')}"]
        with open(d / f"{tag}.txt", "w") as f:
            return subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode

    with ThreadPoolExecutor(2) as ex:
        rc = list(ex.map(lambda a: kboot(*a), [("kitsave", False), ("kitload", True)]))
    check(f"persist: the Kit runs exited {rc}", rc == [0, 0])
    ks = (d / "kitsave_kimg.bin").read_bytes()
    slot_kit = ks[O_RESID + bank * 4]
    tab = lambda im, k: held(im[O_LIB + k * REC + REC1:O_LIB + (k + 1) * REC])
    check(f"persist: SAVE KIT: the slot holds Kit {slot_kit}, whose table is {tab(ks, slot_kit) if slot_kit != 255 else None} (predicted {want})",
          slot_kit != 255 and tab(ks, slot_kit) == want)
    kl = (d / "kitload_kimg.bin").read_bytes()
    check(f"persist: LOAD KIT after the locks were cleared: the slot's locks {held(msc('kitload'))} (predicted {want})",
          held(msc("kitload")) == want)


def seq_group(a, images, out, bank, check):
    """Phase 3: scenarios on the playing sequencer, MIDI out compared with the oracle's."""
    tags = [t for t in SEQ if not a.only or t in a.only.split(",")]
    if not tags:
        return
    sd = out / "seq"; sd.mkdir(exist_ok=True)
    seq_fixture(pathlib.Path(a.project).expanduser(), sd / "project", bank)
    card = sd / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(sd / "project"), "OCTABAM",
                        "SCN", "--tree", str(sd / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    check("seq: the card with Parts holding locks staged", r.returncode == 0)
    res = {}
    for name, path, _msc in images:
        if name == "stock":
            continue
        d = sd / name if name in a.reuse.split(",") else run_image(name, path, None, sd, card, tags, a.jobs, bank, SEQ)
        res[name] = {t: collect(d, t) for t in tags}
    for t in tags:
        print(f"-- seq {t}")
        o = res["ours"][t]
        check(f"seq {t}: ours ran ({len(o['midi'] or [])} MIDI messages)", o["midi"] is not None)
        if o["midi"] is None:
            continue
        cc1 = [int(m.split()[2], 16) for _f, m in o["midi"] if m.startswith("ba 01 ")]
        check(f"seq {t}: CC 1 on the wire {cc1} (predicted {SEQ_WIRE[t]})", cc1 == SEQ_WIRE[t])
        h = res.get("his", {}).get(t)
        if h is None:
            continue
        if h["midi"] is None:
            check(f"seq {t}: his left no MIDI record", False); continue
        om, hm = o["midi"], h["midi"]
        same = len(om) == len(hm) and all(x[1] == y[1] and abs(x[0] - y[0]) <= a.tolerance for x, y in zip(om, hm))
        worst = max((abs(x[0] - y[0]) for x, y in zip(om, hm)), default=0)
        check(f"seq {t}: midi against his: {len(om)} vs {len(hm)} messages, largest frame difference {worst}"
              f" (tolerance {a.tolerance})", same)
        if not same:
            print(f"       ours: {om}\n       his: {hm}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--oracle", default=os.environ.get("OT_MSC21_IMAGE", ""), help="MIDISC2.1's MAIN image")
    ap.add_argument("--image", action="append", default=[], help="NAME=PATH: record only, repeatable")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--card", default="", help="a staged card (skips staging)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", default="4")
    ap.add_argument("--reuse", default="", help="image names whose last run in --out is read instead of run again")
    ap.add_argument("--persist", action="store_true", help="also run the storage scenarios (our image only: SAVE PROJECT, a second boot, power cycles; six more boots, not timed)")
    ap.add_argument("--tolerance", type=int, default=0, help="frames of MIDI timing jitter allowed")
    a = ap.parse_args()
    if not a.remix and not a.image:
        sys.exit("verify_scenes: a REMIX or --image NAME=PATH")
    if a.remix and "MIDI SCENES" not in registry.remix(a.remix).modules:
        print(f"  [ -- ] verify_scenes: {a.remix} carries no MIDI SCENES"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_scenes: no port binary (make emu-cf)"); return 0
    if not a.project:
        pf = pathlib.Path.home() / ".octabam_project"
        a.project = pf.read_text().strip() if pf.is_file() else ""
    if not a.card and not a.project:
        print("  [SKIP] verify_scenes: no project (--project, OT_PROJECT or ~/.octabam_project)"); return 0
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tags = [t for t in SCENARIOS if not a.only or t in a.only.split(",")]

    images = []                                   # (name, path, address of the lock table or None)
    if a.remix:
        lib, clip, kimg, syms = build(a.remix)
        ours = out / "mainos_ours.bin"; shutil.copy2(ROOT / "out/mainos_bus.bin", ours)
        images.append(("ours", ours, (lib, clip)))
        if a.oracle and pathlib.Path(a.oracle).is_file():
            images.append(("his", pathlib.Path(a.oracle), (HIS_MSC, HIS_MSC + MSC_LEN)))
        if STOCK.is_file():
            images.append(("stock", STOCK, None))
    for spec in a.image:
        n, p = spec.split("=", 1)
        images.append((n, pathlib.Path(p), (HIS_MSC, HIS_MSC + MSC_LEN) if n == "his" else None))

    card = pathlib.Path(a.card) if a.card else out / "card.img"
    if not a.card:
        fixture(pathlib.Path(a.project).expanduser(), out / "project")
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(out / "project"), "OCTABAM",
                            "SCN", "--tree", str(out / "tree"), "--out", str(card)], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_scenes: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    proj = out / "project" / "project.work"
    bank = 2
    if not a.card and proj.is_file():
        import re
        m = re.search(rb"\[STATES\]\r?\nBANK=(\d+)", proj.read_bytes())
        bank = int(m.group(1)) if m else 0

    res = {}
    for name, path, msc in images:
        if name in a.reuse.split(","):
            d = out / name
        else:
            d = run_image(name, path, msc, out, card, tags, a.jobs, bank)
        res[name] = {t: collect(d, t) for t in tags}

    if not a.remix:
        for name in res:
            for t in tags:
                print(f"  {name}.{t}:")
                for fr, m in res[name][t]["midi"] or []:
                    print(f"    frame {fr:>6}: {m}")
        return 0

    fails = 0
    kits_remix = registry.remix(a.remix).modules

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    for t in tags:
        o = res["ours"][t]
        print(f"-- {t}")
        check(f"{t}: ours ran ({len(o['midi'] or [])} MIDI messages, table {'read' if o['msc'] else 'MISSING'})",
              o["midi"] is not None and o["msc"] is not None and o["trk"] is not None)
        if o["msc"] is None or o["midi"] is None:
            continue
        cc1 = [int(m.split()[2], 16) for _f, m in o["midi"] if m.startswith("ba 01 ")]
        check(f"{t}: CC 1 on the wire {cc1} (predicted {WIRE_CC1[t]})", cc1 == WIRE_CC1[t])
        if t in ("b1", "b7"):
            want = {0x015: 40, 0x815: 100}
            held = {i: v for i, v in enumerate(o["msc"]) if v != 0xff}
            check(f"{t}: lock table holds {held} (predicted {want})", held == want)
            check(f"{t}: track record +21 = {o['trk'][21]} (predicted {100 if t == 'b1' else 40})",
                  o["trk"][21] == (100 if t == "b1" else 40))
        for other in ("his",):
            h = res.get(other, {}).get(t)
            if h is None:
                continue
            if h["midi"] is None:
                check(f"{t}: {other} left no MIDI record", False); continue
            om, hm = o["midi"], h["midi"]
            same = len(om) == len(hm) and all(x[1] == y[1] and abs(x[0] - y[0]) <= a.tolerance for x, y in zip(om, hm))
            worst = max((abs(x[0] - y[0]) for x, y in zip(om, hm)), default=0)
            check(f"{t}: midi against {other}: {len(om)} vs {len(hm)} messages, largest frame difference {worst}"
                  f" (tolerance {a.tolerance})", same)
            if not same:
                print(f"       ours: {om}\n       {other}: {hm}")
            for k in ("msc", "clip", "trk", "mask"):
                if k == "clip" and t != "b29copy":
                    # untouched: his starts as zeros, ours as 0xff (README, differences)
                    check(f"{t}: clip untouched (ours 0xff x 256, {other} zeros)",
                          o[k] == b"\xff" * CLIP_LEN and h[k] == bytes(CLIP_LEN))
                    continue
                eq = o[k] == h[k]
                diff = [i for i in range(min(len(o[k]), len(h[k]))) if o[k][i] != h[k][i]][:6] if not eq else []
                check(f"{t}: {k} against {other}" + (f" (first differing offsets {[hex(i) for i in diff]})" if diff else ""), eq)
            if "KITS" in kits_remix:
                pass                                   # KITS rewrites the status line's Part field
            elif o["screen"] and h["screen"]:
                same_lcd = o["screen"][0] == h["screen"][0]
                rows = {r: hex(v) for r, v in o["screen"][1].items() if v != h["screen"][1].get(r)}
                check(f"{t}: screen against {other}: LCD plane equal", same_lcd)
                check(f"{t}: screen against {other}: LED rows and levels equal ({rows or 'same'})",
                      not rows and o["screen"][2] == h["screen"][2])
        s = res.get("stock", {}).get(t)
        if s and s["parts"] is not None:
            check(f"{t}: nopart: the Part windows equal stock's", o["parts"] == s["parts"])
    if not a.card and a.project:
        seq_group(a, images, out, bank, check)
    if a.persist and not a.card:
        persist(card, out, bank, images[0][2][0], check, kimg, syms)
    print(f"verify_scenes: {'PASS' if not fails else 'FAIL'} ({fails} failing)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
