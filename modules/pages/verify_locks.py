#!/usr/bin/env python3
"""PAGES' locks under the port (MKII): DRUMMER's KIT BALANCE takes step locks and scene locks.

    .venv/bin/python3 modules/pages/verify_locks.py [REMIX] [--image out/mainos_bus.bin] [--card CARD]

The image is a remix with PAGES' locks (DRUMMER, PAGES, EVENTS, STORE: remixes/test/drummer); a
remix without them SKIPs. With no --card the gate makes its own (no sample of anyone's): an empty
project made by the image (tools/hw/ot_fresh.py), DRUMMER's manual loop (manual_fixture.py: 16
synthetic hits, one slice each) on FLEX slot 1, T1 signed a DRUMMER track with a kit in
drummer.work (so no AUTO question at the load). It first checks that the two generated units are
current (pages/generate.py and drummer/generate.py --check). Each run answers the date prompt, selects T1,
opens KIT BALANCE (SRC again), then:

  lock    GRID RECORDING (REC), trig 3 placed, then held, A -64, C +6, let go: step 3 of bank 1's
          pattern 1 locks KICK OUT (0) and HATS +30 (83); the Part's six bytes stay 64
  empty   trig 7 held on an empty step, A -64: stock places the trig at the press (GRID RECORDING), so
          the step has its trig and the lock, as stock's own lock on an empty step
  off     lock, then trig 3 tapped (taken off): its locks go with it
  relock  off, then trig 3 placed again: no lock comes back
  clear   lock, then trig 3 held + PLAY (stock's clear of the held steps' locks): none
  copy    lock, trig 3 held + REC (copy), trig 9 held + STOP (paste): step 9 has step 3's locks
  track   lock, FUNC + REC (copy the track), T2, FUNC + STOP (paste): T2's step 3 has them too
  pattern lock, REC off, FUNC + REC (copy the pattern), PATTERN + trig 2, FUNC + STOP: pattern 2 too
  pclear  pattern, then FUNC + PLAY (clear pattern 2): pattern 2's go, pattern 1's stay
  pundo   pclear, then FUNC + PLAY again (undo): pattern 2's back
  held    the same, the screen read with trig 3 still held: the title names STEP 3 (dr_l2_where)
  two     trigs 1 and 5 placed, held, F +4: PERC +20 (77) on steps 1 and 5
  func    trig 3 held, A -64, then FUNC held and A turned: the lock removed, none left
  scene   SCENE A held, B -4: Part 1's scene A (its byte read) locks SNARE -20 (51), no step lock
  sceneb  SCENE B held, A -4: Part 1's scene B (its byte read) locks KICK -20 (51); SCENE B has its own
          knob handler (0x40052e98, not A's 0x40053498: image 86 on the unit locked LIVE's SEED)
  free    no REC, trig 3 held, A +3: stock's knob (no held editor out of GRID RECORDING): the Part
          turns (KICK +15 = 73), no lock
  fills   the page after KIT BALANCE (NEXT: SRC again), REC, trig 3 held, A +2: no lock, and stock's
          held editor never runs (it would lock LIVE under the window: reported on image 87)
  fillsc  the same page, SCENE A held, A +2: no lock, stock's scene handler never runs

  save    lock's step locks and scene's scene lock, then PROJECT > SAVE PROJECT (the card kept): the
          card holds pglocks.work (16-byte header + the 3 entries) and pglocks.strd, the same bytes
  boot2   the saved card booted: the three locks back in the pool (PGLOCKS.WORK through STORE)

Every case: stock's held editor and scene handlers never go on past PAGES (their continuations
0x400508ec, 0x400534a0, 0x40052ea0 not reached): a turn PAGES dropped locks nothing in stock.

Playback is DRUMMER's verify_port.py (cases lockmix, lockscene). Screens: out/pages/locks/<case>.png.
"""
import argparse
import concurrent.futures as cf
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EMU = ROOT / "out/emu/ot_emu"
OUT = ROOT / "out/pages/locks"
PART = 0x40170F60                     # bank 1's Part 1 in RAM (the card's working Part)
MIX_AT = 0x2A                         # T1's KIT BALANCE bytes
SRC, YES, T1, REC, SCENE_A, SCENE_B, FUNC = 0x22, 0x31, 0x10, 0x29, 0x19, 0x1A, 0x2D
PROJ, RIGHT, DOWN = 0x1C, 0x21, 0x20
FAILS = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def symbol(name, need=True):
    for line in (ROOT / "out/platform/runtime/runtime.map").read_text().splitlines():
        w = line.split()
        if len(w) == 2 and w[1] == name and w[0].startswith("0x"):
            return int(w[0], 16)
    if need:
        sys.exit(f"verify_locks: {name} not in the runtime map (build a remix with DRUMMER, PAGES and EVENTS)")
    return None


def fixture(image):
    """The gate's own card: an empty project by the image, DRUMMER's manual loop, T1 a DRUMMER track."""
    import shutil
    import struct
    import zlib
    sys.path.insert(0, str(ROOT / "modules/drummer"))
    import manual_fixture as mf
    import probe_slices as ps
    work = OUT / "fixture"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    r = subprocess.run([str(ROOT / ".venv/bin/python3"), str(ROOT / "tools/hw/ot_fresh.py"), "--image", image,
                        "--out", str(work / "fresh")], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_locks: ot_fresh failed:\n{(r.stdout + r.stderr)[-1500:]}")
    src = next(p.parent for p in (work / "fresh").rglob("project.work"))
    wav = work / "loop.wav"
    frames = mf.loop_wav(wav)
    slices = [(i * mf.STEP, (i + 1) * mf.STEP, 0xFFFFFFFF) for i in range(mf.STEPS)] + [(0, 0, 0)] * (64 - mf.STEPS)
    proj = work / "project"
    ps.build_project(src, proj, frames, slices, mf.STEPS, mf.TEMPO)

    def mut(data):                       # T1 a DRUMMER track ("DR",1 in NEIGHBOR's PLAYBACK bytes), no trig
        for p in range(ps.otp.NPARTS_ALL):
            part = ps.otp.PART_BASE + p * ps.otp.PART_STRIDE
            data[part + 9 + 60:part + 9 + 63] = b"DR\x01"
        off = ps.otp.trac_off(0, 0)
        data[off:off + 64] = bytes(64)
        data[off + 0x59:off + 0x59 + 64 * 32] = bytes([0xFF]) * (64 * 32)
    ps.otp._bank_write(proj, 1, mut, guard=False)
    t1 = (bytes(16) + bytes([15] * 48) + bytes(16) + bytes(48) + bytes(128) + bytes(64)
          + bytes((0, 1, 6, 4, 3, 5, 7, 8, 2)) + bytes((0, 4, 1)))     # drummer.work v1: T1's kit ready
    assert len(t1) == 332
    body = t1 + bytes(332 * 7)
    data = struct.pack(">4I", 0x44524D4B, 1, len(body), zlib.crc32(body)) + body
    for name in ("drummer.work", "drummer.strd"):
        (proj / name).write_bytes(data)
    card = work / "card.img"
    r = subprocess.run([str(ROOT / ".venv/bin/python3"), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj),
                        "OCTABAM", "RIG", "--tree", str(work / "tree"), "--out", str(card),
                        "--audio", f"{wav}:{ps.SAMPLE_REL}"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_locks: stage_card failed:\n{(r.stdout + r.stderr)[-1500:]}")
    return str(card)


def tap(code, gap=0.5):
    return [(gap, f"key {code:#x} down"), (0.06, f"key {code:#x} up")]


OPEN = tap(YES, 0.3) + tap(T1, 1.2) + tap(SRC, 0.6)
STOP, PLAY, PATTERN, T2 = 0x27, 0x28, 0x2E, 0x11
GRID = OPEN + tap(REC)                 # KIT BALANCE open, GRID RECORDING on
LOCK3 = tap(0x2) + [(0.5, "key 0x2 down"), (0.4, "enc 0 -64"), (0.3, "enc 2 6"), (0.4, "key 0x2 up")]   # trig 3 placed, locked


def chord(hold, key):
    return [(0.4, f"key {hold:#x} down"), (0.1, f"key {key:#x} down"), (0.06, f"key {key:#x} up"),
            (0.2, f"key {hold:#x} up")]


QUIT = [(0.6, "quit")]
CASES = {
    "lock": GRID + LOCK3 + QUIT,
    "held": GRID + tap(0x2) + [(0.5, "key 0x2 down"), (0.4, "enc 0 -64"), (0.6, "quit")],
    "two": GRID + tap(0x0) + tap(0x4) + [(0.5, "key 0x0 down"), (0.1, "key 0x4 down"), (0.4, "enc 5 4"),
                                         (0.3, "key 0x4 up"), (0.1, "key 0x0 up")] + QUIT,
    "empty": GRID + [(0.5, "key 0x6 down"), (0.4, "enc 0 -64"), (0.3, "key 0x6 up")] + QUIT,
    "func": GRID + tap(0x2) + [(0.5, "key 0x2 down"), (0.4, "enc 0 -64"), (0.3, f"key {FUNC:#x} down"),
                               (0.3, "enc 0 1"), (0.3, f"key {FUNC:#x} up"), (0.3, "key 0x2 up")] + QUIT,
    "off": GRID + LOCK3 + tap(0x2) + QUIT,
    "relock": GRID + LOCK3 + tap(0x2) + tap(0x2) + QUIT,
    "clear": GRID + LOCK3 + chord(0x2, PLAY) + QUIT,
    "copy": GRID + LOCK3 + chord(0x2, REC) + chord(0x8, STOP) + QUIT,
    "track": GRID + LOCK3 + chord(FUNC, REC) + tap(T2, 0.6) + chord(FUNC, STOP) + QUIT,
    "pattern": GRID + LOCK3 + tap(REC) + chord(FUNC, REC) + chord(PATTERN, 0x1) + chord(FUNC, STOP) + QUIT,
    "pclear": GRID + LOCK3 + tap(REC) + chord(FUNC, REC) + chord(PATTERN, 0x1) + chord(FUNC, STOP)
              + chord(FUNC, PLAY) + QUIT,
    "pundo": GRID + LOCK3 + tap(REC) + chord(FUNC, REC) + chord(PATTERN, 0x1) + chord(FUNC, STOP)
             + chord(FUNC, PLAY) + chord(FUNC, PLAY) + QUIT,
    "scene": OPEN + [(0.5, f"key {SCENE_A:#x} down"), (0.4, "enc 1 -4"), (0.6, "quit")],
    "sceneb": OPEN + [(0.5, f"key {SCENE_B:#x} down"), (0.4, "enc 0 -4"), (0.6, "quit")],
    "free": OPEN + [(0.5, "key 0x2 down"), (0.4, "enc 0 3"), (0.3, "key 0x2 up"), (0.5, "quit")],
    "fills": OPEN + tap(SRC, 0.6) + tap(REC) + [(0.5, "key 0x2 down"), (0.4, "enc 0 2"), (0.3, "key 0x2 up"),
                                                (0.5, "quit")],
    "fillsc": OPEN + tap(SRC, 0.6) + [(0.5, f"key {SCENE_A:#x} down"), (0.4, "enc 0 2"), (0.6, "quit")],
    "save": GRID + LOCK3
            + tap(REC) + [(0.5, f"key {SCENE_A:#x} down"), (0.4, "enc 1 -4"), (0.4, f"key {SCENE_A:#x} up")]
            + tap(PROJ, 1.0) + tap(RIGHT, 0.7) + tap(DOWN, 0.5) + tap(YES, 1.1) + tap(YES, 30.0)
            + [(60.0, "quit")],                # the project store's .strd copies end ~20 s in (port)
    "boot2": [(0.3, f"key {YES:#x} down"), (0.06, f"key {YES:#x} up"), (1.5, "quit")],
}
STOCK_ON = (0x400508EC, 0x400534A0, 0x40052EA0)   # stock's held editor / scene handlers past their prologue


def run(a, name):
    t, lines = 0.0, []
    for gap, ev in CASES[name]:
        t += gap
        lines.append(f"{int(t * 1000)} {ev}")
    script = OUT / f"{name}.script"
    script.write_text("\n".join(lines) + "\n")
    pool, count, where = symbol("pg_lk_pool"), symbol("pg_lk_count"), symbol("dr_l2_where")
    card = str(OUT / "save.img") if name == "boot2" else a.card
    extra = ["--card-out", str(OUT / "save.img")] if name == "save" else []
    cmd = [str(EMU), "--image", a.image, "--card", card, *extra, "--set", "OCTABAM", "--project", "RIG", "--mkii",
           "--load-ms", "90000", "--live-script", str(script), "--lcd", str(OUT / f"{name}.lcd"),
           "--watch-pc", ",".join(f"{a:#x}" for a in STOCK_ON),
           "--mem-dump", f"{PART + MIX_AT:#x},6={OUT}/{name}_mix.bin;{pool:#x},64={OUT}/{name}_pool.bin;"
                         f"{count:#x},4={OUT}/{name}_count.bin;{where:#x},4={OUT}/{name}_where.bin;"
                         f"{PART + 0x10:#x},2={OUT}/{name}_ab.bin;0x400e21e0,8={OUT}/{name}_trigs.bin"]
    with open(OUT / f"{name}.log", "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    subprocess.run([str(ROOT / ".venv/bin/python3"), str(ROOT / "tools/emu/lcd_view.py"), str(OUT / f"{name}.lcd"),
                    "--png", str(OUT / f"{name}.png")], cwd=ROOT, capture_output=True)
    rd = lambda s: (OUT / f"{name}_{s}.bin").read_bytes() if (OUT / f"{name}_{s}.bin").is_file() else b""
    n = int.from_bytes(rd("count"), "big") if rd("count") else -1
    raw = rd("pool")
    entries = [int.from_bytes(raw[i:i + 4], "big") for i in range(0, 4 * max(0, min(n, 16)), 4)]
    text = (OUT / f"{name}.log").read_text()
    m = re.search(r"watch-pc\s*: (\d+) hit", text)
    stock = int(m.group(1)) if m else -1
    return (name, rc, list(rd("mix")), entries, int.from_bytes(rd("where"), "big") if rd("where") else -1,
            list(rd("ab")), stock, rd("trigs"))


def lock(scene, track, ss, slot, value, page=1, bank=0, pp=0):
    """pages/locks.c's entry."""
    return scene << 31 | bank << 27 | pp << 23 | track << 20 | ss << 14 | page << 11 | slot << 8 | value


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="", help="the remix built (make check passes it)")
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--card", default="", help="a card with T1 a DRUMMER track (default: the gate's own)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print("PAGES locks: DRUMMER's KIT BALANCE (port, MKII)")
    for gen in ("modules/pages/generate.py", "modules/drummer/generate.py"):
        r = subprocess.run([sys.executable, str(ROOT / gen), "--check"], cwd=ROOT, capture_output=True, text=True)
        check(f"{gen} --check: the generated unit is current", r.returncode == 0, (r.stdout + r.stderr).strip()[-200:])
    if symbol("pg_lk_pool", need=False) is None or symbol("dr_l2_where", need=False) is None:
        print(f"  [SKIP] verify_locks: {a.remix or 'this image'} has no PAGES locks with DRUMMER")
        return 1 if FAILS else 0
    if not a.card:
        a.card = fixture(a.image)
    first = [n for n in CASES if n != "boot2"]
    with cf.ThreadPoolExecutor(len(first)) as ex:
        res = {r[0]: r[1:] for r in ex.map(lambda n: run(a, n), first)}
    r = run(a, "boot2")                      # on the card "save" left
    res[r[0]] = r[1:]
    for n, (rc, *_r) in res.items():
        check(f"{n}: the port ran", rc == 0, f"exit {rc}")
    part = lambda n: res[n][1]
    ents = lambda n: res[n][2]
    check("lock: step 3 locks KICK OUT and HATS +30, the Part unchanged",
          ents("lock") == [lock(0, 0, 2, 0, 0), lock(0, 0, 2, 2, 83)] and part("lock") == [64] * 6,
          f"{[hex(e) for e in ents('lock')]} Part {part('lock')}")
    check("held: the title names STEP 3 while trig 3 is held", res["held"][3] == 3, f"where {res['held'][3]}")
    check("two: trigs 1 and 5 held lock PERC +20 on both",
          ents("two") == [lock(0, 0, 0, 5, 77), lock(0, 0, 4, 5, 77)], str([hex(e) for e in ents("two")]))
    check("func: FUNC + turn removes the lock", ents("func") == [], str([hex(e) for e in ents("func")]))
    L3 = [lock(0, 0, 2, 0, 0), lock(0, 0, 2, 2, 83)]
    hx = lambda n: str([hex(e) for e in ents(n)])
    trigs = res["empty"][6]
    check("empty: a held empty step gets stock's trig (at the press) and the lock",
          ents("empty") == [lock(0, 0, 6, 0, 0)] and len(trigs) == 8 and trigs[7] >> 6 & 1,
          f"{hx('empty')} trigs {trigs.hex()}")
    check("off: a trig taken off takes its locks", ents("off") == [], hx("off"))
    check("relock: placed again, the trig has none", ents("relock") == [], hx("relock"))
    check("clear: trig + PLAY clears its locks", ents("clear") == [], hx("clear"))
    check("copy: the trig's paste on step 9 carries its locks",
          sorted(ents("copy")) == sorted(L3 + [lock(0, 0, 8, 0, 0), lock(0, 0, 8, 2, 83)]), hx("copy"))
    check("track: T2 (pasted) carries T1's locks",
          sorted(ents("track")) == sorted(L3 + [lock(0, 1, 2, 0, 0), lock(0, 1, 2, 2, 83)]), hx("track"))
    p2 = [lock(0, 0, 2, 0, 0, pp=1), lock(0, 0, 2, 2, 83, pp=1)]
    check("pattern: pattern 2 (pasted) carries pattern 1's locks", sorted(ents("pattern")) == sorted(L3 + p2), hx("pattern"))
    check("pclear: pattern 2 cleared, pattern 1's kept", sorted(ents("pclear")) == sorted(L3), hx("pclear"))
    check("pundo: the clear undone, pattern 2's back", sorted(ents("pundo")) == sorted(L3 + p2), hx("pundo"))
    sa, sb = (res["scene"][4] + [0, 0])[:2]
    check(f"scene: SCENE A held locks SNARE -20 in the Part's scene A ({sa + 1}), the Part unchanged",
          ents("scene") == [lock(1, 0, sa, 1, 51)] and part("scene") == [64] * 6,
          f"{[hex(e) for e in ents('scene')]} Part {part('scene')}")
    check(f"sceneb: SCENE B held locks KICK -20 in the Part's scene B ({sb + 1}), the Part unchanged",
          sa != sb and ents("sceneb") == [lock(1, 0, sb, 0, 51)] and part("sceneb") == [64] * 6,
          f"{[hex(e) for e in ents('sceneb')]} Part {part('sceneb')}")
    check("free: out of GRID RECORDING a held trig takes no lock, the knob turns the Part",
          ents("free") == [] and part("free")[0] == 73, f"{[hex(e) for e in ents('free')]} Part {part('free')}")
    check("fills: the page after KIT BALANCE takes no lock", ents("fills") == [], str([hex(e) for e in ents("fills")]))
    check("fillsc: nor a scene lock", ents("fillsc") == [], str([hex(e) for e in ents("fillsc")]))
    sa = (res["scene"][4] + [0])[0]
    want = sorted([lock(0, 0, 2, 0, 0), lock(0, 0, 2, 2, 83), lock(1, 0, sa, 1, 51)])
    check("save: the locks in the pool before SAVE PROJECT", sorted(ents("save")) == want,
          str([hex(e) for e in ents("save")]))
    check("boot2: the saved card boots with the same locks (PGLOCKS.WORK)", sorted(ents("boot2")) == want,
          str([hex(e) for e in ents("boot2")]))
    files = {}
    if (OUT / "save.img").is_file():
        sys.path.insert(0, str(ROOT / "tools"))
        from emu import emu_card
        files = {k.lower().rsplit("/", 1)[-1]: v for k, v in emu_card.extract_image((OUT / "save.img").read_bytes()).items()
                 if "/RIG/" in k}
    check("save: the card holds pglocks.work and pglocks.strd, the same bytes (the project store)",
          {"pglocks.work", "pglocks.strd"} <= set(files) and files["pglocks.work"] == files["pglocks.strd"]
          and len(files["pglocks.work"]) == 16 + 4 * len(want),
          str(sorted((f, len(v)) for f, v in files.items() if "pglock" in f)))
    for n in CASES:
        if n not in ("free", "boot2", "save"):                  # free: no REC, no scene: stock's own knob
            check(f"{n}: stock's held editor / scene handler never ran on past PAGES", res[n][5] == 0,
                  f"{res[n][5]} hits")
    print(f"{'PASS' if not FAILS else 'FAIL'}: PAGES locks")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
