"""Route A: log the recorder's block walk (0x40006fdc..0x400072d2) per iteration
while fp(3) (recording) is set. Derived from seqprobe.py."""
import argparse, sys
import os; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import emu_rtos as er, emu_card as ec, emu_bringup as eb
from unicorn.m68k_const import *
from unicorn import UC_HOOK_CODE
ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--tree", required=True)
ap.add_argument("--name", default="RECTRIG"); ap.add_argument("--frames", type=int, default=2000)
ap.add_argument("--max", type=int, default=20000); ap.add_argument("--no-arm-fix", action="store_true")
a = ap.parse_args()
card, name = er.stage_project(a.project, "OCTABAM", a.name, tree=a.tree)
r, rt = er.attach(None, card)
log = []
def rd(u, r): return u.reg_read(r) & 0xffffffff
def m32(u, ad): return int.from_bytes(u.mem_read(ad, 4), "big")
def at_7178(u, addr, size, user):
    # d3 = advance candidate, d5 = fp(3), a2 = samples left this call, a0 = block idx, d1 = min term
    fp = rd(u, UC_M68K_REG_A6); sp = rd(u, UC_M68K_REG_A7)
    rec = dict(f=rt.frame_count, s=rt.sample, d3=rd(u, UC_M68K_REG_D3), d5=rd(u, UC_M68K_REG_D5),
               a2=rd(u, UC_M68K_REG_A2), a0=rd(u, UC_M68K_REG_A0), d6=rd(u, UC_M68K_REG_D6),
               d7=rd(u, UC_M68K_REG_D7), pos=m32(u, fp+24), cnt=m32(u, fp+28), st=u.mem_read(fp, 4).hex(),
               budget=m32(u, sp+64), n48=m32(u, sp+48), timing=m32(u, sp+144), end=m32(u, sp+148),
               seg=m32(u, sp+68), pickup=m32(u, sp+128), track=m32(u, sp+136))
    if len(log) < a.max: log.append(rec)
rt.uc.hook_add(UC_HOOK_CODE, at_7178, begin=0x40007178, end=0x40007178)
alloc = []
def at_alloc(u, addr, size, user):
    if len(alloc) < 2000: alloc.append((rt.frame_count, addr, m32(u, 0x80006920), m32(u, 0x8000691c), u.mem_read(0x80000052,1)[0]))
for pc in (0x400071ae, 0x400071b6, 0x40007234, 0x4000726e):
    rt.uc.hook_add(UC_HOOK_CODE, at_alloc, begin=pc, end=pc)
from unicorn import UC_HOOK_MEM_WRITE
wr = []
def on_wr(u, acc, addr, size, val, user):
    if len(wr) < 400: wr.append((rt.frame_count, addr, size, val & 0xffffffff, rd(u, UC_M68K_REG_PC)))
rt.uc.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=0x46c80354, end=0x46c80354 + 31)   # DSP command slots
rt.uc.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=0x46c938d4, end=0x46c938d4 + 3)    # R1 control record +16 (length)
rt.uc.ctl_flush_tb()
if not rt.gate_m6a()[0]:
    rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
mounted, posted, saved_bank, final_bank, _ = rt.load_project_live("OCTABAM", name, run_ms=20000)
if final_bank != saved_bank: final_bank = rt.select_bank_live(saved_bank)
pattern = rt.uc.mem_read(er.CUR_PATTERN, 1)[0]
rt.seq_select_live(final_bank, pattern); rt.internal_clock()
rt.frame = True; rt.next_frame = rt.sample + er.FRAME_PERIOD; rt.exact_clock()
if not a.no_arm_fix: rt.arm_phase_fix()
rt.start_transport_live()
rt.install_trig_log()
frame0 = rt.frame_count + 1; target = frame0 + a.frames
rt.run(ms=a.frames * er.FRAME_PERIOD / er.SAMPLE_HZ * 1000.0 * 5 + 2000, until=lambda x: x.frame_count >= target)
print(f"frames {rt.frame_count - frame0}/{a.frames}, frame0={frame0}; trig words: {rt.trig_words_log[:3]}; walk iters {len(log)}, alloc hits {len(alloc)}")
recs = [x for x in log if x['d5']]
print(f"iterations with fp(3) set: {len(recs)}")
def show(x): print(f"  f{x['f']-frame0:5d} t{x['track']} st={x['st']} pos={x['pos']:#x} cnt={x['cnt']:#x} d3={x['d3']:#x} a2={x['a2']:#x} a0(blk)={x['a0']:#x} d6={x['d6']:#x} d7={x['d7']:#x} budget={x['budget']:#x} n48={x['n48']} tim={x['timing']} end={x['end']} seg={x['seg']} pk={x['pickup']}")
last = None
for i, x in enumerate(recs):
    key = (x['d3'] != 0, x['a0'], x['a2'] == 0)
    if i < 12 or key != last or i >= len(recs) - 6: show(x)
    last = key
print("alloc path hits (frame, pc, free_top, free_bot, flag52):")
for t in alloc[:40]: print("  ", t)

print("writes to DSP cmd slots / R1 length:")
for f, ad, sz, v, pc in wr[:60]: print(f"  f{f-frame0:5d} [{ad:#x}] <- {v:#x} ({sz}) pc {pc:#x}")
print("arm fixes:", getattr(rt, 'arm_fixes', None))
d = rt.uc.mem_read(0x80004f1c, 0x540)
for bank in (0, 1):
    rec = d[bank*672: bank*672 + 84]
    print(f"rec bank{bank} t0:", rec[:48].hex(" "))
