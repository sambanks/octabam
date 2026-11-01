#!/usr/bin/env python3
"""SCENES P2 under the port: page-2 locks reach the DSP frame through the
crossfader, a page-2 knob turned with a scene held writes a cell, and stock
scene copy and paste carry the cells.

    python3 tools/verify/verify_scenes_p2.py REMIX --project DIR

Stages a disposable project copy and boots the remix's image in `ot_emu`.
For EUCLID compositions the fixture selects RATE/MIX on T1, sets unclamped
knob values, enables scenes and starts T1 on step 1; a MIDI-only template
otherwise leaves the audio track's playing-Part pointer unset during the
120-frame probe. Other remixes retain the MODE/TIME fixture below.

The checks are:

  frame   pokes cells into every bank's part-0 window (bytes 30, 31 of the
          stock scene block; scene 0: T1 FX2 MODE = 1 and TIME = 100;
          scene 1: TIME = 20), selects scenes 0/1,
          clears both scene-disable bytes, sets the fader and the stock
          weight table, runs 120 frames with the transport on, and reads
          T1's voice record (0x80000110, both pings): at fader 64 MODE must
          snap to the A side (1) and TIME lerp to 60; at fader 0 the B side
          alone: MODE the knob (measured by a run with no cells),
          TIME 20. The three runs are three boots side by side (each is one
          LOAD PROJECT): a cell poked once the
          transport has started never reaches the live lane, with or
          without a transport restart (measured 28 Sep 2026), so each
          needs the machine as it was after the load: the port loads once
          and forks one child per run (`ot_emu --scenario`), the editor
          pass a fourth.
  editor  calls the FX2 page-2 editor `0x4003a9dc(5, 2 ticks)` on T1 with
          scene A held (0x460d169c = 1): the Part byte and the live lane
          must not move; scene 0's cells in the Part DB's part-0 window
          and its SRAM twin must hold one lock (track 0, FX2 slot 5) whose
          value is the knob's plus the ticks' step. Then, on the same boot
          (`ot_emu --step`), cell 0 is poked to 50 and the call repeated:
          the same cell updated, the other seven empty. Then the same with
          FUNCTION held (0x46100b1d bit 5): the cell empty. Then all eight cells
          are poked with other locks and the call repeated: the turn is
          dropped, the cells unchanged.
  paste   the stock scene copy `0x400274cc(0, 0)` and paste
          `0x40027578(0, 3)` on part 0 with cells in scene 0: scene 3's
          cells equal scene 0's.

SKIPs without a project, without the port, or for a remix without SCENES
P2.
"""
import argparse, os, pathlib, re, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/scenesp2verify"
BLOB, BANK_STRIDE, PART_STRIDE = 0x400e21e0, 0x9b340, 0x18b2
CELL0, SEL_OFF = 0x8f400, 0x8ed90     # scene s, cell c at CELL0 + 0x100*s + 0x20*c
RECORDS, DBPTR, SRAM_PART = 0x80000110, 0x46c82456, 0x100a4ece
WEIGHTS, FADER, SCENE_HELD = 0x80003c60, 0x460d16c8, 0x460d169c
TRACK_CUR, PART_DISP = 0x80000000, 0x100b14cf
FX2_EDITOR, SCENE_COPY, SCENE_PASTE = 0x4003a9dc, 0x400274cc, 0x40027578
LANES = 0x80000810


def pokes_bytes(addr, data):
    return [f"{addr + i:#x}={v:#x}" for i, v in enumerate(data)]


def cell_pokes(window, cells):
    """cells: {(scene, cell): (key, value)} -> pokes into a part window."""
    out = []
    for (sc, c), (key, val) in cells.items():
        out += pokes_bytes(window + CELL0 + 0x100 * sc + 0x20 * c, [key, val])
    return out


def cells_of(dump):
    """A 0x100-byte dump of one scene's blocks -> its eight (key, value) cells."""
    return [(dump[0x20 * c + 30], dump[0x20 * c + 31]) for c in range(8)]


EMPTY = (0xff, 0xff)


def weights(xf):
    hi = (-258 * xf) & 0xffff
    lo = (0x8000 + 258 * xf) & 0xffff
    w = (hi << 16) | lo
    out = []
    for t in range(10):
        out += pokes_bytes(WEIGHTS + 4 * t, w.to_bytes(4, "big"))
    return out + pokes_bytes(FADER, xf.to_bytes(4, "big"))


def run(cmd, log):
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_scenes_p2: ot_emu exit {r.returncode} -- {log}")
    return log.read_text()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="OCTABAM")
    ap.add_argument("--name", default="SCENESP2")
    ap.add_argument("--image", default="")
    ap.add_argument("--out", default="", help="scratch dir (default out/scenesp2verify)")
    a = ap.parse_args()
    global OUT
    if a.out:
        OUT = pathlib.Path(a.out)
    remix = registry.remix(a.remix)
    if "SCENES P2" not in remix.modules:
        print(f"  [ -- ] verify_scenes_p2: {a.remix} carries no SCENES P2"); return 0
    if not a.project:
        print("  [SKIP] verify_scenes_p2: no project (OT_PROJECT=<dir> or --project)"); return 0
    if "/out/fresh/" in str(a.project):
        print("  [SKIP] verify_scenes_p2: the project is a generated empty one (tools/hw/ot_fresh.py); the gate "
              "reads its expected values from a project with scene data"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_scenes_p2: no port binary (make emu-cf)"); return 0
    pdir = pathlib.Path(a.project).expanduser()
    if not (pdir / "project.work").is_file():
        sys.exit(f"verify_scenes_p2: {pdir} is not a project")
    OUT.mkdir(parents=True, exist_ok=True)
    image = pathlib.Path(a.image) if a.image else OUT / "mainos.bin"
    if not a.image:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_scenes_p2: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    copy = OUT / "project"
    if copy.exists():
        shutil.rmtree(copy)
    copy.mkdir(parents=True)
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)
    # The combined EVENTS fixture has EUCLID rather than the bus effect
    # whose page-two MODE/TIME layout this gate originally assumed. Select
    # its real RATE/MIX pair in the disposable copy: a stepped selector and
    # a continuous value exercise the same snap/interpolation contract.
    select_slot, select_name, value_name = 0, "MODE", "TIME"
    if "EUCLID" in remix.modules:
        from hw import ot_project as otp
        effect = registry.bound(remix)["EUCLID"]
        defaults = otp.module_defaults(effect, {"RATE": 0, "MIX": 64})
        otp.set_fx(copy, "fx2", 1, str(effect.menu.fx2_id),
                   page=defaults[:6], page2=defaults[6:], guard=False)
        # The 120-frame probe ends before step 2 at 120 BPM. Activate T1
        # on the first step so its native playing-Part pointer is valid even
        # when the supplied template contains only MIDI trigs.
        for bank_file in copy.glob("bank*.work"):
            def activate(data):
                data[otp.trac_off(0, 0) + 7] |= 1
            otp._bank_write(copy, int(bank_file.stem[4:]), activate, guard=False)
        select_slot, select_name, value_name = 1, "RATE", "MIX"
        project_file = copy / "project.work"
        project_file.write_bytes(re.sub(rb"(SCENE_[AB]_MUTE=)1", rb"\g<1>0", project_file.read_bytes()))
    select_byte = 48 + select_slot
    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_scenes_p2: stage_card failed:\n{r.stdout[-1000:]}{r.stderr[-1000:]}")
    base = [str(EMU), "--image", str(image), "--card", str(card), "--set", a.set_name, "--project", a.name,
            "--load-ms", "90000"]
    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    # ---- the frame pass ---------------------------------------------------
    # the cells (key = track<<4 | fx1<<3 | slot2): scene 0 / T1 / FX2 slot 5
    # (TIME) = 100 and slot 0 (MODE) = 1, scene 1 / T1 / slot 5 = 20 -- in
    # part 0 of every bank (the playing bank is the saved one, not bank 0)
    cells = {(0, 0): (0x05, 100), (1, 0): (0x05, 20), (0, 3): (select_slot, 1)}

    def frames(tag, cells, xf):
        """One frame run as a scenario: (log, args, dump)."""
        common = []
        for bank in range(16):
            common += cell_pokes(BLOB + bank * BANK_STRIDE, cells)
            common += pokes_bytes(BLOB + bank * BANK_STRIDE + SEL_OFF, [0, 1])
        common += ["0x80000006=0", "0x80000007=0"]
        tag_ = tag.replace(" ", "_")
        dump, log = OUT / f"rec_{tag_}.bin", OUT / f"frames_{tag_}.txt"
        args = ["--sequencer", "--internal-clock", "--frames", "120", "--main-level", "64",
                "--poke-trig", "2", "--poke", ";".join(common + weights(xf)),
                "--mem-dump", f"{RECORDS:#x},1024={dump}"]
        return log, args, dump

    # ---- the editor with a scene held: one boot, both seeds ----------------
    early = f"{TRACK_CUR:#x}=0;{SCENE_HELD + 3:#x}=1;{PART_DISP:#x}=0"
    # None: no lock yet; 50: cell 0 holds 50; "func": cell 0 holds 50 and
    # FUNCTION is held; "full": eight other locks
    FULL = {(0, c): (0x10 * (c // 6 + 1) + c % 6, 30 + c) for c in range(8)}
    SEEDS = (None, 50, "func", "full")
    KFUNC_ROW = 0x46100b1d                 # FUNCTION: row 5, bit 5

    def dumps_for(seed):
        d = OUT / f"editor_{seed}"
        d.mkdir(parents=True, exist_ok=True)
        return d, ";".join([f"{DBPTR:#x},4={d / 'dbptr.bin'}"]
                           + [f"{BLOB + b * BANK_STRIDE + CELL0 - 30:#x},256={d / f'scene_{b}.bin'}" for b in range(16)]
                           + [f"{BLOB + b * BANK_STRIDE + 0x8f084:#x},6={d / f'p2_{b}.bin'}" for b in range(16)]
                           + [f"{SRAM_PART + CELL0 - 30 - 0x8ed80:#x},256={d / 'scene_sram.bin'}",
                              f"{LANES + 0x38:#x},6={d / 'lane.bin'}"])

    def editor():
        """Both seeds as one scenario: (log, args)."""
        steps = []
        for seed in SEEDS:
            pokes = early
            seeded = ({(0, 0): (0x05, seed)} if isinstance(seed, int) else {(0, 0): (0x05, 50)} if seed == "func"
                      else FULL if seed == "full" else {})
            pokes += f";{KFUNC_ROW:#x}={0x20 if seed == 'func' else 0}"
            for b in range(16):
                pk = cell_pokes(BLOB + b * BANK_STRIDE, seeded)
                if pk:
                    pokes += ";" + ";".join(pk)
            steps += ["--step", f"-:poke:{pokes}", "--step", f"-:call:{FX2_EDITOR:#x},5,2",
                      "--step", f"-:dump:{dumps_for(seed)[1]}"]
        return OUT / "editor.txt", steps

    # ---- stock scene copy then paste: scene 0 -> scene 3 of part 0 ----------
    def paste():
        d = OUT / "paste"
        d.mkdir(parents=True, exist_ok=True)
        pokes = [f"{PART_DISP:#x}=0", "0x80000003=0"]
        for b in range(16):
            pokes += cell_pokes(BLOB + b * BANK_STRIDE, {(0, 0): (0x05, 77), (0, 5): (0x1b, 9)})
        dumps = ";".join([f"{DBPTR:#x},4={d / 'dbptr.bin'}"]
                         + [f"{BLOB + b * BANK_STRIDE + CELL0 - 30 + 0x100 * sc:#x},256={d / f's{sc}_{b}.bin'}"
                            for b in range(16) for sc in (0, 3)])
        return d, OUT / "paste.txt", ["--step", f"-:poke:{';'.join(pokes)}",
                                      "--step", f"-:call:{SCENE_COPY:#x},0,0",
                                      "--step", f"-:call:{SCENE_PASTE:#x},0,3",
                                      "--step", f"-:dump:{dumps}"]

    # the knob alone: the same run with no cells, so what fader 0
    # (the B side, which holds no MODE lock) must read is measured from the
    # project: T1's MODE is 1 in the stress fixture's part 0 and 0 in
    # OCTABAM89_setgate's (a literal 0 failed `make accept`, 26 Sep 2026)
    # ONE load, four scenarios forked from it (ot_emu --scenario, 29 Sep
    # 2026): the three frame runs and the editor pass each start from the
    # same loaded machine. Until then each was its own LOAD PROJECT, three
    # side by side and one after.
    specs = {tag: frames(tag, pl, xf)
             for tag, pl, xf in (("knob", {}, 0), ("fader 64", cells, 64), ("fader 0", cells, 0))}
    elog, eargs = editor()
    pdir_, plog, pargs = paste()
    scen = ([f"{log} " + " ".join(args) for log, args, _ in specs.values()]
            + [f"{elog} " + " ".join(eargs), f"{plog} " + " ".join(pargs)])
    cmd = base + ["--dsp"] + [x for s in scen for x in ("--scenario", s)]
    run(cmd, OUT / "port.txt")
    results = {}
    for tag, (log, _, dump) in specs.items():
        text = log.read_text()
        rec = dump.read_bytes() if dump.is_file() else bytes(1024)
        results[tag] = ("frames run : 120" in text, [rec[ping * 0x200:ping * 0x200 + 64] for ping in (0, 1)])
    editor_text = elog.read_text()
    for tag, (ran, _) in results.items():
        check(f"{tag}: 120 frames ran", ran)
    recs = {tag: r for tag, (_, r) in results.items()}
    knob = recs["knob"]
    knob_mode = knob[0][select_byte]
    check(f"knob alone: both pings read T1 {select_name} {knob_mode}", knob[1][select_byte] == knob_mode)
    for xf, want_mode, want_time, why in ((64, 1, 60, "the A side, a select snaps"),
                                          (0, knob_mode, 20, "the knob, B alone")):
        for ping, r in enumerate(recs[f"fader {xf}"]):
            check(f"fader {xf}: ping {ping} T1 {select_name} (record byte {select_byte}) = {r[select_byte]} (want {want_mode}: {why})",
                  r[select_byte] == want_mode)
            check(f"fader {xf}: ping {ping} T1 {value_name} (hw 26 lo) = {r[53]} (want {want_time})", r[53] == want_time)

    # ---- the editor's checks ------------------------------------------------
    check(f"editor: all {len(SEEDS)} calls returned", editor_text.count("returned, d0") == len(SEEDS))
    for seed in SEEDS:
        d = dumps_for(seed)[0]
        db = int.from_bytes((d / "dbptr.bin").read_bytes(), "big")
        bank = (db - BLOB) // BANK_STRIDE
        got = cells_of((d / f"scene_{bank}.bin").read_bytes())
        sram = cells_of((d / "scene_sram.bin").read_bytes())
        lane = (d / "lane.bin").read_bytes()
        part = (d / f"p2_{bank}.bin").read_bytes()
        knob = part[5]
        if seed == "full":
            want = [FULL[(0, c)] for c in range(8)]
            check(f"editor (seed full): eight locks held, the turn dropped ({got})", got == want)
            check(f"editor (seed full): the Part byte ({knob}) and the lane ({lane[5]}) did not take the turn",
                  knob == lane[5])
            continue
        check(f"editor (seed {seed}): the SRAM twin's scene 0 cells match bank {bank}'s part 0", sram == got)
        if seed == "func":
            check(f"editor (seed func): FUNCTION + turn removed the lock ({got[0]})", got[0][0] & 0x80 and
                  got[1:] == [EMPTY] * 7)
            continue
        check(f"editor (seed {seed}): cell 0 = T1 FX2 slot 5 ({got[0][0]:#04x}), cells 1-7 empty",
              got[0][0] == 0x05 and got[1:] == [EMPTY] * 7)
        start = seed if seed is not None else knob
        check(f"editor (seed {seed}): value {got[0][1]} moved up from {start} by the ticks", start < got[0][1] <= start + 4)
        check(f"editor (seed {seed}): the Part byte ({knob}) and the lane ({lane[5]}) did not take the turn",
              knob == lane[5] and knob != got[0][1])

    # ---- copy and paste -------------------------------------------------------
    ptext = plog.read_text()
    check("paste: copy and paste returned", ptext.count("returned, d0") == 2)
    db = int.from_bytes((pdir_ / "dbptr.bin").read_bytes(), "big")
    bank = (db - BLOB) // BANK_STRIDE
    s0 = cells_of((pdir_ / f"s0_{bank}.bin").read_bytes())
    s3 = cells_of((pdir_ / f"s3_{bank}.bin").read_bytes())
    check(f"paste: scene 0 holds the two locks ({s0[0]}, {s0[5]})", s0[0] == (0x05, 77) and s0[5] == (0x1b, 9))
    check(f"paste: scene 3's cells equal scene 0's in bank {bank}", s3 == s0)
    print(f"verify_scenes_p2: {'FAIL' if fails else 'ok'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
