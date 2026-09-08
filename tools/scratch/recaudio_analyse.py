"""Read a recaudio.py capture: decode the recorder buffer's block chain as
24-bit stereo, fit the injected counter (L = (16*frame + i) << 8 in 24-bit
terms, times whatever gain the write path applied), and list every place the
buffer's sample-to-sample step is not the counter's -- a repeated sample
(step 0), a skipped one (step 2x), or foreign content. Then the outbound
per-track audio block around each trig, to see what the flex plays.

    .venv/bin/python tools/scratch/recaudio_analyse.py out/_ra_r4_128.pkl [--all]
"""
import pickle, sys, struct, collections

POOL_BASE, POOL_BLOCK = 0x40A955E0, 6144
FRAME = 16

def s24(b):
    v = int.from_bytes(b, "big")
    return v - (1 << 24) if v & 0x800000 else v

def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v

def main(path, show_all=False):
    d = pickle.load(open(path, "rb"))
    print(f"== {path}: frame0 {d['frame0']}, {d['frames']} frames, RECORD_24BIT={d['record_24bit']}, "
          f"setup {list(d.get('rec_setup', b''))}")
    ev = d["events"]
    arms = [e for e in ev if e["label"] == "armcall"]
    ends = [e for e in ev if e["label"] == "endpost"]
    print("arms:", [(e["frame"], round(e["sample"], 1)) for e in arms])
    print("ends:", [(e["frame"], round(e["sample"], 1), e["stack"][2]) for e in ends])
    if len(arms) > 1:
        print("arm spacings (samples):", [round(arms[k+1]["sample"] - arms[k]["sample"], 3) for k in range(len(arms) - 1)])

    # -- the chain: block numbers (row) -> absolute block index, from the pack loop's own writes
    first = [w for w in d["pool_first"] if w[4] in (0x4000785e, 0x40007860)]   # the pack loop's own stores
    if first:
        f0, ad0, *_ = first[0]
        idx0 = (ad0 - POOL_BASE) // POOL_BLOCK
        print(f"first pack write: frame {f0} at {ad0:#x} = block index {idx0}, byte {(ad0 - POOL_BASE) % POOL_BLOCK}; row[0] = {d['pool_row'][0]}"
              f" -> index = number {'+1' if idx0 == d['pool_row'][0] + 1 else '+0' if idx0 == d['pool_row'][0] else '?'}")
        delta = idx0 - d["pool_row"][0]
    else:
        delta = 1
    blocks = d["pool_blocks"]
    chain = []
    for num in d["pool_row"]:
        bi = num + delta
        if bi in blocks: chain.append(blocks[bi])
        else: break
    print(f"chain: {len(chain)} blocks = {len(chain) * 1024} samples")
    if not chain: return
    L = []; R = []
    for b in chain:
        for i in range(0, POOL_BLOCK, 6):
            L.append(s24(b[i:i+3])); R.append(s24(b[i+3:i+6]))
    # written extent: trailing zeros in both channels
    n = len(L)
    while n > 0 and L[n-1] == 0 and R[n-1] == 0: n -= 1
    print(f"nonzero extent: {n} samples")
    steps = [L[i+1] - L[i] for i in range(n - 1)]
    mode = collections.Counter(steps).most_common(4)
    print("L step histogram (top 4):", mode)
    D = mode[0][0]
    gain = D / 256.0
    print(f"fitted gain {gain:.5f} ({20*__import__('math').log10(abs(gain)) if gain else float('nan'):.1f} dB); L[0..8] = {L[:8]}; R[0..8] = {R[:8]}")
    tol = max(2, abs(D) // 8)
    anomalies = [(i, steps[i]) for i in range(n - 1) if abs(steps[i] - D) > tol]
    print(f"step anomalies (|step - {D}| > {tol}): {len(anomalies)}")
    for i, st in anomalies[:60 if not show_all else None]:
        print(f"   at sample {i}->{i+1}: step {st}  L={L[i]},{L[i+1]}  (expected {D}; {st/D if D else 0:+.2f}x)")
    # what sample of the counter does buffer[0] hold?  n_inj = 16*frame + i
    if arms and gain:
        n0 = L[0] / (256 * gain)
        f = arms[0]["frame"]
        print(f"buffer[0] ~ counter {n0:.1f} = frame {n0 // 16:.0f} + {n0 % 16:.1f}; first arm at frame {f} (counter {16*f}..{16*f+15})")

    # -- the outbound block around the trigs: which slot deviates from the input counter
    ao = d["audio_out"]
    byf = {}
    for f, s, g, sa, data in ao:
        byf.setdefault(f, []).append((g, sa, struct.unpack(">256I", data)))
    for e in arms[:3]:
        f = e["frame"]
        print(f"-- outbound block, frames {f-1}..{f+3} (values >> 16, minus the input counter 16*frame+i):")
        for ff in range(f - 1, f + 4):
            for g, sa, w in byf.get(ff, []):
                devs = {}
                for slot in range(8):
                    ls = [s32(w[slot*32 + 2*i]) >> 16 for i in range(16)]
                    dev = [ls[i] - ((16*ff + i) & 0xffff) for i in range(16)]
                    if any(abs(x) > 1 for x in dev): devs[slot] = dev
                print(f"   f{ff} gpio{g} src {sa:#x}: slot0 L>>16 = {[s32(w[2*i]) >> 16 for i in range(16)]}  deviating slots: {devs}")

if __name__ == "__main__":
    main(sys.argv[1], "--all" in sys.argv)
