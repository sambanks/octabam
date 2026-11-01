#!/usr/bin/env python3
"""The octabam hardware suite: every project it needs, the phases that run over the one cable, and a summary.

    python3 tools/hw/ot_suite.py plan  [--remix octabam]
    python3 tools/hw/ot_suite.py build [DEST] [--src FRESH] [--remix octabam]
    python3 tools/hw/ot_suite.py run   LABEL [--dest DEST] [--phase ID,ID] [--yes] [--keep-going]
    python3 tools/hw/ot_suite.py report LABEL

`build` writes, under DEST (default out/suite), from a fresh unit-made or port-made project (`ot_fresh.py`):

    SFX_01..NN  the remix's effect layouts (`ot_matrix.py plan`), generated stimuli on all 8 tracks
    SSCN        SFX_01 + MIDI SCENES stamp: MIDI track 1 ch 11, all 16 scenes locked
    SDJ         SFX_01 + DIRECT_JUMP_KYOTI stamp: pattern 2 on steps 1,2,4,7,8,11,13

and `suite.json`, which names the project, the layouts and the demand-loader transitions each phase uses. The layout
list comes from the remix's manifests at build time, so a module added to the remix (DISTORX) is in the next build.
The audio is `ot_stimuli.py`'s synthetic material; no file from Elektron is read except the user's own fresh project.

`run` executes the phases in order. When a phase needs another project, it prints the load steps and waits (the card
and the panel are not reachable from the Mac). A phase passes when its tool exits 0. Phases that need a panel action
say so in `needs`; the manual plan (docs/contributing/HARDWARE_MANUAL.md) covers everything that has no phase.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = sys.executable
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

STIMULI = "hits,pink,two_tones,sweep,ladder,impulses"
PER_PROJECT = 32                    # ot_matrix.PER_PROJECT: BASE + 31
REVERBS = ("PLATE REV", "SPRING REV", "DARK REV")
OUT = ROOT / "out/hw/suite"


def layout_names(remix):
    import ot_matrix as M
    return [l[0] for l in M.layouts(remix)]


def locate(names):
    """name -> (project number, slot) for the layouts `proj` writes (slot 0 of each project is BASE)."""
    per = PER_PROJECT - 1
    return {n: ((i - 1) // per + 1, (i - 1) % per + 1) for i, n in enumerate(names) if i > 0}


def demand(remix):
    """The effects the remix loads into the shared window on demand (`window_demand`)."""
    from remix import registry
    return tuple(registry.remix(remix).window_demand)


def transitions(names, remix="octabam"):
    """Per project, `switch` pairs 'slotA:slotB' that put a loaded effect on a slot and take it away, change it for a
    stock reverb, and exchange one loaded effect for another; every pair is inside one project."""
    loc = locate(names)
    DEMAND = sorted(demand(remix))
    by_proj = {}

    def add(a, b):
        if a in loc and b in loc and loc[a][0] == loc[b][0]:
            by_proj.setdefault(loc[a][0], []).append(f"{loc[a][1]}:{loc[b][1]}")
            by_proj[loc[a][0]].append(f"{loc[b][1]}:{loc[a][1]}")

    for d in DEMAND:
        for rev in REVERBS:
            add(f"{d} FX2 def", f"{rev} FX2 def")
            add(f"{d} FX1 def", f"{rev} FX2 def")
        for e in DEMAND:
            if d < e:
                add(f"{d} FX2 def", f"{e} FX2 def")
                add(f"{d} FX1 def", f"{e} FX2 def")
    # a pair to or from BASE is inside every project (slot 0)
    for p in sorted({v[0] for v in loc.values()}):
        for d in DEMAND:
            n = f"{d} FX2 def"
            if n in loc and loc[n][0] == p:
                by_proj.setdefault(p, []).extend([f"0:{loc[n][1]}", f"{loc[n][1]}:0"])
    # the heaviest layouts against BASE and against each other come from a run's report (`switch --report`)
    return {p: sorted(set(v)) for p, v in by_proj.items()}


def build(a):
    import ot_matrix as M
    dest = pathlib.Path(a.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    names = layout_names(a.remix)
    if any((dest / f"SFX_{k:02d}").exists() for k in range(1, 9)):
        sys.exit(f"{dest} already holds SFX projects; pick a new DEST")
    r = subprocess.run([PY, str(HERE / "ot_matrix.py"), "proj", a.src, str(dest / "SFX"), a.remix,
                        "--clean", "--stimuli", STIMULI], capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.exit(r.stderr or "proj failed")
    nproj = len(sorted(dest.glob("SFX_*")))
    for name, args in (("SSCN", ["--banks", "1-2", "--all-scenes", "--trigs", "grid4"]),
                       ("SDJ", ["--banks", "1-2", "--pattern-steps", "2=1,2,4,7,8,11,13"])):
        shutil.copytree(dest / "SFX_01", dest / name)
        r = subprocess.run([PY, str(HERE / "ot_scenes.py"), "stamp", str(dest / name), *args],
                           capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        if r.returncode:
            sys.exit(r.stderr or f"stamp {name} failed")
        if name == "SDJ":
            # ot_djump.py models 16-step patterns; the stimuli projects' patterns are 64 steps (a toggle-off landing is at 64)
            import ot_project as P
            for pat in (0, 1):
                P.set_pattern_scale(dest / name, 1, pat, 16, "1X", guard=False)
    suite = {"remix": a.remix, "src": str(a.src), "projects": {"SFX": nproj},
             "layouts": names, "where": {n: list(v) for n, v in locate(names).items()},
             "transitions": {str(k): v for k, v in transitions(names, a.remix).items()},
             "per_project": PER_PROJECT}
    (dest / "suite.json").write_text(json.dumps(suite, indent=1))
    print(f"{len(names)} layouts, {nproj} SFX project(s), SSCN, SDJ -> {dest}/suite.json")


# ---------------------------------------------------------------------------
# phases: id, title, project, needs, minutes, command (strings may use {py} {hw} {proj} {label} {n} {pairs})
# ---------------------------------------------------------------------------
def phases(suite):
    n = suite["projects"]["SFX"]
    ph = [
        dict(id="pre-meter", title="LOAD METER reads and counts frames", project="SFX_01", needs="image with LOAD METER; project loaded; unit playing not required",
             minutes=1, cmd="{py} {hw}/load_meter.py --for 10"),
        dict(id="pre-transport", title="START / STOP and the host clock over USB", project="SFX_01", needs="",
             minutes=1, cmd="{py} {hw}/usb_transport_probe.py"),
        dict(id="pre-usb", title="USB audio ring counters", project="SFX_01", needs="",
             minutes=1, cmd="{py} {hw}/usb_counters.py"),
        dict(id="dsp-watch", title="DSP frame count through program change + START with a continuous clock and the USB audio capture open",
             project="SFX_01", needs="USB TRACKS PRE (the shipped setting)", minutes=6,
             cmd="{py} {hw}/ot_dspwatch.py --cycles 20 --audio --continuous-clock --programs 0,1 --play 12 --out {out}/{id}.json"),
    ]
    for k in range(1, n + 1):
        ph.append(dict(id=f"fx{k:02d}", title=f"effect layouts, project SFX_{k:02d}", project=f"SFX_{k:02d}", needs="",
                       minutes=11, cmd="{py} {hw}/ot_matrix.py run {proj} {label}-{id}"))
    for k in range(1, n + 1):
        pairs = ",".join(suite["transitions"].get(str(k), []))
        if pairs:
            ph.append(dict(id=f"loader{k:02d}", title=f"demand loader and reverb transitions, SFX_{k:02d}", project=f"SFX_{k:02d}",
                           needs="", minutes=max(2, len(pairs.split(",")) * 20 // 60 + 1),
                           cmd="{py} {hw}/ot_matrix.py switch {proj} {label}-{id} --pairs " + pairs))
    ph += [
        dict(id="kits-identity", title="program-change walk over all Kits (firmware-migrated, identity)", project="SFX_01",
             needs="fresh load so the firmware migrates the stock Parts", minutes=10,
             cmd="{py} {hw}/ot_fuzz.py gen 3101 {seq} --profile pc --minutes 10 --layouts 32 && {py} {hw}/ot_fuzz.py run {seq} {label}-{id}"),
        dict(id="scenes-sweep", title="scene A/B select and crossfader sweeps against all 16 scene locks", project="SSCN",
             needs="run settings in the stamped project (clock + transport receive on)", minutes=11,
             cmd="{py} {hw}/ot_fuzz.py gen 3201 {seq} --profile scenes --minutes 10 --layouts 32 && {py} {hw}/ot_fuzz.py run {seq} {label}-{id} --no-silence-check"),
        dict(id="scenes-latency", title="crossfader step to lock CC latency", project="SSCN", needs="", minutes=4,
             cmd="{py} {hw}/ot_xflag.py --out {out}/{id}.json"),
        dict(id="djump-off", title="program change landing, DIRECT_JUMP_KYOTI toggle OFF (control)", project="SDJ",
             needs="toggle OFF (power-on state)", minutes=2,
             cmd="{py} {hw}/ot_djump.py --trials 7 --out {out}/{label}-{id}ump-off.json"),
        dict(id="djump-on", title="program change landing, toggle ON", project="SDJ",
             needs="PANEL: [PTN] + [YES] to turn the toggle on", minutes=3,
             cmd="{py} {hw}/ot_djump.py --trials 12 --out {out}/{label}-{id}ump-on.json"),
        dict(id="djump-burst", title="program-change bursts with the toggle on", project="SDJ",
             needs="toggle ON", minutes=11,
             cmd="{py} {hw}/ot_fuzz.py gen 3301 {seq} --profile pc --minutes 10 --layouts 8 && {py} {hw}/ot_fuzz.py run {seq} {label}-{id} --no-silence-check"),
        dict(id="mix-soak", title="56-minute mixed sequence across the 50.7-minute frame-count mark", project="SFX_01",
             needs="fresh load; power-cycled unit so the 50.7 minutes count from the run", minutes=60,
             cmd="{py} {hw}/ot_fuzz.py gen 3401 {seq} --profile mix --minutes 56 --layouts 32 && {py} {hw}/ot_fuzz.py run {seq} {label}-{id}"),
    ]
    return ph


def cmd_plan(a):
    d = pathlib.Path(a.dest)
    names = layout_names(a.remix)
    per = PER_PROJECT - 1
    nproj = -(-(len(names) - 1) // per)
    print(f"{a.remix}: {len(names) - 1} layouts + BASE -> SFX_01..{nproj:02d}, SSCN, SDJ")
    suite = {"projects": {"SFX": nproj}, "transitions": {str(k): v for k, v in transitions(names, a.remix).items()}}
    t = 0
    for p in phases(suite):
        t += p["minutes"]
        print(f"  {p['id']:<14} {p['project']:<7} ~{p['minutes']:>2} min  {p['title']}" + (f"  [{p['needs']}]" if p["needs"] else ""))
    print(f"about {t} min of rig time, plus loads")


def cmd_run(a):
    d = pathlib.Path(a.dest).resolve()
    suite = json.loads((d / "suite.json").read_text())
    out = OUT / a.label
    out.mkdir(parents=True, exist_ok=True)
    want = set(a.phase.split(",")) if a.phase else None
    sumf = out / "summary.json"
    prev = json.loads(sumf.read_text()) if sumf.exists() else []
    rows, loaded = [], None
    for p in phases(suite):
        if want and p["id"] not in want:
            continue
        if p["project"] != loaded:
            print(f"\n== load {p['project']} ({d / p['project']})\n"
                  f"   card: cp -R <pristine> PRESETS/{p['project']}; dot_clean -m; sync; diff -r; unmount; load on the unit")
            if not a.yes:
                input("   Enter when it is loaded ")
            loaded = p["project"]
        if p["needs"] and not a.yes:
            print(f"   needs: {p['needs']}")
            input("   Enter when done ")
        cmd = p["cmd"].format(py=PY, hw=HERE, proj=d / p["project"], label=a.label, id=p["id"], out=out, seq=out / f"{p['id']}.json")
        print(f"-- {p['id']}: {p['title']}")
        t0 = time.time()
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=ROOT)
        (out / f"{p['id']}.log").write_text(r.stdout + r.stderr)
        rows.append(dict(id=p["id"], title=p["title"], project=p["project"], rc=r.returncode,
                         seconds=round(time.time() - t0), tail=(r.stdout + r.stderr).strip().splitlines()[-6:]))
        print(f"   {'PASS' if r.returncode == 0 else 'FAIL'} rc={r.returncode} {rows[-1]['seconds']} s -> {out / (p['id'] + '.log')}")
        merged = [r for r in prev if r["id"] not in {x["id"] for x in rows}] + rows
        sumf.write_text(json.dumps(merged, indent=1))
        if r.returncode and not a.keep_going:
            print("   stopped (power-cycle the unit, read FAILURE_MODES.md); --keep-going continues")
            break
    return cmd_report(argparse.Namespace(label=a.label))


def cmd_report(a):
    rows = json.loads((OUT / a.label / "summary.json").read_text())
    print(f"\n{a.label}: {sum(r['rc'] == 0 for r in rows)}/{len(rows)} phases passed")
    for r in rows:
        print(f"  {'PASS' if r['rc'] == 0 else 'FAIL'}  {r['id']:<14} {r['project']:<7} {r['seconds']:>5} s  {r['title']}")
    return 1 if any(r["rc"] for r in rows) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="c", required=True)
    for nm in ("plan", "build"):
        p = sub.add_parser(nm)
        p.add_argument("dest", nargs="?", default=str(ROOT / "out/suite"))
        p.add_argument("--src", default=str(pathlib.Path.home() / "octa/projects/EMPTY"))
        p.add_argument("--remix", default="octabam")
    p = sub.add_parser("run"); p.add_argument("label"); p.add_argument("--dest", default=str(ROOT / "out/suite"))
    p.add_argument("--phase"); p.add_argument("--yes", action="store_true"); p.add_argument("--keep-going", action="store_true")
    p = sub.add_parser("report"); p.add_argument("label")
    a = ap.parse_args()
    sys.exit({"plan": cmd_plan, "build": build, "run": cmd_run, "report": cmd_report}[a.c](a) or 0)


if __name__ == "__main__":
    main()
