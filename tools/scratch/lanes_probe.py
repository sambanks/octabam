"""Route A: where do the FX knob bytes stand after a project load? Read the bank blob's Part
knob storage, the live block 0x80000810+track*72 and the frame builder's source registers."""
import sys, os, struct
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import emu_rtos as er, emu_bringup as eb
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.m68k_const import *
proj, image, frames = sys.argv[1], sys.argv[2], int(sys.argv[3])
card, name = er.stage_project(proj, "OCTABAM", "ONEAUX", tree="out/_lanes_tree")
r, rt = er.attach(image, card)
if not rt.gate_m6a()[0]: rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
mounted, posted, saved_bank, final_bank, elapsed = rt.load_project_live("OCTABAM", name, run_ms=6000)
print("load:", mounted, saved_bank, final_bank)
u = rt.uc
def m32(ad): return int.from_bytes(u.mem_read(ad, 4), "big")
def m8(ad, n): return u.mem_read(ad, n)
bank_ptr = m32(0x46c82456); part = m8(0x100b14cf, 1)[0]
print(f"bank blob ptr [0x46c82456] = {bank_ptr:#x}, part byte 0x100b14cf = {part}")
for label, base in (("current blob", bank_ptr), ("bank A blob", 0x400e21e0), ("bank B blob", 0x4017d520)):
    for p in range(2):
        for t in (0, 4, 7):
            off = base + 0x8ee9a + p * 6322 + t * 24
            print(f"  {label} part {p} T{t+1} knobs +0x8ee9a: {m8(off, 24).hex(' ')}")
        ids = base + 0x8ed80 + p * 6322
        print(f"  {label} part {p} FX1 ids {m8(ids,8).hex(' ')}  FX2 ids {m8(ids+8,8).hex(' ')}")
print("live block before play:")
for t in range(8): print(f"  T{t+1} 0x80000810+{t*72}: {m8(0x80000810 + t*72, 72).hex(' ')}")
# who writes the live block, and what the frame builder's a2/a3 are at 0x4000c0f0
writers = {}
def on_wr(u_, acc, addr, size, val, x):
    pc = u_.reg_read(UC_M68K_REG_PC); k = (pc, (addr - 0x80000810) // 72)
    writers[k] = writers.get(k, 0) + 1
u.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=0x80000810, end=0x80000810 + 8*72 - 1)
regs = []
def on_fb(u_, addr, size, x):
    if len(regs) < 6:
        regs.append({n: u_.reg_read(rg) & 0xffffffff for n, rg in (("a0",UC_M68K_REG_A0),("a1",UC_M68K_REG_A1),("a2",UC_M68K_REG_A2),("a3",UC_M68K_REG_A3),("d6",UC_M68K_REG_D6),("d7",UC_M68K_REG_D7))})
u.hook_add(UC_HOOK_CODE, on_fb, begin=0x4000c0f0, end=0x4000c0f0)
bank = saved_bank if saved_bank is not None else final_bank
if final_bank != bank: final_bank = rt.select_bank_live(bank)
pattern = u.mem_read(er.CUR_PATTERN, 1)[0]
rt.seq_select_live(final_bank, pattern)
rt.internal_clock(); rt.frame = True; rt.next_frame = rt.sample + er.FRAME_PERIOD; rt.exact_clock()
rt.start_transport_live()
f0 = rt.frame_count + 1
rt.run(ms=frames * er.FRAME_PERIOD / er.SAMPLE_HZ * 1000 * 5 + 2000, until=lambda x: x.frame_count >= f0 + frames)
print(f"ran {rt.frame_count - f0} frames; bank {final_bank} pattern {pattern}; part byte now {m8(0x100b14cf,1)[0]}")
print("frame builder 0x4000c0f0 entries (first 6):")
for rg in regs: print("  ", {k: hex(v) for k, v in rg.items()})
print("live block writers (pc, track): count")
for (pc, t), n in sorted(writers.items()): print(f"  pc {pc:#x} track {t}: {n}")
print("live block after play:")
for t in range(8): print(f"  T{t+1}: {m8(0x80000810 + t*72, 72).hex(' ')}")
print("DSP halfword array 0x80000a50 + track*64 (T5, T1):")
for t in (4, 0): print(f"  T{t+1}: {m8(0x80000a50 + t*64, 64).hex(' ')}")
