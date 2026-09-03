#!/usr/bin/env python3
"""The MODE formatter really does rename its neighbours -- CALLED, not read.

    python3 tools/verify_modenames.py [remix]      (default: bamsep26)

verify_labels' method (PLAN §6), one step further. That file calls each
select's formatter on the emulated ColdFire and compares what it PRINTED with
the manifest, because the words are printed rather than stored. A MODE view
also REWRITES the descriptor, so this calls the formatter with each mode value
in turn and reads the twelve 6-byte name fields back out of the clone.

What it proves, without a flash:
  * every mode's names land in the right slots of the right descriptor;
  * a mode that does NOT rename a slot RESTORES the Param's own name -- the
    trap a sparse table would leave (land on GRAIN, go back to CLEAN, and the
    knob still reads SCAT);
  * an out-of-range mode value (a part stores a raw byte) clamps to mode 0
    rather than indexing off the end of the table.

What it cannot prove: the ORDER the panel draws in. If the names are drawn
before the MODE value is formatted, the rename lands one redraw late. That is
inferred, and the falsifier is on the unit.
"""
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
BASE = 0x40000400
BUF = 0x47f00800
IMAGE = pathlib.Path("out/mainos_bus.bin")
NAMES_AT = 0x4e
NAME_LEN = 6


def main():
    from remix import registry
    import mode_names
    name = sys.argv[1] if len(sys.argv) > 1 else "bamsep26"
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build_bus.py"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    # the clone addresses, from the build's own report
    clones = {}
    for line in r.stdout.splitlines():
        m = re.match(r"\s+(.+?)\s+id 0x[0-9a-f]+\s+clone P=0x([0-9a-f]+)", line)
        if m:
            clones[m.group(1).strip()] = int(m.group(2), 16)
    img = IMAGE.read_bytes()

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    import emu_bringup as emu
    boot = emu.boot(str(IMAGE))
    uc = boot.uc
    mods = registry.modules()
    remix = registry.remix(name)
    fails = 0
    checked = 0
    for key in remix.modules:
        mod = mods.get(key)
        if mod is None or not mod.mode_views or mod.mode_slot is None:
            continue
        want = mode_names.complete(mod)
        if not want:
            continue
        desc = clones.get(key)
        if desc is None:
            print(f"  [FAIL] {key}: no clone address in the build report")
            fails += 1
            continue
        fmt = rd32(desc + 0x0ca + mod.mode_slot * 4)
        labels = mod.params[mod.mode_slot].labels

        def names_now():
            out = {}
            for slot in range(12):
                a = desc + NAMES_AT + slot * NAME_LEN
                raw = bytes(uc.mem_read(a, NAME_LEN))
                out[slot] = raw.split(b"\0")[0].decode("latin1")
            return out

        for value in range(len(labels)):
            emu._call(uc, fmt, (BUF, value))
            got = names_now()
            bad = [(sl, nm.decode("latin1"), got[sl])
                   for sl, nm in want[value].items()
                   if got[sl] != nm.decode("latin1")]
            checked += 1
            if bad:
                fails += 1
                print(f"  [FAIL] {key} mode {value} ({labels[value]}): "
                      + ", ".join(f"slot {sl} should read {w!r}, reads {g!r}"
                                  for sl, w, g in bad))
            else:
                shown = " ".join(f"{sl}:{got[sl]}" for sl in sorted(want[value]))
                print(f"  [PASS] {key} mode {value} ({labels[value]:<5}) "
                      f"renames {shown}")
        # a part stores a RAW byte, so a value past the count must clamp
        emu._call(uc, fmt, (BUF, 200))
        got = names_now()
        bad = [sl for sl, nm in want[0].items()
               if got[sl] != nm.decode("latin1")]
        checked += 1
        if bad:
            fails += 1
            print(f"  [FAIL] {key}: an out-of-range mode leaves slots {bad} "
                  f"renamed by whatever ran last")
        else:
            print(f"  [PASS] {key}: mode 200 clamps to mode 0's names")
    if not checked:
        sys.exit(f"{name}: no module in this remix declares mode_views")
    print(f"\n{fails} of {checked} checks failed" if fails
          else f"\nOK ({checked} checks)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
