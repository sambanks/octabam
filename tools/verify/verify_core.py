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
  stock clamps  out-of-count bytes in every Part of every bank (T1 BusDelay
                MODE 64 and SIZE 100; SPECTRUM MODE 90 on FX1 of T2-4, T6, T7)
                read count - 1 after the load: stock's Part validator does it,
                which is why the core has no clamp
  save          SAVE AS DEFAULT: core_save_default for T1's FX2 (BusDelay) and
                T2's FX1 (SPECTRUM), then core_card_store, on a card whose
                card.work holds other records: the two records carry the live
                pages' bytes, the others keep their bytes, card.strd is
                card.work; a second boot of that card puts the saved values
                on both descriptors
  menu          the OCTABAM category on the panel: T1, the FX2 page, PROJ,
                DOWN x4, RIGHT, YES on SAVE AS DEFAULT: card.work holds T1's
                FX2 page; then OK, DOWN, YES on CLEAR DEFAULT: no BusDelay
                record left
  mode          a GRAIN record for BusDelay (T1): the FX2 page-2 editor moves
                MODE CLEAN -> GRAIN (verify_modedefaults' call) and MODE
                DEFAULTS lands GRAIN's view with the card's values for the
                slots the view lists; a slot it does not list is skipped

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
            "skip_mode", "skip_crc", "skip_dup", "skip_value", "skip_slot")
FX2_EDITOR = 0x4003a9dc
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
    # FX2 LOCK's poke undone in RAM, so the FX2 chooser's YES selects
    unlock = (["--poke", ";".join(f"{0x400bc374 + i:#x}={b:#x}" for i, b in enumerate(bytes.fromhex("40052474")))]
              if "FX2 LOCK" in remix.modules else [])
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
                   "--load-ms", "90000", "--mkii", "--live-script", sp, *unlock,
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
    # ---- stock clamps: why the core has no clamp of its own ----------------
    # The Part validator 0x40002318 rewrites every FX page byte outside its
    # descriptor's [min, min + count - 1] to the nearer end during the load
    # (STORE.md section 8). Planted out-of-count bytes in every Part of every
    # bank must read count - 1 after the load.
    import ot_project
    sp = mods["SPECTRUM"]
    bd = mods["DELAY SERVER"]
    ccopy = OUT / "project_clamp"
    shutil.rmtree(ccopy, ignore_errors=True)
    shutil.copytree(copy, ccopy)
    b1 = [p.default for p in bd.params[:6]]; b2 = [p.default for p in bd.params[6:12]]
    s1 = [p.default or 0 for p in sp.params[:6]]; s2 = [p.default or 0 for p in sp.params[6:12]]
    b2[0], b2[3], s2[0] = 64, 100, 90
    ot_project.set_fx(ccopy, "fx2", 1, "DELAY SERVER", page=b1, page2=b2, guard=False)
    for tr in (2, 3, 4, 6, 7):
        ot_project.set_fx(ccopy, "fx1", tr, "SPECTRUM", page=s1, page2=s2, guard=False)
    card = OUT / "clamp.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(ccopy), a.set_name, a.name,
                        "--tree", str(OUT / "tree_clamp"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_core: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    # docs/firmware/PARTS.md section 1: working Parts, then the saved ones
    # after the unsaved-bits byte
    BANKS, STRIDE, PLEN = 0x400e21e0, 0x9b340, 6322

    def part_base(p):
        return (0x8ed80 + p * PLEN) if p < 4 else (0x9504a + (p - 4) * PLEN)
    # (track, FX1 0 / FX2 6, page-2 slot, value count)
    planted = [(1, 6, 0, 3), (1, 6, 3, 4)] + [(tr, 0, 0, 4) for tr in (2, 3, 4, 6, 7)]
    c = OUT / "clamp_run.img"
    shutil.copy2(card, c)
    banks = OUT / "clamp_banks.bin"
    cmd = [EMU, "--image", image, "--card", c, "--set", a.set_name, "--project", a.name,
           "--mount", "--load-ms", "90000", "--step", f"-:dump:{BANKS:#x},{16 * STRIDE}={banks}"]
    log = OUT / "clamp.txt"
    with open(log, "w") as fh:
        fh.write(" ".join(map(str, cmd)) + "\n"); fh.flush()
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    if r.returncode or not banks.exists():
        sys.exit(f"verify_core: the clamp run did not finish -- {log}")
    m = banks.read_bytes()
    wrong = sum(m[bank * STRIDE + part_base(part) + 0x2fe + (tr - 1) * 30 + fxo + s2] != cnt - 1
                for bank in range(16) for part in range(8) for tr, fxo, s2, cnt in planted)
    check(f"stock clamps: {16 * 8 * len(planted)} planted out-of-count bytes (16 banks x 8 Parts) read "
          f"count - 1 after the load ({wrong} do not)", wrong == 0)

    # ---- save: SAVE AS DEFAULT writes card.work, SAVE PROJECT card.strd ----
    import emu_card
    # the posts run the writes in the engine task (a --step call runs as main,
    # where file I/O does not return under the port)
    save_at, store_at, scounts_at = symbol("core_post_save"), symbol("core_post_store"), symbol("core_save_counts")
    scard = OUT / "save.img"
    swork = OUT / "save_card.work"
    swork.write_bytes(work)
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree_save"), "--out", str(scard),
                        "--root-file", f"{swork}:OCTABAM/card.work"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_core: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    after, lanes_dump, sdump, log = OUT / "save_after.img", OUT / "save_lanes.bin", OUT / "save_counts.bin", OUT / "save.txt"
    cmd = [EMU, "--image", image, "--card", scard, "--set", a.set_name, "--project", a.name,
           "--mount", "--load-ms", "90000",
           "--sequencer", "--internal-clock", "--frames", "600",
           "--step", f"-:dump:{LANES:#x},576={lanes_dump}",
           "--step", f"-:call:{save_at:#x},0,1",
           "--step", f"150:call:{save_at:#x},1,0",
           "--step", f"300:call:{store_at:#x}",
           "--step", f"500:dump:{scounts_at:#x},16={sdump}",
           "--card-out", after]
    with open(log, "w") as fh:
        fh.write(" ".join(map(str, cmd)) + "\n"); fh.flush()
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    if r.returncode or log.read_text().count("returned, d0") < 3 or not after.exists():
        sys.exit(f"verify_core: the save run did not complete its calls -- {log}")
    saves, err, strd, strd_err = struct.unpack(">4I", sdump.read_bytes())
    check(f"save: two saves, last error {err}, card.strd written {strd} (errors {strd_err})",
          (saves, err, strd, strd_err) == (2, 0, 1, 0))
    files = emu_card.extract_image(after.read_bytes())
    cw = next((v for k, v in files.items() if k.upper().endswith("OCTABAM/CARD.WORK")), None)
    cs = next((v for k, v in files.items() if k.upper().endswith("OCTABAM/CARD.STRD")), None)
    check(f"save: card.work and card.strd on the card ({sorted(k for k in files if 'OCTABAM' in k.upper())})",
          cw is not None and cs is not None)
    lanes = lanes_dump.read_bytes()
    if cw is not None:
        f = obam.parse(cw)
        old_ids = {r.store_id: r.encode() for r in obam.parse(work).records}
        for sid in (store.fx_store_id(delay), store.fx_store_id(character)):
            rec = next((r for r in f.records if r.store_id == sid), None)
            check(f"save: {sid}'s record kept byte for byte", rec is not None and rec.encode() == old_ids[sid])
        for m, tr, lp1, lp2 in ((bd, 0, 0x18, 0x38), (sp, 1, 0x12, 0x32)):
            page = lanes[tr * 72 + lp1:tr * 72 + lp1 + 6] + lanes[tr * 72 + lp2:tr * 72 + lp2 + 6]
            rec = next((r for r in f.records if r.store_id == store.fx_store_id(m)), None)
            keys = store.fx_keys(m)
            want = {k: page[s] for s, k in enumerate(keys) if k}
            got = {v.key: v.data[0] for v in rec.values()} if rec else {}
            check(f"save: {m.key} T{tr + 1}: the record holds the live page {got == want}  (layout "
                  f"{rec.layout() if rec else None} = {store.fx_layout(m)})",
                  rec is not None and got == want and rec.layout() == store.fx_layout(m)
                  and rec.target() == (0, obam.NO_MODE))
        check("save: card.strd is card.work with the .strd kind",
              cs is not None and cs[:8] == cw[:8] and cs[8] == obam.CARD_STRD and cs[9:] == cw[9:])
        # a second boot of that card: the saved values on the descriptors
        after2, ddump, log2 = OUT / "save_boot2.img", OUT / "save_desc.bin", OUT / "save2.txt"
        shutil.copy2(after, after2)
        pb, ps = (struct.unpack(">I", rd(FX2_TABLE + 4 * m.menu.fx2_id, 4))[0] for m in (bd, sp))
        cmd = [EMU, "--image", image, "--card", after2, "--set", a.set_name, "--project", a.name,
               "--mount", "--load-ms", "90000",
               "--step", f"-:dump:{pb + 0x5e:#x},12={ddump}"]
        with open(log2, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        d = ddump.read_bytes() if ddump.exists() else b""
        page = lanes[0x18:0x1e] + lanes[0x38:0x3e]
        check(f"save: the second boot puts T1's saved page on BusDelay's descriptor  {d.hex(' ')}", d == page)

    # a card with no OCTABAM folder: the first save creates it
    fcard, fafter, flog = OUT / "save_fresh.img", OUT / "save_fresh_after.img", OUT / "save_fresh.txt"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree_fresh"), "--out", str(fcard)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_core: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    cmd = [EMU, "--image", image, "--card", fcard, "--set", a.set_name, "--project", a.name,
           "--mount", "--load-ms", "90000", "--sequencer", "--internal-clock", "--frames", "200",
           "--step", f"-:call:{save_at:#x},0,1", "--card-out", fafter]
    with open(flog, "w") as fh:
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    files = emu_card.extract_image(fafter.read_bytes()) if fafter.exists() else {}
    fw = next((v for k, v in files.items() if k.upper().endswith("OCTABAM/CARD.WORK")), None)
    recs = [r.store_id for r in obam.parse(fw).records] if fw else []
    check(f"save: on a card with no OCTABAM folder the first save creates it and card.work  {recs}",
          recs == [store.fx_store_id(bd)])

    # ---- menu: SAVE AS DEFAULT and CLEAR DEFAULT from the panel ------------
    MK = dict(no=0x32, yes=0x31, t1=0x10, fx2=0x26, proj=0x1c, down=0x20, right=0x21)

    def keys_script(keys):
        tt, lines = 1500, []
        for k, gap in keys:
            lines.append(f"{tt} key {MK[k]:#x} down"); tt += 40
            lines.append(f"{tt} key {MK[k]:#x} up"); tt += gap
        lines.append(f"{tt} quit")
        return "\n".join(lines) + "\n"
    nav = [("no", 400), ("t1", 600), ("fx2", 1500), ("proj", 1200)] + [("down", 400)] * 4 + [("right", 800)]
    runs = {"menu_save": nav + [("yes", 2500)],
            "menu_clear": nav + [("yes", 2500), ("yes", 800), ("down", 400), ("yes", 2500)]}
    for name, keys in runs.items():
        mc, mafter, mlog, mlanes = OUT / f"{name}.img", OUT / f"{name}_after.img", OUT / f"{name}.txt", OUT / f"{name}_lanes.bin"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{name}"), "--out", str(mc)], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_core: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        (OUT / f"{name}.script").write_text(keys_script(keys))
        cmd = [EMU, "--image", image, "--card", mc, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
               "--mkii", "--live-script", OUT / f"{name}.script", "--card-out", mafter,
               "--step", f"-:dump:{LANES:#x},576={mlanes}"]
        with open(mlog, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode or "ended on quit" not in mlog.read_text():
            sys.exit(f"verify_core: the {name} run did not finish -- {mlog}")
        files = emu_card.extract_image(mafter.read_bytes())
        mw = next((v for k, v in files.items() if k.upper().endswith("OCTABAM/CARD.WORK")), None)
        recs = {r.store_id: r for r in obam.parse(mw).records} if mw else {}
        lanes = mlanes.read_bytes()
        page = lanes[0x18:0x1e] + lanes[0x38:0x3e]
        if name == "menu_save":
            rec = recs.get(store.fx_store_id(bd))
            got = {v.key: v.data[0] for v in rec.values()} if rec else {}
            want = {k: page[i] for i, k in enumerate(store.fx_keys(bd)) if k}
            check(f"menu: SAVE AS DEFAULT from the panel writes T1's FX2 page ({got == want})", rec is not None and got == want)
        else:
            check(f"menu: CLEAR DEFAULT leaves no BusDelay record ({sorted(recs)})",
                  mw is not None and store.fx_store_id(bd) not in recs)

    # ---- mode: MODE DEFAULTS' view takes the card's values ------------------
    if "MODE DEFAULTS" in remix.modules and bd.mode_views:
        mcopy = OUT / "project_mode"
        shutil.rmtree(mcopy, ignore_errors=True)
        shutil.copytree(copy, mcopy)
        ot_project.set_fx(mcopy, "fx2", 1, "DELAY SERVER", page=[p.default for p in bd.params[:6]],
                          page2=[p.default for p in bd.params[6:12]], guard=False)
        card_vals = {"FDBK": 77, "SCTR": 33, "GLEN": 2, "DEL": 5}
        mwork = OUT / "mode_card.work"
        mwork.write_bytes(ot_store.set_default(None, bd, card_vals, mode="GRAIN"))
        card = OUT / "mode.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(mcopy), a.set_name, a.name,
                            "--tree", str(OUT / "tree_mode"), "--out", str(card),
                            "--root-file", f"{mwork}:OCTABAM/card.work"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_core: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        lanes_dump, cdump, log = OUT / "mode_lanes.bin", OUT / "mode_counts.bin", OUT / "mode.txt"
        cmd = [EMU, "--image", image, "--card", card, "--set", a.set_name, "--project", a.name,
               "--mount", "--load-ms", "90000",
               "--step", f"-:dump:{counts_at:#x},{4 * len(COUNTERS)}={cdump}",
               "--step", "-:poke:0x80000000=0;0x100b14cc=0",
               "--step", f"-:call:{FX2_EDITOR:#x},{bd.mode_slot - 6},2",
               "--step", f"-:dump:{LANES:#x},576={lanes_dump}"]
        with open(log, "w") as fh:
            fh.write(" ".join(map(str, cmd)) + "\n"); fh.flush()
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode or "returned, d0" not in log.read_text():
            sys.exit(f"verify_core: the mode run did not complete its call -- {log}")
        counts = dict(zip(COUNTERS, struct.unpack(f">{len(COUNTERS)}I", cdump.read_bytes())))
        print(f"  mode: counters {counts}")
        lane = lanes_dump.read_bytes()[:72]
        got_mode = lane[0x38 + bd.mode_slot - 6]
        view = next(v for v in bd.mode_views if v.mode == 1)
        check(f"mode: T1 BusDelay MODE -> {got_mode} (GRAIN)", got_mode == 1)
        slot_of = {"FDBK": 2, "SCTR": 7, "GLEN": 9, "DEL": 0}
        for slot, val in sorted(view.defaults.items()):
            want_v = next((card_vals[n] for n, s in slot_of.items() if s == slot and n in card_vals), val)
            off = (0x18 + slot) if slot < 6 else (0x38 + slot - 6)
            check(f"mode: slot {slot:2d} lane = {lane[off]:3d}  (view {val}, expected {want_v})", lane[off] == want_v)
        check(f"mode: DEL, a slot GRAIN's view does not list, skipped ({counts['skip_slot']}) and untouched "
              f"(lane {lane[0x18]}, default {bd.params[0].default})",
              counts["skip_slot"] == 1 and lane[0x18] == bd.params[0].default)
    print(f"verify_core: {'ok' if not fails else 'FAILED'} ({fails} failure(s)) -- {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
