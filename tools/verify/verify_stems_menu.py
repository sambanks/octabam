#!/usr/bin/env python3
"""STEMS in MAIN MENU, key by key under the port, on both panels.

    python3 tools/verify/verify_stems_menu.py [remix]      (default: stems)

Builds the remix and the fixtures (STEMS_TEMPLATE), then boots the image
twice under `ot_emu --interactive` on a copy of the one-track fixture card:
as an MKII (MAIN MENU = PROJ) and as an MKI (FUNC+MIXER). Each boot:
- the cursor walks the five categories, STEMS fifth;
- SYSTEM opens and the cursor reaches OS UPGRADE, the recovery path; ENTER
  is never pressed there;
- STEMS opens on REC; DOWN lands on T1 and UP on REC, the status row
  skipped both ways; DOWN reaches T8 and stays there: PEAK, the last row,
  is never reached (a row with action 0 is skipped one at a time and never
  moved onto at the end, STEM_REC.md 16.1);
- every track row turned off in turn leaves T8 on (the last track stays);
  T3 off, then every other track on again;
- REC arms (CANCEL, ARMED) and cancels (REC, READY), then arms;
- with the menu closed, PLAY; the menu reopened on STEMS shows STOP and
  REC mm:ss, and a key later the seconds have moved on (the menu redraws
  on keys only, STEM_REC.md 16.1); T3 is locked;
- with the menu closed, STOP; the take ends DONE, and its folder holds
  seven files, T3's missing;
- every text the module can show, drawn in the status row, ends left of
  the pane's clip edge, and STEMS left of the root column's.
The keys, as measured (STEM_REC.md 16.1): YES enters a list, LEFT goes
back to the root, NO closes the whole menu; LEFT then RIGHT redraws the
menu and keeps the list's cursor. A PNG of the screen at each step goes to
out/stems_runs/menu-<model>-*.png. Pass or fail comes from memory, never
from a picture.

What it cannot see: the unit's key timing, its card speed while the menu
is open, and the MKII's hardware (flash A)."""
import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_stems as vs  # noqa: E402
from stems_panel import MENU_FOCUS, MenuPort, diff_box  # noqa: E402

ROOT_DESC, SYSTEM_DESC, SEL = 0x400cbd8c, 0x400cbd1c, 0x0c
OS_UPGRADE = 1                  # SYSTEM's row 1 (MAINMENU.md 2)
ENTER, BACK, CLOSE = "yes", "left", "no"
WORK = pathlib.Path("out/stems_runs")
ERRS = ["RING FULL", "PATH FAILED", "OPEN FAILED", "SAME MINUTE", "WRITE FAILED",
        "SEEK FAILED", "CLOSE FAILED", "TASK FAILED"]
TEXTS = (["REC", "CANCEL", "STOP", "SAVING", "READY", "ARMED", "NO CARD", "PEAK 0%", "PEAK 100%",
          "REC 60:00", "DONE 60:00"] + ERRS + [f"T{k} [{m}]" for k in range(1, 9) for m in "X "])


def texts(p, s):
    return [p.cstr(p.long(s["stems_rows"] + vs.ROW_LEN * k)) for k in range(vs.MENU_ROWS)]


def redraw(p):
    """LEFT then RIGHT: to the root and back into the list, which redraws
    the menu and keeps the list's cursor (the menu redraws on keys only)."""
    p.press(BACK)
    p.press("right")


def box_of(p, label_at, scratch, text):
    p.poke(scratch, text.encode("latin1") + b"\0")
    p.poke(label_at, scratch.to_bytes(4, "big"))
    p.run(300)
    redraw(p)
    return p.screen()


def widths(p, s, model):
    """Every text in the status row, and STEMS in the root column, against
    24 Ws: each must end left of the clip edge. The label pointers are put
    back after. The focus is in the STEMS list, its cursor on REC."""
    scratch = s["stems_fpath"]
    for label_at, pane, items in ((s["stems_rows"] + vs.ROW_LEN, "the list pane", TEXTS),
                                  (p.long(ROOT_DESC + 0x18) + vs.ROW_LEN * 4, "the root column", ["STEMS"])):
        keep = p.long(label_at)
        empty = box_of(p, label_at, scratch, "")
        clip = diff_box(empty, box_of(p, label_at, scratch, "W" * 24))
        over = []
        for t in items:
            b = diff_box(empty, box_of(p, label_at, scratch, t))
            if clip is None or b is None or b[1] >= clip[1]:
                over.append((t, b[1] if b else None))
        p.poke(label_at, keep.to_bytes(4, "big"))
        redraw(p)
        vs.check(f"{model}: every text ends inside {pane}", clip is not None and not over,
                 f"clip {clip[1] if clip else None}, over {over}")


def walk(model, s, fx):
    card = WORK / f"menu-{model}.img"
    shutil.copyfile(fx["card"], card)
    lst = s["stems_list"]
    with MenuPort(vs.IMAGE, card, fx["set"], fx["project"], model == "mkii",
                  log_path=WORK / f"menu-{model}.log") as p:
        def shot(name):
            p.png(WORK / f"menu-{model}-{name}.png")

        def sel(desc):
            return p.long(desc + SEL)

        p.settle()
        p.open_menu()
        shot("root")
        seen = [sel(ROOT_DESC)]
        for _ in range(4):
            p.press("down")
            seen.append(sel(ROOT_DESC))
        shot("stems")
        vs.check(f"{model}: MAIN MENU opens on the root and the cursor walks five categories",
                 p.long(MENU_FOCUS) == ROOT_DESC and seen == [0, 1, 2, 3, 4], f"{seen}")
        for _ in range(3):
            p.press("up")                               # SYSTEM
        p.press(ENTER)
        p.press("down")
        shot("os-upgrade")
        vs.check(f"{model}: SYSTEM opens and the cursor reaches OS UPGRADE",
                 p.long(MENU_FOCUS) == SYSTEM_DESC and sel(SYSTEM_DESC) == OS_UPGRADE,
                 f"focus {p.long(MENU_FOCUS):#x}, selection {sel(SYSTEM_DESC)}")
        p.press(BACK)                                   # the root, SYSTEM selected
        for _ in range(3):
            p.press("down")                             # STEMS
        p.press(ENTER)
        vs.check(f"{model}: STEMS opens on REC", p.long(MENU_FOCUS) == lst and sel(lst) == 0,
                 f"focus {p.long(MENU_FOCUS):#x}, selection {sel(lst)}")
        p.press("down")
        down = sel(lst)
        p.press("up")
        up = sel(lst)
        vs.check(f"{model}: DOWN from REC lands on T1 and UP from T1 on REC", (down, up) == (vs.ROW_TRK0, 0),
                 f"{(down, up)}")
        walked = []
        for _ in range(9):
            p.press("down")
            walked.append(sel(lst))
        shot("t8")
        t8 = vs.ROW_TRK0 + 7
        vs.check(f"{model}: DOWN reaches T8 and stays there, never on the PEAK row",
                 walked == list(range(vs.ROW_TRK0, t8 + 1)) + [t8], f"{walked}")
        for _ in range(7):
            p.press("up")                               # T8 -> T1
        for k in range(8):                              # every track off in turn, T1 to T8
            p.press(ENTER)
            if k < 7:
                p.press("down")                         # no DOWN past T8: it might wrap
        left = p.long(s["stems_tracks"]) & 0xFF
        vs.check(f"{model}: turning every track off leaves the last one on", left == 0x80, f"mask {left:#04x}")
        shot("tracks-off")
        for _ in range(7):
            p.press("up")                               # T8 -> T1; then T1 .. T7 on again, T3 stays off
        for k in range(7):
            if k != 2:
                p.press(ENTER)
            p.press("down")
        t = texts(p, s)
        mask = p.long(s["stems_tracks"]) & 0xFF
        trows = t[vs.ROW_TRK0:vs.ROW_TRK0 + 8]
        vs.check(f"{model}: T3 off, every other track on, the rows say so",
                 mask == 0xFB and trows == [f"T{k} [{' ' if k == 3 else 'X'}]" for k in range(1, 9)],
                 f"mask {mask:#04x}, {trows}")
        for _ in range(8):
            p.press("up")                               # T8 -> T1, then REC
        p.press(ENTER)
        a = texts(p, s)[:2] + [p.long(s["stems_state"])]
        p.press(ENTER)
        c = texts(p, s)[:2] + [p.long(s["stems_state"])]
        p.press(ENTER)
        shot("armed")
        vs.check(f"{model}: REC arms and cancels", a == ["CANCEL", "ARMED", vs.ST_ARMED]
                 and c == ["REC", "READY", vs.ST_IDLE] and p.long(s["stems_state"]) == vs.ST_ARMED,
                 f"{a}, {c}")
        p.press(CLOSE)                                  # NO in a list closes the menu
        p.press("play", settle=1500)
        p.open_menu()
        t0 = texts(p, s)
        before = p.screen()
        shot("recording")
        p.run(2500)
        redraw(p)
        t1 = texts(p, s)
        after = p.screen()
        shot("recording-later")
        vs.check(f"{model}: reopened on STEMS: STOP and REC mm:ss, and a key later the seconds moved on",
                 p.long(MENU_FOCUS) == lst and t0[0] == "STOP" and t0[1].startswith("REC ")
                 and t1[1].startswith("REC ") and t1[1] > t0[1] and diff_box(before, after) is not None,
                 f"{t0[:2]} -> {t1[:2]}")
        for _ in range(3):
            p.press("down")                             # REC -> T1 -> T2 -> T3
        p.press(ENTER)
        vs.check(f"{model}: T3 is locked while it records",
                 p.long(s["stems_tracks"]) & 0xFF == 0xFB and texts(p, s)[vs.ROW_TRK0 + 2] == "T3 [ ]")
        p.press(CLOSE)
        p.press("stop", settle=500)
        for _ in range(60):
            if p.long(s["stems_state"]) == vs.ST_IDLE:
                break
            p.run(500)
        p.open_menu()
        t = texts(p, s)
        shot("done")
        vs.check(f"{model}: after STOP: IDLE, REC and DONE mm:ss",
                 p.long(s["stems_state"]) == vs.ST_IDLE and t[0] == "REC" and t[1].startswith("DONE "),
                 f"state {p.long(s['stems_state'])}, {t[:3]}")
        for _ in range(3):
            p.press("up")                               # T3 -> T2 -> T1 -> REC, rows 0-6 showing
        widths(p, s, model)
        p.card_flush()
    names = [n.upper() for n, _ in vs.take_files(str(card))]
    vs.check(f"{model}: the take holds seven files, T3's missing",
             names == [f"T{k}.WAV" for k in (1, 2, 4, 5, 6, 7, 8)], f"{names}")


def main():
    from remix import registry
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    name = args[0] if args else "stems"
    if "STEM REC" not in registry.remix(name).modules:
        print(f"  [ -- ] {name} does not carry STEM REC -- nothing to check")
        return 0
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], capture_output=True, text=True, env=env)
    if r.returncode:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    if not vs.EMU.exists():
        print("  [SKIP] the menu under the port: build the port (make emu-cf)")
        return 0
    if not vs.TEMPLATE.is_dir():
        print(f"  [SKIP] the menu under the port: no project template at {vs.TEMPLATE} (STEMS_TEMPLATE=<dir>)")
        return 0
    if not vs.fixtures():
        return 1
    s = vs.syms()
    fx = json.loads(vs.FIXTURE.read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    for model in ("mkii", "mki"):
        walk(model, s, fx)
    return 1 if vs.fails else 0


if __name__ == "__main__":
    sys.exit(main())
