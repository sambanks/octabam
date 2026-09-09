"""O9b, route A: what does a NOTE trig (a play trig on a FLEX track) write, and
where does it stop? Runs the r4_128 fixture (T2 = FLEX on R1, play trigs at
steps 2/6/10/14) to just past the first trig at frame 323 and logs, for the
trig frames, every write into the per-voice records (0x80000110..0x800004ff),
the per-track records (0x800021d0/0x80001c90 + ping*0xa80, 0x540 bytes each)
and the FLEX arena record of the track, with the writer's PC; plus every call
of the arm caller 0x40005ff0 with its args.

    .venv/bin/python tools/scratch/voiceprobe.py --project out/_fx2/r4_128 --tree out/_vp
"""
import argparse, sys, os, struct, collections
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import emu_rtos as er, emu_card as ec, emu_bringup as eb
from unicorn.m68k_const import *
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--tree", required=True)
ap.add_argument("--frames", type=int, default=340); ap.add_argument("--from-frame", type=int, default=318)
ap.add_argument("--track", type=int, default=1, help="0-based track with the play trig (T2)")
a = ap.parse_args()
card, name = er.stage_project(a.project, "OCTABAM", "RECT", tree=a.tree)
r, rt = er.attach(None, card)
uc = rt.uc
def rd(u, reg): return u.reg_read(reg) & 0xffffffff
W = []
def on_w(u, acc, addr, size, val, x):
    if rt.frame_count >= a.from_frame and len(W) < 20000:
        W.append((rt.frame_count, addr, size, val & 0xffffffff, rd(u, UC_M68K_REG_PC)))
REGIONS = [(0x80000110, 0x80000510), (0x800021d0, 0x800021d0 + 2 * 0xa80), (0x80001c90, 0x80001c90 + 2 * 0xa80),
           (0x46104d00, 0x46104d40), (0x100b14f0 + 128 * 1096, 0x100b14f0 + 136 * 1096)]   # FLEX arena ids 128..135 (R1..R8)
for lo, hi in REGIONS:
    uc.hook_add(UC_HOOK_MEM_WRITE, on_w, begin=lo, end=hi - 1)
C = []
def on_call(u, addr, size, x):
    if rt.frame_count >= a.from_frame and len(C) < 400:
        sp = rd(u, UC_M68K_REG_A7)
        C.append((rt.frame_count, addr, struct.unpack(">6I", u.mem_read(sp, 24))))
for pc in (0x40005ff0, 0x400068e4, 0x40005c7c, 0x40005304):
    uc.hook_add(UC_HOOK_CODE, on_call, begin=pc, end=pc)
uc.ctl_flush_tb()
if not rt.gate_m6a()[0]:
    rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
mounted, posted, saved_bank, final_bank, _ = rt.load_project_live("OCTABAM", name, run_ms=20000)
if final_bank != saved_bank: final_bank = rt.select_bank_live(saved_bank)
pattern = uc.mem_read(er.CUR_PATTERN, 1)[0]
rt.seq_select_live(final_bank, pattern); rt.internal_clock()
rt.frame = True; rt.next_frame = rt.sample + er.FRAME_PERIOD; rt.exact_clock()
rt.start_transport_live(); rt.install_trig_log()
frame0 = rt.frame_count + 1; target = frame0 + a.frames
rt.run(ms=a.frames * er.FRAME_PERIOD / er.SAMPLE_HZ * 1000.0 * 5 + 2000, until=lambda x: x.frame_count >= target)
print(f"frames {rt.frame_count - frame0}; live nibble writes {rt.live_nibble_log[:12]}; trig words {rt.trig_words_log[:6]}")
print("calls (frame, fn, [ret, args...]):")
for f, pc, st in C:
    print(f"  f{f} {pc:#x} " + " ".join(f"{x:#x}" for x in st))
print("writes by (region, pc):")
byk = collections.Counter()
for f, ad, sz, v, pc in W:
    reg = next(lo for lo, hi in REGIONS if lo <= ad < hi)
    byk[(f"{reg:#x}", f"{pc:#x}")] += 1
for k, n in sorted(byk.items()): print("  ", k, n)
print("writes in the trig frames, first 120 (frame addr size val pc):")
for f, ad, sz, v, pc in [w for w in W if 322 <= w[0] <= 326][:120]:
    print(f"  f{f} {ad:#x} ({sz}) <- {v:#x}  pc {pc:#x}")
