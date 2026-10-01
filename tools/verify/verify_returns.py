#!/usr/bin/env python3
"""RETURNS under the port: the reverb return leaves T5 and the delay return
leaves T1, and both land where MASTER TRACK says, at the levels VRB and DLY
say (docs/proposals/RETURNS.md).

    python3 tools/verify/verify_returns.py REMIX --project DIR

Stages six cards from the project (hosted for the remix: T1 BusDelay, T5
BusVerb, T8 RETURNS; every SEND's DEL and REV at 100; T8's FX2 slots 0-1
unlocked and off the LFOs), runs each under `ot_emu` for FRAMES frames with
a block dump and peeks of y:$e00..$e26 (core 0) and the shared
y:$36300..$36308, and checks:

  flags    RETURNS on T8: ALIVE, the latched mode and FRESH carry the magic,
           VRB and DLY are published as the knobs (108 -> $6c0000, 0 -> 0)
           and each glided gain has reached (knob/128)^2; the reverb buffer
           carries the wet; a delay buffer stamp ($5a0000 | offset) is
           pending. T8 = the stock DELAY (the control): the core-0 words and
           every stamp stay zero.
  routing  per track read-back and MAIN, frame by frame after the warm-up:
           MASTER TRACK on, VRB 108 vs 0 and DLY 108 vs 0: T1-T7 equal, T8
           and MAIN differ (each return enters T8's input and leaves through
           T8's chain); MASTER TRACK off, DLY 108 vs 0: every track equal,
           MAIN differs; RETURNS vs the control: T1 and T5 differ (their
           prints are gone) and every other track is equal.

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
FRAMES, WARM = 1000, 650              # both engines warm up dry after load: BusVerb ~256
                                      # blocks, BusDelay until ~frame 584 (measured)
MAGIC = 0x5a5a5a
# tag, T8's FX2, (VRB, DLY), MASTER TRACK
FIXTURES = (("on", "RETURNS", (108, 108), True), ("onv0", "RETURNS", (0, 108), True),
            ("ond0", "RETURNS", (108, 0), True), ("off", "RETURNS", (108, 108), False),
            ("offd0", "RETURNS", (108, 0), False), ("ctl", "DELAY", None, False))
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
        otp.stamp_slot(p, "RETURNS", "VRB", vrb[0], guard=False)
        otp.stamp_slot(p, "RETURNS", "DLY", vrb[1], guard=False)
    else:
        otp.set_fx(p, "fx2", 8, t8, guard=False)
    otp.stamp_slot(p, "SEND", "REV", 100, guard=False)
    otp.stamp_slot(p, "SEND", "DEL", 100, guard=False)
    # a long tail, so the delay's wet is never silent between echoes and
    # every frame carries a return to compare
    otp.stamp_slot(p, "DELAY SERVER", "FDBK", 110, guard=False)

    def free_t8(data):
        # a lock on T8's FX2 slots 0-1 (lock slots 24, 25) or an LFO on them
        # would move VRB / DLY
        for pat in range(16):
            base = otp.trac_off(pat, 7) + 0x59
            for st in range(64):
                data[base + st * 32 + 24] = 0xff
                data[base + st * 32 + 25] = 0xff
        for part in range(otp.NPARTS_ALL):
            lfo = otp.PART_BASE + part * otp.PART_STRIDE + otp.LFO_PM_OFF + 7 * 30
            for k in range(3):
                if data[lfo + k] in (24, 25):
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
           "--block-dump", str(d / "blocks.dump"), "--dsp-peek", "0:Y:e00,39;0:Y:36300,9"]
    with open(d / "run.txt", "w") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    return tag, r.returncode


def words(tag, addr="Y:0x00e00"):
    for line in open(OUT / tag / "run.txt"):
        if f"core 0 {addr}:" in line:
            return [int(x, 16) for x in line.split(f"{addr}:")[1].split()]
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
    for tag, t8, knobs, master in FIXTURES:
        w, sh = words(tag, "Y:0x00e00"), words(tag, "Y:0x36300")
        if w is None or sh is None:
            check(f"{tag}: y:$e00.. and y:$36300.. peeked", False); continue
        buf, alive, fresh, gain, mode = w[:32], w[32], w[34], w[35], w[36]
        stamps, alive_d = sh[:8], sh[8]
        if t8 == "RETURNS":
            check(f"{tag}: ALIVE / mode / FRESH carry the magic "
                  f"({alive:06x} {mode:06x} {fresh:06x})", alive == mode == fresh == MAGIC)
            for name, knob, g in (("VRB", w[33], gain), ("DLY", w[37], w[38])):
                v = knobs[0] if name == "VRB" else knobs[1]
                check(f"{tag}: {name} published as the knob ({knob:06x}, want {v << 16:06x})",
                      knob == v << 16)
                want = int((v / 128) ** 2 * (1 << 23))
                check(f"{tag}: {name}'s gain glided to (knob/128)^2 ({g:06x}, want ~{want:06x})",
                      abs(g - want) <= max(8, want // 100))
            check(f"{tag}: the reverb buffer carries the wet", any(buf))
            check(f"{tag}: a delay buffer is stamped for the hook "
                  f"({' '.join('%06x' % x for x in stamps)})",
                  any((x & 0xff0000) == 0x5a0000 and (x & 0xff) in range(0, 0x71, 0x10) for x in stamps))
        else:
            check(f"{tag}: no RETURNS, the core-0 words zero ({alive:06x} {w[33]:06x} "
                  f"{fresh:06x} {gain:06x} {mode:06x} {w[37]:06x} {w[38]:06x})",
                  not any((alive, w[33], fresh, gain, mode, w[37], w[38])))
            check(f"{tag}: no RETURNS, no delay stamp and no ALIVE_D", not any(stamps) and not alive_d)

    def route(a_, b_, label, differ):
        d = diffs(a_, b_)
        n = d["MAIN"][1]
        for t, (k, m) in d.items():
            want = t in differ
            ok = m > 100 and ((k == m) if want else (k == 0))
            check(f"{label}: {t} {'differs' if want else 'equal'} ({k}/{m} frames differ)", ok)
        return n

    route("on", "onv0", "MASTER TRACK on, VRB 108 vs 0", {"T8", "MAIN"})
    route("on", "ond0", "MASTER TRACK on, DLY 108 vs 0", {"T8", "MAIN"})
    route("off", "offd0", "MASTER TRACK off, DLY 108 vs 0", {"MAIN"})
    route("off", "ctl", "RETURNS vs the hosts' prints", {"T1", "T5", "MAIN"})
    print(f"verify_returns: {'ok' if not fails else 'FAIL'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
