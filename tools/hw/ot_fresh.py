#!/usr/bin/env python3
"""A fresh, empty Octatrack project made by the firmware itself under the ColdFire port, with no file from a unit.

    python3 tools/hw/ot_fresh.py [--remix octabam] [--image out/mainos_bus.bin] [--built] [--out out/fresh]

The port boots the image on a card with no project, a panel script does what a person does (PROJECT > CHANGE >
CREATE EMPTY PROJECT, then SAVE PROJECT: the keys verify_kits.py's `newsave` scenario uses), and the card the firmware
leaves is read back; the project's files are written to OUT/REMIX/NAME (the firmware saves it under the
name that was loaded, NOPROJ). They are derived from the user's own
OS, so they stay under out/ (ignored by git) and are never committed or uploaded. `ot_matrix.py audit` finds nothing
in them, which is what `ot_matrix.py proj --clean` asks of a template: a runner without a unit (CI) can make
its own template this way, and so can anyone who has not made one on a unit.

The project is a function of the image, the port's sources and the panel script, so it is kept under
<git common dir>/octabam-fresh-cache/<sha256 of those>/ and a second run for the same inputs copies it
(CI keeps the directory in the actions cache; OCTABAM_GATE_CACHE=0 makes every run boot the port).
The cache key is also written to OUT/REMIX/fresh.key, next to the project, on a miss and on a hit: gate_cache.project_stamp
keys the project by it, so a project copied from the cache (new file times) keeps the same stamp and the gates' passes are reused.

The firmware makes the project with MIDI program change, clock and transport receive off; STAMP switches them on in
project.work and project.strd before the files are written or cached (verify_brain's `log` case sends a program
change). Nothing else in the project is changed.

What it cannot give: a project the unit made on a particular image. Which files it holds follows the image (with
KITS, a kits.work; with PLOCKS P2, p2lk files). Run it on the remix the test is for.
"""
import argparse
import pathlib
import subprocess
import sys

LOAD_MS = 90000
# The script waits for the card, not for a time (ot_emu's `card` line): the create and the save are over when the
# firmware has left the card alone for QUIET_MS. Measured on octabam, 16 Nov 2026 (emulated ms, so the same on any
# host): the create's last write 558 ms after the key, the save's 14651 ms after, and never more than 49 ms between
# two writes. Until then the script waited 13 s and 30 s: 54 s emulated, 96 s of the 97 s the boot took here.
QUIET_MS = 2000
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/verify"))
sys.path.insert(0, str(ROOT / "tools/emu"))

def panel_script():
    import toolpath  # noqa: F401
    import verify_kits as V
    s = V.Script()
    s.tap("no"); s.tap(0x1c, 1000); s.tap("yes", 1000); s.tap("yes", 1000); s.tap("up", 600)      # PROJECT > CHANGE > CREATE EMPTY PROJECT
    s.tap("yes", 1400); s.tap("yes", 20); s.card(QUIET_MS, 30000)                                # the name, confirmed
    s.tap(0x1c, 1000); s.tap("right", 700); s.tap("down", 500); s.tap("yes", 1100); s.tap("yes", 20); s.card(QUIET_MS, 60000)   # SAVE PROJECT
    return s.text()


# A project the firmware makes has MIDI program change, clock and transport receive off; a project made on a unit
# for these gates has them on. verify_brain's `log` case sends a program change and expects the pattern queued.
STAMP = {"MIDI_PROGRAM_CHANGE_RECEIVE": 1, "MIDI_PROGRAM_CHANGE_RECEIVE_CH": 0,
         "MIDI_CLOCK_RECEIVE": 1, "MIDI_TRANSPORT_RECEIVE": 1}


def stamp_settings(data, values=STAMP):
    """project.work or project.strd with each KEY=value of `values` rewritten. A value keeps its width (zero-padded:
    -1 becomes 00), so the file keeps its length. A key the file lacks is an error."""
    import re
    for key, v in values.items():
        m = re.search(rb"(?m)^" + re.escape(key.encode()) + rb"=([^\r\n]*)", data)
        if not m:
            raise ValueError(f"{key} is not in the project file")
        old = m.group(1)
        new = str(v).rjust(len(old), "0").encode()
        if len(new) != len(old):
            raise ValueError(f"{key}={v} does not fit the width of {old!r}")
        data = data[:m.start(1)] + new + data[m.end(1):]
    return data


def stamp_project(files):
    """The project's files with its settings stamped (.work always; .strd when it carries the keys)."""
    out = dict(files)
    out["project.work"] = stamp_settings(files["project.work"])
    if "project.strd" in files:
        out["project.strd"] = stamp_settings(files["project.strd"])
    return out


def cache_dir(image, load_ms):
    """Where the project for this image, port and script is kept."""
    import hashlib
    import gate_cache
    import reach
    h = hashlib.sha256()
    for part in (pathlib.Path(image).read_bytes(), reach.port_digest(ROOT / "tools/emu/ot_emu").encode(),
                 panel_script().encode(), str(load_ms).encode(), repr(sorted(STAMP.items())).encode()):
        h.update(hashlib.sha256(part).digest())
    return gate_cache.store_dir(ROOT).parent / "octabam-fresh-cache" / h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--remix", default=None, help="build this remix first (make bus); else use --image as it is")
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--built", action="store_true",
                    help="--image is --remix's build already: build nothing (reach.py's plan, which builds each remix once)")
    ap.add_argument("--out", default=str(ROOT / "out/fresh"))
    a = ap.parse_args()
    if a.built and not a.remix:
        ap.error("--built names the remix --image was built from: give --remix")
    if a.remix and not a.built:
        r = subprocess.run(["make", "bus", f"REMIX={a.remix}"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"make bus REMIX={a.remix} failed:\n{r.stdout[-600:]}{r.stderr[-600:]}")
    work = pathlib.Path(a.out) / (a.remix or "image")
    work.mkdir(parents=True, exist_ok=True)
    import gate_cache
    kept = cache_dir(a.image, LOAD_MS) if gate_cache.enabled() else None
    if kept and (kept / "_done").exists():
        import shutil
        for d in sorted(kept.iterdir()):
            if d.is_dir():
                shutil.copytree(d, work / d.name, dirs_exist_ok=True)
                print(f"{work / d.name}: from the cache ({kept.name[:12]})")
        (work / "fresh.key").write_text(kept.name)      # gate_cache.project_stamp keys the project by this, not by file times
        return 0
    empty = work / "_empty_src"
    empty.mkdir(exist_ok=True)
    card = work / "card.img"
    py = ROOT / ".venv/bin/python3"
    r = subprocess.run([str(py), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(empty), "OCTABAM", "NOPROJ",
                        "--tree", str(work / "_tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"stage_card failed:\n{r.stdout[-600:]}{r.stderr[-600:]}")
    script = work / "fresh.script"
    script.write_text(panel_script())
    after = work / "card_after.img"
    cmd = [str(ROOT / "out/emu/ot_emu"), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "NOPROJ",
           "--load-ms", str(LOAD_MS), "--mkii", "--live-script", str(script), "--card-out", str(after)]
    print("booting a blank project under the port and creating one with the panel script ...", flush=True)
    with open(work / "port.txt", "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    if rc or not after.exists():
        sys.exit(f"ot_emu exit {rc}; see {work / 'port.txt'}")
    log = (work / "port.txt").read_text(errors="replace")
    if "WAIT TIMEOUT" in log or "ended on quit" not in log:
        # a card wait that reached its cap, or a script that stopped early: the card may hold half a project
        sys.exit(f"the panel script did not run to its end (a create or a save the card wait did not see finish); "
                 f"see {work / 'port.txt'}")
    import emu_card
    files = emu_card.extract_image(after.read_bytes())
    projects = {}
    for path, data in files.items():
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "OCTABAM" and parts[1] != "AUDIO":
            projects.setdefault(parts[1], {})[parts[2]] = data
    projects = {n: fs for n, fs in projects.items() if "project.work" in fs and "bank01.work" in fs}
    if not projects:
        sys.exit(f"no project with a project.work and bank files on the card the firmware left; see {work / 'port.txt'}; files: {sorted(files)[:20]}")
    projects = {n: stamp_project(fs) for n, fs in projects.items()}
    for name, fs in projects.items():
        dest = work / name
        dest.mkdir(exist_ok=True)
        for fn, data in fs.items():
            (dest / fn).write_bytes(data)
        print(f"{dest}: {len(fs)} files, {sum(map(len, fs.values()))} bytes")
        if kept:
            (kept / name).mkdir(parents=True, exist_ok=True)
            for fn, data in fs.items():
                (kept / name / fn).write_bytes(data)
    if kept:
        (kept / "_done").write_text("")
        (work / "fresh.key").write_text(kept.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
