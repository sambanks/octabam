"""Per-pass seam report from a recaudio.py capture's arm-time snapshots.

At every arm the driver snapshots the recorder buffer's head (48 samples)
and the samples around each candidate period. With the counter injected
(L = ((16*frame + i) & 0x7fff) << 8 in 24-bit terms, R = tag/slot probe), a buffer
sample decodes to the INPUT TIME it was captured at (mod 32768), so for
pass k we can read

    n_first(k)  = input time recorded at position 0          (this pass's arm)
    n_last(k)   = input time recorded at position P-1        (this pass's end)

and compare n_first(k+1) - n_first(k) with the sequencer's own arm spacing
(the ColdFire numbers of RTOS_FORK 10.16.5). Sample-exact recorder: the
two agree, 20,671 included. Frame-quantised recorder: multiples of 16.

    .venv/bin/python tools/scratch/recaudio_seams.py out/_ra_r4_128.pkl
"""
import pickle, sys

def s24(b):
    v = int.from_bytes(b, "big"); return v - (1 << 24) if v & 0x800000 else v

def dec(b6):
    """one packed stereo sample -> (input time mod 65536 from L, slot i from R, raw L, raw R)"""
    L, R = s24(b6[:3]), s24(b6[3:6])
    return ((L >> 8) & 0x7fff), ((R >> 8) & 0xf), L, R

def main(path):
    d = pickle.load(open(path, "rb"))
    ev = d["events"]
    arms = [e for e in ev if e["label"] == "armcall"]
    print(f"== {path}: setup {list(d.get('rec_setup', b''))}")
    print("arm frames/samples:", [(e["frame"], round(e["sample"], 2)) for e in arms])
    spacings = [round(arms[k+1]["sample"] - arms[k]["sample"], 3) for k in range(len(arms) - 1)]
    print("sequencer arm spacings:", spacings)
    snaps = d.get("snaps", [])
    print(f"{len(snaps)} snapshots")
    prev = None
    rows = []
    for k, (f, s, sn) in enumerate(snaps):
        head = sn["head"]
        h = [dec(head[i:i+6]) for i in range(0, len(head), 6)]
        n0, i0 = h[0][0], h[0][1]
        # head continuity: steps of +1 in input time, i cycling 0..15
        hsteps = [((h[i+1][0] - h[i][0]) & 0x7fff) for i in range(len(h) - 1)]
        line = f"snap {k} at arm frame {f} (sample {s:.1f}): buffer[0] = input {n0} (slot {i0})  head steps {sorted(set(hsteps))}"
        for P, raw in ((P, sn[P]) for P in sn if P != "head"):
            v = [dec(raw[i:i+6]) for i in range(0, len(raw), 6)]
            tail = v[:32]; after = v[32:]
            tsteps = sorted(set(((tail[i+1][0] - tail[i][0]) & 0x7fff) for i in range(len(tail) - 1)))
            if any(x[2] or x[3] for x in tail):
                line += f"\n      P={P}: [P-32..P-1] input {tail[0][0]}..{tail[-1][0]} steps {tsteps}; [P..P+7] L={[x[2] for x in after]}"
        print(line)
        rows.append((f, s, n0, i0))
    print("-- per pass: buffer[0] input time vs the sequencer's arm")
    for k in range(1, len(rows)):
        f, s, n0, i0 = rows[k]
        fp_, sp_, np_, ip_ = rows[k-1]
        dn = (n0 - np_) & 0x7fff
        # input time is mod 32768: bring the difference near the sequencer spacing
        seq = spacings[k-1] if k-1 < len(spacings) else None
        if seq is not None:
            while dn + 32768 <= seq + 16384: dn += 32768
        print(f"   pass {k}: buffer[0] input time step {dn} (slot {ip_}->{i0})  sequencer spacing {seq}  -> {'MATCH' if seq is not None and abs(dn - round(seq)) <= 0 else 'DIFF ' + str(dn - round(seq)) if seq is not None else ''}")

if __name__ == "__main__":
    main(sys.argv[1])
