"""Frame-phase-band model of the Octatrack recorder "click" (5 Sep 2026).

A MODEL, not the firmware: it says what the hypothesis in docs/EXTERNAL.md §6
(Sessions 2-4) predicts, so Bryan T's hardware test has numbers to hit or miss.

Recorder: free-running LOOP=ON writer over a buffer of L samples, in 16-sample
frames (the write path is 0x400068e4, called per frame by 0x4000d2a0).  Flex:
playback read of the same buffer, retriggered by the sequencer at
t_k = round(k*P), P = the exact sequencer period in samples.  Both run once per
frame in a fixed order.  Each buffer sample is stamped with the pass number of
its last write.  A read frame is a SEAM frame if the pass number changes
between two consecutive read samples at buffer positions (p, p+1) with p != L-1
(a change across L-1 -> 0 is consecutive writing: continuous content).

Length: the firmware's own arithmetic (firmware_length: truncating EMAC, see
below; round-half-up is wrong on ~1 in 8 cells).  tempo24 from the
displayed tempo is the MEASURED UI mapping (0x4009c7c4):
    tempo24 = 24*bpm + (23*tenths + 4) // 9
Run:  python3 tools/recorder_framephase.py
"""
FRAME = 16
FS = 44100.0

def run(L, P, order, passes=400, mode="rec-free/play-retrig"):
    passid = [0] * L
    wpos = 0; wpass = 1
    k = 0; t_k = 0; next_trig = int(round(P))
    seams = {}; frames = {}
    nframes = int(round(passes * P)) // FRAME
    for f in range(nframes):
        t0 = f * FRAME
        def do_write():
            nonlocal wpos, wpass
            for i in range(FRAME):
                passid[wpos] = wpass; wpos += 1
                if wpos == L: wpos = 0; wpass += 1
        def do_read():
            nonlocal k, t_k, next_trig
            ids = []; poss = []
            for i in range(FRAME):
                t = t0 + i
                if t == next_trig:
                    k += 1; next_trig = int(round((k + 1) * P))
                    if mode == "rec-free/play-retrig": t_k = t
                rpos = (t - t_k) % L if mode == "rec-free/play-retrig" else t % L
                poss.append(rpos); ids.append(passid[rpos])
            seam = any(ids[i] != ids[i-1] and poss[i-1] != L - 1 for i in range(1, FRAME))
            seams[k] = seams.get(k, 0) + seam
            frames[k] = frames.get(k, 0) + 1
        if order == "write-first": do_write(); do_read()
        else: do_read(); do_write()
    last = max(frames)
    return [seams.get(i, 0) / frames[i] for i in range(last) if i in frames]  # drop partial last pass

def summarise(name, L, P, eps, order, mode="rec-free/play-retrig"):
    s = run(L, P, order, mode=mode)
    hot = [i for i, v in enumerate(s) if v > 0.05]
    tag = f"  {name:>8} {order:<11} L={L:<6} eps={eps:+.3f} "
    if not hot:
        print(tag + f"clean for all {len(s)} passes"); return
    # contiguous runs
    runs = []; start = hot[0]; prev = hot[0]
    for h in hot[1:]:
        if h != prev + 1: runs.append((start, prev)); start = h
        prev = h
    runs.append((start, prev))
    desc = "; ".join(f"passes {a}-{b} ({b-a+1} = {(b-a+1)*P/FS:.1f} s, mean seam frac {sum(s[a:b+1])/(b-a+1):.2f})" for a, b in runs)
    print(tag + "SEAMS " + desc + f"; then clean to pass {len(s)}")

rows = [(199, 4), (298.2, 2), (286.2, 2), (251, 16), (198, 16), (229, 16), (120, 16), (120, 4), (300, 2),
        (261.3, 2), (128, 16), (128, 4), (128, 32)]
# Bryan T's hardware log (sessions 4-5). NOTE his epsilon is L - P; ours below is P - L.
obs = {(199, 4): "clicks", (298.2, 2): "clicks", (286.2, 2): "clicks", (251, 16): "clicks",
       (120, 16): "clean", (120, 4): "clean", (300, 2): "clean",
       (261.3, 2): "clicks (session 5)", (128, 16): "clicks (session 5, predicted)"}

def tempo24(bpm):
    """Measured UI conversion, 0x4009c7c4: integer BPM plus a tenths digit."""
    b = int(bpm); tenths = int(round((bpm - b) * 10))
    return 24 * b + (23 * tenths + 4) // 9


def firmware_length(steps, t24):
    """The converter that feeds arm(), 0x40006dfc-0x40006e10, exactly:
    Q = trunc(2^31 / tempo24) (0x4000cab8, biased low), A = steps x 31752000,
    the EMAC multiply truncates (MACSR = 0x20 at 0x4000cf62: fractional,
    round/truncate bit clear -- Bryan T, 6 Sep 2026), then (x + 1) >> 1.
    Differs from round-half-up on ~1 in 8 grid cells, never on exact ones."""
    Q = (1 << 31) // t24
    return (((steps * 31752000 * Q) >> 31) + 1) >> 1


for bpm, rlen in rows:
    t24 = tempo24(bpm); P = rlen * 15876000 / t24; L = firmware_length(rlen, t24); eps = P - L
    print(f"{bpm}/{rlen}: tempo24={t24} P={P:.3f} L={L} (L mod 16 = {L%16})  observed: {obs.get((bpm,rlen),'not recorded')}")
    for order in ("write-first", "read-first"):
        summarise(f"{bpm}/{rlen}", L, P, eps, order)

print("\n=== control: both free-running (flex loops at L itself, never retriggered), 199/4 ===")
t24 = tempo24(199); P = 4 * 15876000 / t24; L = firmware_length(4, t24)
for order in ("write-first", "read-first"):
    summarise("199/4", L, P, P - L, order, mode="both-free")
