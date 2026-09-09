import sys, numpy as np
sys.path.insert(0,'tools/scratch')
import blockdump as bd, o10_recloop as o
dump, ideal = sys.argv[1], float(sys.argv[2])   # ideal pass length in samples
c=bd.classes(bd.read(dump))
x=np.array(o.track_audio(c,2),float)
nz=np.nonzero(x!=0)[0]
print(f"{dump}: {len(x)} T2 samples, first nonzero {nz[0] if len(nz) else None}, ideal pass {ideal}")
# counter value = input index. find big negative steps = buffer wraps (value resets toward buffer start)
d=np.diff(x)
# a wrap is where value drops a lot (from ~buffer_end back toward ~0)
wraps=np.nonzero(d < -ideal*0.5)[0]
# cluster
cl=[]
for i in wraps:
    if cl and i-cl[-1][-1]<50: cl[-1].append(int(i))
    else: cl.append([int(i)])
print(f"detected {len(cl)} wrap events")
prev=None
for w in cl:
    i=w[0]; before=x[i]; after=x[i+1]
    drop=before-after
    print(f"  wrap at out sample {i}: value {int(before)} -> {int(after)} (drop {int(drop)}); spacing from prev {'' if prev is None else i-prev}")
    prev=i
# within-pass continuity: is the delay (out_index - value) constant, and does it step at wraps?
print("delay (out - value) sampled every 4000:", [(k, int(k-x[k])) for k in range(nz[0] if len(nz) else 0, len(x), 4000)][:20])
