#!/usr/bin/env python3
"""RETURNS under the port: the reverb return leaves T5 and lands where
MASTER TRACK says, at the level VRB says (docs/proposals/RETURNS.md).

    python3 tools/verify/verify_returns.py REMIX --project DIR

Stages five cards from the project (hosted for the remix: T1 BusDelay, T5
BusVerb, T8 RETURNS; every SEND's REV at 100; T8's FX2 slot 0 unlocked and
off the LFOs), runs each under `ot_emu` for FRAMES frames with a block dump
and a peek of y:$e00..$e24, and checks:

  flags    RETURNS on T8: ALIVE, the latched mode and FRESH carry the magic,
           VRB is published as the knob (108 -> $6c0000, 0 -> 0) and the
           glided gain has reached (VRB/128)^2; the buffer carries the wet.
           T8 = the stock DELAY (the control): all five words stay zero.
  routing  per track read-back and MAIN, frame by frame after the warm-up:
           MASTER TRACK off, VRB 108 vs 0: every track equal, MAIN differs;
           MASTER TRACK on, VRB 108 vs 0: T1-T7 equal, T8 and MAIN differ
           (the return enters T8's input and leaves through T8's chain);
           RETURNS vs the control: T5 differs (its print is gone) and every
           other track is equal.

What it cannot see: the level on a unit, the sound, the cross-core timing
(core 0 only here, lock-step), and whether T8's FX1 filter treats the
return as it treats the tracks (it reads the same record; not rendered).

SKIPs without a project or the port, and for a remix without RETURNS.
"""
import argparse, os, pathlib, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
import ot_project as otp  # noqa: E402
import blockdump as bd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/returnsverify"
FRAMES, WARM = 700, 300               # BusVerb prints dry for ~256 blocks after load
MAGIC = 0x5a5a5a
FIXTURES = (("on108", "RETURNS", 108, True), ("on0", "RETURNS", 0, True),
            ("off108", "RETURNS", 108, False), ("off0", "RETURNS", 0, False),
            ("ctl", "DELAY", None, False))
READBACK = ((1, (0x80003190, 0x80003590), ("T1", "T2", "T3", "T4")),
            (0, (0x80003390, 0x80003790), ("T5", "T6", "T7", "T8")))
MAIN = ('<', 6, 0, 0x80005e60)


def stage(template, remix, tag, t8, vrb, master, audio):
    d = OUT / tag
    shutil.rmtree(d, ignore_errors=True)
    (d / "project").mkdir(parents=True)
    for f in template.iterdir():
        if f.is_file() and f.suffix.lower() in (".work", ".strd"):
            shutil.copy2(f, d / "project" / f.name)
    p = d / "project"
    otp.host_rig(p, remix, guard=False)
    if t8 == "RETURNS":
        otp.stamp_slot(p, "RETURNS", "VRB", vrb, guard=False)
    else:
        otp.set_fx(p, "fx2", 8, t8, guard=False)
    otp.stamp_slot(p, "SEND", "REV", 100, guard=False)

    def free_t8(data):
        # a lock on T8's FX2 slot 0 (lock slot 24) or an LFO on it would move VRB
        for pat in range(16):
            base = otp.trac_off(pat, 7) + 0x59
            for st in range(64):
                data[base + st * 32 + 24] = 0xff
        for part in range(otp.NPARTS_ALL):
            lfo = otp.PART_BASE + part * otp.PART_STRIDE + otp.LFO_PM_OFF + 7 * 30
            for k in range(3):
                if data[lfo + k] == 24:
                    data[lfo + k] = 18
    for bw in sorted(p.glob("bank*.work")):
        otp._bank_write(p, int(bw.name[4:6]), free_t8, guard=False)
    otp.set_master_track(p, master)
    raw = (p / "project.work").read_bytes()
    (p / "project.work").write_bytes(re.sub(rb"\r\nPATTERN=\d+\r\n", b"\r\nPATTERN=0\r\n", raw))
    cmd = [str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(p), "OCTABAM", "RET",
           "--tree", str(d / "tree"), "--out", str(d / "card.img"), "--image-mb", "64"]
    for a in audio:
        cmd += ["--audio", a]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_returns: stage_card {tag} failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")


def run(image, tag):
    d = OUT / tag
    cmd = [str(EMU), "--image", str(image), "--card", str(d / "card.img"), "--set", "OCTABAM",
           "--project", "RET", "--sequencer", "--internal-clock", "--frames", str(FRAMES),
           "--load-ms", "90000", "--dsp", "--main-level", "64",
           "--block-dump", str(d / "blocks.dump"), "--dsp-peek", "0:Y:e00,37"]
    with open(d / "run.txt", "w") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    return tag, r.returncode


def words(tag):
    for line in open(OUT / tag / "run.txt"):
        if "core 0 Y:0x00e00:" in line:
            return [int(x, 16) for x in line.split("Y:0x00e00:")[1].split()]
    return None


def series(c, key):
    return {f: w for f, w in c.get(key, [])}


def diffs(a, b):
    """{track or MAIN: (frames differing, frames compared)} after the warm-up."""
    A = bd.classes(bd.read(OUT / a / "blocks.dump"))
    B = bd.classes(bd.read(OUT / b / "blocks.dump"))
    out = {}
    for core, rams, tracks in READBACK:
        for ti, t in enumerate(tracks):
            n = d = 0
            for ram in rams:
                sa, sb = series(A, ('<', 1, core, ram)), series(B, ('<', 1, core, ram))
                for f in sa:
                    if f in sb and f > WARM:
                        n += 1
                        d += sa[f][64 * ti:64 * ti + 64] != sb[f][64 * ti:64 * ti + 64]
            out[t] = (d, n)
    sa, sb = series(A, MAIN), series(B, MAIN)
    out["MAIN"] = (sum(1 for f in sa if f in sb and f > WARM and sa[f] != sb[f]),
                   sum(1 for f in sa if f in sb and f > WARM))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--image", default="")
    a = ap.parse_args()
    remix = registry.remix(a.remix)
    if "RETURNS" not in remix.modules:
        print(f"  [ -- ] verify_returns: {a.remix} carries no RETURNS"); return 0
    if not a.project:
        print("  [SKIP] verify_returns: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_returns: no port binary (make emu-cf)"); return 0
    template = pathlib.Path(a.project).expanduser()
    if not (template / "project.work").is_file():
        sys.exit(f"verify_returns: {template} is not a project")
    OUT.mkdir(parents=True, exist_ok=True)
    image = pathlib.Path(a.image) if a.image else OUT / "mainos.bin"
    if not a.image:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_returns: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    # the template's samples, at the card paths its project names
    audio = []
    for s in otp.read_project(template)[1]:
        rel = s["path"]
        src = (template / rel).resolve() if rel else None
        if src is not None and src.is_file():
            card = rel[3:] if rel.startswith("../") else f"RET/{rel}"
            audio.append(f"{src}:{card}")
    for tag, t8, vrb, master in FIXTURES:
        stage(template, a.remix, tag, t8, vrb, master, sorted(set(audio)))
    with ThreadPoolExecutor(len(FIXTURES)) as ex:
        codes = dict(ex.map(lambda f: run(image, f[0]), FIXTURES))

    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    for tag, code in codes.items():
        check(f"{tag}: {FRAMES} frames ran (exit {code})", code == 0)
    if fails:
        print(f"verify_returns: FAIL ({fails})"); return 1
    for tag, t8, vrb, master in FIXTURES:
        w = words(tag)
        if w is None:
            check(f"{tag}: y:$e00.. peeked", False); continue
        buf, alive, knob, fresh, gain, mode = w[:32], w[32], w[33], w[34], w[35], w[36]
        if t8 == "RETURNS":
            check(f"{tag}: ALIVE / mode / FRESH carry the magic "
                  f"({alive:06x} {mode:06x} {fresh:06x})", alive == mode == fresh == MAGIC)
            check(f"{tag}: VRB published as the knob ({knob:06x}, want {vrb << 16:06x})",
                  knob == vrb << 16)
            want = int((vrb / 128) ** 2 * (1 << 23))
            check(f"{tag}: the gain glided to (VRB/128)^2 ({gain:06x}, want ~{want:06x})",
                  abs(gain - want) <= max(8, want // 100))
            check(f"{tag}: the buffer carries the wet", any(buf))
        else:
            check(f"{tag}: no RETURNS, all five words zero ({alive:06x} {knob:06x} "
                  f"{fresh:06x} {gain:06x} {mode:06x})", not any((alive, knob, fresh, gain, mode)))

    def route(a_, b_, label, differ):
        d = diffs(a_, b_)
        n = d["MAIN"][1]
        for t, (k, m) in d.items():
            want = t in differ
            ok = m > 100 and ((k == m) if want else (k == 0))
            check(f"{label}: {t} {'differs' if want else 'equal'} ({k}/{m} frames differ)", ok)
        return n

    route("off108", "off0", "MASTER TRACK off, VRB 108 vs 0", {"MAIN"})
    route("on108", "on0", "MASTER TRACK on, VRB 108 vs 0", {"T8", "MAIN"})
    route("off0", "ctl", "RETURNS vs T5's print", {"T5", "MAIN"})
    print(f"verify_returns: {'ok' if not fails else 'FAIL'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
