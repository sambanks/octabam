#!/usr/bin/env python3
"""Flash 6's remaining claims, read off the port's block dumps (COLDFIRE_PORT.md O12).
  o12_claims.py            (expects out/o9d/cl_{nm,none,dmix0,rmix64,t8send,t4ret,t7ret,long}.dump)"""
import sys, math, pathlib
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import blockdump as bd, o10_recloop as rl
def db(v): return 20*math.log10(v/8388608) if v>0 else -200
def rms(x): return math.sqrt(sum(v*v for v in x)/len(x)) if x else 0
def load(name): return bd.classes(bd.read(f'out/o9d/cl_{name}.dump'))
def rb(c,t,lo,hi,right=False): return rl.readback_audio(c,t,right)[lo*16:hi*16]
def same(a,b): return all(x==y for x,y in zip(a,b)) and len(a)==len(b)
nm=load('nm'); base8=rb(nm,8,0,1200); base8r=rb(nm,8,0,1200,True)
print(f"baseline (T2 sends, master off): T8 return {db(rms(base8[6400:])):.1f} dBFS (frames 400-1200); hosts T1 {db(rms(rb(nm,1,400,1200))):.1f} T5 {db(rms(rb(nm,5,400,1200))):.1f}")
c=load('none'); y=rb(c,8,0,1200); print(f"iii  NONE on T1 and T5: T8 peak {max(abs(v) for v in y)} (0 = digital silence, not garbage) -> {'PASS' if max(abs(v) for v in y)==0 else 'FAIL'}")
c=load('dmix0'); y=rb(c,8,0,1200); on=next((i for i,v in enumerate(y) if v),None); onb=next((i for i,v in enumerate(base8) if v),None)
print(f"iv   delay MIX 0: T8 {db(rms(y[6400:])):.1f} dBFS, onset sample {on} vs baseline {onb} (the reverb of the DRY sends: later onset, no repeats) -> {'PASS' if on and onb and on>onb+100 else 'CHECK'}")
c=load('rmix64'); y=rb(c,8,0,1200); print(f"iv   reverb MIX 64: T8 {db(rms(y[6400:])):.1f} dBFS vs baseline {db(rms(base8[6400:])):.1f} (repeats under the tail: different, not silent) -> {'PASS' if not same(y,base8) and rms(y[6400:])>0 else 'FAIL'}")
c=load('t8send'); y=rb(c,8,0,1200); print(f"v    SEND on T8 FX2 at AUX 127: T8 return bit-identical to baseline -> {'PASS' if same(y,base8) else 'FAIL (differs)'}")
for v,t in (('t4ret',4),('t7ret',7)):
    c=load(v); yt=rb(c,t,0,1200); y8=rb(c,8,0,1200)
    print(f"vii  BUS-mode station on T{t}: T{t} out peak {max(abs(x) for x in yt)} (0 = returns nothing), T8 still returns {'identically' if same(y8,base8) else 'DIFFERENTLY'} -> {'PASS' if max(abs(x) for x in yt)==0 and same(y8,base8) else 'FAIL'}")
c=load('long'); y=rl.readback_audio(c,8); n=len(y)//16
lv=[db(rms(y[f*16:(f+250)*16])) for f in range(500,n-250,250)]
print(f"viii long run ({n} frames): T8 return per 250 frames from 500: min {min(lv):.1f} max {max(lv):.1f} dBFS (flat = no flicker/dropout) -> {'PASS' if max(lv)-min(lv)<1.0 else 'CHECK'}")
print("   ", ' '.join(f"{v:.1f}" for v in lv))
