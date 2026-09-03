#!/usr/bin/env python3
"""The MAIN MENU really gains REVERB and DELAY -- walked, not read.

    python3 tools/verify_menushortcut.py [remix]      (default: bamsep26)

Three checks, in rising order of what they cost to be wrong about:

 1. THE TABLE. The built image's CONTROL descriptor holds the new count and
    points at the relocated rows, and the six stock rows came across byte for
    byte. A static read -- but it is what the two pokes claim.
 2. THE WALK. Boot the image and walk the menu tree out of RAM with the
    firmware's own table layout: the two rows must resolve with their labels,
    with id 0 (the action path -- an id would open a menu-state screen
    instead), and with actions pointing into the cave.
 3. THE GUARD. Call the REVERB action on the warm machine with MIDI mode set.
    It must return without faulting and without touching the page-kind
    globals: in MIDI mode page kind 4 resolves track+8, so bailing is the
    whole point of that first `tst.l`.

What this CANNOT prove is the interesting half: that closing the menu from
inside an action and then selecting a track lands on the FX2 page. That runs
the stock window machinery on a machine with no menu open, which is not the
state the handler is called in. docs/MAINMENU.md section 7 prices it, and the
flash is the test.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
CONTROL_DESC, CONTROL_ROWS, ROW_LEN, STOCK_N = 0x400cbd54, 0x400cc5a8, 24, 6
MIDI_MODE = 0x80000012
PAGE_KIND = 0x460d1684
WANT = ("REVERB", "DELAY")


def main():
    from remix import registry
    name = sys.argv[1] if len(sys.argv) > 1 else "bamsep26"
    if "MENU SHORTCUT" not in registry.remix(name).modules:
        print(f"  [ -- ] {name} does not carry MENU SHORTCUT -- nothing to check")
        return 0
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build_bus.py"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    img, stock = IMAGE.read_bytes(), STOCK.read_bytes()
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}"
              f"{'  ' + detail if detail else ''}")
        fails += 0 if ok else 1

    def u32(buf, a):
        return int.from_bytes(buf[a - BASE:a - BASE + 4], "big")

    # ---- 1. the table ----------------------------------------------------
    count, rows = u32(img, CONTROL_DESC), u32(img, CONTROL_DESC + 0x18)
    check("CONTROL's count is the stock six plus our two",
          count == STOCK_N + len(WANT), f"{count}")
    check("CONTROL's rows pointer was repointed out of the stock array",
          rows != CONTROL_ROWS and 0x40000000 < rows < 0x40200000,
          f"0x{rows:08x}")
    moved = img[rows - BASE:rows - BASE + ROW_LEN * STOCK_N]
    orig = stock[CONTROL_ROWS - BASE:CONTROL_ROWS - BASE + ROW_LEN * STOCK_N]
    check("the six stock rows came across byte for byte", moved == orig)

    # ---- 2. the walk, out of booted RAM ----------------------------------
    import emu_bringup as emu
    boot = emu.boot(str(IMAGE))
    uc = boot.uc
    control = None
    for row in emu.read_menu_tree(uc):
        if row["name"] == "CONTROL":
            control = row.get("children", [])
    if control is None:
        check("the booted firmware still has a CONTROL menu", False)
        print(f"\n{fails} check(s) failed")
        return 1
    names = [c["name"] for c in control]
    check("the booted firmware draws our two rows at the end of CONTROL",
          names[-len(WANT):] == list(WANT), " · ".join(names))
    actions = {}
    for c in control:
        if c["name"] in WANT:
            actions[c["name"]] = c["action"]
            check(f"{c['name']} takes the ACTION path (id 0, not a menu state)",
                  c["page_id"] == 0, f"id={c['page_id']}")
            check(f"{c['name']}'s action points into the cave",
                  0x400d2000 <= c["action"] < 0x400d8000,
                  f"0x{c['action']:08x}")

    # ---- 3. the MIDI-mode guard ------------------------------------------
    if "REVERB" in actions:
        before = int.from_bytes(uc.mem_read(PAGE_KIND, 4), "big")
        uc.mem_write(MIDI_MODE, (1).to_bytes(4, "big"))
        try:
            emu._call(uc, actions["REVERB"], ())
            after = int.from_bytes(uc.mem_read(PAGE_KIND, 4), "big")
            check("in MIDI mode the action returns and changes nothing",
                  after == before, f"page kind 0x{after:08x}")
        except Exception as exc:                      # a fault is the answer
            check("in MIDI mode the action returns and changes nothing",
                  False, f"{type(exc).__name__}: {exc}")
        finally:
            uc.mem_write(MIDI_MODE, (0).to_bytes(4, "big"))

    print(f"\n{fails} check(s) failed" if fails else "\nOK")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
