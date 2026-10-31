#!/usr/bin/env python3
"""STEMS via UP+REC, key by key under the port, on both panels.

    python3 tools/verify/verify_stems_menu.py [remix]      (default: stems)

Builds the remix and the fixtures (STEMS_TEMPLATE), then boots the image
under `ot_emu --interactive` on a copy of the one-track fixture card, as an
MKII (MAIN MENU = PROJ) and as an MKI (FUNC+MIXER). Each panel's walk:
- the cursor walks the stock root categories (four, or five with BRAIN);
  STEMS is not among them; PROJECT's row count stays 15;
- SYSTEM opens and the cursor reaches OS UPGRADE, the recovery path; ENTER
  is never pressed there;
- UP+REC opens STEMS as its own WCREATE window (stems_win) on STEM REC,
  not MAIN MENU; NO closes it; UP+REC again toggles it closed;
- DOWN skips PEAK onto T1 and UP comes back; DOWN reaches 24 BIT and stays,
  the pane scrolled to its last five rows;
- at boot T1 alone is on, at 24 bits, and stays on; T2 to T8 turn on;
- every track row turned off in turn leaves T8 on; with MAIN on, T8 can go
  off and MAIN can't; 24 BIT flips, then goes off for the take; on AB,
  RIGHT picks STEREO and YES
  splits the pair, LEFT picks B and YES leaves it out, so A records alone;
  T3 off, then every other track on again; each checkbox says so;
- every STEMS text fits its column, by the firmware font's own widths;
- STEM REC arms (ARMED) and cancels (READY), then arms;
- with STEMS closed, PLAY; UP+REC shows the take's time, and a key later
  the seconds have moved on; T3 is locked;
- with STEMS closed, STOP; the take ends DONE, and its folder holds seven
  tracks, MAIN and A, T3's and B's missing.
A PNG of the screen at each step goes to out/stems_runs/menu-<model>-*.png.
Pass or fail comes from memory, never from a picture, except in the
third boot below, whose pictures are the point.

A second boot per panel (note 4) taps YES on the main page: twice within
0.5 s arms STEM REC, or starts it while playing; once, or twice 1 s apart,
does not; a double tap never stops a take; with T1 held, or inside MAIN
MENU (CONTROL, then AUDIO), YES stays stock's.

A third boot, on the MKII (both panels draw the same LCD from the same
code), compares STEMS with what it must look like, pixel for pixel: the
look Yves chose on 27 Oct 2026, stock SYSTEM > PERSONALIZE drawn by the
firmware with STEMS's rows in place (stems_reference.py). Opened, scrolled
to the bottom, a pair's STEREO picked and split, its B picked and left
out, both pairs in mono, and recording.

Since 27 Oct 2026 (note 2) it also compares the screen with a fresh redraw
from the rows in memory: opened during a take, and after 3,000 frames with
no key, the window must already show them; closed, it must never draw.

What it cannot see: the unit's key timing, how often the unit's UI task
gets a message (the redraw's rate), its card speed while STEMS is open,
and the MKII's hardware (flash A)."""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_stems as vs  # noqa: E402
from stems_panel import MENU_FOCUS, MenuPort, diff_box  # noqa: E402
from stems_reference import BOX_OFF, BOX_ON, LIST, Font, Reference  # noqa: E402

ROOT_DESC, PROJECT_DESC, SYSTEM_DESC, SEL = 0x400cbd8c, 0x400cbcac, 0x400cbd1c, 0x0c
MENU_STATE, MENU_PAGES, PERSONALIZE_DRAW = 0x400cbf40, 0x400cbdb4, 0x40068e00   # MAIN MENU's page, 20 B each
CARD_MOUNTED = 0x460d1cb8       # stems.s: long, 0 = no card
ARM_HELD = 0x46c7ff64           # the stock arm word while YES is held: 0xffff ARM ALL; with a track key held, the
                                # track's bit (ARM TRK), or bit 8 + track (ARM REC TRK) while 0x460d5db4 = 3
                                # (MAINMENU.md 6); the release clears it
OS_UPGRADE = 1                  # SYSTEM's row 1 (MAINMENU.md 2)
PROJECT_N = 15                  # stock PROJECT row count (unchanged)
ENTER, CLOSE = "yes", "no"
WORK = pathlib.Path("out/stems_runs")
ROW_AB, ROW_CD, ROW_B24 = 12, 13, 14
ERRS = ["RING FULL", "PATH FAILED", "OPEN FAILED", "SAME MINUTE", "WRITE FAILED",
        "SEEK FAILED", "CLOSE FAILED", "TASK FAILED"]
LABELS = ["STEM REC", "PEAK"] + [f"T{k}" for k in range(1, 9)] + ["MAIN", "CUE", "AB", "CD", "24 BIT"] + ERRS
VALUES = ["READY", "ARMED", "SAVING", "DONE", "NO CARD", "MASTER", "60:00", "100%", BOX_ON, BOX_OFF]
TIME = re.compile(r"\d\d:\d\d$")


def rows(p, s):
    """Each row's (label, value) in memory; a pair row's value is None (its
    fields are drawn from stems_tracks and stems_fmt)."""
    out = []
    for k in range(vs.MENU_ROWS):
        a = s["stems_rows"] + vs.ROW_LEN * k
        v = p.long(a + 4)
        out.append((p.cstr(p.long(a)), p.cstr(v) if v else None))
    return out


def redraw(p):
    """Force a STEMS window redraw: DOWN then UP keeps STEM REC selected."""
    p.press("down", settle=80)
    p.press("up", settle=80)


def stems_open(p, s):
    return p.long(s["stems_win"]) != 0 and p.long(s["stems_live"]) != 0


def window(scr, cols):
    """The screen with everything outside STEMS' window blanked, still 128
    by 64 (diff_box's size): the main page around it moves while the
    sequencer plays."""
    return [[v if x in cols else 0 for x, v in enumerate(row)] for row in scr]


def shows_labels(p, s, cols, tries=3):
    """Does the window show the rows in memory now? It is compared with
    what a redraw draws from them (DOWN then UP, STEM REC selected), inside
    the window. A row that changes during the redraw (the take's clock)
    makes a try void; after `tries` void tries the answer is None."""
    for _ in range(tries):
        t_a, scr_a = rows(p, s), window(p.screen(), cols)
        redraw(p)
        t_b, scr_b = rows(p, s), window(p.screen(), cols)
        if t_a == t_b:
            return diff_box(scr_a, scr_b) is None
    return None


def sel(p, desc):
    return p.long(desc + SEL)


def value(p, s, row):
    return rows(p, s)[row][1]


def widths(p, model):
    """Every STEMS text fits its column, by the firmware font's own rule
    (0x40012f30 over its tables, stems_reference.Font): a label from 4 to
    76, before the value column; a value from 77 to 106, inside the bar
    (3 to 107). Computed, not drawn: the third boot draws the rows it shows."""
    f = Font(p)
    over = [(t, f.width(t)) for t in LABELS if 4 + f.width(t) > 77] \
        + [(t, f.width(t)) for t in VALUES if 77 + f.width(t) > 107]
    vs.check(f"{model}: every STEMS label fits before the value column, every value inside the bar",
             not over, f"over {over}")


def enter_stems(p, s, model):
    """UP + REC: open STEMS window on STEM REC."""
    p.chord("up", "rec", settle=400)
    lst = s["stems_list"]
    vs.check(f"{model}: STEMS opens on STEM REC",
             stems_open(p, s) and sel(p, lst) == 0
             and p.long(lst + 0x18) == s["stems_rows"]
             and p.long(PROJECT_DESC) == PROJECT_N,
             f"win {p.long(s['stems_win']):#x}, selection {sel(p, lst)}, "
             f"rows {p.long(lst + 0x18):#x}, live {p.long(s['stems_live'])}, "
             f"project {p.long(PROJECT_DESC)}")


def reopen_stems(p, s, model):
    """After NO / close: UP + REC opens STEMS again on STEM REC."""
    lst = s["stems_list"]
    if stems_open(p, s) and sel(p, lst) == 0 and p.long(lst + 0x18) == s["stems_rows"]:
        return
    p.chord("up", "rec", settle=400)
    vs.check(f"{model}: STEMS reopens on STEM REC",
             stems_open(p, s) and sel(p, lst) == 0
             and p.long(lst + 0x18) == s["stems_rows"],
             f"win {p.long(s['stems_win']):#x}, selection {sel(p, lst)}, "
             f"rows {p.long(lst + 0x18):#x}")


def footprint(p, s):
    """The columns STEMS' window covers: where opening it changes the main
    page's screen, sequencer stopped (UP+REC, then NO)."""
    base = p.screen()
    p.chord("up", "rec", settle=400)
    box = diff_box(base, p.screen())
    p.press(CLOSE, settle=200)
    return range(box[0], box[1] + 1) if box else range(128)


def walk(model, s, fx):
    card = WORK / f"menu-{model}.img"
    shutil.copyfile(fx["card"], card)
    with MenuPort(vs.IMAGE, card, fx["set"], fx["project"], model == "mkii",
                  log_path=WORK / f"menu-{model}.log") as p:
        def shot(name):
            p.png(WORK / f"menu-{model}-{name}.png")

        p.settle()
        cols = footprint(p, s)
        p.open_menu()
        shot("root")
        root_n = p.long(ROOT_DESC)
        seen = [sel(p, ROOT_DESC)]
        for _ in range(root_n - 1):
            p.press("down")
            seen.append(sel(p, ROOT_DESC))
        shot("root-last")
        vs.check(f"{model}: MAIN MENU opens on the root and the cursor walks {root_n} categories",
                 p.long(MENU_FOCUS) == ROOT_DESC and seen == list(range(root_n)), f"{seen}")
        vs.check(f"{model}: PROJECT stays stock ({PROJECT_N} rows)",
                 p.long(PROJECT_DESC) == PROJECT_N, f"count {p.long(PROJECT_DESC)}")
        # SYSTEM is always root selection 1 (PROJECT=0, SYSTEM=1, ...).
        while sel(p, ROOT_DESC) != 1:
            p.press("up")
        p.press(ENTER)
        p.press("down")
        shot("os-upgrade")
        vs.check(f"{model}: SYSTEM opens and the cursor reaches OS UPGRADE",
                 p.long(MENU_FOCUS) == SYSTEM_DESC and sel(p, SYSTEM_DESC) == OS_UPGRADE,
                 f"focus {p.long(MENU_FOCUS):#x}, selection {sel(p, SYSTEM_DESC)}")
        p.press(CLOSE, settle=100)                      # leave MAIN MENU

        enter_stems(p, s, model)
        shot("stems")
        vs.check(f"{model}: STEMS is its own window (MAIN MENU focus stays off stems_list)",
                 p.long(MENU_FOCUS) != s["stems_list"],
                 f"focus {p.long(MENU_FOCUS):#x}")
        lst = s["stems_list"]
        p.press("down")
        down = sel(p, lst)
        p.press("up")
        up = sel(p, lst)
        vs.check(f"{model}: DOWN from STEM REC skips PEAK onto T1, and UP comes back", (down, up) == (vs.ROW_TRK0, 0),
                 f"{(down, up)}")
        walked = []
        for _ in range(14):
            p.press("down")
            walked.append(sel(p, lst))
        shot("last")
        top = p.long(lst + 0x04)
        vs.check(f"{model}: DOWN reaches 24 BIT and stays there, the pane on the last five rows",
                 walked == list(range(vs.ROW_TRK0, ROW_B24 + 1)) + [ROW_B24] and top == vs.MENU_ROWS - vs.MENU_VISIBLE,
                 f"{walked}, top {top}")
        for _ in range(ROW_B24 - vs.ROW_TRK0):
            p.press("up")                               # back to T1
        p.press(ENTER)                                  # T1 off: refused, the only source at boot
        alone = (p.long(s["stems_tracks"]), p.long(s["stems_fmt"]) & 7, value(p, s, vs.ROW_TRK0))
        for _ in range(7):
            p.press("down")
            p.press(ENTER)                              # T2 to T8 on
        vs.check(f"{model}: at boot T1 alone records, at 24 bits, and stays on; T2 to T8 turn on",
                 alone == (0x01, 0b111, BOX_ON) and p.long(s["stems_tracks"]) & 0xFFF == 0xFF,
                 f"boot {alone}, then {p.long(s['stems_tracks']):#05x}")
        for _ in range(7):
            p.press("up")                               # back to T1
        for k in range(8):                              # every track off in turn, T1 to T8
            p.press(ENTER)
            if k < 7:
                p.press("down")
        left = p.long(s["stems_tracks"]) & 0xFF
        vs.check(f"{model}: turning every track off leaves the last one on", left == 0x80, f"mask {left:#04x}")
        p.press("down")                                 # T8 -> MAIN (row 10)
        p.press(ENTER)                                  # MAIN on
        p.press("up")                                   # T8
        p.press(ENTER)                                  # T8 off: MAIN keeps a source
        p.press("down")                                 # MAIN
        p.press(ENTER)                                  # MAIN off: refused, the last source
        left = p.long(s["stems_tracks"]) & 0xFFF
        vs.check(f"{model}: with MAIN on, T8 can go off, and the last source stays on",
                 left == 0x100 and value(p, s, 10) == BOX_ON and value(p, s, 9) == BOX_OFF,
                 f"sources {left:#05x}")
        p.press("up")                                   # T8
        p.press(ENTER)                                  # T8 on again; MAIN stays on for the take
        for _ in range(ROW_B24 - 9):
            p.press("down")                             # T8 (row 9) -> 24 BIT (row 14)
        p.press(ENTER)
        off24 = (p.long(s["stems_fmt"]) & 7, value(p, s, ROW_B24))
        p.press(ENTER)                                  # 24 BIT off, then on
        vs.check(f"{model}: 24 BIT flips and its checkbox says so",
                 off24 == (0b110, BOX_OFF) and (p.long(s["stems_fmt"]) & 7, value(p, s, ROW_B24)) == (0b111, BOX_ON),
                 f"{off24}, {p.long(s['stems_fmt']) & 7:03b}")
        # Off again: the take is at 16 bits. Its nine files are 544 bytes a
        # frame, near the port's card (about 454); at 24 bits, 816, the ring
        # filled 1% a redraw and every shows_labels try saw PEAK change
        # (measured 28 Oct 2026). The unit's card keeps up with either.
        p.press(ENTER)
        p.press("up")
        p.press("up")                                   # AB (row 12)
        p.press(ENTER)                                  # AB on
        p.press("right")                                # STEREO
        p.press(ENTER)                                  # off: A and B
        p.press("left")                                 # B
        p.press(ENTER)                                  # B left out: A alone
        shot("pairs")
        tr, fmt = p.long(s["stems_tracks"]), p.long(s["stems_fmt"]) & 7
        vs.check(f"{model}: on AB, RIGHT picks STEREO and YES splits it; LEFT picks B and YES leaves it out",
                 tr & 0xF400 == 0x2400 and fmt == 0b100 and p.long(s["stems_field"]) == 1,
                 f"sources {tr:#06x}, format {fmt:03b}, field {p.long(s['stems_field'])}")
        for _ in range(ROW_AB - 9):
            p.press("up")                               # AB (row 12) -> T8 (row 9)
        shot("tracks-off")
        for _ in range(7):
            p.press("up")                               # T8 -> T1
        for k in range(7):
            if k != 2:
                p.press(ENTER)
            p.press("down")
        r = rows(p, s)
        mask = p.long(s["stems_tracks"]) & 0xFF
        trows = r[vs.ROW_TRK0:vs.ROW_TRK0 + 8]
        vs.check(f"{model}: T3 off, every other track on, the checkboxes say so",
                 mask == 0xFB and trows == [(f"T{k}", BOX_OFF if k == 3 else BOX_ON) for k in range(1, 9)],
                 f"mask {mask:#04x}, {trows}")
        for _ in range(8):
            p.press("up")                               # T8 -> T1, then STEM REC

        widths(p, model)

        p.press(ENTER)
        a = rows(p, s)[0] + (p.long(s["stems_state"]),)
        p.press(ENTER)
        c = rows(p, s)[0] + (p.long(s["stems_state"]),)
        p.press(ENTER)
        shot("armed")
        vs.check(f"{model}: STEM REC arms and cancels", a == ("STEM REC", "ARMED", vs.ST_ARMED)
                 and c == ("STEM REC", "READY", vs.ST_IDLE) and p.long(s["stems_state"]) == vs.ST_ARMED,
                 f"{a}, {c}")

        p.press(CLOSE, settle=100)                      # NO closes the STEMS window
        vs.check(f"{model}: NO closes the STEMS window",
                 not stems_open(p, s),
                 f"win {p.long(s['stems_win']):#x}, live {p.long(s['stems_live'])}")

        enter_stems(p, s, model)
        p.chord("up", "rec", settle=400)                # UP+REC toggles closed
        vs.check(f"{model}: UP+REC toggles STEMS closed",
                 not stems_open(p, s),
                 f"win {p.long(s['stems_win']):#x}, live {p.long(s['stems_live'])}")

        p.press("play", settle=1500)
        reopen_stems(p, s, model)
        p.run(100, wall=5)                              # the task's next pass, then the UI task's next message
        t0 = rows(p, s)[0]
        shown = shows_labels(p, s, cols)
        vs.check(f"{model}: opened during a take, the window shows the take (STEM REC, mm:ss), no key",
                 shown is True and t0[0] == "STEM REC" and TIME.match(t0[1] or ""), f"{shown}, {t0}")
        t0 = rows(p, s)[0]
        before = p.screen()
        shot("recording")
        lgen0 = p.long(s["stems_lgen"])
        p.run(3000, wall=45)                            # no key, 3 s: the window redraws itself
        idle = p.screen()
        drawn, lgen1 = p.long(s["stems_drawn"]), p.long(s["stems_lgen"])
        vs.check(f"{model}: the window redraws itself while recording (no key in 3 s)",
                 lgen1 > lgen0 and lgen1 - drawn <= 1 and diff_box(window(before, cols), window(idle, cols)) is not None
                 and shows_labels(p, s, cols) is True,
                 f"rows written {lgen1 - lgen0} times, last drawn {drawn} of {lgen1}")
        p.run(2500, wall=30)
        redraw(p)
        t1 = rows(p, s)[0]
        after = p.screen()
        shot("recording-later")
        vs.check(f"{model}: reopened on STEMS: the take's time, and a key later the seconds moved on",
                 stems_open(p, s) and p.long(s["stems_list"] + 0x18) == s["stems_rows"]
                 and TIME.match(t0[1] or "") and TIME.match(t1[1] or "") and t1[1] > t0[1]
                 and diff_box(before, after) is not None,
                 f"{t0} -> {t1}")
        # Review Focus 4: TEMPO is a window of STEMS' class (5): it evicts STEMS,
        # which must come down through its close routine (stems_win 0), or the
        # UI task's redraw would draw into a destroyed window.
        p.press("tempo", settle=300)
        evicted = (p.long(s["stems_win"]), p.long(s["stems_live"]))
        p.run(3000, wall=45)                            # 3 s: the rows move on under TEMPO
        vs.check(f"{model}: TEMPO over STEMS closes it (stems_win 0), and the take runs on 3 s",
                 evicted == (0, 0) and p.long(s["stems_state"]) == vs.ST_RECORDING,
                 f"win {evicted[0]:#x}, live {evicted[1]}, state {p.long(s['stems_state'])}")
        p.press(CLOSE, settle=300)                      # TEMPO closes on NO
        reopen_stems(p, s, model)
        for _ in range(3):
            p.press("down")                             # STEM REC -> T1 -> T2 -> T3
        p.press(ENTER)
        vs.check(f"{model}: T3 is locked while it records",
                 p.long(s["stems_tracks"]) & 0xFF == 0xFB and value(p, s, vs.ROW_TRK0 + 2) == BOX_OFF)
        p.press(CLOSE, settle=100)
        vs.check(f"{model}: NO closes STEMS while recording",
                 not stems_open(p, s),
                 f"win {p.long(s['stems_win']):#x}")
        lgen0 = p.long(s["stems_lgen"])
        p.run(3000, wall=45)                            # 3 s: the rows move on with STEMS closed
        lgen1 = p.long(s["stems_lgen"])
        vs.check(f"{model}: closed with NO, STEMS stays closed (stems_win 0) while the rows move on 3 s",
                 lgen1 > lgen0 and not stems_open(p, s) and p.long(s["stems_state"]) == vs.ST_RECORDING,
                 f"rows written {lgen1 - lgen0} times, win {p.long(s['stems_win']):#x}")
        p.press("stop", settle=500)
        for _ in range(60):
            if p.long(s["stems_state"]) == vs.ST_IDLE:
                break
            p.run(500, wall=5)
        reopen_stems(p, s, model)
        t = rows(p, s)[0]
        shot("done")
        vs.check(f"{model}: after STOP: IDLE, STEM REC DONE",
                 p.long(s["stems_state"]) == vs.ST_IDLE and t == ("STEM REC", "DONE"),
                 f"state {p.long(s['stems_state'])}, {t}")
        p.card_flush()
    names = sorted(n.upper() for n, _ in vs.take_files(str(card)))
    want = sorted(["MAIN.WAV", "A.WAV"] + [f"T{k}.WAV" for k in (1, 2, 4, 5, 6, 7, 8)])
    vs.check(f"{model}: the take holds seven tracks, MAIN and A, T3's and B's missing", names == want, f"{names}")


def personalize(p):
    """MAIN MENU > SYSTEM > PERSONALIZE (SYSTEM's fourth row); True when
    PERSONALIZE is the page MAIN MENU draws."""
    p.open_menu()
    while sel(p, ROOT_DESC) != 1:
        p.press("down")
    p.press(ENTER, settle=200)
    for _ in range(3):
        p.press("down")
    p.press(ENTER, settle=400)
    return p.long(MENU_PAGES + 20 * p.long(MENU_STATE)) == PERSONALIZE_DRAW


def model_rows(tracks, fmt, rec=("STEM REC", "READY"), peak="0%", master=False):
    """The rows STEMS must show for a source word and a format, built from
    the bits as the design says, not read from STEMS."""
    box = lambda on: BOX_ON if on else BOX_OFF  # noqa: E731
    out = [("text",) + tuple(rec), ("text", "PEAK", peak)]
    out += [("text", f"T{k + 1}", "MASTER" if k == 7 and master else box(tracks >> k & 1)) for k in range(8)]
    out += [("text", "MAIN", box(tracks >> 8 & 1)), ("text", "CUE", box(tracks >> 9 & 1))]
    for pair, name in ((0, "AB"), (1, "CD")):
        stereo, on = bool(fmt >> (1 + pair) & 1), bool(tracks >> (10 + pair) & 1)
        left = tracks >> (12 + 2 * pair) & 3
        left = 0 if left == 3 else left
        ins = (on, on) if stereo else (on and not left & 1, on and not left & 2)
        out.append(("pair", name, stereo, ins))
    out.append(("text", "24 BIT", box(fmt & 1)))
    return out


def looks(s, fx):
    """STEMS against the firmware-drawn reference, on the MKII (third boot)."""
    model = "mkii"
    card = WORK / "menu-looks.img"
    shutil.copyfile(fx["card"], card)
    with MenuPort(vs.IMAGE, card, fx["set"], fx["project"], True, log_path=WORK / "menu-looks.log") as p:
        p.settle()
        ref = Reference(p, s)                           # before PERSONALIZE first draws
        icon = [p.long(s["stems_icon"] + 4 * i) for i in range(5)]
        cols = footprint(p, s)
        lst = s["stems_list"]

        def compare(name, want, field=None, in_window=False):
            """STEMS' screen now against PERSONALIZE drawn with `want` at
            STEMS' cursor and pane; STEMS is closed after and reopened on
            STEM REC."""
            mine = p.screen()
            p.png(WORK / f"looks-{name}-stems.png")
            row, top = sel(p, lst), p.long(lst + 0x04)
            p.press(CLOSE, settle=200)
            ref.load("STEMS", icon, want, row, field)
            page = personalize(p)
            ref.place(0, 0)                         # STEMS' rows, cursor on the first, then
            for _ in range(row):                    # DOWN as STEMS reached it (its pane follows)
                p.press("down", settle=60)
            if row == 0:
                p.press("down", settle=60)
                p.press("up", settle=60)
            p.run(150)
            theirs = p.screen()
            p.png(WORK / f"looks-{name}-reference.png")
            placed = (p.long(LIST), p.long(LIST + 8)) == (top, row)
            for _ in range(3):
                p.press(CLOSE, settle=200)
            a, b = (window(mine, cols), window(theirs, cols)) if in_window else (mine, theirs)
            box = diff_box(a, b)
            vs.check(f"{model}: STEMS {name} is drawn as the reference, pixel for pixel",
                     page and placed and box is None,
                     f"PERSONALIZE {page}, placed {placed}, differs in {box} (out/stems_runs/looks-{name}-*.png)")
            p.chord("up", "rec", settle=400)

        def keys(*names):
            for k in names:
                p.press(k, settle=100)

        tracks, fmt = 0x01, 0b111                       # the boot defaults: T1 alone at 24 bits
        p.chord("up", "rec", settle=400)
        compare("opened", model_rows(tracks, fmt))
        keys(*["down"] * 13)
        compare("scrolled", model_rows(tracks, fmt))
        keys(*["down"] * 11, ENTER, "right", ENTER)                         # AB on, STEREO off
        tracks, fmt = tracks | 0x400, 0b101
        vs.check(f"{model}: looks: AB on and split", (p.long(s["stems_tracks"]), p.long(s["stems_fmt"])) ==
                 (tracks, fmt), f"{p.long(s['stems_tracks']):#06x} {p.long(s['stems_fmt']):03b}")
        compare("split", model_rows(tracks, fmt), field="ST")
        keys(*["down"] * 11, "right", "right", "left", ENTER)               # back on AB: B left out
        tracks |= 0x2000
        compare("b-out", model_rows(tracks, fmt), field=1)
        keys(*["down"] * 12, ENTER, "right", ENTER)                         # CD on, split
        tracks, fmt = tracks | 0x800, 0b001
        compare("both-mono", model_rows(tracks, fmt), field="ST")
        p.press(ENTER, settle=200)                                          # STEM REC: armed
        p.press(CLOSE, settle=200)
        p.press("play", settle=1500)
        p.chord("up", "rec", settle=400)
        p.run(1500, wall=20)
        for _ in range(3):
            redraw(p)
            r = rows(p, s)
            if shows_labels(p, s, cols, tries=1) and rows(p, s) == r:
                break
        compare("recording", model_rows(tracks, fmt, rec=r[0], peak=r[1][1]), in_window=True)
        vs.check(f"{model}: looks: recording shows STEM REC and the take's time",
                 r[0][0] == "STEM REC" and TIME.match(r[0][1] or "") is not None, f"{r[0]}")
        p.press(CLOSE, settle=200)
        p.press("stop", settle=500)
        for _ in range(60):
            if p.long(s["stems_state"]) == vs.ST_IDLE:
                break
            p.run(500, wall=5)


def taps(p, gap_ms):
    """Two YES presses on the main page, the second `gap_ms` after the first
    starts (a press is held 40 ms), then 300 ms for the handler and the hook.
    First 600 ms with no key, so a press before this pair can't make its
    first press a second tap (27 Oct 2026: the pair after the 1 s pair
    started 340 ms after it, armed on its first press, and its second
    press's ARM ALL covered STEMS ARMED)."""
    p.run(600)
    p.press("yes", hold=40, settle=gap_ms - 40)
    return yes_held(p)


def yes_held(p):
    """One YES press (held 40 ms, then 300 ms), and the stock arm word read
    while it is held: ARM_HELD is set on the press and cleared on the
    release (MAINMENU.md 6), where the other arm word is a request the frame
    interrupt applies and clears within a frame (0x4000ac44)."""
    p.key("yes", True)
    p.run(40)
    word = int.from_bytes(p.peek(ARM_HELD, 2), "big")
    p.key("yes", False)
    p.run(300)
    return word


def double_tap(model, s, fx):
    """Note 4 of 26 Oct 2026, on its own boot: on the main page, a second
    YES within 0.5 s arms STEM REC (or starts it while playing); one YES,
    or two 1 s apart, does not; a double tap never stops a take; with a
    track key held, or inside MAIN MENU, YES stays stock's."""
    card = WORK / f"menu-{model}-yes.img"
    shutil.copyfile(fx["card"], card)
    st = lambda: p.long(s["stems_state"])               # noqa: E731
    with MenuPort(vs.IMAGE, card, fx["set"], fx["project"], model == "mkii",
                  log_path=WORK / f"menu-{model}-yes.log") as p:
        p.settle()
        # Before any take (no writer task yet): NO CARD must not outlive the card's
        # return across a reopen (stems_enter keeps the rows since note 2).
        mounted = p.peek(CARD_MOUNTED, 4)
        p.poke(CARD_MOUNTED, bytes(4))
        p.chord("up", "rec", settle=400)
        p.press(ENTER, settle=200)
        nocard = rows(p, s)[0]
        p.press(CLOSE, settle=200)
        p.poke(CARD_MOUNTED, mounted)
        p.chord("up", "rec", settle=400)
        back = rows(p, s)[0]
        p.press(CLOSE, settle=200)
        vs.check(f"{model}: NO CARD before any take, then the card back: STEMS reopens on STEM REC READY",
                 nocard == ("STEM REC", "NO CARD") and back == ("STEM REC", "READY") and st() == vs.ST_IDLE,
                 f"{nocard} -> {back}")
        arms = yes_held(p)                              # the same delay as a pair's last press: ARM ALL still up
        one = st()
        single = p.screen()
        p.run(1000)
        pending = p.long(s["stems_yes_n"])
        vs.check(f"{model}: one YES is still stock's ARM ALL (every track's arm bit)", arms == 0xFFFF,
                 f"arm word {arms:#06x}")
        vs.check(f"{model}: a lone YES's first tap lapses: 1 s later no tap waits (DTCN3 wraps every 32.5 s)",
                 pending == 0, f"stems_yes_n {pending}")
        taps(p, 1000)
        slow = st()
        vs.check(f"{model}: one YES, or two 1 s apart, leave STEM REC idle", (one, slow) == (vs.ST_IDLE,) * 2,
                 f"one {one}, 1 s apart {slow}")
        taps(p, 450)
        armed, gap, fires = st(), p.long(s["stems_yes_gap"]), p.long(s["stems_yes_fires"])
        vs.check(f"{model}: YES twice 0.45 s apart arms STEM REC (0.4 s missed Yves's taps), "
                 "and the log's gap reads it in ms", armed == vs.ST_ARMED and 420 <= gap <= 520 and fires == 1,
                 f"state {armed}, gap {gap} ms, double taps {fires}")
        p.chord("up", "rec", settle=400)                # STEMS opens on STEM REC: YES cancels, close
        p.press(ENTER, settle=200)
        p.press(CLOSE, settle=200)
        taps(p, 200)
        armed = st()
        p.png(WORK / f"menu-{model}-yes-armed.png")
        vs.check(f"{model}: YES twice within 0.5 s arms STEM REC, and the toast differs from one YES's ARM ALL",
                 armed == vs.ST_ARMED and diff_box(single, p.screen()) is not None, f"state {armed}")
        taps(p, 200)
        vs.check(f"{model}: a double tap on an armed take leaves it armed (never cancels)", st() == vs.ST_ARMED,
                 f"state {st()}")
        p.chord("up", "rec", settle=400)                # STEMS opens on STEM REC: YES cancels, close
        p.press(ENTER, settle=200)
        p.press(CLOSE, settle=200)
        vs.check(f"{model}: the armed take cancels from STEMS", st() == vs.ST_IDLE and not stems_open(p, s),
                 f"state {st()}")
        p.key("t1", True)
        p.run(100)
        arms = taps(p, 200)
        p.key("t1", False)
        p.run(300)
        held = st()
        vs.check(f"{model}: with T1 held, a double tap stays stock's (T1's bit: ARM TRK, or bit 8 ARM REC TRK), STEM REC idle",
                 held == vs.ST_IDLE and arms in (0x0001, 0x0100), f"state {held}, arm word {arms:#06x}")
        p.open_menu()
        while sel(p, ROOT_DESC) != 2:                   # CONTROL: its first row is AUDIO, a settings
            p.press("down")                             # page (SYSTEM's is USB DISK MODE)
        taps(p, 200)
        inmenu = st()
        for _ in range(3):
            p.press(CLOSE, settle=200)                  # out of whatever YES entered
        vs.check(f"{model}: inside MAIN MENU a double tap leaves STEM REC idle", inmenu == vs.ST_IDLE,
                 f"state {inmenu}")
        taps(p, 200)
        p.press("play", settle=1500)
        rec = st()
        taps(p, 200)
        still = st()
        vs.check(f"{model}: armed by a double tap, PLAY records; a double tap never stops it",
                 (rec, still) == (vs.ST_RECORDING,) * 2, f"after PLAY {rec}, after a double tap {still}")
        p.press("stop", settle=500)
        for _ in range(60):
            if st() == vs.ST_IDLE:
                break
            p.run(500, wall=5)
        p.press("play", settle=1000)
        before = st()
        taps(p, 200)
        started = st()
        p.press("stop", settle=500)
        vs.check(f"{model}: while playing, a double tap starts a take",
                 before == vs.ST_IDLE and started == vs.ST_RECORDING, f"before {before}, after {started}")
        for _ in range(60):
            if st() == vs.ST_IDLE:
                break
            p.run(500, wall=5)


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
    only = [a[len("--only="):].split(",") for a in sys.argv[1:] if a.startswith("--only=")]
    parts = only[0] if only else ["looks", "walk", "yes"]       # --only=looks,walk,yes: a development switch
    if "looks" in parts:
        looks(s, fx)
    for model in ("mkii",) if "--mkii" in sys.argv else ("mkii", "mki"):    # --mkii: a development switch
        if "walk" in parts:
            walk(model, s, fx)
        if "yes" in parts:
            double_tap(model, s, fx)
    return 1 if vs.fails else 0


if __name__ == "__main__":
    sys.exit(main())
