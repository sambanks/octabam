import argparse, sys, collections
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import emu_rtos as er, emu_card as ec, emu_bringup as eb
from unicorn import UC_HOOK_CODE
ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--tree", required=True)
ap.add_argument("--name", default="RECTRIG"); ap.add_argument("--frames", type=int, default=200)
ap.add_argument("--sites", required=True)
a = ap.parse_args()
sites = [int(x, 16) for x in open(a.sites).read().split()]
card, name = er.stage_project(a.project, "OCTABAM", a.name, tree=a.tree)
r, rt = er.attach(None, card)
hits = collections.Counter(); phase = {"seq": False}
def on(u, addr, size, user):
    hits[(addr, phase["seq"])] += 1
for s in sites: rt.uc.hook_add(UC_HOOK_CODE, on, begin=s, end=s)
rt.uc.ctl_flush_tb()
if not rt.gate_m6a()[0]:
    rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
mounted, posted, saved_bank, final_bank, _ = rt.load_project_live("OCTABAM", name, run_ms=20000)
if final_bank != saved_bank: final_bank = rt.select_bank_live(saved_bank)
pattern = rt.uc.mem_read(er.CUR_PATTERN, 1)[0]
rt.seq_select_live(final_bank, pattern); rt.internal_clock()
rt.frame = True; rt.next_frame = rt.sample + er.FRAME_PERIOD; rt.exact_clock()
rt.start_transport_live(); phase["seq"] = True
frame0 = rt.frame_count + 1; target = frame0 + a.frames
rt.run(ms=a.frames * er.FRAME_PERIOD / er.SAMPLE_HZ * 1000.0 * 5 + 2000, until=lambda x: x.frame_count >= target)
n = rt.frame_count - frame0
boot = sum(v for (s, p), v in hits.items() if not p); seq = sum(v for (s, p), v in hits.items() if p)
print(f"frames {n}; EMAC-site hits: boot+load {boot}, sequencer {seq} = {seq/max(n,1):.0f}/frame; emac_shims {getattr(r,'emac_shims',0)}")
for (s, p), v in sorted(hits.items(), key=lambda kv: -kv[1])[:25]: print(f"  {s:#x} {'seq' if p else 'boot'} {v}")
