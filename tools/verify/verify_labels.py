#!/usr/bin/env python3
"""Our mode selects print their WORDS on the unit, not their numbers.

    python3 tools/verify/verify_labels.py <remix>

It is the same method tools/build/stock_labels.py uses for the stock selects: the
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
BASE = 0x40000400
FX2_IDS = 0x400d5fdc                        # build_bus.py's own
P_FMT_A = 0x0ca
STOPS = {("SPECTRUM", 7): {0: "LP", 32: "32", 64: "BP", 96: "96", 127: "HP"}}
BUF = 0x47f00800                 # stock_labels' scratch: above the detour stack
IMAGE = pathlib.Path("out/mainos_bus.bin")


def main():
    from remix import registry
    name = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    from remix import booted
    img = booted.image(IMAGE.read_bytes())

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
        P = rd32(FX2_IDS + m.menu.fx2_id * 4)      # the clone, in ROM or the DRAM runtime
        # A BLANKED module (hidden, nowhere on FX1) draws no knobs, and the
        # build gives it no label formatters; the firmware
        # printing plain numbers for its selects is correct, not a failure.
        # (Keep `cloned` unfiltered: ci is the clone's position.)
        if key in remix.blanked:
            continue
        for i, p in enumerate(m.params):
            if not p.prints_labels:
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
    # A registered formatter on a 0..127 knob that prints words at some
    # values and the number elsewhere (Spectrum SHPE, 27 Sep 2026). The MODE
    # formatter is called first with each mode, so its rename cave sets the
    # slot's name as the panel would: the named modes print the words, a
    # mode that names the slot "---" prints the number.
    for (key, slot), want in STOPS.items():
        if key not in cloned or key in remix.blanked:
            continue
        m = mods[key]
        P = rd32(FX2_IDS + m.menu.fx2_id * 4)
        fmt = rd32(P + P_FMT_A + slot * 4)
        mode_fmt = rd32(P + P_FMT_A + m.mode_slot * 4)
        for mode in range(m.params[m.mode_slot].count):
            view = m.view_for(mode)
            hidden = view is not None and view.names.get(slot) == b"---"
            table = {v: str(v) for v in want} if hidden else want
            uc.mem_write(BUF, b"\0" * 32)
            emu._call(uc, mode_fmt, (BUF, mode))
            mname = emu._cstr(uc, BUF, 16)
            got = {}
            for v in table:
                uc.mem_write(BUF, b"\0" * 32)
                emu._call(uc, fmt, (BUF, v))
                got[v] = emu._cstr(uc, BUF, 16)
            checked += 1
            if got != table:
                fails.append(f"{key} slot {slot} in MODE {mname}: firmware prints "
                             f"{got}, want {table}")
            else:
                print(f"  [PASS] {key:13} slot {slot:<2} in {mname:<5} prints "
                      + " | ".join(f"{v}:{t}" for v, t in got.items()))
    for f in fails:
        print(f"  [FAIL] {f}")
    if not checked:
        print(f"  [N/A] {name} has no labelled selects")
    print("OK" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
