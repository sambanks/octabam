#!/usr/bin/env python3
"""VERB PARTS on a unit: the card project `verify_verb_parts` builds under the port, for `octabam-verbs`.

    .venv/bin/python3 tools/hw/ot_verbparts.py FRESH DEST

FRESH is a fresh project (`ot_matrix.py audit` finds nothing); DEST is written beside it and must not exist. Every Part
of every bank gets, on FX2 (the values are verify_verb_parts', so the port and the unit see one fixture):

    T2  0x16  DARK REV's id (VERB HALL here), DARK's own values, page-2 slots 9 and 10 at 0   -> opens at HALL's defaults
    T4  0x15  SPRING REV's id (VERB ROOM), a stock-looking page, slots 9 and 10 at 0           -> opens at ROOM's defaults
    T3  0x14  PLATE REV's id (VERB PLATE), slot 9 at 4: a Part saved with the row              -> opens as written
    T5  0x1a  VERBERATION, slots 9 and 10 at 0, not a row's id                                  -> opens as written

On the unit (docs/contributing/HARDWARE_PLAN.md, "VERB PARTS"): load DEST, open T2's and T4's FX2 pages and read the
knobs against `--expect`; then, playing, cue B01 (bank B's Part 1, applied at the pattern change) and read them again
-- that is the pattern-change path (0x40009e10) the port has not run.

    .venv/bin/python3 tools/hw/ot_verbparts.py --expect       # the knob values each track should show
"""
import argparse, pathlib, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools/hw"), str(ROOT / "tools/verify")]
import verify_verb_parts as V  # noqa: E402


def expect():
    from remix import registry
    mods = registry.modules()
    rows = {k: [p.default or 0 for p in mods[k].params] for k in ("VERB PLATE", "VERB ROOM", "VERB HALL")}
    print("FX2 page 1 (6 knobs) / page 2 (6 knobs) after the load, every Part as it is applied:")
    print(f"  T2  VERB HALL   {rows['VERB HALL'][:6]} / {rows['VERB HALL'][6:]}   (was DARK REV {V.DARK_P1} / {V.DARK_P2})")
    print(f"  T4  VERB ROOM   {rows['VERB ROOM'][:6]} / {rows['VERB ROOM'][6:]}   (was {V.SPRING_P1} / {V.SPRING_P2})")
    print(f"  T3  VERB PLATE  {V.PLATE_ROW_P1} / {V.PLATE_ROW_P2}   (as written)")
    print(f"  T5  VERBERATION {V.VERB_P1} / {V.VERB_P2}   (as written)")
    print("Page 2's first knob is MODE: HALL is 2, ROOM 0 (stepped: ROOM PLAT HALL GATE).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fresh", nargs="?"); ap.add_argument("dest", nargs="?")
    ap.add_argument("--expect", action="store_true", help="print what each track should show, and stop")
    a = ap.parse_args()
    if a.expect:
        return expect()
    if not (a.fresh and a.dest):
        ap.error("FRESH and DEST, or --expect")
    src, dest = pathlib.Path(a.fresh).expanduser(), pathlib.Path(a.dest).expanduser()
    if dest.exists():
        sys.exit(f"{dest} exists; pick a new DEST")
    shutil.copytree(src, dest)
    import ot_project as otp
    otp.set_fx(dest, "fx2", 2, 0x16, page=V.DARK_P1, page2=V.DARK_P2, guard=False)
    otp.set_fx(dest, "fx2", 4, 0x15, page=V.SPRING_P1, page2=V.SPRING_P2, guard=False)
    otp.set_fx(dest, "fx2", 3, 0x14, page=V.PLATE_ROW_P1, page2=V.PLATE_ROW_P2, guard=False)
    otp.set_fx(dest, "fx2", 5, 0x1A, page=V.VERB_P1, page2=V.VERB_P2, guard=False)
    print(f"wrote {dest}; on the unit compare with --expect")
    expect()


if __name__ == "__main__":
    sys.exit(main() or 0)
