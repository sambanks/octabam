#!/usr/bin/env python3
"""The MODE formatter really does rename its neighbours -- CALLED, not read.

    python3 tools/verify/verify_modenames.py [remix]      

verify_labels' method, one step further. That file calls each
select's formatter on the emulated ColdFire and compares what it PRINTED with
the manifest, because the words are printed rather than stored. A MODE view
also REWRITES the descriptor, so this calls the formatter with each mode value
in turn and reads the twelve 6-byte name fields back out of the clone.

What it proves, without a flash:
  * every mode's names land in the right slots of the right descriptor;
  * a mode that does NOT rename a slot RESTORES the Param's own name -- the
    trap a sparse table would leave (land on GRAIN, go back to CLEAN, and the
    knob still reads SCTR);
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
BASE = 0x40000400
BUF = 0x47f00800
IMAGE = pathlib.Path("out/mainos_bus.bin")
NAMES_AT = 0x16          # P-relative: P + 0x16 = E + 0x4e (P = E + 0x38); 0x4e here was the 13 Sep 2026 bug
NAME_LEN = 6


def main():
    from remix import registry
    import mode_names
    name = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    # the clone addresses, from the build's own report
    clones, targets = {}, {}
    for line in r.stdout.splitlines():
        m = re.match(r"\s+(.+?)\s+id 0x[0-9a-f]+\s+clone P=0x([0-9a-f]+)", line)
        if m:
            clones[m.group(1).strip()] = int(m.group(2), 16)
        # a host_slots module's MODE cave renames the screen's own table
        m = re.match(r"\s+(.+?) MODE renames -> \w+ 0x([0-9a-f]+)", line)
        if m:
            targets[m.group(1).strip()] = int(m.group(2), 16)
    from remix import booted
    img = booted.image(IMAGE.read_bytes())

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    # each clone where the unit finds it: FX2_IDS[id] (ROM, or the DRAM runtime)
    for key in list(clones):
        _m = registry.modules().get(key)
        if _m is not None and _m.menu is not None:
            clones[key] = rd32(0x400d5fdc + _m.menu.fx2_id * 4)

    import emu_bringup as emu
    boot = emu.boot(str(IMAGE))
    uc = boot.uc
    mods = registry.modules()
    remix = registry.remix(name)
    fails = 0
    checked = 0
    work = []
    for key in remix.modules:
        mod = mods.get(key)
        if mod is None or mod.menu is None or getattr(mod, "is_stock", False):
            continue          # a stock effect keeps its own descriptor: no clone, no cave
        # A BLANKED module (hidden, nowhere on FX1) draws no knobs and gets
        # no formatter from the build, so there is nothing to
        # rename on its page; the bus screen prints its own mode words.
        if key in remix.blanked:
            continue
        for slot, prm in enumerate(mod.params):
            if not prm.prints_labels:
                continue
            views = mod.name_views_for(slot)
            if slot == mod.mode_slot:
                want = mode_names.complete(mod, slot, views) if views else {}
                want = mode_names.with_selfname(want, slot, prm.labels)
            elif views:
                want = mode_names.complete(mod, slot, views)
            else:
                # only the MODE select names itself (image 27); every other
                # labelled select renames NOTHING at any value (the tick
                # widget flashes the word). Its own slot's name is whatever
                # the MODE view last set -- `---` where the mode does not
                # read it (20 Sep 2026) -- so the check is "unchanged", not
                # "the Param's own name".
                want = None
            work.append((key, mod, slot, want))
    for key, mod, slot, want in work:
        desc = clones.get(key)
        if desc is None:
            print(f"  [FAIL] {key}: no clone address in the build report")
            fails += 1
            continue
        fmt = rd32(desc + 0x0ca + slot * 4)
        labels = mod.params[slot].labels
        nhost = dict(remix.host_slots).get(key)
        knob = ([(p.name or b"") if i < nhost else b"" for i, p in enumerate(mod.params)]
                if nhost is not None else None)
        if knob is not None and key not in targets:
            print(f"  [FAIL] {key}: host_slots, but the build reported no rename target")
            fails += 1
            continue
        table = targets[key] if knob is not None else desc + NAMES_AT

        def page_names():
            return [bytes(uc.mem_read(desc + NAMES_AT + s * NAME_LEN, NAME_LEN)).split(b"\0")[0]
                    for s in range(12)]

        def names_now():
            out = {}
            for slot in range(12):
                a = table + slot * NAME_LEN
                raw = bytes(uc.mem_read(a, NAME_LEN))
                out[slot] = raw.split(b"\0")[0].decode("latin1")
            return out

        if want is None:
            before = names_now()
            for value in list(range(len(labels))) + [200]:
                emu._call(uc, fmt, (BUF, value))
                got = names_now()
                checked += 1
                changed = [sl for sl in range(12) if got[sl] != before[sl]]
                if changed:
                    fails += 1
                    print(f"  [FAIL] {key} slot {slot} value {value}: a non-MODE select renamed slots {changed}")
                else:
                    print(f"  [PASS] {key} slot {slot} value {value} ({labels[value] if value < len(labels) else 'out of range':<5}) renames nothing")
            continue
        for value in range(len(labels)):
            emu._call(uc, fmt, (BUF, value))
            got = names_now()
            bad = [(sl, nm.decode("latin1"), got[sl])
                   for sl, nm in want[value].items()
                   if got[sl] != nm.decode("latin1")]
            checked += 1
            if bad:
                fails += 1
                print(f"  [FAIL] {key} slot {slot} value {value} ({labels[value]}): "
                      + ", ".join(f"slot {sl} should read {w!r}, reads {g!r}"
                                  for sl, w, g in bad))
            else:
                shown = " ".join(f"{sl}:{got[sl]}" for sl in sorted(want[value]))
                print(f"  [PASS] {key} slot {slot} value {value} ({labels[value]:<5}) "
                      f"names {shown}")
        if knob is not None:
            got = page_names()
            checked += 1
            if got != knob:
                fails += 1
                print(f"  [FAIL] {key}: after every MODE value the host page's names are "
                      + " ".join(n.decode('latin1') or '-' for n in got))
            else:
                print(f"  [PASS] {key}: the host page still reads {' '.join(n.decode('latin1') for n in knob if n)} alone "
                      f"(the renames went to 0x{table:08x})")
        # a part stores a RAW byte, so a value past the count must clamp
        emu._call(uc, fmt, (BUF, 200))
        got = names_now()
        bad = [sl for sl, nm in want[0].items()
               if got[sl] != nm.decode("latin1")]
        checked += 1
        if bad:
            fails += 1
            print(f"  [FAIL] {key} slot {slot}: an out-of-range value leaves slots {bad} "
                  f"renamed by whatever ran last")
        else:
            print(f"  [PASS] {key} slot {slot}: value 200 clamps to value 0's names")
    if not checked:
        print(f"  [ -- ] {name} has no labelled select -- nothing to check")
        return 0
    print(f"\n{fails} of {checked} checks failed" if fails
          else f"\nOK ({checked} checks)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
