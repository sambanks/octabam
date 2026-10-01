#!/usr/bin/env python3
"""POST FADER under the port: the bus sends follow the tracks' fader, mute
and solo, in the DSP-bound records only (modules/post-fader).

    python3 tools/verify/verify_postfader.py REMIX --project DIR

Stages two cards from the project, hosted for the remix (T1 BusDelay, T5
BusVerb, T8 the stock DELAY -- the hosts print their wet, so the returns are
T1's and T5's read-backs; every SEND's DEL and REV at 100, every FX2 slot 0-1
unlocked and off the LFOs), one with T7's SEND at 100/100 and one with T7's
at 0/0. The project has T7 muted (the stress template does; the mixer's MAIN
gain for T7 reads 0). Runs both under `ot_emu`, dumps the ColdFire SRAM at
the end, and checks:

  records  each SEND track's slot 0/1 halfwords in this frame's records are
           the knob (100 << 8) x (L/128)^2, L the mixer record's MAIN gain
           (halfword 1's high byte); T7 (muted) sends 0/0; T8 (not a send)
           keeps its knob.
  audio    the bus returns (T1's and T5's read-backs), frame by frame after
           both engines are warm, are the SAME whether the muted T7 sends
           100/100 or 0/0: a muted sender contributes nothing and does not
           register (a registered silent client would dilute the others'
           level through the auto-gain).

What it cannot see: solo (no fixture), the unit, the sound.
SKIPs without a project or the port, and for a remix without POST FADER.
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
OUT = ROOT / "out/postfaderverify"
FRAMES, WARM = 1000, 650              # both engines warm up dry after load
FIXTURES = (("t7on", 100), ("t7off", 0))
RETURNS_RB = ((1, (0x80003190, 0x80003590), 0, "T1"), (0, (0x80003390, 0x80003790), 0, "T5"))


def stage(template, remix, tag, t7, audio):
    d = OUT / tag
    shutil.rmtree(d, ignore_errors=True)
    (d / "project").mkdir(parents=True)
    for f in template.iterdir():
        if f.is_file() and f.suffix.lower() in (".work", ".strd"):
            shutil.copy2(f, d / "project" / f.name)
    p = d / "project"
    otp.host_rig(p, remix, guard=False)
    otp.set_fx(p, "fx2", 8, "DELAY", guard=False)          # the hosts print: no RETURNS
    otp.stamp_slot(p, "SEND", "DEL", 100, guard=False)
    otp.stamp_slot(p, "SEND", "REV", 100, guard=False)
    otp.stamp_slot(p, "SEND", "DEL", t7, guard=False, tracks={7})
    otp.stamp_slot(p, "SEND", "REV", t7, guard=False, tracks={7})

    def free(data):
        # locks on FX2 slots 0-1 (lock slots 24, 25) and LFOs on them would
        # move the knobs the records are checked against
        for pat in range(16):
            for t in range(8):
                base = otp.trac_off(pat, t) + 0x59
                for st in range(64):
                    data[base + st * 32 + 24] = 0xff
                    data[base + st * 32 + 25] = 0xff
        for part in range(otp.NPARTS_ALL):
            for t in range(8):
                lfo = otp.PART_BASE + part * otp.PART_STRIDE + otp.LFO_PM_OFF + t * 30
                for k in range(3):
                    if data[lfo + k] in (24, 25):
                        data[lfo + k] = 18
    for bw in sorted(p.glob("bank*.work")):
        otp._bank_write(p, int(bw.name[4:6]), free, guard=False)
    otp.set_master_track(p, False)
    raw = (p / "project.work").read_bytes()
    (p / "project.work").write_bytes(re.sub(rb"\r\nPATTERN=\d+\r\n", b"\r\nPATTERN=0\r\n", raw))
    cmd = [str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(p), "OCTABAM", "PF",
           "--tree", str(d / "tree"), "--out", str(d / "card.img"), "--image-mb", "64"]
    for a in audio:
        cmd += ["--audio", a]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_postfader: stage_card {tag} failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")


def run(image, tag):
    d = OUT / tag
    cmd = [str(EMU), "--image", str(image), "--card", str(d / "card.img"), "--set", "OCTABAM",
           "--project", "PF", "--sequencer", "--internal-clock", "--frames", str(FRAMES),
           "--load-ms", "90000", "--dsp", "--main-level", "64",
           "--block-dump", str(d / "blocks.dump"),
           "--mem-dump", f"0x80000000,0x8000={d / 'sram.bin'}"]
    with open(d / "run.txt", "w") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    return tag, r.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--image", default="")
    a = ap.parse_args()
    remix = registry.remix(a.remix)
    if "POST FADER" not in remix.modules:
        print(f"  [ -- ] verify_postfader: {a.remix} carries no POST FADER"); return 0
    if not a.project:
        print("  [SKIP] verify_postfader: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_postfader: no port binary (make emu-cf)"); return 0
    template = pathlib.Path(a.project).expanduser()
    if not (template / "project.work").is_file():
        sys.exit(f"verify_postfader: {template} is not a project")
    OUT.mkdir(parents=True, exist_ok=True)
    image = pathlib.Path(a.image) if a.image else OUT / "mainos.bin"
    if not a.image:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_postfader: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    audio = []
    for s in otp.read_project(template)[1]:
        rel = s["path"]
        src = (template / rel).resolve() if rel else None
        if src is not None and src.is_file():
            audio.append(f"{src}:{rel[3:] if rel.startswith('../') else 'PF/' + rel}")
    for tag, t7 in FIXTURES:
        stage(template, a.remix, tag, t7, sorted(set(audio)))
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
        print(f"verify_postfader: FAIL ({fails})"); return 1

    mods = registry.modules()
    send_id, dly_id, t8_ids = mods["SEND"].menu.fx2_id, mods["DELAY SERVER"].menu.fx2_id, None
    d = (OUT / "t7on" / "sram.bin").read_bytes()
    u16 = lambda addr: int.from_bytes(d[addr - 0x80000000:addr - 0x80000000 + 2], "big")
    u32 = lambda addr: int.from_bytes(d[addr - 0x80000000:addr - 0x80000000 + 4], "big")
    rec = 0x80000110 + (u32(0x800000e0) << 9)
    mix = u32(0x80003c10)
    for t in range(8):
        fid = u16(rec + 64 * t + 56)
        lvl = u16(mix + 8 * t + 2) >> 8
        s0, s1 = u16(rec + 64 * t + 24), u16(rec + 64 * t + 26)
        if fid in (send_id, 0):
            want = (100 << 8) * lvl * lvl >> 14
            check(f"T{t + 1} SEND at L {lvl}: DEL/REV {s0:04x}/{s1:04x}, want {want:04x}"
                  + (" (muted: 0)" if lvl == 0 else ""), s0 == want and s1 == want)
        elif t == 7:
            check(f"T8 (FX2 id {fid:#x}, not a send) keeps its knobs ({s0:04x}/{s1:04x})",
                  fid not in (send_id, 0, dly_id))
    check("T7 is muted in the fixture (its MAIN gain reads 0)", u16(mix + 8 * 6 + 2) == 0)

    A = bd.classes(bd.read(OUT / "t7on" / "blocks.dump"))
    B = bd.classes(bd.read(OUT / "t7off" / "blocks.dump"))
    for core, rams, ti, name in RETURNS_RB:
        n = k = 0
        for ram in rams:
            sa = {f: w for f, w in A.get(('<', 1, core, ram), [])}
            sb = {f: w for f, w in B.get(('<', 1, core, ram), [])}
            for f in sa:
                if f in sb and f > WARM:
                    n += 1
                    k += sa[f][64 * ti:64 * ti + 64] != sb[f][64 * ti:64 * ti + 64]
        check(f"{name}'s return identical whether the muted T7 sends 100 or 0 "
              f"({k}/{n} frames differ)", n > 100 and k == 0)
    print(f"verify_postfader: {'ok' if not fails else 'FAIL'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
