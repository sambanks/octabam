#!/usr/bin/env python3
"""Ask the firmware what it prints for every value of every stock select.

    .venv/bin/python3 tools/stock_labels.py          # -> tools/remix/stock_labels.json
    .venv/bin/python3 tools/stock_labels.py --check  # JSON still matches the firmware?

The rig shows a stock effect's knobs read from its descriptor
(tools/remix/stock.py), but a select's VALUES on the unit are words --
FILTER's page-2 Q draws "none|HP|LP|BOTH", CHORUS TAPS "1".."5", DELAY's
switches "OFF"/"ON" -- and those words are not data anywhere in the image.
Each is printed by the slot's "A" display formatter, a ColdFire function
`fmt(char *buf, int value)` (docs/PARAM_PAGES.md section 7). So rather than
hand-decode eleven formatters and keep the table honest by inspection, this
runs each one on the emulated ColdFire (tools/emu_bringup.py's detour call,
the same machine the workbench draws its screens with) for every legal
value and records what it wrote. The result is checked in as JSON because
the emulator lives in the workbench's venv and the registry must load
without it; `--check` (run by the selftest when unicorn is present) proves
the JSON is still what the firmware prints.

Only stepped slots (value count < 128) are covered: a select shows its
labels beside its value; a 0..127 dial with a formatter (a bipolar +/-
knob, say) keeps printing numbers in the rig, as its count is not declared.
"""

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/remix"))

OUT = ROOT / "tools/remix/stock_labels.json"
BASE = 0x40000400
BUF = 0x47f00800          # scratch, well above the detour stack's growth
P_FMT_A = 0x0ca           # per-slot A formatter array, P-relative


def firmware_labels():
    """{module key: {knob name: [label per value]}} straight from the firmware."""
    import emu_bringup as emu
    from remix import stock
    if not emu.HAVE_UNICORN:
        sys.exit("unicorn not installed -- run: make emu-setup")
    r = emu.boot()
    if r.stopped and "trap" not in str(r.stopped).lower() and not getattr(r, "uc", None):
        sys.exit(f"boot did not reach the handoff: {r.stopped}")
    uc = r.uc
    img = stock.STOCK_IMAGE.read_bytes()

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    out = {}
    for m in stock.MODULES:
        P = m.menu.donor_desc + 0x38
        for i, p in enumerate(m.params):
            if not (p.name and p.active and p.count is not None):
                continue
            fmt = rd32(P + P_FMT_A + i * 4)
            labels = []
            for v in range(p.count):
                if fmt == 0:
                    labels.append(str(v))
                    continue
                uc.mem_write(BUF, b"\x00" * 32)
                emu._call(uc, fmt, (BUF, v))
                labels.append(emu._cstr(uc, BUF, 16))
            out.setdefault(m.key, {})[p.name.decode("latin1")] = labels
    return out


def main(argv):
    got = firmware_labels()
    if "--check" in argv:
        have = json.loads(OUT.read_text()) if OUT.exists() else {}
        if have != got:
            for k in sorted(set(have) | set(got)):
                if have.get(k) != got.get(k):
                    print(f"  {k}: json {have.get(k)} != firmware {got.get(k)}")
            sys.exit(f"{OUT.relative_to(ROOT)} does not match the firmware -- "
                     f"regenerate with: {sys.executable} tools/stock_labels.py")
        print(f"{OUT.relative_to(ROOT)}: matches the firmware "
              f"({sum(len(v) for v in got.values())} selects)")
        return 0
    OUT.write_text(json.dumps(got, indent=1) + "\n")
    for k, knobs in got.items():
        for n, labels in knobs.items():
            print(f"  {k:<12} {n:<6} {' | '.join(labels)}")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
