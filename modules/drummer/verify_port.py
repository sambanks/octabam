#!/usr/bin/env python3
"""DRUMMER under the ColdFire port: the firmware plays what the engine says, step by step.

    .venv/bin/python3 modules/drummer/verify_port.py --sample DIR/NAME.wav [--image out/mainos_bus.bin]
        [--project <empty project>] [--case NAME] [--bars 2]

The user's sample (NAME.wav + NAME.ot) on FLEX slot 1, T1 a DRUMMER track in every Part (FLEX, signed
"DR",1 in the NEIGHBOR PLAYBACK bytes), its LIVE page (STYL DENS CPLX HUMN BRK GHST) and CONFIG page
(SEED VEL ALT SWNG ORN VAR) in the Part's FLEX PLAYBACK bytes. The port plays
`--bars` bars at 240 BPM; every T1 voice start (its slice, pc 0x4000f67c) and the step counter are
watched; each start is matched to the step whose grid it falls on, and the run must equal what
engine.py predicts for the same kit and knobs:

  groove   BREAKBEAT, DENS 64, CPLX 40, HUMAN 0: the slice of every played step, no other start
  human    HIP-HOP, HUMAN 100: the slices and the steps (micro-timing moves a start inside its step)
  forced   FUNK, DENS 0, HUMAN 0, the track's own trigs on steps 3 and 11: they play too
  config   HIP-HOP, HUMAN 127, GHST 100, every CONFIG knob away from its default
  short    groove on a 12-step pattern: each pass starts a bar on step 1 (a 12-step 4/4 bar)
  align    groove, with ALIGN 20 ms on slice 6 (the KIT's RAM poked): its starts 882 samples early
  rolls    BREAKBEAT, HUMAN 127, ORN 127, BRK 110: flams, rolls and repeats; every start's slice in order
           (each hit 1 + RTRG times: stock restarts the voice through the start for each retrig)
  gain     groove, every slice's GAIN -12 dB (the KIT's RAM poked): each hit's VOL is the groove run's x 0.25
           (from a drummer.work of version 1: no GAIN in the file, so 0 until poked)
  scene    groove, slice 5 SCENE 1 (DOSE 100 %) and slice 3 SCENE 1 (DOSE 50 %), scene 1 locking T1's FX1
           first knob to 100 (the KIT's RAM poked): at each start the lane's FX1 knob is 100 on slice 5's
           hits, halfway from the Part's value on slice 3's, the Part's own on the others
  mix      HIP-HOP, HUMAN 0, KIT BALANCE (the zones' mix in the Part's STATIC PLAYBACK bytes, marked 'M'):
           KICK 0, SNARE 64, HATS 127, the others 64: the steps as the engine says with that mix
  redrum   REDRUM on (image 77, in a drummer.work of version 5): HUMN 0, SEED 0, CPLX 64 -- the sample's own loop, each
           slice on the step its start falls on in the 2-bar trim (TRIM_BARS 200, the slot's settings read
           by the adapter), as engine.py's dr_loop_build places it from the .ot
  live     transport stopped, SLICES trig mode, the AED open on its SLICE tab (MKII): trigs 3, 6, 10, 1
           play slices 2, 5, 9, 0 as on a FLEX track (a live start takes the slice stock locked, not the
           engine's; reported 2026-11-06: always the same slice)

The sample stays on the user's disk and on scratch cards under out/.
"""
import argparse
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import probe_slices as ps  # noqa: E402

DEF_ZONE = ["KICK", "PERC", "SNARE", "KICK", "HATC", "KICK", "SNARE", "GHOST",
            "KICK", "PERC", "SNARE", "KICK", "HATC", "KICK", "SNARE", "PERC"]
DEF_ROLE = ["ACCENT", "ACCENT", "NORMAL", "SOFT", "NORMAL", "NORMAL", "ACCENT", "SOFT",
            "ACCENT", "ACCENT", "NORMAL", "SOFT", "NORMAL", "NORMAL", "ACCENT", "NORMAL"]
# name: (STYL DENS CPLX HUMN BRK GHST), (SEED VEL ALT SWNG ORN VAR), forced steps -- knob_rows() puts them on the
# Part's pages; ORN and GHST 0 where HUMN is 0 (their own knobs since images 64 and 65: the cases' groove kept bare)
CASES = {
    "groove": ((0, 64, 40, 0, 0, 0), (1, 64, 64, 64, 0, 64), ()),
    "human": ((6, 64, 40, 100, 0, 64), (1, 64, 64, 64, 32, 64), ()),          # STYL 6: HHOP
    "forced": ((11, 0, 0, 0, 0, 0), (1, 64, 64, 64, 0, 64), (2, 10)),       # STYL 11: FUNK
    "config": ((6, 80, 60, 127, 0, 100), (9, 100, 127, 127, 90, 127), ()),
    "align": ((0, 64, 40, 0, 0, 0), (1, 64, 64, 64, 0, 64), ()),
    "rolls": ((0, 90, 80, 127, 110, 64), (3, 64, 64, 64, 127, 64), ()),
    "short": ((0, 64, 40, 0, 0, 0), (1, 64, 64, 64, 0, 64), ()),
    "gain": ((0, 64, 40, 0, 0, 0), (1, 64, 64, 64, 0, 64), ()),
    "live": ((0, 64, 40, 0, 0, 0), (1, 64, 64, 64, 0, 64), ()),
    "scene": ((0, 64, 40, 0, 0, 0), (1, 64, 64, 64, 0, 64), ()),
    "mix": ((6, 64, 40, 0, 0, 0), (1, 64, 64, 64, 0, 64), ()),
    "redrum": ((0, 64, 64, 0, 0, 0), (0, 64, 64, 64, 0, 64), ()),
}
# REDRUM on (drummer.work version 5, T1's byte; a poke after the load comes after the first step): the loop from the slot (build_project: TRIM_BARSx100=200, BPMx24=2232)
REDRUM = {"redrum": (200, 2232)}
LOOP_SRC = {}                                  # the .ot's slices and the WAV's frames, set by main()
# KIT BALANCE written into every Part (STATIC's PLAYBACK bytes of the track, and the mark after "DR",1)
MIXES = {"mix": (0, 64, 127, 64, 64, 64)}
# SCENE / DOSE poked into the KIT's RAM (slice: (scene 1..16, dose % or 0 = 100)); the scene's cell
SCENES = {"scene": {4: (1, 0), 2: (1, 50)}}
SCENE_K, SCENE_V = 18, 100                     # FX1's first knob (scene byte numbering), locked to 100
# live: (trig key code, the slice stock plays) -- trig n is key n - 1; SLICES mode = 0x460d16f0 := 3
LIVE_KEYS = ((0x2, 2), (0x5, 5), (0x9, 9), (0x0, 0))
# pattern lengths other than 16: every pass of the pattern starts a bar on its step 1
PLEN = {"short": 12}
# cases with retrigs: the starts' slices in time order against each hit's slice x (1 + RTRG)
FLAT = {"rolls", "config"}   # big micro-timing or retrigs: a start can land nearer the next grid
# ALIGN poked into the KIT's RAM after the load (slice: ms): its hits start that much earlier
ALIGNS = {"align": {5: 20}}


def symbol(name):
    for line in (ps.ROOT / "out/platform/runtime/runtime.map").read_text().splitlines():
        w = line.split()
        if len(w) == 2 and w[1] == name and w[0].startswith("0x"):
            return int(w[0], 16)
    raise SystemExit(f"verify_port: {name} not in the runtime map (build the image first)")
TEMPO = 240
STEP = 44100 * 60 / TEMPO / 4                  # samples


def write_kit(proj, track=0, redrum=False):
    """drummer.work (and .strd) with T1's kit: the test kit below, read back by the load (store.c); version 1,
    or version 5 with REDRUM on (GAIN, SCENE, DOSE, links none, SIMILAR off)."""
    import struct, zlib
    zone = {n: i for i, n in enumerate(E.ZONES)}
    role = {n: i for i, n in enumerate(E.ROLES)}
    t1 = (bytes(zone[z] for z in DEF_ZONE) + bytes([15] * 48) + bytes(role[r] for r in DEF_ROLE) + bytes(48)
          + bytes(128) + bytes(64) + bytes((0, 1, 6, 4, 3, 5, 7, 8, 2)) + bytes((0, 4, 1)))
    assert len(t1) == 332
    body = bytes(332 * track) + t1 + bytes(332 * (7 - track))
    ver = 1
    if redrum:
        ver = 5
        body += bytes(4 * 8 * 64 + 16) + bytes(1 if t == track else 0 for t in range(8))
    data = struct.pack(">4I", 0x44524D4B, ver, len(body), zlib.crc32(body)) + body
    for name in ("drummer.work", "drummer.strd"):
        (proj / name).write_bytes(data)


def predict(case, bars):
    live, conf, forced = CASES[case]
    kit = E.make_kit(16, {i: (DEF_ZONE[i], DEF_ROLE[i]) for i in range(16)})
    p = E.params(style=min(live[0] * len(E.STYLES) // 128, len(E.STYLES) - 1), dens=live[1], cplx=live[2], human=live[3], brk=live[4], ghost=live[5],
                 seed=conf[0], vel=conf[1], round=conf[2], time=conf[3], orn=conf[4], var=conf[5],
                 shift=0, phrase=4)
    if case in MIXES:
        p.mix[:] = list(MIXES[case])
    if case in REDRUM:
        slices, count, frames = LOOP_SRC["v"]
        lp = E.loop([s[0] for s in slices[:count]], frames, bars100=REDRUM[case][0], tempo24=REDRUM[case][1])
        return E.play(kit, p, bars, redrum=lp)
    if case in PLEN:                     # bars laid on the pattern: each pass a (short) bar from step 1
        import ctypes
        out, st, h = [], E.State(), E.Hit()
        for bar in range(bars * 16 // PLEN[case] + 1):
            for step in range(PLEN[case]):
                E.lib().dr_step(ctypes.byref(kit), ctypes.byref(p), ctypes.byref(st), bar, step, 0, ctypes.byref(h))
                out.append((bar, step, h.as_tuple()))
        return out[:bars * 16]
    return E.play(kit, p, bars, forced={(b, s) for b in range(bars) for s in forced})


def knob_rows(live, conf):
    """The cases' (STYL DENS CPLX HUMN BRK GHST), (SEED VEL ALT SWNG ORN VAR) as the Part's two knob rows since
    image 61: LIVE SEED DENS CPLX ORN BRK GHST, SETUP STYL VEL ALT SWNG HUMN VAR."""
    return ((conf[0], live[1], live[2], conf[4], live[4], live[5]),
            (live[0], conf[1], conf[2], conf[3], live[3], conf[5]))


def run(a, case, wav, slices, count, frames, out):
    live, conf, forced = CASES[case]
    proj = out / "project"
    t = a.track - 1
    ps.build_project(pathlib.Path(a.project), proj, frames, slices, count, TEMPO, track=t)

    def mut(data):
        row1, row2 = knob_rows(live, conf)
        for p in range(ps.otp.NPARTS_ALL):
            part = ps.otp.PART_BASE + p * ps.otp.PART_STRIDE      # the file's Part = RAM's + 9
            base = part + ps.VALUES_OFF + 30 * t + 6 * ps.FLEX
            data[base:base + 6] = bytes(row1)
            su = part + ps.SETUP_OFF + 30 * t + 6 * ps.FLEX
            data[su:su + 6] = bytes(row2)
            data[part + 9 + 60 + 30 * t:part + 9 + 63 + 30 * t] = b"DR\x01"   # the track is a DRUMMER track
            if case in MIXES:
                data[part + 9 + 0x2a + 30 * t:part + 9 + 0x30 + 30 * t] = bytes(MIXES[case])
                data[part + 9 + 63 + 30 * t] = ord("M")
        off = ps.otp.trac_off(0, t)
        data[off:off + 64] = bytes(64)
        data[off + 0x59:off + 0x59 + 64 * 32] = bytes([0xff]) * (64 * 32)
        for s in forced:
            data[off + 7 - s // 8] |= 1 << (s % 8)
        if case in SCENES:
            for p in range(ps.otp.NPARTS_ALL):
                part = ps.otp.PART_BASE + p * ps.otp.PART_STRIDE + 9
                for sc in {v[0] for v in SCENES[case].values()}:
                    cell = part + 0x662 + ((sc - 1) * 8 + t) * 32
                    data[cell:cell + 32] = bytes([0xff]) * 32
                    data[cell + SCENE_K] = SCENE_V
    ps.otp._bank_write(proj, 1, mut, guard=False)
    if case in PLEN:
        ps.otp.set_pattern_scale(proj, 1, 0, PLEN[case], "1X", guard=False)
    write_kit(proj, t, redrum=case in REDRUM)
    card = out / "card.img"
    r = subprocess.run([str(ps.PY), str(ps.ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "RIG",
                        "--tree", str(out / "tree"), "--out", str(card), "--audio", f"{wav}:{ps.SAMPLE_REL}"],
                       cwd=ps.ROOT, capture_output=True, text=True)
    if r.returncode:
        return None, f"stage_card failed: {(r.stdout + r.stderr)[-600:]}"
    if case == "live":
        return run_live(a, card, out)
    cmd = [str(ps.EMU), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "RIG",
           "--sequencer", "--internal-clock", "--frames", str(int(a.bars * 16 * STEP / 16) + 400),
           "--load-ms", "90000", "--main-level", "64",
           "--watch-mem", f"{0x800049f8 + 0xa8 * t:#x},1;{0x800064d0 + t:#x},1;{0x80000a6e + 64 * t:#x},2;"
                          f"{symbol('dr_strt') + t:#x},1"]
    if case == "gain":
        base = symbol("dr_gain")
        cmd += ["--poke", ";".join(f"{base + 64 * t + sl:#x}={0x100 - 12:#x}" for sl in range(64))]
    if case in SCENES:
        sb, db = symbol("dr_scene"), symbol("dr_dose")
        cmd += ["--poke", ";".join(f"{sb + 64 * t + sl:#x}={sc};{db + 64 * t + sl:#x}={d}"
                                   for sl, (sc, d) in SCENES[case].items())]
        cmd[cmd.index("--watch-mem") + 1] += f";{0x80000810 + 72 * t + SCENE_K:#x},1"
    if case in ALIGNS:
        base = symbol("dr_align")                       # dr_align[track][64]: T1's row first
        cmd += ["--poke", ";".join(f"{base + 64 * t + sl:#x}={ms}" for sl, ms in ALIGNS[case].items())]
    log = out / "port.txt"
    rc = 0
    if not (a.reuse and log.is_file()):
        with open(log, "w") as f:
            f.write(" ".join(cmd) + "\n"); f.flush()
            rc = subprocess.run(cmd, cwd=ps.ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    text = log.read_text()
    if rc or "run ended REACHED" not in text:
        return None, f"port run failed (exit {rc}) -- {log}"
    steps, starts, vols, strts, lane = [], [], [], [], []
    trk = a.track - 1
    strt_addr = symbol("dr_strt") + trk
    for m in re.finditer(r"\[\s*([\d.]+)\] \[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|0) \(\d\) at pc (0x[0-9a-f]+)", text):
        t, addr, val, pc = float(m.group(1)), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16)
        if addr == 0x800064d0 + trk:
            steps.append((t, val))
        elif addr == 0x800049f8 + 0xa8 * trk and pc == 0x4000f67c:
            starts.append((t, val))
        elif addr == 0x80000a6e + 64 * trk:
            vols.append((t, val >> 8, pc))
        elif addr == strt_addr:
            strts.append((t, val))
        elif addr == 0x80000810 + 72 * trk + SCENE_K:
            lane.append((t, val))
    if case in SCENES:
        base = ps.otp.PART_BASE + 9 + 0x11a + 24 * trk + (SCENE_K - 6)
        bank = (out / "project" / "bank01.work").read_bytes()
        part_v = bank[base]
        return (steps, starts, vols, strts, lane, part_v), str(log)
    return (steps, starts, vols, strts), str(log)


def run_live(a, card, out):
    """Select the track, AED, its SLICE tab (AMP), then the trig keys in SLICES mode; the slice each start plays."""
    t = a.track - 1
    ev, ms = [(600, f"key {0x10 + t:#x}"), (1800, "key 0x1e"), (3500, "key 0x23")], 5000
    for code, _ in LIVE_KEYS:
        ev.append((ms, f"key {code:#x}"))
        ms += 1500
    script = out / "live.script"
    script.write_text("".join(f"{m} {k} down\n{m + 250} {k} up\n" for m, k in ev) + f"{ms} quit\n")
    cmd = [str(ps.EMU), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "RIG", "--mkii",
           "--load-ms", "20000", "--main-level", "64", "--poke", "0x460d16f3=3", "--live-script", str(script),
           "--watch-mem", f"{0x800049f8 + 0xa8 * t:#x},1"]
    log = out / "port.txt"
    if not (a.reuse and log.is_file()):
        with open(log, "w") as f:
            f.write(" ".join(cmd) + "\n"); f.flush()
            subprocess.run(cmd, cwd=ps.ROOT, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text()
    if "ended on quit" not in text:
        return None, f"port run failed -- {log}"
    got = [int(m.group(1), 16) for m in re.finditer(r"<- (0x[0-9a-f]+|0) \(1\) at pc 0x4000f67c", text)]
    return got, str(log)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--image", default=str(ps.ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--project", default=str(ps.ROOT / "out/drummer/slices/fresh/image/NOPROJ"))
    ap.add_argument("--case", action="append", choices=sorted(CASES))
    ap.add_argument("--bars", type=int, default=2)
    ap.add_argument("--reuse", action="store_true", help="parse the last run's logs, do not run the port")
    ap.add_argument("--track", type=int, default=1, help="the DRUMMER track, 1..8")
    a = ap.parse_args()
    wav = pathlib.Path(a.sample).expanduser().resolve()
    slices, count = ps.read_ot(wav.with_suffix(".ot"))
    import wave
    with wave.open(str(wav)) as w:
        frames = w.getnframes()
    LOOP_SRC["v"] = (slices, count, frames)
    fails = 0
    for case in a.case or list(CASES):
        out = ps.ROOT / "out/drummer/port" / (case if a.track == 1 else f"{case}-t{a.track}")
        out.mkdir(parents=True, exist_ok=True)
        res, info = run(a, case, wav, slices, count, frames, out)
        if res is None:
            print(f"  [FAIL] {case}: {info}")
            fails += 1
            continue
        if case == "live":
            want = [sl for _, sl in LIVE_KEYS]
            ok = res == want
            print(f"  [{'PASS' if ok else 'FAIL'}] live: SLICES trigs in the AED play {res} (want {want}) -- {info}")
            fails += not ok
            continue
        if case in SCENES:
            steps, starts, vols, strts, lane, part_v = res
            seen, bad = [], 0
            for tt, sl in starts:
                prior = [v for lt, v in lane if lt <= tt]
                now = prior[-1] if prior else part_v
                sc = SCENES[case].get(sl)
                exp = part_v if not sc else part_v + (SCENE_V - part_v) * (sc[1] or 100) // 100
                seen.append((sl, now, exp))
                bad += now != exp
            kinds = sorted({(sl, e) for sl, _, e in seen})
            ok = bool(seen) and not bad and any(SCENES[case].get(sl) for sl, _, _ in seen)
            print(f"  [{'PASS' if ok else 'FAIL'}] scene: {len(seen) - bad}/{len(seen)} starts with FX1's knob as "
                  f"the slice's SCENE / DOSE says (Part {part_v}; slice: want {kinds}) -- {info}")
            if not ok:
                print("   ", [x for x in seen if x[1] != x[2]][:10])
            fails += not ok
            continue
        steps, starts, vols, strts = res
        # the grid instant of global step n: the counter's change to (n+1) mod len, + ~900 samples
        grid = []
        prev = None
        for t, v in steps:
            if v == PLEN.get(case, 16):
                continue                         # the wrap writes the length, then 0 (twice): one step, not two
            if prev is None or v != prev:
                grid.append(t)
            prev = v
        want = predict(case, a.bars)
        got = {}
        for t, sl in starts:
            n = min(range(len(grid)), key=lambda i: abs(grid[i] + 900 - t)) if grid else 0
            if abs(grid[n] + 900 - t) < STEP * 0.75:
                got.setdefault(n, []).append(sl)
        lines, bad = [], 0
        for n, (bar, step, h) in enumerate(want):
            if n >= len(grid):
                break
            exp = [h[1]] if h[0] else []
            ok = got.get(n, []) == exp
            bad += not ok
            lines.append(f"    {bar + 1}.{step + 1:02d}  want {exp!s:6} got {got.get(n, [])!s:8} {'' if ok else '<--'}")
        checked = min(len(want), len(grid))
        ok = bad == 0 and checked >= 16
        if case in FLAT:
            # the hits: every start DRUMMER makes writes dr_strt (2 x slice), in order; the retrigs are
            # stock's own restarts (not through DRUMMER's start), the starts beyond those
            hits = [h for _, _, h in want[:checked] if h[0]]
            mine = [v // 2 for tt, v in strts if grid and tt >= grid[0] - 2000][:len(hits)]
            n_all = len([1 for tt, sl in starts if grid and tt >= grid[0] - 2000 and tt <= grid[-1]])
            asked = sum(h[4] for h in hits)
            ok = mine == [h[1] for h in hits] and 0 < n_all - len(hits) <= asked
            bad = 0 if ok else 1
            print(f"    hits in order: {'the engine' + chr(39) + 's ' + str(len(hits)) if mine == [h[1] for h in hits] else 'got ' + str(mine)}; "
                  f"retrig starts {n_all - len(hits)} (asked {asked}, a hit cuts the retrigs of the one before)")
            if mine != [h[1] for h in hits]:
                print("    want", [h[1] for h in hits])
        print(f"  [{'PASS' if ok else 'FAIL'}] {case}: {checked - bad}/{checked} steps as the engine says "
              f"({len(starts)} starts; VOL writes {len([v for v in vols if v[2] > 0x40000000 and v[2] < 0x40100000])} "
              f"stock, {len(vols)} total) -- {info}")
        if not ok:
            print("\n".join(lines))
            fails += 1
        if case == "gain":
            # the same hits as groove, each VOL the groove's x 256 x 10^(-12/20) >> 8 (= 64, the table's)
            gout = ps.ROOT / "out/drummer/port" / ("groove" if a.track == 1 else f"groove-t{a.track}")
            reuse = a.reuse
            a.reuse = (gout / "port.txt").is_file()
            gres, _ = run(a, "groove", wav, slices, count, frames, gout)
            a.reuse = reuse
            mine = [v for _, v, pc in vols if pc >= 0x40100000]
            ref = [v for _, v, pc in gres[2] if pc >= 0x40100000] if gres else []
            want = [max(1, v * 64 >> 8) if v else 0 for v in ref]
            gok = bool(mine) and mine == want
            print(f"  [{'PASS' if gok else 'FAIL'}] gain: {len(mine)} hits' VOL = groove's x 0.25 (-12 dB)"
                  + ("" if gok else f" -- got {mine[:8]} want {want[:8]}"))
            fails += not gok
    print(f"{'PASS' if not fails else 'FAIL'}: DRUMMER port")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
