"""Frame builder inputs for track 0's lane pair around the trig frames."""
import argparse, sys, os, struct
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import emu_rtos as er, emu_card as ec, emu_bringup as eb
from unicorn.m68k_const import *
from unicorn import UC_HOOK_CODE
ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--tree", required=True)
ap.add_argument("--name", default="RECTRIG"); ap.add_argument("--frames", type=int, default=1400)
ap.add_argument("--from", dest="frm", type=int, default=1280); ap.add_argument("--to", type=int, default=1296)
a = ap.parse_args()
card, name = er.stage_project(a.project, "OCTABAM", a.name, tree=a.tree)
r, rt = er.attach(None, card)
ev = []
def rd(u, r): return u.reg_read(r) & 0xffffffff
def m32(u, ad): return int.from_bytes(u.mem_read(ad, 4), "big")
frame0 = [None]
def head(u, addr, size, user):   # 0x4000aef6: d0 = 62 on the first pair (track 0)
    if rd(u, UC_M68K_REG_D0) != 62: return
    f = rt.frame_count - (frame0[0] or 0)
    if not (a.frm <= f <= a.to): return
    a0 = rd(u, UC_M68K_REG_A0)
    ev.append(("head", rt.frame_count, rt.sample, dict(frameEnd=rd(u, UC_M68K_REG_D4), ev0=m32(u, a0), ev1=m32(u, a0 + 4), t24=m32(u, 0x80001814), d5=rd(u, UC_M68K_REG_D5), fclk=m32(u, 0x46104cf4), sclk=m32(u, 0x4610757c), tick=m32(u, 0x46104cfc))))
def byte(u, addr, size, user):   # 0x4000af16: d2 = byte for lane 0 of the pair
    if rd(u, UC_M68K_REG_D0) != 62: return
    f = rt.frame_count - (frame0[0] or 0)
    if not (a.frm <= f <= a.to): return
    ev.append(("byte", rt.frame_count, rt.sample, dict(b0=rd(u, UC_M68K_REG_D2) & 0xff, d2=rd(u, UC_M68K_REG_D2))))
tr = []
def trace(u, addr, size, user):
    f = rt.frame_count - (frame0[0] or 0)
    if not (a.frm <= f <= a.to) or len(tr) > 400: return
    if rd(u, UC_M68K_REG_D0) not in (62, 60): return
    tr.append((f, addr, [rd(u, r) for r in (UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_A0)]))
rt.uc.hook_add(UC_HOOK_CODE, trace, begin=0x4000aef6, end=0x4000af24)
rt.uc.hook_add(UC_HOOK_CODE, head, begin=0x4000aef6, end=0x4000aef6)
rt.uc.hook_add(UC_HOOK_CODE, byte, begin=0x4000af16, end=0x4000af16)
tw = []
def tword(u, addr, size, user):   # 0x4000d32e: word for track d3 at sp(144)
    if rd(u, UC_M68K_REG_D3) != 0: return
    f = rt.frame_count - (frame0[0] or 0)
    if a.frm <= f <= a.to: tw.append((rt.frame_count, rt.sample, int.from_bytes(u.mem_read(rd(u, UC_M68K_REG_A0), 2), "big")))
rt.uc.hook_add(UC_HOOK_CODE, tword, begin=0x4000d32e, end=0x4000d32e)
rt.uc.ctl_flush_tb()
if not rt.gate_m6a()[0]:
    rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
mounted, posted, saved_bank, final_bank, _ = rt.load_project_live("OCTABAM", name, run_ms=20000)
if final_bank != saved_bank: final_bank = rt.select_bank_live(saved_bank)
pattern = rt.uc.mem_read(er.CUR_PATTERN, 1)[0]
rt.seq_select_live(final_bank, pattern); rt.internal_clock()
rt.frame = True; rt.next_frame = rt.sample + er.FRAME_PERIOD; rt.exact_clock()
print("start: fclk", hex(m32(rt.uc, 0x46104cf4)), "sclk", hex(m32(rt.uc, 0x4610757c)), "flag6686", rt.uc.mem_read(0x80006686,1)[0], "sample", rt.sample)
rt.start_transport_live()
print("after start: fclk", hex(m32(rt.uc, 0x46104cf4)), "sclk", hex(m32(rt.uc, 0x4610757c)), "flag6686", rt.uc.mem_read(0x80006686,1)[0], "sample", rt.sample, "frame", rt.frame_count)
rt.install_trig_log()
frame0[0] = rt.frame_count + 1; target = frame0[0] + a.frames
rt.run(ms=a.frames * er.FRAME_PERIOD / er.SAMPLE_HZ * 1000.0 * 5 + 2000, until=lambda x: x.frame_count >= target)
print(f"frames {rt.frame_count - frame0[0]}/{a.frames}, frame0={frame0[0]}; trig words: {rt.trig_words_log[:4]}")
for kind, f, s, d in ev:
    print(f"  f{f-frame0[0]:5d} [{s:10.1f}] {kind:5s} " + " ".join(f"{k}={v:#x}" for k, v in d.items()))
for f, pc, regs in tr: print(f"  f{f} {pc:#x} d0={regs[0]:#x} d1={regs[1]:#x} d2={regs[2]:#x} d3={regs[3]:#x} d4={regs[4]:#x} d5={regs[5]:#x} a0={regs[6]:#x}")
print("track-0 words at dispatcher:", [(f - frame0[0], w) for f, s, w in tw if w])
