#!/usr/bin/env python3
"""APPLY SCENE under the port (MKII, and MKI for a subset): the scene keys' gestures on a fresh project.

    .venv/bin/python3 tools/verify/verify_apply_scene.py [REMIX] [--image out/mainos_bus.bin] [--case NAME ...]

The image is a remix with APPLY SCENE (remixes/test/apply-scene); a remix without it SKIPs. The gate makes its
own card: an empty project made by the image (tools/hw/ot_fresh.py). Each case answers the date prompt, selects
T1, opens AMP and locks scene A's ATK and HOLD (A +10, B +5) and, for the blends, scene B's ATK (A -20), with
the panel as a person does; then the gesture. Every case reads the Part (bank 1, Part 1), pattern 1's T1
record and CUE's held flag from RAM after the script, and the screen. The morph's working copy (0x80000ed4)
is not read: under a live script no track plays a Part (0x8000182a/0x80001832 stay 0xff), so stock never
fills it. That the commit reaches it rests on 0x40002df4, which copies all 32 bytes of the scene,
unlocked ones included, for every track playing the bank and Part. TRACKS is ACTIVE unless a case pokes ALL.
The p2* cases are page 2 (SCENES P2): cells poked into the Part's scenes at the start, then the gesture; the
Part's page 2, every scene's cells and T1's live page 2 are read after. p2panel makes its lock from the panel
(FX2 SETUP, SCENE A + knob C), as SCENES P2's own gate does.
Screens and logs: out/apply-scene/<case>.*.
"""
import argparse
import concurrent.futures as cf
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EMU = ROOT / "out/emu/ot_emu"
OUT = ROOT / "out/apply-scene"
BANK = 0x400E21E0                     # bank 1 in RAM
PART = BANK + 0x8ED80                 # its Part 1
PART_SIZE = 0x18B2
TRACK1 = BANK                         # pattern 1's T1 record
TRACK_SIZE = 0x91A
SCENES = 0x662                        # Part + scene * 0x100 + track * 0x20 + flat
AMP = 0x11A + 6                       # Part + track * 24 + this: AMP page 1 (flats 12-17)
ATK, HOLD, XVOL = 12, 13, 17
YES, T1, T2, SRC, AMPK, REC, PLAY, STOP, SCENE_A, SCENE_B = 0x31, 0x10, 0x11, 0x22, 0x23, 0x29, 0x28, 0x27, 0x19, 0x1A
FUNC, CUE, PTN, RIGHT, MIDI = 0x2D, 0x2A, 0x2E, 0x21, 0x35
MISC = ((BANK + 0x8E57, 1), (BANK + 0x8ED8 + 0x8E57, 1), (0x100B14CF, 1), (0x100B14D0, 1), (0x460D168F, 1),
        (0x80000842, 12))
#   patterns 1 and 2's Part bytes, the edited Part and pattern, CUE held (low byte), T1's live page 2 (the lane)
ARM_ALL = 0x4005E294
FAILS = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def symbol(name):
    m = ROOT / "out/platform/runtime/runtime.map"
    if not m.is_file():
        return None
    for line in m.read_text().splitlines():
        w = line.split()
        if len(w) == 2 and w[1] == name and w[0].startswith("0x"):
            return int(w[0], 16)
    return None


def fixture(image):
    """An empty project made by the image, staged on a card."""
    work = OUT / "fixture"
    work.mkdir(parents=True, exist_ok=True)
    py = str(ROOT / ".venv/bin/python3")
    r = subprocess.run([py, str(ROOT / "tools/hw/ot_fresh.py"), "--image", image, "--out", str(work / "fresh")],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_apply_scene: ot_fresh failed:\n{(r.stdout + r.stderr)[-1500:]}")
    proj = next(p.parent for p in (work / "fresh").rglob("project.work"))
    card = work / "card.img"
    r = subprocess.run([py, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "RIG",
                        "--tree", str(work / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_apply_scene: stage_card failed:\n{(r.stdout + r.stderr)[-1500:]}")
    return str(card)


def tap(code, gap=0.5):
    return [(gap, f"key {code:#x} down"), (0.06, f"key {code:#x} up")]


def hold(code, gap=0.4):
    return [(gap, f"key {code:#x} down")]


def let(code, gap=0.3):
    return [(gap, f"key {code:#x} up")]


OPEN = tap(YES, 0.3) + tap(T1, 1.2) + tap(AMPK, 0.6)
LOCK_A = hold(SCENE_A) + [(0.4, "enc 0 10"), (0.3, "enc 1 -10")] + let(SCENE_A)
LOCK_B = hold(SCENE_B) + [(0.4, "enc 0 30"), (0.3, "enc 2 -20")] + let(SCENE_B)
QUIT = [(0.8, "quit")]

# Page 2 (SCENES P2): cells poked into Part 1's scenes, (scene, cell) -> (key, value), key = track<<4 | fx1<<3 |
# slot. A fresh Part: scene A = 0, B = 8; T1 and T2 FX1 FILTER (page 2: slots A-E selects, F 0..127), FX2 DELAY
# (slot C 0..127, the rest selects); page 2 j = FX1 slot (0-5), FX2 slot + 6.
CELLS = 0x680                          # Part + scene * 0x100 + cell * 0x20: a cell's key, its value at + 1
P2 = 0x2FE                             # Part + track * 30 + j: page 2
P2_0 = [0, 0, 1, 0, 3, 0, 0, 1, 127, 1, 0, 0]    # a fresh Part's page 2 (FILTER, DELAY)
P2_CELLS = {(0, 0): (0x0D, 20),        # A: T1 FX1 F (j 5)
            (0, 1): (0x02, 30),        # A: T1 FX2 C (j 8)
            (0, 2): (0x0C, 1),         # A: T1 FX1 E (j 4), a select of 4
            (0, 3): (0x12, 40),        # A: T2 FX2 C
            (8, 0): (0x02, 100),       # B: T1 FX2 C
            (8, 1): (0x0C, 3),         # B: T1 FX1 E
            (3, 0): (0x0D, 77)}        # scene 4, assigned to neither: T1 FX1 F


def p2_seed(knobs=None):
    pokes = [f"{PART + CELLS + sc * 0x100 + c * 0x20 + i:#x}={b}" for (sc, c), kv in P2_CELLS.items()
             for i, b in enumerate(kv)]
    pokes += [f"{PART + P2 + j:#x}={v}" for j, v in (knobs or {}).items()]
    return [(0.2, "poke " + ";".join(pokes))]


CASES = {
    "pass": OPEN + hold(SCENE_A) + tap(0x2, 0.3) + let(SCENE_A) + tap(YES, 0.5) + QUIT,
    "applyA": OPEN + LOCK_A + hold(SCENE_A) + tap(YES, 0.3) + let(SCENE_A) + QUIT,
    "applyB": OPEN + LOCK_A + LOCK_B + hold(SCENE_B) + tap(YES, 0.3) + let(SCENE_B) + QUIT,
    "blend": OPEN + LOCK_A + LOCK_B + [(0.4, "pot 128")] + hold(SCENE_A) + hold(SCENE_B, 0.1) + tap(YES, 0.3)
             + let(SCENE_B) + let(SCENE_A, 0.1) + QUIT,
    "nothing": OPEN + hold(SCENE_A) + tap(YES, 0.3) + let(SCENE_A) + QUIT,
    "grid": OPEN + LOCK_A + tap(REC) + tap(0x2) + hold(0x2, 0.5) + hold(SCENE_A) + let(SCENE_A) + let(0x2) + QUIT,
    "gridab": OPEN + LOCK_A + LOCK_B + [(0.4, "pot 128")] + tap(REC) + tap(0x2) + hold(0x2, 0.5) + hold(SCENE_A)
              + hold(SCENE_B, 0.1) + let(SCENE_B) + let(SCENE_A, 0.1) + let(0x2) + QUIT,
    "live": OPEN + LOCK_A + tap(T2, 0.6) + LOCK_A + tap(REC) + tap(0x0) + tap(0x8) + tap(REC) + tap(T1, 0.6)
            + tap(REC) + tap(0x4) + tap(REC)
            + hold(REC) + tap(PLAY, 0.2) + let(REC, 0.2) + hold(SCENE_A, 0.3) + hold(YES, 0.2)
            + let(YES, 2.6) + let(SCENE_A, 0.1) + tap(STOP, 0.3) + QUIT,
    "kits": OPEN + LOCK_A + hold(PTN) + hold(FUNC, 0.1) + tap(RIGHT, 0.3) + let(FUNC) + let(PTN, 0.1)
            + hold(SCENE_A, 2.0) + tap(YES, 0.3) + let(SCENE_A) + QUIT,
    "midi": OPEN + LOCK_A + tap(MIDI) + hold(SCENE_A) + tap(YES, 0.3) + let(SCENE_A) + QUIT,
    "undo": OPEN + LOCK_A + hold(SCENE_A) + tap(YES, 0.3) + let(SCENE_A) + hold(FUNC, 0.6) + tap(CUE, 0.2)
            + let(FUNC, 1.5) + [(1.5, "quit")],
    "undoknob": OPEN + [(0.4, "enc 0 10"), (0.3, "enc 1 -10")] + hold(FUNC, 0.6) + tap(CUE, 0.2)
                + let(FUNC, 1.5) + [(1.5, "quit")],
    "savek": OPEN + LOCK_A + LOCK_B + [(0.4, "pot 128")] + hold(SCENE_A) + hold(SCENE_B, 0.1) + tap(0x4, 0.3)
             + let(SCENE_B) + let(SCENE_A, 0.1) + QUIT,
    "commit": OPEN + LOCK_A + LOCK_B + hold(SCENE_A) + tap(YES, 0.3) + let(SCENE_A) + QUIT,
    "active": OPEN + LOCK_A + tap(T2, 0.6) + LOCK_A + tap(T1, 0.6) + hold(SCENE_A) + tap(YES, 0.3) + let(SCENE_A)
              + QUIT,
    "all": OPEN + LOCK_A + tap(T2, 0.6) + LOCK_A + tap(T1, 0.6) + hold(SCENE_A) + tap(YES, 0.3) + let(SCENE_A)
           + QUIT,
    "p2commit": OPEN + p2_seed() + hold(SCENE_A) + tap(YES, 0.3) + let(SCENE_A) + QUIT,
    "p2all": OPEN + p2_seed() + hold(SCENE_A) + tap(YES, 0.3) + let(SCENE_A) + QUIT,
    "p2blend": OPEN + p2_seed() + [(0.4, "pot 128")] + hold(SCENE_A) + hold(SCENE_B, 0.1) + tap(YES, 0.3)
               + let(SCENE_B) + let(SCENE_A, 0.1) + QUIT,
    "p2savek": OPEN + p2_seed() + [(0.4, "pot 128")] + hold(SCENE_A) + hold(SCENE_B, 0.1) + tap(0x4, 0.3)
               + let(SCENE_B) + let(SCENE_A, 0.1) + QUIT,
    # from the panel: T1, FX2 SETUP (FX2 three times, as verify_scenes_p2), SCENE A held, knob C turned down
    # (SCENES P2 writes the lock), then SCENE A + YES
    "p2panel": OPEN + tap(0x26, 0.6) + tap(0x26, 0.25) + tap(0x26, 0.06) + hold(SCENE_A, 0.6)
               + [(0.3, "enc 2 -10"), (0.3, "enc 2 -10"), (0.3, "enc 2 -10")] + let(SCENE_A, 0.3)
               + hold(SCENE_A, 0.6) + tap(YES, 0.3) + let(SCENE_A) + QUIT,
}
# Settings poked into BRAIN's value longs before the script: (setting, value).
POKES = {"all": ((1, 1),), "p2all": ((1, 1),)}


def run(a, name, mkii=True):
    t, lines = 0.0, []
    for gap, ev in CASES[name]:
        t += gap
        lines.append(f"{int(t * 1000)} {ev}")
    script = OUT / f"{name}.script"
    script.write_text("\n".join(lines) + "\n")
    tag = name if mkii else f"{name}.mki"
    pokes = []
    for k, val in POKES.get(name, ()):        # TRACKS (1) = ALL: BRAIN's value long
        v = symbol(f"brain_v_octabam_apply_scene_{k}")
        pokes += ["--poke", f"{v + 3:#x}={val}"] if v else []
    misc = ";".join(f"{ad:#x},{n}={OUT}/{tag}_m{i}.bin" for i, (ad, n) in enumerate(MISC))
    cmd = [str(EMU), "--image", a.image, "--card", a.card, "--set", "OCTABAM", "--project", "RIG",
           *(["--mkii"] if mkii else []), "--load-ms", "90000", *pokes, "--live-script", str(script),
           "--lcd", str(OUT / f"{tag}.lcd"), "--watch-pc", f"{ARM_ALL:#x}",
           "--mem-dump", f"{PART:#x},{4 * PART_SIZE}={OUT}/{tag}_part.bin;{TRACK1:#x},{2 * TRACK_SIZE}={OUT}/{tag}_trk.bin;"
                         + misc]
    with open(OUT / f"{tag}.log", "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    subprocess.run([str(ROOT / ".venv/bin/python3"), str(ROOT / "tools/emu/lcd_view.py"), str(OUT / f"{tag}.lcd"),
                    "--png", str(OUT / f"{tag}.png")], cwd=ROOT, capture_output=True)
    rd = lambda s: (OUT / f"{tag}_{s}.bin").read_bytes() if (OUT / f"{tag}_{s}.bin").is_file() else b""
    log = (OUT / f"{tag}.log").read_text(errors="replace")
    misc = bytes(b for i in range(len(MISC)) for b in rd(f"m{i}"))
    return tag, rc, rd("part"), rd("trk") + misc, log


def ex_map(a, names, mkii=True):
    with cf.ThreadPoolExecutor(max(1, len(names))) as ex:
        return list(ex.map(lambda n: run(a, n, mkii), names))


def view(parts, trk, pn=0, t=0):
    """What a case left in Part pn: scene A / B slots, T1's AMP, a scene's T1 row; track t's step locks and
    trig mask (pattern 1)."""
    part = parts[pn * PART_SIZE:(pn + 1) * PART_SIZE]
    rec = trk[t * TRACK_SIZE:(t + 1) * TRACK_SIZE]
    sa, sb = part[0x10], part[0x11]
    row = lambda slot: list(part[SCENES + slot * 0x100:SCENES + slot * 0x100 + 32])
    step = lambda s: list(rec[0x59 + s * 32:0x59 + s * 32 + 30])
    trig = lambda s: rec[7 - s // 8] >> (s % 8) & 1
    return sa, sb, list(part[AMP:AMP + 6]), row, step, trig


def misc(trk):
    """Patterns 1 and 2's Part bytes, the edited Part, the edited pattern, CUE held."""
    return list(trk[2 * TRACK_SIZE:2 * TRACK_SIZE + 5])


def lane(trk):
    """T1's live page-2 values (0x80000810 + 0x32: what the frame builder sends)."""
    return list(trk[2 * TRACK_SIZE + 5:2 * TRACK_SIZE + 17])


def amp(part, t):
    """Track t's AMP page 1 in Part 1."""
    return list(part[0x11A + t * 24 + 6:0x11A + t * 24 + 12])


AMP0 = [0, 127, 127, 64, 64, 127]     # a fresh Part's T1 AMP: ATK HOLD REL VOL BAL XVOL's knob
A_ROW = {ATK: 10, HOLD: 117}          # LOCK_A
B_ROW = {ATK: 30, ATK + 2: 107}       # LOCK_B: ATK and REL
MID = lambda x, y: (x * 16512 + y * (32768 - 16512) + 0x4000) >> 15   # the crossfader at 64 (pot 128): weight 258 * 64


def arm_hits(log):
    """ARM ALL's entries: the date prompt's YES is one."""
    import re
    m = re.search(r"watch-pc\s*: (\d+) hit", log)
    return int(m.group(1)) if m else -1


def judge_new(res):
    """The commit and TRACKS."""
    U = 0xFF
    for tag in ("commit", "commit.mki"):
        if tag in res and res[tag][1]:
            sa, sb, a, row, step, trig = view(res[tag][1], res[tag][2])
            check(f"{tag}: SCENE A + YES: the Part takes A, ATK and HOLD leave scenes A and B, B's REL "
                  "stays",
                  a == [10, 117] + AMP0[2:] and row(sa)[12:15] == [U, U, U] and row(sb)[12:15] == [U, U, 107],
                  f"T1 AMP {a}, scene A {row(sa)[12:15]}, scene B {row(sb)[12:15]}")
    for n, both in (("active", False), ("all", True)):
        if n in res and res[n][1]:
            part = res[n][1]
            sa = part[0x10]
            r = lambda t: list(part[SCENES + sa * 0x100 + t * 32 + 12:SCENES + sa * 0x100 + t * 32 + 14])
            a1, a2 = amp(part, 0), amp(part, 1)
            ok = a1[:2] == [10, 117] and r(0) == [U, U] and (
                (a2[:2] == [10, 117] and r(1) == [U, U]) if both else (a2 == AMP0 and r(1) == [10, 117]))
            check(f"{n}: TRACKS {'ALL' if both else 'ACTIVE'}: SCENE A + YES on "
                  + ("T1 and T2" if both else "T1 only; T2 keeps its Part and its scene locks"), ok,
                  f"T1 AMP {a1[:2]} scene A {r(0)}; T2 AMP {a2[:2]} scene A {r(1)}")


def p2_view(part):
    """Part 1's page 2 of T1 and T2, and every scene's cells as {scene: {key: value}}."""
    p2 = lambda t: list(part[P2 + t * 30:P2 + t * 30 + 12])
    cells = {sc: {part[CELLS + sc * 0x100 + c * 0x20]: part[CELLS + sc * 0x100 + c * 0x20 + 1]
                  for c in range(8) if part[CELLS + sc * 0x100 + c * 0x20] < 0x80} for sc in range(16)}
    return p2(0), p2(1), cells


def judge_p2(res):
    """Page 2 (SCENES P2): apply and commit, TRACKS, the blend and the saved blend."""
    applied = P2_0[:4] + [1, 20] + P2_0[6:8] + [30] + P2_0[9:]
    seeded = {sc: {k: v for (s2, c), (k, v) in P2_CELLS.items() if s2 == sc} for sc in (0, 8, 3)}
    for tag in ("p2commit", "p2commit.mki"):
        if tag in res and res[tag][1]:
            t1, t2, cells = p2_view(res[tag][1])
            check(f"{tag}: SCENE A + YES: T1's page 2 takes A's FX1 E and F and FX2 C; those leave "
                  "scenes A and B, T2's lock and scene 4's stay",
                  t1 == applied and t2 == P2_0 and cells[0] == {0x12: 40} and cells[8] == {} and cells[3] == seeded[3],
                  f"T1 page 2 {t1}, T2 {t2}, scene A {cells[0]}, B {cells[8]}, scene 4 {cells[3]}")
            lv = lane(res[tag][2])
            check(f"{tag}: T1's live page 2 (the lane the frame builder reads) is the applied values", lv == applied,
                  f"lane {lv}")
    if "p2all" in res and res["p2all"][1]:
        t1, t2, cells = p2_view(res["p2all"][1])
        check("p2all: TRACKS ALL: T2's FX2 C takes scene A's 40 too, and its lock leaves A",
              t1 == applied and t2 == P2_0[:8] + [40] + P2_0[9:] and cells[0] == {} and cells[8] == {},
              f"T1 {t1}, T2 {t2}, scene A {cells[0]}, B {cells[8]}")
    # the fader at 64: wA = 258 * 64 = 16512, the B side 32768 - wA (SCENES P2's frame pass); E snaps to A
    blend = P2_0[:4] + [1, MID(20, P2_0[5])] + P2_0[6:8] + [MID(30, 100)] + P2_0[9:]
    if "p2blend" in res and res["p2blend"][1]:
        t1, t2, cells = p2_view(res["p2blend"][1])
        check("p2blend: A + B + YES at the middle: FX2 C and FX1 F the frame pass's blend, the select E "
              "snapped to A, T2 unchanged; T1's locks leave A and B, T2's and scene 4's stay",
              t1 == blend and t2 == P2_0 and cells[0] == {0x12: 40} and cells[8] == {} and cells[3] == seeded[3],
              f"T1 {t1}, want {blend}; T2 {t2}; scene A {cells[0]}, B {cells[8]}")
    if "p2savek" in res and res["p2savek"][1]:
        t1, t2, cells = p2_view(res["p2savek"][1])
        want = {0x0D: MID(20, P2_0[5]), 0x02: MID(30, 100), 0x0C: 1, 0x12: MID(40, P2_0[8])}
        check("p2savek: A + B + trig 5: scene 5 holds the blend of every page-2 lock in A or B, both tracks; "
              "the Part unchanged", cells[4] == want and t1 == P2_0, f"scene 5 {cells[4]}, want {want}; T1 {t1}")
    if "p2panel" in res and res["p2panel"][1]:
        t1, t2, cells = p2_view(res["p2panel"][1])
        check("p2panel: FX2 SETUP, SCENE A + knob C (SCENES P2's lock, the Part untouched), then SCENE A + YES: "
              "T1's FX2 C takes the turned-down lock, and the lock leaves scene A",
              t1[8] < P2_0[8] and 0x02 not in cells[0], f"scene A {cells[0]}, T1 FX2 page 2 {t1[6:]}")


def judge(res):
    judge_new(res)
    judge_p2(res)
    if "midi" in res and "nothing" in res:
        h, h0 = arm_hits(res["midi"][3]), arm_hits(res["nothing"][3])
        check("midi: SCENE A + YES in MIDI mode is stock's (ARM ALL reached)", h >= 3 and h0 == 1,
              f"ARM ALL entries: MIDI mode {h}, audio {h0}")
    if "kits" in res and res["kits"][1]:
        rc, parts, trk, log = res["kits"]
        p1, p2, ui, up = misc(trk)[:4]
        new, old = view(parts, trk, ui & 3), view(parts, trk, p1 & 3)
        check("kits: PTN+FUNC+RIGHT, then SCENE A + YES: the new pattern's Part takes scene A, pattern 1's does not",
              up == 1 and ui == p2 and p1 != p2 and new[2][:2] == [10, 117] and old[2] == AMP0,
              f"patterns' Parts {p1 + 1}/{p2 + 1}, edited Part {ui + 1} pattern {up + 1}; new {new[2]}, old {old[2]}")
    if "live" in res and res["live"][1]:
        sa, sb, a, row, step, trig = view(res["live"][1], res["live"][2])
        locks = [step(s)[12] for s in range(16)]
        check("live: LIVE RECORDING with the pattern playing, SCENE A + YES does nothing: the Part, the step locks "
              "and scene A's locks are as they were",
              a == AMP0 and locks == [0xFF] * 16 and row(sa)[12:14] == [10, 117],
              f"T1 AMP {a}, ATK step locks {locks}, scene A {row(sa)[12:15]}")
    if "undo" in res and "undoknob" in res and res["undo"][1] and res["undoknob"][1]:
        u, k = view(res["undo"][1], res["undo"][2])[2], view(res["undoknob"][1], res["undoknob"][2])[2]
        check("undo: FUNC + CUE treats an applied scene as it treats the same values turned on the knobs", u == k,
              f"T1 AMP after FUNC + CUE: applied {u}, turned {k}")
    if "pass" in res and "applyA" in res:
        h, h2 = arm_hits(res["pass"][3]), arm_hits(res["applyA"][3])
        check("YES alone reaches stock's ARM ALL; SCENE + YES does not", h >= h2 + 2 and h2 == 1,
              f"ARM ALL entries: YES alone {h}, SCENE A + YES {h2} (1 is the date prompt)")
    def get(n):
        rc, part, trk, log = res[n]
        return view(part, trk) if part else None
    want_blend = [MID(A_ROW[ATK], B_ROW[ATK]), MID(A_ROW[HOLD], AMP0[1]), MID(AMP0[2], B_ROW[ATK + 2])]
    for n, test in (
        ("pass", lambda v: (v[0] == 2, f"scene A {v[0] + 1} (SCENE A + trig 3)")),
        ("applyA", lambda v: (v[2] == [10, 117] + AMP0[2:], f"T1 AMP {v[2]}")),
        ("applyB", lambda v: (v[2] == [30, 127, 107] + AMP0[3:], f"T1 AMP {v[2]}")),
        ("blend", lambda v: (v[2][:3] == want_blend and v[2][3:] == AMP0[3:], f"T1 AMP {v[2]}, want {want_blend}")),
        ("nothing", lambda v: (v[2] == AMP0, f"T1 AMP {v[2]}")),
        ("grid", lambda v: (v[4](2)[12:14] == [10, 117] and v[4](2)[14] == 0xff and v[3] and v[5](2) and v[2] == AMP0,
                            f"step 3 AMP locks {v[4](2)[12:18]}, trig {v[5](2)}, Part {v[2]}")),
        ("gridab", lambda v: (v[4](2)[12:15] == want_blend and v[5](2) and v[2] == AMP0,
                              f"step 3 AMP locks {v[4](2)[12:18]}, want {want_blend}")),
        ("savek", lambda v: (v[3](4)[12:15] == want_blend and v[3](4)[:12] == [0xff] * 12 and v[3](4)[17] == 0xff
                             and (v[0], v[1]) == (0, 8) and v[2] == AMP0, f"scene 5 T1 {v[3](4)[:18]}, A/B {v[0]}/{v[1]}")),
        ("midi", lambda v: (v[2] == AMP0, f"T1 AMP {v[2]}")),
    ):
        for tag in (n, f"{n}.mki"):
            if tag in res:
                v = get(tag)
                if v is None:
                    continue
                ok, detail = test(v)
                check(f"{tag}: {CHECKS[n]}", ok, detail)


CHECKS = {
    "pass": "SCENE A + trig 3 is stock's assign; YES alone stock's ARM ALL",
    "applyA": "SCENE A + YES: T1's ATK and HOLD are scene A's, the rest stock",
    "applyB": "SCENE B + YES: T1's ATK and REL are scene B's, HOLD unchanged",
    "blend": "both + YES, crossfader in the middle: the blend (an unlocked side is the Part's own)",
    "nothing": "SCENE A + YES with no lock: the Part unchanged",
    "grid": "GRID RECORDING, trig 3 held, SCENE A: step 3 locks ATK and HOLD, the trig kept, the Part unchanged",
    "gridab": "the same with both scene keys: the blend as step locks",
    "savek": "SCENE A + SCENE B + trig 5: scene 5 holds the blend of every flat locked in A or B",
    "midi": "SCENE A + YES in MIDI mode: the Part unchanged",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="")
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--card", default="")
    ap.add_argument("--case", action="append", default=[])
    ap.add_argument("--no-mki", dest="mki", action="store_false")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print("APPLY SCENE: the scene keys' gestures (port)")
    if symbol("aps_yes") is None:
        print(f"  [SKIP] verify_apply_scene: {a.remix or 'this image'} has no APPLY SCENE")
        return 0
    if not a.card:
        a.card = fixture(a.image)
    names = a.case or list(CASES)
    res = {r[0]: r[1:] for r in ex_map(a, names)}
    if a.mki:
        res.update({r[0]: r[1:] for r in ex_map(a, [n for n in ("applyA", "grid", "savek", "commit", "p2commit")
                                                    if n in names], mkii=False)})
    for n, (rc, part, trk, log) in res.items():
        check(f"{n}: the port ran its script and dumped", rc == 0 and bool(part) and "ended on quit" in log, f"exit {rc}")
    judge(res)
    print(f"{len(FAILS)} FAILED" if FAILS else "verify_apply_scene: OK")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
