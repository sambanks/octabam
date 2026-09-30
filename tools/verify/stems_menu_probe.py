#!/usr/bin/env python3
"""What STEMS's menu design assumes, measured under the port (piece 3,
Task 2; docs/superpowers/specs/2026-09-28-stem-rec-menu-design.md).

    python3 tools/verify/stems_menu_probe.py [--mki]

Builds REMIX=stems and the fixtures, boots the one-track fixture card
under `ot_emu --interactive`, and prints:
1. MAIN MENU opens (PROJ on an MKII, FUNC+MIXER on an MKI) on the root.
2. YES enters a category's list, LEFT leaves it, RIGHT enters it (the
   focus pointer). NO in a list closes the whole menu (the first run of
   29 Sep 2026: the focus kept CONTROL and the screen showed PLAYBACK),
   which item 7 records at the end.
3. Whether a label changed while the menu shows it redraws with no key
   (octalab's MENU.md: "the main menu is a live screen"); 3b, after RIGHT
   and LEFT.
4. The clip edge of the root column and of the list pane: a row's label
   set to an empty string, then to 24 Ws, each redrawn by RIGHT and LEFT;
   the box of what changed.
5. A heading row: CONTROL's row 1 (INPUT) with its action poked to 0 --
   the cursor goes from AUDIO to SEQUENCER, and the PNG shows its drawing.
6. PLAY and STOP with the menu open: the transport word.
7. NO inside a list: the screen and the focus pointer after it.
8. The LAST row with action 0: DOWN twice from the row above it. The
   engine skips one such row (item 5) but not two in a row (the gate, 29
   Sep 2026); whether it can land on a last one decides STEMS's PEAK row.
PNGs go to out/stems_runs/probe-<model>-*.png."""
import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_stems as vs  # noqa: E402
from stems_panel import MENU_FOCUS, MenuPort, diff_box  # noqa: E402

ROOT_DESC, ROOT_ROWS, CONTROL_DESC = 0x400cbd8c, 0x400cc698, 0x400cbd54
SEL, TRANSPORT = 0x0c, 0x800065b8
WORK = pathlib.Path("out/stems_runs")


def label_box(p, label_at, scratch, text, kick=True):
    """Point the row whose label pointer is at `label_at` at `text` (written
    to `scratch`) and return the screen. `kick`: RIGHT then LEFT first, into
    the list and out again, which redraws the menu (run 2 of 29 Sep 2026: a
    label change alone does not reach the screen)."""
    p.poke(scratch, text.encode("latin1") + b"\0")
    p.poke(label_at, scratch.to_bytes(4, "big"))
    p.run(500)
    if kick:
        p.press("right")
        p.press("left")
    return p.screen()


def main():
    model = "mki" if "--mki" in sys.argv else "mkii"
    env = {**os.environ, "REMIX": "stems", "XBUS": "1", "SPEC": "1"}
    subprocess.run([sys.executable, "tools/build/build_bus.py"], check=True, capture_output=True, env=env)
    if not vs.fixtures():
        sys.exit("no fixture template (STEMS_TEMPLATE)")
    s = vs.syms()
    fx = json.loads(vs.FIXTURE.read_text())
    card = WORK / f"probe-{model}.img"
    WORK.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fx["card"], card)
    scratch = s["stems_fpath"]            # 256 bytes the runtime uses only while a take starts
    with MenuPort(vs.IMAGE, card, fx["set"], fx["project"], model == "mkii",
                  log_path=WORK / f"probe-{model}.log") as p:
        p.settle()
        p.open_menu()
        p.png(WORK / f"probe-{model}-root.png")
        print(f"1. focus {p.long(MENU_FOCUS):#x} (root {ROOT_DESC:#x}), root selection {p.long(ROOT_DESC + SEL)}")
        for _ in range(2):
            p.press("down")
        p.press("yes")
        ctl = p.long(MENU_FOCUS)
        p.press("left")
        left = p.long(MENU_FOCUS)
        p.press("right")
        right = p.long(MENU_FOCUS)
        p.press("left")
        print(f"2. YES on CONTROL: focus {ctl:#x} (CONTROL {CONTROL_DESC:#x}); LEFT: {left:#x}; "
              f"RIGHT: {right:#x}; LEFT: {p.long(MENU_FOCUS):#x} (root {ROOT_DESC:#x})")
        p.png(WORK / f"probe-{model}-back.png")
        rows = p.long(CONTROL_DESC + 0x18)
        audio = p.long(rows)                 # AUDIO's label pointer, put back after
        before = p.screen()
        after = label_box(p, rows, scratch, "LIVE TEST", kick=False)
        p.run(2500)
        print(f"3. a label changed with no key, 3 s: screen changed {diff_box(before, p.screen())}")
        p.png(WORK / f"probe-{model}-live.png")
        p.press("right")
        p.press("left")
        print(f"3b. then RIGHT, LEFT: screen changed {diff_box(before, p.screen())}")
        p.png(WORK / f"probe-{model}-live-kick.png")
        empty = label_box(p, rows, scratch, "")
        wide = label_box(p, rows, scratch, "W" * 24)
        print(f"4a. list pane: 24 Ws against empty, box {diff_box(empty, wide)}")
        p.png(WORK / f"probe-{model}-pane.png")
        for text in ("SAME MINUTE", "WRITE FAILED", "CLOSE FAILED", "DONE 60:00", "PEAK 100%", "T8 [X]"):
            print(f"    {text!r}: box {diff_box(empty, label_box(p, rows, scratch, text))}")
        p.poke(rows, audio.to_bytes(4, "big"))
        root_label = p.long(ROOT_DESC + 0x18) + 3 * 24   # MIDI's label pointer, in the live root rows
        stock = p.long(root_label)
        empty = label_box(p, root_label, scratch, "")
        wide = label_box(p, root_label, scratch, "W" * 24)
        print(f"4b. root column: 24 Ws against empty, box {diff_box(empty, wide)}")
        print(f"    'STEMS': box {diff_box(empty, label_box(p, root_label, scratch, 'STEMS'))}")
        p.png(WORK / f"probe-{model}-root-wide.png")
        p.poke(root_label, stock.to_bytes(4, "big"))
        p.poke(rows + 24 + 8, bytes(4))     # INPUT's action := 0, a heading
        p.press("yes")
        seen = [p.long(CONTROL_DESC + SEL)]
        p.press("down")
        seen.append(p.long(CONTROL_DESC + SEL))
        p.press("up")
        seen.append(p.long(CONTROL_DESC + SEL))
        p.png(WORK / f"probe-{model}-heading.png")
        print(f"5. CONTROL selection: start, down, up = {seen} (a skipped heading reads [0, 2, 0])")
        n = p.long(CONTROL_DESC)
        p.poke(rows + 24 * (n - 1) + 8, bytes(4))     # the last row's action := 0 as well
        p.press("down")                               # AUDIO -> SEQUENCER (INPUT skipped)
        for _ in range(n):                            # to the row above the last, bounded
            if p.long(CONTROL_DESC + SEL) >= n - 2:
                break
            p.press("down")
        last = [p.long(CONTROL_DESC + SEL)]
        for _ in range(2):
            p.press("down")
            last.append(p.long(CONTROL_DESC + SEL))
        p.png(WORK / f"probe-{model}-last.png")
        print(f"8. the last row ({n - 1}) with action 0: from row {n - 2}, DOWN, DOWN = {last} "
              f"(it stays: [{n - 2}, {n - 2}, {n - 2}]; it lands: {n - 1} appears)")
        p.press("up")
        p.press("up")
        t0 = p.long(TRANSPORT)
        p.press("play", settle=600)
        t1 = p.long(TRANSPORT)
        p.press("stop", settle=600)
        print(f"6. transport with the menu open: {t0} -> PLAY {t1} -> STOP {p.long(TRANSPORT)}; "
              f"focus after {p.long(MENU_FOCUS):#x}")
        p.png(WORK / f"probe-{model}-transport.png")
        before = p.screen()
        p.press("no", settle=400)
        print(f"7. NO in a list: the screen changed {diff_box(before, p.screen())}, focus {p.long(MENU_FOCUS):#x}")
        p.png(WORK / f"probe-{model}-no.png")


if __name__ == "__main__":
    main()
