#!/usr/bin/env python3
"""Prove modules/busscreen in the ColdFire emulator, no hardware.

The bus screen is a 17th MAIN MENU state reached from two CONTROL rows,
REVERB and DELAY, each of which selects the track hosting that engine and
opens a screen of its twelve controls as two pages of six (up/down cross the
page boundary). The level knob edits the cursor row: page-1 rows through the
self-contained writer 0x40054cd8 (proven here), page-2 rows through
0x4003a474 (built; the value-move is the flash question, docs/MAINMENU.md
9c-ii). Draw and edit use the same Part arrays, so an edit is visible.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
IMAGE = ROOT / "out/mainos_bus.bin"
BASE = 0x40000400
STATE_TABLE = 0x400cbdac
ENTRY_LEN, ENTRY_N = 0x14, 16
CONTROL_DESC = 0x400cbd54
ID_BASE = 0x80000ecc                       # per-track FX2 ids the scan reads


def _build(remix):
    env = {**os.environ, "REMIX": remix, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build_bus.py"],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit(f"build {remix} failed:\n{(r.stdout + r.stderr)[-800:]}")


def _load_src():
    """HANDLER / VERB_NAMES / DLY_NAMES from the manifest without importing it."""
    import types
    ns = types.ModuleType("busscreen_src")
    src = (ROOT / "modules/busscreen/manifest.py").read_text()
    g = {"pathlib": pathlib}
    exec(compile(src[:src.index("def _stock_table")], "manifest", "exec"), g)
    ns.HANDLER = g["HANDLER"]
    ns.VERB_NAMES = g["VERB_NAMES"]
    ns.DLY_NAMES = g["DLY_NAMES"]
    sys.modules["busscreen_src"] = ns
    return ns


def main():
    import emu_bringup as emu
    import shutil
    src = _load_src()
    fails = []

    def check(ok, msg):
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
        if not ok:
            fails.append(msg)

    # reference walk on the un-grown image
    _build("bus")
    backup = IMAGE.read_bytes()
    ref = emu.boot(str(IMAGE))
    if not ref.clean:
        sys.exit(f"reference image did not boot: {ref.stopped}")
    ref_tree = emu.read_menu_tree(ref.uc)

    # the grown image
    _build("busscreen")
    img = IMAGE.read_bytes()

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    # every reference to the table repointed (3 enter leas + draw/key/enc)
    REFS = ((0x40064bd4, 0x0), (0x40064e36, 0x0), (0x400650e8, 0x0),
            (0x40064e04, 0x8), (0x4006511c, 0xc), (0x40065086, 0x10))
    new_base = rd32(REFS[0][0])
    check(new_base != STATE_TABLE and new_base != 0,
          f"table relocated off 0x{STATE_TABLE:08x} (-> 0x{new_base:08x})")
    for op, moff in REFS:
        check(rd32(op) == new_base + moff,
              f"ref at 0x{op:08x} -> 0x{new_base + moff:08x} (member +0x{moff:x})")

    # 16 stock entries verbatim, 17th has draw/key/enc set, enter/exit 0
    stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
    st = STATE_TABLE - BASE
    grown = img[new_base - BASE:new_base - BASE + ENTRY_LEN * (ENTRY_N + 1)]
    check(grown[:ENTRY_LEN * ENTRY_N] == stock[st:st + ENTRY_LEN * ENTRY_N],
          "16 stock entries copied verbatim into the cave")
    e17 = grown[ENTRY_LEN * ENTRY_N:]
    for nm, off in (("DRAW", 8), ("KEY", 12), ("ENC", 16)):
        v = int.from_bytes(e17[off:off + 4], "big")
        check(new_base < v < new_base + 0x800,
              f"17th entry's {nm} member points into the cave (0x{v:08x})")
    check(int.from_bytes(e17[0:4], "big") == 0
          and int.from_bytes(e17[4:8], "big") == 0,
          "17th entry's enter/exit members are 0 (skipped)")

    # source still assembles to the shipped bytes
    if shutil.which("m68k-elf-as") and shutil.which("m68k-elf-objcopy"):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            o, bp = td + "/c.o", td + "/c.bin"
            subprocess.run(["m68k-elf-as", "-mcpu=5407", "-o", o,
                            str(ROOT / "modules/busscreen/screen_draw.s")], check=True)
            subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text",
                            o, bp], check=True)
            check(pathlib.Path(bp).read_bytes() == src.HANDLER,
                  "screen_draw.s still assembles to the shipped HANDLER bytes")

    # boots, and the menu gains exactly REVERB and DELAY under CONTROL
    grown_boot = emu.boot(str(IMAGE))
    check(grown_boot.clean,
          f"grown image boots to the RTOS handoff ({grown_boot.stopped})")
    uc = grown_boot.uc

    def labels(tree):
        out = []
        for node in tree:
            out.append(node["name"])
            out.extend(labels(node["children"]))
        return out
    ref_l = labels(ref_tree)
    added = [x for x in labels(emu.read_menu_tree(uc)) if x not in ref_l]
    check(added == ["REVERB", "DELAY"],
          f"menu gains exactly REVERB and DELAY (added {added})")

    if not getattr(grown_boot, "_menu_ready", False):
        emu._prime_menu(grown_boot)

    def u32(a):
        return int.from_bytes(uc.mem_read(a, 4), "big")

    # the two CONTROL row actions
    rows_ptr = rd32(CONTROL_DESC + 0x18)
    rev_action = rd32(rows_ptr + 6 * 24 + 8)
    dly_action = rd32(rows_ptr + 7 * 24 + 8)

    def draw():
        for _ in range(3):
            if u32(0x400cbf4c) != 0:
                break
            emu._call(uc, emu.MENU_OPEN)
        uc.mem_write(emu.MENU_VIEWPORT, (13).to_bytes(4, "big"))
        grown_boot._draws.clear()
        emu._call(uc, emu.MENU_DRAW)
        return grown_boot._draws

    def texts():
        return [t for _x, _y, t in grown_boot._draws]

    def cursor_row():
        for x, y, t in grown_boot._draws:
            if t == ">":
                return (y - 8) // 8
        return None

    def value_row(row):
        y = 8 + row * 8
        for x, yy, t in grown_boot._draws:
            if yy == y and x == 54:
                return int(t) if t.lstrip("-").isdigit() else None
        return None

    def press(kc):
        e17_key = int.from_bytes(e17[12:16], "big")
        emu._call(uc, e17_key, (kc,))

    def val_addr(track, slot):
        DB = u32(0x46c82456)
        part = uc.mem_read(0x80000003, 1)[0]
        base = DB + part * 6322 + track * (24 if slot < 6 else 30)
        return base + (0x8ee9a + 18 + slot if slot < 6 else 0x8ef5a + 18 + slot)

    def setup(track, eid, values):
        # the scan reads 0x80000ecc; the label picks off the Part id 0x8ed88
        uc.mem_write(ID_BASE + track, bytes([eid]))
        emu.assign_fx2(grown_boot, track=track, effect_id=eid)
        for slot, v in enumerate(values):
            uc.mem_write(val_addr(track, slot), bytes([v & 0xff]))

    VERB_VALS = [i + 20 for i in range(12)]     # 20..31, distinct
    # ---- REVERB row: selects the verb track, draws page 1 ----------------
    uc.mem_write(0x80000000, bytes([0]))         # not on the verb track yet
    setup(4, 7, VERB_VALS)                        # BusVerb on track 4
    emu._call(uc, rev_action, (0,))
    check(uc.mem_read(0x80000000, 1)[0] == 4,
          f"REVERB selects the host track 4 (got {uc.mem_read(0x80000000, 1)[0]})")
    check(u32(0x400cbf40) == 16, "REVERB opens the screen (state 16)")
    draw()
    want_p1 = [n.decode() for n in src.VERB_NAMES[:6]]
    check(all(n in texts() for n in want_p1),
          f"page 1 shows the first six verb names (got {[t for t in texts() if t][:10]})")
    check(all(str(v) in texts() for v in VERB_VALS[:6]),
          f"page 1 shows their values {VERB_VALS[:6]} (got {texts()})")
    check(cursor_row() == 0, f"cursor starts at row 0 (got {cursor_row()})")

    # ---- navigation across the page boundary -----------------------------
    for _ in range(5):
        press(0x34)
    draw()
    check(cursor_row() == 5, f"five downs -> row 5, still page 1 (got {cursor_row()})")
    check(all(n in texts() for n in want_p1),
          "still page 1 at row 5")
    press(0x34); draw()
    want_p2 = [n.decode() for n in src.VERB_NAMES[6:]]
    check(cursor_row() == 0 and all(n in texts() for n in want_p2),
          f"down past row 5 flips to page 2 row 0 (cursor {cursor_row()}, "
          f"got {[t for t in texts() if t][:10]})")
    press(0x33); draw()
    check(cursor_row() == 5 and all(n in texts() for n in want_p1),
          f"up from page 2 row 0 returns to page 1 row 5 (cursor {cursor_row()})")

    # ---- edit a page-1 row (locally proven) ------------------------------
    for _ in range(5):
        press(0x33)                              # back to page 1 row 0
    press(0x34); press(0x34)                      # row 2 = SIZE
    draw()
    check(cursor_row() == 2, f"cursor on row 2 (got {cursor_row()})")
    v0 = value_row(2)
    e17_enc = int.from_bytes(e17[16:20], "big")
    emu._call(uc, e17_enc, (0, 5))
    draw()
    check(value_row(2) == v0 + 5,
          f"encoder +5 moves the page-1 value {v0} -> {v0 + 5} (got {value_row(2)})")

    # page-2 edit: runs without fault (value-move is the flash test)
    press(0x34); press(0x34); press(0x34); press(0x34)   # into page 2
    st_before = u32(0x400cbf40)
    ok_p2 = True
    try:
        emu._call(uc, e17_enc, (0, 1))
    except Exception:
        ok_p2 = False
    check(ok_p2 and u32(0x400cbf40) == st_before,
          "page-2 encoder call runs without fault (value-move is the flash test)")

    # ---- DELAY row: selects the delay track, switches the label set ------
    uc.mem_write(0x80000000, bytes([0]))
    setup(2, 6, [i + 40 for i in range(12)])      # BusDelay on track 2
    emu._call(uc, dly_action, (0,))
    check(uc.mem_read(0x80000000, 1)[0] == 2,
          f"DELAY selects the host track 2 (got {uc.mem_read(0x80000000, 1)[0]})")
    draw()
    want_d1 = [n.decode() for n in src.DLY_NAMES[:6]]
    check(all(n in texts() for n in want_d1),
          f"DELAY draws the delay's names (got {[t for t in texts() if t][:10]})")

    IMAGE.write_bytes(backup)                      # restore for the rest of make check
    print(f"\n{'FAILED' if fails else 'busscreen OK (2 rows, paged, edit)'}: "
          f"{len(fails)} failure(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
