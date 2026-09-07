"""Route A: recorder END path -- the trig, the arm, the end test, the end post, the +32 write."""
import argparse, sys
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import emu_rtos as er, emu_card as ec, emu_bringup as eb
from unicorn.m68k_const import *
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--tree", required=True)
ap.add_argument("--name", default="RECTRIG"); ap.add_argument("--frames", type=int, default=2700)
ap.add_argument("--arm-fix", action="store_true")
a = ap.parse_args()
card, name = er.stage_project(a.project, "OCTABAM", a.name, tree=a.tree)
r, rt = er.attach(None, card)
ev = []
def rd(u, r): return u.reg_read(r) & 0xffffffff
def m32(u, ad): return int.from_bytes(u.mem_read(ad, 4), "big")
def at(label):
    def h(u, addr, size, user):
        fp = rd(u, UC_M68K_REG_A6); sp = rd(u, UC_M68K_REG_A7)
        if len(ev) < 4000:
            ev.append((rt.frame_count, rt.sample, label, dict(d0=rd(u,UC_M68K_REG_D0), d1=rd(u,UC_M68K_REG_D1), d3=rd(u,UC_M68K_REG_D3), a0=rd(u,UC_M68K_REG_A0), a1=rd(u,UC_M68K_REG_A1), a2=rd(u,UC_M68K_REG_A2), pos=m32(u,fp+24), cnt=m32(u,fp+28), f32=m32(u,fp+32), st=u.mem_read(fp,4).hex(), budget=m32(u,sp+64), tim=m32(u,sp+144), end=m32(u,sp+148), track=m32(u,sp+136))))
    return h
for pc, label in ((0x40006e8e, "endtest"), (0x40006ea8, "subframe"), (0x40006edc, "endpost"), (0x40006b18, "armpost"), (0x400070ba, "post70ba")):
    rt.uc.hook_add(UC_HOOK_CODE, at(label), begin=pc, end=pc)
wr = []
def on_wr(u, acc, addr, size, val, user):
    if len(wr) < 200: wr.append((rt.frame_count, rt.sample, addr, size, val & 0xffffffff, rd(u, UC_M68K_REG_PC)))
rt.uc.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=0x46c80354, end=0x46c80354 + 31)
rt.uc.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=0x80004f1c + 672 + 32, end=0x80004f1c + 672 + 35)   # bank1 t0 +32
rt.uc.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=0x80004f1c + 32, end=0x80004f1c + 35)               # bank0 t0 +32
rt.uc.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=0x46105366, end=0x46105366 + 3)                    # engine post opcode word
rt.uc.ctl_flush_tb()
if not rt.gate_m6a()[0]:
    rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
mounted, posted, saved_bank, final_bank, _ = rt.load_project_live("OCTABAM", name, run_ms=20000)
if final_bank != saved_bank: final_bank = rt.select_bank_live(saved_bank)
pattern = rt.uc.mem_read(er.CUR_PATTERN, 1)[0]
rt.seq_select_live(final_bank, pattern); rt.internal_clock()
rt.frame = True; rt.next_frame = rt.sample + er.FRAME_PERIOD; rt.exact_clock()
if a.arm_fix: rt.arm_phase_fix()
rt.start_transport_live()
rt.install_trig_log()
frame0 = rt.frame_count + 1; target = frame0 + a.frames
rt.run(ms=a.frames * er.FRAME_PERIOD / er.SAMPLE_HZ * 1000.0 * 5 + 2000, until=lambda x: x.frame_count >= target)
print(f"frames {rt.frame_count - frame0}/{a.frames}, frame0={frame0}; trig words: {rt.trig_words_log[:4]}; arm fixes {getattr(rt,'arm_fixes',None)}")
seen = {}
for f, s, label, d in ev:
    seen[label] = seen.get(label, 0) + 1
    if label == "endtest" and seen[label] > 3 and d['budget'] - d['pos'] > 64: continue
    print(f"  f{f-frame0:5d} [{s:10.1f}] {label:9s} " + " ".join(f"{k}={v:#x}" if isinstance(v,int) else f"{k}={v}" for k, v in d.items()))
print("label counts:", seen)
print("writes (cmd slots, +32 fields, engine opcode):")
for f, s, ad, sz, v, pc in wr: print(f"  f{f-frame0:5d} [{s:10.1f}] [{ad:#x}] <- {v:#x} ({sz}) pc {pc:#x}")
d = rt.uc.mem_read(0x80004f1c, 0x540)
for bank in (0, 1): print(f"rec bank{bank} t0:", d[bank*672: bank*672 + 48].hex(" "))
print("R1 control:", rt.uc.mem_read(0x46c938c4, 44).hex(" "))
