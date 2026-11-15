#!/usr/bin/env python3
"""SEQ FUNC+BANK clear LISTPOP under MKII port (Detour 0x4007c0d0).

Cases:
  - SEQ open → CLEAR DEST list on top (SEQ soft-closed, not stacked)
  - FUNC+BANK again toggles closed and restores SEQ
  - one NO closes list and restores SEQ (cancel layer)
  - after restore, one NO closes SEQ (state not stranded)
  - CLEAR DEST / ALL DEST / ALL+TRIGS YES: list gone + SEQ restored
  - outside SEQ is not our CLEAR list
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools/verify"), str(ROOT / "tools/panel")]

from stems_panel import MenuPort  # noqa: E402
from seq_port_fixture import stage_project  # noqa: E402

IMAGE = ROOT / "out/mainos_bus.bin"
CARD = ROOT / "out/_seq_fb_card.img"
MAP = ROOT / "out/platform/runtime/runtime.map"

M_OBJ = 0x460e5e30
M_CBS = 0x460e5e28
M_LAB = 0x460e5e2c
FUNC_LAYER_KEYS = 0x400bfa36
MKII_TRIG_EDIT = 0x4007c0d0

FAILS = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global FAILS
    if ok:
        print(f"  [PASS] {name}" + (f" ({detail})" if detail else ""))
    else:
        FAILS += 1
        print(f"  [FAIL] {name}" + (f": {detail}" if detail else ""))


def sym(name: str) -> int:
    for line in MAP.read_text().splitlines():
        if line.rstrip().endswith(name) and "0x" in line:
            return int(line.split()[0], 16)
    raise SystemExit(f"missing {name} in runtime.map")


def ensure_card():
    return stage_project(IMAGE, CARD, ROOT / "out/_seq_fb_tree")


def labels(p) -> list[str]:
    obj = p.long(M_OBJ)
    lab = p.long(M_LAB)
    if not obj or not lab:
        return []
    out = []
    for i in range(3):
        lp = p.long(lab + 4 * i)
        out.append(p.cstr(lp, 24) if lp else "")
    return out


def bank_press_in_table(p, base: int) -> int | None:
    raw = p.peek(base, 0x400)
    for i in range(0, len(raw) - 8):
        if raw[i] == 0x2F and raw[i + 1] == 0:
            press = int.from_bytes(raw[i + 2 : i + 6], "big")
            if 0x40000000 <= press <= 0x40F00000:
                return press
    return None


def open_clear(p, ef_win: int) -> None:
    p.chord("func", "bank", settle=700)
    check("CLEAR list open", "CLEAR DEST" in labels(p), str(labels(p)))
    check("SEQ soft-closed while CLEAR up", p.long(ef_win) == 0,
          f"ef_win={p.long(ef_win):#x}")


def assert_restored(p, ef_win: int, how: str) -> None:
    check(f"{how}: list closed", p.long(M_OBJ) == 0)
    check(f"{how}: SEQ restored", p.long(ef_win) != 0, f"ef_win={p.long(ef_win):#x}")


def main() -> int:
    if not IMAGE.exists():
        print("verify_seq_func_bank: no out/mainos_bus.bin")
        return 1
    if not (ROOT / "out/emu/ot_emu").exists():
        print("verify_seq_func_bank: no out/emu/ot_emu")
        return 1
    if not MAP.exists():
        print("verify_seq_func_bank: no runtime.map")
        return 1

    remix = ensure_card()
    ef_win = sym("ef_win")
    ef_fb = sym("ef_fb_mkii")

    print("SEQ FUNC+BANK (MKII port):")
    with MenuPort(IMAGE, CARD, "OCTABAM", "A", mkii=True) as p:
        p.settle()
        for _ in range(3):
            p.press("no", settle=80)

        # Image wiring
        site = p.peek(MKII_TRIG_EDIT, 6)
        check("Detour site is jmp abs", site[:2] == bytes.fromhex("4ef9"), site.hex())
        dest = int.from_bytes(site[2:6], "big")
        check("Detour target is ef_fb_mkii", dest == ef_fb, f"{dest:#x} vs {ef_fb:#x}")

        fk = p.long(FUNC_LAYER_KEYS)
        if "BRAIN" in remix.modules:
            check("FUNC layer keys ptr is DRAM (BRAIN clone)", fk >= 0x40A00000, f"{fk:#x}")
        press = bank_press_in_table(p, fk)
        check("FUNC+BANK press = TRACK TRIG EDIT entry",
              press == MKII_TRIG_EDIT, f"{press:#x}" if press else "none")

        # Open SEQ
        p.chord("t1", "page", settle=600)
        win = p.long(ef_win)
        check("SEQ open (ef_win)", win != 0, f"{win:#x}")
        open_scr = p.screen()

        # FUNC+BANK once — list must stay up (no layer double-fire toggle)
        p.key("func", True)
        p.run(80)
        p.press("bank", settle=700)
        p.key("func", False)
        p.run(200)

        labs = labels(p)
        obj = p.long(M_OBJ)
        check("CLEAR DEST list open",
              obj != 0 and labs[:1] == ["CLEAR DEST"] and "CLEAR ALL DEST" in labs
              and "CLEAR ALL+TRIGS" in labs,
              str(labs))
        check("list still up after FUNC release", p.long(M_OBJ) != 0)
        check("SEQ soft-closed while list up (not stacked over CLEAR)",
              p.long(ef_win) == 0, f"ef_win={p.long(ef_win):#x}")
        list_scr = p.screen()
        changed = sum(1 for y in range(64) for x in range(128)
                      if open_scr[y][x] != list_scr[y][x])
        check("LCD changed when CLEAR opened", changed > 100, f"changed={changed}")

        # FUNC+BANK toggles closed and restores SEQ
        p.chord("func", "bank", settle=700)
        assert_restored(p, ef_win, "FUNC+BANK toggle")

        # One NO closes + restores (cancel layer). Then SEQ still closes cleanly.
        open_clear(p, ef_win)
        p.press("no", settle=500)
        assert_restored(p, ef_win, "NO")
        p.press("no", settle=400)
        check("after NO-restore, next NO closes SEQ", p.long(ef_win) == 0)
        p.chord("t1", "page", settle=600)
        check("SEQ reopens after clean close", p.long(ef_win) != 0)

        # Each YES row: dismiss list + restore SEQ (row 0 already selected).
        for row, name in (
            (0, "CLEAR DEST YES"),
            (1, "CLEAR ALL DEST YES"),
            (2, "CLEAR ALL+TRIGS YES"),
        ):
            open_clear(p, ef_win)
            for _ in range(row):
                p.press("down", settle=200)
            p.press("yes", settle=800)
            assert_restored(p, ef_win, name)

        # Outside SEQ
        p.press("no", settle=400)
        check("SEQ closed", p.long(ef_win) == 0)
        p.chord("func", "bank", settle=700)
        check("outside SEQ is not CLEAR list", "CLEAR DEST" not in labels(p),
              str(labels(p)))

    print(f"SEQ FUNC+BANK: {FAILS} failed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
