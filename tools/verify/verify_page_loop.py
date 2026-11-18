#!/usr/bin/env python3
"""PAGE LOOP under the port: in GRID RECORDING, PAGE + trig n loops page n
of the current track, in time with the others.

    python3 tools/verify/verify_page_loop.py REMIX

Bank 0 pattern 0 is made 64 steps long after the load (40 for `short`),
T1 gets a sample trig on step 18 with an AMP VOL lock of 33. One load,
forked; each scenario: grid on, the combo, grid off, PLAY, then quit.

  loop     PAGE + trig 2: loop state = T1 page 2; the shown page did not
           flip and no trig was placed (stock's PAGE + trig does both);
           after 1.1 s of play T1's play step = 16 + (T2's step % 16) and
           step 18 has fired (live AMP VOL 33).
  none     no combo, same play: T1's step = T2's, AMP VOL is the Part's
           (step 18 not reached yet) -- the contrast for `loop`.
  exit     loop on, PAGE + trig 2 again before PLAY: off; steps equal.
  late     loop on, play 1.1 s, then PAGE + trig 2 (grid on again) and
           0.5 s more: off, T1's step = T2's again (back in time).
  short    40-step pattern: PAGE + trig 4 is refused (state off), PAGE +
           trig 3 loops the 8-step page: T1's step = 32 + (T2's % 8)... as
           T2 is on the full pattern, compared as 32 + ((T2 % 16) % 8).
  midi     MIDI mode, PAGE + trig 2: state = MIDI track 1 (8), its play
           step = 16 + (MIDI track 2's % 16).
  long     loop on, 9 s of play (past the 64-step wrap): still in step.
  long_exit  ... then ended: T1 = T2 again.
  restart  loop on, play, STOP, PLAY again: still in step.
  pattern  loop on, then the playing pattern changed (PATTERN + trig 2,
           stopped) before PLAY: the loop ends at the first step.

Uses OT_PROJECT / ~/.octabam_project when set, else an empty project.
Cannot see: the hardware, trig conditions and micro timing on the looped
page beyond what the play step drives, the LCD.
"""
import os
import pathlib
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
# relative to ROOT (main chdirs there): --scenario is split at spaces, so an absolute
# path under a folder with a space in its name broke every scenario
OUT = pathlib.Path("out/pageloop-verify")
BLOB = 0x400e21e0                     # bank 0, pattern 0, track 0
PAT_LEN = 0x8e53
STEP = 0x800064d0                     # play step, 16 tracks (8 audio, 8 MIDI)
PAGE = 0x460d1e04
LANES = 0x80000810
K = dict(no=0x32, rec=0x29, play=0x28, stop=0x27, page=0x1b, midi=0x35, pattern=0x2e,
         t1=0x00, t2=0x01, t3=0x02, t4=0x03)


class Script:
    def __init__(self):
        self.t, self.lines = 1500, []

    def send(self, x, gap=60):
        self.lines.append(f"{self.t} {x}"); self.t += gap

    def tap(self, k, gap=300):
        self.send(f"key {K[k]:#x} down", 40); self.send(f"key {K[k]:#x} up", gap)

    def combo(self, hold, k):
        self.send(f"key {K[hold]:#x} down", 150); self.tap(k, 150)
        self.send(f"key {K[hold]:#x} up", 400)

    def text(self):
        return "\n".join(self.lines + [f"{self.t} quit"]) + "\n"


def scenario(tag):
    s = Script()
    s.tap("no", 400)
    if tag == "midi":
        s.tap("midi", 400)
    s.tap("rec", 400)
    if tag in ("loop", "exit", "late", "pattern", "long", "long_exit", "restart"):
        s.combo("page", "t2")
    if tag == "exit":
        s.combo("page", "t2")
    if tag == "short":
        s.combo("page", "t4"); s.combo("page", "t3")
    if tag == "midi":
        s.combo("page", "t2")
    s.tap("rec", 400)
    if tag == "pattern":
        s.combo("pattern", "t2")
    s.tap("play", 9000 if tag.startswith("long") else 1100)
    if tag == "restart":
        s.tap("stop", 400); s.tap("play", 1300)
    if tag == "long_exit":
        s.tap("rec", 150); s.combo("page", "t2"); s.tap("rec", 500)
    if tag == "late":
        s.tap("rec", 150); s.combo("page", "t2"); s.tap("rec", 500)
    return s


def main():
    os.chdir(ROOT)
    remix = sys.argv[1]
    if "PAGE LOOP" not in registry.remix(remix).modules:
        return 0
    if not EMU.is_file():
        print("  [SKIP] verify_page_loop: no port (make emu-cf)")
        return 0
    project = os.environ.get("OT_PROJECT", "")
    if not project:
        cfg = pathlib.Path("~/.octabam_project").expanduser()
        project = cfg.read_text().strip() if cfg.exists() else ""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    if not project:
        (OUT / "empty-project").mkdir()
        project = str(OUT / "empty-project")
    if "--no-build" not in sys.argv:           # --no-build: gate the image already in out/
        env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
        subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, check=True)
    image = OUT / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                        capture_output=True, text=True).stdout
    sym = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    card = OUT / "card.img"
    subprocess.run([str(ROOT / ".venv/bin/python3"), "tools/emu/ot_emu/stage_card.py",
                    project, "PLSET", "PLPRJ", "--out", str(card)], cwd=ROOT,
                   stdout=subprocess.DEVNULL, check=True)

    # T1: a trig on step 18 (index 17: mask 0 byte 5 bit 1), AMP VOL lock 33.
    # Not step 17: the first step after PLAY was built while stopped, before
    # the loop could map it (a known limit, README), so step 17 waits a pass.
    fixture = [(BLOB + 5, 0x02), (BLOB + 0x59 + 17 * 32 + 15, 33)]
    tags = ("loop", "none", "exit", "late", "short", "midi", "pattern", "long", "long_exit",
            "restart")
    cmd = [str(EMU), "--image", str(image), "--card", str(card),
           "--set", "PLSET", "--project", "PLPRJ", "--load-ms", "90000"]
    for tag in tags:
        sp = OUT / f"{tag}.script"; sp.write_text(scenario(tag).text())
        pokes = fixture + [(BLOB + PAT_LEN, 40 if tag == "short" else 64)]
        poke = ";".join(f"{a:#x}={v:#04x}" for a, v in pokes)
        dump = (f"{STEP:#x},16={OUT / (tag + '_step.bin')};"
                f"{sym['pl_trk']:#x},8={OUT / (tag + '_state.bin')};"
                f"{PAGE:#x},4={OUT / (tag + '_page.bin')};"
                f"{BLOB:#x},8={OUT / (tag + '_mask.bin')};"
                f"{LANES:#x},72={OUT / (tag + '_lane.bin')};"
                f"{BLOB + PAT_LEN:#x},1={OUT / (tag + '_len.bin')}")
        cmd += ["--scenario", f"{OUT / (tag + '.log')} --live-script {sp} --poke {poke} --mem-dump {dump}"]
    with (OUT / "port.log").open("w") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        print(f"  [FAIL] verify_page_loop: ot_emu exit {r.returncode} -- {OUT / 'port.log'}")
        return 1

    fails = 0

    def check(ok, what):
        nonlocal fails
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_page_loop: {what}")
        fails += not ok

    for tag in tags:
        log = (OUT / f"{tag}.log").read_text(errors="replace")
        step = (OUT / f"{tag}_step.bin").read_bytes()
        trk, page = struct.unpack(">iI", (OUT / f"{tag}_state.bin").read_bytes())
        shown = struct.unpack(">I", (OUT / f"{tag}_page.bin").read_bytes())[0]
        mask = (OUT / f"{tag}_mask.bin").read_bytes()
        vol = (OUT / f"{tag}_lane.bin").read_bytes()[15]
        ln = (OUT / f"{tag}_len.bin").read_bytes()[0]
        a, b = step[0], step[1]
        info = (f"state=({trk},{page}) T1={a} T2={b} M1={step[8]} M2={step[9]} shown={shown} "
                f"mask={mask.hex()} vol={vol} len={ln}")
        clean = "ended on quit" in log
        if tag == "loop":
            check(clean and (trk, page) == (0, 1) and shown == 0 and mask == bytes.fromhex("0000000000020000")
                  and a == 16 + b % 16 and b < 16 and vol == 33,
                  f"loop: T1 loops page 2 (T1 = 16 + T2 % 16), step 18 fired, no page flip, no trig placed ({info})")
        elif tag == "none":
            check(clean and trk == -1 and a == b and vol != 33,
                  f"none: without the combo T1 = T2 and step 18 has not fired yet ({info})")
        elif tag == "exit":
            check(clean and trk == -1 and a == b, f"exit: the combo again ends it ({info})")
        elif tag == "late":
            check(clean and trk == -1 and a == b, f"late: ended while playing, T1 back in time with T2 ({info})")
        elif tag == "short":
            check(clean and (trk, page) == (0, 2) and a == 32 + (b % 16) % 8,
                  f"short: 40 steps, page 4 refused, page 3 loops its 8 steps ({info})")
        elif tag == "midi":
            check(clean and (trk, page) == (8, 1) and step[8] == 16 + step[9] % 16,
                  f"midi: MIDI track 1 loops page 2 (M1 = 16 + M2 % 16) ({info})")
        elif tag == "long":
            check(clean and (trk, page) == (0, 1) and a == 16 + b % 16,
                  f"long: 9 s, past the pattern's wrap, still T1 = 16 + T2 % 16 ({info})")
        elif tag == "long_exit":
            check(clean and trk == -1 and a == b,
                  f"long_exit: ended after the wrap, T1 back in time with T2 ({info})")
        elif tag == "restart":
            check(clean and (trk, page) == (0, 1) and a == 16 + b % 16,
                  f"restart: STOP and PLAY again, still T1 = 16 + T2 % 16 ({info})")
        elif tag == "pattern":
            check(clean and trk == -1, f"pattern: a pattern change ends the loop ({info})")
    return int(bool(fails))


if __name__ == "__main__":
    sys.exit(main())
