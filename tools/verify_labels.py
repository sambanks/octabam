#!/usr/bin/env python3
"""Our mode selects print their WORDS on the unit, not their numbers.

    python3 tools/verify_labels.py [remix]        (default: bus)

PLAN §6's gate. `Param.labels` used to be authored, schema-checked and then
never read -- the panel drew `1 2 3` where the manifest said FOLD RING BOTH.
The build now plants a small ColdFire formatter per labelled select
(tools/label_fmt.py) and registers it as that slot's "A" callback, so this
asks the FIRMWARE what each one prints and compares it with the manifest.

It is the same method tools/stock_labels.py uses for the stock selects: the
words are PRINTED, not stored, so the only honest way to read them back is to
call the formatter. Everything here runs on the emulated ColdFire -- no flash.

Also checked: an OUT-OF-RANGE value. A part stores the raw byte, so a saved
project can hand a select a value past its count; the formatter clamps to
label 0 rather than indexing off the end of its table.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
BASE = 0x40000400
CLONE_BASE, CLONE_STRIDE = 0x400d6b20, 0x1a0
P_FMT_A = 0x0ca
BUF = 0x47f00800                 # stock_labels' scratch: above the detour stack
IMAGE = pathlib.Path("out/mainos_bus.bin")


def main():
    from remix import registry
    name = sys.argv[1] if len(sys.argv) > 1 else "bus"
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build_bus.py"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    img = IMAGE.read_bytes()

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    import emu_bringup as emu
    boot = emu.boot(str(IMAGE))
    uc = boot.uc
    mods = registry.modules()
    remix = registry.remix(name)
    cloned = [k for k in remix.modules if not mods[k].is_stock
              and mods[k].menu is not None]
    fails, checked = [], 0
    for ci, key in enumerate(cloned):
        m = mods[key]
        P = CLONE_BASE + ci * CLONE_STRIDE
        # A BLANKED module (hidden, nowhere on FX1) draws no knobs, and the
        # build gives it no label formatters (5 Sep 2026); the firmware
        # printing plain numbers for its selects is correct, not a failure.
        # (Keep `cloned` unfiltered: ci is the clone's position.)
        if key in remix.hidden and key not in remix.fx1:
            continue
        for i, p in enumerate(m.params):
            if not (p.active and p.labels):
                continue
            fmt = rd32(P + P_FMT_A + i * 4)
            got = []
            for v in range(len(p.labels)):
                uc.mem_write(BUF, b"\0" * 32)
                emu._call(uc, fmt, (BUF, v))
                got.append(emu._cstr(uc, BUF, 16))
            checked += 1
            if tuple(got) != tuple(p.labels):
                fails.append(f"{key} slot {i} {p.name.decode('latin1')}: "
                             f"firmware prints {got}, manifest says "
                             f"{list(p.labels)}")
                continue
            # A part stores the raw byte, so a value past the count is
            # reachable from a saved project. It must clamp, not index off
            # the end of the table into whatever follows the cave.
            uc.mem_write(BUF, b"\0" * 32)
            emu._call(uc, fmt, (BUF, 200))
            over = emu._cstr(uc, BUF, 16)
            if over != p.labels[0]:
                fails.append(f"{key} slot {i} {p.name.decode('latin1')}: "
                             f"value 200 printed {over!r}, not the clamped "
                             f"{p.labels[0]!r}")
                continue
            print(f"  [PASS] {key:13} slot {i:<2} "
                  f"{p.name.decode('latin1'):<5} prints {' | '.join(got)}")
    for f in fails:
        print(f"  [FAIL] {f}")
    if not checked:
        print(f"  [SKIP] {name} has no labelled selects")
    print("OK" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
