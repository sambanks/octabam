#!/usr/bin/env python3
"""verify_core -- the CORE module applies the card's knob defaults.

    python3 tools/verify/verify_core.py [REMIX] [--project DIR]

Builds REMIX (default `core`: the rig plus CORE, without FX2 LOCK), stages
the project with OCTABAM/card.work and card.strd written by
tools/hw/ot_store.py, and under the port selects T2's effect through the
FX2 chooser (SEND -> stock DELAY) and the FX1 chooser (SPECTRUM ->
CHARACTER), as tools/verify/verify_descdefaults.py does. Each case reads
the core's counters after the load (core_counts, by symbol) and the live
lane at the end:

  none          no file on the card: the image's defaults; state fresh
  work          card.work with DELAY and CHARACTER defaults (one value
                outside its count): those knobs land, the rest stay the
                image's, the outside value is skipped; state card.work
  recover       card.work damaged, card.strd valid: card.strd's values;
                state recovered
  damaged       card.work damaged, no card.strd: the image's defaults;
                state damaged
  layout        a record whose layout hash is not the image's: skipped
  duplicate     two records for DELAY: neither applied

What it cannot see: the unit's card I/O timing, a power-up with no LOAD
PROJECT post (the bank-load hook), the new-part initialiser.
"""
import argparse, os, pathlib, shutil, struct, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import obam, registry, store  # noqa: E402
import ot_store  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
ELF = ROOT / "out/platform/runtime/runtime.elf"
OUT = ROOT / "out/coreverify"
BASE = 0x40000400
LANES, IDS = 0x80000810, 0x80000ec4
FX2_TABLE, FX1_TABLE = 0x400d5fdc, 0x400d5f58
K = dict(no=0x32, fx1=0x25, fx2=0x26, down=0x20, yes=0x31, t2=0x11)
PAGE = {"fx1": (0x12, 0x32, 0), "fx2": (0x18, 0x38, 8)}
COUNTERS = ("loads", "state", "records", "applied", "values", "skip_id", "skip_layout",
            "skip_mode", "skip_crc", "skip_dup", "skip_value")
STATES = {0: "fresh", 1: "card.work", 2: "recovered", 3: "damaged"}


def script(page):
    t, lines = 1500, []

    def tap(k, gap=250):
        nonlocal t
        lines.append(f"{t} key {K[k]:#x} down"); t += 40
        lines.append(f"{t} key {K[k]:#x} up"); t += gap
    tap("no", 400); tap("t2", 400); tap(page, 160); tap(page, 800); tap("down", 600); tap("yes", 1200)
    lines.append(f"{t} quit")
    return "\n".join(lines) + "\n"


def symbol(name):
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    for line in subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == name:
            return int(parts[0], 16)
    sys.exit(f"verify_core: {name} not in {ELF}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="core")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="CORESET")       # not OCTABAM: that is the store's directory
    ap.add_argument("--name", default="COREPROJ")
    a = ap.parse_args()
    project = a.project
    if not project and pathlib.Path("~/.octabam_project").expanduser().is_file():
        project = pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
    if not project:
        print("  [SKIP] verify_core: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_core: no port binary (make emu-cf)"); return 0
    r = subprocess.run([sys.executable, str(ROOT / "modules/core/generate_core.py"), "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    print(f"  [{'ok' if r.returncode == 0 else 'FAIL'}] modules/core/core.s is core.c + hooks.s compiled  {(r.stdout + r.stderr).strip()}")
    if r.returncode:
        return 1
    remix = registry.remix(a.remix)
    if "CORE" not in remix.modules:
        print(f"  [ -- ] verify_core: {a.remix} carries no CORE"); return 0
    mods = registry.bound(remix)
    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "mainos.bin"
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_core: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    counts_at = symbol("core_counts")
    img = image.read_bytes()

    def rd(addr, n):
        return img[addr - BASE:addr - BASE + n]

    def page_of(table, fx):
        P = struct.unpack(">I", rd(table + 4 * fx, 4))[0]
        return P, rd(P + 0x5e, 12), struct.unpack(">12I", rd(P + 0x9a, 48))

    pdir = pathlib.Path(project).expanduser()
    copy = OUT / "project"
    shutil.rmtree(copy, ignore_errors=True)
    copy.mkdir(parents=True)
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)

    delay, character = mods["DELAY"], mods["CHARACTER"]
    want = {"DELAY": {"TIME": 52, "FB": 5, "X": 1, "TAPE": 0}, "CHARACTER": {"DRV": 9, "MIX": 77}}
    work = ot_store.set_default(None, delay, want["DELAY"])
    work = ot_store.set_default(work, character, want["CHARACTER"])
    # a value outside its count: DELAY's SYNC (slot 9) has two values
    f = obam.parse(work)
    rec = next(r for r in f.records if r.store_id == store.fx_store_id(delay))
    rec.replace(store.fx_keys(delay)[9], obam.BYTE, b"\x05")
    work = f.encode()
    strd = ot_store.set_default(None, delay, {"TIME": 33})
    bad_layout = obam.File(obam.CARD_WORK, [obam.Record(obam.DEFAULT, store.fx_store_id(delay), payload=obam.prefix_bytes(
        obam.DEFAULT, layout=store.fx_layout(delay) ^ 1) + obam.Value(1, obam.BYTE, b"\x11").encode())]).encode()
    dup = obam.parse(ot_store.set_default(None, delay, {"TIME": 40}))
    dup.records.append(dup.records[0])
    dup = dup.encode()
    damaged = work[:-3] + b"xyz"

    cases = {
        "none": {}, "work": {"card.work": work}, "recover": {"card.work": damaged, "card.strd": strd},
        "damaged": {"card.work": damaged}, "layout": {"card.work": bad_layout}, "duplicate": {"card.work": dup},
    }
    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    for name, files in cases.items():
        roots = []
        for fn, data in files.items():
            p = OUT / f"{name}_{fn}"
            p.write_bytes(data)
            roots += ["--root-file", f"{p}:OCTABAM/{fn}"]
        card = OUT / f"{name}.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{name}"), "--out", str(card), *roots],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_core: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        lanes = {}
        for page in ("fx2", "fx1"):
            sp, dump, cdump, log, c = (OUT / f"{page}.script", OUT / f"{name}_{page}.bin",
                                       OUT / f"{name}_{page}_counts.bin", OUT / f"{name}_{page}.txt",
                                       OUT / f"{name}_{page}_run.img")
            sp.write_text(script(page))
            shutil.copy2(card, c)
            cmd = [EMU, "--image", image, "--card", c, "--set", a.set_name, "--project", a.name,
                   "--load-ms", "90000", "--mkii", "--live-script", sp,
                   "--step", f"-:dump:{counts_at:#x},{4 * len(COUNTERS)}={cdump}",
                   "--mem-dump", f"{LANES:#x},{IDS + 16 - LANES}={dump}"]
            with open(log, "w") as fh:
                fh.write(" ".join(map(str, cmd)) + "\n"); fh.flush()
                r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
            if r.returncode or "ended on quit" not in log.read_text() or not cdump.exists():
                sys.exit(f"verify_core: ot_emu did not finish -- {log}")
            m = dump.read_bytes()
            lanes[page] = (m[IDS - LANES:], m[72:144])
            counts = dict(zip(COUNTERS, struct.unpack(f">{len(COUNTERS)}I", cdump.read_bytes())))
        print(f"  {name}: counters {counts}")
        state = STATES.get(counts["state"], counts["state"])

        def landed(page):
            ids, lane = lanes[page]
            p1, p2, row = PAGE[page]
            fx = ids[row + 1]
            P, defaults, cnt = page_of(FX2_TABLE if page == "fx2" else FX1_TABLE, fx)
            return fx, defaults, lane[p1:p1 + 6] + lane[p2:p2 + 6]

        fx2, d2, got2 = landed("fx2")
        fx1, d1, got1 = landed("fx1")
        check(f"{name}: the selects land DELAY (0x08) and CHARACTER (0x1c)  0x{fx2:02x} 0x{fx1:02x}",
              (fx2, fx1) == (0x08, 0x1c))
        check(f"{name}: the core ran at the load ({counts['loads']} call(s))", counts["loads"] >= 1)

        def expect(defaults, m, values):
            out = bytearray(defaults)
            for knob, v in values.items():
                out[[p.name for p in m.params].index(knob.encode())] = v
            return bytes(out)
        if name in ("none", "damaged", "layout", "duplicate"):
            exp2, exp1 = d2, d1
        elif name == "work":
            exp2, exp1 = expect(d2, delay, want["DELAY"]), expect(d1, character, want["CHARACTER"])
        else:
            exp2, exp1 = expect(d2, delay, {"TIME": 33}), d1
        check(f"{name}: DELAY's page  {got2.hex(' ')}  (expected {exp2.hex(' ')})", got2 == exp2)
        check(f"{name}: CHARACTER's page  {got1.hex(' ')}  (expected {exp1.hex(' ')})", got1 == exp1)
        want_state = {"none": "fresh", "work": "card.work", "recover": "recovered", "damaged": "damaged",
                      "layout": "card.work", "duplicate": "card.work"}[name]
        check(f"{name}: state {state}", state == want_state)
        if name == "work":
            check(f"{name}: the value outside its count skipped ({counts['skip_value']})", counts["skip_value"] == 1)
        if name == "layout":
            check(f"{name}: the record with another layout skipped ({counts['skip_layout']})", counts["skip_layout"] == 1)
        if name == "duplicate":
            check(f"{name}: both copies refused ({counts['skip_dup']})", counts["skip_dup"] == 2)
    print(f"verify_core: {'ok' if not fails else 'FAILED'} ({fails} failure(s)) -- {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
