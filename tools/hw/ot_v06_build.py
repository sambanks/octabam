#!/usr/bin/env python3
"""The projects of the v0.6 unit checks (tools/hw/ot_v06.py): ot_matrix projects with machine slots.

    python3 tools/hw/ot_v06_build.py build DEST [--src ~/octa/projects/EMPTY]

Writes DEST/<project>/ for each image below and DEST/v06.json (which project goes with which image and which
layouts must be judged how). Every project is an `ot_matrix.py proj --clean --stimuli ...` project: BASE in slot 0,
then the layouts of the table, then machine slots. Program change n selects bank n // 16, pattern n % 16 + 1;
slot i is bank i // 4 + 1, pattern i % 4 + 1 (ot_matrix._program).

| project   | image          | slots                                                                     | issue        |
|-----------|----------------|---------------------------------------------------------------------------|--------------|
| V06_OCT   | octabam        | OCTA303 on T1+T2; WAVE on T1+T2 (trigs on 1, 5, 9, 13)                    | #1270, #1232 |
| V06_RIG   | v06-rig        | CX OSC on T1; VCA160's layouts (FX1 def, dear)                            | #1263, #1219 |
| V06_VRB   | octabam-verbs  | VERBERATION's layouts (FX2 def, dear, each mode)                          | #1234        |

A machine slot is a FLEX track whose Part carries the machine's signature, `Part' + 0x3c + 30 * track`
(tools/verify/verify_octa303_ui.py and verify_wavecf_ui.py poke the same bytes into RAM). The file offset used here
is PART_BASE + 9 + 0x3c + 30 * track in the Part record and its saved copy (the file record has a 9-byte header the
RAM structure lacks, ot_project.trac_off). That mapping is inferred; a project whose signature missed leaves the
track a FLEX track with no sample, and the slot reads as silent. The machine's PLAYBACK and SETUP values are the
module's own seeds: nothing here writes them.
"""
import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import ot_matrix as M  # noqa: E402
import ot_project as P  # noqa: E402

PY = sys.executable
STIMULI = "hits,pink,two_tones,sweep,ladder,impulses"
SIG_OFF = 0x3C
THRU = 2                                  # machine type byte: STATIC 0, FLEX 1, THRU 2 (inferred)
SIGS = {"OCTA303": (0x54, 0x42, 1), "WAVE": (0x57, 0x56, 1), "CX OSC": (0x43, 0x58, 1)}
STEPS = (1, 5, 9, 13)


def machine_slot(pdir, plan, slot, name, sig, tracks, steps=STEPS):
    """Rewrite slot `slot` of the project as `name`: tracks (0-based) become FLEX tracks signed `sig`, and the
    slot's pattern holds a trig on `steps` of those tracks and nothing else. Updates the plan entry."""
    bank, pat, prog = M._program(slot)
    part = pat

    def mut(data):
        for p in (part, part + P.MTYPE_MIRROR):
            off = P.PART_BASE + (p - 1) * P.PART_STRIDE
            for t in range(8):
                if t not in tracks:
                    data[off + P.MTYPE_OFF + t] = THRU      # a looping stimulus voice would play on across the change
            for t in tracks:
                data[off + P.MTYPE_OFF + t] = 1
                at = off + 9 + SIG_OFF + 30 * t
                data[at:at + 3] = bytes(sig)
        for t in range(8):
            o = P.trac_off(pat - 1, t)
            data[o:o + 64] = bytes(64)
        for t in tracks:
            for s in steps:
                data[P.trac_off(pat - 1, t) + 7 - (s - 1) // 8] |= 1 << ((s - 1) % 8)

    P._bank_write(pdir, bank, mut, guard=False)
    e = plan["layouts"][slot]
    e.update(name=name, kind="machine", layout={str(t + 1): ["-", "-"] for t in range(8)},
             machine={"signature": list(sig), "tracks": [t + 1 for t in tracks], "steps": list(steps)})


def project(dest, src, remix, select_names, machines):
    """ot_matrix proj for `remix` with BASE and the named layouts, then the machine slots after them."""
    d = pathlib.Path(dest)
    sel = d.parent / (d.name + ".select.json")
    names = select_names or [M.layouts(remix)[1][0]]       # ot_matrix proj needs one layout besides BASE
    sel.write_text(json.dumps({"run": names}))
    cmd = [PY, str(HERE / "ot_matrix.py"), "proj", str(src), str(d), remix, "--clean", "--stimuli", STIMULI,
           "--select", str(sel)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.exit(r.stderr or f"proj {remix} failed")
    made = sorted(d.parent.glob(d.name + "_*"))
    if len(made) != 1:
        sys.exit(f"{d}: expected one project, got {[m.name for m in made]}")
    pdir = made[0]
    plan_path = pdir / "OCTABAM_MATRIX.json"
    plan = json.loads(plan_path.read_text())
    first = len(plan["layouts"])
    for i, (name, sig, tracks) in enumerate(machines):
        slot = first + i
        if slot >= M.PER_PROJECT:
            sys.exit("more than 32 slots")
        if slot >= len(plan["layouts"]):
            b, p, prog = M._program(slot)
            plan["layouts"].append({"slot": slot, "bank": M.BANKS[b - 1], "pattern": p, "program": prog,
                                    "name": name, "kind": "machine", "layout": {}})
        machine_slot(pdir, plan, slot, name, sig, tracks)
    P.write_stored(pdir)
    plan_path.write_text(json.dumps(plan, indent=1))
    return pdir, plan


def layout_names(remix, words):
    return [n for n, _k, _l in M.layouts(remix)[1:] if any(w in n for w in words)]


def build(a):
    dest = pathlib.Path(a.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    out = {}
    jobs = (
        ("V06_OCT", "octabam", [], [("OCTA303 T1+T2", SIGS["OCTA303"], (0, 1)), ("WAVE T1+T2", SIGS["WAVE"], (0, 1))]),
        ("V06_RIG", "v06-rig", layout_names("v06-rig", ("VCA160",)), [("CX OSC T1", SIGS["CX OSC"], (0,))]),
        ("V06_VRB", "octabam-verbs", layout_names("octabam-verbs", ("VERBERATION",)), []),
    )
    for name, remix, names, machines in jobs:
        pdir, plan = project(dest / name, a.src, remix, names, machines)
        out[name] = {"remix": remix, "dir": str(pdir), "slots": [e["name"] for e in plan["layouts"]]}
        print(f"{name}: {remix}: {out[name]['slots']}")
    (dest / "v06.json").write_text(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="c", required=True)
    p = sub.add_parser("build")
    p.add_argument("dest")
    p.add_argument("--src", default=str(pathlib.Path.home() / "octa/projects/EMPTY"))
    a = ap.parse_args()
    build(a)


if __name__ == "__main__":
    main()
