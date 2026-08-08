#!/usr/bin/env python3
"""
Synthesise test-audio files for reverb voicing — no external dependencies.
Output lands in out/test_audio/ (already gitignored via out/).

Usage:
    python3 scripts/make_test_audio.py          # build everything
    python3 scripts/make_test_audio.py --list   # list what would be built
    python3 scripts/make_test_audio.py kick     # build just one file

Files produced (all 44.1 kHz mono 16-bit WAV):

    kick        Short 808-style kick — tests low-end density and punch
    snare       Noise burst + tone body — tests mid-range diffusion
    hat         Very short filtered noise — tests high-frequency tail
    clap        Layered noise transients — tests complex-attack smearing
    stab        Sharp minor-9th chord stab — tests pitched-material bloom
    pad         Sustained major-7th pad — tests tail on held material
    bass        Sustained sub-bass note — tests low-end tail clarity
    melody      Eight-bar melodic phrase — the most musical audition
    loop        Drum groove + stab hits — realistic usage
    click       Single-sample impulse — measures the pure IR
"""

import argparse
import math
import os
import pathlib
import random
import struct
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT  = ROOT / "out" / "test_audio"
SR   = 44100

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _freq(n):
    """MIDI note n to Hz (A4=69=440)."""
    return 440.0 * (2.0 ** ((n - 69) / 12.0))

def _db(a):
    return 10.0 ** (a / 20.0)

def write_wav(path, samples, sr=SR):
    """Write a mono 16-bit WAV."""
    os.makedirs(path.parent, exist_ok=True)
    peak = max(abs(s) for s in samples) or 1.0
    scale = 32767.0 / peak
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        out = bytearray()
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32767)
            out += struct.pack("<h", v)
        w.writeframes(bytes(out))
    dur = len(samples) / sr
    print(f"  {path.relative_to(ROOT)}  {dur:.2f}s  peak={peak:.2f}")


def adsr(n, a, d, s, r, sr=SR):
    """Linear ADSR envelope of length n (samples)."""
    env = []
    na, nd, nr = int(a * sr), int(d * sr), int(r * sr)
    ns = max(0, n - na - nd - nr)
    for i in range(na):
        env.append(i / na if na else 1.0)
    for i in range(nd):
        env.append(1.0 - (1.0 - s) * (i / nd) if nd else s)
    for _ in range(ns):
        env.append(s)
    for i in range(nr):
        env.append(s * (1.0 - i / nr) if nr else 0.0)
    return env[:n]


def tone(freq, dur, sr=SR):
    """Pure sine at freq for dur seconds."""
    n = int(dur * sr)
    return [math.sin(2.0 * math.pi * freq * i / sr) for i in range(n)]


def noise(n):
    """White noise (-1..1)."""
    return [random.uniform(-1.0, 1.0) for _ in range(n)]


def mix(*tracks):
    """Sum aligned tracks with hard-clip at ±1."""
    if not tracks:
        return []
    n = max(len(t) for t in tracks)
    out = []
    for i in range(n):
        v = sum((t[i] if i < len(t) else 0.0) for t in tracks)
        out.append(max(-1.0, min(1.0, v)))
    return out


def filt_lp(x, cutoff, sr=SR):
    """One-pole lowpass."""
    out = []
    a = math.exp(-2.0 * math.pi * cutoff / sr)
    y = 0.0
    for v in x:
        y = y + (1.0 - a) * (v - y)
        out.append(y)
    return out


def filt_hp(x, cutoff, sr=SR):
    """One-pole highpass."""
    out = []
    a = math.exp(-2.0 * math.pi * cutoff / sr)
    y = 0.0
    x_prev = 0.0
    for v in x:
        y = a * (y + v - x_prev)
        out.append(y)
        x_prev = v
    return out


def delay(x, t_sec, fb, sr=SR):
    """Feedback delay line."""
    d = int(t_sec * sr)
    buf = [0.0] * d
    out = []
    wi = 0
    for v in x:
        w = buf[wi]
        out.append(v + w)
        buf[wi] = v + w * fb
        wi = (wi + 1) % d
    return out


# ---------------------------------------------------------------------------
# generators — each returns a list of float samples
# ---------------------------------------------------------------------------

def gen_click():
    """Single-sample impulse at full scale."""
    x = [0.0] * SR  # 1 second of silence with the click at the front
    x[0] = 1.0
    return x


def gen_kick():
    """808-style kick: sine sweep 150→40 Hz with exponential decay."""
    dur = 1.0
    n = int(dur * SR)
    env = [math.exp(-i / (SR * 0.15)) for i in range(n)]  # ~150ms decay
    phase = 0.0
    out = []
    for i in range(n):
        # freq sweeps from 150 to 40 Hz
        t = i / n
        f = 150.0 * (1.0 - t) + 40.0 * t
        phase += 2.0 * math.pi * f / SR
        # add a click at the front for attack
        click = 1.0 if i < 4 else 0.0
        out.append((math.sin(phase) + click * 0.4) * env[i])
    # saturate slightly
    return [max(-1.0, min(1.0, s * 1.3)) for s in out]


def gen_snare():
    """Noise burst + 200 Hz body, typical snare envelope."""
    dur = 0.6
    n = int(dur * SR)
    # body tone
    body = tone(200, dur)
    body_env = [math.exp(-i / (SR * 0.08)) for i in range(n)]
    # noise component
    nz = noise(n)
    nz = filt_hp(nz, 800)
    nz_env = [math.exp(-i / (SR * 0.12)) for i in range(n)]
    out = []
    for i in range(n):
        v = body[i] * body_env[i] * 0.6 + nz[i] * nz_env[i] * 0.8
        out.append(v)
    return out


def gen_hat():
    """Very short filtered noise, closed-hi-hat style."""
    dur = 0.15
    n = int(dur * SR)
    nz = noise(n)
    nz = filt_hp(nz, 5000)
    env = [math.exp(-i / (SR * 0.04)) for i in range(n)]
    return [nz[i] * env[i] for i in range(n)]


def gen_clap():
    """Layered noise transients — electronic clap."""
    dur = 0.4
    n = int(dur * SR)
    nz = noise(n)
    nz = filt_hp(nz, 1200)
    # three staggered noise bursts
    env = [0.0] * n
    for offset_s, amp in [(0.0, 1.0), (0.015, 0.7), (0.03, 0.5)]:
        off = int(offset_s * SR)
        for i in range(off, min(n, off + int(0.06 * SR))):
            t = (i - off) / (0.06 * SR)
            env[i] += amp * math.exp(-t * 8.0)
    return [nz[i] * min(1.0, env[i]) for i in range(n)]


def gen_stab():
    """Minor-9th chord stab — Cm9 voiced wide, synth-brass style."""
    # Cm9: C3 Eb3 G3 Bb3 D4
    notes = [_freq(48), _freq(51), _freq(55), _freq(58), _freq(62)]
    dur = 1.2
    n = int(dur * SR)
    out = [0.0] * n
    for f in notes:
        saw = [2.0 * ((i * f / SR) % 1.0) - 1.0 for i in range(n)]
        saw = filt_lp(saw, 3000)
        out = [out[i] + saw[i] * 0.22 for i in range(n)]
    env = adsr(n, 0.01, 0.15, 0.5, 0.8)
    return [out[i] * env[i] for i in range(n)]


def gen_pad():
    """Sustained Cmaj7 pad — filtered saws, slow attack."""
    # Cmaj7: C4 E4 G4 B4
    notes = [_freq(60), _freq(64), _freq(67), _freq(71)]
    dur = 3.0
    n = int(dur * SR)
    out = [0.0] * n
    for f in notes:
        saw = [2.0 * ((i * f / SR) % 1.0) - 1.0 for i in range(n)]
        saw = filt_lp(saw, 1200)
        # slight detune via slow phasor
        out = [out[i] + saw[i] * 0.18 for i in range(n)]
    env = adsr(n, 0.4, 0.3, 0.7, 0.5)
    return [out[i] * env[i] for i in range(n)]


def gen_bass():
    """Sustained sub-bass — C2, filtered saw."""
    f = _freq(36)  # C2
    dur = 2.5
    n = int(dur * SR)
    saw = [2.0 * ((i * f / SR) % 1.0) - 1.0 for i in range(n)]
    saw = filt_lp(saw, 200)
    env = adsr(n, 0.02, 0.1, 0.0, 0.3)  # no sustain — more of a pluck
    return [saw[i] * env[i] * 0.9 for i in range(n)]


def gen_melody():
    """Eight-bar melodic phrase in C minor — pentatonic with a twist.

    The phrase is designed to expose reverb character: short staccato notes,
    longer held notes, and rests that let the tail speak.
    """
    # (MIDI note, start beat, duration beats, velocity)
    # 8 bars of 4/4 at 100 BPM → 19.2 s total
    bpm = 100.0
    beat_s = 60.0 / bpm
    notes_cm = [
        # bar 1 — rising motif
        (60, 0.0, 0.5, 0.8),   # C4
        (63, 0.5, 0.5, 0.7),   # Eb4
        (67, 1.0, 1.0, 0.8),   # G4
        (63, 2.5, 0.5, 0.6),   # Eb4
        # bar 2
        (65, 4.0, 0.5, 0.7),   # F4
        (67, 4.5, 1.5, 0.8),   # G4
        (60, 6.5, 0.5, 0.5),   # C4
        # bar 3 — descent
        (67, 8.0, 0.5, 0.7),   # G4
        (65, 9.0, 0.5, 0.6),   # F4
        (63, 10.0, 0.5, 0.6),  # Eb4
        (60, 11.0, 1.0, 0.7),  # C4
        # bar 4 — rest-heavy
        (58, 13.0, 0.5, 0.5),  # Bb3
        (60, 14.0, 0.5, 0.6),  # C4
        (58, 15.0, 1.0, 0.5),  # Bb3
        # bar 5 — higher register
        (72, 16.0, 0.5, 0.8),  # C5
        (70, 17.0, 0.5, 0.7),  # Bb4
        (67, 18.0, 0.5, 0.7),  # G4
        (72, 19.0, 1.5, 0.8),  # C5
        # bar 6
        (70, 21.0, 0.5, 0.6),  # Bb4
        (67, 22.0, 0.5, 0.6),  # G4
        (63, 23.0, 1.0, 0.5),  # Eb4
        # bar 7 — staccato run
        (60, 24.5, 0.3, 0.6),  # C4
        (63, 25.0, 0.3, 0.6),  # Eb4
        (65, 25.5, 0.3, 0.6),  # F4
        (67, 26.0, 0.3, 0.6),  # G4
        (70, 26.5, 0.3, 0.6),  # Bb4
        (72, 27.0, 1.5, 0.8),  # C5 — held
        # bar 8 — resolution
        (67, 29.0, 0.5, 0.6),  # G4
        (63, 30.0, 0.5, 0.5),  # Eb4
        (60, 31.0, 1.0, 0.7),  # C4 — final
    ]

    total_beats = 32.0
    dur_s = total_beats * beat_s + 1.5  # extra tail
    n = int(dur_s * SR)
    out = [0.0] * n

    for note, start_beat, dur_beat, vel in notes_cm:
        t0 = int(start_beat * beat_s * SR)
        t1 = t0 + int(dur_beat * beat_s * SR)
        f = _freq(note)
        for i in range(t0, min(t1, n)):
            # simple triangle wave — soft and clear
            phase = (i - t0) * f / SR
            tri = 2.0 * abs(2.0 * (phase % 1.0) - 1.0) - 1.0
            # tiny envelope per note
            local_t = (i - t0) / max(1, t1 - t0)
            note_env = 1.0 if local_t < 0.85 else (1.0 - (local_t - 0.85) / 0.15)
            out[i] += tri * vel * note_env * 0.35

    # subtle global compression
    return [max(-1.0, min(1.0, s * 1.2)) for s in out]


def gen_loop():
    """Short drum groove with stab hits — practical usage test."""
    bpm = 110.0
    beat_s = 60.0 / bpm
    bars = 4
    dur_s = bars * 4 * beat_s + 0.5
    n = int(dur_s * SR)
    out = [0.0] * n

    def place(sound_fn, beat, amp=1.0):
        """Mix a short sound at a given beat position."""
        snd = sound_fn()
        t0 = int(beat * beat_s * SR)
        for i, v in enumerate(snd):
            idx = t0 + i
            if 0 <= idx < n:
                out[idx] += v * amp

    # kick on 1 and 3
    for bar in range(bars):
        for beat_off in (0.0, 2.0):
            place(gen_kick, bar * 4 + beat_off, 0.8)

    # snare on 2 and 4
    for bar in range(bars):
        for beat_off in (1.0, 3.0):
            place(gen_snare, bar * 4 + beat_off, 0.7)

    # hats on eighth notes
    for bar in range(bars):
        for eighth in range(8):
            place(gen_hat, bar * 4 + eighth * 0.5, 0.35)

    # clap on the 2 of bar 4
    place(gen_clap, 14.0, 1.0)

    # stab hits — sparse, to hear the verb
    place(gen_stab, 0.0, 0.6)   # bar 1 downbeat
    place(gen_stab, 6.0, 0.5)   # bar 2 beat 3
    place(gen_stab, 12.0, 0.7)  # bar 4 downbeat

    return [max(-1.0, min(1.0, s)) for s in out]


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

FILES = {
    "click":  (gen_click,  "single-sample impulse — measures the pure IR"),
    "kick":   (gen_kick,   "short 808-style kick — tests low-end density"),
    "snare":  (gen_snare,  "noise burst + tone body — tests mid diffusion"),
    "hat":    (gen_hat,    "very short filtered noise — tests HF tail"),
    "clap":   (gen_clap,   "layered noise transients — tests attack smearing"),
    "stab":   (gen_stab,   "sharp minor-9th chord stab — tests pitched bloom"),
    "pad":    (gen_pad,    "sustained Cmaj7 pad — tests tail on held material"),
    "bass":   (gen_bass,   "sustained sub-bass pluck — tests low-end clarity"),
    "melody": (gen_melody, "eight-bar C-minor phrase — most musical audition"),
    "loop":   (gen_loop,   "drum groove + stab hits — realistic usage"),
}


def main():
    p = argparse.ArgumentParser(description="Synthesise test audio for reverb voicing")
    p.add_argument("which", nargs="*", choices=list(FILES) + [[]],
                   help="which files to build (default: all)")
    p.add_argument("--list", action="store_true", help="list files and exit")
    p.add_argument("--seed", type=int, default=42, help="random seed (default: 42)")
    args = p.parse_args()

    if args.list:
        print("out/test_audio/")
        for name, (_, desc) in FILES.items():
            print(f"  {name}.wav  — {desc}")
        return

    random.seed(args.seed)
    names = args.which if args.which else list(FILES)
    print(f"writing {len(names)} file(s) to out/test_audio/ ...")
    for name in names:
        gen, desc = FILES[name]
        samples = gen()
        write_wav(OUT / f"{name}.wav", samples)
    print("done.")


if __name__ == "__main__":
    main()
