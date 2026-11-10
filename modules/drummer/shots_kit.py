#!/usr/bin/env python3
"""DRUMMER's KIT window on the panel under the port (TRIG 3 + BANK, DOWN DOWN, A +1, C +5, trig 6, YES),
one PNG per stage in out/drummer/ui; the card is verify_port.py's groove (T1 signed)."""
import subprocess, pathlib, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'out/drummer/ui'
def key(code, gap=.6, hold=.3): return [(gap, f"key {code:#x} down"), (hold, f"key {code:#x} up")]
open_ = key(0x10) + [(.6, 'key 0x2 down'), (.3, 'key 0x2f down'), (.2, 'key 0x2f up'), (.3, 'key 0x2 up')]
edit = open_ + key(0x20, .5, .1) + key(0x20, .5, .1) + [(.6, 'enc 0 1'), (.4, 'enc 2 5')]
jump = edit + key(0x5, .6, .1)
close = jump + key(0x31)
scripts = {'k1_open': open_ + [(1.0, 'quit')], 'k2_edit': edit + [(1.0, 'quit')], 'k3_jump': jump + [(1.0, 'quit')],
           'k4_close': close + [(1.0, 'quit')]}
def run(name):
    t, lines = 0.0, []
    for d, ev in scripts[name]:
        t += d; lines.append(f"{int(t*1000)} {ev}")
    sf = OUT / f'{name}.script'; sf.write_text("\n".join(lines) + "\n")
    lcd = OUT / f'{name}.lcd'
    cmd = [str(ROOT/'out/emu/ot_emu'), '--image', str(ROOT/'out/drummer/drummer_4c.bin'), '--card', str(ROOT/'out/drummer/port/groove/card.img'),
           '--set', 'OCTABAM', '--project', 'RIG', '--load-ms', '20000', '--main-level', '64', '--lcd', str(lcd), '--live-script', str(sf),
           '--watch-mem', '0x800049f8,1']
    with open(OUT/f'{name}.log', 'w') as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=1500)
    subprocess.run([str(ROOT/'.venv/bin/python3'), str(ROOT/'tools/emu/lcd_view.py'), str(lcd), '--png', str(OUT/f'{name}.png')], cwd=ROOT)
    return name, r.returncode
with cf.ThreadPoolExecutor(4) as ex:
    for name, rc in ex.map(run, scripts): print(name, rc)
