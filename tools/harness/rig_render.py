#!/usr/bin/env python3
"""Render the whole rig locally: eight tracks, both DSP cores, the real image.

    python3 tools/harness/rig_render.py --tracks T1=D,T2=S,T3=S,T4=S,T5=R,T6=S,T7=S,T8=S \\
        --stems out/test_audio --out out/rig

    python3 tools/harness/rig_render.py --project ~/octa/backups/OCTABAM_RIG --bank 2 --part 1 \\
        --stems ~/stems --out out/rig            # ids and every knob from the part

Each track is what the unit makes of it: its FX1 and FX2 effects, chained on
the track's own audio, on the CORE that track lives on -- tracks 5-8 on
payload A (core 0), 1-4 on payload B (core 1), in dispatch order, with the
shared window Y:0x30000-0x3FFFF really shared between the two emulated cores
(tools/harness/dsp_host, 7 Sep 2026). So a SEND on T2 reaches BusVerb on T5 the way
it does on hardware: across the core boundary, through the bus scratch.

What comes out: T1.wav .. T8.wav (each track's stereo output, dry + wet as
the DSP emits it -- the chain output, before LEVEL), mix.wav (the main out:
every track through its LEVEL, summed, saturated the way a 24-bit sum is),
and meter.txt (per-block instruction counts per core: the cycle floor of
THIS layout).

THE MIXER MODEL (12 Sep 2026, tools/harness/mixer.py). The unit's gain
chain around the DSP, measured under the ColdFire port: AMP VOL (v/127)^2
and AMP BAL (a balance: the far side falls to zero, the near side stays)
are applied to the stem BEFORE the FX chain, exactly as the DSP's own AMP
stage does it; track LEVEL (L/128)^2 is applied AFTER, at the mix. The
values come from the part (--project: the AMP page and the LEVEL pair) or
the unit's defaults (VOL 64 = -11.9 dB, BAL 64, LEVEL 108 = -3.0 dB), and
--mix T1:VOL=127,LEVEL=100 overrides them. A stem is therefore THE VOICE at
its sample GAIN (0 dBFS in the file = 0 dBFS at the voice), which is why
--amp defaults to 1.0 with the model on. --mixer off is the old harness:
stems at --amp 0.5 straight into the chain, mix.wav a unity sum at -6 dB.

What this is NOT: the ColdFire. Knobs are poked into r6 the way the harness
always has (a slot can draw a knob and publish nothing -- docs/firmware/PARAM_PAGES.md),
the main level and the cue mix are not modelled, samples do not play
(stems stand in for what the track would play), and the cores are lock-step
unless --skew interleaves them (a fuzz of the hardware's timing, never a
proof). docs/remixer/HARNESS.md.

IMAGE. --image is a BUILT image (default out/mainos_bus.bin, i.e. `make bus`
for the remix you want); both payloads are dumped from it into out/dsp/. An
effect the image does not carry on a track's core dispatches to the SEND
alias there, exactly as the unit would -- reported, never silently rendered
as a passthrough (the 12 Aug 2026 trap).
"""
import argparse
import array
import math
import os
import pathlib
import struct
import subprocess
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import send_probe                      # noqa: E402  (entry_points, dump_mem, HOST)
import mixer                           # noqa: E402  (the measured gain chain)
from remix import registry             # noqa: E402

SR = 44100
FRAMES = 16                            # the firmware's frame; the harness's own cap is 15
                                       # (dsp_host -frames overrides it, COLDFIRE_PORT.md O12).
                                       # Voicing renders run whole blocks since 12 Sep 2026;
                                       # the bit-identity gates (send_probe) stay at 15.
NTRACKS = 8
# Track -> core. Measured 10 Aug 2026 (marker flash): payload A serves 5-8.
CORE_OF = {t: (0 if t >= 5 else 1) for t in range(1, NTRACKS + 1)}
POS_OF = {t: (t - 1) % 4 for t in range(1, NTRACKS + 1)}    # dispatch position on its core
# r7 (the state block) is 0x6100 + 0x300*pos + 0x100*(fx-1): the stock
# dispatcher bumps its counter THREE times per track (an unconditional third
# bump at P:0x51e after FX2). Measured 8 Sep 2026 on both payloads under the
# firmware (COLDFIRE_PORT.md O11); the old 1 + 2*pos + (fx-1) put every
# position >= 1 one or more blocks low, and the one-aux return's pin on
# position 3 matched only here -- never on the unit.
# Where the per-track audio buffers go in the harness. Hardware runs every
# track's block at X:0 (the dispatcher copies it in and out); the harness
# gives each track its own buffer, and puts them ABOVE the loaded modules so
# a stock effect scratching X:0x20-0xff (the FLANGER lesson, 2 Sep 2026)
# cannot reach another track's audio.
AUDIO_BASE = 0x9000


def die(msg):
    sys.exit(f"rig_render: {msg}")


# ---- what a track runs -----------------------------------------------------
class Slot:
    """One effect on one track's FX1 or FX2 slot."""
    def __init__(self, module, fx, values):
        self.module = module            # remix.schema.Module
        self.fx = fx                    # 1 or 2
        self.values = list(values)      # 12 knob bytes

    @property
    def key(self):
        return self.module.key


def remix_id_map(remix_name):
    """id -> Module for the modules THIS remix places (a station replaces a
    stock id, so the registry alone is ambiguous), then stock as fallback."""
    r = registry.remix(remix_name)
    mods = registry.modules()
    out = {}
    for k in r.modules:
        m = mods.get(k)
        if m is not None and m.menu is not None:
            out.setdefault(m.menu.fx2_id, m)
    for m in mods.values():
        if m.is_stock and m.menu is not None:
            out.setdefault(m.menu.fx2_id, m)
    return out


def letter_map():
    """layout letter (send_probe's alphabet) -> Module."""
    return {m.harness.layout_char: m for m in registry.modules().values()
            if m.harness is not None and m.harness.layout_char and m.menu is not None}


def defaults_of(m):
    vals = [(p.default or 0) & 0x7f for p in m.params] + [0] * 12
    return vals[:12]


def parse_tracks(spec, remix_name):
    """--tracks 'T1=D,T2=S,T5=R,T3=1+S' -> {track: [Slot...]}.

    A letter or a module KEY names the FX2 effect; 'a+b' puts a on FX1 and
    b on FX2; '.' or omission is an empty track."""
    letters = letter_map()
    mods = registry.modules()
    out = {}
    for item in filter(None, spec.split(",")):
        if "=" not in item:
            die(f"--tracks item {item!r}: want T<n>=<effect>")
        tn, eff = item.split("=", 1)
        t = int(tn.strip().upper().lstrip("T"))
        if not 1 <= t <= NTRACKS:
            die(f"track {t} out of range")
        parts = [p.strip() for p in eff.split("+")]
        fx1, fx2 = (None, parts[0]) if len(parts) == 1 else (parts[0], parts[1])
        slots = []
        for fx, name in ((1, fx1), (2, fx2)):
            if not name or name == ".":
                continue
            m = letters.get(name) or mods.get(name.upper())
            if m is None:
                die(f"track {t}: unknown effect {name!r} (a layout letter or a module KEY)")
            slots.append(Slot(m, fx, defaults_of(m)))
        out[t] = slots
    return out


def part_tracks(project, bank, part, remix_name):
    """ids and knob bytes from a project's bank file, part `part` (1-based)."""
    import ot_project as otp
    pdir = pathlib.Path(project).expanduser()
    bf = pdir / f"bank{bank:02d}.work"
    if not bf.is_file():
        die(f"no {bf}")
    data = bf.read_bytes()
    ids = remix_id_map(remix_name)
    off = otp.PART_BASE + (part - 1) * otp.PART_STRIDE
    out = {}
    mix = {}
    for i in range(NTRACKS):
        # the AMP page (ATK HOLD REL VOL BAL XVOL) sits six bytes before the
        # track's FX1 row; LEVEL is the first of the (LEVEL, cue) pair at +0x1b
        amp = off + otp.P1_OFF + i * otp.TRACK_STRIDE - 6
        mix[i + 1] = dict(vol=data[amp + 3] & 0x7f, bal=data[amp + 4] & 0x7f,
                          level=data[off + 0x1b + 2 * i] & 0x7f)
        slots = []
        for fx, idoff, sub in ((1, otp.FX1_OFF, 0), (2, otp.FX2_OFF, 6)):
            fid = data[off + idoff + i]
            if fid == 0:
                continue
            m = ids.get(fid)
            if m is None:
                print(f"  T{i+1} FX{fx}: id 0x{fid:02x} is not in remix {remix_name!r} or stock -- skipped")
                continue
            a = off + otp.P1_OFF + i * otp.TRACK_STRIDE + sub
            b = off + otp.P2_OFF + i * otp.P2_STRIDE + sub
            vals = list(data[a:a + 6]) + list(data[b:b + 6])
            slots.append(Slot(m, fx, [v & 0x7f for v in vals]))
        if slots:
            out[i + 1] = slots
    return out, mix


def default_mix():
    return {t: dict(vol=mixer.VOL_DEFAULT, bal=mixer.BAL_DEFAULT, level=mixer.LEVEL_DEFAULT)
            for t in range(1, NTRACKS + 1)}


def apply_mix(mix, specs):
    """--mix T1:VOL=127,BAL=64,LEVEL=100 (any subset, repeatable)."""
    for spec in specs:
        try:
            tn, rest = spec.split(":", 1)
            t = int(tn.upper().lstrip("T"))
            for kv in rest.split(","):
                k, v = kv.split("=")
                k = k.strip().lower()
                if k not in ("vol", "bal", "level"):
                    raise ValueError
                mix[t][k] = max(0, min(127, int(v)))
        except (ValueError, KeyError):
            die(f"--mix {spec!r}: want T<n>:VOL=<0..127>,BAL=<0..127>,LEVEL=<0..127>")


def apply_sets(tracks, sets):
    """--set T2:-VRB=100 (or T2:FX1:-VRB=100 when both slots carry the name)."""
    for spec in sets:
        try:
            lhs, val = spec.split("=")
            bits = lhs.split(":")
            t = int(bits[0].upper().lstrip("T"))
            fx = int(bits[1].upper().lstrip("FX")) if len(bits) == 3 else None
            name = bits[-1].upper()
        except ValueError:
            die(f"--set {spec!r}: want T<n>[:FX<1|2>]:<KNOB>=<0..127>")
        hit = False
        for s in tracks.get(t, []):
            if fx is not None and s.fx != fx:
                continue
            kmap = s.module.knob_map_all() if not s.module.is_stock else {
                p.name.decode().strip(): i for i, p in enumerate(s.module.params) if p.name}
            if name in kmap:
                s.values[kmap[name]] = int(val) & 0x7f
                hit = True
        if not hit:
            die(f"--set {spec!r}: no such knob on track {t}")


# ---- audio ----------------------------------------------------------------
def read_stem(path):
    """-> (L, R) float lists at SR. A mono file is the same list twice."""
    from render_reverb import read_wav_channels, resample
    chans, sr = read_wav_channels(path)
    L = resample(chans[0], sr, SR)
    R = resample(chans[1], sr, SR) if len(chans) > 1 else L
    return L, R


def write_wav(path, L, R):
    send_probe.write_wav(path, L, R)


# ---- the run --------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default="out/mainos_bus.bin", help="a BUILT image (make bus REMIX=...)")
    ap.add_argument("--remix", default=os.environ.get("REMIX", "bamsep26"),
                    help="which remix the image is (resolves ids to modules)")
    ap.add_argument("--tracks", default="", help="T1=D,T2=S,... (letter or module KEY; 'a+b' = FX1+FX2)")
    ap.add_argument("--project", help="project dir: take ids AND knobs from a part")
    ap.add_argument("--bank", type=int, default=1)
    ap.add_argument("--part", type=int, default=1)
    ap.add_argument("--set", action="append", default=[], help="T2:-VRB=100 knob override")
    ap.add_argument("--mix", action="append", default=[], help="T1:VOL=127,BAL=64,LEVEL=100 mixer override")
    ap.add_argument("--mixer", choices=("on", "off"), default="on",
                    help="the measured gain chain (AMP VOL/BAL pre-FX, LEVEL post-FX); off = the old unity harness")
    ap.add_argument("--stems", help="dir of T1.wav..T8.wav (a missing one is silence)")
    ap.add_argument("--stem", action="append", default=[], help="T3=file.wav")
    ap.add_argument("--seconds", type=float, help="length (default: longest stem)")
    ap.add_argument("--tail", type=float, default=2.0, help="seconds after the stems end")
    ap.add_argument("--amp", type=float, help="stem scale (default 1.0 with the mixer, 0.5 = -6 dBFS without)")
    ap.add_argument("--tempo", type=float, help="publish tempo24 / clocks as the ColdFire cave does")
    ap.add_argument("--skew", type=int, help="interleave the cores, core 0 N instructions ahead")
    ap.add_argument("--out", default="out/rig")
    ap.add_argument("--keep", action="store_true", help="keep the raw files")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--frames", type=int, default=FRAMES, help="samples per dsp_host block (16 = the firmware's frame, the default; 15 = the old harness)")
    ap.add_argument("--extra", default="", help="extra dsp_host arguments, e.g. '-dumpy 36000,360d3,file' (the bus scratch after the render)")
    a = ap.parse_args()

    image = pathlib.Path(a.image)
    if not image.is_file():
        die(f"{image} does not exist -- `make bus REMIX={a.remix}` first")
    outdir = pathlib.Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # the tracks
    mix = default_mix()
    if a.project:
        tracks, mix = part_tracks(a.project, a.bank, a.part, a.remix)
    elif a.tracks:
        tracks = parse_tracks(a.tracks, a.remix)
    else:
        die("give --tracks or --project")
    apply_sets(tracks, a.set)
    apply_mix(mix, a.mix)
    model = a.mixer == "on"
    if a.amp is None:
        a.amp = 1.0 if model else 0.5

    # both payloads
    mems = {}
    for core, tag in ((0, "A"), (1, "B")):
        mems[core] = send_probe.dump_mem(image, ROOT / f"out/dsp/mem_{a.remix}_{tag}.mem", tag)
    send_id = send_probe.SERVER_ID["S"]
    send_ep = {c: send_probe.entry_points(mems[c], send_id) for c in (0, 1)}

    # instances, in dispatch order: core 0 (tracks 5-8) then core 1 (1-4),
    # each track FX1 then FX2 on ONE audio buffer
    # An EMPTY FX2 slot is not empty on the unit: a fresh or unassigned track
    # dispatches to the fallback, SEND (id 0 aliases to it), which houskeeps
    # like any bus participant and costs its cycles. Model it, or a layout
    # with nothing on core 0's position 0 has no housekeeper at all and the
    # bus never rotates (found 7 Sep 2026: a delay-only render was silent).
    send_mod = registry.modules().get("SEND")
    r_ = registry.remix(a.remix)
    if send_mod is not None and "SEND" in r_.modules:
        for t in range(1, NTRACKS + 1):
            if not any(s.fx == 2 for s in tracks.get(t, [])):
                tracks.setdefault(t, []).append(Slot(send_mod, 2, defaults_of(send_mod)))
    inst = []            # dicts
    for t in [5, 6, 7, 8, 1, 2, 3, 4]:
        for s in tracks.get(t, []):
            core = CORE_OF[t]
            fid = s.module.menu.fx2_id
            ep = send_probe.entry_points(mems[core], fid)
            aliased = (s.module.key != "SEND") and ep == send_ep[core]
            if aliased:
                print(f"  T{t} FX{s.fx} {s.module.key}: not in payload {'AB'[core]} -- "
                      f"this core dispatches it to SEND (the alias), as the unit does")
            pos = POS_OF[t]
            inst.append(dict(track=t, fx=s.fx, key=s.module.key, core=core,
                             alloc=2 * pos + (s.fx - 1), r7=1 + 3 * pos + (s.fx - 1),
                             init=ep[0], proc=ep[1], values=s.values,
                             aliased=aliased, stock=s.module.is_stock))
    if not inst:
        die("no effect on any track")

    # stems
    stems = {}
    if a.stems:
        d = pathlib.Path(a.stems).expanduser()
        for t in range(1, NTRACKS + 1):
            for cand in (d / f"T{t}.wav", d / f"t{t}.wav", d / f"track{t}.wav"):
                if cand.is_file():
                    stems[t] = read_stem(cand)
                    break
    for spec in a.stem:
        tn, f = spec.split("=", 1)
        stems[int(tn.upper().lstrip("T"))] = read_stem(pathlib.Path(f).expanduser())
    longest = max((len(x[0]) for x in stems.values()), default=0)
    n_src = int(a.seconds * SR) if a.seconds else longest
    if n_src == 0:
        die("no stems and no --seconds: nothing to render")
    FR = a.frames
    pad = send_probe.WARMUP_BLOCKS * FR            # the engines stay dry for 256 CALLS, so the
                                                   # pad is in blocks of THIS length (at 16 frames
                                                   # the old 260 x 15 left 196 dry samples in)
    total = pad + n_src + int(a.tail * SR)
    blocks = -(-total // FR)
    n = blocks * FR

    # what the chain is fed: the stem at --amp, and with the model on, through
    # the DSP's AMP stage (VOL^2 and the balance) -- interleaved L,R (-stereo)
    def pre_gains(t):
        if not model:
            return a.amp, a.amp
        gl, gr = mixer.bal_gains(mix[t]["bal"])
        g = a.amp * mixer.vol_gain(mix[t]["vol"])
        return g * gl, g * gr
    tag = os.getpid()
    raws = {}
    for t, (xl, xr) in stems.items():
        p = ROOT / f"out/dsp/_rig_in_T{t}_{tag}.raw"
        gl, gr = pre_gains(t)
        m = min(len(xl), n_src)
        with open(p, "wb") as f:
            for i in range(n):
                j = i - pad
                if 0 <= j < m:
                    l_, r_ = gl * xl[j], gr * xr[j]
                else:
                    l_ = r_ = 0.0
                f.write(struct.pack("<ii", max(-8388608, min(8388607, int(l_ * 8388607))),
                                    max(-8388608, min(8388607, int(r_ * 8388607)))))
        raws[t] = p
    silent = ROOT / f"out/dsp/_rig_silence_{tag}.raw"
    silent.write_bytes(b"\0" * (8 * n))

    out = ROOT / f"out/dsp/_rig_out_{tag}.raw"
    cmd = [str(send_probe.HOST), "-mem", str(mems[0]), "-memB", str(mems[1]),
           "-init", ",".join(f"{i['init']:x}" for i in inst),
           "-proc", ",".join(f"{i['proc']:x}" for i in inst),
           "-inst", str(len(inst)),
           "-core", ",".join(str(i["core"]) for i in inst),
           "-alloc", ",".join(str(i["alloc"]) for i in inst),
           "-r7", ",".join(str(i["r7"]) for i in inst),
           "-audioidx", ",".join(str(i["track"] - 1) for i in inst),
           "-audio", f"{AUDIO_BASE:x}",
           "-in", ",".join(str(raws.get(i["track"], silent)) for i in inst),
           "-frames", str(FR), "-blocks", str(blocks), "-stereo",
           "-out", str(out), "-meter", str(outdir / "meter.txt")]
    for i in inst:
        cmd += ["-params", ",".join(map(str, i["values"]))]
    if a.tempo:
        cmd += ["-tempo", str(a.tempo)]
    if a.skew is not None:
        cmd += ["-skew", str(a.skew)]
    if a.extra:
        cmd += a.extra.split()
    print("tracks:")
    for i in inst:
        print(f"  T{i['track']} FX{i['fx']} {i['key']:14s} core {i['core']} "
              f"alloc {i['alloc']} r7 {i['r7']} init P:0x{i['init']:05x} "
              f"params {' '.join(map(str, i['values']))}"
              f"{'   <- SEND alias' if i['aliased'] else ''}")
    if model:
        def desc(t, m):
            db = lambda g: 20 * math.log10(g) if g > 0 else -200.0
            bal = "" if m["bal"] == 64 else f" BAL {m['bal']}"
            return (f"T{t} VOL {m['vol']} ({db(mixer.vol_gain(m['vol'])):+.1f} dB){bal}"
                    f" LVL {m['level']} ({db(mixer.level_gain(m['level'])):+.1f})")
        print("mixer (the measured chain, tools/harness/mixer.py): "
              + "  ".join(desc(t, m) for t, m in sorted(mix.items()) if t in stems or t in tracks))
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if a.verbose:
        print(r.stdout)
    if r.returncode != 0:
        die(f"dsp_host failed:\n{r.stdout[-3000:]}{r.stderr[-2000:]}")
    for line in r.stdout.splitlines():
        if "meter:" in line or "HANG" in line or "!!" in line:
            print(line)

    # per-track outputs: the LAST instance on a track's buffer captured it
    last = {}
    for k, i in enumerate(inst):
        last[i["track"]] = k
    mixL = [0.0] * (n - pad)
    mixR = [0.0] * (n - pad)
    for t in range(1, NTRACKS + 1):
        if t in last:
            k = last[t]
            p = out if k == 0 else pathlib.Path(f"{out}.i{k}")
            arr = array.array("i"); arr.frombytes(p.read_bytes())
            L, R = list(arr[0::2])[pad:], list(arr[1::2])[pad:]
        elif t in stems:                       # no instance at all: the stem passes through
            xl, xr = stems[t]; gl, gr = pre_gains(t); m = min(len(xl), n_src)
            L = [int(gl * (xl[j] if j < m else 0.0) * 8388607) for j in range(n - pad)]
            R = [int(gr * (xr[j] if j < m else 0.0) * 8388607) for j in range(n - pad)]
        else:
            continue
        write_wav(outdir / f"T{t}.wav", L, R)
        peak = max((abs(v) for v in L + R), default=0)
        print(f"  T{t}.wav  peak {20 * math.log10(max(peak, 1) / 8388608):6.1f} dBFS")
        lv = mixer.level_gain(mix[t]["level"]) if model else 1.0
        for j in range(len(L)):
            mixL[j] += lv * L[j]; mixR[j] += lv * R[j]
    if not model:
        mixL = [v * 0.5 for v in mixL]; mixR = [v * 0.5 for v in mixR]
    peak = max((abs(v) for v in mixL + mixR), default=0)
    clip = sum(1 for v in mixL + mixR if abs(v) > 8388607)
    mixL = [max(-8388608, min(8388607, int(v))) for v in mixL]
    mixR = [max(-8388608, min(8388607, int(v))) for v in mixR]
    write_wav(outdir / "mix.wav", mixL, mixR)
    print(f"  mix.wav  peak {20 * math.log10(max(peak, 1) / 8388608):6.1f} dBFS"
          f"{f'  !! {clip} clipped samples' if clip else ''}   "
          + ("(the main out: each track through LEVEL, summed)" if model else "(unity sum, -6 dB; --mixer off)"))
    print(f"-> {outdir}")
    if not a.keep:
        for p in [out, silent, *raws.values()] + [pathlib.Path(f"{out}.i{k}") for k in range(1, len(inst))]:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
