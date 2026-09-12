#!/usr/bin/env python3
"""One part, under the firmware and under the harness, on the same input:
does `rig_render` (mixer model included) match the ColdFire port?

    python3 tools/harness/port_compare.py --project out/o9d/proj_t1eqA --remix bus
    python3 tools/harness/port_compare.py --project PROJ --image out/mainos_bus.bin --remix bamsep27 \\
        --tracks 1,2,5,8 --frames 400

The port (`tools/emu/ot_emu`) boots IMAGE, loads PROJECT from a staged card,
starts the sequencer with TONE on the ESAI inputs and dumps every host-port
block (`--block-dump`) and the ESAI output (`--audio-out`). From the dump,
per track: the chain INPUT (the 84-word track record's audio, after the
THRU's input gain and before the DSP's AMP stage) and the chain OUTPUT (the
core's read-back slot, after FX2 and before LEVEL). Then `rig_render` runs
the SAME part on the SAME image with each track's chain input as its stem
(`--amp 1.0`, the model applying VOL^2 and the balance as the DSP does) and
the two are fitted per track -- lag, least-squares scale, residual -- and
the port's TX0 main slot against `mix.wav` (LEVEL^2 and the sum).

What a result means. A linear chain (SEND, a flat EQ, a station at rest)
should fit to a scale of 0.00 dB and a residual of -100 dB or better: that
is the mixer model, the parameter path and the harness's dispatch all
agreeing with the firmware on this part. An engine with history (the
reverb's free-running allpass modulator, the delay's LFO) matches in level
and not in residual (COLDFIRE_PORT.md O12: -14 dB with the modulators
live, levels within 0.1 dB) -- read the scale, not the residual, there.
A scale that is NOT 0 dB on a linear chain is a finding: a knob the port
publishes that the harness does not, or the reverse.

Cost: one port run (~75 s for 400 frames) plus one rig_render. The project
is COPIED before anything is written to it; `--master-off` (default) turns
MASTER_TRACK off in the copy so TX0 is the mix itself and not the master's
FX (the RIG's T8 master carries stock LO-FI, O14).
"""
import argparse, json, math, os, pathlib, shutil, subprocess, sys, wave
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "scratch"))   # the block-dump readers
import blockdump as bd                      # noqa: E402  (tools/scratch)
import o10_recloop as rl                    # noqa: E402  (track_audio, readback_audio)

ROOT = pathlib.Path(__file__).resolve().parents[2]
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
TONE = ROOT / "out/o9c/toneC_300.wav"
SR = 44100


def db(x):
    return 20 * math.log10(x) if x > 0 else -200.0


def rms(x):
    return math.sqrt(sum(v * v for v in x) / len(x)) if x else 0.0


def write_wav(path, L, R):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(3); w.setframerate(SR)
        w.writeframes(b"".join(int(max(-8388608, min(8388607, v))).to_bytes(3, "little", signed=True)
                               for pair in zip(L, R) for v in pair))


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        nch, sw, n = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    ch = [[int.from_bytes(raw[(i * nch + c) * sw:(i * nch + c + 1) * sw], "little", signed=True) / (1 << (8 * sw - 1))
           for i in range(n)] for c in range(nch)]
    return ch


def fit(port, host, lo, hi, win=200, start=1500):
    """Best lag over lo..hi by residual (whole span), then the per-window
    MEDIAN scale and worst residual at that lag (a re-trig or a slew inside
    the span moves an rms and not a median, O14)."""
    n = min(len(port), len(host)) - 300
    span = range(max(start, -lo), min(n, n - hi))
    if len(span) < 2 * win:
        return None
    best = None
    for lag in range(lo, hi + 1):
        den = sum(host[i + lag] ** 2 for i in span)
        if den <= 0:
            continue
        k = sum(port[i] * host[i + lag] for i in span) / den
        r = rms([port[i] - k * host[i + lag] for i in span])
        if best is None or r < best[1]:
            best = (lag, r)
    if best is None:
        return None
    lag = best[0]
    ks, res = [], []
    for s in range(span.start, span.stop - win, win):
        seg = range(s, s + win)
        den = sum(host[i + lag] ** 2 for i in seg)
        if den <= 0:
            continue
        k = sum(port[i] * host[i + lag] for i in seg) / den
        p = rms([port[i] for i in seg])
        res.append(db(rms([port[i] - k * host[i + lag] for i in seg]) / p) if p else -200.0)
        ks.append(k)
    if not ks:
        return None
    ks.sort()
    return dict(lag=lag, scale_db=db(abs(ks[len(ks) // 2])), worst_db=max(res),
                median_db=sorted(res)[len(res) // 2], windows=len(ks))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="project dir (copied; never written)")
    ap.add_argument("--image", default=str(STOCK), help="the image the PORT boots (a built out/mainos_bus.bin, or stock)")
    ap.add_argument("--remix", default="bus", help="which remix that image is (rig_render resolves ids by it; stock ids always resolve)")
    ap.add_argument("--set-name", default="OCTABAM")
    ap.add_argument("--name", default="RIG", help="the project's name on the card")
    ap.add_argument("--bank", type=int, default=1)
    ap.add_argument("--part", type=int, default=1)
    ap.add_argument("--tone", default=str(TONE), help="8-channel wav onto RX0 slots 0..7")
    ap.add_argument("--frames", type=int, default=400, help="sequencer frames to run under the port")
    ap.add_argument("--load-ms", type=int, default=20000)
    ap.add_argument("--main-level", type=int, default=64)
    ap.add_argument("--tracks", default="", help="1,2,5 (default: every track whose chain input is not silent)")
    ap.add_argument("--master-off", dest="master_off", action="store_true", default=True)
    ap.add_argument("--master-on", dest="master_off", action="store_false")
    ap.add_argument("--out", default="out/port_compare")
    ap.add_argument("--reuse", action="store_true", help="skip the port run if its dump is already there")
    ap.add_argument("--tol", type=float, default=0.1, help="scale tolerance in dB for the PASS line")
    ap.add_argument("--lag", type=int, default=96,
                    help="lag search +-N samples (the record pipeline is 32, a bus stage 16; on a periodic "
                         "tone the fit is ambiguous modulo the period -- 147 at 300 Hz -- so keep it short)")
    a = ap.parse_args()

    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    proj = out / "project"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(a.project, proj)
    if a.master_off:
        pw = proj / "project.work"
        pw.write_bytes(pw.read_bytes().replace(b"MASTER_TRACK=1", b"MASTER_TRACK=0"))
    card = out / "card.img"
    dump = out / "port.dump"
    if not (a.reuse and dump.is_file()):
        subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), a.set_name, a.name,
                        "--tree", str(out / "tree"), "--out", str(card)], check=True, stdout=subprocess.DEVNULL)
        cmd = [str(ROOT / "out/emu/ot_emu"), "--image", a.image, "--card", str(card),
               "--set", a.set_name, "--project", a.name, "--sequencer", "--internal-clock",
               "--frames", str(a.frames), "--load-ms", str(a.load_ms), "--dsp", "--main-level", str(a.main_level),
               "--audio-in", a.tone, "--audio-out", str(out / "port"), "--block-dump", str(dump)]
        print("port: " + " ".join(cmd[1:]))
        with open(out / "port.txt", "w") as log:
            subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)
    c = bd.classes(bd.read(str(dump)))

    # the taps
    taps = {}
    for t in range(1, 9):
        inL, inR = rl.track_audio(c, t), rl.track_audio(c, t, True)
        if not inL:
            continue
        outL, outR = rl.readback_audio(c, t), rl.readback_audio(c, t, True)
        taps[t] = dict(inL=inL, inR=inR, outL=outL, outR=outR,
                       in_db=db(rms(inL[1500:] + inR[1500:]) / 8388608), out_db=db(rms(outL[1500:] + outR[1500:]) / 8388608))
    # Compare the tracks that PASS audio under the port: chain input AND chain
    # output live. A record with audio and a chain output of digital zero is
    # not a closed chain -- it is a machine whose record carries something
    # other than its chain input (a STATIC/FLEX slot's record is not the
    # THRU's, O10), and feeding that to the harness compares two different
    # things. Listed, not compared, unless --tracks names it.
    # A bus HOST or a return has chain output and no chain input of its own
    # (it is fed over the bus): compared on its output, its stem silent.
    live = [t for t, v in taps.items() if v["out_db"] > -120]
    skipped = [t for t, v in taps.items() if v["in_db"] > -120 and t not in live]
    want = [int(x) for x in a.tracks.split(",") if x] if a.tracks else live
    if not want:
        sys.exit("no track passes audio under the port -- is the THRU trigged, is the tone on its input?")
    n = min(len(taps[t]["inL"]) for t in want)
    print("port taps (dBFS, from sample 1500): " + "  ".join(f"T{t} in {taps[t]['in_db']:.1f} out {taps[t]['out_db']:.1f}" for t in want)
          + (f"   (record audio but no chain output, not compared: {', '.join(f'T{t}' for t in skipped)})" if skipped else ""))

    # the harness on the same part, fed each track's chain input
    stems = []
    for t in want:
        if taps[t]["in_db"] <= -120:
            continue                                   # a host: nothing of its own to feed
        p = out / f"stem_T{t}.wav"
        write_wav(p, taps[t]["inL"][:n], taps[t]["inR"][:n])
        stems += ["--stem", f"T{t}={p}"]
    rig = out / "rig"
    cmd = [sys.executable, str(ROOT / "tools/harness/rig_render.py"), "--image", a.image, "--remix", a.remix,
           "--project", str(proj), "--bank", str(a.bank), "--part", str(a.part), "--amp", "1.0",
           "--frames", "16", "--tail", "0", "--out", str(rig)] + stems
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    (out / "rig.txt").write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        sys.exit(f"rig_render failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    for line in r.stdout.splitlines():
        if line.startswith("mixer") or "SEND alias" in line or "skipped" in line:
            print("  " + line.strip())

    # per track: the port's chain output against the harness's T<n>.wav
    results = {}
    print(f"\n{'track':6} {'lag':>5} {'scale dB':>9} {'resid worst':>12} {'median':>8}   (port chain out vs rig T<n>.wav, L)")
    ok = True
    for t in want:
        L, R = read_wav(rig / f"T{t}.wav")
        port = [v / 8388608 for v in taps[t]["outL"]]
        f = fit(port, L, -a.lag, a.lag)
        if f is None:
            print(f"T{t:<5} (nothing to fit)"); continue
        results[t] = f
        flag = "" if abs(f["scale_db"]) <= a.tol else "  <- scale off"
        ok &= abs(f["scale_db"]) <= a.tol
        print(f"T{t:<5} {f['lag']:5d} {f['scale_db']:+9.3f} {f['worst_db']:12.1f} {f['median_db']:8.1f}{flag}")

    # the mix: the port's TX0 slots against mix.wav
    mixL, mixR = read_wav(rig / "mix.wav")
    tx = read_wav(out / "port_core0.wav")
    start = None
    for line in open(out / "port.txt"):
        if "audio out" in line and "transport start at frame" in line:
            start = int(line.rsplit("frame", 1)[1].split()[0])
    best = None
    for ch, seg in enumerate(tx):
        s = seg[start:start + n]
        if rms(s[1500:]) < 1e-6:
            continue
        for side, m in (("L", mixL), ("R", mixR)):
            f = fit(s, m, -a.lag, a.lag)
            if f and (best is None or f["worst_db"] < best[2]["worst_db"]):
                best = (ch, side, f)
    if best:
        ch, side, f = best
        flag = "" if abs(f["scale_db"]) <= a.tol else "  <- scale off"
        ok &= abs(f["scale_db"]) <= a.tol
        print(f"mix    {f['lag']:5d} {f['scale_db']:+9.3f} {f['worst_db']:12.1f} {f['median_db']:8.1f}{flag}   (port TX0 slot {ch} vs mix.wav {side})")
        results["mix"] = dict(slot=ch, side=side, **f)
    else:
        print("mix    (TX0 silent -- master on, or nothing reached the main out)")
    (out / "result.json").write_text(json.dumps(results, indent=1))
    print(f"\n{'PASS' if ok else 'FAIL'}: every fitted scale within {a.tol} dB of the firmware's"
          + ("" if ok else " -- a knob the port publishes and the harness does not, or the reverse"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
