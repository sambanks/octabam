#!/usr/bin/env python3
"""VOCODER render gates, against the float reference (modules/vocoder/vocoder_ref.py).

Renders the module straight through dsp_host (the render-gate shape: the id and the
slots come from the manifest, and the entry points are checked against SEND's so an
absent module cannot pass as a passthrough). The modulator is synthetic and
deterministic: a 120 Hz glottal pulse train through three formant resonators, the
vowel changing every 200 ms, with noise bursts for consonants, so no audio file is
needed.

Gates:
  the law       -> INT at C3 and EXT with a chord carrier: the output matches the float
                   reference within -50 dB (error RMS re signal RMS) and 0.1 dB in level
  silence       -> silence in gives silence out, bit-exact, with CONS and DRY up
  pauses        -> 0.3 s after the voice stops the output is below -100 dBFS (the
                   48-bit envelopes decay; 24-bit ones stuck at -90 and leaked carrier)
  bands         -> a sine at a band's centre on L, noise as the EXT carrier: the output's
                   power at that band is 15 dB or more above its neighbours'
  NOTE          -> the INT carrier's pitch is NOTE's within 0.05 % (C1, C3, C6)
  NOTE clamp    -> a saved NOTE byte past C6 plays C6
  0.2 controls  -> GEND at both ends, WHSP 64 and 127, a p-locked melody with two BEND
                   moves under GLDE 80 ms, BEND, GEND and WHSP swept by the fader one value a
                   call, and scene jumps of GEND, WHSP, DRY and CONS up and down each match the
                   reference (its pitch, GEND, noise and de-zipper arithmetic bit-exact), each
                   jump's first 20 ms too (down: a negative multiplier, the mpysu trap); BEND -64 and +63 land on C2 and +11.8 semitones
  SCAL KEY RANG -> page 2's selectors: for every scale and key, NOTE swept up and down its
                   range gives the reference's phase increment on every call, bit for bit
                   (the reference's pitches are checked against a table of notes in
                   vocoder_ref.py's self-check); RANG 0, 1 and 2 at BEND -64, 0 and +63 on C1,
                   C3 and C6 settle on the right pitch (C0 the floor); measured pitches by FFT
                   for a few; KEY does nothing with SCAL CHRO; value 0 of all three renders the
                   build before the selectors bit for bit (nine renders' SHA-256 recorded from it;
                   with VC_BASE_MEM, a .mem of that build, compared directly as well)
  guard         -> dsp_host -guard: no write over a loaded module
  two per core  -> runs at r7 0x6500 and 0x6b00 (FX2 of T2 T4 T6 T8) and is an exact dry
                   pass at every other FX2 and FX1 state block; position 3's output is
                   position 1's bit for bit
  every knob    -> renders at both ends without dsp_host dying

    python3 tools/verify/verify_vocoder.py
"""
import importlib.util, math, pathlib, struct, subprocess, sys, tempfile

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe  # dispatch-table entry resolution
from remix import registry
from remix.schema import R7_ALLOC

ROOT = pathlib.Path(__file__).resolve().parents[2]
MOD = registry.by_name("vocoder")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES = 15
TMP = pathlib.Path(tempfile.mkdtemp(prefix="vcgate_"))

_spec = importlib.util.spec_from_file_location("vocoder_ref", ROOT / "modules/vocoder/vocoder_ref.py")
REF = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(REF)
FS = REF.FS

# The image of the `vocoder` remix, not the audition's: VOCODER claims its allocator slot
# (GEND's coefficients), and the audition's scratch remix carries SEND, a bus participant
# the ledger will not seat beside a slot user (verify_wave, removed with the DSP WAVE, built the same way: `git show 755a02ac:tools/verify/verify_wave.py`).
import os
pathlib.Path(MEM).unlink(missing_ok=True)
subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, check=True, capture_output=True,
               env={**os.environ, "REMIX": "vocoder", "XBUS": "1", "SPEC": "1"})
send_probe.dump_mem(ROOT / "out/mainos_bus.bin", pathlib.Path(MEM), "A")
if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM}: the vocoder remix did not build")
init, proc = send_probe.entry_points(MEM, FXID)
if (init, proc) == send_probe.entry_points(MEM, SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{FXID:02x} resolves to SEND's entry points -- {MOD.name} is NOT in this dump")
print(f"entries from dispatch tables: init=P:0x{init:04x} proc=P:0x{proc:04x}")

DEFAULTS = [(p.default or 0) for p in MOD.params]


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


def q23f(x):
    """What dsp_host hands back for an untouched frame: the Q23 input as floats."""
    return np.asarray(q23(x), float) / (1 << 23)


def q23(x):
    return [max(-(1 << 23), min((1 << 23) - 1, int(round(s * (1 << 23))))) for s in x]


ALLOC = R7_ALLOC                  # r7 (0x6000 + 0x100 n) -> its base-table entry


def render(L, R, r7=5, plocks=(), guard=False, frames=None, track=None, mem=None, entries=None, **kw):
    """L, R: float arrays. Returns (L, R) floats from the module. r7 = dsp_host's state block,
    0x6000 + 0x100 r7: 5 (0x6500) is a core's second FX2 slot, VOCODER's home; it runs at 5 and 11
    only (the built-in two-per-core limit, off a core's first track). plocks: (call, {knob: value}) pairs, applied from
    that call on, through dsp_host's -paramfile (a p-lock, or a fader move one call at a time)."""
    fr = frames or FRAMES
    n = len(L) - len(L) % fr
    li, ri = q23(L[:n]), q23(R[:n])
    fin, fout = TMP / "vc_in.raw", TMP / "vc_out.raw"
    fin.write_bytes(b"".join(struct.pack("<ii", a, b) for a, b in zip(li, ri)))
    ei, ep = entries or (init, proc)
    cmd = [HOST, "-mem", mem or MEM, "-init", f"{ei:x}", "-proc", f"{ep:x}",
           "-inst", "1", "-r7", str(r7), "-alloc", str(ALLOC[r7]), "-inmask", "1", "-stereo",
           *(["-guard"] if guard else []),
           *(["-track", ",".join(f"{t:x}" for t in track), "-trackout", str(TMP / "vc_track.txt")] if track else []),
           "-frames", str(fr), "-blocks", str(n // fr),
           "-in", str(fin), "-out", str(fout),
           "-params", ",".join(str(x) for x in params(**kw))]
    if plocks:
        cur, rows, merged = dict(kw), [], {}
        for blk, ch in sorted(plocks, key=lambda bc: bc[0]):    # one row per call, in order
            merged.setdefault(blk, {}).update(ch)
        for blk in sorted(merged):
            cur.update(merged[blk])
            rows.append(f"{blk}," + ",".join(str(x) for x in params(**cur)))
        pf = TMP / "vc_plocks.txt"
        pf.write_text("\n".join(rows) + "\n")
        cmd += ["-paramfile", str(pf)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    render.guard_out = r.stdout + r.stderr
    w = np.frombuffer(fout.read_bytes(), dtype="<i4").astype(float) / (1 << 23)
    return w[0::2][:n], w[1::2][:n]


FAILS = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def db(x):
    return 20 * math.log10(max(float(np.sqrt(np.mean(np.asarray(x) ** 2))), 1e-30))


def speech_like(seconds=2.0, seed=5):
    """A 120 Hz glottal pulse train through three formants, vowels every 200 ms, noise bursts."""
    def lfilter(b, a, x):                            # a two-pole resonator (no scipy here)
        y = np.zeros(len(x)); y1 = y2 = 0.0
        for i, v in enumerate(x):
            y0 = b[0] * v - a[1] * y1 - a[2] * y2
            y[i] = y0; y2, y1 = y1, y0
        return y
    n = int(seconds * FS); rng = np.random.default_rng(seed)
    src = np.zeros(n); src[::int(FS / 120)] = 1.0
    vowels = ((730, 1090, 2440), (270, 2290, 3010), (300, 870, 2240), (530, 1840, 2480), (570, 840, 2410))
    out = np.zeros(n); seg = int(0.2 * FS)
    for i in range(0, n, seg):
        x = src[i:i + seg].copy()
        if (i // seg) % 3 == 2:                      # a consonant: noise
            x = rng.uniform(-0.3, 0.3, len(x))
        y = np.zeros_like(x)
        for f in vowels[(i // seg) % len(vowels)]:
            r = math.exp(-math.pi * 80 / FS); th = 2 * math.pi * f / FS
            y += lfilter([1 - r], [1, -2 * r * math.cos(th), r * r], x)
        out[i:i + seg] = y * np.hanning(len(y)) ** 0.25
    return out / np.max(np.abs(out)) * 0.5


v = speech_like()
z = np.zeros_like(v)

# ---- the law ---------------------------------------------------------------------------
nb = len(v) // FRAMES
mel = [24, 24, 31, 29, 27, 27, 24, 22]
MEL = [(j * (nb // 8), {"NOTE": mel[j]}) for j in range(8)] + [(nb // 2, {"BEND": 100}), (3 * nb // 4, {"BEND": 30})]


def sweep(knob, lo, hi, start=0, calls=None):
    """A fader move: the knob from lo to hi, one value per call (a crossfader or an LFO)."""
    calls = calls or nb - start
    return [(start + i, {knob: int(round(lo + (hi - lo) * i / max(1, calls - 1)))}) for i in range(calls)]


JUMP, DOWN = nb // 3, 2 * nb // 3   # scene jumps: four page-1 knobs change on one call, up then down
SCENE = [(JUMP, {"GEND": 127, "WHSP": 127, "DRY": 127, "CONS": 127}),
         (DOWN, {"GEND": 0, "WHSP": 0, "DRY": 0, "CONS": 0})]


def per_call(plocks, knob, default):
    """The knob's value for every call, as the paramfile applies the locks."""
    out = np.full(nb, default)
    for blk, ch in plocks:
        if knob in ch:
            out[blk:] = ch[knob]
    return out


CHORD = sum(REF._saw(len(v), REF.note_inc(s), REF.note_idt(s), 0) for s in (24, 27, 31)) / 3
for label, L, R, kw, pl in (("INT, C3", v, v, dict(MODE=0, NOTE=24), ()),
                            ("EXT, a chord carrier on R", v, CHORD, dict(MODE=1), ()),
                            ("GEND 0 (x0.84 formants, male)", v, v, dict(GEND=0), ()),
                            ("GEND 127 (x1.41 formants, female)", v, v, dict(GEND=127), ()),
                            ("WHSP 64", v, v, dict(WHSP=64), ()),
                            ("WHSP 127 (noise)", v, v, dict(WHSP=127), ()),
                            ("a NOTE melody and two BEND moves, GLDE 80 ms", v, v, dict(GLDE=2), MEL),
                            ("the melody in D PMAJ, BEND over 24ST, GLDE 80 ms", v, v, dict(GLDE=2, SCAL=7, KEY=2, RANG=2), MEL),
                            ("BEND swept -64 to +63 by the fader", v, v, dict(), sweep("BEND", 0, 127)),
                            ("GEND swept -64 to +63 by the fader", v, v, dict(), sweep("GEND", 0, 127)),
                            ("WHSP swept 0 to 127 by the fader", v, v, dict(), sweep("WHSP", 0, 127)),
                            ("scene jumps up and down (GEND, WHSP, DRY, CONS at once)", v, v, dict(GEND=0, WHSP=0, DRY=0, CONS=0), SCENE)):
    oL, oR = render(L, R, plocks=pl, **kw)
    d = {k: DEFAULTS[K[k]] for k in ("NOTE", "BEND", "GEND", "WHSP", "GLDE", "CONS", "DRY", "SCAL", "KEY", "RANG")}
    d.update(kw)
    knobs = {k: (per_call(pl, k, d[k]) if any(k in ch for _, ch in pl) else d[k]) for k in d}
    ref = REF.vocode(L[:len(oL)], R[:len(oL)], mode=kw.get("MODE", 0), note=knobs["NOTE"], bend=knobs["BEND"],
                     gend=knobs["GEND"], whsp=knobs["WHSP"], glide=knobs["GLDE"],
                     cons=knobs["CONS"], dry=knobs["DRY"], frames=FRAMES,
                     scal=knobs["SCAL"], key=knobs["KEY"], rang=knobs["RANG"])
    err = db(oL - ref) - db(ref)
    lv = db(oL) - db(ref)
    check(f"the law, {label}: within {err:.1f} dB of the float reference, level {lv:+.3f} dB (output {db(oL):.1f} dBFS RMS)",
          err < -50 and abs(lv) < 0.1 and np.array_equal(oL, oR))
    if pl is SCENE:               # the 20 ms after each jump, where the de-zipper is all there is
        for at, way in ((JUMP, "up"), (DOWN, "down: T - s < 0, the multiply's sign")):
            w = slice(at * FRAMES, at * FRAMES + int(0.02 * FS))
            ew = db(oL[w] - ref[w]) - db(ref[w])
            check(f"the scene jump's first 20 ms, {way}: within {ew:.1f} dB of the reference's 8 ms de-zipper", ew < -50)

# ---- silence and pauses ---------------------------------------------------------------------
oL, _ = render(z[:44100], z[:44100], CONS=127, DRY=127)
check("silence in, silence out (CONS and DRY up)", not np.any(oL))
vp = np.concatenate([v[:int(FS)], np.zeros(int(0.6 * FS))])
oL, _ = render(vp, vp)
tail = db(oL[-int(0.3 * FS):])
check(f"0.3 s into a pause the output is {tail:.1f} dBFS", tail < -100)

# ---- bands ------------------------------------------------------------------------------------
rng = np.random.default_rng(9)
noise = rng.uniform(-0.9, 0.9, int(FS))
t = np.arange(int(FS)) / FS
worst = 99.0
for k in (1, 4, 7):
    fc = REF.CENTRES[k]
    oL, _ = render(0.5 * np.sin(2 * np.pi * fc * t), noise, MODE=1, CONS=0)
    X = np.abs(np.fft.rfft(oL[4410:])) ** 2; fr = np.fft.rfftfreq(len(oL) - 4410, 1 / FS)
    p = lambda f: X[(fr > f / 1.1) & (fr < f * 1.1)].sum()
    sel = 10 * math.log10(p(fc) / max(p(REF.CENTRES[k - 1]), p(REF.CENTRES[k + 1])))
    worst = min(worst, sel)
check(f"bands: a centre sine keeps its band at least {worst:.1f} dB above the neighbours", worst > 15)

# ---- NOTE ---------------------------------------------------------------------------------------
noise3 = np.random.default_rng(11).uniform(-0.9, 0.9, int(3 * FS))
for step, bend in ((0, 64), (24, 64), (60, 64), (24, 0), (24, 127)):
    oL, _ = render(noise3, noise3, MODE=0, NOTE=step, BEND=bend, CONS=0)
    x = oL[4410:]; n = len(x)
    X = np.abs(np.fft.rfft(x * np.hanning(n), 4 * n)); fr = np.fft.rfftfreq(4 * n, 1 / FS)
    f0 = 440.0 * 2 ** ((REF.NOTE_LO + step - 69 + 24 * (bend - 64) / 128) / 12)
    h = max(1, math.ceil(400 / f0))                   # a harmonic inside the bands
    m = np.nonzero((fr > h * f0 * 0.99) & (fr < h * f0 * 1.01))[0]
    i = m[np.argmax(X[m])]
    a_, b_, c_ = np.log(X[i - 1:i + 2])               # parabolic interpolation of the peak
    fm = (fr[i] + 0.5 * (a_ - c_) / (a_ - 2 * b_ + c_) * (fr[1] - fr[0])) / h
    check(f"NOTE {REF.note_name(step)} BEND {bend - 64:+d}: {fm:.3f} Hz (want {f0:.3f}; harmonic {h})", abs(fm / f0 - 1) < 5e-4)
a, _ = render(noise[:22050], noise[:22050], NOTE=99)
b, _ = render(noise[:22050], noise[:22050], NOTE=60)
check("a NOTE byte past C6 plays C6", np.array_equal(a, b))

# ---- two per core, built in: runs at r7 0x6500 and 0x6b00 only, dry elsewhere -------------------
# Three on a core overran the MKII. The FX2 blocks are 0x6200 + 0x300 pos and the FX1 blocks
# 0x6100 + 0x300 pos (measured under the port, modules/send/README.md); dsp_host's -r7 n is
# 0x6000 + 0x100 n. A dry pass writes nothing, so its output is its input bit for bit.
src = noise[:22050]
runs, dry = [], []
for r7 in (5, 8, 2, 11, 1, 4, 7, 10):
    L, R = render(src, src, r7=r7, CONS=127, DRY=0)
    (dry if np.array_equal(L, q23f(src)) and np.array_equal(R, q23f(src)) else runs).append(r7)
check("runs at FX2 positions 1 and 3 only (r7 0x6500, 0x6b00): T2 T4 T6 T8",
      runs == [5, 11], f"(runs at {[hex(0x6000 + 0x100 * r) for r in runs]})")
check("an exact dry pass at FX2 positions 0 and 2 (T1 T3 T5 T7) and every FX1 slot",
      dry == [8, 2, 1, 4, 7, 10], f"(dry at {[hex(0x6000 + 0x100 * r) for r in dry]})")
# position 3 keeps GEND's coefficients in another Y slot (the shared window); the law is the same
a1 = render(v[:22050], v[:22050], GEND=0, WHSP=64, BEND=100)
a3 = render(v[:22050], v[:22050], r7=11, GEND=0, WHSP=64, BEND=100)
check("position 3 (r7 0x6b00) renders position 1's output bit for bit (GEND off the centre)",
      np.array_equal(a1[0], a3[0]) and np.array_equal(a1[1], a3[1]))

# ---- page 2's selectors: SCAL (slot 7), RANG (slot 9), KEY (slot 10) -----------------------------
def tracked_incs(plocks, nbk, frames=FRAMES, **kw):
    """Render nbk calls of silence with these locks; the DSP's phase increment (r7+$0c) per call."""
    zz = np.zeros(nbk * frames)
    render(zz, zz, plocks=plocks, frames=frames, track=(0x0c,), **kw)
    rows = [ln.split() for ln in (TMP / "vc_track.txt").read_text().splitlines() if ln.strip()]
    return np.array([int(r[1]) for r in rows])


def knob_calls(plocks, nbk, knob, default):
    out = np.full(nbk, default)
    for blk, ch in sorted(plocks, key=lambda bc: bc[0]):
        if knob in ch:
            out[blk:] = ch[knob]
    return out


# every scale in every key: NOTE up and down its whole range, three calls a step, GLDE OFF
HOLD = 3
seq, blk = [], 0
for si in range(len(REF.SCALES)):
    for key in range(12):
        for n in list(range(61)) + list(range(60, -1, -1)):
            seq.append((blk, {"SCAL": si, "KEY": key, "NOTE": n})); blk += HOLD
nsk = blk
got = tracked_incs(seq, nsk)
want = REF.incs_02(nsk, *(knob_calls(seq, nsk, k, DEFAULTS[K[k]]) for k in ("NOTE", "BEND", "GLDE")),
                   frames=FRAMES, **{k.lower(): knob_calls(seq, nsk, k, 0) for k in ("SCAL", "KEY", "RANG")})
bad = np.nonzero(got[:nsk] != want)[0]
check(f"SCAL x KEY (10 x 12), NOTE swept C1-C6-C1: the phase increment is the reference's on all {nsk} calls",
      len(got) >= nsk and not len(bad), f"(first mismatch at call {bad[0]})" if len(bad) else "")
# and where each held note settles: the scale note at or below, in Hz against the table
HOLDS = 220                       # 75 ms a note: GLDE OFF's 8 ms has settled to 0.01 %
cases = [(si, key, n) for si, key in ((1, 0), (2, 9), (6, 4), (7, 2), (8, 9), (9, 7), (3, 5)) for n in range(0, 61, 7)]
seq = [(i * HOLDS, {"SCAL": si, "KEY": key, "NOTE": n}) for i, (si, key, n) in enumerate(cases)]
got = tracked_incs(seq, len(cases) * HOLDS)
worst = 0.0
for i, (si, key, n) in enumerate(cases):
    m = n
    while (m - key) % 12 not in REF.SCALES[si][1]:
        m -= 1
    want_hz = 440.0 * 2 ** ((REF.NOTE_LO + m - 69) / 12)
    worst = max(worst, abs(got[(i + 1) * HOLDS - 1] * FS / (1 << 24) / want_hz - 1))
check(f"{len(cases)} held notes in seven scales and keys settle on the scale note at or below NOTE, "
      f"within {worst * 100:.3f} % of the table", worst < 5e-4)
# RANG: BEND's reach, at both ends and the centre, on C1, C3 and C6; under C0 it is held at C0
cases = [(r, n, b) for r in range(3) for n in (0, 24, 60) for b in (0, 64, 127)]
seq = [(i * HOLDS, {"RANG": r, "NOTE": n, "BEND": b}) for i, (r, n, b) in enumerate(cases)]
nbk = len(cases) * HOLDS
got = tracked_incs(seq, nbk)
want = REF.incs_02(nbk, *(knob_calls(seq, nbk, k, DEFAULTS[K[k]]) for k in ("NOTE", "BEND", "GLDE")),
                   frames=FRAMES, rang=knob_calls(seq, nbk, "RANG", 0))
worst = 0.0
for i, (r, n, b) in enumerate(cases):
    semis = REF.NOTE_LO + n - 12 + REF.RANGE_ST[r] * (b - 64) / 64
    want_hz = REF.C0_HZ * 2 ** (max(semis, 0) / 12)
    worst = max(worst, abs(got[(i + 1) * HOLDS - 1] * FS / (1 << 24) / want_hz - 1))
check(f"RANG 12ST 6ST 24ST x NOTE C1 C3 C6 x BEND -64 0 +63: settles within {worst * 100:.3f} % of the table "
      f"(C1 - 24 held at C0), every call the reference's", worst < 5e-4 and np.array_equal(got[:nbk], want))


def measured_f0(oL, f0):
    x = oL[4410:]; n = len(x)
    X = np.abs(np.fft.rfft(x * np.hanning(n), 4 * n)); fr = np.fft.rfftfreq(4 * n, 1 / FS)
    h = max(1, math.ceil(400 / f0))
    m = np.nonzero((fr > h * f0 * 0.99) & (fr < h * f0 * 1.01))[0]
    i = m[np.argmax(X[m])]
    a_, b_, c_ = np.log(X[i - 1:i + 2])
    return (fr[i] + 0.5 * (a_ - c_) / (a_ - 2 * b_ + c_) * (fr[1] - fr[0])) / h, h


for label, kw, semis in (("C#3 in C MAJ plays C3", dict(NOTE=25, SCAL=1), 36),
                         ("C3 in E PMIN plays B2", dict(NOTE=24, SCAL=8, KEY=4), 35),
                         ("C3, RANG 24ST, BEND +63 plays 23.6 semitones up", dict(NOTE=24, RANG=2, BEND=127), 36 + 24 * 63 / 64),
                         ("C3, RANG 6ST, BEND -64 plays F#2", dict(NOTE=24, RANG=1, BEND=0), 30),
                         ("C1, RANG 24ST, BEND -64 is held at C0", dict(NOTE=0, RANG=2, BEND=0), 0)):
    oL, _ = render(noise3, noise3, MODE=0, CONS=0, **kw)
    f0 = REF.C0_HZ * 2 ** (semis / 12)
    fm, h = measured_f0(oL, f0)
    check(f"{label}: {fm:.3f} Hz (want {f0:.3f}; harmonic {h})", abs(fm / f0 - 1) < 5e-4)
a = render(v[:22050], v[:22050], KEY=5, BEND=100, GLDE=2)
b = render(v[:22050], v[:22050], KEY=0, BEND=100, GLDE=2)
check("KEY does nothing with SCAL CHRO (KEY F renders KEY C bit for bit)", np.array_equal(a[0], b[0]))

# value 0 of SCAL, KEY and RANG is the build before them, bit for bit: each render's SHA-256
# against the one the build before the selectors gave (branch vocoder-02-even at 330c6da6,
# 18 Oct 2026); with VC_BASE_MEM (a .mem of that build) the renders are compared directly too
BASE = os.environ.get("VC_BASE_MEM")
BASE_RENDERS = {
    'defaults': "2dff4b27d22620c4e621bebe4ef19bdb21066cc4a2d132365294c873d3b6ab7d",
    'EXT, a chord carrier': "07de9944195cd230cfec6625de6888858d0b02a4aa299ff0794ee84b2f1181ab",
    'GEND 0, WHSP 64, BEND +36': "7d01b2a5683c5803b141fdcce269a4bff65cc77cbfafd3dea3bb7e8d93b7e7d4",
    'the melody under GLDE 80 ms': "abe1c508113b9906657902658fa51f176d070af0463dbd54b6e7a856361d86a4",
    'BEND swept': "4ea12b1a0502ccde3c4e39b4616b8c989c5b752c84cbc364951ed44032b26e7c",
    'the scene jumps': "7d60505427384d566d50d24ff5e66af447f4f33a52f417a6f3a77c0168b2f0ca",
    'NOTE swept C1 to C6, BEND -64': "0304cae0caf7e08f60a4d728113ca7b3360340b0f95ae1ac8f01f693fe0c1c90",
    '1-sample calls at C6, BEND +63': "16ad2770996d8462cb5d8a5c0d4a17f2a02765c2692999fcc3cac412bc7fc739",
    'position 3, GEND 127': "556a0e91b699bac2a9a9853ad00c90982a447326fc5e90adb6a6ea517417289a",
}
cases = [("defaults", v, v, dict(), (), None), ("EXT, a chord carrier", v, CHORD, dict(MODE=1), (), None),
         ("GEND 0, WHSP 64, BEND +36", v, v, dict(GEND=0, WHSP=64, BEND=100), (), None),
         ("the melody under GLDE 80 ms", v, v, dict(GLDE=2), MEL, None),
         ("BEND swept", v, v, dict(), sweep("BEND", 0, 127), None),
         ("the scene jumps", v, v, dict(GEND=0, WHSP=0, DRY=0, CONS=0), SCENE, None),
         ("NOTE swept C1 to C6, BEND -64", v, v, dict(BEND=0), [(i * (nb // 61), {"NOTE": i}) for i in range(61)], None),
         ("1-sample calls at C6, BEND +63", v[:22050], v[:22050], dict(NOTE=60, BEND=127), (), 1),
         ("position 3, GEND 127", v, v, dict(GEND=127, BEND=20), (), None)]
import hashlib
same, direct, digests = 0, 0, {}
be = send_probe.entry_points(BASE, FXID) if BASE else None
for label, L, R, kw, pl, fr in cases:
    r7 = 11 if label.startswith("position 3") else 5
    n_ = render(L, R, r7=r7, plocks=pl, frames=fr, **kw)
    h = hashlib.sha256(np.concatenate(n_).tobytes()).hexdigest()
    digests[label] = h
    same += h == BASE_RENDERS[label]
    if BASE:
        o_ = render(L, R, r7=r7, plocks=pl, frames=fr, mem=BASE, entries=be, **kw)
        direct += np.array_equal(n_[0], o_[0]) and np.array_equal(n_[1], o_[1])
        digests[label] = hashlib.sha256(np.concatenate(o_).tobytes()).hexdigest()   # the base build's
if os.environ.get("VC_PRINT_DIGESTS"):
    print("BASE_RENDERS = " + repr(digests))
check(f"SCAL CHRO, KEY C, RANG 12ST (value 0): {same} of {len(cases)} renders hash as the build before the selectors"
      + (f"; against that build's .mem directly, {direct} of {len(cases)} bit for bit" if BASE else ""),
      same == len(cases) and (not BASE or direct == len(cases)))

# ---- its writes: the state block and its 20-word Y slot, nothing over a loaded module ----------
render(v[:22050], v[:22050], guard=True, GEND=0, WHSP=127, BEND=127)
g5 = render.guard_out
render(v[:22050], v[:22050], r7=11, guard=True, GEND=0, WHSP=127, BEND=127)    # position 3: its slot in the shared window
render.guard_out = g5 + render.guard_out
g = render.guard_out
check("no write over a loaded module, at position 1 and at position 3 (its Y slot in the shared window)", g.count("guard clean") == 2,
      next((ln.strip() for ln in reversed(g.splitlines()) if "guard" in ln), ""))

# ---- 1-sample calls (T1's first piece of every frame): the per-call work skips them when the
# call before did it, never twice in a row; a run of them must still play the right pitch
for step, bend in ((24, 64), (24, 127)):
    oL, _ = render(noise3[:int(FS)], noise3[:int(FS)], frames=1, MODE=0, NOTE=step, BEND=bend, CONS=0)
    x = oL[4410:]; n = len(x)
    X = np.abs(np.fft.rfft(x * np.hanning(n), 4 * n)); fr = np.fft.rfftfreq(4 * n, 1 / FS)
    f0 = 440.0 * 2 ** ((REF.NOTE_LO + step - 69 + 24 * (bend - 64) / 128) / 12)
    h = max(1, math.ceil(400 / f0))
    m = np.nonzero((fr > h * f0 * 0.99) & (fr < h * f0 * 1.01))[0]
    i = m[np.argmax(X[m])]
    a_, b_, c_ = np.log(X[i - 1:i + 2])
    fm = (fr[i] + 0.5 * (a_ - c_) / (a_ - 2 * b_ + c_) * (fr[1] - fr[0])) / h
    check(f"1-sample calls, NOTE C3 BEND {bend - 64:+d}: {fm:.3f} Hz (want {f0:.3f})", abs(fm / f0 - 1) < 5e-4)

# ---- every knob at both ends ---------------------------------------------------------------------
for name, hi in (("NOTE", 60), ("BEND", 127), ("GEND", 127), ("WHSP", 127), ("CONS", 127), ("DRY", 127),
                 ("MODE", 1), ("GLDE", 4), ("SCAL", 9), ("RANG", 2), ("KEY", 11)):
    for val in (0, hi):
        render(v[:22050], v[:22050], **{name: val})
check("every knob at both ends renders", True)

if FAILS:
    sys.exit(f"verify_vocoder: {len(FAILS)} gate(s) failed")
print("verify_vocoder: OK")
