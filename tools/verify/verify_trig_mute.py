#!/usr/bin/env python3
"""TRIG MUTE under the port: GRID RECORDING, hold a step + FUNC mutes or
unmutes its trig; a muted trig keeps its locks and condition, does not play,
and its red LED blinks. Saved with the pattern.

    python3 tools/verify/verify_trig_mute.py REMIX

Track 1, pattern A01, step 5 (trig key 5, code 0x04). The trig word's
condition is the low 7 bits of TRAC + 0x89a + 2 * 4 + 1; muted = cond + 65.

  mute      tap step 5 (a trig), hold it + FUNC: condition 65 in the bank and
            its battery copy, the trig and its locks unchanged.
  unmute    ... + FUNC again: condition 0, trig kept.
  empty     hold an empty step 5 + FUNC: a muted trig (stock places it at
            the press).
  cond      hold step 5, RIGHT (the trig popup), LEVEL +3 (stock condition
            edit: 3), FUNC (68), LEVEL
            +1 while held: 69 (the trig's own 4, still muted); FUNC: 4.
  play_*    steps 1 and 5, step 5 muted or not, PLAY ~4 s: the sequencer's
            trig events (code 29 at 0x46c7a810, task main or engine -- a key's preview
            runs in sys) are two a loop unmuted, one muted.
  blink     step 5 muted: its red LED (id 8) is inverted by the overlay
            0x460ba9ae again and again; unmuted (control): never.
  save      (MKII, FUNC + PROJ) the muted step saved; reload: still 65
            (stock's pattern check after a load clamped it to 64).
  power     a power cycle from that save's CS1 (--no-post: the current
            bank from battery RAM): still 65.
  stock     the saved card on the stock OS loads (its parser succeeds).

Cannot see: the hardware, the LCD's condition label (the editor's value is
checked instead), MIDI tracks (audio only).
"""
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
# relative to ROOT (main chdirs there): --scenario is split at spaces, so an absolute
# path under a folder with a space in its name broke every scenario
OUT = pathlib.Path("out/trig-mute-verify")
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
BLOB, BANK_LEN, DBPTR, MIRROR = 0x400e21e0, 0x9b340, 0x46c82456, 0x1001614e
EVENT = 0x46c7a810                      # track 1's trig event (29 = sample trig)
OVERLAY = 0x460ba9ae                    # LED inversion bits; red id 8 = byte 1
OK_RET, BAD_KEY = 0x4008827A, 0x40086D3A
STEP = 4                                # step 5
TW = 0x89a + 2 * STEP + 1
NO, YES, REC, PLAY, FUNC, PROJ, T1, T5, RIGHT = 0x32, 0x31, 0x29, 0x28, 0x2D, 0x1C, 0x00, 0x04, 0x21
LEVEL = 6
WORK = "[STATES]\nBANK=0\n\n"


class Script:
    def __init__(self, t=1500):
        self.t, self.lines = t, []

    def send(self, x, gap=60):
        self.lines.append(f"{self.t} {x}"); self.t += gap

    def down(self, k, gap=150):
        self.send(f"key {k:#x} down", gap)

    def up(self, k, gap=300):
        self.send(f"key {k:#x} up", gap)

    def tap(self, k, gap=400):
        self.down(k, 40); self.up(k, gap)

    def mute(self, k=T5, between=()):
        self.down(k); self.tap(FUNC, 150)
        for x in between:
            self.send(x, 200)
        self.up(k, 400)

    def text(self, end=500):
        return "\n".join(self.lines + [f"{self.t + end} quit"]) + "\n"


def scenario(tag):
    s = Script()
    s.tap(NO)                                       # the date prompt
    s.tap(REC)                                      # grid recording
    if tag == "empty":
        s.mute()
        return s
    if tag == "cond":
        s.down(T5); s.tap(RIGHT, 300)               # the trig popup (LEVEL = condition)
        s.send(f"enc {LEVEL} 3", 200); s.tap(FUNC, 200)
        s.send(f"enc {LEVEL} 1", 200); s.up(T5, 400)
        return s
    if tag.startswith("play") or tag.startswith("blink"):
        if tag.startswith("play"):
            s.tap(T1)
    s.tap(T5)
    if tag in ("mute", "unmute", "play_muted", "blink", "save"):
        s.mute()
    if tag == "unmute":
        s.mute()
    if tag.startswith("play"):
        s.tap(REC)                                  # grid off
        s.tap(PLAY, 4000)
    if tag.startswith("blink"):
        s.t += 2000
    if tag == "save":
        s.tap(REC)
        s.send(f"key {FUNC:#x} down", 60); s.send(f"key {PROJ:#x} down", 60)
        s.send(f"key {PROJ:#x} up", 60); s.send(f"key {FUNC:#x} up", 1300)
        s.tap(YES, 30000)
    return s


def stage(work):
    project = work / "project"
    project.mkdir(parents=True)
    (project / "project.work").write_text(WORK)
    (project / "project.strd").write_text(WORK)
    card = work / "card.img"
    subprocess.run([str(ROOT / ".venv/bin/python3"), "tools/emu/ot_emu/stage_card.py", str(project), "OCTABAM",
                    "TMUTE", "--tree", str(work / "tree"), "--out", str(card)], cwd=ROOT, check=True,
                   capture_output=True)
    return card


def boot(work, name, image, card, text, mkii=False, extra=()):
    (work / f"{name}.script").write_text(text)
    dump = (f"{BLOB:#x},{BANK_LEN:#x}={work / (name + '_bank.bin')};{DBPTR:#x},4={work / (name + '_db.bin')};"
            f"{MIRROR:#x},{0x8ed8:#x}={work / (name + '_mirror.bin')}")
    args = [str(EMU), "--image", str(image), "--card", str(card), "--card-out", str(work / f"{name}.img"),
            "--set", "OCTABAM", "--project", "TMUTE", "--load-ms", "90000", *(["--mkii"] if mkii else []),
            "--watch-mem", f"{EVENT:#x},1;{OVERLAY + 1:#x},1", "--watch-pc", f"{OK_RET:#x},{BAD_KEY:#x},0x400866c4",
            "--live-script", str(work / f"{name}.script"), "--mem-dump", dump, *map(str, extra)]
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    log = r.stdout + r.stderr
    (work / f"{name}.log").write_text(log)
    return r.returncode, log


def state(work, name):
    """(trig bit of step 5, its condition byte, the mirror's, its 32 lock bytes)."""
    bank = (work / f"{name}_bank.bin").read_bytes()
    db = struct.unpack(">I", (work / f"{name}_db.bin").read_bytes())[0]
    mirror = (work / f"{name}_mirror.bin").read_bytes()
    base = db - BLOB
    trig = bool(bank[base + 7] & (1 << STEP))
    locks = bank[base + 0x59 + 32 * STEP: base + 0x59 + 32 * STEP + 32]
    return trig, bank[base + TW], mirror[TW], locks


def played(log):
    """Sample-trig events from the sequencer (a step key's preview runs in sys). The port names the
    task the write interrupted: main, or engine when the frame work shifts (ACCLOOP28's monitor
    hook, 7 Nov 2026: the same events at the same samples, two now read "in engine")."""
    return len(re.findall(rf"\] \[{EVENT:#x}\] <- 0x1d \(4\) at pc \S+ in (?:main|engine)", log))


def writes(log, addr):
    return [int(v, 0) for v in re.findall(rf"\] \[{addr:#x}\] <- (\S+) \(\d\)", log)]


def main():
    os.chdir(ROOT)
    remix = sys.argv[1]
    if "TRIG MUTE" not in registry.remix(remix).modules:
        return 0
    if not EMU.is_file():
        print("  [SKIP] verify_trig_mute: no port (make emu-cf)")
        return 0
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    if "--no-build" not in sys.argv:           # --no-build: gate the image already in out/
        env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
        subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, check=True)
    image = OUT / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    tags = ("mute", "unmute", "empty", "cond", "play_muted", "play_open", "blink", "blink_open")
    work = {t: OUT / t for t in tags + ("save",)}
    cards = {t: stage(work[t]) for t in work}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {t: pool.submit(boot, work[t], t, image, cards[t], scenario(t).text()) for t in tags}
        futs["save"] = pool.submit(boot, work["save"], "save", image, cards["save"], scenario("save").text(), True,
                                   ("--mem-dump", f"0x10000000,0x100000={work['save'] / 'cs1.bin'}"))
        res = {t: f.result() for t, f in futs.items()}
    # --mem-dump is one string: the save's CS1 dump replaced the bank dump; read the card instead
    saved = work["save"] / "save.img"
    with ThreadPoolExecutor(max_workers=3) as pool:
        rl = pool.submit(boot, work["save"], "reload", image, saved, Script().text(100))
        pw = pool.submit(boot, work["save"], "power", image, saved, Script().text(100), False,
                         ("--no-post", "--cs1-in", work["save"] / "cs1.bin"))
        st = pool.submit(boot, work["save"], "stock", STOCK, saved, Script().text(100))
        res["reload"], res["power"], res["stock"] = rl.result(), pw.result(), st.result()

    fails = []

    def check(ok, what):
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_trig_mute: {what}")
        if not ok:
            fails.append(what)

    check(all(rc == 0 for rc, _ in res.values()), "every boot exits 0")
    no_locks = bytes([0xFF]) * 32

    def st_(t, w=None):
        try:
            return state(w or work[t], t)
        except (OSError, struct.error) as e:
            return (None, None, None, str(e))

    trig, c, m, locks = st_("mute")
    check(trig and c & 0x7F == 65 and m == c and locks == no_locks,
          f"mute: hold step 5 + FUNC -> condition 65 in bank and battery copy, trig + locks kept "
          f"(trig={trig} cond={c} mirror={m})")
    trig, c, m, _ = st_("unmute")
    check(trig and c is not None and c & 0x7F == 0 and m == c, f"unmute: FUNC again -> condition 0 (cond={c})")
    trig, c, m, _ = st_("empty")
    check(trig and c is not None and c & 0x7F == 65, f"empty: an empty step + FUNC -> a muted trig (cond={c})")
    trig, c, m, _ = st_("cond")
    check(trig and c is not None and c & 0x7F == 69,
          f"cond: LEVEL +3 = 3, FUNC = 68, LEVEL +1 while muted = 69 (cond={c})")
    fired_m, fired_o = played(res["play_muted"][1]), played(res["play_open"][1])
    check(fired_m >= 2 and fired_o >= fired_m + 2,
          f"play: sequencer trig events over ~4 s, steps 1 + 5: {fired_o}; step 5 muted: {fired_m}")
    inv_m = sum(v & 1 for v in writes(res["blink"][1], OVERLAY + 1))       # red id 8 = byte 1, bit 0
    inv_o = sum(v & 1 for v in writes(res["blink_open"][1], OVERLAY + 1))
    check(inv_m >= 3 and inv_o == 0, f"blink: step 5's red LED inverted {inv_m} times muted, {inv_o} unmuted")
    rl_log = res["reload"][1]
    try:
        trig, c, m, _ = state(work["save"], "reload")
    except (OSError, struct.error):
        trig, c = None, None
    check(trig and c is not None and c & 0x7F == 65, f"reload: the saved card -> still muted (cond={c})")
    try:
        trig, c, m, _ = state(work["save"], "power")
    except (OSError, struct.error):
        trig, c = None, None
    check(trig and c is not None and c & 0x7F == 65,
          f"power: a power cycle (the bank from battery RAM) -> still muted (cond={c})")
    log = res["stock"][1]
    check(f"at {OK_RET:#x}" in log and f"at {BAD_KEY:#x}" not in log, "stock: the saved project loads on stock")
    _ = rl_log
    if fails:
        print(f"  verify_trig_mute: {len(fails)} FAIL")
        return 1
    print("  verify_trig_mute: ALL GOOD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
