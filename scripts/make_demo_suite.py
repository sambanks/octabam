#!/usr/bin/env python3
"""Render the Discord demo suite: every BongDelay mode and ChonVerb character
on real + synthesized sources, tempo-matched to the delay's TIME grid.

    python3 scripts/make_demo_suite.py            # everything -> out/demo_suite/
    python3 scripts/make_demo_suite.py --only grain   # name substring filter

TEMPO MATH. Delay length is TIME*128 + 64 samples (dsp/delay_server.asm p0),
ceiling 16320 (~370 ms), so a musical echo means picking the source BPM and
the TIME knob together:
    8th  = 2 beats/s worth: TIME 93  -> 11968 smp = 271.4 ms = 110.55 BPM 8th
    8th  at 90 BPM:         TIME 114 -> 14656 smp = 332.3 ms =  90.27 BPM 8th
    16th at 110.55:         TIME 46  ->  5952 smp (and 46/47 straddle it)
    16th at  90.27:         TIME 57  ->  7360 smp
The MusicRadar kits are cut at 110 and 90 BPM (close enough that echoes hold
lock over a 4-bar loop); the synthesized sources below are sequenced ON the
grid (16th = 5984 smp at "110.55", 7328 smp at "90.27") so they lock exactly.

ARCHITECTURE NOTE. Both effects are RETURNS (v3/v4): the emulator render is
the WET ALONE, so every demo here is dry + K*wet summed offline, K chosen per
demo as a wet-vs-dry RMS offset in dB (the 13 Aug demo-pass method; Sam's
"sounds a lot better lower" verdict is why the defaults sit -8..-12 dB).
PITCH caps TIME at ~111; FREEZE is unhearable locally (DFRZ from block 0
holds silence) so it is deliberately absent.
"""

import argparse, array, math, os, pathlib, random, struct, subprocess, sys, wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "demo_suite"
SRC = OUT / "_src"          # trimmed/tiled/synthesized dry sources
WET = OUT / "_wet"          # raw emulator wet renders (kept for re-mixing)
SR = 44100
DEV_MEM = ROOT / "out" / "dsp" / "mem_dev_A.mem"

# ---------------------------------------------------------------- wav io ----

def read_wav(path):
    """-> (list[(L,R) floats -1..1], sr). Mono is duplicated."""
    w = wave.open(str(path), "rb")
    n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
    raw = w.readframes(n)
    w.close()
    out = []
    if sw == 2:
        a = array.array("h"); a.frombytes(raw)
        sc = 1 / 32768.0
        if ch == 1:
            out = [(v * sc, v * sc) for v in a]
        else:
            out = [(a[i] * sc, a[i + 1] * sc) for i in range(0, len(a), ch)]
    elif sw == 3:
        sc = 1 / 8388608.0
        def s24(o):
            v = raw[o] | (raw[o + 1] << 8) | (raw[o + 2] << 16)
            return v - 16777216 if v & 0x800000 else v
        stride = 3 * ch
        for f in range(n):
            l = s24(f * stride)
            r = s24(f * stride + 3) if ch > 1 else l
            out.append((l * sc, r * sc))
    else:
        raise SystemExit(f"{path}: unhandled sample width {sw}")
    return out, sr

def write_wav(path, frames):
    path.parent.mkdir(parents=True, exist_ok=True)
    w = wave.open(str(path), "wb")
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    a = array.array("h")
    for l, r in frames:
        a.append(max(-32767, min(32767, int(round(l * 32767)))))
        a.append(max(-32767, min(32767, int(round(r * 32767)))))
    w.writeframes(a.tobytes()); w.close()

def rms_db(frames, upto=None):
    n = min(len(frames), upto) if upto else len(frames)
    if n == 0:
        return -120.0
    acc = sum(l * l + r * r for l, r in frames[:n]) / (2 * n)
    return 10 * math.log10(acc) if acc > 1e-12 else -120.0

# ------------------------------------------------- synthesized sources ----
# Sequenced directly on the delay grid so echoes lock sample-exact.

def synth_kalimba(step=5984, bars=4):
    """Kalimba-ish plucks: strong fundamental (exp decay), a fast-dying
    inharmonic ~5.4x partial and a 3 ms attack tick. D maj pentatonic."""
    scale = [293.66, 329.63, 369.99, 440.0, 493.88, 587.33, 659.25, 739.99]
    # 2-bar pattern of (16th index, scale degree, velocity), then repeated
    pat = [(0, 5, .9), (2, 3, .6), (4, 6, .8), (6, 4, .5), (8, 7, .9),
           (10, 5, .6), (12, 3, .7), (14, 1, .5), (16, 4, .85), (18, 2, .55),
           (20, 5, .8), (24, 0, .9), (26, 2, .6), (28, 3, .75)]
    total = step * 16 * bars
    buf = [0.0] * total
    rng = random.Random(7)
    for rep in range(bars // 2):
        base = rep * step * 32
        for pos, deg, vel in pat:
            f = scale[deg]
            start = base + pos * step
            dur = min(int(SR * 0.9), total - start)
            w1 = 2 * math.pi * f / SR
            w2 = 2 * math.pi * f * 5.4 / SR
            for i in range(dur):
                env1 = math.exp(-i / (SR * 0.28))
                env2 = math.exp(-i / (SR * 0.03))
                v = vel * (0.7 * math.sin(w1 * i) * env1
                           + 0.12 * math.sin(w2 * i) * env2)
                if i < 132:                        # 3 ms tick
                    v += vel * 0.15 * (rng.random() - 0.5) * (1 - i / 132)
                buf[start + i] += v
    pk = max(abs(v) for v in buf) or 1.0
    g = 0.55 / pk
    return [(v * g, v * g) for v in buf]

def synth_arp(step=7328, bars=4):
    """Soft square-ish arp (odd harmonics, one-pole LP feel via 1/n^1.6
    rolloff), B minor add9, on the 90.27 BPM 16th grid."""
    chords = [[123.47, 185.0, 246.94, 293.66, 369.99],
              [110.0, 164.81, 220.0, 277.18, 329.63]]
    total = step * 16 * bars
    buf = [0.0] * total
    for bar in range(bars):
        notes = chords[(bar // 2) % 2]
        for s in range(16):
            f = notes[(s * 2) % len(notes)] * (2 if s % 4 == 2 else 1)
            start = bar * 16 * step + s * step
            dur = min(int(step * 1.6), total - start)
            for i in range(dur):
                env = min(1.0, i / 200.0) * math.exp(-i / (SR * 0.16))
                ph = f * i / SR
                v = 0.0
                for h in (1, 3, 5, 7):
                    if f * h < 12000:
                        v += math.sin(2 * math.pi * ph * h) / h ** 1.6
                buf[start + i] += 0.55 * env * v
    pk = max(abs(v) for v in buf) or 1.0
    g = 0.5 / pk
    return [(v * g, v * g) for v in buf]

# ------------------------------------------------------- source registry ----

def tile(frames, times):
    return frames * times

def prep_sources():
    """Build every dry source into SRC/ once. -> {name: path}"""
    d = ROOT / "out" / "demo_sources"
    dd = d / "discord"
    plans = {
        # name: (builder) — trims are gentle: full loops, capped for suite size
        "drums110": lambda: read_wav(dd / "drums_dry.wav")[0],
        "drums90": lambda: tile(read_wav(d / "RRD_KitC_Clean-90-01.wav")[0], 4),
        "piano": lambda: read_wav(d / "piano_chords.wav")[0][: 16 * SR],
        "glow": lambda: read_wav(d / "glow_excerpt.wav")[0][: 16 * SR],
        "guitar": lambda: read_wav(d / "solo_guitar.wav")[0][: 14 * SR],
        "band": lambda: read_wav(dd / "band_dry.wav")[0][: 14 * SR],
        "melody": lambda: read_wav(ROOT / "out" / "test_audio" / "melody.wav")[0][: 12 * SR],
        "kalimba": synth_kalimba,
        "arp": synth_arp,
    }
    paths = {}
    for name, fn in plans.items():
        p = SRC / f"{name}.wav"
        if not p.exists():
            print(f"  [src] {name}")
            write_wav(p, fn())
        paths[name] = p
    return paths

# ------------------------------------------------------------- renders ----

def run_cmd(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"FAILED: {' '.join(map(str, cmd))}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout

def render_reverb(src, wet_path, mode, tail, params):
    cmd = [sys.executable, "tools/render_reverb.py", str(src),
           "--mode", str(mode), "--tail", str(tail), "-o", str(wet_path)]
    for k, v in params.items():
        cmd += ["-p", f"{k}={v}"]
    run_cmd(cmd)
    # render_reverb appends the mode label to the filename
    label = {0: "ROOM", 1: "PLATE", 2: "BIG"}[mode]
    got = wet_path.with_name(wet_path.name + f"_{label}.wav")
    return got if got.exists() else wet_path

def render_send(src, wet_path, tail, layout, pick, dargs):
    cmd = [sys.executable, "tools/send_probe.py", "--mem", str(DEV_MEM),
           "--layout", layout, "--in", str(src), "--tail", str(tail),
           "--wav", str(wet_path)]
    if pick:
        cmd += ["--pick", pick]
    for k, v in dargs.items():
        cmd += [f"--{k}", str(v)]
    run_cmd(cmd)
    return wet_path

def mix(dry_path, wets, out_path, headroom=0.97):
    """out = dry + sum(K_i * wet_i); each wet targeted wet_db below the dry's
    RMS (measured over the dry's own length)."""
    dry, _ = read_wav(dry_path)
    n_dry = len(dry)
    layers = []
    n_out = n_dry
    for wet_path, wet_db in wets:
        wf, _ = read_wav(wet_path)
        k = 10 ** ((rms_db(dry) + wet_db - rms_db(wf, upto=n_dry)) / 20)
        layers.append((wf, k))
        n_out = max(n_out, len(wf))
    out = []
    for i in range(n_out):
        l = dry[i][0] if i < n_dry else 0.0
        r = dry[i][1] if i < n_dry else 0.0
        for wf, k in layers:
            if i < len(wf):
                l += wf[i][0] * k
                r += wf[i][1] * k
        out.append((l, r))
    pk = max(max(abs(l), abs(r)) for l, r in out)
    if pk > headroom:
        g = headroom / pk
        out = [(l * g, r * g) for l, r in out]
    write_wav(out_path, out)
    return pk

# ---------------------------------------------------------------- suite ----
# Each entry: (name, source, kind, spec, wet_db, blurb)
#   kind 'verb':  spec = (mode, {KNOB: val})
#   kind 'delay': spec = {send_probe --dX args}
#   kind 'combo': spec = ({delay args incl dvrbw}, {reverb args}, wash_db)

SUITE = [
    # ---- ChonVerb alone: the mode ladder, then each mode's range ----
    ("verb_room_piano", "piano", "verb", (0, {"TIME": 64}), -11,
     "ROOM, stock TIME - the three modes on the same piano for A/B"),
    ("verb_plate_piano", "piano", "verb", (1, {"TIME": 64}), -11,
     "PLATE, same settings as the ROOM render"),
    ("verb_big_piano", "piano", "verb", (2, {"TIME": 64}), -11,
     "BIG, same settings - the mode ladder's third rung"),
    ("verb_room_tight_drums", "drums110", "verb", (0, {"TIME": 18, "LP": 70}), -10,
     "ROOM at its smallest: TIME 18, darkened - drum-booth ambience"),
    ("verb_room_kalimba", "kalimba", "verb", (0, {"TIME": 40}), -10,
     "tight ROOM on kalimba - small-space realism check"),
    ("verb_plate_short_band", "band", "verb", (1, {"TIME": 35}), -12,
     "short bright PLATE as mix glue on the full band"),
    ("verb_plate_infinite_glow", "glow", "verb", (1, {"TIME": 127}), -9,
     "PLATE at TIME 127 - the coolest-running mode, endless and clean"),
    ("verb_plate_warble_pad", "arp", "verb",
     (1, {"TIME": 90, "MOD": 127, "RATE": 3}), -9,
     "PLATE, MOD 127 at 4x RATE - the R41 relaw pushed to chorus-warble"),
    ("verb_big_glow", "glow", "verb", (2, {"TIME": 100}), -9,
     "BIG long tail on ambient guitar"),
    ("verb_big_dark_guitar", "guitar", "verb", (2, {"TIME": 110, "LP": 45}), -9,
     "BIG with LP 45: dark cathedral, all bloom and no air"),
    ("verb_big_thin_piano", "piano", "verb", (2, {"TIME": 127, "HP": 90}), -9,
     "BIG at max TIME with HP 90: just the airy top of the tail"),
    ("verb_big_shimmer_glow", "glow", "verb", (2, {"TIME": 100, "SPEED": 90}), -8,
     "BIG + SHMR 90: octave-up bloom on the tail"),
    ("verb_big_shimmer_piano", "piano", "verb", (2, {"TIME": 90, "SPEED": 70}), -9,
     "BIG + SHMR 70 on piano chords"),
    ("verb_shimmer_max_glow", "glow", "verb", (2, {"TIME": 127, "SPEED": 127}), -8,
     "SHMR 127 at max TIME - full glassy choir, the extreme end"),
    ("verb_gate8_drums", "drums110", "verb", (2, {"TIME": 110, "GATE": 8}), -6,
     "gated BIG, tight hold (GATE 8) - the Phil Collins slam"),
    ("verb_gate20_drums", "drums110", "verb", (2, {"TIME": 110, "GATE": 20}), -6,
     "gated BIG, longer hold (GATE 20) - breathes, then chops"),

    # ---- BongDelay alone: every locally-hearable mode, ends of each ----
    ("delay_clean_pong_drums110", "drums110", "delay",
     {"dtime": 93, "dfdbk": 70, "dtone": 110, "dping": 115, "dwow": 0}, -8,
     "CLEAN ping-pong 8ths at 110 BPM (TIME 93 = 271.4 ms), bright, DPTH 0"),
    ("delay_clean_16th_kalimba", "kalimba", "delay",
     {"dtime": 46, "dfdbk": 60, "dtone": 100, "dping": 127, "dwow": 0}, -8,
     "CLEAN 16ths on the grid-locked kalimba, full ping-pong"),
    ("delay_slapback_band", "band", "delay",
     {"dtime": 46, "dfdbk": 12, "dtone": 95, "dping": 0, "dwow": 10,
      "drate": 40}, -9,
     "135 ms rockabilly slapback, one repeat, hint of wobble"),
    ("delay_dub_drums90", "drums90", "delay",
     {"dtime": 114, "dfdbk": 100, "dtone": 30, "dspray": 70, "dwow": 25}, -7,
     "dub: 8ths at 90 BPM, dark TONE, DRV 70 drive, light wobble (now live)"),
    ("delay_runaway_dub_drums90", "drums90", "delay",
     {"dtime": 114, "dfdbk": 127, "dtone": 22, "dspray": 95, "dwow": 40}, -7,
     "FDBK 127 + DRV 95: the runaway dub end, repeats smearing into drone"),
    ("delay_tape_warm_arp", "arp", "delay",
     {"dtime": 57, "dfdbk": 80, "dtone": 70, "dwow": 35, "drate": 40,
      "dspray": 35}, -8,
     "warm tape: gentle DPTH/RATE drift + mild drive on 90 BPM 16ths"),
    ("delay_tape_seasick_kalimba", "kalimba", "delay",
     {"dtime": 93, "dfdbk": 85, "dtone": 80, "dwow": 127, "drate": 110,
      "dspray": 30}, -8,
     "seasick tape: DPTH 127 at fast RATE - the broken-cassette end"),
    ("delay_pitch_up12_kalimba", "kalimba", "delay",
     {"dmode": 1, "dptch": 0, "dtime": 93, "dfdbk": 70, "dwow": 0}, -9,
     "PITCH +12: every repeat an octave up, shifted once (no cascade)"),
    ("delay_pitch_up7_arp", "arp", "delay",
     {"dmode": 1, "dptch": 1, "dtime": 57, "dfdbk": 85, "dwow": 0}, -9,
     "PITCH +7: fifths on 16th repeats - instant harmony"),
    ("delay_pitch_dn12_melody", "melody", "delay",
     {"dmode": 1, "dptch": 2, "dtime": 93, "dfdbk": 80, "dwow": 0}, -9,
     "PITCH -12: sub-octave repeats"),
    ("delay_pitch_detune_glow", "glow", "delay",
     {"dmode": 1, "dptch": 3, "dtime": 108, "dfdbk": 75, "dwow": 0}, -8,
     "PITCH detune (+-15 cents, L up / R down): wide chorus echo"),
    ("delay_grain_piano", "piano", "delay",
     {"dmode": 3, "dtime": 32, "dfdbk": 127, "dspray": 64, "dtone": 127,
      "dwow": 45, "dptch": 3}, -12,
     "GRAIN, the ear-passed voicing: DENS 45, SPRAY 64, wide interval set"),
    ("delay_grain_dense_glow", "glow", "delay",
     {"dmode": 3, "dtime": 32, "dfdbk": 127, "dspray": 64, "dtone": 127,
      "dwow": 80, "dptch": 3}, -11,
     "GRAIN at DENS 80 - fuller cloud, the other approved end"),
    ("delay_grain_coherent_melody", "melody", "delay",
     {"dmode": 3, "dtime": 32, "dfdbk": 127, "dspray": 10, "dtone": 127,
      "dwow": 60, "dptch": 2}, -11,
     "GRAIN near-coherent: SPRAY 10, mid set - the pitch-shifter-adjacent end"),
    ("delay_grain_narrow_band", "band", "delay",
     {"dmode": 3, "dtime": 32, "dfdbk": 127, "dspray": 64, "dtone": 127,
      "dwow": 60, "dptch": 1}, -13,
     "GRAIN on a full band, NARROW set 1 (wide sets land wrong notes on chords)"),
    ("delay_reverse_guitar", "guitar", "delay",
     {"dmode": 4, "dptch": 0, "dtime": 100, "dfdbk": 55, "dwow": 0}, -7,
     "REVERSE, 93 ms segments on solo guitar"),
    ("delay_reverse_piano", "piano", "delay",
     {"dmode": 4, "dptch": 1, "dtime": 100, "dfdbk": 70, "dwow": 0}, -7,
     "REVERSE, 46 ms segments - choppier flip"),
    ("delay_reverse_stutter_drums110", "drums110", "delay",
     {"dmode": 4, "dptch": 3, "dtime": 100, "dfdbk": 80, "dwow": 0}, -7,
     "REVERSE at 512-sample segments: glitch stutter on drums"),

    # ---- Together: BongDelay -> ChonVerb over the -VRB cross-send ----
    ("combo_grain_bigwash_glow", "glow", "combo",
     ({"dmode": 3, "dtime": 32, "dfdbk": 127, "dspray": 64, "dtone": 127,
       "dwow": 45, "dptch": 3, "dvrbw": 100}, {"time": 100, "rmode": 2}, -9), -12,
     "the Microcosm shot: GRAIN cloud washing into long BIG"),
    ("combo_pong_verb_drums110", "drums110", "combo",
     ({"dtime": 93, "dfdbk": 70, "dtone": 110, "dping": 115, "dwow": 0,
       "dvrbw": 85}, {"time": 60, "rmode": 2}, -11), -8,
     "CLEAN ping-pong 8ths, each echo pulling a BIG tail behind it"),
    ("combo_pitch_shimmer_kalimba", "kalimba", "combo",
     ({"dmode": 1, "dptch": 0, "dtime": 93, "dfdbk": 70, "dwow": 0,
       "dvrbw": 100}, {"time": 90, "shmr": 80, "rmode": 2}, -9), -10,
     "PITCH +12 into BIG + SHMR 80: octave echoes into an octave-up wash"),
    ("combo_slap_room_band", "band", "combo",
     ({"dtime": 46, "dfdbk": 20, "dtone": 90, "dwow": 20, "dvrbw": 70},
      {"time": 40, "rmode": 0}, -12), -9,
     "135 ms slapback + small ROOM glue on the full band"),
    ("combo_dub_cathedral_drums90", "drums90", "combo",
     ({"dtime": 114, "dfdbk": 110, "dtone": 28, "dspray": 70, "dwow": 30,
       "dvrbw": 110}, {"time": 127, "rmode": 2}, -8), -9,
     "dark dub into BIG at max TIME: the dronescape end"),
    ("combo_reverse_plate_guitar", "guitar", "combo",
     ({"dmode": 4, "dptch": 0, "dtime": 100, "dfdbk": 55, "dwow": 0,
       "dvrbw": 100}, {"time": 100, "rmode": 1}, -9), -8,
     "REVERSE segments washing into long PLATE: the backwards-tape trick"),
    ("combo_seasick_shimmer_glow", "glow", "combo",
     ({"dtime": 93, "dfdbk": 85, "dtone": 80, "dwow": 110, "drate": 95,
       "dspray": 30, "dvrbw": 100}, {"time": 110, "shmr": 90, "rmode": 2}, -8), -9,
     "warped tape echoes into shimmer BIG - the wildest patch in the set"),
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="substring filter on demo names")
    ap.add_argument("--force", action="store_true",
                    help="re-render even when the output already exists")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    if not DEV_MEM.exists():
        print("building DEV image (delay hatch) ...")
        env = dict(os.environ, DEV="1", XBUS="1")
        r = subprocess.run([sys.executable, "tools/build_bus.py"], cwd=ROOT,
                           env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(r.stdout[-2000:] + r.stderr[-2000:])

    print("preparing sources ...")
    srcs = prep_sources()

    jobs = [j for j in SUITE if not a.only or a.only in j[0]]
    results = []
    for name, src, kind, spec, wet_db, blurb in jobs:
        out_path = OUT / f"{name}.wav"
        if out_path.exists() and not a.force:
            results.append((name, src, blurb, None))
            continue
        print(f"[{len(results)+1}/{len(jobs)}] {name}")
        if kind == "verb":
            mode, params = spec
            wet = render_reverb(srcs[src], WET / f"{name}.wav", mode, 8, params)
            pk = mix(srcs[src], [(wet, wet_db)], out_path)
        elif kind == "delay":
            wet = render_send(srcs[src], WET / f"{name}.wav", 3.0, "DS", None, spec)
            pk = mix(srcs[src], [(wet, wet_db)], out_path)
        else:  # combo: one RDS run per pick, honest single-render bus
            dargs, rargs, wash_db = spec
            common = dict(dargs)
            common.update(rargs)
            common["dlevel"] = 127
            common["level"] = 0
            wet_d = render_send(srcs[src], WET / f"{name}_D.wav", 6.0, "RDS", "D", common)
            wet_r = render_send(srcs[src], WET / f"{name}_R.wav", 6.0, "RDS", "R", common)
            pk = mix(srcs[src], [(wet_d, wet_db), (wet_r, wash_db)], out_path)
        results.append((name, src, blurb, pk))
        print(f"    -> {out_path.name}  peak {pk:.2f}", flush=True)

    idx = OUT / "INDEX.md"
    with open(idx, "w") as f:
        f.write("# BongDelay + ChonVerb demo suite\n\n")
        f.write("Every file is dry + wet summed offline (both effects are "
                "returns; balances follow the 13 Aug demo-pass verdicts). "
                "Dry sources in `_src/`, raw wet renders in `_wet/`.\n\n")
        f.write("Sources: MusicRadar sample kits (drums, royalty-free), "
                "University of Iowa MIS piano, Scott Buckley - 'Glow' "
                "(CC-BY 4.0, credit Scott Buckley), band/guitar/melody from "
                "the existing demo set, kalimba + arp synthesized in-repo "
                "(scripts/make_demo_suite.py, tempo-locked to the TIME grid)."
                "\n\nFREEZE is absent: it engages from block 0 in a fixed-"
                "param render and holds silence (PLAN.md).\n\n")
        for name, src, blurb, pk in results:
            f.write(f"- **{name}.wav** ({src}) - {blurb}\n")
    print(f"\n{len(results)} demos -> {OUT}\nindex -> {idx}")

if __name__ == "__main__":
    main()
