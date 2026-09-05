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
    ns.HANDLER_AT = g["HANDLER_AT"]          # the handler is PINNED (5 Sep 2026)
    ns.KEY_OFF = g["KEY_OFF"]
    ns.ENC_OFF = g["ENC_OFF"]
    ns.VERB_NAMES = g["VERB_NAMES"]
    ns.DLY_NAMES = g["DLY_NAMES"]
    ns.VERB_SELECTS = g["VERB_SELECTS"]
    ns.DLY_SELECTS = g["DLY_SELECTS"]
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

    # snapshot whatever make check built (the default remix) BEFORE we
    # rebuild, so it can be restored for the rest of the run.
    backup = IMAGE.read_bytes() if IMAGE.exists() else None
    # reference walk on the un-grown image
    _build("bus")
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
    # The handler is a separate PINNED cave (5 Sep 2026): the 17th entry's
    # members are exact addresses into it, not offsets into the table's cave.
    for nm, off, want in (("DRAW", 8, src.HANDLER_AT),
                          ("KEY", 12, src.HANDLER_AT + src.KEY_OFF),
                          ("ENC", 16, src.HANDLER_AT + src.ENC_OFF)):
        v = int.from_bytes(e17[off:off + 4], "big")
        check(v == want,
              f"17th entry's {nm} member is the pinned handler's "
              f"(0x{v:08x}, want 0x{want:08x})")
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
    e17_key = int.from_bytes(e17[12:16], "big")
    e17_enc = int.from_bytes(e17[16:20], "big")
    KEY_UP, KEY_DOWN = 0x34, 0x33        # UP / DOWN as they move on the unit

    def draw():
        for _ in range(3):
            if u32(0x400cbf4c) != 0:
                break
            emu._call(uc, emu.MENU_OPEN)
        uc.mem_write(0x400cbf40, (16).to_bytes(4, "big"))   # MENU_OPEN may reset
        uc.mem_write(emu.MENU_VIEWPORT, (13).to_bytes(4, "big"))
        grown_boot._draws.clear()
        inverts.clear()
        emu._call(uc, emu.MENU_DRAW)

    def geom(slot):
        col = 0 if slot < 6 else 1
        row = slot % 6
        bar_y = 4 + row * 7
        return bar_y + 1, (32 if col == 0 else 90), col

    def value_at(slot):
        y, val_x, _ = geom(slot)
        for x, yy, t in grown_boot._draws:
            if yy == y and x == val_x:
                return t
        return None

    # the cursor is an INVERTED BAR (0x40012254), which the text hook cannot
    # see -- hook the invert call and read (x1, y1) off its stack.
    inverts = []
    def _inv_hook(u, addr, size, user):
        sp = u.reg_read(UC_M68K_REG_A7)
        x1 = int.from_bytes(u.mem_read(sp + 8, 4), "big")
        y1 = int.from_bytes(u.mem_read(sp + 12, 4), "big")
        inverts.append((x1, y1))
    from unicorn import UC_HOOK_CODE
    from unicorn.m68k_const import UC_M68K_REG_A7
    uc.hook_add(UC_HOOK_CODE, _inv_hook, begin=0x40012254, end=0x40012254)

    # The page-2 editor 0x4003a474 calls a helper 0x4003249c that reads the
    # staged page and SPINS on a cold machine (docs/MAINMENU.md 9c-ii). On
    # hardware it returns. Stub it (moveq #0,d0; rts) so the editor returns
    # and the screen's own select-clamp code after the call is exercised.
    from unicorn.m68k_const import UC_M68K_REG_PC, UC_M68K_REG_D0
    def _stub(u, addr, size, user):
        sp = u.reg_read(UC_M68K_REG_A7)
        ret = int.from_bytes(u.mem_read(sp, 4), "big")
        u.reg_write(UC_M68K_REG_A7, sp + 4)
        u.reg_write(UC_M68K_REG_D0, 0)
        u.reg_write(UC_M68K_REG_PC, ret)
    uc.hook_add(UC_HOOK_CODE, _stub, begin=0x4003249c, end=0x4003249c)
    for b in (0x100a0000, 0x100f0000):
        try:
            uc.mem_map(b, 0x10000)
        except Exception:
            pass

    def cursor_slot():
        # the last invert of a draw with a row-sized bar y (4 + row*7)
        for x1, y1 in reversed(inverts):
            if (y1 - 4) % 7 == 0 and 0 <= (y1 - 4) // 7 < 6 and x1 in (2, 60):
                return (0 if x1 == 2 else 1) * 6 + (y1 - 4) // 7
        return None

    def press(kc):
        emu._call(uc, e17_key, (kc,))

    def val_addr(track, slot):
        DB = u32(0x46c82456)
        part = uc.mem_read(0x80000003, 1)[0]
        base = DB + part * 6322 + track * (24 if slot < 6 else 30)
        return base + (0x8ee9a + 18 + slot if slot < 6 else 0x8ef5a - 6 + slot)   # page 2: +0+slot2, staged index 0 (measured 5 Sep)

    # ---- REVERB: selects host track 4, draws all 12 in two columns --------
    uc.mem_write(0x80000000, bytes([0]))
    uc.mem_write(ID_BASE + 4, bytes([7]))
    emu.assign_fx2(grown_boot, track=4, effect_id=7)
    from busscreen_src import VERB_SELECTS, DLY_SELECTS
    for slot in range(12):
        v = 1 if slot in VERB_SELECTS else 50 + slot
        uc.mem_write(val_addr(4, slot), bytes([v]))
    emu._call(uc, rev_action, (0,))
    check(uc.mem_read(0x80000000, 1)[0] == 4, "REVERB selects host track 4")
    draw()
    names = [n.decode() for n in src.VERB_NAMES]
    check(all(n in [t for _x, _y, t in grown_boot._draws] for n in names),
          "all 12 verb names shown at once (double-wide)")
    # every slot shows the right thing: knobs -> number, selects -> word
    bad = []
    for slot in range(12):
        shown = value_at(slot)
        if slot in VERB_SELECTS:
            want = VERB_SELECTS[slot][1]      # index 1
            want = want.decode() if isinstance(want, bytes) else want
        else:
            want = str(50 + slot)
        if shown != want:
            bad.append(f"slot {slot}: {shown!r} != {want!r}")
    check(not bad, f"all 12 verb values correct (knobs numbers, selects words) {bad}")
    check(cursor_slot() == 0, f"cursor starts at slot 0 (got {cursor_slot()})")

    # navigation: linear 0..11 across both columns, clamped
    for _ in range(7):
        press(KEY_DOWN)
    draw()
    check(cursor_slot() == 7,
          f"seven downs -> slot 7 (right column row 1) (got {cursor_slot()})")
    for _ in range(3):
        press(KEY_UP)
    draw()
    check(cursor_slot() == 4, f"three ups -> slot 4 (got {cursor_slot()})")
    # infinite scroll: wraps both ways (4 -> 11 downs -> 3 ... use exact counts)
    for _ in range(7):
        press(KEY_DOWN)                  # 4 -> 11
    draw()
    check(cursor_slot() == 11, f"seven downs from 4 -> slot 11 (got {cursor_slot()})")
    press(KEY_DOWN); draw()
    check(cursor_slot() == 0, f"down from 11 WRAPS to 0 (got {cursor_slot()})")
    press(KEY_UP); draw()
    check(cursor_slot() == 11, f"up from 0 WRAPS to 11 (got {cursor_slot()})")
    press(KEY_DOWN); draw()              # back to 0
    check(cursor_slot() == 0, "back at slot 0")

    # edit a page-1 knob (slot 2 = SIZE)
    press(KEY_DOWN); press(KEY_DOWN)
    draw()
    v0 = int(value_at(2))
    emu._call(uc, e17_enc, (0, 5))
    draw()
    check(int(value_at(2)) == v0 + 5,
          f"encoder +5 moves SIZE {v0} -> {v0 + 5} (got {value_at(2)})")

    # a SELECT edit steps by its COUNT (the editor alone ramps 0..127):
    # MODE (slot 6, count 3): 0 -> 1 -> 2 -> clamps at 2; Part + live byte
    for _ in range(4):
        press(KEY_DOWN)                  # slot 2 -> slot 6 (MODE)
    draw()
    check(cursor_slot() == 6, f"cursor on MODE, slot 6 (got {cursor_slot()})")
    uc.mem_write(val_addr(4, 6), bytes([0]))
    seq = []
    for _ in range(3):
        emu._call(uc, e17_enc, (0, 1))
        draw()
        seq.append((uc.mem_read(val_addr(4, 6), 1)[0],
                    uc.mem_read(0x80000950, 1)[0], value_at(6)))
    check(seq == [(1, 1, "PLATE"), (2, 2, "BIG"), (2, 2, "BIG")],
          f"MODE +1 x3 steps 0->1->2 and clamps at 2 in Part, live byte and word (got {seq})")
    emu._call(uc, e17_enc, (0, (-5) & 0xffffffff))
    draw()
    check(uc.mem_read(val_addr(4, 6), 1)[0] == 0 and value_at(6) == "ROOM",
          f"MODE -5 clamps at 0 -> ROOM (got {value_at(6)!r})")

    # ---- DELAY: selects host track 2, switches label set -----------------
    uc.mem_write(0x80000000, bytes([0]))
    uc.mem_write(ID_BASE + 2, bytes([6]))
    emu.assign_fx2(grown_boot, track=2, effect_id=6)
    for slot in range(12):
        v = 1 if slot in DLY_SELECTS else 50 + slot
        uc.mem_write(val_addr(2, slot), bytes([v]))
    emu._call(uc, dly_action, (0,))
    check(uc.mem_read(0x80000000, 1)[0] == 2, "DELAY selects host track 2")
    draw()
    dnames = [n.decode() for n in src.DLY_NAMES]
    check(all(n in [t for _x, _y, t in grown_boot._draws] for n in dnames),
          "DELAY shows its 12 names (label set switched)")
    check(value_at(6) == DLY_SELECTS[6][1].decode(),
          f"DELAY MODE shows its word (got {value_at(6)!r})")

    # NOTE (4 Sep 2026): the 13th RETURN row and its rig phase were removed
    # here when screen-in-rig was deferred -- bamsep27 cannot float the cave in
    # the safe band (its clones+formatters fill it) and pinning into the image
    # bss crashed on [PROJ]. The return-row code stays in screen_draw.s,
    # dormant (NSLOT=13 only when T8 FX1 is CHARACTER), to be re-gated when the
    # cave is split or the rig trimmed and the screen goes back into the rig.
    if backup is not None:
        IMAGE.write_bytes(backup)                  # restore for the rest of make check
    print(f"\n{'FAILED' if fails else 'busscreen OK (2 rows, double-wide, all 24 edit)'}: "
          f"{len(fails)} failure(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
