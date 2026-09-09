#!/usr/bin/env python3
"""One Flash-7 bus claim measured LIVE on pattern A01, with the variant set BY
HAND on the unit (the FX2 chooser hides the hosts, and a pattern/part change
drops the THRU source after ~5 s -- 9 Sep 2026 -- so program-change variants
could not be measured; a by-hand effect select on the stable A01 source can).

    python3 tools/hw/hw_flash7_liveclaim.py v      # T8 FX2 = SEND set by hand: the send is refused on the master
    python3 tools/hw/hw_flash7_liveclaim.py vii    # T4 FX1 = CHARACTER, RET up: T4 returns nothing, T8 still returns
    python3 tools/hw/hw_flash7_liveclaim.py iii    # T5 FX2 = SEND (reverb removed): repeats return, no reverb (fall-through)

Rig as tools/hw/hw_flash7.py: OT on UM-ONE, MicroBook out -> inputs A/B for the
1 kHz burst, MicroBook in captures the OT's main outs on channel 4. The Mac is
clock master. Judge vii-b by the return's ABSOLUTE presence (silence = the
pre-fix stolen-stamp bug), not the burst's noisy RET toggle."""
import sys, time, subprocess
claim = sys.argv[1]
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path); sys.argv=["x"]; import hw_flash7 as h
rig = h.Rig('UM-ONE', None, 'MicroBook', 3)
src = subprocess.Popen([str(h.TONE),"1000","90","MicroBook","0.1","80","610"], stdout=subprocess.PIPE, text=True); src.stdout.readline()
clk = h.Clock(rig.out, 121.0); clk.start(); time.sleep(3)
for t in range(1,9): rig.cc(t,h.CC_MUTE,0,0.02)
rig.cc(1,16,1); rig.cc(1,17,127); rig.cc(1,25,100)          # T1 THRU input
rig.cc(1,h.AUX,127); rig.cc(1,h.MIX,127); rig.cc(5,h.MIX,127); rig.cc(8,h.RET,127); rig.cc(8,h.AUX,0)
time.sleep(1.5)
base,_ = rig.level(2,"live_base"); h.log(f"  return present: {base:.1f} dBFS")
if base < -55:
    h.log("  STOP: no return -- is T1 passing / RET up?"); clk.close(); src.terminate(); sys.exit(1)

if claim == "v":     # SEND now on T8 FX2 (user set). T8's AUX must do nothing.
    c = rig.toggle(8, h.RET, 127, 0, "v_ret")
    t = rig.toggle(8, h.AUX, 0, 127, "v_t8aux"); rig.cc(8,h.AUX,0)
    ok = c["t"]>=3 and t["t"]<3
    h.log(f"  CLAIM v {'PASS' if ok else 'FAIL'}: RET |t|={c['t']:.1f} (control), T8 AUX |t|={t['t']:.1f} "
          f"(<3 = the send is refused on T8; audible = the pin is wrong)")
elif claim == "vii": # CHARACTER BUS now on T4 FX1 (user set), RET up.
    m = rig.toggle(4, h.CC_MUTE, 0, 127, "vii_t4mute"); rig.cc(4,h.CC_MUTE,0)
    c = rig.toggle(8, h.RET, 127, 0, "vii_t8ret")
    ok = abs(m["gap"])<2 and c["t"]>=3
    h.log(f"  CLAIM vii {'PASS' if ok else 'FAIL'}: T4 mute moves gaps {m['gap']:+.1f} dB (t {m['t']:.1f}, ~0 = T4 returns nothing); "
          f"T8 RET |t|={c['t']:.1f} (>=3 = T8 still returns beside the T4 station -- the 9-Sep stolen-stamp fix)")
elif claim == "iii": # T5 FX2 now NONE (user set). Repeats return, no reverb.
    d = rig.toggle(1, h.MIX, 127, 0, "iii_delaymix")
    r = rig.toggle(5, h.MIX, 127, 0, "iii_reverbmix"); rig.cc(5,h.MIX,127)
    ok = d["t"]>=3 and r["t"]<3
    h.log(f"  CLAIM iii {'PASS' if ok else 'FAIL'}: delay MIX |t|={d['t']:.1f} (>=3 = repeats still return); "
          f"reverb MIX |t|={r['t']:.1f} (<3 = no reverb effect present, the fall-through)")
rig.cc(8,h.RET,127); clk.close(); src.terminate()
