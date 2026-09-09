"""Build isolated FLEX-playback fixtures: T1 records (armed, RLEN 16, single
REC1 trig at step 1), T2 plays R1 back and is NEVER armed -- so T2's own
rendered output cannot contain a live input-monitor passthrough by
construction (RTOS_FORK 10.38's own retraction: every self-loop fixture used
since 10.16 has the record and play roles on the SAME armed track, which is
exactly where a monitor and real buffer playback are indistinguishable).

Same geometry as g65/n128 (RLEN 16, single REC1+play trig at step 1, 1X 16
steps) but split across two tracks, at both the golden and non-golden tempo.

    .venv/bin/python tools/scratch/make_isolated_flex_fixtures.py out/_iso
"""
import argparse, pathlib, shutil, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ot_project as o

SRC = pathlib.Path.home() / "octa/backups/RECTRIG_20260906_step9"
FIX = {"g65_iso": "65.6", "n128_iso": "128.0"}

def build(root):
    root = pathlib.Path(root); root.mkdir(parents=True, exist_ok=True)
    for name, bpm in FIX.items():
        d = root / name
        if d.exists(): shutil.rmtree(d)
        shutil.copytree(SRC, d, ignore=shutil.ignore_patterns("._*"))

        def clear_t1_t2(data):
            for track in (0, 1):
                for mask in (0x00, 0x20, 0x28, 0x30):
                    base = o.trac_off(0, track) + mask
                    for k in range(8):
                        data[base + k] = 0
        o._bank_write(d, 1, clear_t1_t2, guard=False)

        o.set_machine_type(d, 1, 1, 1, 1, guard=False)      # T1 FLEX
        o.set_track_slot(d, 1, 1, 1, 129, "flex")           # T1 on R1 (its own recorder buffer)
        o.set_machine_type(d, 1, 1, 2, 1, guard=False)      # T2 FLEX
        o.set_track_slot(d, 1, 1, 2, 129, "flex")           # T2 ALSO on R1 -- plays T1's buffer, never armed

        o.set_pattern_trig(d, 1, 0, 0, 1, 0x20, guard=False)   # T1 step1: REC1 (INAB) -- the only trig T1 gets
        o.set_pattern_trig(d, 1, 0, 1, 1, 0x00, guard=False)   # T2 step1: PLAY -- the only trig T2 gets

        o.set_pattern_scale(d, 1, 0, 16, "1X", guard=False)
        o.set_recorder_setup(d, 1, 1, 0, "RLEN", 15, guard=False)   # RLEN 15 = display 16, matches g65/n128
        o.set_tempo(d, bpm)
        print(f"== {d}  (T1 records+arms, T2 plays R1, never armed, {bpm} BPM)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="out/_iso")
    a = ap.parse_args()
    build(a.root)
