#!/usr/bin/env python3
"""verify_brain -- the BRAIN module applies the card's knob defaults.

    python3 tools/verify/verify_brain.py [REMIX] [--project DIR] [--only-cases]

Builds REMIX (default `octabam`; `octabam-bus` too), stages
the project with BRAIN/card.work and card.strd written by
tools/hw/ot_brain.py, and under the port selects T2's effect through the
FX2 chooser (SEND -> stock DELAY) and the FX1 chooser (SPECTRUM ->
CHARACTER), as tools/verify/verify_desc_defaults.py does. Each case reads
the brain's counters after the load (brain_counts, by symbol) and the live
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
                which is why the brain has no clamp
  save          SAVE FX DEFAULT: brain_save_default for T1's FX2 (BusDelay) and
                T2's FX1 (SPECTRUM), then brain_card_store, on a card whose
                card.work holds other records: the two records carry the live
                pages' bytes, the others keep their bytes, card.strd is
                card.work; a second boot of that card puts the saved values
                on both descriptors
  menu          the BRAIN category on the panel: T1, the FX2 page, PROJ,
                DOWN x4, RIGHT, YES on DEFAULTS, DOWN, YES on SAVE FX DEFAULT: card.work
                holds T1's FX2 page; then OK, UP, YES on CLEAR FX DEFAULT: no
                BusDelay record left
  mode          a GRAIN record for BusDelay (T1): the FX2 page-2 editor moves
                MODE CLEAN -> GRAIN (verify_mode_defaults' call) and MODE
                DEFAULTS lands GRAIN's view with the card's values for the
                slots the view lists; a slot it does not list is skipped

What it cannot see: the unit's card I/O timing, a power-up with no LOAD
PROJECT post (the bank-load hook), the new-part initialiser.
"""
import argparse, os, pathlib, shutil, struct, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import brainfile, registry, brain  # noqa: E402
import ot_brain  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
ELF = ROOT / "out/platform/runtime/runtime.elf"
OUT = ROOT / "out/coreverify"
BASE = 0x40000400
LANES, IDS = 0x80000810, 0x80000ec4
FX2_TABLE, FX1_TABLE = 0x400d5fdc, 0x400d5f58
LIST_REF = 0x400375f4        # the operand of FUN_40052474 that holds the FX2 chooser list's address
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
    sys.exit(f"verify_brain: {name} not in {ELF}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="octabam")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="BRAINSET")       # not BRAIN: that is the store's directory
    ap.add_argument("--name", default="BRAINPRJ")
    ap.add_argument("--only-cases", action="store_true",
                    help="run the eight card cases (none .. settings_bad) and stop: minutes, not the whole gate")
    a = ap.parse_args()
    project = a.project
    if not project and pathlib.Path("~/.octabam_project").expanduser().is_file():
        project = pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
    if not project:
        print("  [SKIP] verify_brain: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_brain: no port binary (make emu-cf)"); return 0
    r = subprocess.run([sys.executable, str(ROOT / "modules/brain/generate_brain.py"), "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    print(f"  [{'ok' if r.returncode == 0 else 'FAIL'}] modules/brain/brain.s is brain.c + hooks.s compiled  {(r.stdout + r.stderr).strip()}")
    if r.returncode:
        return 1
    remix = registry.remix(a.remix)
    if "BRAIN" not in remix.modules:
        print(f"  [ -- ] verify_brain: {a.remix} carries no BRAIN"); return 0
    mods = registry.bound(remix)
    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "mainos.bin"
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_brain: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    counts_at = symbol("brain_counts")
    from remix import booted
    img = booted.image(image.read_bytes())   # descriptors may be in the DRAM runtime

    def rd(addr, n):
        return img[addr - BASE:addr - BASE + n]

    def page_of(table, fx):
        P = struct.unpack(">I", rd(table + 4 * fx, 4))[0]
        return P, rd(P + 0x5e, 12), struct.unpack(">12I", rd(P + 0x9a, 48))

    def fx2_chooser_ids():
        """The id on each row of the FX2 chooser, top to bottom, read from the built image: the list the
        chooser walks holds each row's descriptor, whose first word's low byte is the id it stores."""
        lst = struct.unpack(">I", rd(LIST_REF, 4))[0]
        ids = []
        while True:
            ptr = struct.unpack(">I", rd(lst + 4 * len(ids), 4))[0]
            if not ptr:
                return ids
            ids.append(struct.unpack(">I", rd(ptr, 4))[0] & 0xff)

    pdir = pathlib.Path(project).expanduser()
    copy = OUT / "project"
    shutil.rmtree(copy, ignore_errors=True)
    copy.mkdir(parents=True)
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)

    # T2's FX1 is SPECTRUM, so the FX1 chooser opens on its row and one DOWN lands CHARACTER. The
    # project's own bytes name an effect by id, and which one that is depends on the remix.
    import ot_project
    # The save/menu probes below require BusDelay on T1, even when the
    # supplied project is MIDI-only. Seed the disposable copy explicitly.
    bd = mods["DELAY SERVER"]
    ot_project.set_fx(copy, "fx2", 1, "DELAY SERVER", page=[p.default for p in bd.params[:6]],
                      page2=[p.default for p in bd.params[6:12]], guard=False)
    spm = mods["SPECTRUM"]
    ot_project.set_fx(copy, "fx1", 2, "SPECTRUM", page=[p.default or 0 for p in spm.params[:6]],
                      page2=[p.default or 0 for p in spm.params[6:12]], guard=False)
    # The panel script opens T2's FX2 chooser on the track's own row and presses DOWN once, so the track has to start
    # on the row above DELAY: SEND in the bus remix, whatever sits above it in the others (LO-FI in octabam).
    rows = fx2_chooser_ids()
    if 0x08 not in rows[1:]:
        sys.exit(f"verify_brain: DELAY (0x08) is not below the first row of {a.remix}'s FX2 chooser {rows}")
    ot_project.set_fx(copy, "fx2", 2, rows[rows.index(0x08) - 1], guard=False)
    delay, character = mods["DELAY"], mods["CHARACTER"]
    # T1's FX2: DELAY SERVER is the bus remix's core-B FX2 by construction; a remix without it is given MODULATION there
    # (live on FX2 with SLOTS FX1+FX2, a page 2 with a MODE, and no card record of its own to collide with).
    bus = "DELAY SERVER" in remix.modules
    t1 = mods["DELAY SERVER"] if bus else mods["MODULATION"]
    if not bus:
        ot_project.set_fx(copy, "fx2", 1, t1.key, page=[q.default or 0 for q in t1.params[:6]],
                          page2=[q.default or 0 for q in t1.params[6:12]], guard=False)
    want = {"DELAY": {"TIME": 52, "FB": 5, "X": 1, "TAPE": 0}, "CHARACTER": {"DRV": 9, "MIX": 77}}
    work = ot_brain.set_default(None, delay, want["DELAY"])
    work = ot_brain.set_default(work, character, want["CHARACTER"])
    # a value outside its count: DELAY's SYNC (slot 9) has two values
    f = brainfile.parse(work)
    rec = next(r for r in f.records if r.store_id == brain.fx_store_id(delay))
    rec.replace(brain.fx_keys(delay)[9], brainfile.BYTE, b"\x05")
    work = f.encode()
    strd = ot_brain.set_default(None, delay, {"TIME": 33})
    bad_layout = brainfile.File(brainfile.CARD_WORK, [brainfile.Record(brainfile.DEFAULT, brain.fx_store_id(delay), payload=brainfile.prefix_bytes(
        brainfile.DEFAULT, layout=brain.fx_layout(delay) ^ 1) + brainfile.Value(1, brainfile.BYTE, b"\x11").encode())]).encode()
    dup = brainfile.parse(ot_brain.set_default(None, delay, {"TIME": 40}))
    dup.records.append(dup.records[0])
    dup = dup.encode()
    damaged = work[:-3] + b"xyz"
    # settings (BRAIN's own store): MIDI LOG and DEFAULTS off, a key this
    # image does not know; a second file with a value out of bounds (2 for
    # a Binary) and one of the wrong type (an Option)
    V = brainfile.Value
    sett = brainfile.parse(work)
    sett.records.append(brainfile.Record(brainfile.SETTINGS, "octabam.brain",
        payload=V(1, brainfile.BINARY, b"\x00").encode() + V(2, brainfile.BINARY, b"\x00").encode()
        + V(99, brainfile.BINARY, b"\x01").encode()))
    sett = sett.encode()
    sbad = brainfile.parse(work)
    sbad.records.append(brainfile.Record(brainfile.SETTINGS, "octabam.brain",
        payload=V(1, brainfile.BINARY, b"\x02").encode() + V(2, brainfile.OPTION, b"\x00").encode()))
    sbad = sbad.encode()

    cases = {
        "none": {}, "work": {"card.work": work}, "recover": {"card.work": damaged, "card.strd": strd},
        "damaged": {"card.work": damaged}, "layout": {"card.work": bad_layout}, "duplicate": {"card.work": dup},
        "settings": {"card.work": sett}, "settings_bad": {"card.work": sbad},
    }
    values_at, set_counts_at = symbol("brain_values"), symbol("brain_set_counts")
    # APPLY DFLTS (key 2) and MIDI LOG (key 1) among the run-time values (EVENT LOG is the third)
    v_apply, v_midilog = symbol("brain_v_octabam_brain_2") - values_at, symbol("brain_v_octabam_brain_1") - values_at
    # FX2 LOCK's poke undone in RAM, so the FX2 chooser's YES selects
    unlock = (["--poke", ";".join(f"{0x400bc374 + i:#x}={b:#x}" for i, b in enumerate(bytes.fromhex("40052474")))]
              if "FX2 LOCK" in remix.modules else [])
    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    # The platform leaves a unit's .bss as the boot left it; the port boots
    # zeroed RAM and cannot show what BRAIN reads there before it writes
    # (image A7 halted on every power-on, docs/contributing/FAILURE_MODES.md).
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    kinds = {l.split()[2]: l.split()[1] for l in subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout.splitlines()
             if len(l.split()) == 3}
    for name in ("snapped", "table_len", "brain_counts", "brain_save_counts", "brain_pcounts",
                 "brain_proj_counts"):
        check(f"{name} is in .data (the unit's .bss holds what the boot left)  [{kinds.get(name)}]",
              kinds.get(name, "?").lower() == "d")

    for name, files in cases.items():
        roots = []
        for fn, data in files.items():
            p = OUT / f"{name}_{fn}"
            p.write_bytes(data)
            roots += ["--root-file", f"{p}:BRAIN/{fn}"]
        card = OUT / f"{name}.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{name}"), "--out", str(card), *roots],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        lanes = {}
        for page in ("fx2", "fx1"):
            vdump, scdump = OUT / f"{name}_{page}_values.bin", OUT / f"{name}_{page}_setcounts.bin"
            sp, dump, cdump, log, c = (OUT / f"{page}.script", OUT / f"{name}_{page}.bin",
                                       OUT / f"{name}_{page}_counts.bin", OUT / f"{name}_{page}.txt",
                                       OUT / f"{name}_{page}_run.img")
            sp.write_text(script(page))
            shutil.copy2(card, c)
            cmd = [EMU, "--image", image, "--card", c, "--set", a.set_name, "--project", a.name,
                   "--load-ms", "90000", "--mkii", "--live-script", sp, *unlock,
                   "--step", f"-:dump:{counts_at:#x},{4 * len(COUNTERS)}={cdump}",
                   "--step", f"-:dump:{values_at:#x},16={vdump}",
                   "--step", f"-:dump:{set_counts_at:#x},16={scdump}",
                   "--mem-dump", f"{LANES:#x},{IDS + 16 - LANES}={dump}"]
            with open(log, "w") as fh:
                fh.write(" ".join(map(str, cmd)) + "\n"); fh.flush()
                r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
            if r.returncode or "ended on quit" not in log.read_text() or not cdump.exists():
                sys.exit(f"verify_brain: ot_emu did not finish -- {log}")
            m = dump.read_bytes()
            lanes[page] = (m[IDS - LANES:], m[72:144])
            counts = dict(zip(COUNTERS, struct.unpack(f">{len(COUNTERS)}I", cdump.read_bytes())))
            vb = vdump.read_bytes()
            svals = (struct.unpack_from(">i", vb, v_apply)[0], struct.unpack_from(">i", vb, v_midilog)[0])
            scounts = dict(zip(("records", "values", "skip", "dup"), struct.unpack(">4I", scdump.read_bytes())))
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
        check(f"{name}: the selects land DELAY (0x08) and CHARACTER (0x{character.menu.fx2_id:02x})  0x{fx2:02x} 0x{fx1:02x}",
              (fx2, fx1) == (0x08, character.menu.fx2_id))
        check(f"{name}: the brain ran at the load ({counts['loads']} call(s))", counts["loads"] >= 1)

        def expect(defaults, m, values):
            out = bytearray(defaults)
            for knob, v in values.items():
                out[[p.name for p in m.params].index(knob.encode())] = v
            return bytes(out)
        if name in ("none", "damaged", "layout", "duplicate", "settings"):
            exp2, exp1 = d2, d1
        elif name in ("work", "settings_bad"):
            exp2, exp1 = expect(d2, delay, want["DELAY"]), expect(d1, character, want["CHARACTER"])
        else:
            exp2, exp1 = expect(d2, delay, {"TIME": 33}), d1
        check(f"{name}: DELAY's page  {got2.hex(' ')}  (expected {exp2.hex(' ')})", got2 == exp2)
        check(f"{name}: CHARACTER's page  {got1.hex(' ')}  (expected {exp1.hex(' ')})", got1 == exp1)
        want_state = {"none": "fresh", "work": "card.work", "recover": "recovered", "damaged": "damaged",
                      "layout": "card.work", "duplicate": "card.work", "settings": "card.work",
                      "settings_bad": "card.work"}[name]
        check(f"{name}: state {state}", state == want_state)
        if name == "work":
            check(f"{name}: the value outside its count skipped ({counts['skip_value']})", counts["skip_value"] == 1)
        if name == "layout":
            check(f"{name}: the record with another layout skipped ({counts['skip_layout']})", counts["skip_layout"] == 1)
        if name == "duplicate":
            check(f"{name}: both copies refused ({counts['skip_dup']})", counts["skip_dup"] == 2)
        if name == "settings":
            check(f"settings: APPLY DFLTS and MIDI LOG read off from card.work, so the default records "
                  f"are not applied (values {svals}, {scounts})",
                  svals == (0, 0) and scounts["values"] == 2 and counts["applied"] == 0)
        if name == "settings_bad":
            check(f"settings: a value out of bounds and one of the wrong type take the layer below "
                  f"(values {svals}, {scounts})", svals == (1, 0) and scounts["skip"] == 2)
        if name == "none":
            check(f"settings: no card store, the defaults of layers 1 and 2 (values {svals}: APPLY DFLTS, MIDI LOG)",
                  svals == (1, 0))
    if a.only_cases:
        print(f"verify_brain: {'ok' if not fails else 'FAILED'} ({fails} failure(s)) -- the eight card cases only")
        return 1 if fails else 0
    # ---- stock clamps: why the brain has no clamp of its own ----------------
    # The Part validator 0x40002318 rewrites every FX page byte outside its
    # descriptor's [min, min + count - 1] to the nearer end during the load
    # (BRAIN.md section 8). Planted out-of-count bytes in every Part of every
    # bank must read count - 1 after the load.
    import ot_project
    sp = mods["SPECTRUM"]
    bd = mods["DELAY SERVER"]
    # T1's FX2 hosts a module the image carries: DELAY SERVER where the remix has the bus, CHARACTER (page 2: SAT
    # of 3 values, KEY of 2) where it does not. Two page-2 slots with a count, planted past it.
    host = bd if "DELAY SERVER" in remix.modules else mods["CHARACTER"]
    counted = [i - 6 for i, q in enumerate(host.params[6:12], 6) if q.count and q.count < 128][:2]
    ccopy = OUT / "project_clamp"
    shutil.rmtree(ccopy, ignore_errors=True)
    shutil.copytree(copy, ccopy)
    b1 = [p.default or 0 for p in host.params[:6]]; b2 = [p.default or 0 for p in host.params[6:12]]
    s1 = [p.default or 0 for p in sp.params[:6]]; s2 = [p.default or 0 for p in sp.params[6:12]]
    for slot, v in zip(counted, (64, 100)):
        b2[slot] = v
    s2[0] = 90
    ot_project.set_fx(ccopy, "fx2", 1, host.key, page=b1, page2=b2, guard=False)
    for tr in (2, 3, 4, 6, 7):
        ot_project.set_fx(ccopy, "fx1", tr, "SPECTRUM", page=s1, page2=s2, guard=False)
    card = OUT / "clamp.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(ccopy), a.set_name, a.name,
                        "--tree", str(OUT / "tree_clamp"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    # docs/firmware/PARTS.md section 1: working Parts, then the saved ones
    # after the unsaved-bits byte
    BANKS, STRIDE, PLEN = 0x400e21e0, 0x9b340, 6322

    def part_base(p):
        return (0x8ed80 + p * PLEN) if p < 4 else (0x9504a + (p - 4) * PLEN)
    # (track, FX1 0 / FX2 6, page-2 slot, value count)
    planted = [(1, 6, slot, host.params[6 + slot].count) for slot in counted] + [(tr, 0, 0, 4) for tr in (2, 3, 4, 6, 7)]
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
        sys.exit(f"verify_brain: the clamp run did not finish -- {log}")
    m = banks.read_bytes()
    wrong = sum(m[bank * STRIDE + part_base(part) + 0x2fe + (tr - 1) * 30 + fxo + s2] != cnt - 1
                for bank in range(16) for part in range(8) for tr, fxo, s2, cnt in planted)
    check(f"stock clamps: {16 * 8 * len(planted)} planted out-of-count bytes (16 banks x 8 Parts) read "
          f"count - 1 after the load ({wrong} do not)", wrong == 0)

    # ---- save: SAVE FX DEFAULT writes card.work, SAVE PROJECT card.strd ----
    import emu_card
    # the posts run the writes in the engine task (a --step call runs as main,
    # where file I/O does not return under the port)
    save_at, store_at, scounts_at = symbol("brain_post_save"), symbol("brain_post_store"), symbol("brain_save_counts")
    pcounts_at, psave_at = symbol("brain_pcounts"), symbol("brain_proj_counts")
    scard = OUT / "save.img"
    swork = OUT / "save_card.work"
    swork.write_bytes(work)
    # the project's brain.work before the save: an unknown record kind (kept byte
    # for byte) and a project record from another image (replaced)
    unknown = brainfile.Record(9, "other.store", payload=b"keep me!!")
    stale = brainfile.Record(brainfile.PROJECT_RECORD, "octabam.brain",
                             payload=brainfile.Entry(0x7e, "octabam.old", 5).encode())
    pwork = OUT / "save_brain.work"
    pwork.write_bytes(brainfile.File(brainfile.PROJECT_WORK, [unknown, stale], "OLD").encode())
    pfile = f"{a.set_name}/{a.name}/brain"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree_save"), "--out", str(scard),
                        "--root-file", f"{swork}:BRAIN/card.work",
                        "--root-file", f"{pwork}:{pfile}.work"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    after, lanes_dump, sdump, log = OUT / "save_after.img", OUT / "save_lanes.bin", OUT / "save_counts.bin", OUT / "save.txt"
    cmd = [EMU, "--image", image, "--card", scard, "--set", a.set_name, "--project", a.name,
           "--mount", "--load-ms", "90000",
           "--sequencer", "--internal-clock", "--frames", "600",
           "--step", f"-:dump:{LANES:#x},576={lanes_dump}",
           "--step", f"-:call:{save_at:#x},0,1",
           "--step", f"150:call:{save_at:#x},1,0",
           "--step", f"300:call:{store_at:#x}",
           "--step", f"500:dump:{scounts_at:#x},16={sdump}",
           "--step", f"500:dump:{psave_at:#x},16={OUT / 'save_pcounts.bin'}",
           "--card-out", after]
    with open(log, "w") as fh:
        fh.write(" ".join(map(str, cmd)) + "\n"); fh.flush()
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    if r.returncode or log.read_text().count("returned, d0") < 3 or not after.exists():
        sys.exit(f"verify_brain: the save run did not complete its calls -- {log}")
    saves, err, strd, strd_err = struct.unpack(">4I", sdump.read_bytes())
    check(f"save: two saves, last error {err}, card.strd written {strd} (errors {strd_err})",
          (saves, err, strd, strd_err) == (2, 0, 1, 0))
    files = emu_card.extract_image(after.read_bytes())
    cw = next((v for k, v in files.items() if k.upper().endswith("BRAIN/CARD.WORK")), None)
    cs = next((v for k, v in files.items() if k.upper().endswith("BRAIN/CARD.STRD")), None)
    check(f"save: card.work and card.strd on the card ({sorted(k for k in files if 'BRAIN' in k.upper())})",
          cw is not None and cs is not None)
    lanes = lanes_dump.read_bytes()
    if cw is not None:
        f = brainfile.parse(cw)
        old_ids = {r.store_id: r.encode() for r in brainfile.parse(work).records}
        for sid in (brain.fx_store_id(delay), brain.fx_store_id(character)):
            rec = next((r for r in f.records if r.store_id == sid), None)
            check(f"save: {sid}'s record kept byte for byte", rec is not None and rec.encode() == old_ids[sid])
        for m, tr, lp1, lp2 in ((t1, 0, 0x18, 0x38), (sp, 1, 0x12, 0x32)):
            page = lanes[tr * 72 + lp1:tr * 72 + lp1 + 6] + lanes[tr * 72 + lp2:tr * 72 + lp2 + 6]
            rec = next((r for r in f.records if r.store_id == brain.fx_store_id(m)), None)
            keys = brain.fx_keys(m)
            want = {k: page[s] for s, k in enumerate(keys) if k}
            got = {v.key: v.data[0] for v in rec.values()} if rec else {}
            check(f"save: {m.key} T{tr + 1}: the record holds the live page {got == want}  (layout "
                  f"{rec.layout() if rec else None} = {brain.fx_layout(m)})",
                  rec is not None and got == want and rec.layout() == brain.fx_layout(m)
                  and rec.target() == (0, brainfile.NO_MODE))
        check("save: card.strd is card.work with the .strd kind",
              cs is not None and cs[:8] == cw[:8] and cs[8] == brainfile.CARD_STRD and cs[9:] == cw[9:])
        # a second boot of that card: the saved values on the descriptors
        after2, ddump, log2 = OUT / "save_boot2.img", OUT / "save_desc.bin", OUT / "save2.txt"
        shutil.copy2(after, after2)
        pb, ps = (struct.unpack(">I", rd(FX2_TABLE + 4 * m.menu.fx2_id, 4))[0] for m in (t1, sp))
        cmd = [EMU, "--image", image, "--card", after2, "--set", a.set_name, "--project", a.name,
               "--mount", "--load-ms", "90000",
               "--step", f"-:dump:{pb + 0x5e:#x},12={ddump}"]
        with open(log2, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        d = ddump.read_bytes() if ddump.exists() else b""
        page = lanes[0x18:0x1e] + lanes[0x38:0x3e]
        check(f"save: the second boot puts T1's saved page on BusDelay's descriptor  {d.hex(' ')}", d == page)

    # the project pair, written by the same SAVE PROJECT
    def find(fs, tail):
        return next((v for k, v in fs.items() if k.upper().endswith(tail.upper())), None)
    files = emu_card.extract_image(after.read_bytes())
    pw_, ps_ = find(files, f"{a.set_name}/{a.name}/BRAIN.WORK"), find(files, f"{a.set_name}/{a.name}/BRAIN.STRD")
    check(f"project: brain.work and brain.strd in the project's folder "
          f"({sorted(k for k in files if a.name.upper() in k.upper() and 'BRAIN.' in k.upper())})",
          pw_ is not None and ps_ is not None)
    want_entries = {m_.menu.fx2_id: (brain.fx_store_id(m_), brain.fx_layout(m_))
                    for m_ in brain.fx_targets(remix, mods)}
    if pw_ is not None and ps_ is not None:
        pf = brainfile.parse(pw_)
        precs = [r for r in pf.records if r.kind == brainfile.PROJECT_RECORD]
        got_entries = {e.fx_id: (e.store_id, e.layout) for e in precs[0].entries()} if len(precs) == 1 else {}
        check(f"project: one project record, one entry per effect in the image, store id and layout hash "
              f"as the build ({len(got_entries)} entries)", len(precs) == 1 and got_entries == want_entries
              and precs[0].store_id == "octabam.brain")
        old_unknown = unknown.encode()
        check("project: the unknown record kind is kept byte for byte",
              any(r.kind == 9 and r.encode() == old_unknown for r in pf.records) and len(pf.records) == 2)
        check("project: the stale project record is gone", all(e.fx_id != 0x7e for r in precs for e in r.entries()))
        check("project: brain.strd is brain.work with the .strd kind",
              ps_[:8] == pw_[:8] and ps_[8] == brainfile.PROJECT_STRD and ps_[9:] == pw_[9:]
              and pf.kind == brainfile.PROJECT_WORK)
    ps_counts = struct.unpack(">4I", (OUT / "save_pcounts.bin").read_bytes())
    check(f"project: one project save, error {ps_counts[1]}, brain.strd written {ps_counts[2]} "
          f"(errors {ps_counts[3]})", ps_counts == (1, 0, 1, 0))

    # ---- project load: the project record against the image ---------------
    PC = ("loads", "state", "record", "entries", "same", "moved", "layout", "gone", "skip")
    ch_, dl_, ds_, sp_ = mods["CHARACTER"], mods["DELAY"], mods["DELAY SERVER"], mods["SPECTRUM"]

    def pentry(m_, fx=None, layout=None):
        return brainfile.Entry(m_.menu.fx2_id if fx is None else fx, brain.fx_store_id(m_),
                               brain.fx_layout(m_) if layout is None else layout)
    entries = [pentry(dl_, layout=brain.fx_layout(dl_) ^ 1),        # same store, another layout
               pentry(ch_),                                        # unchanged
               brainfile.Entry(0x7e, "octabam.nosuch", 1),         # a store the image lacks
               pentry(t1, fx=sp_.menu.fx2_id)]                     # this FX id now names SPECTRUM
    prec = brainfile.Record(brainfile.PROJECT_RECORD, "octabam.brain",
                            payload=b"".join(e.encode() for e in entries))
    pgood = brainfile.File(brainfile.PROJECT_WORK, [prec], "OLD").encode()
    pstrd = brainfile.File(brainfile.PROJECT_STRD, [prec], "OLD").encode()
    pbad = pgood[:-3] + b"xyz"
    for tag, pfiles, want_state in (("pload", {"brain.work": pgood}, 1),
                                    ("precover", {"brain.work": pbad, "brain.strd": pstrd}, 2),
                                    ("pdamaged", {"brain.work": pbad}, 3)):
        roots = []
        for fn, data in pfiles.items():
            fp = OUT / f"{tag}_{fn}"
            fp.write_bytes(data)
            roots += ["--root-file", f"{fp}:{a.set_name}/{a.name}/{fn}"]
        pc_card, pc_dump, pc_log = OUT / f"{tag}.img", OUT / f"{tag}_counts.bin", OUT / f"{tag}.txt"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{tag}"), "--out", str(pc_card), *roots],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        cmd = [EMU, "--image", image, "--card", pc_card, "--set", a.set_name, "--project", a.name,
               "--mount", "--load-ms", "90000",
               "--step", f"-:dump:{pcounts_at:#x},{4 * len(PC)}={pc_dump}"]
        with open(pc_log, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode or not pc_dump.exists():
            sys.exit(f"verify_brain: the {tag} run did not finish -- {pc_log}")
        pcs = dict(zip(PC, struct.unpack(f">{len(PC)}I", pc_dump.read_bytes())))
        if want_state == 3:
            check(f"project: {tag}: brain.work damaged and no brain.strd, state damaged, no record read  {pcs}",
                  pcs["state"] == 3 and pcs["record"] == 0 and pcs["entries"] == 0)
        else:
            check(f"project: {tag}: state {want_state}, 4 entries: 1 same, 1 layout, 1 moved, 1 gone  {pcs}",
                  (pcs["state"], pcs["entries"], pcs["same"], pcs["layout"], pcs["moved"], pcs["gone"])
                  == (want_state, 4, 1, 1, 1, 1))

    # a card with no BRAIN folder: the first save creates it
    fcard, fafter, flog = OUT / "save_fresh.img", OUT / "save_fresh_after.img", OUT / "save_fresh.txt"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree_fresh"), "--out", str(fcard)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    cmd = [EMU, "--image", image, "--card", fcard, "--set", a.set_name, "--project", a.name,
           "--mount", "--load-ms", "90000", "--sequencer", "--internal-clock", "--frames", "200",
           "--step", f"-:call:{save_at:#x},0,1", "--card-out", fafter]
    with open(flog, "w") as fh:
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    files = emu_card.extract_image(fafter.read_bytes()) if fafter.exists() else {}
    fw = next((v for k, v in files.items() if k.upper().endswith("BRAIN/CARD.WORK")), None)
    recs = [r.store_id for r in brainfile.parse(fw).records] if fw else []
    check(f"save: on a card with no BRAIN folder the first save creates it and card.work  {recs}",
          recs == [brain.fx_store_id(t1)])

    # ---- menu: SAVE FX DEFAULT and CLEAR FX DEFAULT from the panel ------------
    MK = dict(no=0x32, yes=0x31, t1=0x10, fx2=0x26, proj=0x1c, down=0x20, up=0x33, right=0x21)

    def keys_script(keys):
        tt, lines = 1500, []
        for k, gap in keys:
            if k.startswith("raw:"):			# a line for the script as it is
                lines.append(f"{tt} {k[4:]}"); tt += gap
                continue
            lines.append(f"{tt} key {MK[k]:#x} down"); tt += 40
            lines.append(f"{tt} key {MK[k]:#x} up"); tt += gap
        lines.append(f"{tt} quit")
        return "\n".join(lines) + "\n"
    # the page shortcut: hold the FX2 page key and press FUNC (a list: SAVE FX DEFAULT, CLEAR FX DEFAULT, ...)
    hold = [("raw:key 0x26 down", 100), ("raw:key 0x2d down", 100), ("raw:key 0x2d up", 100), ("raw:key 0x26 up", 800)]
    nav = [("no", 400), ("t1", 600), ("fx2", 1500)]
    runs = {"menu_save": nav + hold + [("yes", 2500)],
            "menu_clear": nav + hold + [("yes", 2500), ("yes", 1500)] + hold + [("down", 400), ("yes", 2500)]}   # SAVE, then CLEAR
    for name, keys in runs.items():
        mc, mafter, mlog, mlanes = OUT / f"{name}.img", OUT / f"{name}_after.img", OUT / f"{name}.txt", OUT / f"{name}_lanes.bin"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{name}"), "--out", str(mc)], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        (OUT / f"{name}.script").write_text(keys_script(keys))
        cmd = [EMU, "--image", image, "--card", mc, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
               "--mkii", "--live-script", OUT / f"{name}.script", "--card-out", mafter,
               "--step", f"-:dump:{LANES:#x},576={mlanes}"]
        with open(mlog, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode or "ended on quit" not in mlog.read_text():
            sys.exit(f"verify_brain: the {name} run did not finish -- {mlog}")
        files = emu_card.extract_image(mafter.read_bytes())
        mw = next((v for k, v in files.items() if k.upper().endswith("BRAIN/CARD.WORK")), None)
        recs = {r.store_id: r for r in brainfile.parse(mw).records} if mw else {}
        lanes = mlanes.read_bytes()
        page = lanes[0x18:0x1e] + lanes[0x38:0x3e]
        if name == "menu_save":
            rec = recs.get(brain.fx_store_id(t1))
            got = {v.key: v.data[0] for v in rec.values()} if rec else {}
            want = {k: page[i] for i, k in enumerate(brain.fx_keys(t1)) if k}
            check(f"menu: SAVE FX DEFAULT from the panel writes T1's FX2 page ({got == want})", rec is not None and got == want)
        else:
            check(f"menu: CLEAR FX DEFAULT leaves no BusDelay record ({sorted(recs)})",
                  mw is not None and brain.fx_store_id(t1) not in recs)

    # ---- settings from the panel: MIDI > MIDI LOG, YES (off by default: on) ----
    seed = brainfile.File(brainfile.CARD_WORK, [brainfile.Record(brainfile.SETTINGS, "octabam.brain",
        payload=brainfile.Value(99, brainfile.BINARY, b"\x01").encode())]).encode()
    (OUT / "mset_seed.work").write_bytes(seed)
    mc, mafter, mlog = OUT / "menu_settings.img", OUT / "menu_settings_after.img", OUT / "menu_settings.txt"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree_menu_settings"), "--out", str(mc),
                        "--root-file", f"{OUT / 'mset_seed.work'}:BRAIN/card.work"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    keys = [("no", 400), ("proj", 1200)] + [("down", 400)] * 4 + [("right", 800)] + [("down", 400)] * 4 + [("yes", 800), ("right", 600), ("yes", 3000)]   # BRAIN > LOG (the fifth row), MIDI tab, MIDI LOG
    (OUT / "menu_settings.script").write_text(keys_script(keys))
    cmd = [EMU, "--image", image, "--card", mc, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
           "--mkii", "--live-script", OUT / "menu_settings.script", "--card-out", mafter]
    with open(mlog, "w") as fh:
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    if r.returncode or "ended on quit" not in mlog.read_text():
        sys.exit(f"verify_brain: the menu_settings run did not finish -- {mlog}")
    files = emu_card.extract_image(mafter.read_bytes())
    mw = next((v for k, v in files.items() if k.upper().endswith("BRAIN/CARD.WORK")), None)
    srec = [r for r in brainfile.parse(mw).records
            if r.kind == brainfile.SETTINGS and r.store_id == "octabam.brain"] if mw else []
    got = {v.key: v.data[0] for v in srec[0].values()} if len(srec) == 1 else {}
    check(f"settings: YES on LOG > MIDI > MIDI LOG writes the octabam.brain settings record, MIDI LOG on, APPLY DFLTS on, "
          f"EVENT LOG at its default (on), the unknown key kept  {got}", got == {1: 1, 2: 1, 3: 1, 99: 1})

    # ---- USB's pair rule from the panel: IN is refused while TRACKS, MAIN, CUE and MASTER are off ----
    # BRAIN > SETTINGS: TRACKS PRE -> POST -> OFF, MAIN off, CUE off, then YES on IN. The rule
    # compares the usb entries' keys (modules/usb/manifest.py); with the wrong keys it found none
    # and IN went to AB (19 Oct 2026, usb_pair_ok looked for keys 1-5, the settings are 7-11).
    if "USB" in remix.modules:
        uc, uafter, ulog = OUT / "menu_usb.img", OUT / "menu_usb_after.img", OUT / "menu_usb.txt"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / "tree_menu_usb"), "--out", str(uc)], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        keys = ([("no", 400), ("proj", 1200)] + [("down", 400)] * 4 + [("right", 800)] + [("down", 400)] * 2 + [("yes", 800)]
                + [("down", 300)] * 6 + [("yes", 500)] * 2           # TRACKS: PRE, POST, OFF
                + [("up", 300)] * 3 + [("yes", 500)]                 # MAIN off
                + [("up", 300)] * 2 + [("yes", 500)]                 # CUE off
                + [("down", 300), ("yes", 1500)])                    # IN: refused
        (OUT / "menu_usb.script").write_text(keys_script(keys))
        cmd = [EMU, "--image", image, "--card", uc, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
               "--mkii", "--live-script", OUT / "menu_usb.script", "--card-out", uafter]
        with open(ulog, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode or "ended on quit" not in ulog.read_text():
            sys.exit(f"verify_brain: the menu_usb run did not finish -- {ulog}")
        files = emu_card.extract_image(uafter.read_bytes())
        mw = next((v for k, v in files.items() if k.upper().endswith("BRAIN/CARD.WORK")), None)
        urec = [r for r in brainfile.parse(mw).records
                if r.kind == brainfile.SETTINGS and r.store_id == "octabam.usb"] if mw else []
        got = {v.key: v.data[0] for v in urec[0].values()} if len(urec) == 1 else {}
        check(f"settings: USB's IN is refused while TRACKS, MAIN and CUE are OFF (record, key: value {got}; want TRACKS 0, MAIN 0, CUE 0, IN 0)",
              got.get(7) == 0 and got.get(8) == 0 and got.get(9) == 0 and got.get(11) == 0)

    # ---- templates: SAVE from the shortcut; LOAD of a seeded template -------
    # Run 1: T1's FX1 page; hold FX1 + FUNC (the shortcut), SAVE TEMPLATE:
    # card.work holds one template record of the effect, equal to the page.
    # Run 2: card.work seeded with TPL 99 for the same effect, each value the
    # page's + 1 inside its count (so every keyed slot differs from the page);
    # the shortcut, LOAD TEMPLATE, the first name: the page takes TPL 99.
    def tap(code, t, gap=500):
        return [f"{t} key {code:#x} down", f"{t + 30} key {code:#x} up"], t + gap
    def shortcut(t, hold):
        return [f"{t} key {hold:#x} down", f"{t + 200} key 0x2d down", f"{t + 230} key 0x2d up",
                f"{t + 500} key {hold:#x} up"], t + 900
    FX1_REGIONS = ((0x8eea6, 6), (0x8f07e, 6))
    # T1's FX1 is CHARACTER in the templates' project: the project's own bytes name an effect by id,
    # and which one that is depends on the remix.
    tcopy = OUT / "project_tpl"
    shutil.rmtree(tcopy, ignore_errors=True)
    shutil.copytree(copy, tcopy)
    chm = mods["CHARACTER"]
    ot_project.set_fx(tcopy, "fx1", 1, "CHARACTER", page=[p.default or 0 for p in chm.params[:6]],
                      page2=[p.default or 0 for p in chm.params[6:12]], guard=False)
    def tpl_run(tag, picks, seed=None, part_at=None, pre=(0x32, 0x10, 0x25), hold=0x25, regions=FX1_REGIONS):
        lines, tt = [], 1500
        for c in pre:
            l, tt = tap(c, tt); lines += l
        l, tt = shortcut(tt, hold); lines += l
        for c in picks:
            l, tt = tap(c, tt, 800); lines += l
        lines.append(f"{tt + 2000} quit")
        tc, tafter, tlog, tl = (OUT / f"{tag}.img", OUT / f"{tag}_after.img", OUT / f"{tag}.txt",
                                OUT / f"{tag}_lanes.bin")
        roots = []
        if seed is not None:
            (OUT / f"{tag}_seed.work").write_bytes(seed)
            roots = ["--root-file", f"{OUT / f'{tag}_seed.work'}:BRAIN/card.work"]
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(tcopy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{tag}"), "--out", str(tc), *roots],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        (OUT / f"{tag}.script").write_text("\n".join(lines) + "\n")
        # the current bank's pointer and Part index, and (part_at given) T1's
        # regions in that Part (FX1 page 1 and page 2 by default): what LOAD
        # writes. The live lane
        # is not read: under the port the playing bank is not the bank the UI
        # shows, and the stock writer updates the lane only when they match
        # (AGENTS.md "the part the emulated load applies is not the part that
        # plays").
        tdb = OUT / f"{tag}_db.bin"
        dumps = [f"0x46c82456,4={tdb}", f"0x80000003,1={OUT / f'{tag}_part.bin'}"]
        if part_at is not None:
            dumps += [f"{part_at + off:#x},{n}={OUT / f'{tag}_r{i}.bin'}" for i, (off, n) in enumerate(regions)]
        cmd = [EMU, "--image", image, "--card", tc, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
               "--mkii", "--live-script", OUT / f"{tag}.script", "--card-out", tafter, "--midi-out", OUT / f"{tag}_midi.bin",
               "--step", f"-:dump:{LANES:#x},144={tl}", "--mem-dump", ";".join(dumps)]
        with open(tlog, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode or "ended on quit" not in tlog.read_text():
            sys.exit(f"verify_brain: the {tag} run did not finish -- {tlog}")
        lane = tl.read_bytes()
        files = emu_card.extract_image(tafter.read_bytes())
        work = next((v for k, v in files.items() if k.upper().endswith("BRAIN/CARD.WORK")), None)
        db = int.from_bytes(tdb.read_bytes(), "big") + (OUT / f"{tag}_part.bin").read_bytes()[0] * 6322
        partpage = (b"".join((OUT / f"{tag}_r{i}.bin").read_bytes() for i in range(len(regions)))
                    if part_at is not None else b"")
        return lane[0x12:0x18] + lane[0x32:0x38], work, db, partpage   # T1's FX1 page 1, page 2

    ch = mods["CHARACTER"]
    keys = brain.fx_keys(ch)
    page, mw, part_at, _ = tpl_run("tpl_save", (0x20, 0x20, 0x31, 0x31))   # SAVE TEMPLATE, then OK
    trecs = [r for r in brainfile.parse(mw).records if r.kind == brainfile.TEMPLATE_REC] if mw else []
    got = {v.key: v.data[0] for v in trecs[0].values()} if len(trecs) == 1 else {}
    check(f"templates: SAVE TEMPLATE from the shortcut writes one template record of the page "
          f"({len(trecs)}, name {trecs[0].name() if trecs else None!r})  {got}",
          len(trecs) == 1 and trecs[0].store_id == brain.fx_store_id(ch) and trecs[0].name().startswith("CHAR 01")
          and got == {k: page[i] for i, k in enumerate(keys) if k})
    P = struct.unpack(">I", rd(FX1_TABLE + 4 * ch.menu.fx2_id, 4))[0]
    mins, cnts = struct.unpack(">12i", rd(P + 0x6a, 48)), struct.unpack(">12i", rd(P + 0x9a, 48))
    seedv = [mins[i] + (page[i] - mins[i] + 1) % cnts[i] if cnts[i] > 1 else page[i] for i in range(12)]
    vals = b"".join(brainfile.Value(k, brainfile.BYTE, bytes([seedv[i]])).encode() for i, k in enumerate(keys) if k)
    seed = brainfile.File(brainfile.CARD_WORK, [brainfile.Record(brainfile.TEMPLATE_REC, brain.fx_store_id(ch),
        payload=brainfile.prefix_bytes(brainfile.TEMPLATE_REC, layout=brain.fx_layout(ch), name="TPL 99") + vals)]).encode()
    want = bytes(seedv)
    moves = [i for i, k in enumerate(keys) if k and want[i] != page[i]]
    _, _, _, lpage = tpl_run("tpl_load", (0x20, 0x20, 0x20, 0x31, 0x31), seed, part_at)  # LOAD TEMPLATE, TPL 99
    check(f"templates: LOAD TEMPLATE of a seeded TPL 99 writes its values into T1's FX1 page in the current "
          f"Part ({len(moves)} keyed slots differ from the page before)  {lpage.hex(' ')}  (expected "
          f"{want.hex(' ')}, unkeyed slots not compared)",
          len(moves) >= 1 and len(lpage) == 12 and all(lpage[i] == want[i] for i, k in enumerate(keys) if k))

    # ---- templates on the stock targets: T1's AMP and LFO pages, MIDI track 1 --
    # Slot order, keys and ranges as brain.c's view_fill: each target's Part
    # regions in order, the range from the stock page descriptor (entry E,
    # minimum E+0xa2, count E+0xd2), None for a raw byte (the CTRL enable
    # bitmaps); key 0 for a slot whose enable nibble has bit 0 clear. SAVE
    # writes every keyed slot's Part byte; LOAD of a seeded TPL 99 (each
    # ranged value + 1 inside its count) writes every one.
    def rng(E, s):
        return struct.unpack(">i", rd(E + 0xa2 + 4 * s, 4))[0], struct.unpack(">i", rd(E + 0xd2 + 4 * s, 4))[0]
    def on(E, s):
        hi, lo = struct.unpack(">II", rd(E + 0x1c2, 8))
        return ((hi << 32 | lo) >> (4 * s)) & 1
    D_LFO, D_AMP, D_NOTE, D_ARP, D_MLFO, D_CTL1, D_CTL2 = (0x400d37be, 0x400d3950, 0x400d3e06, 0x400d3f98,
                                                         0x400d412a, 0x400d42bc, 0x400d444e)
    midi_desc = (D_NOTE, D_MLFO, D_ARP, D_CTL1, D_CTL2)
    stock = {
        "amp": dict(id=brain.STOCK_TARGETS["amp"][0], layout=brain.STOCK_TARGETS["amp"][1], pre=(0x32, 0x10, 0x23), hold=0x23,
                    regions=((0x8eea0, 6), (0x8f078, 6)),
                    slots=[(1 + s if on(D_AMP, s) else 0, rng(D_AMP, s)) for s in range(12)]),
        "lfo": dict(id=brain.STOCK_TARGETS["lfo"][0], layout=brain.STOCK_TARGETS["lfo"][1], pre=(0x32, 0x10, 0x24), hold=0x24,
                    regions=((0x8ee9a, 6), (0x8f072, 6), (0x8f08a, 6)),
                    slots=[(1 + s, rng(D_LFO, s if s < 6 else 6 + (s - 6) // 3)) for s in range(18)]),
        "midi": dict(id=brain.STOCK_TARGETS["midi"][0], layout=brain.STOCK_TARGETS["midi"][1], pre=(0x32, 0x35, 0x10, 0x22), hold=0x22,
                     regions=((0x8f162, 32), (0x8f262, 36)),
                     slots=[(64 + f if f >= 30 or on(midi_desc[f // 6], f % 6) else 0,
                             rng(midi_desc[f // 6], f % 6) if f < 30 else None) for f in range(32)]
                     + [(1 + o if on(E, s) else 0, rng(E, s))
                        for o in range(36) for E, s in [(D_MLFO, 8 + (o - 30) // 3) if o >= 30
                                                        else (D_MLFO, 6 + (o - 6) // 3) if o // 6 == 1
                                                        else (midi_desc[o // 6], 6 + o % 6)]]),
    }
    for name, tg in stock.items():
        sl = tg["slots"]
        if name != "lfo":
            page, mw, _, part = tpl_run(f"tpl_{name}_save", (0x20, 0x20, 0x31, 0x31), None, part_at, tg["pre"],
                                        tg["hold"], tg["regions"])
            trecs = [r for r in brainfile.parse(mw).records if r.kind == brainfile.TEMPLATE_REC] if mw else []
            got = {v.key: v.data[0] for v in trecs[0].values()} if len(trecs) == 1 else {}
            want = {k: part[i] for i, (k, _) in enumerate(sl) if k}
            check(f"templates: SAVE TEMPLATE on T1's {name.upper()} writes one {tg['id']} record of its "
                  f"{len(want)} Part bytes ({len(trecs)} records, {len(got)} values, equal {got == want})",
                  len(trecs) == 1 and trecs[0].store_id == tg["id"] and got == want)
        else:
            _, _, _, part = tpl_run(f"tpl_{name}_read", (0x32,), None, part_at, tg["pre"], tg["hold"], tg["regions"])
        seedv = [r[0] + (part[i] - r[0] + 1) % r[1] if k and r and r[1] > 1 else part[i] for i, (k, r) in enumerate(sl)]
        vals = b"".join(brainfile.Value(k, brainfile.BYTE, bytes([seedv[i]])).encode() for i, (k, _) in enumerate(sl) if k)
        seed = brainfile.File(brainfile.CARD_WORK, [brainfile.Record(brainfile.TEMPLATE_REC, tg["id"],
            payload=brainfile.prefix_bytes(brainfile.TEMPLATE_REC, layout=tg["layout"], name="TPL 99") + vals)]).encode()
        moves = [i for i, (k, _) in enumerate(sl) if k and seedv[i] != part[i]]
        _, _, _, lp = tpl_run(f"tpl_{name}_load", (0x20, 0x20, 0x20, 0x31, 0x31), seed, part_at,
                              tg["pre"], tg["hold"], tg["regions"])
        bad = [i for i, (k, _) in enumerate(sl) if k and lp[i] != seedv[i]]
        check(f"templates: LOAD TEMPLATE of a seeded {tg['id']} TPL 99 writes T1's {name.upper()} bytes in the "
              f"current Part ({len(moves)} slots differ from before, {len(bad)} wrong: {bad[:8]})",
              len(moves) >= 1 and len(lp) == len(sl) and not bad)
        if name == "midi":
            chan, prog = seedv[32], seedv[34]
            tx = (OUT / f"tpl_{name}_load_midi.bin").read_bytes()
            pc = bytes([0xc0 | (chan - 1), prog])
            check(f"templates: the MIDI LOAD sends program {prog} on channel {chan} ({tx.hex(' ')[:60]})",
                  chan == 0 or prog >= 128 or pc in tx)

    rd_stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()

    # ---- shared: one panel run on a staged card ---------------------------
    def ui_run(tag, keys, roots=(), dumps=(), extra=()):
        """keys: (code, gap) taps or 'midi ..'/'poke ..' lines. roots: (file,
        card path). dumps: (address, length). Returns (card files, log text,
        [dumped bytes])."""
        uc, uafter, ulog = OUT / f"{tag}.img", OUT / f"{tag}_after.img", OUT / f"{tag}.txt"
        rr = []
        for f_, path in roots:
            rr += ["--root-file", f"{f_}:{path}"]
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{tag}"), "--out", str(uc), *rr],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        t, lines = 1500, []
        for item in keys:
            if isinstance(item, str):
                lines.append(f"{t} {item}"); t += 300
            else:
                lines += [f"{t} key {item[0]:#x} down", f"{t + 30} key {item[0]:#x} up"]; t += item[1]
        lines.append(f"{t + 1500} quit")
        (OUT / f"{tag}.script").write_text("\n".join(lines) + "\n")
        dfiles = [OUT / f"{tag}_d{i}.bin" for i in range(len(dumps))]
        cmd = [EMU, "--image", image, "--card", uc, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
               "--mkii", "--live-script", OUT / f"{tag}.script", "--card-out", uafter, *extra]
        if dumps:
            cmd += ["--mem-dump", ";".join(f"{ad:#x},{n}={f_}" for (ad, n), f_ in zip(dumps, dfiles))]
        with open(ulog, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        text = ulog.read_text()
        if r.returncode or "ended on quit" not in text:
            sys.exit(f"verify_brain: the {tag} run did not finish -- {ulog}")
        return emu_card.extract_image(uafter.read_bytes()), text, [f_.read_bytes() for f_ in dfiles]

    def card_file(files, tail):
        return next((v for k, v in files.items() if k.upper().endswith(tail.upper())), None)

    # ---- BRAIN > TEMPLATES: APPLY TO..., RENAME, DELETE, edit, NEW ------------
    # TEMPLATES has four tabs, PART first, then FX, MIDI, PROJECT; each template's screen is the
    # actions (APPLY TO..., SET AS DEFAULT where the target has one, SAVE, RENAME, DELETE), a VALUES
    # line, then its values. card.work seeded with one CHARACTER template TPL 07 (its first slot 5):
    # the FX tab lists it under a heading.
    #   load    APPLY TO..., the slot list (T1 FX1 first, CHARACTER there): T1's FX1 page slot 0 becomes 5
    #   rename  RENAME, the name editor (its cursor opens after the name):
    #           UP sets the character there ('0', measured under the port), YES
    #   delete  DELETE: the record leaves card.work
    #   edit    RIGHT three times on the first value, SAVE: the record holds 8
    #   new     no card.work: NEW PART TEMPLATE, YES on the name (PART 01): one stock.part2 record, the
    #           Part's 6,322 bytes and the project's name
    tseed = OUT / "tpl_pane_seed.work"
    tseed.write_bytes(brainfile.File(brainfile.CARD_WORK, [brainfile.Record(brainfile.TEMPLATE_REC, brain.fx_store_id(ch),
        payload=brainfile.prefix_bytes(brainfile.TEMPLATE_REC, layout=brain.fx_layout(ch), name="TPL 07")
        + brainfile.Value(keys[0], brainfile.BYTE, b"\x05").encode())]).encode())
    to_pane = [(0x1c, 1200)] + [(0x20, 400)] * 4 + [(0x21, 800)] + [(0x31, 800)]     # BRAIN > TEMPLATES (the first row), the PART tab
    fx_tab = [(0x21, 400), (0x20, 400)]                                               # the FX tab, its first template
    def pane_recs(files):
        w = card_file(files, "BRAIN/CARD.WORK")
        return [(r.store_id, r.name(), {v.key: v.data[0] for v in r.values()})
                for r in brainfile.parse(w).records if r.kind == brainfile.TEMPLATE_REC] if w else []
    files, _, (drv0,) = ui_run("tpl_pane_load", [(0x32, 400)] + to_pane + fx_tab + [(0x31, 3000), (0x31, 800), (0x31, 800), (0x31, 2500)],
                               roots=((tseed, "BRAIN/card.work"),), dumps=((part_at + 0x8eea6, 1),))
    check(f"templates: BRAIN > TEMPLATES, APPLY TO... on TPL 07, T1 FX1, sets T1's FX1 slot 0 to 5  {drv0.hex()}",
          drv0[0] == 5)
    fid = brain.fx_store_id(ch)
    files, _, _ = ui_run("tpl_pane_rename", [(0x32, 400)] + to_pane + fx_tab + [(0x31, 3000), (0x20, 500), (0x20, 500), (0x20, 500),
                                                                      (0x31, 1200), (0x33, 300), (0x31, 2500)],
                         roots=((tseed, "BRAIN/card.work"),))     # APPLY TO..., SET AS DEFAULT, SAVE, RENAME: the editor
    recs = pane_recs(files)
    check(f"templates: BRAIN > TEMPLATES, RENAME on the template's screen renames TPL 07 through the name editor "
          f"(UP, YES) to TPL 070, its value kept  {recs}", recs == [(fid, "TPL 070", {keys[0]: 5})])
    files, _, _ = ui_run("tpl_pane_delete", [(0x32, 400)] + to_pane + fx_tab + [(0x31, 3000)] + [(0x20, 500)] * 4 + [(0x31, 2500)],
                         roots=((tseed, "BRAIN/card.work"),))     # ... DELETE
    recs = pane_recs(files)
    check(f"templates: BRAIN > TEMPLATES, DELETE on the template's screen removes TPL 07  {recs}", recs == [])
    files, _, _ = ui_run("tpl_pane_edit", [(0x32, 400)] + to_pane + fx_tab + [(0x31, 3000)] + [(0x20, 400)] * 5 + [(0x21, 400)] * 3
                                                                      + [(0x33, 400)] * 3 + [(0x31, 2500), (0x31, 2500)],
                         roots=((tseed, "BRAIN/card.work"),))     # DOWN x5 to the first value (past the VALUES line), RIGHT x3, UP x3 to SAVE
    recs = pane_recs(files)
    check(f"templates: BRAIN > TEMPLATES, the template's screen: RIGHT three times raises the first value 5 to 8 "
          f"and SAVE writes it  {recs}", recs == [(fid, "TPL 07", {keys[0]: 8})])
    files, _, _ = ui_run("tpl_pane_new", [(0x32, 400)] + to_pane + [(0x31, 1200), (0x31, 4000)])
    w_ = card_file(files, "BRAIN/CARD.WORK")
    prec = [r for r in brainfile.parse(w_).records if r.kind == brainfile.TEMPLATE_REC] if w_ else []
    pv = prec[0].values() if len(prec) == 1 else []
    check(f"templates: BRAIN > TEMPLATES, NEW PART TEMPLATE and YES on the name editor's PART 01 write one stock.part2 "
          f"record: the Part's 6,322 bytes and the project's name  "
          f"{[(r.store_id, r.name()) for r in prec]}",
          len(prec) == 1 and prec[0].store_id == "stock.part2" and prec[0].name().startswith("PART 01")
          and len(pv) == 2 and len(pv[0].data) == 6322 and pv[1].data.rstrip(b"\0") == a.name.encode())

    # ---- a PART template: APPLY TO..., a section from a track onto another track ------------------
    # card.work seeded with a PART template whose Part image is the project's Part with T1's FX1 page 1
    # slot 0 = 77 and T1's AMP page 1 slot 0 = 66. APPLY TO..., FX (row 1), FROM T1, ONTO T2: T2's FX1
    # page 1 slot 0 = 77 in the Part, T2's AMP page 1 untouched.
    def blob_with(fn):
        import random
        rng = random.Random(5)
        # 0 or 1 (inside every count, so the stock Part validator keeps it), from a seeded generator: no period, a probe is found once
        b = bytearray(rng.getrandbits(1) for _ in range(6322))
        fn(b)
        return bytes(b)
    pblob = blob_with(lambda b: (b.__setitem__(0x126, 77), b.__setitem__(0x120, 66), b.__setitem__(0x00, 0), b.__setitem__(0x08, 0)))
    def part_rec(kind, blob, name="PART 07"):
        pay = brainfile.prefix_bytes(kind, layout=0x50525432, name=name) if kind == brainfile.TEMPLATE_REC \
            else brainfile.prefix_bytes(kind, layout=0x50525432)
        pay += brainfile.Value(1, brainfile.BLOB, blob).encode()
        if kind == brainfile.TEMPLATE_REC:
            pay += brainfile.Value(2, brainfile.BLOB, a.name.encode() + b"\0").encode()
        return brainfile.Record(kind, "stock.part2", payload=pay)
    pseed2 = OUT / "tpl_part_seed.work"
    pseed2.write_bytes(brainfile.File(brainfile.CARD_WORK, [part_rec(brainfile.TEMPLATE_REC, pblob)]).encode())
    parea = [(0x31, 3000), (0x31, 800), (0x20, 600), (0x31, 800), (0x20, 600), (0x31, 800), (0x20, 600), (0x31, 2500)]
    # the template (PART tab, its first row after NEW), YES; APPLY TO...; FX; FROM T1; ONTO T2; OK
    files, _, (db_, part_, w126, w120, t2fx, t2amp) = ui_run(
        "tpl_part_apply", [(0x32, 400)] + to_pane + [(0x20, 400)] + parea,
        roots=((pseed2, "BRAIN/card.work"),),
        dumps=((0x46c82456, 4), (0x80000003, 1), (part_at + 0x8ed80 + 0x126, 1), (part_at + 0x8ed80 + 0x120, 1),
               (part_at + 0x8ed80 + 0x126 + 24, 1), (part_at + 0x8ed80 + 0x120 + 24, 1)))
    check(f"templates: PART template APPLY TO..., FX, FROM T1, ONTO T2: T2's FX1 slot 0 is 77 and T2's AMP slot 0 "
          f"keeps its value (T2 FX1 {t2fx.hex()}, T2 AMP {t2amp.hex()}, T1 FX1 {w126.hex()} T1 AMP {w120.hex()} unchanged)",
          t2fx[0] == 77 and t2amp[0] != 66)

    # ---- a PART template: APPLY TO..., WHOLE PART --------------------------------------------------
    # The template's Part image has valid FX ids (0 = NONE), valid machines and scene selections, and a
    # byte pattern everywhere else. WHOLE PART, then the live Part: every section's bytes equal the
    # template's (FX, LFO, INPUT SRC, MIDI TRACKS, SCENES, MACHINES), the bytes no section carries
    # (the AMP pages, the levels, the sample slots) still the project's own.
    def whole_fn(b):
        for k in range(16):
            b[k] = 0
        for t, m in enumerate((0, 1, 2, 0, 4, 1, 0, 2)):
            b[0x22 + t] = m
        b[0x10], b[0x11] = 2, 5
    wblob = blob_with(whole_fn)
    wseed = OUT / "tpl_whole_seed.work"
    wseed.write_bytes(brainfile.File(brainfile.CARD_WORK, [part_rec(brainfile.TEMPLATE_REC, wblob)]).encode())
    files, _, (live0,) = ui_run("tpl_part_whole0", [(0x32, 400)], dumps=((part_at + 0x8ed80, 6322),))
    files, _, (live1,) = ui_run(
        "tpl_part_whole", [(0x32, 400)] + to_pane + [(0x20, 400), (0x31, 3000), (0x31, 800), (0x31, 800), (0x31, 4000)],
        roots=((wseed, "BRAIN/card.work"),), dumps=((part_at + 0x8ed80, 6322),))
    def span(b, off, n): return b[off:off + n]
    secs = {"FX ids": (0x00, 16), "FX pages 1": (0x126, 12), "LFO": (0x11a, 6), "LFO designer": (0x1702, 304),
            "INPUT SRC T1 page": (0x02a + 12, 18), "MIDI T1 page 1": (0x3e2, 32), "scenes T1 lock": (0x662, 32),
            "scene A, B": (0x10, 2), "machines": (0x22, 8)}
    bad = [n for n, (o, c) in secs.items() if span(live1, o, c) != span(wblob, o, c)]
    kept = [n for n, (o, c) in {"AMP T1 page 1": (0x120, 6), "levels": (0x12, 16), "sample slots": (0x2ca, 40)}.items()
            if span(live1, o, c) != span(live0, o, c)]
    check(f"templates: PART template APPLY TO..., WHOLE PART: every section equals the template's "
          f"(differing: {bad or 'none'}); the AMP page, the levels and the sample slots keep the project's "
          f"(changed: {kept or 'none'})", not bad and not kept)

    # ---- the PART default: CREATE EMPTY PROJECT and every Part of every bank, the sample slots apart ----
    dblob = blob_with(lambda b: (b.__setitem__(slice(0, 16), bytes(16)), b.__setitem__(slice(0x22, 0x2a), bytes([1] * 8)),
                                 b.__setitem__(slice(0x2ca, 0x2f2), bytes([0x33] * 40))))
    pdseed = OUT / "part_def_seed.work"
    pdseed.write_bytes(brainfile.File(brainfile.CARD_WORK, [part_rec(brainfile.DEFAULT, dblob)]).encode())
    keys_new = [(0x32, 400), (0x1c, 1000), (0x31, 1000), (0x31, 1000), (0x33, 600), (0x31, 1400), (0x31, 13000)]
    files, _, _ = ui_run("part_def_new", keys_new, roots=((pdseed, "BRAIN/card.work"),))
    banks = {k: v for k, v in files.items() if k.upper().endswith(".WORK") and "BANK" in k.upper() and a.name.upper() not in k.upper()}
    probe = dblob[0x662:0x762]                  # scene 0's locks of the eight tracks: wholly in a section, and not clamped by the stock Part validator (the MIDI pages are)
    hits = {k: v.count(probe) for k, v in banks.items()}
    check(f"PART default: CREATE EMPTY PROJECT writes the card's PART default into the Parts of the new project's "
          f"banks (the working and the saved copy of each of four Parts: 8 in a bank file)  {sorted(hits.values())[:4]}...",
          len(banks) >= 1 and all(n == 8 for n in hits.values()))
    check("PART default: the default's sample slot bytes (0x33 x 40) are in none of the new project's banks",
          not any(b"\x33" * 40 in v for v in banks.values()))

    # Part Clear (stock 0x4004a9d0, called as the Part window's CLEAR does) of Part 3: the stock initialiser
    # runs, so the card's default lands on the working Part, and its sample slots are the stock default's
    files, _, (cleared,) = ui_run("part_def_clear", [], roots=((pdseed, "BRAIN/card.work"),),
                                  dumps=((part_at + 0x8ed80 + 2 * 6322, 6322),), extra=("--call", "0x4004a9d0,2"))
    dsecs = {"FX ids": (0x00, 16), "LFO": (0x11a, 6), "MIDI T1 page 1": (0x3e2, 32), "machines": (0x22, 8), "scenes T1 lock": (0x662, 32)}
    badc = [n for n, (o, c) in dsecs.items() if cleared[o:o + c] != dblob[o:o + c]]
    check(f"PART default: Part Clear of Part 3 leaves the default's sections on it (differing: {badc or 'none'}) "
          f"and not its sample slots", not badc and cleared[0x2ca:0x2f2] != dblob[0x2ca:0x2f2])

    # ---- MIDI knob names: NAME KNOB, the CTRL1 label, SAVE TEMPLATE ----------
    # MIDI mode, T1, the CTRL1 page; the shortcut, NAME KNOB (row 6), CC1, the
    # name editor: UP sets the character at its cursor ('0' on an empty name,
    # as RENAME measured), YES. Then the shortcut, SAVE TEMPLATE. Checked: the
    # project's brain.work holds a stock.midi field block for the current
    # bank and Part with track 1 CC1's name; the CTRL1 drawer pushed that
    # name for slot 2 (a PC watch at 0x4004e480, the draw call's arguments);
    # the template carries it as a Name value keyed 129.
    knames_at = symbol("knames")
    hold = ["key 0x25 down", "key 0x2d down", "key 0x2d up", "key 0x25 up"]
    keys = [(0x32, 400), (0x35, 400), (0x10, 500), (0x25, 800)] + hold + [(0x20, 400)] * 5 \
        + [(0x31, 800), (0x31, 1200), (0x33, 300), (0x31, 2500), (0x25, 800)] + hold \
        + [(0x20, 400)] * 2 + [(0x31, 800), (0x31, 2500)]
    files, text, (bank_b, part_b) = ui_run("kn_name", keys, dumps=((0x80000002, 1), (0x80000003, 1)),
                                           extra=("--watch-pc", "0x4004e480"))
    bp = (bank_b[0] & 15) * 4 + (part_b[0] & 3)
    pwork_ = card_file(files, f"{a.set_name}/{a.name}/BRAIN.WORK")
    blocks = [r for r in brainfile.parse(pwork_).records
              if r.kind == brainfile.FIELD_BLOCK and r.store_id == "stock.midi"] if pwork_ else []
    got = {(r.target()[0], v.key): v.data for r in blocks for v in r.values()}
    check(f"knob names: NAME KNOB on MIDI track 1's CC1 writes a stock.midi field block for the current "
          f"bank and Part ({bp})  {got}", got == {(bp, 1): b"0\0\0\0\0\0"})
    label = knames_at + bp * 8 * 10 * 6
    pushed = [ln for ln in text.splitlines() if "at 0x4004e480" in ln and f"[sp " in ln
              and ln.split(":", 2)[-1].split()[0] == f"{label:#x}"]
    check(f"knob names: the CTRL1 page draws CC1 with the name (the label pushed is BRAIN's, "
          f"{len(pushed)} draws)", len(pushed) >= 1)
    work_ = card_file(files, "BRAIN/CARD.WORK")
    trec = [r for r in brainfile.parse(work_).records
            if r.kind == brainfile.TEMPLATE_REC and r.store_id == "stock.midi"] if work_ else []
    names_ = {v.key: v.data for r in trec for v in r.values() if v.type == brainfile.NAME}
    check(f"knob names: SAVE TEMPLATE on the MIDI track carries the name as a Name value keyed 129  {names_}",
          names_ == {129: b"0\0\0\0\0\0"})

    # ---- templates on the SRC page: the target of T1's machine type ---------
    # The machine byte (Part +0x8eda2 + t) names the target (stock.static,
    # .flex, .thru, .neighbor, .pickup); its slots and ranges are the
    # PLAYBACK descriptor's for that machine (brain.stock_slots). SAVE on
    # T1's SRC page, then LOAD of a seeded TPL 99 (each value + 1 inside its
    # count), as for AMP above.
    _, _, (mach_b,) = ui_run("src_machine", [(0x32, 400)], dumps=((part_at + 0x8eda2, 1),))
    mname = brain.MACHINES[mach_b[0]] if mach_b[0] < len(brain.MACHINES) else None
    if mname is None or not brain.stock_slots(mname, rd_stock):
        check(f"templates: T1's machine type {mach_b[0]} has SRC slots to test", False)
    else:
        sid, slay = brain.STOCK_TARGETS[mname]
        slots = brain.stock_slots(mname, rd_stock)
        regions = ((0x8edaa + 6 * mach_b[0], 6), (0x8ef5a + 6 * mach_b[0], 6))
        page, mw, _, part = tpl_run("tpl_src_save", (0x20, 0x20, 0x31, 0x31), None, part_at, (0x32, 0x10, 0x22),
                                    0x22, regions)
        trecs = [r for r in brainfile.parse(mw).records if r.kind == brainfile.TEMPLATE_REC] if mw else []
        got = {v.key: v.data[0] for v in trecs[0].values()} if len(trecs) == 1 else {}
        want = {k: part[k - 1] for k, _n, _l, _c in slots}
        check(f"templates: SAVE TEMPLATE on T1's SRC page ({mname}) writes one {sid} record of its "
              f"{len(want)} Part bytes  {got == want}", len(trecs) == 1 and trecs[0].store_id == sid and got == want)
        seedv = {k: lo + (part[k - 1] - lo + 1) % c if c > 1 else part[k - 1] for k, _n, lo, c in slots}
        vals = b"".join(brainfile.Value(k, brainfile.BYTE, bytes([v])).encode() for k, v in seedv.items())
        seed = brainfile.File(brainfile.CARD_WORK, [brainfile.Record(brainfile.TEMPLATE_REC, sid,
            payload=brainfile.prefix_bytes(brainfile.TEMPLATE_REC, layout=slay, name="TPL 99") + vals)]).encode()
        _, _, _, lp = tpl_run("tpl_src_load", (0x20, 0x20, 0x20, 0x31, 0x31), seed, part_at, (0x32, 0x10, 0x22),
                              0x22, regions)
        bad = [k for k, v in seedv.items() if lp[k - 1] != v]
        check(f"templates: LOAD TEMPLATE of a seeded {sid} TPL 99 writes T1's SRC bytes in the current Part "
              f"({sum(seedv[k] != part[k - 1] for k in seedv)} differ from before, wrong keys {bad})",
              not bad and any(seedv[k] != part[k - 1] for k in seedv))

    # ---- project settings for new projects (stock.project) ------------------
    # Run 1: BRAIN > DEFAULTS > SAVE NEW PROJ writes a card default of the
    # settings bytes (docs/firmware/STORAGE.md section 5) equal to RAM.
    # Run 2: card.work seeded with LOAD_24BIT_FLEX (0x51) = 1 and
    # MIDI_AUTO_CHANNEL (0x47) = 5; PROJECT > CHANGE > <CREATE EMPTY
    # PROJECT>, its name confirmed: the new project.work carries both (a
    # new project's own values are 0 and 10, measured under the port).
    ps_keys = [1 + o for o in range(0x70) if o == 0x24 or 0x28 <= o <= 0x37 or 0x3f <= o <= 0x54
               or 0x56 <= o <= 0x6a]
    keys = [(0x32, 400), (0x1c, 1200)] + [(0x20, 400)] * 4 + [(0x21, 800)] + [(0x31, 800)] + [(0x34, 400)] * 6 + [(0x21, 400)] * 6 + [
        (0x31, 1200), (0x31, 4000), (0x20, 400), (0x31, 2500)]  # PROJECT tab: NEW PROJECT TPL, YES on the name; its screen: APPLY TO PROJECT, SET AS DEFAULT
    files, _, (ram,) = ui_run("pset_save", keys, dumps=((0x80000000, 0x70),))
    work_ = card_file(files, "BRAIN/CARD.WORK")
    prec = [r for r in brainfile.parse(work_).records
            if r.kind == brainfile.DEFAULT and r.store_id == "stock.project"] if work_ else []
    got = {v.key: v.data[0] for v in prec[0].values()} if len(prec) == 1 else {}
    check(f"project settings: SAVE NEW PROJ writes one stock.project default of the {len(ps_keys)} settings "
          f"bytes, equal to RAM  ({len(got)} values)", got == {k: ram[k - 1] for k in ps_keys})
    pseed = OUT / "pset_seed.work"
    pseed.write_bytes(brainfile.File(brainfile.CARD_WORK, [brainfile.Record(brainfile.DEFAULT, "stock.project",
        payload=brainfile.prefix_bytes(brainfile.DEFAULT, layout=0x50524a31)
        + brainfile.Value(1 + 0x51, brainfile.BYTE, b"\x01").encode()
        + brainfile.Value(1 + 0x47, brainfile.BYTE, b"\x05").encode())]).encode())
    keys = [(0x32, 400), (0x1c, 1000), (0x31, 1000), (0x31, 1000), (0x33, 600), (0x31, 1400), (0x31, 13000)]
    files, _, _ = ui_run("pset_new", keys, roots=((pseed, "BRAIN/card.work"),))
    newp = next((v for k, v in files.items() if k.upper().endswith("PROJECT.WORK") and a.name not in k.upper()), None)
    sett = {}
    if newp:
        t_ = newp.decode("latin1")
        sett = dict(l.split("=", 1) for l in t_[t_.find("[SETTINGS]"):t_.find("[/SETTINGS]")].splitlines() if "=" in l)
    got = {k: sett.get(k) for k in ("LOAD_24BIT_FLEX", "MIDI_AUTO_CHANNEL")}
    check(f"project settings: CREATE EMPTY PROJECT applies the card's stock.project default to the new "
          f"project.work  {got}", got == {"LOAD_24BIT_FLEX": "1", "MIDI_AUTO_CHANNEL": "5"})

    # ---- the live screens: BRAIN > MIDI and BRAIN > LOAD ---------------------
    # With the frame timer (--frame) so LOAD METER publishes; each run dumps
    # the screens' data after a few half-second ticks: MIDI's three monitor
    # lines (mon_buf, 3 x 32) and LOAD's figures (load_now, three ints:
    # percent, -1 before a sample; load_peak_us).
    def live_run(tag, script, wait, dumps, seed=None):
        lc, ll = OUT / f"{tag}.img", OUT / f"{tag}.txt"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{tag}"), "--out", str(lc)]
                           + (["--root-file", f"{seed}:BRAIN/card.work"] if seed else []),
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        t, out_lines = 1500, []
        for item in script:
            if isinstance(item, str):
                out_lines.append(f"{t} {item}"); t += 300
            else:
                code, gap = item
                out_lines += [f"{t} key {code:#x} down", f"{t + 30} key {code:#x} up"]; t += gap
        out_lines.append(f"{t + wait} quit")
        (OUT / f"{tag}.script").write_text("\n".join(out_lines) + "\n")
        files_ = [OUT / f"{tag}_d{i}.bin" for i in range(len(dumps))]
        cmd = [EMU, "--image", image, "--card", lc, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
               "--mkii", "--frame", "--live-script", OUT / f"{tag}.script",
               "--mem-dump", ";".join(f"{symbol(sym):#x},{n}={f_}" for (sym, n), f_ in zip(dumps, files_))]
        with open(ll, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode or "ended on quit" not in ll.read_text():
            sys.exit(f"verify_brain: the {tag} run did not finish -- {ll}")
        return [f_.read_bytes() for f_ in files_]

    logon = OUT / "logon.work"       # MIDI LOG is off by default; these runs read the log
    logon.write_bytes(brainfile.File(brainfile.CARD_WORK, [brainfile.Record(
        brainfile.SETTINGS, "octabam.brain",
        payload=brainfile.Value(1, brainfile.BINARY, b"\x01").encode())]).encode())
    into = [(0x1c, 500)] + [(0x20, 500)] * 4 + [(0x21, 500)]     # PROJ, BRAIN's pane
    (mon, mcnt, ata, bts) = live_run("midimon", [(0x32, 500), "midi B0 07 14", "midi C0 02", "midi 91 24 64"]
                                     + into + [(0x20, 500)] * 4 + [(0x31, 500), (0x21, 500)], 2000,
                                     (("mon_buf", 96), ("midi_cnt", 24), ("ata_cmds", 12), ("brain_ts", 96)), seed=logon)
    mc = struct.unpack(">6I", mcnt)
    ac = struct.unpack(">3I", ata)
    check(f"io: the MIDI counters count one note, one controller and one program change  {mc}",
          mc[0] == 1 and mc[1] == 1 and mc[2] == 1)
    ts = struct.unpack(">24I", bts)
    sums = ts[1::2]
    check(f"cpu: the scheduler hook charged time to the idle task and to {sum(1 for x in sums if x)} slots in all  {list(sums)}",
          sums[10] > 0 and sum(1 for x in sums if x) >= 3)
    check(f"io: the ATA hook counted the card's reads while the project loaded  {ac}", ac[0] > 0)
    got = [mon[i * 32:i * 32 + 32].split(b"\0")[0].decode("ascii", "replace") for i in range(3)][::-1]   # newest first
    check(f"midimon: BRAIN > MIDI shows the last three messages decoded  {got}",
          got[0].startswith("CH01 CC") and got[0].replace(" ", "").endswith("7=20")
          and got[1].startswith("CH01 PC") and got[2].startswith("CH02 NOTE"))
    now, peak = live_run("loadview", [(0x32, 500)] + into + [(0x20, 500)] * 3 + [(0x31, 500)], 20000,
                         (("load_now", 12), ("load_peak_us", 4)))
    pcts = struct.unpack(">3i", now)
    check(f"otop: BRAIN > OTOP has LOAD METER's figures: the frame interrupt's share and its longest run, "
          f"and each DSP core's (no DSP runs here: -1)  {pcts}, {struct.unpack('>I', peak)[0]} us",
          pcts[0] >= 0 and pcts[1] == -1 and pcts[2] == -1 and struct.unpack(">I", peak)[0] > 0)

    # ---- debug log: the MIDI thread's messages to /BRAIN/debug.txt ----------
    log_at = symbol("brain_post_log")
    lcard, lafter, llog, lmidi = OUT / "log.img", OUT / "log_after.img", OUT / "log.txt", OUT / "log.midi"
    lmidi.write_text("40 B0 07 14\n60 C0 02\n80 B1 28 40\n")
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree_log"), "--out", str(lcard),
                        "--root-file", f"{logon}:BRAIN/card.work"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    cmd = [EMU, "--image", image, "--card", lcard, "--set", a.set_name, "--project", a.name,
           "--mount", "--load-ms", "90000", "--sequencer", "--internal-clock", "--frames", "400",
           "--midi", lmidi, "--step", f"200:call:{log_at:#x}", "--card-out", lafter]
    with open(llog, "w") as fh:
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    files = emu_card.extract_image(lafter.read_bytes()) if lafter.exists() else {}
    dbg = next((v for k, v in files.items() if k.upper().endswith("BRAIN/DEBUG.TXT")), b"").decode("ascii", "replace")
    rows = [l.split() for l in dbg.splitlines()[2:]]
    want = [["B0", "07", "14"], ["C0", "02", "00"], ["B1", "28", "40"]]
    check(f"log: debug.txt holds the three messages as sent, in order  {[r[1:4] for r in rows]}",
          [r[1:4] for r in rows] == want)
    check(f"log: the program change left pattern {rows[1][6] if len(rows) > 1 else '?'} queued (sent 2)",
          len(rows) > 1 and rows[1][6] == "2")

    # ---- mode: MODE DEFAULTS' view takes the card's values ------------------
    if "MODE DEFAULTS" in remix.modules and t1.mode_views:
        mcopy = OUT / "project_mode"
        shutil.rmtree(mcopy, ignore_errors=True)
        shutil.copytree(copy, mcopy)
        ot_project.set_fx(mcopy, "fx2", 1, t1.key, page=[p.default or 0 for p in t1.params[:6]],
                          page2=[p.default or 0 for p in t1.params[6:12]], guard=False)
        if bus:      # GRAIN's view lists FDBK, SCTR, GLEN; DEL (slot 0) is the slot it does not list
            card_vals, slot_of, mode_label, skipped = {"FDBK": 77, "SCTR": 33, "GLEN": 2, "DEL": 5}, \
                {"FDBK": 2, "SCTR": 7, "GLEN": 9, "DEL": 0}, "GRAIN", 0
        else:        # MODULATION's mode 1 lists RATE, DLY, FDBK; LOFI (slot 4) is the slot it does not list
            card_vals, slot_of, mode_label, skipped = {"RATE": 77, "DLY": 33, "FDBK": 100, "LOFI": 5}, \
                {"RATE": 0, "DLY": 2, "FDBK": 3, "LOFI": 4}, 1, 4
        mwork = OUT / "mode_card.work"
        mwork.write_bytes(ot_brain.set_default(None, t1, card_vals, mode=mode_label))
        card = OUT / "mode.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(mcopy), a.set_name, a.name,
                            "--tree", str(OUT / "tree_mode"), "--out", str(card),
                            "--root-file", f"{mwork}:BRAIN/card.work"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_brain: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        lanes_dump, cdump, log = OUT / "mode_lanes.bin", OUT / "mode_counts.bin", OUT / "mode.txt"
        cmd = [EMU, "--image", image, "--card", card, "--set", a.set_name, "--project", a.name,
               "--mount", "--load-ms", "90000",
               "--step", f"-:dump:{counts_at:#x},{4 * len(COUNTERS)}={cdump}",
               "--step", "-:poke:0x80000000=0;0x100b14cc=0",
               "--step", f"-:call:{FX2_EDITOR:#x},{t1.mode_slot - 6},2",
               "--step", f"-:dump:{LANES:#x},576={lanes_dump}"]
        with open(log, "w") as fh:
            fh.write(" ".join(map(str, cmd)) + "\n"); fh.flush()
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode or "returned, d0" not in log.read_text():
            sys.exit(f"verify_brain: the mode run did not complete its call -- {log}")
        counts = dict(zip(COUNTERS, struct.unpack(f">{len(COUNTERS)}I", cdump.read_bytes())))
        print(f"  mode: counters {counts}")
        lane = lanes_dump.read_bytes()[:72]
        got_mode = lane[0x38 + t1.mode_slot - 6]
        view = next(v for v in t1.mode_views if v.mode == 1)
        check(f"mode: T1 {t1.key} MODE -> {got_mode} (view mode 1)", got_mode == 1)
        for slot, val in sorted(view.defaults.items()):
            want_v = next((card_vals[n] for n, s in slot_of.items() if s == slot and n in card_vals), val)
            off = (0x18 + slot) if slot < 6 else (0x38 + slot - 6)
            check(f"mode: slot {slot:2d} lane = {lane[off]:3d}  (view {val}, expected {want_v})", lane[off] == want_v)
        check(f"mode: slot {skipped}, one the view does not list, skipped ({counts['skip_slot']}) and untouched "
              f"(lane {lane[0x18 + skipped]}, default {t1.params[skipped].default or 0})",
              counts["skip_slot"] == 1 and lane[0x18 + skipped] == (t1.params[skipped].default or 0))
    print(f"verify_brain: {'ok' if not fails else 'FAILED'} ({fails} failure(s)) -- {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
