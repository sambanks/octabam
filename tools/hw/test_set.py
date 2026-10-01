#!/usr/bin/env python3
"""A test set for a rig remix: a COPY of a project where every track plays a
STATIC sample, every send starts at 0, and the rig's hosts (and RETURNS on
T8, when the remix carries it) are in place.

    python3 tools/hw/test_set.py SRC DEST --remix bottleservice-pf \\
        --static "3=../AUDIO/Breaks/Funky Worm.wav" --static "4=..." [--tracks 7] [--master-track on]

SRC is left alone; DEST must not exist. Every path is the card's, relative to
the project folder as the project's own [SAMPLE] entries are. RIGTEST (30 Sep
2026, from the owner's MODLIIVE RET) was built this way:

  - the project's STATIC list gains each --static SLOT=PATH (LOOPMODE on,
    TSMODE off, GAIN 48); slots the project already fills are kept
  - bank A part 1 (and its saved copy, part 5): tracks 1..--tracks are
    STATIC machines on slots 1..N, each with a trig on step 1 of A01
  - `ot_project.host`: T1 BusDelay, T5 BusVerb, T8 RETURNS (if the remix
    carries it), the rest SEND, the modules' defaults stamped; then every
    DEL and REV to 0 on the hosts and SEND
  - MASTER TRACK as asked, and every .strd equal to its .work (a unit-saved
    project carries both identical; RELOAD needs them)

`ot_project`'s own write guard wants a backup directory on its author's
machine; this writes only into the fresh copy, so it calls the functions
with guard=False. Octatrack project files never enter the repo.
"""
import argparse
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import ot_project as ot  # noqa: E402


def add_static(pdir, samples):
    pw = pdir / "project.work"
    t = pw.read_bytes().decode("latin1")
    nl = "\r\n" if "\r\n" in t else "\n"
    last = t.rindex("[/SAMPLE]") + len("[/SAMPLE]")
    blocks = "".join(
        f"{nl}{nl}[SAMPLE]{nl}TYPE=STATIC{nl}SLOT={s:03d}{nl}PATH={p}{nl}TRIM_BARSx100=0{nl}"
        f"TSMODE=0{nl}LOOPMODE=1{nl}GAIN=48{nl}TRIGQUANTIZATION=-1{nl}[/SAMPLE]" for s, p in samples)
    pw.write_bytes((t[:last] + blocks + t[last:]).encode("latin1"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src", type=pathlib.Path)
    ap.add_argument("dest", type=pathlib.Path)
    ap.add_argument("--remix", required=True)
    ap.add_argument("--static", action="append", default=[], metavar="SLOT=PATH")
    ap.add_argument("--tracks", type=int, default=7, help="tracks 1..N play STATIC slots 1..N (default 7)")
    ap.add_argument("--master-track", choices=("on", "off"), default="on")
    a = ap.parse_args()
    if not (a.src / "project.work").is_file():
        sys.exit(f"{a.src} is not an Octatrack project directory")
    if a.dest.exists():
        sys.exit(f"{a.dest} exists -- refusing to overwrite")
    if not 1 <= a.tracks <= 8:
        sys.exit("--tracks is 1..8")
    samples = []
    for spec in a.static:
        slot, _, path = spec.partition("=")
        if not slot.isdigit() or not path:
            sys.exit(f"--static wants SLOT=PATH, not {spec!r}")
        samples.append((int(slot), path))

    shutil.copytree(a.src, a.dest, ignore=shutil.ignore_patterns("._*"))
    if samples:
        add_static(a.dest, samples)
    for tr in range(1, a.tracks + 1):
        ot.set_machine_type(a.dest, 1, 1, tr, 0, guard=False)              # STATIC, part 1 and its saved copy
        for part in (1, 5):
            def mut(data, part=part, tr=tr):
                off = ot.PART_BASE + (part - 1) * ot.PART_STRIDE + 0x2d3 + (tr - 1) * 5 + ot.SLOT_KIND["static"]
                data[off] = tr - 1
            ot._bank_write(a.dest, 1, mut, guard=False)
        ot.set_pattern_trig(a.dest, 1, 0, tr - 1, 1, guard=False)
    ot.host_rig(a.dest, a.remix, guard=False)
    for m in ("DELAY SERVER", "REVERB SERVER", "SEND"):
        for knob in ("DEL", "REV"):
            ot.stamp_slot(a.dest, m, knob, "0")
    ot.set_master_track(a.dest, a.master_track == "on")
    for w in a.dest.glob("*.work"):
        shutil.copy2(w, w.with_suffix(".strd"))
    print(f"{a.dest}: test set for {a.remix} -- T1..T{a.tracks} STATIC, sends at 0, "
          f"MASTER TRACK {a.master_track}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
