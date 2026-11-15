#!/usr/bin/env python3
"""MODE DEFAULTS under the port: a page-2 editor call that lands on a MODE
leaves that mode's view in the track's live lane.

    python3 tools/verify/verify_mode_defaults.py REMIX --project DIR

Stages the project (T1's FX2 and T2's FX1 rewritten into every part of every
bank: the emulated load applies bank A part 1), boots the remix's image in
`ot_emu` ONCE, LOAD PROJECTs, and calls the editor as the panel would
(`--step`: the current-track pokes, the call and the lane dump for each
case in turn, after the load and before the transport; then, with CC MAP in
the remix, the transport starts, which re-applies the part's bytes over the
live lane, and the CC arrives over MIDI IN):

  FX2: `0x4003a9dc(0, 2 ticks)` on T1 (BusDelay: slot 6 = MODE, CLEAN -> GRAIN)
  FX1: `0x4003abe4(1, 2 ticks)` on T2 (Modulation: slot 6 = MODE, JUNO -> DIM)

then reads the live lane (`0x80000810 + t*72`: page 1 at +0x12 (FX1) /
+0x18 (FX2), page 2 at +0x32 / +0x38) and asserts every (slot, value) of
the landed mode's ModeView, and that the MODE byte itself moved. A control
run of the same calls on the stock editors (the same image with the module's
detours skipped is not buildable here, so the control is the lane BEFORE the
call: the fixture's stamped bytes) shows what the editor alone changes.

SKIPs without a project (OT_PROJECT / --project), without the port, or for
a remix without MODE DEFAULTS. What it cannot see: the panel redraw, the
DSP receiving page 1 (the page-1 writer's live byte is what the frame
builder reads; verify_set covers the delivery).
"""
import argparse, os, pathlib, re, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import registry  # noqa: E402
import ot_project  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _cc_map_ccs():
    """CC MAP's page-2 CCs (FX2, FX1), slot 6..11 order, from its manifest (as verify_cc_map reads them)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ccmap_manifest_md", ROOT / "modules/cc-map/manifest.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FX2_CCS, mod.FX1_CCS


CC_MAP_FX2, CC_MAP_FX1 = _cc_map_ccs()
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/modedefverify"
LANES = 0x80000810
FX2_EDITOR, FX1_EDITOR = 0x4003a9dc, 0x4003abe4
PAGE1 = {"fx1": 0x12, "fx2": 0x18}
PAGE2 = {"fx1": 0x32, "fx2": 0x38}


def lane_bytes(path, track):
    raw = path.read_bytes()
    return raw[track * 72:(track + 1) * 72]


def expect_view(mod, mode):
    for v in mod.mode_views:
        if v.mode == mode:
            return v
    return None


def run_port(image, card, set_name, name, steps, midi, dump, log):
    """One boot: the post-load steps in order, then (with `midi`) the
    transport and the MIDI file, then the end dump."""
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", set_name, "--project", name,
           "--mount", "--load-ms", "90000"]
    for s in steps:
        cmd += ["--step", s]
    if midi:
        cmd += ["--sequencer", "--internal-clock", "--frames", "120", "--midi", str(midi),
                "--mem-dump", f"{LANES:#x},576={dump}"]
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text()
    calls = sum(1 for s in steps if ":call:" in s)
    if r.returncode or text.count("returned, d0") < calls:
        sys.exit(f"verify_mode_defaults: ot_emu did not complete the {calls} call(s) -- {log}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="OCTABAM")
    ap.add_argument("--name", default="MODEDEF")
    ap.add_argument("--image", default="")
    a = ap.parse_args()
    remix = registry.remix(a.remix)
    if "MODE DEFAULTS" not in remix.modules:
        print(f"  [ -- ] verify_mode_defaults: {a.remix} carries no MODE DEFAULTS"); return 0
    if not a.project:
        print("  [SKIP] verify_mode_defaults: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_mode_defaults: no port binary (make emu-cf)"); return 0
    pdir = pathlib.Path(a.project).expanduser()
    if not (pdir / "project.work").is_file():
        sys.exit(f"verify_mode_defaults: {pdir} is not a project")
    mods = registry.modules()
    OUT.mkdir(parents=True, exist_ok=True)

    image = pathlib.Path(a.image) if a.image else OUT / "mainos.bin"
    if not a.image:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_mode_defaults: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    # The fixture: T1 FX2 = the first FX2 module with views, T2 FX1 = the
    # first FX1 module with views, both at their manifest defaults (MODE 0),
    # in every part of every bank.
    cases = []
    for kind, keys in (("fx2", [k for k in remix.modules if k not in remix.fx1]),
                       ("fx1", list(remix.fx1))):
        best = None
        for k in keys:
            m = mods[k]
            if getattr(m, "mode_views", ()) and m.mode_slot is not None and m.menu is not None:
                if best is None or len(m.mode_views) > len(best[2].mode_views):
                    best = (kind, k, m)
        if best:
            cases.append(best)
    if not cases:
        print("  [ -- ] verify_mode_defaults: no module with ModeViews in the remix"); return 0
    copy = OUT / "project"
    if copy.exists():
        shutil.rmtree(copy)
    copy.mkdir(parents=True)
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)
    tracks = {"fx2": 0, "fx1": 1}
    for kind, k, m in cases:
        p1 = [p.default or 0 for p in m.params[:6]]
        p2 = [p.default or 0 for p in m.params[6:12]]
        ot_project.set_fx(copy, kind, tracks[kind] + 1, k, page=p1, page2=p2, guard=False)
    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_mode_defaults: stage_card failed:\n{r.stdout[-1000:]}{r.stderr[-1000:]}")

    fails = 0
    # One boot for everything: each case's current-track pokes (both bytes,
    # as a track key moves them), its editor call
    # and its lane dump, after the load; then the MIDI path below on the
    # same boot. The editor takes ENCODER ticks: 256 units a tick against
    # the slot's step (0x46c7dede + slot2*20 + 8: 0x10e for a 3-way select,
    # 0x100 for a knob under the port), so two ticks move a select by one
    # and a knob-stepped select by two. The landed MODE is read back.
    steps, dumps = [], {}
    for kind, k, m in cases:
        t = tracks[kind]
        editor = FX2_EDITOR if kind == "fx2" else FX1_EDITOR
        dumps[kind] = OUT / f"{kind}_lanes.bin"
        steps += [f"-:poke:0x80000000={t};0x100b14cc={t}",
                  f"-:call:{editor:#x},{m.mode_slot - 6},2",
                  f"-:dump:{LANES:#x},576={dumps[kind]}"]
    midi = cc_dump = None
    cc_case = None
    if "CC MAP" in remix.modules and cases:
        # CC MAP's FX2 block writes only on bus hosts (Part FX2 id 6 or 7:
        # its clamp tables are theirs, modules/cc-map/cc_map.s); the FX1
        # block writes for any non-zero FX1 id. Take the first case the cave
        # can write, so a remix without a bus host still exercises the
        # MODE DEFAULTS adapter over the FX1 block.
        for kind0, k0, m0 in cases:
            if kind0 == "fx2" and (m0.menu is None or m0.menu.fx2_id not in (6, 7)):
                continue
            slot2 = m0.mode_slot - 6
            # a mode the editor step (+2 ticks, MODE 1 or 2) cannot have left: with MODE 1 already in the lane
            # (octabam, 15 Nov 2026) a CC of 1 passed with or without CC MAP's write
            want_mode = next((v for v in (3, 1, 2) if expect_view(m0, v)), None)
            if want_mode is not None:
                # CC MAP's own numbers (modules/cc-map/manifest.py FX2_CCS, FX1_CCS): page 2 moved off the pedal
                # CCs on 1 Nov 2026 (#981; 62-67 and 68-73 before), and the gate sent the old ones until 15 Nov
                cc = (CC_MAP_FX2 if kind0 == "fx2" else CC_MAP_FX1)[slot2]
                midi = OUT / "cc.midi"
                # the case's track's own channel (MIDI_TRIG_CHn, as verify_set reads it). Until 15 Nov 2026 the CC
                # went on channel 1, T1's, for T2's FX1 case: it never reached T2, and the check passed only while
                # the editor step had left the mode it asked for (octabam: MODE 1)
                raw = (copy / "project.work").read_bytes().decode("latin1")
                chans = [int(c) for c in re.findall(r"MIDI_TRIG_CH\d=(-?\d+)", raw)][:8]
                ch = chans[tracks[kind0]] & 0xf if len(chans) > tracks[kind0] else 0
                midi.write_text(f"40 B{ch:X} {cc:02X} {want_mode:02X}\n")
                cc_dump = OUT / f"cc_{kind0}_lanes.bin"
                cc_case = (kind0, k0, m0, slot2, cc, want_mode)
                break
    log = OUT / "port.txt"
    run_port(image, card, a.set_name, a.name, steps, midi, cc_dump, log)
    for kind, k, m in cases:
        t = tracks[kind]
        slot2 = m.mode_slot - 6
        lane = lane_bytes(dumps[kind], t)
        got_mode = lane[PAGE2[kind] + slot2]
        view = expect_view(m, got_mode) if got_mode else None
        ok = view is not None
        print(f"  [{'ok' if ok else 'FAIL'}] {k} T{t + 1}: {kind.upper()} editor slot {m.mode_slot} +2 ticks -> MODE {got_mode}"
              f"{'' if ok else ' (no view for it)'}")
        fails += not ok
        if not ok:
            continue
        for slot, val in sorted(view.defaults.items()):
            off = PAGE1[kind] + slot if slot < 6 else PAGE2[kind] + slot - 6
            got = lane[off]
            name = m.params[slot].name.decode()
            ok = got == val
            print(f"  [{'ok' if ok else 'FAIL'}]   slot {slot:2d} {name:4s} lane +{off:#04x} = {got:3d}  (view {val})")
            fails += not ok
        # a slot the view leaves alone keeps the fixture's default
        untouched = [s for s in range(12) if s not in view.defaults and s != m.mode_slot]
        for slot in untouched[:2]:
            off = PAGE1[kind] + slot if slot < 6 else PAGE2[kind] + slot - 6
            got, want = lane[off], m.params[slot].default
            ok = got == want
            print(f"  [{'ok' if ok else 'FAIL'}]   slot {slot:2d} {m.params[slot].name.decode():4s} untouched = {got} (default {want})")
            fails += not ok
    # ---- the MIDI path: CC MAP's cave calls the unit after its write --------
    # The transport start re-applied the part's bytes over the live lane,
    # so the CC lands on MODE 0, as the two-boot form of this gate had it.
    if cc_case:
        kind, k, m, slot2, cc, want_mode = cc_case
        t = tracks[kind]
        lane = lane_bytes(cc_dump, t)
        got_mode = lane[PAGE2[kind] + slot2]
        view = expect_view(m, got_mode) if got_mode == want_mode else None
        ok = view is not None
        print(f"  [{'ok' if ok else 'FAIL'}] {k} T{t + 1}: CC {cc} = {want_mode} over MIDI IN -> MODE {got_mode} (CC MAP's cave calls the unit)")
        fails += not ok
        if ok:
            for slot, val in sorted(view.defaults.items()):
                off = PAGE1[kind] + slot if slot < 6 else PAGE2[kind] + slot - 6
                got = lane[off]
                okv = got == val
                print(f"  [{'ok' if okv else 'FAIL'}]   slot {slot:2d} {m.params[slot].name.decode():4s} lane +{off:#04x} = {got:3d}  (view {val})")
                fails += not okv
    print(f"verify_mode_defaults: {'FAIL' if fails else 'ok'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
