#!/usr/bin/env python3
"""Seam/click detector for a recorded-and-replayed TONE: the instantaneous
phase of a known frequency, from a sliding DFT, must advance linearly; a
dropped sample is a +360/period degree jump, a duplicated one the negative,
a level step shows in the magnitude. Prints every window-to-window phase jump
above `thresh` degrees (after removing the expected advance).
  o10_phase.py DUMP TRACK FREQ_HZ [win=64] [thresh=4]
  o10_phase.py --wav FILE.wav CHANNEL FREQ_HZ [win=64] [thresh=4]   (e.g. --audio-out's ring word 2)
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import blockdump as bd, o10_recloop as rl

def read_wav_channel(path, ch):
    import wave
    w = wave.open(path, 'rb'); n = w.getnframes(); nch = w.getnchannels(); sw = w.getsampwidth(); raw = w.readframes(n)
    return [int.from_bytes(raw[(i * nch + ch) * sw:(i * nch + ch + 1) * sw], 'little', signed=True) << (24 - 8 * sw) for i in range(n)]

def main():
    if sys.argv[1] == '--wav':
        path, track, f = sys.argv[2], int(sys.argv[3]), float(sys.argv[4]); args = sys.argv[5:]
    else:
        path, track, f = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]); args = sys.argv[4:]
    win = int(args[0]) if len(args) > 0 else 64
    thresh = float(args[1]) if len(args) > 1 else 4.0
    if sys.argv[1] == '--wav':
        x = read_wav_channel(path, track)
    else:
        c = bd.classes(bd.read(path)); x = rl.track_audio(c, track)
    period = 44100 / f
    w = 2 * math.pi * f / 44100
    cos = [math.cos(w * i) for i in range(win)]; sin = [math.sin(w * i) for i in range(win)]
    prev = None; hops = 0; first = None; jumps = []
    for s in range(0, len(x) - win, win // 2):
        seg = x[s:s + win]
        re = sum(v * cs for v, cs in zip(seg, cos)); im = sum(v * sn for v, sn in zip(seg, sin))
        mag = 2 * math.hypot(re, im) / win
        if mag < 8388608 * 1e-4:
            prev = None; continue
        ph = math.degrees(math.atan2(re, im))
        if first is None: first = s
        if prev is not None:
            pmag, pph, ps = prev
            expect = pph - math.degrees(w * (s - ps))          # phase of the tone referenced to the window start
            d = (ph - expect + 180) % 360 - 180
            if abs(d) > thresh:
                jumps.append((s, d, 20 * math.log10(mag / pmag) if pmag else 0))
        prev = (mag, ph, s)
    print(f"T{track} {f:.0f} Hz (period {period:.2f} samples = {360 / period:.1f} deg/sample): audio from sample {first}, "
          f"{len(jumps)} phase jump(s) > {thresh} deg in {win}-sample windows")
    for s, d, dl in jumps[:40]:
        print(f"   sample {s:7d} (frame {s / 16:8.1f}, pass {s / 20672:6.3f}): {d:+6.1f} deg = {d / (360 / period):+.2f} samples, level {dl:+.1f} dB")

if __name__ == '__main__':
    main()
