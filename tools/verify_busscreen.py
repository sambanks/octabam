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
LEA_SITES = (0x40064bd2, 0x40064e34, 0x400650e6)
DONOR_STATE = 2


def _build(remix):
    env = {**os.environ, "REMIX": remix, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build_bus.py"],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit(f"build {remix} failed:\n{(r.stdout + r.stderr)[-800:]}")


def main():
    import emu_bringup as emu
    import shutil
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

    # the three lea operands now point at the cave, not the stock table
    new_base = rd32(LEA_SITES[0] + 2)
    check(new_base != STATE_TABLE and new_base != 0,
          f"lea[0] repointed off the stock table (-> 0x{new_base:08x})")
    for s in LEA_SITES:
        check(rd32(s + 2) == new_base,
              f"lea at 0x{s:08x} operand -> 0x{new_base:08x}")
        check(img[s - BASE:s - BASE + 2] in
              (b"\x41\xf9", b"\x43\xf9", b"\x45\xf9",
               b"\x47\xf9", b"\x49\xf9", b"\x4b\xf9"),
              f"site 0x{s:08x} is still a lea")

    # the relocated table: 16 stock entries + a 17th = clone of DONOR_STATE
    stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
    st = STATE_TABLE - BASE
    stock_tab = stock[st:st + ENTRY_LEN * ENTRY_N]
    cave = new_base - BASE
    grown = img[cave:cave + ENTRY_LEN * (ENTRY_N + 1)]
    check(grown[:ENTRY_LEN * ENTRY_N] == stock_tab,
          "16 stock entries copied verbatim into the cave")
    donor = stock_tab[DONOR_STATE * ENTRY_LEN:(DONOR_STATE + 1) * ENTRY_LEN]
    check(grown[ENTRY_LEN * ENTRY_N:] == donor,
          f"17th entry is a byte-clone of state {DONOR_STATE}")

    # 3) it still boots and the menu tree is identical
    grown_boot = emu.boot(str(IMAGE))
    check(grown_boot.clean,
          f"grown image boots to the RTOS handoff ({grown_boot.stopped})")
    grown_tree = emu.read_menu_tree(grown_boot.uc)
    check(grown_tree == ref_tree,
          "MAIN MENU tree walks identically to the un-grown image")

    if backup is not None:
        IMAGE.write_bytes(backup)       # restore for the rest of make check
    print(f"\n{'FAILED' if fails else 'busscreen step 1 OK'}: "
          f"{len(fails)} failure(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
