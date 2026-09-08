"""Build Bryan's seam fixtures from the RECTRIG backup, on disk, with the
ot_project toolkit (RTOS_FORK 10.16.5 / 10.18), in the SEAMTEST geometry the
tag-19/21 flashes carried (FLASHPLAN): a 16-step 1X A01 in bank 1, part 1,
T1 = recorder trigs (REC1 = INAB, mask 0x20) at steps 2/6/10/14, T2 = FLEX
on R1 with play trigs at the same steps.  `--self` puts the play trigs on
T1 (FLEX on R1 too): record what you play, the sound-on-sound shape.

    .venv/bin/python tools/scratch/make_seam_fixtures.py out/_fx [--self] [--ab N]

Produces <dir>/r4_128 (RLEN 4, 128 BPM: Bryan's test 1), <dir>/max_128
(RLEN MAX, 128: his test 3, with the play trigs), <dir>/r4_120 (control).
"""
import argparse, pathlib, shutil, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ot_project as o

SRC = pathlib.Path.home() / "octa/backups/RECTRIG_20260906_step9"
FIX = {"r4_128": (3, "128.0"), "max_128": (64, "128.0"), "r4_120": (3, "120.0")}

def build(root, self_play=False, ab=None):
    root = pathlib.Path(root); root.mkdir(parents=True, exist_ok=True)
    play_track = 0 if self_play else 1
    for name, (rlen, bpm) in FIX.items():
        d = root / name
        if d.exists(): shutil.rmtree(d)
        shutil.copytree(SRC, d, ignore=shutil.ignore_patterns("._*"))
        # the backup (RECTRIG_20260906_step9) carries T1 trigs of its own in
        # A01 -- a REC trig at step 9 on all three masks and a play trig at
        # step 1; measured 8 Sep 2026 when a ten-pass run showed arms every
        # 3 and 1 steps. Clear T1's four masks in A01 first.
        def clear_t1(data):
            for mask in (0x00, 0x20, 0x28, 0x30):
                base = o.trac_off(0, 0) + mask
                for k in range(8): data[base + k] = 0
        o._bank_write(d, 1, clear_t1, guard=False)
        for t in sorted({0, play_track}):
            o.set_machine_type(d, 1, 1, t + 1, 1, guard=False)      # FLEX
            o.set_track_slot(d, 1, 1, t + 1, 129, "flex")           # on R1
        for step in (2, 6, 10, 14):
            o.set_pattern_trig(d, 1, 0, play_track, step, 0x00, guard=False)   # play trig
            o.set_pattern_trig(d, 1, 0, 0, step, 0x20, guard=False)            # REC1 (INAB) on T1
        o.set_pattern_scale(d, 1, 0, 16, "1X", guard=False)
        o.set_recorder_setup(d, 1, 1, 0, "RLEN", rlen, guard=False)
        if ab is not None:
            o.set_recorder_setup(d, 1, 1, 0, "AB", ab, guard=False)
        o.set_tempo(d, bpm)
        print(f"== {d}  (play trigs on T{play_track+1}, AB {ab})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="out/_fx")
    ap.add_argument("--self", action="store_true", dest="self_play")
    ap.add_argument("--ab", type=int, default=None)
    a = ap.parse_args()
    build(a.root, a.self_play, a.ab)
