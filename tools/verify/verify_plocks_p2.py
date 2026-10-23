#!/usr/bin/env python3
"""PLOCKS P2 under the port: page-2 parameter locks recorded from the panel,
moved by stock's trig and pattern operations, played on trigs, saved to the
card and loaded back.

    python3 tools/verify/verify_plocks_p2.py REMIX --project DIR

Stages the project's card and boots the remix's image in `ot_emu`. A probe
load reads the bank the panel edits, its track and part; the track's FX2
becomes an effect whose page-2 slot 0 takes values (the project's own when
it has one, else the first stock reverb in the image). Then one load,
forked (`ot_emu --scenario`):

  record   FX2 SETUP open, grid recording, trig 1 placed, trig 1 held and
           knob A turned: step 1's page-2 lock (STORE) takes a value other
           than the Part's, and stock's page-1 locks of step 1 stay 0xff.
           Then trig 1 copied (held + REC) and pasted onto trig 5 (held +
           STOP): step 5 carries the same lock.
  tap_clear after the edit and release, a new bare trig tap still clears
           the step's page-2 locks.
  clear    ... and trig 5's locks cleared (held + PLAY): step 5 none, step 1
           kept.
  pattern  ... grid off, the pattern copied (FUNC+REC), pattern 2 selected,
           pasted (FUNC+STOP): pattern 2's step 1 carries the lock.
  pclear   ... pattern 2 cleared (FUNC+PLAY): no lock.
  undo     ... and the clear undone (FUNC+PLAY again): the lock is back.
  play     plk_init called after the load, T1 step 1 FX2 page-2 slot 0
           locked to 99 in every bank and pattern, trigs on steps 1 and 2 of
           the playing pattern, the transport on: at frame 50 T1's live lane
           reads 99, at frame 1500 (after step 2) the Part's value again,
           and no other track's page-2 lane byte moved.
  save     record, then the unit's SAVE PROJECT (FUNC+MIXER, RIGHT, DOWN,
           YES, YES): the card holds p2lkNN.work and p2lkNN.strd for the
           edited bank with the lock; a second boot of that card has it in
           STORE after the load.
  power    the same card and that run's CS1 (`--cs1-in`), booted with the
           firmware's own power-up load (`--no-post`: the current bank from
           CS1, the rest from the card): the lock is in STORE. Likewise a
           lock recorded and never saved (the CS1 copy), and the saved one
           with the CS1 copy's magic cleared (read from p2lkNN.work).

SKIPs without a project, without the port, or for a remix without PLOCKS
P2. The display walk decodes the panel UART and compares held-lock dials
with actual stock page-one held locks and unheld references on FX1 and FX2.
It cannot measure physical panel timing or a slide trig (page 2 does not slide).
"""
import argparse, os, pathlib, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/plocksp2verify"
BASE = 0x40000400
BLOB, BANK_STRIDE, PART_STRIDE, PTN_STRIDE, TRK_STRIDE = 0x400e21e0, 0x9b340, 0x18b2, 0x8ed8, 0x91a
DBPTR, UI_TRACK, UI_PART = 0x46c82456, 0x100b14cc, 0x100b14cf
ID2_OFF, P2_OFF, DESC2, LIVE_IDS = 0x8ed88, 0x8f07e, 0x400d5fdc, 0x80000ec4
LANES = 0x80000810
CS1, CS1_LEN, NV = 0x10000000, 0x100000, 0x100f8600
REC, TRACK_B = 12, 64 * 12
K = dict(no=0x32, fx2=0x26, rec=0x29, play=0x28, stop=0x27, func=0x2d, pattern=0x2e,
         mixer=0x30, right=0x21, down=0x20, yes=0x31, t1=0x00, t2=0x01, t5=0x04)
REVERBS = (0x14, 0x15, 0x16)            # PLATE, SPRING, DARK


def run(cmd, log):
    with open(log, "w") as f:
        f.write(" ".join(map(str, cmd)) + "\n"); f.flush()
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_plocks_p2: ot_emu exit {r.returncode} -- {log}")
    return log.read_text()


class Script:
    """A --live-script at emulated milliseconds."""

    def __init__(self):
        self.t, self.lines = 1500.0, []

    def send(self, x, gap=60):
        self.lines.append(f"{self.t:.0f} {x}"); self.t += gap

    def tap(self, k, gap=250):
        self.send(f"key {K[k]:#x} down", 40); self.send(f"key {K[k]:#x} up", gap)

    def hold(self, k, *inner, gap=300):
        self.send(f"key {K[k]:#x} down", 40)
        for x in inner:
            self.tap(x, 150)
        self.send(f"key {K[k]:#x} up", gap)

    def turn(self, k, enc, ticks):
        self.send(f"key {K[k]:#x} down", 40); self.send(f"enc {enc} {ticks}", 150)
        self.send(f"key {K[k]:#x} up", 300)

    def text(self):
        return "\n".join(self.lines + [f"{self.t:.0f} quit"]) + "\n"


def record(s):
    s.tap("no", 400)                               # the boot's date prompt
    s.tap("fx2"); s.tap("fx2", 60); s.tap("fx2", 400)   # FX2, then its SETUP
    s.tap("rec"); s.tap("t1")                      # grid recording, trig 1
    s.turn("t1", 0, 3)                             # held trig 1 + knob A: page-2 slot 0
    s.tap("no", 400)                               # close SETUP


def hold_display_timing(p, box, target):
    """Observe native key-down to decoded lock pixels, at 10 ms resolution.

    Run through the hold event even if the image displays the lock early.
    No injected events, forced redraws, sleeps or writes to firmware state.
    """
    x0, y0, x1, y1 = box
    def cell():
        return tuple(v for row in p.screen()[y0:y1] for v in row[x0:x1])
    before = cell()
    first_change = first_lock = None
    p.key("trig1", True)
    for ms in range(10, 401, 10):
        p.run(10)
        pixels = cell()
        if first_change is None and pixels != before:
            first_change = ms
        if first_lock is None and pixels == target:
            first_lock = ms
    return first_change, first_lock


def stock_lock_references(card, set_name, project, out, check):
    """Capture real page-one locks on unmodified stock, using panel inputs.

    COMPRESSOR ATK uses the same numeric dial renderer as the page-two
    fixture. Only the cell position differs: page one starts seven rows
    above SETUP. No injected flags, forced redraws or RAM-written locks.
    """
    from stems_panel import MenuPort

    out.mkdir(parents=True, exist_ok=True)
    run_card = out / "card.img"
    shutil.copy2(card, run_card)
    refs = {}
    with MenuPort(ROOT / "out/raw/section_3_MAIN_OS.bin", run_card,
                  set_name, project, True, log_path=out / "port.log",
                  extra=("--load-ms", "90000")) as p:
        p.settle()
        p.press("t1")
        p.press("pg_fx1")
        def turn(ticks):
            p.proc.command(f"knob 48 {ticks}", "ok")
            p.run(350)
        def screen(name):
            p.png(out / (name + ".png"))
            return tuple(v for row in p.screen()[10:28] for v in row[61:79])
        turn(-127)
        turn(20)
        p.press("rec")
        p.press("trig1")
        p.key("trig1", True)
        p.run(350)
        current = 20
        for value in (50, 51, 52, 53):
            turn(value - current)
            current = value
            refs[value] = screen(f"stock-held-{value}")
            check(f"stock reference: page-one ATK lock stores {value}",
                  p.peek(p.long(DBPTR) + 0x59 + 18, 1) == bytes([value]))
        turn(50 - current)
        p.run(2500)
        check("stock reference: held number remains after the normal timeout",
              screen("stock-held-settled") == refs[50])
        p.key("trig1", False)
        p.run(2500)
        timing = hold_display_timing(p, (61, 10, 79, 28), refs[50])
        check("stock reference: lock display waits for the native hold event",
              all(t is not None and 200 <= t <= 350 for t in timing))
        print(f"  stock held-lock display: change/complete={timing} ms")
        check("stock reference: rehold shows saved number without a turn",
              screen("stock-reheld") == refs[50])
        p.run(2500)
        check("stock reference: reheld number remains after the normal timeout",
              screen("stock-reheld-settled") == refs[50])
        check("stock reference: different lock values produce different pixels",
              len(set(refs.values())) == len(refs))
    return refs, timing


def display_walk(image, card, set_name, project, store, out, check):
    """Compare native panel pixels with stock held-lock and unheld references.

    The disposable card has COMPRESSOR in FX1 and a stock reverb (or
    COMPRESSOR when the reverb id is replaced by an insert) in FX2,
    with slot A's normal value zero. No live RAM writes or draw calls.
    """
    from stems_panel import MenuPort
    from panel_server import setup_window_open

    out.mkdir(parents=True, exist_ok=True)
    stock, stock_timing = stock_lock_references(card, set_name, project, out / "stock", check)
    run_card = out / "card.img"
    shutil.copy2(card, run_card)
    with MenuPort(image, run_card, set_name, project, True,
                  log_path=out / "port.log", extra=("--load-ms", "90000")) as p:
        p.settle()
        p.press("t1")
        db = p.long(DBPTR)
        bank = (db - BLOB) // BANK_STRIDE
        part = p.peek(UI_PART, 1)[0]
        pattern = p.peek(0x100b14d0, 1)[0]
        block = store + ((bank * 16 + pattern) * 8) * TRACK_B
        part_addr = db + part * PART_STRIDE + P2_OFF

        def turn(ticks):
            p.proc.command(f"knob 48 {ticks}", "ok")
            p.run(350)

        def held(name, down):
            p.key(name, down)
            p.run(350)

        def screen(name):
            (out / (name + ".png")).write_bytes(p.link.render_png(4, dark=0, light=255))
            return p.screen()

        def crop(rows, box):
            x0, y0, x1, y1 = box
            return tuple(v for row in rows[y0:y1] for v in row[x0:x1])

        # SETUP draws names after widgets; the native name's bottom padding
        # clears row 16 (x=62..76). Check that padding with the name, and
        # compare the visible dial/number rows 17..34 with stock rows 10..27.
        dial = (61, 17, 79, 35)
        label = (62, 11, 77, 17)
        # Both popup descriptors place slot A at the same LCD coordinates.
        for slot, offset in (("fx2", 6), ("fx1", 0)):
            p.press("pg_" + slot, hold=180, settle=180)
            # A double press opens the native SETUP window.
            descriptor = 0x400bc48c if slot == "fx2" else 0x400bc262
            if not setup_window_open(p.rt.uc):
                p.press("pg_" + slot, hold=30, settle=30)
                p.press("pg_" + slot, hold=180, settle=180)
            check(f"display {slot}: expected SETUP window is active",
                  p.long(0x460d175c) == p.long(0x400bc48c if slot == "fx2" else 0x400bc262)
                  and setup_window_open(p.rt.uc))
            refs = {}
            aged = {}
            current = 0
            for value in (20, 21, 50, 51, 52, 53):
                turn(value - current)
                current = value
                refs[value] = screen(f"{slot}-reference-{value}")
                check(f"display {slot}: native reference value {value} is drawn",
                      p.peek(part_addr + offset, 1)[0] == value
                      and sum(crop(refs[value], (63, 29, 77, 34))) > 8)
                if value == 20:
                    p.run(2000)
                    aged[value] = screen(f"{slot}-reference-{value}-settled")
            turn(20 - current)
            if slot == "fx2":
                p.press("rec")
                p.press("trig1")
            held("trig1", True)
            empty = screen(f"{slot}-held-unlocked")
            check(f"display {slot}: held step without a lock shows the normal label and value",
                  crop(empty, label) == crop(refs[20], label)
                  and crop(empty, dial) == crop(refs[20], dial))
            turn(30)
            locked = screen(f"{slot}-locked-50")
            check(f"display {slot}: held dial and number match stock page-one lock 50",
                  crop(locked, dial) == stock[50])
            check(f"display {slot}: parameter names stay unchanged while a lock is held",
                  crop(locked, label) == crop(refs[50], label)
                  and crop(locked, (81, 10, 98, 16)) == crop(refs[50], (81, 10, 98, 16)))
            p.run(2500)
            check(f"display {slot}: held value stays visible after the normal timeout",
                  crop(screen(f"{slot}-held-settled"), dial) == stock[50])
            held("trig1", False)
            released = screen(f"{slot}-released-20")
            check(f"display {slot}: release restores normal label and Part value 20",
                  crop(released, (61, 10, 79, 35)) == crop(aged[20], (61, 10, 79, 35)))
            check(f"display {slot}: release preserves lock 50 and Part 20",
                  p.peek(block + offset, 1) == bytes([50])
                  and p.peek(part_addr + offset, 1) == bytes([20]))
            p.run(2000)
            settled = screen(f"{slot}-released-20-settled")
            check(f"display {slot}: released dial follows the native value timeout",
                  crop(settled, (61, 10, 79, 35)) == crop(aged[20], (61, 10, 79, 35)))
            turn(1)
            after = screen(f"{slot}-normal-turn-21")
            check(f"display {slot}: first unheld tick moves Part 20 to 21",
                  p.peek(part_addr + offset, 1) == bytes([21])
                  and crop(after, dial) == crop(refs[21], dial))
            p.run(2000)
            timing = hold_display_timing(p, dial, stock[50])
            # The input scan and decoded LCD frame can land on adjacent
            # samples. Compare both first change and complete cell to stock.
            check(f"display {slot}: held-lock timing follows stock page one",
                  all(t is not None and s is not None and abs(t - s) <= 30
                      for t, s in zip(timing, stock_timing)))
            print(f"  {slot} held-lock display: change/complete={timing} ms")
            reheld = screen(f"{slot}-reheld-50")
            check(f"display {slot}: native hold event displays the saved lock",
                  crop(reheld, (61, 10, 79, 35)) == crop(locked, (61, 10, 79, 35)))
            p.run(2500)
            check(f"display {slot}: reheld number stays visible without turning",
                  crop(screen(f"{slot}-reheld-settled"), dial) == stock[50])
            for value in (51, 52, 53):
                turn(1)
                changed = screen(f"{slot}-slow-{value}")
                check(f"display {slot}: slow held tick shows {value} and keeps Part 21",
                      crop(changed, dial) == stock[value]
                      and p.peek(block + offset, 1) == bytes([value])
                      and p.peek(part_addr + offset, 1) == bytes([21]))
            held("trig2", True)
            check(f"display {slot}: two held trigs keep the first step's lock visible",
                  crop(screen(f"{slot}-two-held"), dial) == stock[53])
            held("trig2", False)
            check(f"display {slot}: releasing the second trig keeps the first lock visible",
                  crop(screen(f"{slot}-second-released"), dial) == stock[53])
            held("trig1", False)
            p.run(2000)
            normal = crop(p.screen(), dial)
            p.press("trig2", hold=40, settle=400)
            check(f"display {slot}: short tap leaves no delayed lock display",
                  crop(screen(f"{slot}-short-tap"), dial) == normal)
            p.key("trig1", True)
            p.run(50)
            p.proc.command("knob 48 -1", "ok")
            p.run(50)
            check(f"display {slot}: encoder edit before hold event displays lock 52 promptly",
                  crop(screen(f"{slot}-early-edit"), dial) == stock[52]
                  and p.peek(block + offset, 1) == bytes([52]))
            p.key("trig1", False)
            p.run(50)
            released_early = screen(f"{slot}-early-release")
            p.run(400)
            check(f"display {slot}: early release restores Part without a late lock redraw",
                  crop(released_early, dial) == crop(p.screen(), dial) == crop(refs[21], dial)
                  and p.peek(part_addr + offset, 1) == bytes([21])
                  and p.peek(block + offset, 1) == bytes([52]))
            # A quick encoder turn also starts stock's normal numeric-value
            # timeout. Release shows Part 21 before that number disappears.
            p.run(2500)
            check(f"display {slot}: early-release Part number follows its normal timeout",
                  crop(screen(f"{slot}-early-release-settled"), dial) == normal)
            held("trig1", True)
            held("func", True)
            turn(1)
            removed = screen(f"{slot}-removed")
            check(f"display {slot}: FUNC turn removes lock, highlight and lock value",
                  p.peek(block + offset, 1) == b"\xff"
                  and crop(removed, (61, 10, 79, 35)) == crop(refs[21], (61, 10, 79, 35)))
            held("func", False)
            held("trig1", False)
            check(f"display {slot}: page-one lock bytes remain untouched",
                  p.peek(db + 0x59, 32) == b"\xff" * 32)
            p.press("no")

        # The FX popup object is reused by other native windows. Trig redraws
        # must not paint FX controls over MIXER, TEMPO or MIDI setup pages.
        for modal in ("mixer", "tempo"):
            p.press(modal, settle=300)
            before = screen(modal + "-before")
            held("trig1", True)
            during = screen(modal + "-held")
            held("trig1", False)
            after = screen(modal + "-released")
            check(f"display {modal}: trig press/release preserves the native window",
                  crop(before, (8, 0, 120, 44)) == crop(during, (8, 0, 120, 44))
                  == crop(after, (8, 0, 120, 44)))
            p.press("no")
        p.press("midi")
        p.press("pg_fx1", hold=180, settle=180)
        if not setup_window_open(p.rt.uc):
            p.press("pg_fx1", hold=30, settle=30)
            p.press("pg_fx1", hold=180, settle=180)
        before = screen("midi-setup-before")
        held("trig1", True)
        during = screen("midi-setup-held")
        held("trig1", False)
        after = screen("midi-setup-released")
        check("display MIDI: trig press/release preserves the native SETUP title",
              p.long(0x80000012) != 0 and setup_window_open(p.rt.uc)
              and crop(before, (40, 0, 110, 8)) == crop(during, (40, 0, 110, 8))
              == crop(after, (40, 0, 110, 8)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="OCTABAM")
    ap.add_argument("--name", default="PLOCKSP2")
    ap.add_argument("--out", default="")
    ap.add_argument("--display-only", action="store_true", help="run the panel-pixel regression only")
    a = ap.parse_args()
    global OUT
    if a.out:
        OUT = pathlib.Path(a.out)
    remix = registry.remix(a.remix)
    if "PLOCKS P2" not in remix.modules:
        print(f"  [ -- ] verify_plocks_p2: {a.remix} carries no PLOCKS P2"); return 0
    if not a.project:
        print("  [SKIP] verify_plocks_p2: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_plocks_p2: no port binary (make emu-cf)"); return 0
    pdir = pathlib.Path(a.project).expanduser()
    if not (pdir / "project.work").is_file():
        sys.exit(f"verify_plocks_p2: {pdir} is not a project")
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- the image and its runtime's symbols --------------------------------
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_plocks_p2: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                        capture_output=True, text=True).stdout
    sym = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    STORE, INIT = sym["STORE"], sym["plk_init"]
    img = image.read_bytes()

    def rd32(addr):
        o = addr - BASE
        return int.from_bytes(img[o:o + 4], "big") if 0 <= o < len(img) - 4 else 0

    def page2_ok(fx_id):
        if fx_id == 0:
            return False
        p = rd32(DESC2 + 4 * fx_id)
        return p and rd32(p + 0x9a + 4 * 6) >= 2

    # ---- the card -------------------------------------------------------------
    copy = OUT / "project"
    if copy.exists():
        shutil.rmtree(copy)
    copy.mkdir(parents=True)
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)
    # Install the fallback in the copied bank files, including saved Parts.
    # Poking only RAM/live IDs after load leaves the UI's SRAM Part as NONE;
    # it then records no lock even though the descriptor probe looks valid.
    sys.path.insert(0, str(ROOT / "tools/hw"))
    import ot_project
    fallback = next((i for i in REVERBS if page2_ok(i)), None)
    if fallback is None:
        sys.exit("verify_plocks_p2: no FX2 page-2 slot 0 available for the fixture")
    for bankfile in sorted(copy.glob("bank*.work")):
        def usable_fx(data):
            # Panel recording creates its own trigs and locks. Clear the copied
            # first pattern, including inherited locks: clearing only trig 1
            # leaves a stress project's ATK lock as the encoder's starting value
            # and breaks even the unmodified-stock reference walk.
            for track in range(8):
                at = ot_project.trac_off(0, track)
                data[at:at + 64] = bytes(64)
                data[at + 0x59:at + 0x59 + 64 * 32] = b'\xff' * (64 * 32)
            for part_index in range(ot_project.NPARTS_ALL):
                part_start = ot_project.PART_BASE + part_index * ot_project.PART_STRIDE
                for track in range(8):
                    at = part_start + ot_project.FX2_OFF + track
                    if not page2_ok(data[at]):
                        data[at] = fallback
                    # record() turns +3. A copied value at/above this image's
                    # limit clamps to the same value (e.g. a reverb id reused
                    # for a three-choice selector in Inserts), falsely making
                    # a correctly recorded lock look like an unedited Part.
                    count = rd32(rd32(DESC2 + 4 * data[at]) + 0x9a + 4 * 6)
                    knob_at = part_start + ot_project.P2_OFF + track * ot_project.P2_STRIDE + 6
                    if data[knob_at] >= count - 1:
                        data[knob_at] = 0
        ot_project._bank_write(copy, int(bankfile.stem[4:]), usable_fx, guard=False)

    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_plocks_p2: stage_card failed:\n{r.stdout[-1000:]}{r.stderr[-1000:]}")
    base = [EMU, "--image", image, "--card", card, "--set", a.set_name, "--project", a.name, "--load-ms", "90000"]
    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    # ---- the probe: which bank, track and part the panel edits ---------------
    pr = OUT / "probe"
    pr.mkdir(exist_ok=True)
    run(base + ["--sequencer", "--internal-clock", "--frames", "1",
                "--step", f"-:dump:{DBPTR:#x},4={pr / 'db.bin'};{UI_TRACK:#x},1={pr / 'trk.bin'};"
                          f"{UI_PART:#x},1={pr / 'part.bin'}"], OUT / "probe.txt")
    db = int.from_bytes((pr / "db.bin").read_bytes(), "big")
    trk, part = (pr / "trk.bin").read_bytes()[0], (pr / "part.bin").read_bytes()[0]
    bank = (db - BLOB) // BANK_STRIDE
    pwin = db + part * PART_STRIDE
    run(base + ["--sequencer", "--internal-clock", "--frames", "1",
                "--step", f"-:dump:{pwin + ID2_OFF + trk:#x},1={pr / 'id.bin'};"
                          f"{pwin + P2_OFF + 30 * trk + 6:#x},1={pr / 'p2.bin'}"], OUT / "probe2.txt")
    fx_id, knob = (pr / "id.bin").read_bytes()[0], (pr / "p2.bin").read_bytes()[0]
    pokes = []
    if not page2_ok(fx_id):
        fx_id = next((i for i in REVERBS if page2_ok(i)), None)
        if fx_id is None:
            sys.exit("verify_plocks_p2: no FX2 in the image with a page-2 slot 0 to lock")
        pokes = [f"{pwin + ID2_OFF + trk:#x}={fx_id:#x}", f"{LIVE_IDS + 8 + trk:#x}={fx_id:#x}"]
    print(f"  bank {bank + 1}, track {trk + 1}, part {part + 1}, FX2 id {fx_id:#04x}, page-2 slot 0 = {knob}")

    def block(ptn, track):
        return STORE + ((bank * 16 + ptn) * 8 + track) * TRACK_B

    # An independent, deterministic UI fixture. Never alter the user's project
    # or the card used by the save/playback tests below.
    display_project = OUT / "display-project"
    if display_project.exists():
        shutil.rmtree(display_project)
    shutil.copytree(copy, display_project)
    ot_project.set_fx(display_project, "fx1", 1, "COMPRESSOR", page2=[0] * 6, guard=False)
    # Inserts may reuse a reverb id for a small-range selector. The pixel
    # oracle needs a numeric slot covering 20..53, not that selector.
    display_fx2 = fallback if rd32(rd32(DESC2 + 4 * fallback) + 0x9a + 4 * 6) >= 54 else "COMPRESSOR"
    ot_project.set_fx(display_project, "fx2", 1, display_fx2, page2=[0] * 6, guard=False)
    display_card = OUT / "display-card.img"
    run([PY, ROOT / "tools/emu/ot_emu/stage_card.py", display_project, a.set_name, a.name,
         "--tree", OUT / "display-tree", "--out", display_card], OUT / "display-stage.log")
    display_walk(image, display_card, a.set_name, a.name, STORE, OUT / "display", check)
    if a.display_only:
        print(f"verify_plocks_p2 display: {fails} failure(s)")
        return int(bool(fails))

    # ---- the panel scenarios, one load ----------------------------------------
    def panel(tag, extra):
        s = Script(); record(s); extra(s)
        sp = OUT / f"{tag}.script"; sp.write_text(s.text())
        dump = (f"{block(0, trk):#x},{TRACK_B}={OUT / f'{tag}_p0.bin'};"
                f"{block(1, trk):#x},{TRACK_B}={OUT / f'{tag}_p1.bin'};"
                f"{db + trk * TRK_STRIDE + 0x59:#x},32={OUT / f'{tag}_stock.bin'}")
        args = (["--poke", ";".join(pokes)] if pokes else []) + ["--live-script", sp, "--mem-dump", dump]
        return f"{OUT / (tag + '.txt')} " + " ".join(map(str, args))

    def copy_paste(s):
        s.hold("t1", "rec"); s.hold("t5", "stop")

    def clear5(s):
        copy_paste(s); s.hold("t5", "play")

    def pattern(s):
        clear5(s); s.tap("rec", 400); s.hold("func", "rec"); s.hold("pattern", "t2"); s.hold("func", "stop")

    def pclear(s):
        pattern(s); s.hold("func", "play")

    def undo(s):
        pclear(s); s.hold("func", "play")

    def tap_clear(s):
        s.tap("t1")

    scen = [panel("record", copy_paste), panel("clear", clear5), panel("pattern", pattern),
            panel("pclear", pclear), panel("undo", undo), panel("tap_clear", tap_clear)]

    # playback: T1 step 1 FX2 page-2 slot 0 = 99 everywhere, trigs on steps 1 and 2
    lock = [f"{STORE + ((b * 16 + p) * 8 + 0) * TRACK_B + 6:#x}=99" for b in range(16) for p in range(16)]
    play_dumps = [f"{f}:dump:{LANES:#x},{8 * 72}={OUT / f'lane_{f}.bin'}" for f in (50, 1500)]
    play = ["--dsp", "--sequencer", "--internal-clock", "--frames", "1600", "--main-level", "64",
            "--step", f"-:call:{INIT:#x}", "--step", f"-:poke:{';'.join(lock)};{db + 7:#x}=0x03",
            "--step", f"-:dump:{LANES:#x},{8 * 72}={OUT / 'lane_pre.bin'}"]
    for d in play_dumps:
        play += ["--step", d]
    scen.append(f"{OUT / 'play.txt'} " + " ".join(play))

    # save: record, then SAVE PROJECT, the card out
    s = Script(); record(s)
    s.hold("func", "mixer", gap=1000); s.tap("right", 700); s.tap("down", 500)
    s.tap("yes", 1100); s.tap("yes", 9000)
    (OUT / "save.script").write_text(s.text())
    saved = OUT / "saved.img"
    scen.append(f"{OUT / 'save.txt'} " + " ".join(
        (["--poke", ";".join(pokes)] if pokes else []) + ["--live-script", str(OUT / "save.script"),
                                                          "--card-out", str(saved),
                                                          "--mem-dump", f"{CS1:#x},{CS1_LEN:#x}={OUT / 'cs1_saved.bin'}"]))
    # unsaved: record, a pause, the card and CS1 as a power cut leaves them
    s = Script(); record(s); s.send("enc 6 0", 2000)
    (OUT / "unsaved.script").write_text(s.text())
    unsaved = OUT / "unsaved.img"
    scen.append(f"{OUT / 'unsaved.txt'} " + " ".join(
        (["--poke", ";".join(pokes)] if pokes else []) + ["--live-script", str(OUT / "unsaved.script"),
                                                          "--card-out", str(unsaved),
                                                          "--mem-dump", f"{CS1:#x},{CS1_LEN:#x}={OUT / 'cs1_unsaved.bin'}"]))
    cmd = base + [x for sc in scen for x in ("--scenario", sc)]
    run(cmd, OUT / "port.txt")

    # ---- the panel checks -----------------------------------------------------
    def steps(tag, ptn):
        d = (OUT / f"{tag}_p{ptn}.bin").read_bytes()
        return {i: d[i * REC:(i + 1) * REC] for i in range(64)}

    rec = steps("record", 0)
    v = rec[0][6]
    check(f"record: step 1 FX2 page-2 slot 0 locked ({v}, the Part's {knob})", v not in (0xff, knob))
    check(f"record: no other page-2 byte of step 1 ({rec[0].hex()})",
          all(b == 0xff for i, b in enumerate(rec[0]) if i != 6))
    check("bare trig tap after editing still clears the step's page-2 locks",
          steps("tap_clear", 0)[0] == b"\xff" * REC)
    stock = (OUT / "record_stock.bin").read_bytes()
    check(f"record: stock's page-1 locks of step 1 untouched ({stock.hex()})", stock == b"\xff" * 32)
    check(f"trig copy + paste: step 5 = step 1 ({rec[4].hex()})", rec[4] == rec[0])
    c = steps("clear", 0)
    check(f"clear locks: step 5 none ({c[4].hex()}), step 1 kept", c[4] == b"\xff" * 12 and c[0] == rec[0])
    check(f"pattern copy + paste: pattern 2 step 1 = {steps('pattern', 1)[0].hex()}",
          steps("pattern", 1)[0] == rec[0])
    check(f"clear pattern: pattern 2 step 1 none ({steps('pclear', 1)[0].hex()})",
          steps("pclear", 1)[0] == b"\xff" * 12)
    check(f"undo: pattern 2 step 1 back ({steps('undo', 1)[0].hex()})", steps("undo", 1)[0] == rec[0])

    # ---- the playback checks --------------------------------------------------
    pre = (OUT / "lane_pre.bin").read_bytes()
    lanes = {f: (OUT / f"lane_{f}.bin").read_bytes() for f in (50, 1500)}
    at = 50 + 6                                   # T1, FX2 page-2 slot 0
    check(f"play: frame 50 T1 FX2 page-2 slot 0 = {lanes[50][at]} (want 99)", lanes[50][at] == 99)
    check(f"play: frame 1500 back to the Part's {pre[at]} ({lanes[1500][at]})", lanes[1500][at] == pre[at])
    moved = [(t, j) for f in (50, 1500) for t in range(8) for j in range(50, 62)
             if (t, j) != (0, at) and lanes[f][72 * t + j] != pre[72 * t + j]]
    check(f"play: no other page-2 lane byte moved ({moved[:6]})", not moved)

    # ---- the save, and the load of the saved card -----------------------------
    sys.path.insert(0, str(ROOT / "tools/emu"))
    import emu_card  # noqa: E402
    files = emu_card.extract_image(saved.read_bytes()) if saved.is_file() else {}
    nn = f"p2lk{bank + 1:02d}"
    for ext in ("work", "strd"):
        k = next((k for k in files if k.lower().endswith(f"/{nn}.{ext}")), None)
        d = files.get(k, b"")
        got = d[16 + (trk * 64) * REC + 6] if len(d) == 16 + 16 * 8 * TRACK_B else None
        check(f"save: {nn}.{ext} holds the lock ({got})", got == v)
    if saved.is_file():
        reload_dump = OUT / "reload.bin"
        s = Script(); s.tap("no", 400)
        (OUT / "reload.script").write_text(s.text())
        run([EMU, "--image", image, "--card", saved, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
             "--live-script", OUT / "reload.script", "--mem-dump", f"{block(0, trk) + 6:#x},1={reload_dump}"],
            OUT / "reload.txt")
        got = reload_dump.read_bytes()[0] if reload_dump.is_file() else None
        check(f"load: the saved card's lock is in STORE after the load ({got})", got == v)

    # ---- power cycles -----------------------------------------------------------
    cs1s, cs1u = OUT / "cs1_saved.bin", OUT / "cs1_unsaved.bin"
    if cs1s.is_file():
        d = bytearray(cs1s.read_bytes())
        d[NV - CS1:NV - CS1 + 4] = bytes(4)            # no CS1 copy: the file
        (OUT / "cs1_nocopy.bin").write_bytes(d)
    s = Script(); s.tap("no", 400)
    (OUT / "power.script").write_text(s.text())

    def power(tag, img_, cs1_):
        if not (img_.is_file() and cs1_.is_file()):
            return tag, None
        dump = OUT / f"power_{tag}.bin"
        run([EMU, "--image", image, "--card", img_, "--cs1-in", cs1_, "--no-post", "--set", a.set_name,
             "--project", a.name, "--load-ms", "90000", "--live-script", OUT / "power.script",
             "--mem-dump", f"{block(0, trk) + 6:#x},1={dump}"], OUT / f"power_{tag}.txt")
        return tag, dump.read_bytes()[0] if dump.is_file() else None
    jobs = [("saved", saved, cs1s), ("unsaved", unsaved, cs1u), ("nocopy", saved, OUT / "cs1_nocopy.bin")]
    with ThreadPoolExecutor(3) as ex:
        got = dict(ex.map(lambda j: power(*j), jobs))
    check(f"power cycle, saved: the lock is in STORE ({got['saved']})", got["saved"] == v)
    check(f"power cycle, never saved: the lock is in STORE from CS1 ({got['unsaved']})", got["unsaved"] == v)
    check(f"power cycle, no CS1 copy: the lock is in STORE from p2lk{bank + 1:02d}.work ({got['nocopy']})",
          got["nocopy"] == v)
    # ---- a refused p2lkNN.work is listed and never written over -------------------
    if saved.is_file() and "store_npend" in sym:
        prefix = f"/{a.name.lower()}/"
        proj = OUT / "proj_bad"
        if proj.exists():
            shutil.rmtree(proj)
        proj.mkdir(parents=True)
        for k, v in files.items():
            if prefix in k.lower() and "/" not in k.lower().split(prefix, 1)[1]:
                (proj / k.rsplit("/", 1)[1]).write_bytes(v)
        wk = proj / f"{nn}.work"
        bad = bytearray(wk.read_bytes()); bad[0] ^= 0x20; wk.write_bytes(bytes(bad))        # 'P2LK' -> 'p2LK'
        card_bad = OUT / "card_bad.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), a.set_name, a.name,
                            "--tree", str(OUT / "tree_bad"), "--out", str(card_bad)], cwd=ROOT, capture_output=True, text=True)
        check("refused: the card with a bad p2lk header staged", r.returncode == 0)
        run([EMU, "--image", image, "--card", card_bad, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
             "--live-script", OUT / "save.script", "--card-out", OUT / "refused.img",
             "--mem-dump", f"{sym['store_npend']:#x},4={OUT / 'ref_np.bin'};{sym['store_pend']:#x},32={OUT / 'ref_pend.bin'}"],
            OUT / "refused.txt")
        npend = int.from_bytes((OUT / "ref_np.bin").read_bytes(), "big")
        pend = (OUT / "ref_pend.bin").read_bytes()
        listed = [(pend[2 * i], pend[2 * i + 1]) for i in range(npend)]
        check(f"refused: STORE lists the bank ({listed}, wanted (0, {bank}))", (0, bank) in listed)
        after = emu_card.extract_image((OUT / "refused.img").read_bytes())
        k = next((k for k in after if k.lower().endswith(f"/{nn}.work")), None)
        check(f"refused: {nn}.work is as it was after a SAVE PROJECT (it used to be overwritten)", after.get(k) == bytes(bad))
        # The first dialog names the lost feature, before any recovery choice.
        def refusal_ui(tag):
            s = Script(); s.tap("no", 400); s.send("enc 1 1", 800)
            if tag == "options":
                s.tap("yes", 600)
            elif tag == "cancel":
                s.tap("no", 400); s.send("enc 1 1", 800)
            script = OUT / f"ref_{tag}.script"; script.write_text(s.text())
            dump = OUT / f"ref_{tag}.bin"
            run([EMU, "--image", image, "--card", card_bad, "--set", a.set_name, "--project", a.name,
                 "--load-ms", "90000", "--mkii", "--live-script", script, "--lcd", OUT / f"ref_{tag}.lcd",
                 "--mem-dump", f"{sym['store_info_lines']:#x},4={dump};"
                 f"{sym['NWMASK']:#x},4={OUT / f'ref_{tag}_mask.bin'};"
                 f"0x460e5cd0,4={OUT / f'ref_{tag}_dialog.bin'};"
                 f"{sym['store_mown']:#x},4={OUT / f'ref_{tag}_menu.bin'}"], OUT / f"ref_{tag}.txt")
            word = lambda name: int.from_bytes((OUT / f"ref_{tag}_{name}.bin").read_bytes(), "big")
            check(f"refused {tag}: names FX page 2 locks and keeps the original file protected",
                  int.from_bytes(dump.read_bytes(), "big") == sym["store_info_plk"] and word("mask") & (1 << bank))
            check(f"refused {tag}: the expected dialog or choices are open",
                  bool(word("dialog")) == (tag == "info") and bool(word("menu")) == (tag == "options"))
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(refusal_ui, ("info", "options", "cancel")))
    print(f"verify_plocks_p2: {'FAIL' if fails else 'ok'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
