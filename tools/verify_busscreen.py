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
    ns.HANDLER = g["HANDLER"]; ns.LABELS = g["LABELS"]
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
    draw = int.from_bytes(e17[8:12], "big")            # {enter,exit,DRAW,...}
    others = [int.from_bytes(e17[m*4:m*4+4], "big") for m in (0, 1, 3, 4)]
    check(new_base < draw < new_base + 0x400,
          f"17th entry's DRAW member points into the cave (0x{draw:08x})")
    check(all(o == 0 for o in others),
          "17th entry's enter/exit/key/enc members are 0 (skipped)")

    # the shipped handler bytes still match the source
    import shutil, subprocess, tempfile
    from busscreen_src import HANDLER          # loaded below
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
    check(grown_tree == ref_tree,
          "MAIN MENU tree walks identically to the un-grown image")

    # 4) enter state 16 and confirm the draw handler renders the 12 labels
    from busscreen_src import LABELS
    uc = grown_boot.uc
    if not getattr(grown_boot, "_menu_ready", False):
        emu._prime_menu(grown_boot)
    def u32(a):
        return int.from_bytes(uc.mem_read(a, 4), "big")
    def draw_state_16():
        # MENU_DRAW bails unless the window-context pointer 0x400cbf4c is set;
        # MENU_OPEN toggles it, so open until it is non-zero.
        for _ in range(3):
            if u32(0x400cbf4c) != 0:
                break
            emu._call(uc, emu.MENU_OPEN)
        uc.mem_write(emu.MENU_STATE, (16).to_bytes(4, "big"))
        uc.mem_write(emu.MENU_VIEWPORT, (13).to_bytes(4, "big"))
        grown_boot._draws.clear()
        emu._call(uc, emu.MENU_DRAW)
        return [t for _x, _y, t in grown_boot._draws]
    drawn = draw_state_16()
    want = [s.decode() for s in LABELS]
    check(all(w in drawn for w in want),
          f"state 16 draws all 12 labels (drew {len(drawn)}: {drawn[:14]})")

    if backup is not None:
        IMAGE.write_bytes(backup)       # restore for the rest of make check
    print(f"\n{'FAILED' if fails else 'busscreen step 1 OK'}: "
          f"{len(fails)} failure(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
