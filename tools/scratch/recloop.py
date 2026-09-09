"""Route A: a LOOPING recorder (trigs every 4 steps, RLEN 4) -- log every arm-caller entry,
every engine post, every state-byte write, with the sample clock, to measure the seam."""
import argparse, sys, os, struct
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import emu_rtos as er, emu_card as ec, emu_bringup as eb
from unicorn.m68k_const import *
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--tree", required=True)
ap.add_argument("--name", default="RECTRIG"); ap.add_argument("--frames", type=int, default=7000); ap.add_argument("--image", default=None)
a = ap.parse_args()
card, name = er.stage_project(a.project, "OCTABAM", a.name, tree=a.tree)
r, rt = er.attach(a.image, card)
ev = []
def rd(u, r): return u.reg_read(r) & 0xffffffff
def m32(u, ad): return int.from_bytes(u.mem_read(ad, 4), "big")
def stack(u, n=6):
    sp = rd(u, UC_M68K_REG_A7); return struct.unpack(f">{n}I", u.mem_read(sp, 4 * n))
def at(label, nargs=5):
    def h(u, addr, size, user):
        if len(ev) < 6000:
            st = stack(u, nargs + 1)
            ev.append((rt.frame_count, rt.sample, label, st, u.mem_read(0x80004f1c + 672, 40).hex(" ")))
    return h
for pc, label in ((0x40005ff0, "armcall"), (0x40005c7c, "post"), (0x40006edc, "endpost"), (0x40006b18, "armpost"), (0x40006ea8, "subframe"), (0x40006080, "bit7path")):
    rt.uc.hook_add(UC_HOOK_CODE, at(label), begin=pc, end=pc)
wr = []
def on_wr(u, acc, addr, size, val, user):
    if len(wr) < 2000: wr.append((rt.frame_count, rt.sample, addr, size, val & 0xffffffff, rd(u, UC_M68K_REG_PC)))
for bank in (0, 1):
    b = 0x80004f1c + bank * 672
    rt.uc.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=b + 2, end=b + 3)      # state byte, +3 recording flag
    rt.uc.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=b + 32, end=b + 35)    # +32 end/length
rt.uc.hook_add(UC_HOOK_MEM_WRITE, on_wr, begin=0x46c938d4, end=0x46c938d7)  # R1 control +16
rt.uc.ctl_flush_tb()
if not rt.gate_m6a()[0]:
    rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
mounted, posted, saved_bank, final_bank, _ = rt.load_project_live("OCTABAM", name, run_ms=20000)
if final_bank != saved_bank: final_bank = rt.select_bank_live(saved_bank)
pattern = rt.uc.mem_read(er.CUR_PATTERN, 1)[0]
rt.seq_select_live(final_bank, pattern); rt.internal_clock()
rt.frame = True; rt.next_frame = rt.sample + er.FRAME_PERIOD; rt.exact_clock()
rt.start_transport_live()
rt.install_trig_log()
frame0 = rt.frame_count + 1; target = frame0 + a.frames
rt.run(ms=a.frames * er.FRAME_PERIOD / er.SAMPLE_HZ * 1000.0 * 5 + 2000, until=lambda x: x.frame_count >= target)
print(f"frames {rt.frame_count - frame0}/{a.frames}, frame0={frame0}; trig words: {rt.trig_words_log[:12]}")
print("events (frame, sample, label, [ret, args...], bank1 t0 record):")
for f, s, label, st, rec in ev:
    print(f"  f{f-frame0:5d} [{s:10.1f}] {label:8s} ret={st[0]:#x} args=" + " ".join(f"{x:#x}" for x in st[1:]) + f"  rec={rec[:24]} +32={rec[96:108]}")
print("writes (state byte / +3 / +32 / R1 len):")
last = None
for f, s, ad, sz, v, pc in wr:
    key = (ad, v)
    if key != last: print(f"  f{f-frame0:5d} [{s:10.1f}] [{ad:#x}] <- {v:#x} ({sz}) pc {pc:#x}")
    last = key
