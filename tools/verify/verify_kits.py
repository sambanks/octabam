#!/usr/bin/env python3
"""KITS under the port: the Kits each pattern plays, staged through the
stock Part slots; LOAD / SAVE KIT; kits.work over a save, a reboot and a
power cycle; the migration, Em's v3 import, a rejected bank file and a
missing project directory.

    python3 tools/verify/verify_kits.py REMIX [--project DIR] [--octakit-project DIR]
                                              [--strand-project DIR]

The project (OT_PROJECT, ~/.octabam_project) is staged once with no
kits.work, so its Parts migrate at the load; every panel scenario forks
from that load (`ot_emu --scenario`). Bank 3 (the project's saved bank on
OCTABAM89_setgate) is the bank under test; ASSIGN and Part bytes are
poked after the load so the scenarios do not depend on the project's
pattern content beyond pattern 1 playing.

  base      the migration: READY, kits.work on the card with a good CRC,
            Kit n = bank n/4's Part n%4 (working copy, its name), ASSIGN
            = each pattern's Part byte; no stock file rewritten.
  free      pattern 2 -> Kit 0, PTN+TRIG 2 while playing: the pattern's
            own slot (free) holds Kit 0, the engine plays it after the
            switch.
  repoint   ... with pattern 2's Part byte on the playing slot: another
            slot takes Kit 0 and the Part byte names it.
  stopped   the same while stopped: applied at once.
  progchg   a program change (bank 3 pattern 2) while playing.
  chain     patterns 2-4 -> Kits 0, 1, 4, all on the playing slot,
            chained: each in its own slot, the chain cycles.
  trackbtn  the chain, and track keys every 25 ms for 3 s across its
            first switch (ems-octakit#5).
  trackbtn1 the same sweep across a single PTN+TRIG 2 switch.
  presses   the chain, 250 track presses at 180 ms.
  cc        a CC every frame for 3,000 frames with a program change.
  extplay   the trackbtn1 switch with the transport on MIDI start and a
            120 BPM MIDI clock (the Rytm as master).
  extnoclk  the same with MIDI start and no clock: the switch does not
            land, so extplay's transport is the clock's.
  a5        under that clock: STOP, PTN+TRIG, PLAY, three times over the
            chain's patterns: each plays its Kit, the last one playing.
  unattended  the chain on that clock for 60 s with a CC every 250 ms
            across tracks 1-8 (CC 7, 46, 47, 55: a BCR2000): each slot is
            its Kit outside the levels the CCs wrote (+0x10..+0x21).
  load      PART, UP UP, YES (MKII): the current pattern plays the Kit
            two rows up, its slot holds it, UNDO KIT then brings the old
            one back.
  save      FUNC+PART, DOWN DOWN, YES, YES (the name editor): the Kit
            two rows down is the current Part, named.
  quick     FUNC+PART, DOWN, FUNC+YES: saved at once.
  saveproj  LOAD KIT, SAVE PROJECT: kits.work and kits.strd on the card
            with the change; a second boot of that card reads it; a power
            cycle (`--cs1-in`, `--no-post`) of the same card too, and of a
            card whose change was never saved (RESID and ASSIGN from CS1).
  lcopy     LOAD KIT open on the current Kit: FUNC+REC, UP, FUNC+STOP:
            the Kit above is a copy; FUNC+STOP again: it is back.
  lclear    SAVE KIT open, DOWN x3, FUNC+PLAY: that Kit is empty; again:
            it is back.
  ptncopy   FUNC+REC (pattern 1), pattern 14, FUNC+STOP: pattern 14
            plays pattern 1's Kit; FUNC+STOP again: its own again.
  pclone    ... the paste with STOP held and PART pressed: pattern 14
            plays a copy of the Kit, in the next empty Kit.
  fright    PTN+FUNC+RIGHT: the current Part saved into its slot's Kit;
            pattern 14 (the first empty one after 1) is pattern 1, playing
            a copy of that Kit.
  inactive  PTN and FUNC held: TRIG 1 + REC (copy pattern 1), TRIG 14 +
            STOP (paste): pattern 14 is pattern 1 with its Kit.
  inundo    ... and TRIG 14 + STOP again: pattern 14 as it was.
  mki*      the MKI panel (no --mkii), its own load. FUNC+BANK: on the
            main screen PATTERN SETTINGS (mkiptn); after FUNC+MIDI (LOAD
            KIT) SAVE KIT in its place (mkilist), closed by FUNC+BANK
            again (mkiclose); after LOAD KIT closed by NO, PATTERN SETTINGS
            (mkino); FUNC+MIDI, FUNC+BANK, DOWN DOWN, YES, YES saves the
            Kit two rows down, named (mkisave); over the Kit name editor it
            cancels, nothing saved (mkiedit); a list not KITS' leaves FUNC+BANK
            to stock: LOAD KIT open with the list's
            callbacks pointer poked to stock's Part menu table (mkiforeign;
            the recorder setup's own key map never reaches the hook).
  k256save  bank 3's four slots with no Kit (RESID 0xff): SAVE KIT opens
            on the first empty Kit (record 255 is "no Kit", never a row).
  k256load  the same, LOAD KIT: the cursor on UNDO KIT.
  drawn     stopped, LOAD KIT two rows up: the screen is the same as after
            a further FUNC tap (drawn by the load itself, as stock FUNC+CUE).
  lvl       LOAD KIT open, LEVEL +3 then -1: the cursor two rows below
            where it opened (lvl0: LOAD KIT open alone).
  lvlstock  LEVEL +3 on the main screen: the current track's level +3 (stock).
  ptnmask   playing, PATTERN held, TRIG 2 tapped, then TRIG 3: a switch
            each, so the held-TRIG mask (0x460d1ab6) is 0 with PATTERN still
            down (a bit left set makes the next tap a chain).
  k256rescue  a Part in record 255 (its valid bit and a name poked) and
            pattern 5 noted as on Em's Kit 256: rescue_k256 moves the Part
            to the first empty Kit and assigns pattern 5 to it.
  import    a project with Em's kits3a/b.work and no kits.work: each
            occupied Kit's name and Part and the newest manifest's ASSIGN,
            as tools/verify's own reader of her format gives them.
  strand    a project whose bank01.work the firmware rejects: the load,
            400 frames playing and a pattern paste, no halt.
  noproj    a project name with no directory on the card: the load runs.

Every scenario: no halt, the counters CNT_NOSLOT, CNT_INVALID,
CNT_IOERR and CNT_BADFILE at zero (CNT_ISR is reported), the firmware's
LOG without an error beyond the samples the stage leaves out. SKIPs
without a project or the port, or for a remix without KITS.

What it cannot see: the hardware; the arranger (its schedule runs in the
tick, counted as CNT_ISR, untested here); the sound.

Cost. The load and the scenarios run without the DSP cores: the frame
engine runs the transport and every check passes without them (6 Oct
2026: base + free 119 s against 404 s with --dsp, the same 10 checks).
Three scenarios at a time, the port's default for four performance
cores. The whole gate on bottleservice, native binary, quiet machine:
630 s. A playing pattern switch on OCTABAM89_setgate lands between 12 s
and 17 s emulated after PTN+TRIG (waits of 6, 9 and 12 s failed), so the
17 s and 48 s waits stay.
"""
import argparse
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/kitsverify"
BLOB, BSTRIDE, PSTRIDE, PARTSZ = 0x400e21e0, 0x9b340, 0x8ed8, 0x18b2
WORK, SAVED, PNAMES, PBYTE = 0x8ed80, 0x9504a, 0x9b316, 0x8e57
REC, O_ASSIGN, O_VALID, O_RESID, O_LIB = 6338, 64, 320, 352, 416
IMG_LEN = O_LIB + 256 * REC
TRK = 0x8000182a
CS1, CS1_LEN = 0x10000000, 0x100000
STATE = ("READY KDIRTY NOWRITE PENDING ISR NOSLOT INVALID IOERR BADFILE "
         "STAGED REPOINT STAMP").split()
K = dict(no=0x32, yes=0x31, play=0x28, stop=0x27, ptn=0x2e, func=0x2d, part=0x1d,
         up=0x33, down=0x20, right=0x21, mixer=0x30, rec=0x29)
BANK = 2                                  # bank 3: the project's own
MKI = dict(midi=0x35, bank=0x2f, recab=0x2b)   # held with FUNC on the MKI panel
MENU = 0x460e5e28                         # the stock list: callbacks, labels, object, &selection
PSET, TEXTED = 0x460fab34, 0x460e7612     # PATTERN SETTINGS' window, the text editor (nonzero: open)
LCD = 0x46c7e0ea                          # the 1-bpp plane (tools/emu/README.md "The screen")


def run(cmd, log):
    with open(log, "w") as f:
        f.write(" ".join(map(str, cmd)) + "\n"); f.flush()
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_kits: ot_emu exit {r.returncode} -- {log}")
    return log.read_text(errors="replace")


class Script:
    """A --live-script at emulated milliseconds."""

    def __init__(self):
        self.t, self.lines, self.bg = 1500, [], []

    def send(self, x, gap=60):
        self.lines.append(f"{self.t:.0f} {x}"); self.t += gap

    def tap(self, k, gap=400):
        c = K[k] if isinstance(k, str) else k
        self.send(f"key {c:#x} down", 40); self.send(f"key {c:#x} up", gap)

    def down(self, k, gap=80):
        self.send(f"key {(K[k] if isinstance(k, str) else k):#x} down", gap)

    def up(self, k, gap=80):
        self.send(f"key {(K[k] if isinstance(k, str) else k):#x} up", gap)

    def hold(self, k, *inner, gap=400):
        self.down(k)
        for x in inner:
            self.tap(x, 200)
        self.up(k, gap)

    def wait(self, ms):
        self.send("enc 6 0", ms)

    def clock(self, start, end, bpm=120):
        """MIDI clock (F8, 24 per beat) from start to end ms, beside the
        keys: an external master keeps time while the panel is used."""
        t, step = start, 60000 / bpm / 24
        while t < end:
            self.bg.append((t, f"{t:.0f} midi f8")); t += step

    def text(self):
        fg = [(float(l.split(" ", 1)[0]), l) for l in self.lines]
        lines = [l for _t, l in sorted(fg + self.bg, key=lambda x: x[0])]
        return "\n".join(lines + [f"{self.t + 300:.0f} quit"]) + "\n"


def v3_reference(files):
    """Em's kits3a/b.work as her reader takes them (persistence.c): per Kit
    the newest generation of a record whose CRC-32 holds; ASSIGN from the
    newest valid manifest. -> ({kit: (name, payload) or None}, assign[256])."""
    best, mgen, assign = {}, None, [0xff] * 256
    for d in files:
        if len(d) < 0x600:
            continue
        for off in (0x200, 0x400):
            m = d[off:off + 0x200]
            if m[:4] != b"OTK3" or struct.unpack(">I", m[0x1fc:])[0] != zlib.crc32(m[:0x1fc]):
                continue
            g = struct.unpack(">I", m[20:24])[0]
            if mgen is None or g > mgen:
                mgen = g
                assign = [m[0x20 + i] if m[0x120 + i // 8] >> (i % 8) & 1 else 0xff for i in range(256)]
        for k in range(256):
            r = d[0x600 + k * 0x1a00:0x600 + (k + 1) * 0x1a00]
            if len(r) < 0x1a00 or r[:8] != b"OTK3KITS" or struct.unpack(">H", r[24:26])[0] != k:
                continue
            if struct.unpack(">I", r[0x19fc:])[0] != zlib.crc32(r[:0x19fc]):
                continue
            g = struct.unpack(">I", r[20:24])[0]
            if k in best and g <= best[k][0]:
                continue
            best[k] = (g, (r[0x20:0x27].split(b"\0")[0], r[0x28:0x28 + PARTSZ]) if r[9] & 1 else None)
    return {k: v for k, (g, v) in best.items()}, assign


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    proj = os.environ.get("OT_PROJECT") or (pathlib.Path.home() / ".octabam_project").read_text().strip() \
        if (pathlib.Path.home() / ".octabam_project").is_file() else os.environ.get("OT_PROJECT", "")
    ap.add_argument("--project", default=proj)
    ap.add_argument("--octakit-project", default=str(pathlib.Path.home() / "octa/backups/card_20261003_bottleservice/kept/Bottleservice 2026"))
    ap.add_argument("--strand-project", default=str(pathlib.Path.home() / "octa/backups/card_20261004_strand/PROJECT 261004p"))
    ap.add_argument("--only", default="", help="comma-separated scenario names")
    a = ap.parse_args()
    remix = registry.remix(a.remix)
    if "KITS" not in remix.modules:
        print(f"  [ -- ] verify_kits: {a.remix} carries no KITS"); return 0
    if not a.project:
        print("  [SKIP] verify_kits: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_kits: no port binary (make emu-cf)"); return 0
    pdir = pathlib.Path(a.project).expanduser()
    if not (pdir / "project.work").is_file():
        sys.exit(f"verify_kits: {pdir} is not a project")
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.only.split(",")))

    # ---- the image and the unit's symbols -------------------------------------
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_kits: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                        capture_output=True, text=True).stdout
    sym = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    KI, KS = sym["KIMG"], sym["KSTATE"]
    b3 = BLOB + BANK * BSTRIDE
    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    sys.path.insert(0, str(ROOT / "tools/emu"))
    import emu_card  # noqa: E402

    def stage(src, name, extra=()):
        d = OUT / f"proj_{name}"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        for f in pathlib.Path(src).iterdir():
            if f.is_file() and f.suffix.lower() in (".work",):
                shutil.copy2(f, d / f.name)
        for f in extra:
            shutil.copy2(f, d / f.name)
        card = OUT / f"card_{name}.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(d), "OCTABAM", name,
                            "--tree", str(OUT / f"tree_{name}"), "--out", str(card)],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_kits: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        return card

    card = stage(pdir, "KITS")
    base = [EMU, "--image", image, "--card", card, "--set", "OCTABAM", "--project", "KITS",
            "--load-ms", "90000", "--mkii"]

    def dumps(tag):
        return (f"{KS:#x},48={OUT / f'{tag}_st.bin'};{KI:#x},{IMG_LEN}={OUT / f'{tag}_img.bin'};"
                f"{b3:#x},{BSTRIDE:#x}={OUT / f'{tag}_b3.bin'};{TRK:#x},16={OUT / f'{tag}_trk.bin'};"
                f"0x80001828,2={OUT / f'{tag}_eng.bin'}")

    def pa(ptn):
        return KI + O_ASSIGN + BANK * 16 + ptn

    def pb(ptn):
        return b3 + ptn * PSTRIDE + PBYTE

    scen, mki_scen, scripts = [], [], {}

    def add(tag, script=None, pokes=(), extra=(), more_dumps="", mki=False):
        if only and tag not in only:
            return
        args = []
        if pokes:
            args += ["--poke", ";".join(f"{x:#x}={v:#x}" for x, v in pokes)]
        if script is not None:
            sp = OUT / f"{tag}.script"; sp.write_text(script.text()); args += ["--live-script", sp]
        args += list(extra) + ["--mem-dump", dumps(tag) + more_dumps]
        (mki_scen if mki else scen).append(f"{OUT / (tag + '.txt')} " + " ".join(map(str, args)))
        scripts[tag] = script

    def playing_switch(s, ptn, wait=17000):
        s.tap("no"); s.tap("play", 2000); s.hold("ptn", ptn); s.wait(wait)

    s = Script(); s.tap("no"); add("base", s, extra=["--card-out", OUT / "base.img"])
    s = Script(); playing_switch(s, 1); add("free", s, [(pa(1), 0)])
    s = Script(); playing_switch(s, 1); add("repoint", s, [(pa(1), 0), (pb(1), 0)])
    s = Script(); s.tap("no"); s.hold("ptn", 1); s.wait(1500); add("stopped", s, [(pa(1), 0), (pb(1), 0)])
    (OUT / "progchg.midi").write_text("200 c0 21\n")
    add("progchg", None, [(pa(1), 0), (pb(1), 0)],
        ["--sequencer", "--internal-clock", "--frames", "60000", "--midi", OUT / "progchg.midi"])

    def chain(s, extra=None):
        s.tap("no"); s.tap("play", 2000)
        s.down("ptn"); s.down(1, 120); s.tap(2, 120); s.tap(3, 120); s.up(1, 120); s.up("ptn", 300)
        if extra:
            extra(s)
    cpokes = [(pa(1), 0), (pa(2), 1), (pa(3), 4), (pb(1), 0), (pb(2), 0), (pb(3), 0)]
    s = Script(); chain(s, lambda s: s.wait(48000)); add("chain", s, cpokes)

    def sweep(s):
        s.wait(11500)
        for i in range(120):                # a track key every 25 ms, 12 ms down
            s.send(f"key {0x10 + i % 8:#x} down", 12); s.send(f"key {0x10 + i % 8:#x} up", 13)
        s.wait(3000)
    s = Script(); chain(s, sweep); add("trackbtn", s, cpokes)
    s = Script(); s.tap("no"); s.tap("play", 2000); s.hold("ptn", 1); sweep(s)
    add("trackbtn1", s, [(pa(1), 0), (pb(1), 0)])

    # An external master (the Rytm): MIDI start, 120 BPM clock, stop.
    def extstart(s, ms):
        s.send("midi fa", 0); s.clock(s.t, s.t + ms); s.wait(ms)
    s = Script(); s.tap("no", 1000); t0 = s.t; s.send("midi fa", 2000); s.hold("ptn", 1); s.wait(17000)
    s.clock(t0, s.t); add("extplay", s, [(pa(1), 0), (pb(1), 0)])
    s = Script(); s.tap("no", 1000); s.send("midi fa", 2000); s.hold("ptn", 1); s.wait(17000)
    add("extnoclk", s, [(pa(1), 0), (pb(1), 0)])

    def a5(s):                               # STOP, switch, PLAY under the master, x3
        s.tap("no", 1000); extstart(s, 4000)
        for p in (1, 2, 3):
            s.send("midi fc", 300); s.hold("ptn", p, gap=200); extstart(s, 4000 if p < 3 else 8000)
    s = Script(); a5(s); add("a5", s, cpokes)

    def unattended(s):                       # the chain on the master's clock, CCs from a BCR2000
        s.tap("no", 1000); t0 = s.t; s.send("midi fa", 2000)
        s.down("ptn"); s.down(1, 120); s.tap(2, 120); s.tap(3, 120); s.up(1, 120); s.up("ptn", 300)
        for i in range(240):
            ch, cc = i % 8, (7, 46, 47, 55)[i // 8 % 4]
            s.send(f"midi {0xb0 + ch:02x} {cc:02x} {(i * 13) % 128:02x}", 250)
        s.clock(t0, s.t)
    s = Script(); unattended(s); add("unattended", s, cpokes)

    def presses(s):
        for i in range(250):
            s.tap(0x10 + i % 8, 140)
    s = Script(); chain(s, presses); add("presses", s, cpokes)
    (OUT / "cc.midi").write_text("".join(f"{f} b0 07 {(f * 7) % 128:02x}\n" for f in range(1, 3000))
                                 + "300 c0 21\n")
    add("cc", None, [(pa(1), 0)], ["--sequencer", "--internal-clock", "--frames", "3100", "--midi", OUT / "cc.midi"])
    s = Script(); s.tap("no"); s.tap("part", 800); s.tap("up", 200); s.tap("up", 200); s.tap("yes", 1500); add("load", s)
    s = Script(); s.tap("no"); s.tap("part", 800); s.tap("up", 200); s.tap("up", 200); s.tap("yes", 1500)
    s.tap("part", 800); s.send(f"key {K['up']:#x} down", 60); s.send(f"key {K['up']:#x} up", 60)
    for _ in range(40):                    # back to row 0, UNDO KIT
        s.tap("up", 60)
    s.tap("yes", 1500); add("undo", s)
    s = Script(); s.tap("no"); s.hold("func", "part", gap=800); s.tap("down", 200); s.tap("down", 200)
    s.tap("yes", 1200); s.tap("yes", 1500); add("save", s)
    s = Script(); s.tap("no"); s.hold("func", "part", gap=800); s.tap("down", 200)
    s.down("func", 100); s.tap("yes", 200); s.up("func", 1500); add("quick", s)

    lcdd = f";{LCD:#x},1024="
    menud = f";{MENU:#x},36="
    s = Script(); s.tap("no"); s.tap("part", 800); s.tap("up", 200); s.tap("up", 200); s.tap("yes", 1500)
    add("drawn", s, more_dumps=lcdd + str(OUT / "drawn_lcd.bin"))
    s = Script(); s.tap("no"); s.tap("part", 800); s.tap("up", 200); s.tap("up", 200); s.tap("yes", 1500)
    s.tap("func", 1500); add("drawnf", s, more_dumps=lcdd + str(OUT / "drawnf_lcd.bin"))

    s = Script(); s.tap("no"); s.tap("part", 800)
    add("lvl0", s, more_dumps=menud + str(OUT / "lvl0_menu.bin"))
    s = Script(); s.tap("no"); s.tap("part", 800); s.send("enc 6 3", 300); s.send("enc 6 -1", 600)
    add("lvl", s, more_dumps=menud + str(OUT / "lvl_menu.bin"))
    s = Script(); s.tap("no"); s.send("enc 6 3", 600)
    add("lvlstock", s, more_dumps=f";0x80000c50,16={OUT / 'lvlstock_lev.bin'}")
    s = Script(); s.tap("no", 600)
    add("lvlbase", s, more_dumps=f";0x80000c50,16={OUT / 'lvlbase_lev.bin'}")
    s = Script(); s.tap("no"); s.tap("play", 2000); s.down("ptn", 100); s.tap(1, 800); s.tap(2, 800)
    s.wait(500); add("ptnmask", s, more_dumps=f";0x460d1ab6,2={OUT / 'ptnmask_mask.bin'}")

    # ---- record 255 is "no Kit" ---------------------------------------------
    nokit = [(KI + O_RESID + BANK * 4 + i, 0xff) for i in range(4)]
    s = Script(); s.tap("no"); s.hold("func", "part", gap=800)
    add("k256save", s, nokit, more_dumps=menud + str(OUT / "k256save_menu.bin"))
    s = Script(); s.tap("no"); s.tap("part", 800)
    add("k256load", s, nokit, more_dumps=menud + str(OUT / "k256load_menu.bin"))
    r255 = KI + O_LIB + 255 * REC
    if not only or "k256rescue" in only:
        add("k256rescue", None, (), ["--step", f"-:poke:{KI + O_VALID + 31:#x}=0x80;{sym['V3K256']:#x}=0x20;"
                                     + ";".join(f"{r255 + i:#x}={c:#x}" for i, c in enumerate(b"RESCUE\0")),
                                     "--step", f"-:call:{sym['rescue_k256']:#x}"])

    # ---- Phase 2 -----------------------------------------------------------
    s = Script(); s.tap("no"); s.tap("part", 800); s.hold("func", "rec"); s.tap("up", 200)
    s.hold("func", "stop", gap=600)
    s.down("func"); s.tap("stop", 300); s.up("func", 600); add("lundo", s)       # the second paste undoes
    s = Script(); s.tap("no"); s.tap("part", 800); s.hold("func", "rec"); s.tap("up", 200)
    s.hold("func", "stop", gap=600); add("lcopy", s)
    s = Script(); s.tap("no"); s.hold("func", "part", gap=800)
    for _ in range(3):
        s.tap("down", 150)
    s.hold("func", "play", gap=600); add("lclear", s)
    s = Script(); s.tap("no"); s.hold("func", "part", gap=800)
    for _ in range(3):
        s.tap("down", 150)
    s.hold("func", "play", gap=600); s.hold("func", "play", gap=600); add("lclundo", s)

    def ptncopy(s, extra=None):
        s.tap("no"); s.hold("func", "rec", gap=600)                 # pattern 1 copied
        s.hold("ptn", 13, gap=800)                                    # pattern 14
        if extra:
            extra(s)
        else:
            s.hold("func", "stop", gap=800)
    s = Script(); ptncopy(s); add("ptncopy", s, [(pa(0), 5)])
    # The stock undo of a pattern paste (0x4002ba2c: 0x4002b9b0 from the undo
    # buffer) is not reached from the panel under the port, on stock either
    # (a second FUNC+STOP pastes again): the routines are called in order.
    add("ptnundo", None, (),
        ["--step", f"-:poke:{pa(0):#x}=5;{pa(13):#x}=3", "--step", "-:call:0x40026eb0,0", "--step", "-:call:0x40026ef0,0x11,13",
         "--step", "-:call:0x4002b9b0,0x460c8122,13",
         "--step", f"-:dump:{pa(13):#x},1={OUT / 'ptnundo_mid.bin'}",
         "--step", "-:call:0x4002b9b0,0x460bf218,13"])
    s = Script(); ptncopy(s, lambda s: (s.down("func"), s.down("stop", 300), s.tap("part", 300),
                                       s.up("stop"), s.up("func", 800)))
    add("pclone", s, [(pa(0), 5)])
    s = Script(); s.tap("no"); s.down("ptn"); s.down("func"); s.tap("right", 300); s.up("func"); s.up("ptn", 2000)
    add("fright", s, [(pa(0), 5)])

    def inactive(s, again=False):
        s.tap("no"); s.down("ptn"); s.down("func")
        s.down(0, 100); s.tap("rec", 200); s.up(0, 200)
        s.down(13, 100); s.tap("stop", 300); s.up(13, 200)
        if again:
            s.down(13, 100); s.tap("stop", 300); s.up(13, 200)
        s.up("func"); s.up("ptn", 800)
    s = Script(); inactive(s); add("inactive", s, [(pa(0), 5)])
    s = Script(); inactive(s, True); add("inundo", s, [(pa(0), 5)])

    def loadkit(s):
        s.tap("no"); s.tap("part", 800); s.tap("up", 200); s.tap("up", 200); s.tap("yes", 1500)
    s = Script(); loadkit(s)
    s.tap(0x1c, 1000); s.tap("right", 700); s.tap("down", 500); s.tap("yes", 1100); s.tap("yes", 30000)  # PROJ: SAVE PROJECT
    add("saveproj", s, extra=["--card-out", OUT / "saved.img"],
        more_dumps=f";{CS1:#x},{CS1_LEN:#x}={OUT / 'cs1_saved.bin'}")
    s = Script(); loadkit(s); s.wait(2000)
    add("unsaved", s, extra=["--card-out", OUT / "unsaved.img"],
        more_dumps=f";{CS1:#x},{CS1_LEN:#x}={OUT / 'cs1_unsaved.bin'}")

    # ---- the MKI panel: FUNC+BANK (its own load: the panel is chosen at boot) --
    def ui(tag):
        return (f";{MENU:#x},36={OUT / f'{tag}_menu.bin'};{sym['MOWN']:#x},4={OUT / f'{tag}_mown.bin'}"
                f";{PSET:#x},4={OUT / f'{tag}_pset.bin'};{TEXTED:#x},4={OUT / f'{tag}_ted.bin'}")

    def mki(tag, *steps, pokes=()):
        s = Script(); s.tap("no")
        for st_ in steps:
            if isinstance(st_, tuple):          # (address, long): a poke at this point of the script
                s.send("poke " + ";".join(f"{st_[0] + i:#x}={st_[1] >> 24 - 8 * i & 0xff:#x}" for i in range(4)), 200)
            elif st_ in MKI:
                s.hold("func", MKI[st_], gap=800)
            else:
                s.tap(st_, 600)
        add(tag, s, pokes, more_dumps=ui(tag), mki=True)
    mki("mkiptn", "bank")
    mki("mkilist", "midi", "bank")
    mki("mkiclose", "midi", "bank", "bank")
    mki("mkino", "midi", "no", "bank")
    mki("mkisave", "midi", "bank", "down", "down", "yes", "yes")
    mki("mkiedit", "midi", "bank", "yes", "bank")
    mki("mkiforeign", "midi", (MENU, 0x400b9b04), "bank", (MENU, sym["CBTAB"]))
    if scen:
        run(base + [x for sc in scen for x in ("--scenario", sc)] + ["--scenario-jobs", "3"], OUT / "port.txt")
    if mki_scen:
        run([x for x in base if x != "--mkii"] + [x for sc in mki_scen for x in ("--scenario", sc)]
            + ["--scenario-jobs", "3"], OUT / "port_mki.txt")

    # ---- reading a run back ---------------------------------------------------
    def st(tag):
        d = (OUT / f"{tag}_st.bin").read_bytes()
        return {n: struct.unpack(">I", d[4 * i:4 * i + 4])[0] for i, n in enumerate(STATE)}

    def img(tag):
        return (OUT / f"{tag}_img.bin").read_bytes()

    def b3_(tag):
        return (OUT / f"{tag}_b3.bin").read_bytes()

    def kit(im, k):
        return im[O_LIB + k * REC + 16:O_LIB + (k + 1) * REC]

    def slot(b, s):
        return b[WORK + s * PARTSZ:WORK + (s + 1) * PARTSZ]

    def clean(tag, extra_ok=()):
        log = (OUT / f"{tag}.txt").read_text(errors="replace")
        halted = any(w in log for w in ("stopped before", "FAULT", "ILLEGAL", "EXCEPTION", "DID NOT RETURN"))
        s = st(tag)
        bad = {k: s[k] for k in ("NOSLOT", "INVALID", "IOERR", "BADFILE") if s[k] and k not in extra_ok}
        check(f"{tag}: no halt, READY {s['READY']}, counters {bad or 'zero'} (ISR {s['ISR']}, "
              f"staged {s['STAGED']}, repointed {s['REPOINT']})", not halted and not bad and s["READY"] == 1)
        return s

    def exists(tag):
        return (OUT / f"{tag}_st.bin").is_file()

    # base: the migration
    if exists("base"):
        clean("base")
        im, b = img("base"), b3_("base")
        files = emu_card.extract_image((OUT / "base.img").read_bytes())
        kw = next((v for k, v in files.items() if k.lower().endswith("/kits/kits.work")), b"")
        check(f"base: kits.work on the card ({len(kw)} B), CRC-32 holds",
              len(kw) == IMG_LEN and struct.unpack(">I", kw[12:16])[0] == zlib.crc32(kw[64:]))
        # MIDI SCENES rewrites its Part-window bytes in the current Part after
        # the load (KITS's equality leaves them out the same way)
        lo, hi = 0, 0
        if "MIDI SCENES" in remix.modules:
            pw = registry.modules()["MIDI SCENES"].claims.part_window
            lo, hi = min(o for o, _l, _w in pw) - WORK, max(o + l for o, l, _w in pw) - WORK

        def eq(x, y):
            return x[:lo] == y[:lo] and x[hi:] == y[hi:]
        ok = all(eq(kit(im, BANK * 4 + p), slot(b, p)) for p in range(4))
        check("base: Kits 9-12 are bank 3's working Parts"
              + (f" (outside MIDI SCENES' +{lo:#x}..+{hi:#x})" if hi else ""), ok)
        names = [im[O_LIB + (BANK * 4 + p) * REC:O_LIB + (BANK * 4 + p) * REC + 7].split(b"\0")[0] for p in range(4)]
        stock = [b[PNAMES + 7 * p:PNAMES + 7 * p + 7].split(b"\0")[0] for p in range(4)]
        check(f"base: their names are the Parts' ({names})", names == stock)
        asg = [im[O_ASSIGN + BANK * 16 + p] for p in range(16)]
        want = [BANK * 4 + b[p * PSTRIDE + PBYTE] if asg[p] != 0xff else 0xff for p in range(16)]
        check(f"base: bank 3's assignments follow the Part bytes ({asg})", asg == want and asg[0] != 0xff)
        changed = [k for k, v in files.items() if k.startswith("OCTABAM/KITS/")
                   and (k.endswith(".work") or k.endswith(".strd")) and "kits" not in k.rsplit("/", 1)[1]
                   and (OUT / "proj_KITS" / k.rsplit("/", 1)[1]).is_file()
                   and (OUT / "proj_KITS" / k.rsplit("/", 1)[1]).read_bytes() != v]
        check(f"base: no stock file rewritten ({changed})", not changed)
        log = next((v for k, v in files.items() if k.upper().startswith("LOG")), b"").decode("latin1")
        errs = [l for l in log.splitlines() if "ERROR" in l and "Couldn't load" not in l]
        check(f"base: the firmware's LOG has no other error ({errs[:2]})", not errs)

    def plays(tag, ptn, k):
        b, im = b3_(tag), img(tag)
        s = b[ptn * PSTRIDE + PBYTE]
        trk = (OUT / f"{tag}_trk.bin").read_bytes()
        return s, slot(b, s) == kit(im, k), trk

    for tag in ("free", "repoint", "stopped", "progchg", "trackbtn1", "extplay"):
        if not exists(tag):
            continue
        s = clean(tag)
        sl, ok, trk = plays(tag, 1, 0)
        eng = (OUT / f"{tag}_eng.bin").read_bytes()
        engine = {trk[8 + t] for t in range(8) if trk[t] == BANK}
        check(f"{tag}: pattern 2's slot {sl + 1} holds Kit 1, the engine plays it (engine {eng[0] + 1}:{eng[1] + 1}, "
              f"tracks' parts {sorted(engine)})",
              ok and eng[0] == BANK and eng[1] == sl and engine <= {sl})
        if tag == "free":
            check("free: the pattern's own slot (2), nothing repointed", sl == 1 and s["REPOINT"] == 0)
        if tag in ("repoint", "stopped", "progchg", "trackbtn1", "extplay"):
            check(f"{tag}: the Part byte repointed off the playing slot ({sl + 1})", sl != 0 or tag == "stopped")

    for tag in ("chain", "trackbtn", "presses", "unattended"):
        if not exists(tag):
            continue
        clean(tag)
        b, im = b3_(tag), img(tag)
        sl = [b[p * PSTRIDE + PBYTE] for p in (1, 2, 3)]
        # unattended: the CCs edit the playing Parts' levels (+0x10..+0x21,
        # measured); the Kits keep theirs
        cut = (lambda x: x[:0x10] + x[0x22:]) if tag == "unattended" else (lambda x: x)
        held = [cut(slot(b, x)) == cut(kit(im, k)) for x, k in zip(sl, (0, 1, 4))]
        check(f"{tag}: patterns 2-4 on slots {[x + 1 for x in sl]}, each holding its Kit ({held})",
              len(set(sl)) == 3 and all(held))

    if exists("extnoclk"):
        clean("extnoclk")
        eng = (OUT / "extnoclk_eng.bin").read_bytes()
        check(f"extnoclk: MIDI start without the clock, the switch does not land (engine {eng[0] + 1}:{eng[1] + 1}): "
              "extplay's switch is the clock's", eng[0] == BANK and eng[1] == 0)

    if exists("a5"):
        clean("a5")
        b, im = b3_("a5"), img("a5")
        sl = [b[p * PSTRIDE + PBYTE] for p in (1, 2, 3)]
        held = [slot(b, x) == kit(im, k) for x, k in zip(sl, (0, 1, 4))]
        eng = (OUT / "a5_eng.bin").read_bytes()
        check(f"a5: patterns 2-4 on slots {[x + 1 for x in sl]}, each holding its Kit ({held}); "
              f"the engine on pattern 4's (engine {eng[0] + 1}:{eng[1] + 1})",
              all(held) and eng[0] == BANK and eng[1] == sl[2])

    if exists("cc"):
        clean("cc")
        log = (OUT / "cc.txt").read_text(errors="replace")
        check("cc: the sequencer ran its 3,100 frames", "REACHED" in log)

    def cur_slot(b, ptn=0):
        return b[ptn * PSTRIDE + PBYTE]

    if exists("load"):
        clean("load")
        im, b = img("load"), b3_("load")
        b0 = img("base") if exists("base") else None
        k = im[O_ASSIGN + BANK * 16]
        s_ = cur_slot(b)
        check(f"load: pattern 1 plays Kit {k + 1} (two rows above Kit {BANK * 4 + s_ + 1}), its slot holds it",
              k == BANK * 4 + s_ - 2 and im[O_RESID + BANK * 4 + s_] == k and slot(b, s_) == kit(im, k))
        sv = b[SAVED + s_ * PARTSZ:SAVED + (s_ + 1) * PARTSZ]
        check("load: the saved Part is the Kit too (FUNC+CUE reloads it)", sv == kit(im, k))
    if exists("undo"):
        clean("undo")
        im, b = img("undo"), b3_("undo")
        s_ = cur_slot(b)
        check(f"undo: UNDO KIT brought Kit {BANK * 4 + s_ + 1} back ({im[O_ASSIGN + BANK * 16] + 1})",
              im[O_ASSIGN + BANK * 16] == BANK * 4 + s_)
    for tag, rows, named in (("save", 2, True), ("quick", 1, False)):
        if not exists(tag):
            continue
        clean(tag)
        im, b = img(tag), b3_(tag)
        s_ = cur_slot(b)
        k = BANK * 4 + s_ + rows
        name = im[O_LIB + k * REC:O_LIB + k * REC + 8].split(b"\0")[0]
        check(f"{tag}: Kit {k + 1} = the current Part, assigned, named {name}",
              kit(im, k) == slot(b, s_) and im[O_ASSIGN + BANK * 16] == k and name)

    if exists("drawn") and exists("drawnf"):
        clean("drawn")
        a_, b_ = (OUT / "drawn_lcd.bin").read_bytes(), (OUT / "drawnf_lcd.bin").read_bytes()
        check(f"drawn: LOAD KIT while stopped draws the Kit at once (screen equal to after a FUNC tap, "
              f"{sum(x != y for x, y in zip(a_, b_))} bytes differ)", a_ == b_)

    if exists("lvl") and exists("lvl0"):
        clean("lvl")
        c0 = struct.unpack(">9I", (OUT / "lvl0_menu.bin").read_bytes())[6]
        c1 = struct.unpack(">9I", (OUT / "lvl_menu.bin").read_bytes())[6]
        check(f"lvl: LEVEL scrolls LOAD KIT: +3 then -1 moved the cursor {c0} -> {c1}", c1 == c0 + 2)
    if exists("lvlstock") and exists("lvlbase"):
        clean("lvlstock")
        a_, b_ = (OUT / "lvlbase_lev.bin").read_bytes(), (OUT / "lvlstock_lev.bin").read_bytes()
        moved = [(i // 2 + 1, a_[i], b_[i]) for i in range(0, 16, 2) if a_[i] != b_[i]]
        check(f"lvlstock: with no list open LEVEL is stock's: the current track's level moved (track, from, to: {moved})",
              len(moved) == 1 and moved[0][2] == moved[0][1] + 3)
    if exists("ptnmask"):
        clean("ptnmask")
        m_ = struct.unpack(">H", (OUT / "ptnmask_mask.bin").read_bytes())[0]
        check(f"ptnmask: TRIG 2 then TRIG 3 under PATTERN leave no TRIG held in the mask ({m_:#06x})", m_ == 0)

    # ---- record 255 ---------------------------------------------------------------
    def first_empty(im):
        return next(k for k in range(255) if not im[O_VALID + k // 8] >> (k % 8) & 1)
    if exists("k256save"):
        clean("k256save")
        im = img("k256save"); cur = struct.unpack(">9I", (OUT / "k256save_menu.bin").read_bytes())[6]
        check(f"k256save: no Kit in the slot: SAVE KIT opens on Kit {cur + 1}, the first empty one "
              f"({first_empty(im) + 1})", cur == first_empty(im))
    if exists("k256load"):
        clean("k256load")
        cur = struct.unpack(">9I", (OUT / "k256load_menu.bin").read_bytes())[6]
        check(f"k256load: no Kit in the slot: LOAD KIT opens on UNDO KIT (row {cur})", cur == 0)
    if exists("k256rescue") and exists("base"):
        clean("k256rescue")
        im, k = img("k256rescue"), first_empty(img("base"))
        check(f"k256rescue: record 255's Part is Kit {k + 1}, named RESCUE, pattern 5 on it; record 255 empty",
              im[O_LIB + k * REC:O_LIB + k * REC + 7] == b"RESCUE\0" and im[O_VALID + k // 8] >> (k % 8) & 1
              and not im[O_VALID + 31] & 0x80 and im[O_ASSIGN + 5] == k)

    # ---- the MKI panel --------------------------------------------------------
    def menu(tag):
        w = struct.unpack(">9I", (OUT / f"{tag}_menu.bin").read_bytes())
        lw = lambda n: struct.unpack(">I", (OUT / f"{tag}_{n}.bin").read_bytes()[:4])[0]
        return dict(cbs=w[0], obj=w[2], count=w[8], mown=lw("mown"), pset=lw("pset"), ted=lw("ted"))
    cb = sym["CBTAB"]
    if exists("mkiptn"):
        clean("mkiptn"); m = menu("mkiptn")
        check(f"mkiptn: FUNC+BANK opens PATTERN SETTINGS ({m['pset']:#x}), no list", m["pset"] and not m["obj"])
    if exists("mkilist"):
        clean("mkilist"); m = menu("mkilist")
        check(f"mkilist: FUNC+MIDI, FUNC+BANK: SAVE KIT open ({m['count']} rows), PATTERN SETTINGS closed",
              m["obj"] and m["cbs"] == cb and m["mown"] == 2 and m["count"] == 255 and not m["pset"])
    if exists("mkiclose"):
        clean("mkiclose"); m = menu("mkiclose")
        check("mkiclose: FUNC+BANK again closes SAVE KIT", not m["obj"] and not m["pset"])
    if exists("mkino"):
        clean("mkino"); m = menu("mkino")
        check("mkino: LOAD KIT closed by NO, FUNC+BANK: PATTERN SETTINGS", m["pset"] and not m["obj"])
    if exists("mkisave"):
        clean("mkisave")
        im, b = img("mkisave"), b3_("mkisave")
        s_ = cur_slot(b)
        k = BANK * 4 + s_ + 2
        name = im[O_LIB + k * REC:O_LIB + k * REC + 8].split(b"\0")[0]
        check(f"mkisave: Kit {k + 1} = the current Part, assigned, named {name}",
              kit(im, k) == slot(b, s_) and im[O_ASSIGN + BANK * 16] == k and name)
    if exists("mkiedit") and exists("base"):
        clean("mkiedit"); m = menu("mkiedit")
        check("mkiedit: FUNC+BANK over the Kit name editor cancels it: no editor, no list, "
              "no PATTERN SETTINGS, the Kits as loaded",
              not m["ted"] and not m["obj"] and not m["pset"] and img("mkiedit")[O_LIB:] == img("base")[O_LIB:])
    if exists("mkiforeign"):
        clean("mkiforeign"); m = menu("mkiforeign")
        check(f"mkiforeign: a list whose callbacks are not KITS': FUNC+BANK is stock's (PATTERN SETTINGS "
              f"{m['pset']:#x}), SAVE KIT not opened (MOWN {m['mown']})", m["pset"] and m["mown"] == 1)

    # ---- Phase 2 checks -------------------------------------------------------
    def valid(im, k):
        return im[O_VALID + k // 8] >> (k % 8) & 1

    if exists("lcopy") and exists("base"):
        clean("lcopy")
        im, b0 = img("lcopy"), img("base")
        s_ = cur_slot(b3_("lcopy"))
        k = BANK * 4 + s_
        check(f"lcopy: Kit {k} (above Kit {k + 1}) is a copy of it",
              im[O_LIB + (k - 1) * REC:O_LIB + k * REC] == b0[O_LIB + k * REC:O_LIB + (k + 1) * REC])
    if exists("lundo") and exists("base"):
        clean("lundo")
        im, b0 = img("lundo"), img("base")
        k = BANK * 4 + cur_slot(b3_("lundo")) - 1
        check(f"lundo: the second paste brought Kit {k + 1} back", kit(im, k) == kit(b0, k))
    if exists("lclear") and exists("base"):
        clean("lclear")
        im = img("lclear")
        k = BANK * 4 + cur_slot(b3_("lclear")) + 3
        check(f"lclear: Kit {k + 1} is empty", not valid(im, k))
    if exists("lclundo") and exists("base"):
        clean("lclundo")
        im, b0 = img("lclundo"), img("base")
        k = BANK * 4 + cur_slot(b3_("lclundo")) + 3
        check(f"lclundo: the second clear brought Kit {k + 1} back", valid(im, k) and kit(im, k) == kit(b0, k))
    if exists("ptncopy"):
        clean("ptncopy")
        im = img("ptncopy")
        check(f"ptncopy: pattern 14 plays pattern 1's Kit ({im[O_ASSIGN + BANK * 16 + 13]})",
              im[O_ASSIGN + BANK * 16 + 13] == 5)
    if exists("ptnundo"):
        clean("ptnundo")
        im = img("ptnundo")
        mid = (OUT / "ptnundo_mid.bin").read_bytes()[0]
        check(f"ptnundo: the paste gave pattern 14 Kit 6 ({mid + 1}), the undo its own Kit 4 back "
              f"({im[O_ASSIGN + BANK * 16 + 13] + 1})", mid == 5 and im[O_ASSIGN + BANK * 16 + 13] == 3)
    if exists("pclone"):
        clean("pclone")
        im = img("pclone")
        k2 = im[O_ASSIGN + BANK * 16 + 13]
        check(f"pclone: pattern 14 plays Kit {k2 + 1}, a copy of Kit 6",
              k2 not in (5, 0xff) and valid(im, k2) and kit(im, k2) == kit(im, 5))
    if exists("fright"):
        clean("fright")
        im, b = img("fright"), b3_("fright")
        k2 = im[O_ASSIGN + BANK * 16 + 13]
        k1 = img("base")[O_RESID + BANK * 4 + cur_slot(b3_("base"))] if exists("base") else BANK * 4
        same = all(b[i] == b[13 * PSTRIDE + i] for i in range(PSTRIDE) if i != PBYTE)
        check(f"fright: pattern 14 = pattern 1 ({same}), plays Kit {k2 + 1}, a copy of Kit {k1 + 1}",
              same and k2 not in (k1, 0xff) and kit(im, k2) == kit(im, k1))

    if exists("inactive"):
        clean("inactive")
        im, b = img("inactive"), b3_("inactive")
        same = all(b[i] == b[13 * PSTRIDE + i] for i in range(PSTRIDE) if i != PBYTE)
        check(f"inactive: pattern 14 = pattern 1 ({same}) with its Kit ({im[O_ASSIGN + BANK * 16 + 13] + 1}), "
              , same and im[O_ASSIGN + BANK * 16 + 13] == 5)
    if exists("inundo") and exists("base"):
        clean("inundo")
        b, b0 = b3_("inundo"), b3_("base")
        same = b[13 * PSTRIDE:14 * PSTRIDE] == b0[13 * PSTRIDE:14 * PSTRIDE]
        check(f"inundo: the second paste gave pattern 14 back as it was ({same}, Kit "
              f"{img('inundo')[O_ASSIGN + BANK * 16 + 13]})", same)

    # ---- the save, a second boot, power cycles --------------------------------
    s1 = OUT / "power.script"
    sc = Script(); sc.tap("no"); s1.write_text(sc.text())

    def boot(tag, card_, cs1=None):
        cmd = [EMU, "--image", image, "--card", card_, "--set", "OCTABAM", "--project", "KITS", "--load-ms", "90000",
               "--live-script", s1, "--mem-dump", dumps(tag)]
        if cs1 is not None:
            cmd += ["--cs1-in", cs1, "--no-post"]
        run(cmd, OUT / f"{tag}.txt")
        return tag

    if exists("saveproj"):
        clean("saveproj")
        want = img("saveproj")
        files = emu_card.extract_image((OUT / "saved.img").read_bytes())
        for ext in ("work", "strd"):
            d = next((v for k, v in files.items() if k.lower().endswith(f"/kits/kits.{ext}")), b"")
            check(f"saveproj: kits.{ext} holds the loaded Kit's assignment",
                  len(d) == IMG_LEN and d[O_ASSIGN + BANK * 16] == want[O_ASSIGN + BANK * 16])
        jobs = [("reboot", OUT / "saved.img", None), ("power", OUT / "saved.img", OUT / "cs1_saved.bin")]
        if exists("unsaved"):
            jobs.append(("powerun", OUT / "unsaved.img", OUT / "cs1_unsaved.bin"))
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(lambda j: boot(*j), jobs))
        for tag, ref in (("reboot", "saveproj"), ("power", "saveproj"), ("powerun", "unsaved")):
            if not exists(tag):
                continue
            clean(tag)
            im, w = img(tag), img(ref)
            check(f"{tag}: ASSIGN and RESID as before ({im[O_ASSIGN + BANK * 16]}, "
                  f"{im[O_RESID + BANK * 4:O_RESID + BANK * 4 + 4].hex()})",
                  im[O_ASSIGN:O_RESID + 64] == w[O_ASSIGN:O_RESID + 64] or
                  (im[O_ASSIGN:O_VALID] == w[O_ASSIGN:O_VALID] and im[O_RESID:O_RESID + 64] == w[O_RESID:O_RESID + 64]))

    # ---- Em's v3 files ----------------------------------------------------------
    ok_dir = pathlib.Path(a.octakit_project).expanduser()
    v3 = [ok_dir / f"kits3{p}.work" for p in "ab"]
    if (not only or "import" in only) and all(f.is_file() for f in v3):
        c = stage(ok_dir, "IMPORT", extra=v3)
        run([EMU, "--image", image, "--card", c, "--set", "OCTABAM", "--project", "IMPORT", "--load-ms", "90000",
             "--live-script", s1, "--mem-dump", dumps("import"), "--card-out", OUT / "import.img"], OUT / "import.txt")
        clean("import")
        im = img("import")
        ref, asg = v3_reference([f.read_bytes() for f in v3])
        occ = {k: v for k, v in ref.items() if v}
        bad = [k for k, (name, pay) in occ.items()
               if kit(im, k) != pay or im[O_LIB + k * REC:O_LIB + k * REC + 8].split(b"\0")[0] != name
               or not im[O_VALID + k // 8] >> (k % 8) & 1]
        check(f"import: {len(occ)} occupied Kits, name and Part as her files give them ({bad[:5]})", occ and not bad)
        check("import: ASSIGN from her newest manifest", list(im[O_ASSIGN:O_ASSIGN + 256]) == asg)
        files = emu_card.extract_image((OUT / "import.img").read_bytes())
        check("import: kits.work written, her files left in place",
              any(k.lower().endswith("/import/kits.work") for k in files)
              and all(any(k.endswith(f"/IMPORT/kits3{p}.work") for k in files) for p in "ab"))
    elif not only or "import" in only:
        print("  [SKIP] import: no kits3a/b.work at --octakit-project")

    # ---- a rejected bank file, a missing project --------------------------------
    sd = pathlib.Path(a.strand_project).expanduser()
    if (not only or "strand" in only) and (sd / "project.work").is_file():
        c = stage(sd, "STRAND")
        sc = Script(); sc.tap("no"); sc.tap("play", 9000); sc.tap("stop", 400)
        sc.hold("func", "rec"); sc.hold("ptn", 1); sc.hold("func", "stop", gap=1000)   # copy, pattern 2, paste
        (OUT / "strand.script").write_text(sc.text())
        run([EMU, "--image", image, "--card", c, "--set", "OCTABAM", "--project", "STRAND", "--load-ms", "90000",
             "--dsp", "--live-script", OUT / "strand.script", "--mem-dump", dumps("strand")], OUT / "strand.txt")
        clean("strand")
    elif not only or "strand" in only:
        print("  [SKIP] strand: no project at --strand-project")
    if not only or "noproj" in only:
        run([EMU, "--image", image, "--card", card, "--set", "OCTABAM", "--project", "NOPROJ", "--load-ms", "90000",
             "--live-script", s1, "--mem-dump", dumps("noproj")], OUT / "noproj.txt")
        s = st("noproj")
        log = (OUT / "noproj.txt").read_text(errors="replace")
        check(f"noproj: the load ran, no halt (READY {s['READY']}, IOERR {s['IOERR']})",
              not any(w in log for w in ("stopped before", "FAULT", "ILLEGAL")))

    print(f"verify_kits: {'FAIL' if fails else 'ok'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
