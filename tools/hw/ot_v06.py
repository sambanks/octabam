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

`suite` runs everything, in this order, stopping at the first failure that needs a power-cycle:
  for each of V06_OCT on `OCTABAM T1`, V06_RIG on `V06-RIG T1`, V06_VRB on `OCTABAM-VRB T1`: boot the image (a
  switch, with MB_PARK and the health check), load the project over DISK MODE, run `ot_matrix.py run` on it; then
  `diskread`, then 12 more boots round the three images. The projects come from `ot_v06_build.py build`.
  A layout fails on CRASH, FREEZE, UNHEALTHY, OVERLOAD, DROPS, NO AUDIO CAPTURED, or any other flag ot_matrix
  raises (CLICKS, ROUGH, RINGS: a tail still sounding after STOP, LEVEL, ...); a machine slot also fails below
  -70 dBFS RMS (the machine did not play).

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


def diskread(path, reads, play=True):
    """With `play`, the unit is started first on a host clock (the project has CLOCK SEND on and clock and transport
    receive on), so it is sending USB MIDI clock when COMMAND 1 is sent."""
    import ot_ladder
    clock = ot_ladder.Clock(120.0, "Octatrack") if play else None
    if clock:
        clock.start()
        time.sleep(2.0)
    u = ot_card.Unit()
    try:
        ot_card.enter_disk(u)
    except BaseException:
        if clock:
            clock.stop()
            clock.close()
        raise
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
        if clock:
            clock.stop()
            clock.close()
        ot_card.leave_disk(u)
    print(f"diskread {path}: {n} blocks x {reads} reads, {len(differ)} differing, {len(marked)} with 0f f8 00 00 in one read only: "
          f"{'PASS' if res['pass_'] else 'FAIL'}", flush=True)
    return res, res["pass_"]


IMAGES = (("V06_OCT", "OCTABAM T1.RMX"), ("V06_RIG", "V06-RIG T1.RMX"), ("V06_VRB", "OCTABAM-VRB T1.RMX"))
FATAL = {"CRASH", "FREEZE", "UNHEALTHY", "OVERLOAD", "DROPS", "NO AUDIO CAPTURED"}
SILENT_DB = -70.0
PROJECT = "RMT_SFX_01"


def sh(*args):
    return subprocess.run([sys.executable, *map(str, args)], cwd=ROOT).returncode


def judge_rows(results, plan):
    """[(slot name, issues)] for one ot_matrix report: every flag, and a machine slot below SILENT_DB."""
    kinds = {e["name"]: e.get("kind") for e in plan["layouts"]}
    out = []
    for r in results:
        why = list(r["flags"])
        m = r.get("metrics") or {}
        if kinds.get(r["name"]) == "machine" and m.get("rms_db") is not None and m["rms_db"] < SILENT_DB:
            why.append(f"SILENT {m['rms_db']:.0f} dBFS")
        out.append((r["name"], why))
    return out


def suite(a):
    dest = os.path.abspath(a.dest)
    with open(os.path.join(dest, "v06.json")) as f:
        projects = json.load(f)
    summary, ok = {}, True
    names = [img for _p, img in IMAGES]
    for proj, img in IMAGES:
        step = {"image": img}
        summary[proj] = step
        if sh(os.path.join(HERE, "ot_card.py"), "boot", img):
            step["boot"] = "FAIL"
            ok = False
            print(f"{proj}: boot of {img} failed: stopped (power-cycle the unit if it is on the boot screen)")
            break
        step["boot"] = "ok"
        if sh(os.path.join(HERE, "ot_card.py"), "load", projects[proj]["dir"], "--name", PROJECT):
            step["load"] = "FAIL"
            ok = False
            break
        label = f"{a.label}-{proj}"
        rc = sh(os.path.join(HERE, "ot_matrix.py"), "run", projects[proj]["dir"], label)
        with open(os.path.join(ROOT, "out", "hw", "matrix", label, "report.json")) as f:
            report = json.load(f)
        with open(os.path.join(projects[proj]["dir"], "OCTABAM_MATRIX.json")) as f:
            plan = json.load(f)
        rows = judge_rows(report["results"], plan)
        step["layouts"] = {n: w or "ok" for n, w in rows}
        step["ran"] = len(rows)
        step["planned"] = len(plan["layouts"])
        bad = [(n, w) for n, w in rows if w]
        step["pass"] = not bad and len(rows) == len(plan["layouts"]) and rc in (0, 1)
        for n, w in rows:
            print(f"  {proj} {n}: {' '.join(w) or 'ok'}")
        if not step["pass"]:
            ok = False
            if any(set(w) & FATAL for _n, w in bad):
                print("a fatal flag: stopped")
                break
    else:
        summary["diskread"], good = diskread(None, a.reads)
        ok &= good
        rows, good = switch(names, a.cycles)
        summary["switch"] = rows
        ok &= good
    d = os.path.join(ROOT, "out", "hw", "v06", a.label)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(f"{'PASS' if ok else 'FAIL'}: {d}/summary.json")
    return 0 if ok else 1


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
    p = sub.add_parser("suite")
    p.add_argument("--dest", default=os.path.join(ROOT, "out", "v06b"))
    p.add_argument("--cycles", type=int, default=12)
    p.add_argument("--reads", type=int, default=6)
    p.add_argument("--label", default=time.strftime("%Y%m%d-%H%M%S"))
    p = sub.add_parser("diskread")
    p.add_argument("--file")
    p.add_argument("--reads", type=int, default=6)
    a = ap.parse_args()
    if a.cmd == "switch":
        return 0 if switch(a.names.split(","), a.cycles)[1] else 1
    if a.cmd == "suite":
        return suite(a)
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
