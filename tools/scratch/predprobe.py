"""Inside the converter (0x40006e0c, fixed-RLEN path, 2/frame while recording): predict the next
arm's dispatcher sample as cf8 + 16 + floor((lane[t] - look) * r) and compare with the real arm."""
import argparse, sys
import os; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import emu_rtos as er, emu_card as ec, emu_bringup as eb
from unicorn.m68k_const import *
from unicorn import UC_HOOK_CODE
ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--tree", required=True)
ap.add_argument("--name", default="RECTRIG"); ap.add_argument("--frames", type=int, default=3000)
a = ap.parse_args()
card, name = er.stage_project(a.project, "OCTABAM", a.name, tree=a.tree)
r, rt = er.attach(None, card)
def m32(u, ad): return int.from_bytes(u.mem_read(ad, 4), "big")
def s32(u, ad): return int.from_bytes(u.mem_read(ad, 4), "big", signed=True)
frame0 = [None]; preds = []; arms = []
def at_conv(u, addr, size, user):
    f = rt.frame_count - (frame0[0] or 0)
    track = m32(u, u.reg_read(UC_M68K_REG_A7) + 136)
    lane = m32(u, 0x80001904 + 4 * track); look = m32(u, 0x46104cf0); cf8 = m32(u, 0x46104cf8)
    recip = -s32(u, 0x80001820); t24 = m32(u, 0x80001814)
    diff = (lane - look) & 0xffffffff
    if diff & 0x80000000: diff -= 1 << 32
    n = (diff * recip) >> 31           # the firmware's macl (fractional, >>31, floor)
    stock = u.reg_read(UC_M68K_REG_D0) & 0xffffffff   # product before +1 >>1
    preds.append((f, track, lane / t24, look / t24, cf8, n, cf8 + 16 + n, m32(u, 0x46c7fa84 + 4 * track), (stock + 1) >> 1))
rt.uc.hook_add(UC_HOOK_CODE, at_conv, begin=0x40006e0c, end=0x40006e0c)
def at_arm(u, addr, size, user):
    f = rt.frame_count - (frame0[0] or 0); sp = u.reg_read(UC_M68K_REG_A7)
    arms.append((f, m32(u, sp + 4), m32(u, sp + 8), m32(u, 0x46104cf8)))
rt.uc.hook_add(UC_HOOK_CODE, at_arm, begin=0x40005ff0, end=0x40005ff0)
rt.uc.ctl_flush_tb()
if not rt.gate_m6a()[0]:
    rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
mounted, posted, saved_bank, final_bank, _ = rt.load_project_live("OCTABAM", name, run_ms=20000)
if final_bank != saved_bank: final_bank = rt.select_bank_live(saved_bank)
pattern = rt.uc.mem_read(er.CUR_PATTERN, 1)[0]
rt.seq_select_live(final_bank, pattern); rt.internal_clock()
rt.frame = True; rt.next_frame = rt.sample + er.FRAME_PERIOD; rt.exact_clock()
rt.start_transport_live(); rt.install_trig_log()
frame0[0] = rt.frame_count + 1; target = frame0[0] + a.frames
rt.run(ms=a.frames * er.FRAME_PERIOD / er.SAMPLE_HZ * 1000.0 * 5 + 2000, until=lambda x: x.frame_count >= target)
print(f"frames {rt.frame_count - frame0[0]}/{a.frames}")
print("arms (frame, track, word, cf8):", [(f, t, hex(w), hex(c)) for f, t, w, c in arms])
print("fa84 after each arm (from converter rows):", sorted(set(p[7] for p in preds)))
last = None
for p in preds:
    key = (p[2], p[5] >> 4)
    if key != last or p is preds[-1]:
        f, t, lane, look, cf8, n, pred, fa84, L = p
        print(f"  f{f:5d} t{t} lane={lane:11.3f} look={look:10.3f} cf8={cf8:#x} n={n:6d} pred_next={pred:#x} ({pred}) arm={fa84:#x} L={L}")
    last = key
