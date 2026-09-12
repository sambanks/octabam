#!/usr/bin/env python3
"""Measure the unit's gain chain around the DSP under the ColdFire port.

The O9d fixture (Sam's RIG, T1 THRU with FX1 = SEND and FX2 = EQUALIZER
flat, tone on RX0 slot 2) gave ONE point of the pre-FX track gain:
k = 2130129/2^23 = -11.906 dB at AMP VOL 64 (COLDFIRE_PORT.md O9d). This
sweeps the part bytes the mixer model needs and fits each stage:

  chain in   : the 84-word track record's audio     (what the FX chain is fed)
  chain out  : T1's slot of core 1's read-back      (pre-mix, after FX2)
  TX0        : --audio-out, the ESAI's main pair     (post-mix)

  python3 tools/scratch/mixer_sweep.py vol   0 32 64 96 127     # AMP VOL, T1
  python3 tools/scratch/mixer_sweep.py level 0 64 100 108 127   # track LEVEL, T1
  python3 tools/scratch/mixer_sweep.py bal   0 32 64 96 127     # AMP BAL, T1
  python3 tools/scratch/mixer_sweep.py report                   # table of every run so far

Each run: copy the fixture project, write the byte into EVERY part record of
every bank (current + saved, the set_fx rule), stage a card with route A's
own staging, run the port for FRAMES frames, extract both taps, fit rms
ratios over the LAST window (the ColdFire slews a knob from the transport
start: the first 160 frames are a ramp, O12). Results land in OUT/<stage>_<v>.json.
"""
import json, math, pathlib, shutil, subprocess, sys, wave
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import ot_project as op   # noqa: E402
import o9d_compare as oc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "out/o9d/proj_t1eqA"
IMAGE = ROOT / "out/raw/section_3_MAIN_OS.bin"
TONE = ROOT / "out/o9c/toneC_300.wav"          # 8 ch, RX0 slot k = a tone; slot 2 reaches T1
OUT = ROOT / "out/mixer"
FRAMES = 400                                   # 6400 samples; the slew is over by 2560
TRACK = 1
AMP_VOL, AMP_BAL = 3, 4                        # ATK HOLD REL VOL BAL XVOL

def rms(x):
    return math.sqrt(sum(v * v for v in x) / len(x)) if x else 0.0

def db(x):
    return 20 * math.log10(x) if x > 0 else -200.0

def write_byte(pdir, stage, value):
    t = TRACK - 1
    for bank in sorted(pdir.glob("bank*.work")):
        def mut(data):
            for p in range(op.NPARTS_ALL):
                off = op.PART_BASE + p * op.PART_STRIDE
                if stage == "vol":
                    data[off + op.P1_OFF + t * op.TRACK_STRIDE - 6 + AMP_VOL] = value
                elif stage == "bal":
                    data[off + op.P1_OFF + t * op.TRACK_STRIDE - 6 + AMP_BAL] = value
                elif stage == "level":
                    data[off + 0x1b + 2 * t] = value
                else:
                    sys.exit(f"stage {stage!r}")
        op._bank_write(pdir, int(bank.name[4:6]), mut, guard=False)

def run(stage, value):
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{stage}_{value:03d}"
    proj = OUT / f"proj_{tag}"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(FIXTURE, proj)
    # the RIG's T8 is a master track with stock LO-FI on FX1 -- nonlinear, and
    # between the chain output and TX0. Off, so TX0 is the mix itself.
    pw = proj / "project.work"
    pw.write_bytes(pw.read_bytes().replace(b"MASTER_TRACK=1", b"MASTER_TRACK=0"))
    write_byte(proj, stage, value)
    card = OUT / f"card_{tag}.img"
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "RIG",
                    "--tree", str(OUT / f"tree_{tag}"), "--out", str(card)], check=True,
                   stdout=subprocess.DEVNULL)
    prefix = OUT / tag
    cmd = [str(ROOT / "out/emu/ot_emu"), "--image", str(IMAGE), "--card", str(card),
           "--set", "OCTABAM", "--project", "RIG", "--sequencer", "--internal-clock",
           "--frames", str(FRAMES), "--load-ms", "20000", "--dsp", "--main-level", "64",
           "--audio-in", str(TONE), "--audio-out", str(prefix), "--block-dump", f"{prefix}.dump"]
    with open(f"{prefix}.txt", "w") as log:
        subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)
    return analyse(stage, value)

def win_fit(port, host, lag, lo=1500, win=200):
    """Per-window least-squares scale of port against host (lag-aligned), the
    MEDIAN over windows and the worst residual: the RIG's pattern re-trigs T1
    ~frame 340 (a ~400-sample dip at the chain output, the input tap flat), so
    a whole-run rms is not the gain and a median is."""
    n = min(len(port), len(host) - max(lag, 0)) - 200
    ks, res = [], []
    for s in range(max(lo, -lag), n - win, win):
        seg = range(s, s + win)
        den = sum(host[i + lag] ** 2 for i in seg)
        if den <= 0:
            continue
        k = sum(port[i] * host[i + lag] for i in seg) / den
        r = rms([port[i] - k * host[i + lag] for i in seg]); pw = rms([port[i] for i in seg])
        ks.append(k); res.append(db(r / pw) if pw else -200.0)
    ks.sort()
    return ks[len(ks) // 2], max(res), len(ks)

def best_lag(port, host, lo, hi, seg):
    best = None
    for lag in range(lo, hi + 1):
        den = sum(host[i + lag] ** 2 for i in seg)
        if den <= 0:
            continue
        k = sum(port[i] * host[i + lag] for i in seg) / den
        r = rms([port[i] - k * host[i + lag] for i in seg])
        if best is None or r < best[1]:
            best = (lag, r)
    return best[0]

def analyse(stage, value):
    tag = f"{stage}_{value:03d}"
    prefix = OUT / tag
    oc.extract(f"{prefix}.dump", TRACK, str(prefix))
    inp = oc.rd(f"{prefix}_in.wav"); outp = oc.rd(f"{prefix}_rb_L.wav")
    n = min(len(inp), len(outp))
    k, worst, nw = win_fit(outp, inp, -32)          # O9d's lag: the 32-sample record pipeline
    # TX0: every slot, from the transport start; the main pair is fitted against the chain output
    w = wave.open(f"{prefix}_core0.wav", "rb"); nch, sw, nfr = w.getnchannels(), w.getsampwidth(), w.getnframes()
    raw = w.readframes(nfr)
    start = None
    for line in open(f"{prefix}.txt"):
        if "audio out" in line and "transport start at frame" in line:
            start = int(line.rsplit("frame", 1)[1].split()[0])
    slots, tx = [], []
    for ch in range(nch):
        seg = [int.from_bytes(raw[(i * nch + ch) * sw:(i * nch + ch + 1) * sw], "little", signed=True) / (1 << 23)
               for i in range(start, start + n)]
        tx.append(seg); slots.append(rms(seg[1500:n - 200]))
    r_in = rms(inp[1500:n - 200]); r_out = rms(outp[1500:n - 200])
    txfit = {}
    for ch in range(nch):
        if slots[ch] < 1e-6:
            continue
        lag = best_lag(tx[ch], outp, -256, 256, range(1500, 3000))
        kk, ww, _ = win_fit(tx[ch], outp, lag)
        txfit[ch] = {"lag": lag, "g_db": db(abs(kk)), "g_lin": kk, "worst_resid_db": ww}
    res = {"stage": stage, "value": value, "in_db": db(r_in), "out_db": db(r_out),
           "k_db": db(abs(k)), "k_lin": k, "k_q23": round(k * 8388608), "worst_resid_db": worst, "windows": nw,
           "tx0_db": [db(s) for s in slots], "tx0_fit": txfit, "n": n}
    (OUT / f"{tag}.json").write_text(json.dumps(res, indent=1))
    print(f"{tag}: in {res['in_db']:.2f} dBFS, chain k {res['k_db']:.3f} dB ({res['k_q23']}/2^23, worst window {worst:.1f} dB); "
          + "TX0 " + " ".join(f"s{ch}:{f['g_db']:+.3f}dB@{f['lag']:+d}(worst {f['worst_resid_db']:.0f})" for ch, f in txfit.items()))
    return res

def report():
    rows = sorted((json.loads(p.read_text()) for p in OUT.glob("*.json")), key=lambda r: (r["stage"], r["value"]))
    print(f"{'stage':6} {'v':>4} {'in dBFS':>8} {'chain k dB':>11} {'k/2^23':>8} {'worst':>6}  TX0 slot: gain vs chain out (lag)")
    for r in rows:
        print(f"{r['stage']:6} {r['value']:4d} {r['in_db']:8.2f} {r['k_db']:11.3f} {r['k_q23']:8d} {r['worst_resid_db']:6.0f}  "
              + "  ".join(f"s{ch}:{f['g_db']:+7.3f} ({f['lag']:+d})" for ch, f in r["tx0_fit"].items()))

if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    elif sys.argv[1] == "analyse":
        analyse(sys.argv[2], int(sys.argv[3]))
    else:
        for v in sys.argv[2:]:
            run(sys.argv[1], int(v))
