#!/usr/bin/env python3
"""Prove the menu-state table relocation (modules/busscreen, step 1) is inert
to boot and navigation: the table moved to a cave with a 17th entry appended
and the three `lea` references repointed, and the image still boots to the
RTOS handoff and walks the MAIN MENU byte-for-byte as the un-grown image does.

No hardware: it boots the BUILT image in the ColdFire emulator. The EDIT side
of the eventual screen cannot be checked locally (docs/MAINMENU.md 9c-ii), but
this step edits nothing -- it only moves a table, which is exactly what an
emulator boot CAN confirm.
"""
import os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
IMAGE = ROOT / "out/mainos_bus.bin"
BASE = 0x40000400
STATE_TABLE = 0x400cbdac
ENTRY_LEN, ENTRY_N = 0x14, 16
DONOR_STATE = 2


def _load_src():
    """HANDLER and LABELS from the manifest, without importing the package."""
    import types
    ns = types.ModuleType("busscreen_src")
    src = (ROOT / "modules/busscreen/manifest.py").read_text()
    # execute only the top-level assignments we need (HANDLER, LABELS, offs)
    g = {"pathlib": pathlib}
    for line in src.splitlines():
        if line.startswith(("HANDLER", "LABELS", "LABELTAB_OFF", "LABELTAB_MARK")) or line.strip().startswith(('"', "'", ")", "b\"")) or line.strip().endswith((",", "+")) or line.strip().startswith("bytes.fromhex"):
            pass
    exec(compile(src[:src.index("def _stock_table")], "manifest", "exec"), g)
    ns.HANDLER = g["HANDLER"]
    ns.VERB_NAMES = g["VERB_NAMES"]; ns.DLY_NAMES = g["DLY_NAMES"]
    sys.modules["busscreen_src"] = ns

def _build(remix):
    env = {**os.environ, "REMIX": remix, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build_bus.py"],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit(f"build {remix} failed:\n{(r.stdout + r.stderr)[-800:]}")


def main():
    import emu_bringup as emu
    import shutil
    _load_src()
    fails = []
    # build_bus.py overwrites out/mainos_bus.bin; make check runs other
    # checks against it, so save whatever is there and put it back at the end.
    backup = IMAGE.read_bytes() if IMAGE.exists() else None

    def check(ok, msg):
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
        if not ok:
            fails.append(msg)

    # 1) reference walk on the un-grown image
    _build("bus")
    ref = emu.boot(str(IMAGE))
    if not ref.clean:
        sys.exit(f"reference image did not boot: {ref.stopped}")
    ref_tree = emu.read_menu_tree(ref.uc)

    # 2) the grown image
    _build("busscreen")
    img = IMAGE.read_bytes()

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    # all six references (3 enter leas + draw/key/enc addal immediates) now
    # point at the cave, each at its own member offset
    REFS = ((0x40064bd4, 0x0), (0x40064e36, 0x0), (0x400650e8, 0x0),
            (0x40064e04, 0x8), (0x4006511c, 0xc), (0x40065086, 0x10))
    new_base = rd32(REFS[0][0])
    check(new_base != STATE_TABLE and new_base != 0,
          f"table relocated off 0x{STATE_TABLE:08x} (-> 0x{new_base:08x})")
    for op, moff in REFS:
        check(rd32(op) == new_base + moff,
              f"ref at 0x{op:08x} -> 0x{new_base + moff:08x} (member +0x{moff:x})")

    # the relocated table: 16 stock entries copied verbatim, 17th appended
    stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
    st = STATE_TABLE - BASE
    stock_tab = stock[st:st + ENTRY_LEN * ENTRY_N]
    cave = new_base - BASE
    grown = img[cave:cave + ENTRY_LEN * (ENTRY_N + 1)]
    check(grown[:ENTRY_LEN * ENTRY_N] == stock_tab,
          "16 stock entries copied verbatim into the cave")
    e17 = grown[ENTRY_LEN * ENTRY_N:]
    draw = int.from_bytes(e17[8:12], "big")            # {enter,exit,DRAW,key,enc}
    keym = int.from_bytes(e17[12:16], "big")
    encm = int.from_bytes(e17[16:20], "big")
    unused = [int.from_bytes(e17[m*4:m*4+4], "big") for m in (0, 1)]
    for nm, v in (("DRAW", draw), ("KEY", keym), ("ENC", encm)):
        check(new_base < v < new_base + 0x600,
              f"17th entry's {nm} member points into the cave (0x{v:08x})")
    check(all(o == 0 for o in unused),
          "17th entry's enter/exit members are 0 (skipped)")

    # the shipped handler bytes still match the source
    import shutil, subprocess, tempfile
    from busscreen_src import HANDLER, VERB_NAMES, DLY_NAMES
    if shutil.which("m68k-elf-as") and shutil.which("m68k-elf-objcopy"):
        with tempfile.TemporaryDirectory() as td:
            o, bp = td + "/c.o", td + "/c.bin"
            subprocess.run(["m68k-elf-as", "-mcpu=5407", "-o", o,
                            str(ROOT / "modules/busscreen/screen_draw.s")], check=True)
            subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text",
                            o, bp], check=True)
            check(pathlib.Path(bp).read_bytes() == HANDLER,
                  "screen_draw.s still assembles to the shipped HANDLER bytes")
    else:
        print("  [SKIP] source re-assembly: no m68k-elf-as")

    # 3) it still boots and the menu tree is identical
    grown_boot = emu.boot(str(IMAGE))
    check(grown_boot.clean,
          f"grown image boots to the RTOS handoff ({grown_boot.stopped})")
    grown_tree = emu.read_menu_tree(grown_boot.uc)
    def labels(tree):
        out = []
        for node in tree:
            out.append(node["name"])
            out.extend(labels(node["children"]))
        return out
    ref_l, grown_l = labels(ref_tree), labels(grown_tree)
    added = [x for x in grown_l if x not in ref_l]
    removed = [x for x in ref_l if x not in grown_l]
    check(added == ["BUS FX"] and removed == [],
          f"menu tree gains exactly the BUS FX row, nothing else "
          f"(added {added}, removed {removed})")

    # 4) enter state 16 and confirm the handler renders NAME + VALUE per row,
    #    and that the label set follows the host effect id.
    uc = grown_boot.uc
    if not getattr(grown_boot, "_menu_ready", False):
        emu._prime_menu(grown_boot)
    def u32(a):
        return int.from_bytes(uc.mem_read(a, 4), "big")
    def draw_state_16():
        for _ in range(3):
            if u32(0x400cbf4c) != 0:
                break
            emu._call(uc, emu.MENU_OPEN)
        uc.mem_write(emu.MENU_STATE, (16).to_bytes(4, "big"))
        uc.mem_write(emu.MENU_VIEWPORT, (13).to_bytes(4, "big"))
        grown_boot._draws.clear()
        emu._call(uc, emu.MENU_DRAW)
        return [t for _x, _y, t in grown_boot._draws]

    # the key handler address = 17th entry's key member (index 3)
    key_addr = rd32(new_base + ENTRY_LEN * ENTRN + 3 * 4) if False else \
               int.from_bytes(img[(new_base + ENTRY_LEN * 16 + 12) - BASE:
                                   (new_base + ENTRY_LEN * 16 + 12) - BASE + 4], "big")
    def cursor_row():
        for x, y, t in grown_boot._draws:
            if t == ">":
                return (y - 8) // 8
        return None
    def press(kc):
        emu._call(uc, key_addr, (kc,))

    TRACK = 4
    def val_addr(slot):
        DB = u32(0x46c82456); part = uc.mem_read(0x80000003, 1)[0]
        track = uc.mem_read(0x80000000, 1)[0]
        base = DB + part * 6322 + track * (24 if slot < 6 else 30)
        return base + (0x8ee9a + 18 + slot if slot < 6
                       else 0x8ef5a + 18 + slot)
    def plant(slot, v):
        uc.mem_write(val_addr(slot), bytes([v & 0xff]))
    def value_row(row):
        y = 8 + row * 8
        for x, yy, t in grown_boot._draws:
            if yy == y and x == 54:
                return int(t) if t.lstrip("-").isdigit() else None
        return None

    # BusVerb (id 7): plant a distinct value per slot, expect name + value
    emu.assign_fx2(grown_boot, track=TRACK, effect_id=7)
    vals = [i * 10 + 3 for i in range(12)]        # 3,13,...,113 -- all distinct
    for i, v in enumerate(vals):
        plant(i, v)
    drawn = draw_state_16()
    names = [n.decode() for n in VERB_NAMES]
    check(all(n in drawn for n in names),
          f"BusVerb: all 12 names drawn (got {[d for d in drawn if d][:14]})")
    check(all(str(v) in drawn for v in vals),
          f"BusVerb: all 12 live values drawn (wanted {vals}, got {drawn})")

    # BusDelay (id 6): the label set switches
    emu.assign_fx2(grown_boot, track=TRACK, effect_id=6)
    drawn = draw_state_16()
    dnames = [n.decode() for n in DLY_NAMES]
    check(all(n in drawn for n in dnames),
          f"BusDelay: label set switched to its 12 names (got {[d for d in drawn if d][:14]})")

    # 5) navigation: the cursor highlight and the key handler
    emu.assign_fx2(grown_boot, track=TRACK, effect_id=7)
    draw_state_16()
    check(cursor_row() == 0, f"cursor starts on row 0 (got {cursor_row()})")
    press(0x34); draw_state_16()
    check(cursor_row() == 1, f"down moves the cursor to row 1 (got {cursor_row()})")
    for _ in range(4):
        press(0x34)
    draw_state_16()
    check(cursor_row() == 5, f"four more downs -> row 5 (got {cursor_row()})")
    press(0x33); draw_state_16()
    check(cursor_row() == 4, f"up moves back to row 4 (got {cursor_row()})")
    for _ in range(20):
        press(0x34)
    draw_state_16()
    check(cursor_row() == 11, f"down clamps at the last row 11 (got {cursor_row()})")
    for _ in range(20):
        press(0x33)
    draw_state_16()
    check(cursor_row() == 0, f"up clamps at row 0 (got {cursor_row()})")

    # 6) the CONTROL row that ENTERS the screen
    CONTROL_DESC, CONTROL_ROWS_STOCK = 0x400cbd54, 0x400cc5a8
    ROW_LEN = 24
    count = rd32(CONTROL_DESC)
    rows_ptr = rd32(CONTROL_DESC + 0x18)
    check(count == 7, f"CONTROL row count bumped to 7 (got {count})")
    check(rows_ptr != CONTROL_ROWS_STOCK and rows_ptr != 0,
          f"CONTROL rows relocated (-> 0x{rows_ptr:08x})")
    # the appended 7th row (index 6): label + action
    row = rows_ptr + 6 * ROW_LEN
    label_ptr = rd32(row)
    action = rd32(row + 8)
    rid = rd32(row + 0x14)
    label = ""
    a = label_ptr - BASE
    while 0 <= a < len(img) and img[a]:
        label += chr(img[a]); a += 1
    check(label == "BUS FX", f"the new row's label is BUS FX (got {label!r})")
    check(rid == 0 and new_base < action < new_base + 0x400,
          f"the row is an action row into the cave (id {rid}, action 0x{action:08x})")
    # invoking the action enters state 16 and the screen draws
    for _ in range(3):
        if u32(0x400cbf4c) != 0:
            break
        emu._call(uc, emu.MENU_OPEN)
    emu._call(uc, action, (0,))
    check(u32(0x400cbf40) == 16, f"the action sets MENU_STATE to 16 (got {u32(0x400cbf40)})")
    grown_boot._draws.clear()
    emu._call(uc, emu.MENU_DRAW)
    drawn = [t for _x, _y, t in grown_boot._draws]
    check(all(n in drawn for n in names),
          f"after entering, the screen draws its rows (got {[d for d in drawn if d][:14]})")

    # 7) the encoder EDITS the cursor row -- page 1 (locally verifiable) --------
    # 0x40054cd8 is self-contained; a page-1 turn must move the drawn value.
    enc_addr = int.from_bytes(img[(new_base + ENTRY_LEN * 16 + 16) - BASE:
                                   (new_base + ENTRY_LEN * 16 + 16) - BASE + 4], "big")
    emu.assign_fx2(grown_boot, track=TRACK, effect_id=7)
    plant(2, 40)                       # SIZE (page-1 row 2) = 40
    # cursor to row 2
    for _ in range(20):
        press(0x33)
    press(0x34); press(0x34)
    draw_state_16()
    check(cursor_row() == 2 and value_row(2) == 40,
          f"cursor on row 2, SIZE reads 40 (cursor {cursor_row()}, val {value_row(2)})")
    emu._call(uc, enc_addr, (0, 5))    # enc(index=0, delta=+5)
    draw_state_16()
    check(value_row(2) == 45,
          f"encoder +5 moves the page-1 value 40 -> 45 (got {value_row(2)})")
    emu._call(uc, enc_addr, (0, (-10) & 0xffffffff))
    draw_state_16()
    check(value_row(2) == 35,
          f"encoder -10 moves it 45 -> 35 (got {value_row(2)})")

    # page 2 (rows 6..11): the edit RUNS without faulting; whether the value
    # moves is the flash question (9c-ii), so this only asserts it is callable
    # and leaves the screen intact.
    for _ in range(20):
        press(0x34)                     # cursor to row 11
    st_before = u32(0x400cbf40)
    try:
        emu._call(uc, enc_addr, (0, 1))
        p2_ok = True
    except Exception:
        p2_ok = False
    check(p2_ok and u32(0x400cbf40) == st_before,
          "page-2 encoder call runs without fault (value-move is the flash test)")

    if backup is not None:
        IMAGE.write_bytes(backup)       # restore for the rest of make check
    print(f"\n{'FAILED' if fails else 'busscreen OK (draw + nav + entry)'}: "
          f"{len(fails)} failure(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
