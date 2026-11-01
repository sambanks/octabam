#!/usr/bin/env python3
"""KITS under the port: the Kits each pattern plays, staged through the
stock Part slots; LOAD / SAVE KIT; kits.work over a save, a reboot and a
power cycle; the migration, Em's v3 import, a rejected bank file and a
missing project directory.

    python3 tools/verify/verify_kits.py REMIX [--project DIR] [--octakit-project DIR]
                                              [--strand-project DIR]

KITS_JOBS is the scenario forks run at once; by default the free gate
slots, at least 3 (fork_jobs).

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
  editfull  slots 2-4 each edited (a Part byte no Kit holds), pattern 1
            playing slot 1, PTN+TRIG 2 (Kit 1, Part byte on slot 1):
            pattern 2 plays Kit 1; the edits are not lost.
  editback  editfull, then PTN+TRIG 4 (Kit 10, Part byte on slot 2): its
            slot holds Kit 10 with the edit slot 2 had (from the edit
            pool), unsaved; the library's Kit 10 unchanged. With MIDI
            SCENES each edited slot also holds a scene lock (table byte
            0x015): slot 2's comes back with Kit 10, the other slots' stay.
  freload   FUNC+CUE with an edit on pattern 1's slot (its unsaved bit
            clear, so stock's reload does nothing): the slot is its Kit.
  statusnew NEW PROJECT on the panel: the status line is "001 ---"
            (stock draws "Pt:1 ONE"); the plane is dumped, not compared.
  noasg     pattern 3 with no Kit on slot 2 (Kit 10); PTN+TRIG 2 (Kit 1,
            Part byte on slot 2), then PTN+TRIG 3: pattern 3 still plays
            Kit 10.
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
  lfyes     PART, DOWN, FUNC+YES: stock's ARM ALL does not run (both arm
            words clear), nothing is saved, LOAD KIT stays open.
  lname     PART, the plane 150 ms in: LOAD KIT's name toast (sname: SAVE
            KIT's); dumped, not compared.
  newproj   PROJECT > CHANGE > <CREATE EMPTY PROJECT> on the panel; on
            patterns 2 and 3 knob A turned and SAVE KIT (two and three rows
            down); playing, PTN 2, PTN 3: each pattern's slot holds its Kit,
            the engine plays pattern 3's.
  newsave   the same project, SAVE PROJECT: every bank file the size of the
            gate project's, with its checksum; a cold boot of that card
            (newboot) loads it with no bank file refused in the firmware's
            LOG, the Kits and assignments as saved, and PTN 2 playing
            stages Kit 3.
  saveproj  LOAD KIT, SAVE PROJECT: kits.work and kits.strd on the card
            with the change; a second boot of that card reads it; a power
            cycle (`--cs1-in`, `--no-post`) of the same card too, and of a
            card whose change was never saved (RESID and ASSIGN from CS1).
  lcopy     LOAD KIT open on the current Kit: FUNC+REC, UP, FUNC+STOP:
            the Kit above is a copy; FUNC+STOP again: it is back.
  lclear    SAVE KIT open, DOWN x3, FUNC+PLAY: that Kit is empty; again:
            it is back.
  lcopylive LOAD KIT open on the current Kit, whose slot carries an edit:
            FUNC+REC, UP, FUNC+STOP: the Kit above is the slot's Part with
            the edit, not the library's record.
  follow    LOAD KIT open, PTN+TRIG 2 (Kit 4): the list's cursor moves to
            Kit 4.
  lclearlive LOAD KIT open on the current Kit, FUNC+PLAY: the Kit is empty
            and the playing slot is a cleared Part at once.
  swback    Kit 3 on pattern 3 and Kit 4 on pattern 4, playing, PTN 3, 4, 3, 4:
            each pattern keeps its Kit and its slot holds it.
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
import time
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
REC1 = REC
IMG_LEN = O_LIB + 256 * REC
TRK = 0x8000182a
CS1, CS1_LEN = 0x10000000, 0x100000
STATE = ("READY KDIRTY NOWRITE PENDING ISR NOSLOT INVALID IOERR BADFILE "
         "STAGED REPOINT STAMP").split()
K = dict(no=0x32, yes=0x31, play=0x28, stop=0x27, ptn=0x2e, func=0x2d, part=0x1d,
         up=0x33, down=0x20, right=0x21, mixer=0x30, rec=0x29)
BANK = 2                                  # bank 3: the project's own
ENG_PART = 0x80001829                     # the engine's current Part: changes when a pattern switch lands
CUR_PTN = 0x80000004                      # the current pattern: changes when a switch lands on the same Part too
TEMPO24 = 0x80001814, 0x80000020          # BPM x 24 and its shadow (long); the setter's clamp is 720..7200
FAST = [(a + i, v) for a in TEMPO24 for i, v in enumerate((0, 0, 5760 >> 8, 5760 & 255))]   # 240 BPM
LOCK_IDX = 0x015                          # a lock-table index: scene A, track 1, flat 21
EDIT_OFF, EDIT_VAL = 0x10, 0x30           # a Part byte (track 1's level) set to EDIT_VAL + slot: an edit no Kit holds
NEWKNOB = (5, 11)                        # knob A turns on patterns 2 and 3 of the panel-made project
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


STARTED = {}        # log -> the boot start() launched


def fork_jobs():
    """Scenario forks at once: KITS_JOBS, else the machine's gate slots no
    other session holds, at least 3 (tools/verify/slots.py). bottleservice,
    longest first: 3 jobs 264 s, 4 251 s, 5 231 s (12 Oct 2026; the
    performance cores are shared with the MKI pass and strand)."""
    if os.environ.get("KITS_JOBS"):
        return int(os.environ["KITS_JOBS"])
    import slots
    return max(3, slots.count() - len([h for h in slots.holders() if f"pid {os.getpid()} " not in h[1]]))
# The MKII scenarios that run longest, longest first: wall seconds of each
# fork on bottleservice at 3 jobs (12 Oct 2026, its log's birth to its last
# write): swback 81, unattended 77, chain 63, presses 61, saveproj 48, a5
# 31, extplay 31, trackbtn 25, progchg 24, free 24, trackbtn1 24, repoint
# 23, extnoclk 21; the rest 11 s or less, in their own order after.
QUICK_SKIP = ("unattended", "presses", "strand")      # 125 s, 89 s and 106-188 s of a 400-470 s gate (12 Oct 2026)
LONGEST = ("swback", "unattended", "chain", "presses", "saveproj", "a5", "extplay", "trackbtn",
           "progchg", "free", "trackbtn1", "repoint", "extnoclk")


def start(cmd, log):
    """run(), in the background: finish(log) waits for it. For the boots
    that need nothing from the main scenario run (strand, import, noproj):
    after it they took 133 s of a 545 s gate, strand 106 s on its own
    (12 Oct 2026)."""
    f = open(log, "w")
    f.write(" ".join(map(str, cmd)) + "\n"); f.flush()
    STARTED[log] = (subprocess.Popen(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT), f)


def finish(log):
    p, f = STARTED.pop(log)
    rc = p.wait()
    f.close()
    if rc:
        sys.exit(f"verify_kits: ot_emu exit {rc} -- {log}")
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

    def until(self, addr, nbytes, op="chg", cap=20000):
        """Wait for the event instead of a time (ot_emu's `wait` line): the bytes at
        `addr` differ from what they were when the wait began (chg), or are
        (eq) / are not (ne) the hex `nbytes`; at most `cap` ms. A cap reached
        is a FAIL (clean()). The lines after it follow the event."""
        arg = "00" * nbytes if op == "chg" else nbytes
        self.lines.append(f"{self.t:.0f} wait {addr:#x} {arg} {op} {cap}"); self.t += cap

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
    ap.add_argument("--quick", action="store_true",
                    help="skip the scenarios in QUICK_SKIP (FULL only); make reach sets OCTABAM_QUICK=1 in QUICK mode")
    a = ap.parse_args()
    remix = registry.remix(a.remix)
    global REC, IMG_LEN
    if "MIDI SCENES" in remix.modules:        # a Kit record carries its Part's lock table (kits.work version 2)
        REC = REC1 + 4096
        IMG_LEN = O_LIB + 256 * REC
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
    quick = a.quick or os.environ.get("OCTABAM_QUICK") == "1"
    skipped = [t for t in QUICK_SKIP if not only or t in only] if quick else []
    if skipped:
        print(f"  [ -- ] FULL only (skipped by --quick): {', '.join(skipped)}")
        for t in skipped:                       # a leftover of a full run must not be read as this run's
            for f in OUT.glob(f"{t}_*"):
                f.unlink()
            (OUT / f"{t}.txt").unlink(missing_ok=True)

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

    SAVE_MARGIN = int(os.environ.get("KITS_SAVE_MARGIN", "15000"))
    scen, mki_scen, scripts = [], [], {}
    LASTDUMP = {}
    NOPLAY = set(filter(None, os.environ.get("KITS_NOPLAY", "").split(",")))     # negative test: these scenarios never press PLAY

    def add(tag, script=None, pokes=(), extra=(), more_dumps="", mki=False, fast=False):
        if (only and tag not in only) or tag in skipped:
            return
        args = []
        pokes = list(pokes) + (FAST if fast else [])
        if tag in NOPLAY and script is not None:        # the negative test: no transport, no switch
            script.lines = [l for l in script.lines if "key 0x28 " not in l]
        if pokes:
            args += ["--poke", ";".join(f"{x:#x}={v:#x}" for x, v in pokes)]
        if script is not None:
            sp = OUT / f"{tag}.script"; sp.write_text(script.text()); args += ["--live-script", sp]
        args += list(extra) + ["--mem-dump", dumps(tag) + more_dumps]
        last = (dumps(tag) + more_dumps).split(";")[-1]            # written last: the scenario is complete when it is
        LASTDUMP[tag] = (last.split("=", 1)[1], int(last.split("=", 1)[0].split(",")[1], 0),
                         next((str(extra[i + 1]) for i, x in enumerate(extra) if x == "--card-out"), None))
        (mki_scen if mki else scen).append(f"{OUT / (tag + '.txt')} " + " ".join(map(str, args)))
        scripts[tag] = script

    def playing_switch(s, ptn):
        s.tap("no"); s.tap("play", 2000); s.hold("ptn", ptn); s.until(ENG_PART, 1)

    s = Script(); s.tap("no"); add("base", s, extra=["--card-out", OUT / "base.img"])
    s = Script(); playing_switch(s, 1); add("free", s, [(pa(1), 0)], fast=True)
    s = Script(); playing_switch(s, 1); add("repoint", s, [(pa(1), 0), (pb(1), 0)], fast=True)
    s = Script(); s.tap("no"); s.hold("ptn", 1); s.wait(1500); add("stopped", s, [(pa(1), 0), (pb(1), 0)])
    (OUT / "progchg.midi").write_text("200 c0 21\n")
    add("progchg", None, [(pa(1), 0), (pb(1), 0)],
        ["--sequencer", "--internal-clock", "--frames", "60000", "--midi", OUT / "progchg.midi"])

    def chain(s, extra=None):
        s.tap("no"); s.tap("play", 2000)
        s.down("ptn"); s.down(1, 120); s.tap(2, 120); s.tap(3, 120); s.up(1, 120); s.up("ptn", 300)
        if extra:
            extra(s)
    # Kit 3 on pattern 3 and Kit 4 on pattern 4 (a field report: pattern 4 reverted to Kit 3
    # on a pattern switch); switched 3, 4, 3, 4 while playing.
    s = Script(); s.tap("no"); s.tap("play", 2000)
    for p_ in (2, 3, 2, 3):
        s.hold("ptn", p_); s.until(ENG_PART, 1)
    add("swback", s, [(pa(2), 2), (pa(3), 3), (pb(2), 0), (pb(3), 0)], fast=True)
    # Slots 2-4 each carry an edit no Kit holds (EDIT_OFF), pattern 1 plays
    # slot 1: pattern 2 (Kit 1, Part byte on slot 1) has no slot it may take.
    edits = [(b3 + WORK + s_ * PARTSZ + EDIT_OFF, EDIT_VAL + s_) for s_ in (1, 2, 3)]
    s = Script(); s.tap("no"); s.tap("play", 2000); s.hold("ptn", 1); s.until(CUR_PTN, "01", "eq")
    add("editfull", s, [(pa(1), 0), (pb(1), 0)] + edits, fast=True)
    # ... then PTN+TRIG 4 (Kit 10, Part byte on slot 2): the edit slot 2 held
    # comes back with Kit 10, unsaved; Kit 10 in the library as it was.
    s = Script(); s.tap("no"); s.tap("play", 2000); s.hold("ptn", 1); s.until(CUR_PTN, "01", "eq")
    s.hold("ptn", 3); s.until(CUR_PTN, "03", "eq")
    lockp, lockd = [], ""
    if "MIDI SCENES" in remix.modules:        # each edited slot also holds a scene lock no Kit has (its lock table, byte 0x015)
        scn = sym["scn_lib"] + BANK * 4 * 4096
        lockp = [(scn + s_ * 4096 + LOCK_IDX, EDIT_VAL + s_) for s_ in (1, 2, 3)]
        lockd = f";{scn:#x},{4 * 4096:#x}=" + str(OUT / "editback_msc.bin")
    add("editback", s, [(pa(1), 0), (pb(1), 0), (pa(3), BANK * 4 + 1), (pb(3), 1)] + edits + lockp,
        more_dumps=lockd, fast=True)
    # Pattern 3 has no Kit and plays slot 2 (Kit 10); pattern 2's Kit 1 lands
    # in slot 2, its own; then PTN 3.
    s = Script(); playing_switch(s, 1); s.hold("ptn", 2); s.until(CUR_PTN, "02", "eq")
    add("noasg", s, [(pa(1), 0), (pb(1), 1), (pa(2), 0xff), (pb(2), 1)], fast=True)
    cpokes = [(pa(1), 0), (pa(2), 1), (pa(3), 4), (pb(1), 0), (pb(2), 0), (pb(3), 0)]
    def chain_cycle(s):                      # patterns 2, 3, 4 each land: three changes of the engine's Part
        for _ in range(3):
            s.until(ENG_PART, 1)
    s = Script(); chain(s, chain_cycle); add("chain", s, cpokes, fast=True)

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
    lcdd = f";{LCD:#x},1024="
    menud = f";{MENU:#x},36="
    s = Script(); s.tap("no"); s.hold("func", "part", gap=800); s.tap("down", 200)
    s.down("func", 100); s.tap("yes", 200); s.up("func", 1500); add("quick", s)
    # FUNC+YES with LOAD KIT open: stock's ARM ALL must not run, nothing is saved, the list stays
    armd = f";0x46c7ff64,4={OUT / 'lfyes_arm.bin'};0x46c803d4,4={OUT / 'lfyes_arm2.bin'}"
    s = Script(); s.tap("no"); s.tap("part", 800); s.tap("down", 200)
    s.down("func", 100); s.tap("yes", 200); s.up("func", 1500)
    add("lfyes", s, more_dumps=armd + menud + str(OUT / "lfyes_menu.bin"))
    # each list says which it is when it opens (both look alike): the screen, 150 ms in
    s = Script(); s.tap("no"); s.tap("part", 150); add("lname", s, more_dumps=lcdd + str(OUT / "lname_lcd.bin"))
    s = Script(); s.tap("no"); s.hold("func", "part", gap=150)
    add("sname", s, more_dumps=lcdd + str(OUT / "sname_lcd.bin"))

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
    s = Script(); s.tap("no"); s.tap("part", 800); s.hold("func", "rec"); s.tap("up", 200)
    s.hold("func", "stop", gap=600); add("lcopylive", s, [(b3 + WORK + EDIT_OFF, EDIT_VAL)])
    s = Script(); s.tap("no"); s.tap("part", 800); s.hold("func", "play", gap=1500); add("lclearlive", s)
    s = Script(); s.tap("no"); s.tap("part", 800); s.hold("ptn", 1, gap=1500); s.wait(1500)
    add("follow", s, [(pa(1), 3)], more_dumps=f";{sym['MSEL']:#x},4=" + str(OUT / "follow_msel.bin"))
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
    add("fright", s, [(pa(0), 5)], more_dumps=f";0x460d1742,4=" + str(OUT / "fright_ptnwin.bin"))

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
    s.tap(0x1c, 1000); s.tap("right", 700); s.tap("down", 500); s.tap("yes", 1100); s.tap("yes", 400)  # PROJ: SAVE PROJECT
    s.until(KS + 4, "00000000", "eq", 60000); s.wait(SAVE_MARGIN)       # kits.work written (KDIRTY clear), then the rest of the save
    add("saveproj", s, extra=["--card-out", OUT / "saved.img"],
        more_dumps=f";{CS1:#x},{CS1_LEN:#x}={OUT / 'cs1_saved.bin'}")
    s = Script(); loadkit(s); s.wait(2000)
    add("unsaved", s, extra=["--card-out", OUT / "unsaved.img"],
        more_dumps=f";{CS1:#x},{CS1_LEN:#x}={OUT / 'cs1_unsaved.bin'}")

    # ---- a project made on the panel ------------------------------------------
    # PROJECT > CHANGE > <CREATE EMPTY PROJECT>, its name confirmed (the keys
    # verify_brain's pset_new uses); pattern 2: knob A +NEWKNOB[0], SAVE KIT two
    # rows down; pattern 3: knob A +NEWKNOB[1], SAVE KIT three rows down.
    def newproj(s):
        s.tap("no"); s.tap(0x1c, 1000); s.tap("yes", 1000); s.tap("yes", 1000); s.tap("up", 600)
        s.tap("yes", 1400); s.tap("yes", 13000)
        for p_, rows, d in ((1, 2, NEWKNOB[0]), (2, 3, NEWKNOB[1])):
            s.hold("ptn", p_, gap=1500); s.send(f"enc 0 {d}", 600)
            s.hold("func", "part", gap=800)
            for _ in range(rows):
                s.tap("down", 200)
            s.tap("yes", 1200); s.tap("yes", 1500)
    newb = f";{BLOB:#x},{BSTRIDE:#x}={OUT / 'NAME_b1.bin'}"
    s = Script(); s.tap("no"); s.hold("func", 0x2a, gap=1500); s.wait(1500)       # FUNC+CUE
    add("freload", s, [(b3 + WORK + EDIT_OFF, EDIT_VAL)])
    s = Script(); s.tap("no"); s.tap(0x1c, 1000); s.tap("yes", 1000); s.tap("yes", 1000); s.tap("up", 600)
    s.tap("yes", 1400); s.tap("yes", 13000); s.wait(1500)
    add("statusnew", s, more_dumps=f";{LCD:#x},1024=" + str(OUT / "statusnew_lcd.bin"))
    s = Script(); newproj(s); s.tap("play", 2000)
    for p_ in (1, 2):
        s.hold("ptn", p_); s.until(ENG_PART, 1)
    add("newproj", s, more_dumps=newb.replace("NAME", "newproj"))
    s = Script(); newproj(s)
    s.tap(0x1c, 1000); s.tap("right", 700); s.tap("down", 500); s.tap("yes", 1100); s.tap("yes", 30000)  # SAVE PROJECT
    add("newsave", s, extra=["--card-out", OUT / "newsave.img"], more_dumps=newb.replace("NAME", "newsave"))

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
    # ---- the boots that need nothing from the main run, started beside it ------
    s1 = OUT / "power.script"
    sc = Script(); sc.tap("no"); s1.write_text(sc.text())
    def boot(tag, card_, cs1=None):
        cmd = [EMU, "--image", image, "--card", card_, "--set", "OCTABAM", "--project", "KITS", "--load-ms", "90000",
               "--live-script", s1, "--mem-dump", dumps(tag)]
        if cs1 is not None:
            cmd += ["--cs1-in", cs1, "--no-post"]
        run(cmd, OUT / f"{tag}.txt")
        return tag

    # Boots that read a scenario's output start the moment it is complete (its
    # last dump written in full, and its card image), beside the rest of the pool.
    bg, bgpool = {}, ThreadPoolExecutor(8)

    def complete(tag, wait=1800):
        path, n, card = LASTDUMP[tag]
        t0 = time.monotonic()
        while not (os.path.isfile(path) and os.path.getsize(path) == n and (card is None or os.path.isfile(card))):
            if time.monotonic() - t0 > wait:
                raise SystemExit(f"verify_kits: scenario {tag} never completed ({path})")
            time.sleep(1)
        time.sleep(1)

    for tag in scripts:       # a leftover of an earlier run would read as complete: clear what complete() looks for
        for f in LASTDUMP[tag][::2]:
            if f:
                pathlib.Path(f).unlink(missing_ok=True)

    def defer(name, tags, fn):
        if all(t in scripts for t in tags):
            bg[name] = bgpool.submit(lambda: (*map(complete, tags), fn())[-1])

    def joined(name):
        if name in bg:
            bg.pop(name).result()


    # The blank boot: no CS1 -- an EMPTY RESET's next power-up (the stock
    # checksum fails, the boot takes the blank path). The stock blank project
    # never runs the store's new-project event, so without the boot hook
    # (kits_bootblank) KITS stays off and PART opens the stock Part window
    # (a field report, 15 Oct 2026). The hook makes the boot's blank project
    # a KITS project: the empty library, READY from the first screen.
    def blankboot_run():
        dmp = (f"{KS:#x},48={OUT / 'blank_st.bin'};0x100f85a0,72={OUT / 'blank_cs1.bin'};"
               f"0x46c82456,4={OUT / 'blank_cur.bin'}")
        run([EMU, "--image", image, "--card", card, "--set", "OCTABAM", "--project", "KITS",
             "--load-ms", "90000", "--no-post", "--live-script", s1, "--mem-dump", dmp], OUT / "blank.txt")

    if not only or "blank" in only:
        for f in ("blank_st.bin", "blank_cs1.bin", "blank_cur.bin", "blank.txt"):
            (OUT / f).unlink(missing_ok=True)
        defer("blank", (), blankboot_run)

    def newboot_run():
        files = emu_card.extract_image((OUT / "newsave.img").read_bytes())
        name = next(k.split("/")[1] for k in files if k.startswith("OCTABAM/") and k.count("/") == 2
                    and k.split("/")[1] != "KITS")
        sc = Script(); sc.tap("no"); sc.tap("play", 2000); sc.hold("ptn", 1); sc.until(ENG_PART, 1)
        (OUT / "newboot.script").write_text(sc.text())
        run([EMU, "--image", image, "--card", OUT / "newsave.img", "--set", "OCTABAM", "--project", name,
             "--load-ms", "90000", "--mkii", "--live-script", OUT / "newboot.script", "--card-out", OUT / "newboot.img",
             "--mem-dump", dumps("newboot") + newb.replace("NAME", "newboot")], OUT / "newboot.txt")

    def v1up_run():
        kw = next((v for k, v in emu_card.extract_image((OUT / "base.img").read_bytes()).items()
                   if k.lower().endswith("/kits/kits.work")), b"")
        body = kw[64:O_LIB]
        for k in range(256):
            body += kw[O_LIB + k * REC:O_LIB + k * REC + REC1]
        v1 = struct.pack(">4sIII", b"KITS", 1, O_LIB + 256 * REC1, zlib.crc32(body)) + bytes(48) + body
        (OUT / "v1up_kits").mkdir(exist_ok=True)
        f = OUT / "v1up_kits/kits.work"; f.write_bytes(v1)
        c = stage(pathlib.Path(a.strand_project).expanduser(), "V1UP", extra=[f])
        run([EMU, "--image", image, "--card", c, "--set", "OCTABAM", "--project", "V1UP", "--load-ms", "90000",
             "--live-script", s1, "--mem-dump", dumps("v1up")], OUT / "v1up.txt")

    def krefuse_run():
        kw = next((v for k, v in emu_card.extract_image((OUT / "base.img").read_bytes()).items()
                   if k.lower().endswith("/kits/kits.work")), b"")
        badk = bytearray(kw); badk[O_LIB + 3000] ^= 0x55; badk = bytes(badk)       # the CRC fails
        (OUT / "kbad_kits").mkdir(exist_ok=True)
        f = OUT / "kbad_kits/kits.work"; f.write_bytes(badk)
        c = stage(pathlib.Path(a.strand_project).expanduser(), "KBAD", extra=[f])

        def kbad(tag, choice):
            dmp = (f"{KS:#x},48={OUT / f'{tag}_st.bin'};{sym['store_npend']:#x},4={OUT / f'{tag}_np.bin'};"
                   f"{sym['store_pend']:#x},32={OUT / f'{tag}_pend.bin'};{sym['KBACKUP']:#x},8={OUT / f'{tag}_bk.bin'}")
            cmd = [EMU, "--image", image, "--card", c, "--set", "OCTABAM", "--project", "KBAD", "--load-ms", "90000",
                   "--live-script", s1, "--mem-dump", dmp]
            if choice is not None:
                cmd += ["--step", f"-:call:{sym['store_answer_cb']:#x},{choice},0"]
            run(cmd, OUT / f"{tag}.txt")
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(lambda t: kbad(*t), [("kbad_ignore", None), ("kbad_over", 1), ("kbad_back", 2)]))
        # The refusal explanation comes first; YES opens the recovery list.
        def ui(tag, *rows):
            sc = Script(); sc.tap("no", 400); sc.send("enc 1 1", 800)
            if tag != "kui_info" and tag != "kui_cancel":
                sc.tap("yes", 400)
            for r in rows:
                sc.send(r, 700)
            sp = OUT / f"{tag}.script"; sp.write_text(sc.text())
            dmp = (f"{KS:#x},48={OUT / f'{tag}_st.bin'};{sym['store_npend']:#x},4={OUT / f'{tag}_np.bin'};"
                   f"{sym['store_pend']:#x},32={OUT / f'{tag}_pend.bin'};{sym['KBACKUP']:#x},8={OUT / f'{tag}_bk.bin'};"
                   f"0x460e5e28,4={OUT / f'{tag}_cbs.bin'};0x460e5e30,4={OUT / f'{tag}_obj.bin'};"
                   f"{sym['store_mown']:#x},4={OUT / f'{tag}_mown.bin'};"
                   f"{sym['store_info_lines']:#x},4={OUT / f'{tag}_explain.bin'};"
                   f"0x460e5cd0,4={OUT / f'{tag}_dialog.bin'}")
            run([EMU, "--image", image, "--card", c, "--set", "OCTABAM", "--project", "KBAD", "--load-ms", "90000",
                 "--live-script", sp, "--mem-dump", dmp], OUT / f"{tag}.txt")
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(lambda t: ui(*t), [("kui_info",), ("kui_cancel", "key 0x32 down", "key 0x32 up", "enc 1 1"),
                                           ("kui_open",), ("kui_over", "enc 6 1", "key 0x31 down", "key 0x31 up"),
                                           ("kui_ignore", "key 0x31 down", "key 0x31 up")]))

    defer("reboot", ("saveproj",), lambda: boot("reboot", OUT / "saved.img"))
    defer("power", ("saveproj",), lambda: boot("power", OUT / "saved.img", OUT / "cs1_saved.bin"))
    defer("powerun", ("unsaved",), lambda: boot("powerun", OUT / "unsaved.img", OUT / "cs1_unsaved.bin"))
    defer("newboot", ("newsave",), newboot_run)
    if (not only or "v1up" in only) and "MIDI SCENES" in remix.modules:
        defer("v1up", ("base",), v1up_run)
    if (not only or "krefuse" in only) and "store_answer_cb" in sym:
        defer("krefuse", ("base",), krefuse_run)

    sd = pathlib.Path(a.strand_project).expanduser()
    if "strand" not in skipped and (not only or "strand" in only) and (sd / "project.work").is_file():
        c = stage(sd, "STRAND")
        sc = Script(); sc.tap("no"); sc.tap("play", 9000); sc.tap("stop", 400)
        sc.hold("func", "rec"); sc.hold("ptn", 1); sc.hold("func", "stop", gap=1000)   # copy, pattern 2, paste
        (OUT / "strand.script").write_text(sc.text())
        start([EMU, "--image", image, "--card", c, "--set", "OCTABAM", "--project", "STRAND", "--load-ms", "90000",
               "--dsp", "--live-script", OUT / "strand.script", "--mem-dump", dumps("strand")], OUT / "strand.txt")
    ok_dir = pathlib.Path(a.octakit_project).expanduser()
    v3 = [ok_dir / f"kits3{p}.work" for p in "ab"]
    if (not only or "import" in only) and all(f.is_file() for f in v3):
        c = stage(ok_dir, "IMPORT", extra=v3)
        start([EMU, "--image", image, "--card", c, "--set", "OCTABAM", "--project", "IMPORT", "--load-ms", "90000",
               "--live-script", s1, "--mem-dump", dumps("import"), "--card-out", OUT / "import.img"], OUT / "import.txt")
    if not only or "noproj" in only:
        start([EMU, "--image", image, "--card", card, "--set", "OCTABAM", "--project", "NOPROJ", "--load-ms", "90000",
               "--live-script", s1, "--mem-dump", dumps("noproj")], OUT / "noproj.txt")
    # The MKI pass is its own load: beside the MKII scenarios, not after them.
    if mki_scen:
        start([x for x in base if x != "--mkii"] + [x for sc in mki_scen for x in ("--scenario", sc)]
              + ["--scenario-jobs", str(fork_jobs())], OUT / "port_mki.txt")
    if scen:
        # the longest scenarios first (seconds of emulated time: unattended
        # 60 s, saveproj three boots), so the fork queue does not end on one
        scen.sort(key=lambda e: next((i for i, t in enumerate(LONGEST) if e.startswith(f"{OUT / t}.txt ")),
                                     len(LONGEST)))
        run(base + [x for sc in scen for x in ("--scenario", sc)] + ["--scenario-jobs", str(fork_jobs())], OUT / "port.txt")
    if mki_scen:
        finish(OUT / "port_mki.txt")

    # ---- reading a run back ---------------------------------------------------
    def st(tag):
        d = (OUT / f"{tag}_st.bin").read_bytes()
        return {n: struct.unpack(">I", d[4 * i:4 * i + 4])[0] for i, n in enumerate(STATE)}

    def img(tag):
        return (OUT / f"{tag}_img.bin").read_bytes()

    def b3_(tag):
        return (OUT / f"{tag}_b3.bin").read_bytes()

    def kit(im, k):
        return im[O_LIB + k * REC + 16:O_LIB + k * REC + REC1]

    def slot(b, s):
        return b[WORK + s * PARTSZ:WORK + (s + 1) * PARTSZ]

    def clean(tag, extra_ok=()):
        log = (OUT / f"{tag}.txt").read_text(errors="replace")
        halted = any(w in log for w in ("stopped before", "stopped in a wait", "FAULT", "ILLEGAL", "EXCEPTION", "DID NOT RETURN",
                                        "WAIT TIMEOUT"))
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
        ok = all(kit(im, BANK * 4 + p) == slot(b, p) for p in range(4))
        check("base: Kits 9-12 are bank 3's working Parts", ok)
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

    if exists("swback"):
        clean("swback")
        b, im = b3_("swback"), img("swback")
        sl = [b[p * PSTRIDE + PBYTE] for p in (2, 3)]
        asg = [im[O_ASSIGN + BANK * 16 + p] for p in (2, 3)]
        held = [slot(b, x) == kit(im, k) for x, k in zip(sl, (2, 3))]
        check(f"swback: after switching 3, 4, 3, 4 the patterns keep Kits {[a + 1 for a in asg]} (3, 4), "
              f"on slots {[x + 1 for x in sl]} holding them ({held})",
              asg == [2, 3] and all(held) and sl[0] != sl[1])
    if exists("editfull"):
        clean("editfull")
        b, im = b3_("editfull"), img("editfull")
        sl, ok, _ = plays("editfull", 1, 0)
        kept = [slot(b, x)[EDIT_OFF] == EDIT_VAL + x for x in (1, 2, 3) if x != sl]
        check(f"editfull: pattern 2's slot {sl + 1} holds Kit 1 ({ok}); the edits on the other slots kept ({kept})",
              ok and all(kept))
    if exists("editback"):
        clean("editback")
        b, im = b3_("editback"), img("editback")
        sl = b[3 * PSTRIDE + PBYTE]
        got, k = slot(b, sl), kit(im, BANK * 4 + 1)
        same = got[:EDIT_OFF] + got[EDIT_OFF + 1:] == k[:EDIT_OFF] + k[EDIT_OFF + 1:]
        unsaved = bool(b[0x95048] >> sl & 1)
        check(f"editback: pattern 4's slot {sl + 1} is Kit 10 with its edit ({same}, {got[EDIT_OFF]:#x}), "
              f"unsaved ({unsaved}); the library's Kit 10 unedited ({k[EDIT_OFF]:#x})",
              same and got[EDIT_OFF] == EDIT_VAL + 1 and unsaved and k[EDIT_OFF] != EDIT_VAL + 1)
        mf = OUT / "editback_msc.bin"
        if mf.is_file():
            tab = mf.read_bytes()
            kl = im[O_LIB + (BANK * 4 + 1) * REC + REC1:O_LIB + (BANK * 4 + 2) * REC]
            rest = [x for x in (1, 2, 3) if x not in (sl, 1)]   # slot 2 holds pattern 2's Kit 1 since editfull
            kept = [tab[x * 4096 + LOCK_IDX] == EDIT_VAL + x for x in rest]
            check(f"editback: slot {sl + 1}'s lock table is the one slot 2 had ({tab[sl * 4096 + LOCK_IDX]:#x}, "
                  f"{EDIT_VAL + 1:#x} was set), slot 2 is Kit 1's (no lock, {tab[4096 + LOCK_IDX]:#x}), "
                  f"slots {[x + 1 for x in rest]} kept theirs ({kept}), the library's Kit 10 has no lock ({kl[LOCK_IDX]:#x})",
                  tab[sl * 4096 + LOCK_IDX] == EDIT_VAL + 1 and tab[4096 + LOCK_IDX] == 0xff and all(kept)
                  and kl[LOCK_IDX] == 0xff)
    if exists("freload"):
        clean("freload")
        b, im = b3_("freload"), img("freload")
        sl = b[PBYTE]
        check(f"freload: FUNC+CUE with an edit on the playing slot {sl + 1} whose unsaved bit is clear: the slot is "
              f"Kit {BANK * 4 + sl + 1} again ({slot(b, sl) == kit(im, BANK * 4 + sl)})",
              slot(b, sl) == kit(im, BANK * 4 + sl))
    if exists("statusnew"):
        clean("statusnew")      # the plane (statusnew_lcd.bin) reads "001 ---" where stock draws "Pt:1 ONE": read by eye, 13 Oct 2026
    if exists("noasg"):
        clean("noasg")
        b, im = b3_("noasg"), img("noasg")
        sl, ok, _ = plays("noasg", 2, BANK * 4 + 1)
        a3 = im[O_ASSIGN + BANK * 16 + 2]
        check(f"noasg: pattern 3 (no Kit) still plays what slot 2 held, Kit {BANK * 4 + 2} (slot {sl + 1}: {ok}, "
              f"ASSIGN {a3 + 1 if a3 != 0xff else '-'})", ok)
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

    if exists("lfyes"):
        clean("lfyes")
        im = img("lfyes"); b0 = img("base") if exists("base") else None
        arm = (OUT / "lfyes_arm.bin").read_bytes() + (OUT / "lfyes_arm2.bin").read_bytes()
        mobj = struct.unpack(">9I", (OUT / "lfyes_menu.bin").read_bytes())[2]
        check(f"lfyes: FUNC+YES in LOAD KIT arms nothing (arm words {arm.hex()})", arm.count(0xff) == 0)
        check(f"lfyes: ... saves nothing (the library as at the load) and the list stays open ({mobj:#x})",
              (b0 is None or im[O_LIB:] == b0[O_LIB:]) and im[O_ASSIGN:O_ASSIGN + 256] == (b0 or im)[O_ASSIGN:O_ASSIGN + 256]
              and mobj != 0)
    for tag in ("lname", "sname"):
        if exists(tag):
            clean(tag)
            pl = (OUT / f"{tag}_lcd.bin").read_bytes()
            print(f"  [ -- ] {tag}: the plane dumped to {OUT / (tag + '_lcd.bin')} ({sum(map(bool, pl))} non-zero bytes)")

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
    if exists("lcopylive"):
        clean("lcopylive")
        im, b = img("lcopylive"), b3_("lcopylive")
        s_ = cur_slot(b)
        k = BANK * 4 + s_
        check(f"lcopylive: Kit {k} (above Kit {k + 1}) is the playing slot's Part with its edit "
              f"({kit(im, k - 1) == slot(b, s_)}, byte {kit(im, k - 1)[EDIT_OFF]:#x}); Kit {k + 1} has not got it "
              f"({kit(im, k)[EDIT_OFF]:#x})",
              kit(im, k - 1) == slot(b, s_) and kit(im, k - 1)[EDIT_OFF] == EDIT_VAL and kit(im, k)[EDIT_OFF] != EDIT_VAL)
    if exists("lclearlive") and exists("base"):
        clean("lclearlive")
        im, b, b0 = img("lclearlive"), b3_("lclearlive"), b3_("base")
        s_ = cur_slot(b)
        k = BANK * 4 + s_
        check(f"lclearlive: LOAD KIT's cursor on the current Kit {k + 1}, FUNC+PLAY: the Kit is empty "
              f"({not valid(im, k)}), the playing slot {s_ + 1} is a cleared Part (no Kit in RESID: "
              f"{im[O_RESID + BANK * 4 + s_] == 0xff}, Part changed: {slot(b, s_) != slot(b0, s_)}), pattern 1 keeps "
              f"its assignment ({im[O_ASSIGN + BANK * 16] + 1})",
              not valid(im, k) and im[O_RESID + BANK * 4 + s_] == 0xff and slot(b, s_) != slot(b0, s_)
              and im[O_ASSIGN + BANK * 16] == k)
    if exists("follow"):
        clean("follow")
        msel = struct.unpack(">I", (OUT / "follow_msel.bin").read_bytes())[0]
        check(f"follow: LOAD KIT open, PTN+TRIG 2 (Kit 4): the cursor is on Kit 4's row ({msel}, row 0 is UNDO KIT)",
              msel == 4)
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
        win = struct.unpack(">I", (OUT / "fright_ptnwin.bin").read_bytes())[0]
        check(f"fright: PTN released after PTN+FUNC+RIGHT: SELECT PATTERN not opened (0x460d1742 = {win}, 2 when it is)",
              win != 2)

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
    if exists("saveproj"):
        clean("saveproj")
        want = img("saveproj")
        files = emu_card.extract_image((OUT / "saved.img").read_bytes())
        for ext in ("work", "strd"):
            d = next((v for k, v in files.items() if k.lower().endswith(f"/kits/kits.{ext}")), b"")
            check(f"saveproj: kits.{ext} holds the loaded Kit's assignment",
                  len(d) == IMG_LEN and d[O_ASSIGN + BANK * 16] == want[O_ASSIGN + BANK * 16])
        for n in ("reboot", "power", "powerun"):
            joined(n)
        for tag, ref in (("reboot", "saveproj"), ("power", "saveproj"), ("powerun", "unsaved")):
            if not exists(tag):
                continue
            clean(tag)
            im, w = img(tag), img(ref)
            check(f"{tag}: ASSIGN and RESID as before ({im[O_ASSIGN + BANK * 16]}, "
                  f"{im[O_RESID + BANK * 4:O_RESID + BANK * 4 + 4].hex()})",
                  im[O_ASSIGN:O_RESID + 64] == w[O_ASSIGN:O_RESID + 64] or
                  (im[O_ASSIGN:O_VALID] == w[O_ASSIGN:O_VALID] and im[O_RESID:O_RESID + 64] == w[O_RESID:O_RESID + 64]))

    # ---- the panel-made project: Kits on patterns 2 and 3; saved, cold boot --------
    def b1_(tag):
        return (OUT / f"{tag}_b1.bin").read_bytes()

    def follows(tag, ptns, kits):
        """-> the patterns' slots, whether each holds its Kit, the engine's (bank, part)"""
        b, im = b1_(tag), img(tag)
        sl = [b[p * PSTRIDE + PBYTE] for p in ptns]
        return sl, [slot(b, x) == kit(im, k) for x, k in zip(sl, kits)], (OUT / f"{tag}_eng.bin").read_bytes()

    if exists("newproj"):
        clean("newproj")
        im = img("newproj")
        asg = [im[O_ASSIGN + p] for p in (1, 2)]
        sl, held, eng = follows("newproj", (1, 2), asg)
        check(f"newproj: NEW PROJECT on the panel, SAVE KIT on patterns 2 and 3: Kits {[k + 1 for k in asg]} (3, 6), "
              f"their Parts differ ({kit(im, 2) != kit(im, 5)}); playing, PTN 2 then PTN 3: on slots "
              f"{[x + 1 for x in sl]} holding them ({held}), the engine on pattern 3's (engine {eng[0] + 1}:{eng[1] + 1})",
              asg == [2, 5] and kit(im, 2) != kit(im, 5) and all(held) and sl[0] != sl[1]
              and eng[0] == 0 and eng[1] == sl[1])
    if exists("newsave"):
        clean("newsave")
        files = emu_card.extract_image((OUT / "newsave.img").read_bytes())
        name = next(k.split("/")[1] for k in files if k.startswith("OCTABAM/") and k.count("/") == 2
                    and k.split("/")[1] != "KITS")
        size = (pdir / "bank01.work").stat().st_size
        banks = {k.rsplit("/", 1)[1]: v for k, v in files.items() if k.startswith(f"OCTABAM/{name}/bank")}
        bad = [k for k, v in banks.items()
               if len(v) != size or v[:4] != b"FORM" or int.from_bytes(v[-2:], "big") != sum(v[0x10:-2]) & 0xffff]
        check(f"newsave: SAVE PROJECT of '{name}' wrote {len(banks)} bank files, each {size} B, FORM, its checksum "
              f"holding ({bad})", len(banks) == 32 and not bad)
        joined("newboot")
        clean("newboot")
        log = next((v for k, v in emu_card.extract_image((OUT / "newboot.img").read_bytes()).items()
                    if k.upper().startswith("LOG")), b"").decode("latin1")
        rej = [l for l in log.splitlines() if "bank file" in l or "PARSE ERROR" in l or "WRONG CHECKSUM" in l]
        check(f"newboot: a cold boot of that card loads '{name}', no bank file refused ({rej[:2]})", log and not rej)
        im, w = img("newboot"), img("newsave")
        sl, held, eng = follows("newboot", (1,), (2,))
        check(f"newboot: the assignments and Kits 3 and 6 as saved; playing, PTN 2: slot {sl[0] + 1} holds Kit 3 "
              f"({held[0]}), the engine on it (engine {eng[0] + 1}:{eng[1] + 1})",
              im[O_ASSIGN:O_VALID] == w[O_ASSIGN:O_VALID] and kit(im, 2) == kit(w, 2) and kit(im, 5) == kit(w, 5)
              and held[0] and eng[0] == 0 and eng[1] == sl[0])

    # ---- the blank boot (no CS1: an EMPTY RESET's next power-up) -------------
    # The boot's own migration then fills the library (every bank's Parts as
    # Kits), as it does on a stock NEW PROJECT; what the hook adds is READY
    # from the first screen and the CS1 copy, asserted here.
    if not only or "blank" in only:
        joined("blank")
        if exists("blank"):
            clean("blank")
            cs1 = (OUT / "blank_cs1.bin").read_bytes()
            check("blank: CS1 holds the KCS1 header (the empty library, saved at the boot)",
                  cs1[:4] == b"KCS1")
            cur = (OUT / "blank_cur.bin").read_bytes()
            check(f"blank: the boot took the stock blank path (project {cur.hex()})",
                  cur == b"\x40\x0e\x21\xe0")

    # ---- Em's v3 files ----------------------------------------------------------
    if (not only or "import" in only) and all(f.is_file() for f in v3):
        finish(OUT / "import.txt")
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

    # ---- a version 1 kits.work under MIDI SCENES: read, expanded, empty tables --
    if (not only or "v1up" in only) and "MIDI SCENES" in remix.modules and exists("base"):
        joined("v1up")
        v1 = (OUT / "v1up_kits/kits.work").read_bytes()
        clean("v1up")
        im, b0 = img("v1up"), img("base")
        same = all(im[O_LIB + k * REC:O_LIB + k * REC + REC1] == b0[O_LIB + k * REC:O_LIB + k * REC + REC1] for k in range(256))
        blank = all(im[O_LIB + k * REC + REC1:O_LIB + (k + 1) * REC] == b"\xff" * 4096 for k in range(256))
        check(f"v1up: the version 1 file read ({len(v1)} B): every Kit as in the version 2 file ({same}), "
              f"every table empty ({blank})", same and blank)

    # ---- a refused kits.work: listed by STORE, kept; OVERWRITE and BACKUP --------
    if (not only or "krefuse" in only) and exists("base") and "store_answer_cb" in sym:
        joined("krefuse")
        w = lambda tag, n: struct.unpack(">I", (OUT / f"{tag}_{n}.bin").read_bytes())[0]
        check("kui_info: explains the refused file before the recovery choices, still protected",
              w("kui_info", "dialog") != 0 and w("kui_info", "mown") == 0 and w("kui_info", "np") == 1
              and w("kui_info", "explain") == sym["store_info_kits"]
              and st("kui_info")["NOWRITE"] == 1)
        check("kui_cancel: NO leaves the file protected and another encoder turn does not reopen the prompt",
              w("kui_cancel", "dialog") == 0 and w("kui_cancel", "mown") == 0 and w("kui_cancel", "np") == 1
              and st("kui_cancel")["NOWRITE"] == 1)
        check(f"kui_open: the encoder turn opened STORE's list (M_OBJ {w('kui_open', 'obj'):#x}, callbacks {w('kui_open', 'cbs'):#x} "
              f"= store_cbtab {sym['store_cbtab']:#x}, open flag {w('kui_open', 'mown')}); the file is still listed ({w('kui_open', 'np')})",
              w("kui_open", "obj") != 0 and w("kui_open", "cbs") == sym["store_cbtab"] and w("kui_open", "mown") == 1
              and w("kui_open", "np") == 1)
        so = st("kui_over")
        check(f"kui_over: LEVEL down, YES: OVERWRITE answered (listed {w('kui_over', 'np')}, NOWRITE {so['NOWRITE']}, "
              f"READY {so['READY']}, KDIRTY {so['KDIRTY']}, list closed {w('kui_over', 'obj') == 0})",
              w("kui_over", "np") == 0 and not so["NOWRITE"] and so["READY"] == 1 and so["KDIRTY"] == 1
              and w("kui_over", "obj") == 0)
        si = st("kui_ignore")
        check(f"kui_ignore: YES on the first row: IGNORE answered (listed {w('kui_ignore', 'np')}, NOWRITE {si['NOWRITE']}, "
              f"READY {si['READY']}, list closed {w('kui_ignore', 'obj') == 0})",
              w("kui_ignore", "np") == 0 and si["NOWRITE"] == 1 and not si["READY"] and w("kui_ignore", "obj") == 0)
        for tag in ("kbad_ignore", "kbad_over", "kbad_back"):
            s_ = st(tag)
            np_ = struct.unpack(">I", (OUT / f"{tag}_np.bin").read_bytes())[0]
            pend = (OUT / f"{tag}_pend.bin").read_bytes()
            bk = struct.unpack(">II", (OUT / f"{tag}_bk.bin").read_bytes())      # KBACKUP, KDEFER
            if tag == "kbad_ignore":
                check(f"{tag}: listed ({np_} entry {tuple(pend[:2])}), refused (BADFILE {s_['BADFILE']}), "
                      f"NOWRITE {s_['NOWRITE']}, READY {s_['READY']}",
                      np_ == 1 and tuple(pend[:2]) == (1, 0) and s_["BADFILE"] == 1 and s_["NOWRITE"] == 1 and not s_["READY"])
            else:
                check(f"{tag}: answered (listed {np_}), NOWRITE {s_['NOWRITE']}, READY {s_['READY']}, KDIRTY {s_['KDIRTY']}, "
                      f"backup flag {bk[0]}, write deferred {bk[1]}",
                      np_ == 0 and not s_["NOWRITE"] and s_["READY"] == 1 and s_["KDIRTY"] == 1
                      and bk == (1 if tag == "kbad_back" else 0, 0))

    # ---- a rejected bank file, a missing project --------------------------------
    if "strand" in skipped:
        pass
    elif (not only or "strand" in only) and (sd / "project.work").is_file():
        finish(OUT / "strand.txt")
        clean("strand")
    elif not only or "strand" in only:
        print("  [SKIP] strand: no project at --strand-project")
    if not only or "noproj" in only:
        finish(OUT / "noproj.txt")
        s = st("noproj")
        log = (OUT / "noproj.txt").read_text(errors="replace")
        check(f"noproj: the load ran, no halt (READY {s['READY']}, IOERR {s['IOERR']})",
              not any(w in log for w in ("stopped before", "FAULT", "ILLEGAL")))

    if skipped:
        print(f"  [ -- ] FULL only (skipped by --quick): {', '.join(skipped)}")
    print(f"verify_kits: {'FAIL' if fails else 'ok'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
