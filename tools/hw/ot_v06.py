#!/usr/bin/env python3
"""v0.6 unit checks that need no panel step: REMIX SWITCH boots and USB DISK MODE reads, over REMOTE.

    python3 tools/hw/ot_v06.py switch  --names "A.RMX,B.RMX" [--cycles 20]
    python3 tools/hw/ot_v06.py diskread [--file PATH] [--reads 6]
    python3 tools/hw/ot_v06.py run     --names "A.RMX,B.RMX" [--cycles 20] [--label NAME]

`switch` boots the names in turn with `ot_card.py boot` (COMMAND 3; each attempt is a line of
out/hw/boot_ledger.tsv) and after each return reads MB_PARK (0x41200038: bit 0 core 0, bit 1 core 1,
modules/remix-switch/osw.inc) and LOAD METER's health. It fails on a boot that does not return, a fall-back to
another image, MB_PARK other than 3, or a DSP that is not counting. #1233 and #1272 (REMIX SWITCH) and #1247 are
answered by this run: a boot that does not return means the unit is on the boot screen and needs a power-cycle,
and the run stops there.

`diskread` enters DISK MODE (COMMAND 1) and reads one card file --reads times in 64 KB blocks, then leaves
(COMMAND 2). It fails when a block differs between reads or a block starts with `0f f8 00 00` that no other read
has there (#1264: a USB MIDI clock packet written over the mass-storage read buffer, about 2 % of blocks with
CLOCK SEND on). The file must be larger than 128 sectors (64 KB); default: the largest file under
/Volumes/OCTATRACK/PRESETS. The corruption needs the unit to be sending USB MIDI clock, so the project's CLOCK SEND
must be on and the sequencer playing when COMMAND 1 is sent.

`run` is `switch`, then `diskread`, then `switch` again, and writes out/hw/v06/<label>/summary.json.

macOS only (ot_card.py: diskutil, /Volumes/OCTATRACK). Needs an image with REMOTE, STORE, USB and REMIX SWITCH,
and every name in /BRAIN/REMIXES (`ot_card.py copy`).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ot_card  # noqa: E402
import ot_events as ev  # noqa: E402

MB_PARK = 0x41200038
BLOCK = 64 * 1024
MARK = bytes.fromhex("0ff80000")


def health(u):
    import load_meter
    try:
        return load_meter.healthy(u.dev)
    except (SystemExit, Exception) as e:  # noqa: BLE001
        return False, str(e)


def switch(names, cycles):
    """Boot `names` round-robin for `cycles` boots. Returns (rows, ok); stops at the first boot that does not return."""
    rows, ok = [], True
    for i in range(cycles):
        name = names[i % len(names)]
        t0 = time.monotonic()
        r = subprocess.run([sys.executable, os.path.join(HERE, "ot_card.py"), "boot", name], cwd=ROOT,
                           capture_output=True, text=True)
        row = dict(n=i + 1, name=name, rc=r.returncode, seconds=round(time.monotonic() - t0),
                   tail=(r.stdout + r.stderr).strip().splitlines()[-3:])
        try:
            u = ot_card.Unit()
            park = int.from_bytes(ev.peek(u.peek1, MB_PARK, 4), "big")
            alive, why = health(u)
            row.update(mb_park=park, counting=alive, health=why)
        except (SystemExit, Exception) as e:  # noqa: BLE001
            row.update(mb_park=None, counting=False, health=f"no reading: {e}")
        row["pass"] = r.returncode == 0 and row["mb_park"] is not None and row["mb_park"] & 3 == 3 and row["counting"]
        rows.append(row)
        print(f"switch {i + 1}/{cycles} {name}: {'PASS' if row['pass'] else 'FAIL'} rc={r.returncode} "
              f"MB_PARK={row['mb_park']} counting={row['counting']} {row['seconds']} s", flush=True)
        if not row["pass"]:
            ok = False
            if "no answer" in " ".join(row["tail"]) or r.returncode:
                print("stopped: the unit may be on the boot screen; power-cycle it and add the ledger line to FAILURE_MODES.md")
                break
    return rows, ok


def largest(root):
    best, size = None, 0
    for d, _, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            if not f.startswith("._") and os.path.getsize(p) > size:
                best, size = p, os.path.getsize(p)
    return best, size


def blocks(path):
    out = []
    with open(path, "rb") as f:
        while True:
            b = f.read(BLOCK)
            if not b:
                return out
            out.append((hashlib.sha1(b).hexdigest(), b[:4]))


def diskread(path, reads):
    u = ot_card.Unit()
    ot_card.enter_disk(u)
    try:
        if path is None:
            path, size = largest(os.path.join(ot_card.CARD, "PRESETS"))
        if path is None or os.path.getsize(path) <= BLOCK:
            return dict(file=path, pass_=False, why="no card file larger than 64 KB"), False
        runs = []
        for _ in range(reads):
            subprocess.run(["purge"], capture_output=True)      # drop the Mac's cache so the next read reaches the unit
            runs.append(blocks(path))
        n = len(runs[0])
        differ = [i for i in range(n) if len({r[i][0] for r in runs}) > 1]
        marked = [i for i in range(n) if any(r[i][1] == MARK for r in runs) and len({r[i][1] for r in runs}) > 1]
        res = dict(file=path, bytes=os.path.getsize(path), blocks=n, reads=reads, differing_blocks=differ,
                   marked_blocks=marked, pass_=not differ and not marked)
    finally:
        ot_card.leave_disk(u)
    print(f"diskread {path}: {n} blocks x {reads} reads, {len(differ)} differing, {len(marked)} with 0f f8 00 00 in one read only: "
          f"{'PASS' if res['pass_'] else 'FAIL'}", flush=True)
    return res, res["pass_"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("switch", "run"):
        p = sub.add_parser(n)
        p.add_argument("--names", required=True, help="comma-separated .RMX names in /BRAIN/REMIXES")
        p.add_argument("--cycles", type=int, default=20)
        if n == "run":
            p.add_argument("--file")
            p.add_argument("--reads", type=int, default=6)
            p.add_argument("--label", default=time.strftime("%Y%m%d-%H%M%S"))
    p = sub.add_parser("diskread")
    p.add_argument("--file")
    p.add_argument("--reads", type=int, default=6)
    a = ap.parse_args()
    if a.cmd == "switch":
        return 0 if switch(a.names.split(","), a.cycles)[1] else 1
    if a.cmd == "diskread":
        return 0 if diskread(a.file, a.reads)[1] else 1
    names = a.names.split(",")
    summary, ok = {}, True
    for step, fn in (("switch-1", lambda: switch(names, a.cycles)), ("diskread", lambda: diskread(a.file, a.reads)),
                     ("switch-2", lambda: switch(names, a.cycles))):
        summary[step], good = fn()
        ok &= good
        if not good and step.startswith("switch"):
            break
    d = os.path.join(ROOT, "out", "hw", "v06", a.label)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(f"{'PASS' if ok else 'FAIL'}: {d}/summary.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
